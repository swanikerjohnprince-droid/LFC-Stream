import json
import secrets
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from cryptography.fernet import Fernet, InvalidToken
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from pydantic_settings import BaseSettings, SettingsConfigDict
from redis import Redis
from sqlalchemy import DateTime, Integer, String, create_engine, select
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
def google_oauth_start() -> RedirectResponse:
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
def google_drive_status() -> dict[str, Any]:
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
) -> dict[str, Any]:
    service = drive_service()
    clauses = ["trashed = false"]
    if parent_id:
        safe_parent = parent_id.replace("\\", "\\\\").replace("'", "\\'")
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


@app.post("/api/v1/drive/disconnect", tags=["google-drive"])
def disconnect_google_drive() -> dict[str, bool]:
    with SessionLocal() as session:
        row = session.get(GoogleConnection, 1)
        if row is not None:
            session.delete(row)
            session.commit()
    return {"disconnected": True}
