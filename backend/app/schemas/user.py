from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class UserSyncPayload(BaseModel):
    id: str
    email: Optional[str] = None
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    image_url: Optional[str] = None


class UserOut(BaseModel):
    id: str
    email: Optional[str] = None
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    image_url: Optional[str] = None
    created_at: datetime
    last_sign_in_at: Optional[datetime] = None

    class Config:
        from_attributes = True
