from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_TORCH", "1")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            str(Path(__file__).resolve().parents[2] / ".env"),
            str(Path(__file__).resolve().parents[1] / ".env"),
            ".env",
        ),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = ""
    sqlite_db_url: str = ""
    redis_url: str = ""
    gemini_api_key: str = ""
    gemini_model: str = ""
    query_rate_limit: str = "5/minute"
    ingest_rate_limit: str = "2/minute"
    cache_ttl_seconds: int = 3600

    app_dir: Path = Path(__file__).resolve().parents[1]

    @property
    def backend_dir(self) -> Path:
        return Path(__file__).resolve().parents[2]

    @property
    def chroma_db_path(self) -> Path:
        if self.sqlite_db_url and self.sqlite_db_url.startswith("sqlite:///"):
            raw_path = self.sqlite_db_url.replace("sqlite:///", "")
            p = Path(raw_path)
            if not p.is_absolute():
                backend_dir = Path(__file__).resolve().parents[2]
                return (backend_dir / p).resolve()
            return p
        return self.app_dir / "vector_db" / "chroma.sqlite3"

    @property
    def chroma_dir(self) -> Path:
        return self.chroma_db_path.parent

    @field_validator("app_dir", mode="before")
    @classmethod
    def resolve_app_dir(cls, v: str | Path) -> Path:
        p = Path(v)
        if not p.is_absolute():
            backend_dir = Path(__file__).resolve().parents[2]
            candidate = (backend_dir / p).resolve()
            if (candidate / "vector_db").exists() or (candidate / "news_database").exists():
                return candidate
            candidate_app = (Path(__file__).resolve().parents[1] / p).resolve()
            if (candidate_app / "vector_db").exists() or (candidate_app / "news_database").exists():
                return candidate_app
            return candidate
        return p

    fetch_interval_minutes: int = 20

    backend_cors_origins: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
