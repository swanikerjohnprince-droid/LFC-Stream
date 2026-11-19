import json
import secrets
import re
import base64
import hashlib
import hmac
import time
from datetime import datetime, timezone
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse
from google.auth.transport.requests import AuthorizedSession, Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from redis import Redis
from sqlalchemy import DateTime, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Settings(BaseSettings):
    app_env: str = "development"
    frontend_origin: str = "http://localhost:5173"
    database_url: str = "postgresql+psycopg://lfcstream:lfcstream@db:5432/lfcstream"
    redis_url: str = "redis://redis:6379/0"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"
    token_encryption_key: str = ""
    admin_username: str = "admin"
    admin_password_hash: str = ""
    jwt_secret_key: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
app = FastAPI(
    title="LFC Stream API",
    version="0.2.0",
    description="Cloud video broadcasting control plane for Google Drive media.",
)
allowed_origins = list(dict.fromkeys([
    settings.frontend_origin,
    "http://localhost:5173",
    "http://localhost:8080",
]))
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


class Base(DeclarativeBase):
    pass


class GoogleConnection(Base):
    __tablename__ = "google_connections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    encrypted_credentials: Mapped[str] = mapped_column(String, nullable=False)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


def get_fernet() -> Fernet:
    if not settings.token_encryption_key:
        raise HTTPException(503, "TOKEN_ENCRYPTION_KEY is not configured.")
    try:
        return Fernet(settings.token_encryption_key.encode("utf-8"))
    except (ValueError, TypeError):
        raise HTTPException(503, "TOKEN_ENCRYPTION_KEY must be a valid Fernet key.")


def oauth_ready() -> None:
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(503, "Google OAuth is not configured. Add the client ID and secret to the server environment.")


def make_flow(state: str | None = None) -> Flow:
    oauth_ready()
    return Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.google_redirect_uri],
            }
        },
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
        state=state,
        redirect_uri=settings.google_redirect_uri,
    )


def load_credentials() -> Credentials:
    get_fernet()
    with SessionLocal() as session:
        row = session.get(GoogleConnection, 1)
        if row is None:
            raise HTTPException(409, "Google Drive is not connected.")
        try:
            payload = get_fernet().decrypt(row.encrypted_credentials.encode()).decode()
            credentials = Credentials.from_authorized_user_info(json.loads(payload))
        except (InvalidToken, ValueError, KeyError, TypeError):
            raise HTTPException(500, "Stored Google credentials could not be decrypted.")
    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(GoogleRequest())
            save_credentials(credentials)
        except Exception:
            raise HTTPException(401, "Google authorization expired. Reconnect Google Drive.")
    return credentials


def save_credentials(credentials: Credentials) -> None:
    encrypted = get_fernet().encrypt(credentials.to_json().encode()).decode()
    with SessionLocal() as session:
        row = session.get(GoogleConnection, 1)
        if row is None:
            row = GoogleConnection(id=1, encrypted_credentials=encrypted, connected_at=datetime.now(timezone.utc))
            session.add(row)
        else:
            row.encrypted_credentials = encrypted
        session.commit()


def drive_service() -> Any:
    return build("drive", "v3", credentials=load_credentials(), cache_discovery=False)


class LoginPayload(BaseModel):
    username: str
    password: str


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(_b64encode(actual), expected)
    except (ValueError, TypeError):
        return False


