from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.user import UserOut, UserSyncPayload
from app.services import metadata_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/sync", response_model=UserOut, tags=["Users"])
async def sync_user_profile(
    payload: UserSyncPayload,
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    logger.info("Syncing user profile id=%s email=%s", payload.id, payload.email)
    user = await metadata_service.sync_user(
        db=db,
        user_id=payload.id,
        email=payload.email,
        name=payload.name,
        first_name=payload.first_name,
        last_name=payload.last_name,
        image_url=payload.image_url,
    )
    return UserOut.model_validate(user)


@router.get("/profile/{user_id}", response_model=UserOut, tags=["Users"])
async def get_user_profile(
    user_id: str,
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await metadata_service.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut.model_validate(user)
