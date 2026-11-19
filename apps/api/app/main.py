from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    frontend_origin: str = "http://localhost:5173"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
app = FastAPI(
    title="LFC Stream API",
    version="0.1.0",
    description="Cloud video broadcasting control plane for Google Drive media.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health", tags=["operations"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "lfc-stream-api", "environment": settings.app_env}


@app.get("/api/v1", tags=["operations"])
async def api_info() -> dict[str, str]:
    return {"name": "LFC Stream API", "version": "0.1.0", "status": " 초기".replace(" 초기", "initializing")}