def _create_session(username: str) -> str:
    if not settings.jwt_secret_key:
        raise HTTPException(503, "JWT_SECRET_KEY is not configured.")
    now = int(time.time())
    header = _b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64encode(json.dumps({"sub": username, "iat": now, "exp": now + 43200}, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}".encode()
    signature = hmac.new(settings.jwt_secret_key.encode(), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64encode(signature)}"


def require_auth(session_cookie: str | None = Cookie(default=None, alias="lfc_session")) -> str:
    if not session_cookie or not settings.jwt_secret_key:
        raise HTTPException(401, "Please sign in to LFC Stream.")
    try:
        header, payload, signature = session_cookie.split(".")
        signing_input = f"{header}.{payload}".encode()
        expected = _b64encode(hmac.new(settings.jwt_secret_key.encode(), signing_input, hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid signature")
        claims = json.loads(_b64decode(payload))
        if claims.get("exp", 0) < int(time.time()) or claims.get("sub") != settings.admin_username:
            raise ValueError("Expired or invalid session")
        return claims["sub"]
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise HTTPException(401, "Your session has expired. Please sign in again.")


@app.post("/api/v1/auth/login", tags=["authentication"])
def login(payload: LoginPayload, response: Response) -> dict[str, bool]:
    if not settings.admin_password_hash or not settings.jwt_secret_key:
        raise HTTPException(503, "Dashboard login is not configured on the server.")
    valid_user = hmac.compare_digest(payload.username, settings.admin_username)
    valid_password = _verify_password(payload.password, settings.admin_password_hash)
    if not (valid_user and valid_password):
        raise HTTPException(401, "Incorrect username or password.")
    response.set_cookie(
        key="lfc_session",
        value=_create_session(settings.admin_username),
        max_age=43200,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        path="/",
    )
    return {"authenticated": True}


@app.post("/api/v1/auth/logout", tags=["authentication"])
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie("lfc_session", path="/", httponly=True, samesite="lax")
    return {"authenticated": False}


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.on_event("shutdown")
def shutdown() -> None:
    redis_client.close()
    engine.dispose()


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "lfc-stream-api", "environment": settings.app_env}


@app.get("/api/v1", tags=["operations"])
def api_info() -> dict[str, str]:
    return {"name": "LFC Stream API", "version": "0.2.0", "status": "initializing"}


@app.get("/api/v1/auth/google/start", tags=["google-drive"])
def google_oauth_start(_: str = Depends(require_auth)) -> RedirectResponse:
    oauth_ready()
    state = secrets.token_urlsafe(32)
    try:
        redis_client.setex(f"google-oauth-state:{state}", 600, "pending")
    except Exception:
        raise HTTPException(503, "OAuth state storage is unavailable. Check Redis.")
    flow = make_flow(state)
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return RedirectResponse(authorization_url, status_code=302)


@app.get("/api/v1/auth/google/callback", tags=["google-drive"])
def google_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    frontend = settings.frontend_origin.rstrip("/")
    if error:
        return RedirectResponse(f"{frontend}/?drive_error=authorization_denied")
    if not code or not state:
        raise HTTPException(400, "Missing OAuth callback parameters.")
    try:
        valid_state = redis_client.getdel(f"google-oauth-state:{state}")
    except Exception:
        raise HTTPException(503, "OAuth state storage is unavailable.")
    if valid_state != "pending":
        raise HTTPException(400, "OAuth state is invalid or expired. Please try connecting again.")
    flow = make_flow(state)
    try:
        flow.fetch_token(code=code)
        credentials = flow.credentials
        if not credentials.refresh_token:
            raise HTTPException(400, "Google did not return a refresh token. Disconnect the app in your Google Account and try again.")
        save_credentials(credentials)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "Google authorization could not be completed.")
    return RedirectResponse(f"{frontend}/?drive=connected")


@app.get("/api/v1/drive/status", tags=["google-drive"])
def google_drive_status(_: str = Depends(require_auth)) -> dict[str, Any]:
    with SessionLocal() as session:
        row = session.get(GoogleConnection, 1)
        if row is None:
            return {"connected": False}
        return {"connected": True, "connected_at": row.connected_at.isoformat()}


@app.get("/api/v1/drive/files", tags=["google-drive"])
def list_drive_files(
    parent_id: str | None = Query(default=None, max_length=200),
    search: str | None = Query(default=None, max_length=200),
    page_token: str | None = Query(default=None, max_length=2000),
    page_size: int = Query(default=50, ge=1, le=100),
    _: str = Depends(require_auth),
) -> dict[str, Any]:
    service = drive_service()
    clauses = ["trashed = false"]
    safe_parent = (parent_id or "root").replace("\\", "\\\\").replace("'", "\\'")
    clauses.append(f"'{safe_parent}' in parents")
    if search:
        safe_search = search.replace("\\", "\\\\").replace("'", "\\'")
        clauses.append(f"name contains '{safe_search}'")
    query = " and ".join(clauses)
    try:
        result = service.files().list(
            q=query,
            pageSize=page_size,
            pageToken=page_token,
            orderBy="folder,name",
            fields="nextPageToken,files(id,name,mimeType,size,modifiedTime,thumbnailLink,webViewLink,parents)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
    except Exception:
        raise HTTPException(502, "Could not retrieve files from Google Drive. Please retry.")
    items = []
    for item in result.get("files", []):
        mime = item.get("mimeType", "")
        items.append({
            "id": item["id"],
            "name": item.get("name", "Untitled"),
            "mime_type": mime,
            "kind": "folder" if mime == "application/vnd.google-apps.folder" else ("video" if mime.startswith("video/") else "file"),
            "size": item.get("size"),
            "modified_time": item.get("modifiedTime"),
            "thumbnail_url": item.get("thumbnailLink"),
            "web_view_url": item.get("webViewLink"),
            "parent_ids": item.get("parents", []),
        })
    return {"files": items, "next_page_token": result.get("nextPageToken")}



@app.get("/api/v1/drive/files/{file_id}/stream", tags=["google-drive"])
def stream_drive_video(
    file_id: str,
    range_header: str | None = Header(default=None, alias="Range"),
    _: str = Depends(require_auth),
) -> StreamingResponse:
    """Proxy a Drive video progressively and forward browser byte-range requests."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{5,200}", file_id):
        raise HTTPException(400, "Invalid Google Drive file ID.")

    credentials = load_credentials()
    service = build("drive", "v3", credentials=credentials, cache_discovery=False)
    try:
        metadata = service.files().get(
            fileId=file_id,
            fields="id,name,mimeType,size,trashed",
            supportsAllDrives=True,
        ).execute()
    except Exception:
        raise HTTPException(404, "The requested Drive file could not be found or accessed.")

    mime_type = metadata.get("mimeType", "")
    if metadata.get("trashed") or not mime_type.startswith("video/"):
        raise HTTPException(415, "Only video files can be streamed.")

    headers = {}
    if range_header:
        requested_range = range_header.strip()
        if not re.fullmatch(r"bytes=(\d+-\d*|-\d+)", requested_range):
            raise HTTPException(416, "Only a single valid byte range is supported.")
        headers["Range"] = requested_range

    media_url = "https://www.googleapis.com/drive/v3/files/" + file_id + "?alt=media"
    session = AuthorizedSession(credentials)
    try:
        upstream = session.get(media_url, headers=headers, stream=True, timeout=(15, 60))
    except Exception:
        session.close()
        raise HTTPException(502, "Google Drive could not start the video stream.")

    if upstream.status_code not in (200, 206, 416):
        status = upstream.status_code
        upstream.close()
        session.close()
        if status in (401, 403):
            raise HTTPException(403, "Google Drive denied access to this video.")
        raise HTTPException(502, "Google Drive returned an error while opening the video.")

    response_headers = {"Accept-Ranges": "bytes"}
    for header_name in ("Content-Length", "Content-Range"):
        if header_name in upstream.headers:
            response_headers[header_name] = upstream.headers[header_name]

    def chunks():
        try:
            for chunk in upstream.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    yield chunk
        finally:
            upstream.close()
            session.close()

    return StreamingResponse(
        chunks(),
        status_code=upstream.status_code,
        media_type=upstream.headers.get("Content-Type", mime_type),
        headers=response_headers,
    )


@app.post("/api/v1/drive/disconnect", tags=["google-drive"])
def disconnect_google_drive(_: str = Depends(require_auth)) -> dict[str, bool]:
    with SessionLocal() as session:
        row = session.get(GoogleConnection, 1)
        if row is not None:
            session.delete(row)
            session.commit()
    return {"disconnected": True}
