from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..blog_schemas import BlogUserCreate
from ..database import get_db
from ..models import BlogUser
from .auth import get_current_user_email

router = APIRouter(prefix="/api/v1/blog/users", tags=["blog-users"])


def user_response(user: BlogUser) -> dict:
    return {"exists": True, "nickname": user.nickname}


@router.get("/me")
def get_me(
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """로그인한 사람에게 블로그 닉네임이 있는지 확인해요."""
    user = db.scalar(select(BlogUser).where(BlogUser.user_email == user_email))
    if user is None:
        return {"exists": False}
    return user_response(user)


@router.post("/me", status_code=201)
def create_me(
    payload: BlogUserCreate,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """블로그 닉네임을 처음 한 번만 저장해요. 수정 API는 두지 않아요."""
    exists = db.scalar(select(BlogUser).where(BlogUser.user_email == user_email))
    if exists is not None:
        raise HTTPException(status_code=409, detail="블로그 닉네임은 바꿀 수 없어요")

    user = BlogUser(user_email=user_email, nickname=payload.nickname)
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="블로그 닉네임은 바꿀 수 없어요") from error
    db.refresh(user)
    return user_response(user)
