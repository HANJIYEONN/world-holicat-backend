from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import HeadacheEntry
from ..schemas import EntryCreate, EntryOut, EntryUpdate
from .auth import get_current_user_email

router = APIRouter(prefix="/entries", tags=["entries"])


def find_owned_entry(entry_id: int, db: Session, user_email: str) -> HeadacheEntry:
    """내 기록(또는 로그인 기능 전에 만든 주인 없는 기록)만 찾아주는 도우미"""
    entry = db.get(HeadacheEntry, entry_id)
    # 주인이 다른 사람이면 존재 자체를 숨기려고 404로 답해요
    if entry is None or entry.user_email not in (None, user_email):
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없어요")
    return entry


@router.get("", response_model=list[EntryOut])
def list_entries(
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),  # 로그인 필수!
):
    return db.scalars(
        select(HeadacheEntry)
        # 내 기록 + 로그인 기능이 생기기 전의 옛 기록(주인 없음)을 함께 보여줘요
        .where(
            or_(
                HeadacheEntry.user_email == user_email,
                HeadacheEntry.user_email.is_(None),
            )
        )
        .order_by(HeadacheEntry.entry_date.desc())
    ).all()


@router.post("", response_model=EntryOut, status_code=201)
def create_entry(
    payload: EntryCreate,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    entry = HeadacheEntry(
        **payload.model_dump(), user_email=user_email
    )  # 기록에 주인 도장!
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/{entry_id}", response_model=EntryOut)
def get_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    return find_owned_entry(entry_id, db, user_email)


@router.put("/{entry_id}", response_model=EntryOut)
def update_entry(
    entry_id: int,
    payload: EntryUpdate,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    entry = find_owned_entry(entry_id, db, user_email)
    for key, value in payload.model_dump().items():
        setattr(entry, key, value)
    entry.user_email = user_email  # 옛 기록을 수정하면 그때 내 것으로 도장!
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=204)
def delete_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    entry = find_owned_entry(entry_id, db, user_email)
    db.delete(entry)
    db.commit()
