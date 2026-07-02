"""Auth routes. Mirrors apps/api/src/routes/auth.ts."""

from __future__ import annotations

from fastapi import APIRouter

from leadforge_api.core.deps import CurrentUser, CurrentUserId, DBSession
from leadforge_api.core.response import success
from leadforge_api.core.security import create_access_token
from leadforge_api.schemas import (
    AuthResponse,
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from leadforge_api.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=None)
async def register(body: RegisterRequest, session: DBSession) -> dict:
    user = await auth_service.register(session, body.email, body.password, body.full_name)
    token = create_access_token(user.id, user.email)
    return success(AuthResponse(user=UserResponse.model_validate(user), token=token).model_dump())


@router.post("/login", response_model=None)
async def login(body: LoginRequest, session: DBSession) -> dict:
    user = await auth_service.login(session, body.email, body.password)
    token = create_access_token(user.id, user.email)
    return success(TokenResponse(token=token, user=UserResponse.model_validate(user)).model_dump())


@router.get("/me", response_model=None)
async def me(user: CurrentUser) -> dict:
    return success(UserResponse.model_validate(user).model_dump(mode="json"))


@router.put("/me", response_model=None)
async def update_me(body: UpdateProfileRequest, user_id: CurrentUserId, session: DBSession) -> dict:
    updated = await auth_service.update_profile(
        session,
        user_id,
        full_name=body.full_name,
        email=body.email,
    )
    return success(UserResponse.model_validate(updated).model_dump(mode="json"))


@router.put("/password", response_model=None)
async def change_password(
    body: ChangePasswordRequest, user_id: CurrentUserId, session: DBSession
) -> dict:
    await auth_service.change_password(
        session,
        user_id,
        body.current_password,
        body.new_password,
    )
    return success({"changed": True})
