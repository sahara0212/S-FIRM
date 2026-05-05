"""인증 API — 로그인 / 내 정보 / 로그아웃"""
import hashlib
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_TOKEN_STORE: dict[str, str] = {}   # token → user_id


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginBody, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username, User.is_active == True).first()
    if not user or user.password_hash != _hash(body.password):
        raise HTTPException(401, "아이디 또는 비밀번호가 올바르지 않습니다.")

    token = secrets.token_urlsafe(32)
    _TOKEN_STORE[token] = user.id

    return {
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
            "client_id": user.client_id,
        },
    }


@router.get("/me")
def me(token: Optional[str] = None, db: Session = Depends(get_db)):
    if not token or token not in _TOKEN_STORE:
        raise HTTPException(401, "인증이 필요합니다.")

    user_id = _TOKEN_STORE[token]
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "유효하지 않은 토큰입니다.")

    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "client_id": user.client_id,
    }


@router.post("/logout")
def logout(token: Optional[str] = None):
    _TOKEN_STORE.pop(token, None)
    return {"status": "ok"}
