import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..cat_schemas import (
    NOTE_ID_MAX,
    NOTE_ID_MIN,
    NOTE_ID_PATTERN,
    CatUserCreate,
    CatUserUpdate,
)
from ..database import get_db
from ..models import CatUser
from ..writing_prompts import prompt_for
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


def note_id_problem(note_id: str, db: Session) -> str | None:
    """수첩 아이디를 못 쓰는 이유를 돌려줘요. 쓸 수 있으면 None.

    순서가 중요해요 — 사용자에게 **제일 도움 되는 이유 하나**만 알려주려고요.
    예를 들어 "지우"는 길이도 짧고 글자도 안 되는데, "영어와 숫자만 쓸 수 있어요"가
    더 쓸모 있는 안내라 그걸 먼저 봐요.
    """
    if not note_id:
        return "too_short"
    if not re.fullmatch(NOTE_ID_PATTERN, note_id):
        return "invalid_char"
    if len(note_id) < NOTE_ID_MIN:
        return "too_short"
    if len(note_id) > NOTE_ID_MAX:
        return "too_long"
    if db.scalar(select(CatUser).where(CatUser.note_id == note_id)):
        return "duplicate"
    return None


def suggest_note_ids(wanted: str, db: Session, how_many: int = 3) -> list[str]:
    """비슷하면서 **실제로 쓸 수 있는** 아이디를 몇 개 만들어줘요.

    'jiwoo07' 처럼 끝에 숫자가 붙어 있으면 그걸 떼고(jiwoo) 다른 걸 붙여봐요.
    후보를 만든 뒤 이미 쓰는 것들을 DB에서 **한 번에** 걸러내요.
    """
    base = re.sub(r"[^a-z0-9]", "", wanted.lower())[:NOTE_ID_MAX]
    stem = base.rstrip("0123456789") or base or "cat"

    candidates = [f"{stem}{n}" for n in (1, 7, 22, 99, 2026)]
    candidates += [f"happy{stem}", f"{stem}cat", f"my{stem}"]

    # 길이 규칙에 맞고, 원래 쓰려던 것과 다른 것만
    candidates = [
        c for c in candidates if NOTE_ID_MIN <= len(c) <= NOTE_ID_MAX and c != base
    ]

    # 이미 쓰는 아이디를 한 번의 조회로 걸러내요 (후보마다 조회하면 느려요)
    taken = set(
        db.scalars(select(CatUser.note_id).where(CatUser.note_id.in_(candidates))).all()
    )

    picked: list[str] = []
    for c in candidates:
        if c not in taken and c not in picked:
            picked.append(c)
        if len(picked) == how_many:
            break
    return picked


@router.get("/note-id/check")
def check_note_id(
    value: str,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """수첩 아이디를 쓸 수 있는지 알려줘요 — 아이디 만들기 화면(2g)에서 써요.

    타이핑할 때마다가 아니라 **잠깐 멈췄을 때** 한 번 부르는 게 좋아요.
    못 쓰면 이유(reason)와 대신 쓸 만한 후보(suggestions)를 함께 줘요.
    """
    candidate = value.strip().lower()  # 대소문자 구분 안 함 (D-10)

    reason = note_id_problem(candidate, db)
    if reason is None:
        return {"available": True, "reason": None, "suggestions": []}

    return {
        "available": False,
        "reason": reason,
        "suggestions": suggest_note_ids(candidate, db),
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


@router.patch("/me")
def update_me(
    payload: CatUserUpdate,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """내 정보 수정 — 내 정보 탭(시안 2f)에서 써요.

    **보낸 항목만** 바꿔요. 안 보낸 건 그대로 둬요.
    예: {"nickname": "지우"} 만 보내면 별명만 바뀌고 나머지는 안 건드려요.

    짝꿍(partner)도 바꿀 수 있어요 — 말투만 정하는 거라 데이터·친구 관계에
    영향이 없거든요 (D-17).
    """
    user = db.scalar(select(CatUser).where(CatUser.user_email == user_email))
    if user is None:
        raise HTTPException(status_code=404, detail="아직 수첩이 없어요")

    # exclude_unset=True → 진짜로 보낸 항목만 꺼내요.
    # 이게 없으면 안 보낸 항목까지 None 으로 덮어써버려요.
    changes = payload.model_dump(exclude_unset=True)

    for field, value in changes.items():
        setattr(user, field, value)

    if changes:
        db.commit()
        db.refresh(user)

    return to_response(user)


@router.get("/prompts/today")
def today_prompt(
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """오늘의 글감 — "오늘 뭐 쓰지?" 하고 막힐 때 보여줘요 (WRITE-02).

    같은 날이면 몇 번을 불러도 **같은 글감**이 나와요. 쓰는 도중에 질문이
    바뀌면 당황스러우니까요.

    글감은 사용자가 **설명받을 언어**로 나와요 — "무엇을 쓸지" 알려주는
    안내라서, 배우는 언어가 아니라 알아듣는 언어여야 해요.
    """
    user = db.scalar(select(CatUser).where(CatUser.user_email == user_email))
    language = None
    if user is not None:
        language = user.feedback_language or user.learning_language

    return {"prompt": prompt_for(date.today(), language)}
