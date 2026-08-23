from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..cat_schemas import CatUserCreate
from ..database import get_db
from ..models import CatUser
from .auth import get_current_user_email

router = APIRouter(prefix="/api/v1/cat-note", tags=["cat-note"])


def to_response(user: CatUser) -> dict:
    """CatUser 한 줄을 응답 모양으로 바꿔주는 도우미"""
    return {
        "exists": True,
        "note_id": user.note_id,
        "partner": user.partner,
        "nickname": user.nickname,
        "bio": user.bio,
        "avatar": user.avatar,
        "learning_language": user.learning_language,
        "feedback_language": user.feedback_language,
        "writing_stage": user.writing_stage,
        "daily_reminder": user.daily_reminder,
    }


@router.get("/hello")
def hello():
    return {"message": "안녕! 콩이야 🐱"}


@router.get("/who")
def who(user_email: str = Depends(get_current_user_email)):
    return {"당신은": user_email}


@router.get("/me")
def get_me(
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """첫 진입 — 계정 있으면 정보, 없으면 exists: false"""
    user = db.scalar(select(CatUser).where(CatUser.user_email == user_email))
    if user is None:
        return {"exists": False}
    return to_response(user)


@router.post("/me", status_code=201)
def create_me(
    payload: CatUserCreate,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """계정 만들기 — 짝꿍과 수첩 아이디를 정하고 '수첩 만들기'를 누를 때"""
    # 한 사람이 수첩을 두 개 가질 순 없어요
    if db.scalar(select(CatUser).where(CatUser.user_email == user_email)):
        raise HTTPException(status_code=409, detail="이미 수첩이 있어요")

    # 아이디는 소문자로 통일해서 저장해요 (Jiwoo07 과 jiwoo07 을 같은 걸로)
    note_id = payload.note_id.lower()
    if db.scalar(select(CatUser).where(CatUser.note_id == note_id)):
        raise HTTPException(status_code=409, detail="이미 있는 아이디예요")

    user = CatUser(
        user_email=user_email,
        note_id=note_id,
        partner=payload.partner,
        nickname=payload.nickname,
        learning_language=payload.learning_language,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return to_response(user)
