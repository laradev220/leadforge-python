"""Auth service. Mirrors apps/api/src/services/auth-service.ts."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from leadforge_api.core.errors import conflict, unauthorized
from leadforge_api.core.security import hash_password, verify_password
from leadforge_database.models import User


async def register(
    session: AsyncSession, email: str, password: str, full_name: str | None
) -> User:
    result = await session.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none() is not None:
        raise conflict("Email already registered")

    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise conflict("Email already registered") from e
    await session.refresh(user)
    return user


async def login(session: AsyncSession, email: str, password: str) -> User:
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        raise unauthorized("Invalid email or password")
    if not user.is_active:
        raise unauthorized("Account is inactive")
    return user


async def get_by_id(session: AsyncSession, user_id) -> User:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise unauthorized("User not found")
    return user
