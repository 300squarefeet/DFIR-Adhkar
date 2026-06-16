"""MFA enrollment / confirmation / disable / backup-code regeneration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adhkar.api.deps import CurrentUser, get_current_user, get_db, get_settings
from adhkar.auth.crypto import decrypt, encrypt
from adhkar.auth.mfa import generate_backup_codes, generate_seed, qr_png_data_url, verify_totp
from adhkar.auth.password import verify_password
from adhkar.core.settings import Settings
from adhkar.db.models import MfaSecret, User

router = APIRouter(prefix="/v1/auth/mfa", tags=["mfa"])


class EnrollResponse(BaseModel):
    secret: str
    qr_data_url: str
    issuer: str = "Adhkar"


class ConfirmRequest(BaseModel):
    code: str


class ConfirmResponse(BaseModel):
    backup_codes: list[str]


class DisableRequest(BaseModel):
    password: str
    code: str


@router.post("/enroll", response_model=EnrollResponse)
async def mfa_enroll(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EnrollResponse:
    db_user = (await db.execute(select(User).where(User.id == user.user_id))).scalar_one()
    existing = (
        await db.execute(select(MfaSecret).where(MfaSecret.user_id == user.user_id))
    ).scalar_one_or_none()
    if existing and existing.confirmed_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "mfa_already_enrolled")

    seed = generate_seed()
    encrypted = encrypt(seed.encode(), settings.secret_key)
    if existing:
        existing.seed_encrypted = encrypted
        existing.backup_codes_hash = []
        existing.backup_codes_used = []
        existing.confirmed_at = None
    else:
        db.add(
            MfaSecret(
                user_id=user.user_id,
                seed_encrypted=encrypted,
                backup_codes_hash=[],
                backup_codes_used=[],
            )
        )
    await db.flush()
    return EnrollResponse(
        secret=seed, qr_data_url=qr_png_data_url(seed, account_email=db_user.email)
    )


@router.post("/confirm", response_model=ConfirmResponse)
async def mfa_confirm(
    body: ConfirmRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConfirmResponse:
    row = (
        await db.execute(select(MfaSecret).where(MfaSecret.user_id == user.user_id))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "mfa_not_enrolling")
    if row.confirmed_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "mfa_already_confirmed")
    seed = decrypt(row.seed_encrypted, settings.secret_key).decode()
    if not verify_totp(seed, body.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "mfa_code_invalid")
    plain_codes, hashed_codes = generate_backup_codes()
    row.backup_codes_hash = hashed_codes
    row.backup_codes_used = []
    row.confirmed_at = datetime.now(tz=UTC)
    await db.flush()
    return ConfirmResponse(backup_codes=plain_codes)


@router.post("/disable", status_code=status.HTTP_204_NO_CONTENT)
async def mfa_disable(
    body: DisableRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    db_user = (await db.execute(select(User).where(User.id == user.user_id))).scalar_one()
    if not db_user.password_hash or not verify_password(db_user.password_hash, body.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials")
    row = (
        await db.execute(select(MfaSecret).where(MfaSecret.user_id == user.user_id))
    ).scalar_one_or_none()
    if not row or not row.confirmed_at:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "mfa_not_enrolled")
    seed = decrypt(row.seed_encrypted, settings.secret_key).decode()
    if not verify_totp(seed, body.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "mfa_code_invalid")
    await db.delete(row)
    await db.flush()


@router.post("/backup-codes/regenerate", response_model=ConfirmResponse)
async def mfa_regenerate_backup_codes(
    body: DisableRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConfirmResponse:
    db_user = (await db.execute(select(User).where(User.id == user.user_id))).scalar_one()
    if not db_user.password_hash or not verify_password(db_user.password_hash, body.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials")
    row = (
        await db.execute(select(MfaSecret).where(MfaSecret.user_id == user.user_id))
    ).scalar_one_or_none()
    if not row or not row.confirmed_at:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "mfa_not_enrolled")
    seed = decrypt(row.seed_encrypted, settings.secret_key).decode()
    if not verify_totp(seed, body.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "mfa_code_invalid")
    plain_codes, hashed_codes = generate_backup_codes()
    row.backup_codes_hash = hashed_codes
    row.backup_codes_used = []
    await db.flush()
    return ConfirmResponse(backup_codes=plain_codes)
