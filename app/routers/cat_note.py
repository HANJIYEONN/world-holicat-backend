import re
from datetime import date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..ai_grader import accuracy_percent, grade_sentences
from ..cat_schemas import (
    FRIEND_LIMIT,
    MEANING_MAX,
    NOTE_ID_MAX,
    NOTE_ID_MIN,
    NOTE_ID_PATTERN,
    SENTENCES_PER_ENTRY,
    CatUserCreate,
    CatUserUpdate,
    CommentCreate,
    FriendRequest,
    SentenceSave,
    VocabCreate,
)
from ..database import get_db
from ..models import (
    CatComment,
    CatCorrection,
    CatEntry,
    CatFriendship,
    CatPraise,
    CatSentence,
    CatUser,
    CatVocabItem,
)
from ..writing_prompts import prompt_for
from .auth import get_current_user_email

router = APIRouter(prefix="/api/v1/cat-note", tags=["cat-note"])


def vocab_count_of(db: Session, user_id: int) -> int:
    """단어장에 모은 표현 개수. 단계를 세는 기준이에요 (D-23)."""
    return db.scalar(
        select(func.count(CatVocabItem.id)).where(CatVocabItem.cat_user_id == user_id)
    ) or 0


def to_response(user: CatUser, db: Session) -> dict:
    """CatUser 한 줄을 응답 모양으로 바꿔주는 도우미.

    writing_stage 는 **저장된 값을 쓰지 않고 그때그때 세요** (D-23).
    저장해두면 GET /me 와 GET /stats 가 서로 다른 단계를 말할 수 있거든요.
    """
    return {
        "exists": True,
        "note_id": user.note_id,
        "partner": user.partner,
        "nickname": user.nickname,
        "bio": user.bio,
        "avatar": user.avatar,
        "learning_language": user.learning_language,
        "feedback_language": user.feedback_language,
        "writing_stage": stage_of(vocab_count_of(db, user.id)),
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
    return to_response(user, db)


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
    return to_response(user, db)


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

    return to_response(user, db)


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


# ══════════════════════════════════════════════════════════
#  2장 — 쓰기
# ══════════════════════════════════════════════════════════


def require_user(db: Session, user_email: str) -> CatUser:
    """수첩 주인을 찾아와요. 아직 안 만들었으면 404."""
    user = db.scalar(select(CatUser).where(CatUser.user_email == user_email))
    if user is None:
        raise HTTPException(status_code=404, detail="아직 수첩이 없어요")
    return user


def today_entry(db: Session, user: CatUser) -> CatEntry:
    """오늘 수첩을 가져와요. 없으면 빈 수첩을 만들어서 줘요."""
    today = date.today()
    where = (CatEntry.cat_user_id == user.id, CatEntry.entry_date == today)

    entry = db.scalar(select(CatEntry).where(*where))
    if entry is not None:
        return entry

    entry = CatEntry(cat_user_id=user.id, entry_date=today)
    db.add(entry)
    try:
        db.commit()
    except IntegrityError:
        # 요청 두 개가 거의 동시에 오면 둘 다 "오늘 것이 없네?" 하고 만들려 해요.
        # 늦은 쪽은 uq_cat_entry_user_date 규칙에 막히는데, 그게 정상이에요.
        # 먼저 만들어진 수첩을 다시 찾아서 쓰면 돼요.
        db.rollback()
        return db.scalar(select(CatEntry).where(*where))
    db.refresh(entry)
    return entry


def sentences_of(db: Session, entry: CatEntry) -> list[CatSentence]:
    """그 수첩의 문장들을 1번부터 순서대로."""
    return list(
        db.scalars(
            select(CatSentence)
            .where(CatSentence.entry_id == entry.id)
            .order_by(CatSentence.position)
        )
    )


def graded_sentences(db: Session, entry: CatEntry) -> list[dict]:
    """채점이 끝난 문장들을 응답 모양으로 바꿔요.

    새로 채점했든 예전 것을 다시 열어봤든 **항상 같은 모양**이 나오게 하려고
    저장된 값에서만 만들어요.
    """
    result = []
    for sentence in sentences_of(db, entry):
        corrections = db.scalars(
            select(CatCorrection)
            .where(CatCorrection.sentence_id == sentence.id)
            .order_by(CatCorrection.id)
        )
        result.append(
            {
                "position": sentence.position,
                "original_text": sentence.original_text,
                "corrected_text": sentence.corrected_text,
                # 번역은 교정 카드에 같이 나와요 (D-20). 따로 부르는 API 는 없어요.
                "translation": sentence.translation,
                "corrections": [
                    {
                        # 단어장에 담을 때(5장) 이 번호가 필요해요
                        "correction_id": c.id,
                        "wrong_text": c.wrong_text,
                        "right_text": c.right_text,
                        "note": c.note,
                        "pronunciation": c.pronunciation,
                    }
                    for c in corrections
                ],
            }
        )
    return result


def learned_expressions(graded: list[dict]) -> list[str]:
    """새로 배운 표현 = 오늘 고쳐준 것들 (중복 빼고 순서대로).

    AI 도 new_expressions 를 따로 돌려주지만 저장할 칸이 없어요.
    교정에서 그때그때 뽑아 쓰면 다시 열어봐도 늘 같은 목록이 나와요.
    """
    learned = []
    for sentence in graded:
        for correction in sentence["corrections"]:
            if correction["right_text"] not in learned:
                learned.append(correction["right_text"])
    return learned


def streak_and_stamps(db: Session, user: CatUser) -> tuple[int, int]:
    """(연속 기록 일수, 발도장 개수)

    발도장은 다 쓴 날의 개수예요.
    연속 기록은 오늘부터 하루씩 거슬러 올라가다가 빈 날을 만나면 멈춰요.
    """
    done = set(
        db.scalars(
            select(CatEntry.entry_date).where(
                CatEntry.cat_user_id == user.id, CatEntry.is_complete.is_(True)
            )
        )
    )
    streak = 0
    day = date.today()
    while day in done:
        streak += 1
        day -= timedelta(days=1)
    return streak, len(done)


@router.get("/entries/today")
def read_today_entry(
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """오늘 수첩 가져오기 — 홈 화면과 쓰기 화면에서 써요."""
    user = require_user(db, user_email)
    entry = today_entry(db, user)
    return {
        "entry_id": entry.id,
        "entry_date": entry.entry_date.isoformat(),
        "is_complete": entry.is_complete,
        "accuracy": entry.accuracy,
        # 쓰는 중엔 교정을 안 보여줘요 (D-12) — 그래서 쓴 글만 그대로 돌려줘요.
        "sentences": [
            {"position": s.position, "text": s.original_text}
            for s in sentences_of(db, entry)
        ],
    }


@router.put("/entries/today/sentences/{position}")
def save_sentence(
    position: Annotated[int, Path(ge=1, le=SENTENCES_PER_ENTRY)],
    payload: SentenceSave,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """문장 한 개 저장 — 쓸 때마다 바로 불러요 (NF-06, 글이 유실되면 안 돼요)."""
    user = require_user(db, user_email)
    entry = today_entry(db, user)
    if entry.is_complete:
        raise HTTPException(status_code=400, detail="오늘 수첩은 이미 다 냈어요")

    sentence = db.scalar(
        select(CatSentence).where(
            CatSentence.entry_id == entry.id, CatSentence.position == position
        )
    )
    if sentence is None:
        sentence = CatSentence(
            entry_id=entry.id, position=position, original_text=payload.text
        )
        db.add(sentence)
    else:
        sentence.original_text = payload.text

    db.commit()
    db.refresh(sentence)
    return {
        "position": sentence.position,
        "text": sentence.original_text,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }


@router.post("/entries/today/complete")
def complete_today_entry(
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """다 썼어요! — AI 채점은 하루에 여기서 딱 한 번만 해요 (D-12)."""
    user = require_user(db, user_email)
    entry = today_entry(db, user)

    # 이미 낸 수첩이면 저장해둔 결과를 그대로 돌려줘요.
    # 💸 여기서 AI 를 다시 부르면 같은 글에 돈을 두 번 내게 돼요.
    if not entry.is_complete:
        written = [s for s in sentences_of(db, entry) if s.original_text.strip()]
        if len(written) < SENTENCES_PER_ENTRY:
            raise HTTPException(
                status_code=400,
                detail=f"아직 다 못 썼어요 ({len(written)}/{SENTENCES_PER_ENTRY})",
            )

        result = grade_sentences(
            [s.original_text for s in written],
            learning_language=user.learning_language,
            feedback_language=user.feedback_language,
            partner=user.partner,
        )

        # 우리가 보낸 순서대로 짝을 지어요.
        # AI 가 알려준 position 을 그대로 믿었다가 번호가 밀리면
        # 엉뚱한 문장에 교정이 붙어버려요.
        for sentence, grade in zip(written, result.sentences):
            sentence.corrected_text = grade.corrected_text
            sentence.translation = grade.translation
            for correction in grade.corrections:
                db.add(
                    CatCorrection(
                        sentence_id=sentence.id,
                        wrong_text=correction.wrong_text,
                        right_text=correction.right_text,
                        note=correction.note,
                        pronunciation=correction.pronunciation,
                    )
                )

        entry.is_complete = True
        entry.completed_at = datetime.now()
        entry.accuracy = accuracy_percent(result)
        db.commit()

    graded = graded_sentences(db, entry)
    streak, stamps = streak_and_stamps(db, user)
    return {
        "entry_id": entry.id,
        "is_complete": entry.is_complete,
        "accuracy": entry.accuracy,
        "sentences": graded,
        "new_expressions": learned_expressions(graded),
        "streak_days": streak,
        "total_stamps": stamps,
    }


# ══════════════════════════════════════════════════════════
#  3장 — 기록 보기 (달력 · 통계)
# ══════════════════════════════════════════════════════════

# 단계 규칙 — 표현을 50개 모을 때마다 한 단계 올라가요.
# 명세서 예시(단어 124개 → "중급 1", 다음까지 26개)에 맞춘 값이에요.
EXPRESSIONS_PER_LEVEL = 50
LEVEL_NAMES = ["초급 1", "초급 2", "중급 1", "중급 2", "고급 1", "고급 2"]


def stage_of(vocab_count: int) -> int:
    """내 단계 번호 (1~6). 표현 50개마다 하나씩 올라가요 (D-23).

    GET /me 의 writing_stage 와 GET /stats 의 level 이 여기 하나를 같이 봐요.
    """
    return min(vocab_count // EXPRESSIONS_PER_LEVEL + 1, len(LEVEL_NAMES))


def level_of(vocab_count: int) -> tuple[str, int]:
    """(단계 이름, 다음 단계까지 남은 표현 수)

    마지막 단계에 닿으면 더 올라갈 곳이 없어서 남은 개수는 0이에요.
    """
    stage = stage_of(vocab_count)
    if stage == len(LEVEL_NAMES):
        return LEVEL_NAMES[-1], 0
    return LEVEL_NAMES[stage - 1], stage * EXPRESSIONS_PER_LEVEL - vocab_count


def average_accuracy(db: Session, user: CatUser, since: date, until: date) -> int | None:
    """그 기간에 다 쓴 날들의 정확도 평균. 쓴 날이 없으면 None.

    0 이 아니라 None 인 이유 — 아직 안 쓴 사람에게 "정확도 0%"라고
    보여주면 못했다는 뜻으로 읽혀요. 화면에서 카드를 숨길 수 있게 None 을 줘요.
    """
    scores = list(
        db.scalars(
            select(CatEntry.accuracy).where(
                CatEntry.cat_user_id == user.id,
                CatEntry.is_complete.is_(True),
                CatEntry.accuracy.is_not(None),
                CatEntry.entry_date >= since,
                CatEntry.entry_date <= until,
            )
        )
    )
    if not scores:
        return None
    return round(sum(scores) / len(scores))


@router.get("/entries")
def read_month_entries(
    year: Annotated[int, Query(ge=2000, le=2100)],
    month: Annotated[int, Query(ge=1, le=12)],
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """달력 화면용 — 그 달 어느 날에 발도장이 있는지."""
    user = require_user(db, user_email)

    first_day = date(year, month, 1)
    # 그 달의 마지막 날을 직접 세는 대신 "다음 달 1일보다 앞" 으로 잡아요.
    # 그러면 28일·29일·30일·31일을 따로 신경 쓰지 않아도 돼요.
    next_month_first = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

    entries = db.scalars(
        select(CatEntry)
        .where(
            CatEntry.cat_user_id == user.id,
            CatEntry.entry_date >= first_day,
            CatEntry.entry_date < next_month_first,
        )
        .order_by(CatEntry.entry_date)
    )
    days = [
        {
            "date": entry.entry_date.isoformat(),
            "is_complete": entry.is_complete,
            "accuracy": entry.accuracy,
        }
        for entry in entries
    ]
    return {
        "days": days,
        "total_stamps_this_month": sum(1 for day in days if day["is_complete"]),
    }


@router.get("/stats")
def read_stats(
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """홈 화면 숫자 카드들 — 저장해둔 값이 아니라 부를 때마다 세는 값이에요."""
    user = require_user(db, user_email)
    streak, stamps = streak_and_stamps(db, user)

    # 내 수첩들이 받은 칭찬도장 개수
    praises = db.scalar(
        select(func.count(CatPraise.id))
        .join(CatEntry, CatPraise.entry_id == CatEntry.id)
        .where(CatEntry.cat_user_id == user.id)
    )
    vocab_count = vocab_count_of(db, user.id)

    today = date.today()
    this_week = average_accuracy(db, user, today - timedelta(days=6), today)
    last_week = average_accuracy(db, user, today - timedelta(days=13), today - timedelta(days=7))
    # 지난주에 쓴 날이 없으면 비교할 게 없어요 — 그래서 0 이 아니라 None.
    diff = None if this_week is None or last_week is None else this_week - last_week

    level, to_next = level_of(vocab_count)
    return {
        "streak_days": streak,
        "total_stamps": stamps,
        "praises_received": praises or 0,
        "weekly_accuracy": this_week,
        "weekly_accuracy_diff": diff,
        "vocab_count": vocab_count,
        "level": level,
        "expressions_to_next_level": to_next,
    }


# ⚠️ 이 API는 파일 맨 아래에 있어야 해요.
# /entries/today 보다 먼저 등록되면 "today" 를 날짜로 읽으려다 실패해요.
# FastAPI 는 먼저 등록된 주소부터 맞춰보거든요.
@router.get("/entries/{entry_date}")
def read_entry_by_date(
    entry_date: date,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """지난 날짜 수첩 펼쳐보기 — 채점 결과까지 같이 나와요."""
    user = require_user(db, user_email)
    entry = db.scalar(
        select(CatEntry).where(
            CatEntry.cat_user_id == user.id, CatEntry.entry_date == entry_date
        )
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="그날은 쓴 수첩이 없어요")

    graded = graded_sentences(db, entry)
    return {
        "entry_id": entry.id,
        "entry_date": entry.entry_date.isoformat(),
        "is_complete": entry.is_complete,
        "accuracy": entry.accuracy,
        "sentences": graded,
        "new_expressions": learned_expressions(graded),
    }


# ══════════════════════════════════════════════════════════
#  4장 — 친구
# ══════════════════════════════════════════════════════════


def user_card(user: CatUser) -> dict:
    """친구 목록·검색에 보여줄 최소 정보. 이메일 같은 건 절대 안 나가요."""
    return {"note_id": user.note_id, "nickname": user.nickname, "avatar": user.avatar}


def friendship_between(db: Session, one_id: int, other_id: int) -> CatFriendship | None:
    """두 사람 사이의 관계. 누가 먼저 신청했든 하나로 찾아요."""
    return db.scalar(
        select(CatFriendship).where(
            or_(
                and_(
                    CatFriendship.requester_id == one_id,
                    CatFriendship.receiver_id == other_id,
                ),
                and_(
                    CatFriendship.requester_id == other_id,
                    CatFriendship.receiver_id == one_id,
                ),
            )
        )
    )


def friend_ids(db: Session, user_id: int) -> list[int]:
    """수락된 친구들의 id. 내가 신청한 것과 받은 것을 합쳐서 봐요 (D-22)."""
    rows = db.execute(
        select(CatFriendship.requester_id, CatFriendship.receiver_id).where(
            CatFriendship.status == "accepted",
            or_(
                CatFriendship.requester_id == user_id,
                CatFriendship.receiver_id == user_id,
            ),
        )
    ).all()
    return [
        row.receiver_id if row.requester_id == user_id else row.requester_id
        for row in rows
    ]


def ensure_friend_room(db: Session, user_id: int, message: str) -> None:
    """친구 자리가 남았는지 확인해요. 꽉 찼으면 409."""
    if len(friend_ids(db, user_id)) >= FRIEND_LIMIT:
        raise HTTPException(status_code=409, detail=message)


FULL_ME = f"친구는 {FRIEND_LIMIT}명까지 사귈 수 있어요"
FULL_THEM = "그 친구는 이미 친구가 가득 찼어요"


def friend_entry(
    db: Session, entry_id: int, user: CatUser, allow_own: bool = False
) -> CatEntry:
    """친구 수첩을 꺼내오되, 볼 자격이 있는지 먼저 확인해요.

    남의 수첩을 id만 바꿔가며 훔쳐보지 못하게 막는 자리예요.
    """
    entry = db.get(CatEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="그런 수첩이 없어요")
    if entry.cat_user_id == user.id:
        if allow_own:
            return entry
        raise HTTPException(status_code=403, detail="내 수첩에는 칭찬도장을 못 줘요")
    if entry.cat_user_id not in friend_ids(db, user.id):
        raise HTTPException(status_code=403, detail="친구의 수첩만 볼 수 있어요")
    return entry


def comment_card(comment: CatComment, writer: CatUser) -> dict:
    return {
        "comment_id": comment.id,
        "note_id": writer.note_id,
        "nickname": writer.nickname,
        "avatar": writer.avatar,
        "content": comment.content,
        "created_at": comment.created_at.isoformat(timespec="seconds")
        if comment.created_at
        else None,
    }


@router.get("/users/search")
def search_user(
    note_id: Annotated[str, Query(min_length=NOTE_ID_MIN, max_length=NOTE_ID_MAX)],
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """수첩 아이디로 찾기 — **정확히 같을 때만** 찾아져요 (NF-04).

    "민" 만 넣어도 찾아지면 모르는 어른이 아이들을 훑을 수 있어요.
    그래서 부분 검색은 일부러 안 만들어요.
    """
    require_user(db, user_email)
    found = db.scalar(select(CatUser).where(CatUser.note_id == note_id.lower()))
    if found is None:
        return {"found": False}
    return {"found": True, **user_card(found)}


@router.get("/friends")
def read_friends(
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """내 친구 목록 + 나에게 온 친구 신청."""
    user = require_user(db, user_email)

    ids = friend_ids(db, user.id)
    friends = (
        db.scalars(select(CatUser).where(CatUser.id.in_(ids)).order_by(CatUser.nickname))
        if ids
        else []
    )

    waiting = db.execute(
        select(CatFriendship, CatUser)
        .join(CatUser, CatFriendship.requester_id == CatUser.id)
        .where(CatFriendship.receiver_id == user.id, CatFriendship.status == "pending")
        .order_by(CatFriendship.id)
    ).all()

    return {
        "friends": [user_card(friend) for friend in friends],
        "pending_received": [
            {"friendship_id": friendship.id, **user_card(sender)}
            for friendship, sender in waiting
        ],
        # 화면에 "내 친구 4 / 10" 을 그릴 때 10을 프론트에 또 적지 않게 같이 내려줘요
        "max_friends": FRIEND_LIMIT,
    }


@router.post("/friends", status_code=201)
def request_friend(
    payload: FriendRequest,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """친구 신청 — 수첩 아이디로."""
    user = require_user(db, user_email)

    target = db.scalar(select(CatUser).where(CatUser.note_id == payload.note_id.lower()))
    if target is None:
        raise HTTPException(status_code=404, detail="그런 수첩 아이디를 못 찾았어요")
    if target.id == user.id:
        raise HTTPException(status_code=400, detail="나에게는 친구 신청을 못 해요")
    if friendship_between(db, user.id, target.id) is not None:
        raise HTTPException(status_code=409, detail="이미 친구이거나 신청했어요")

    ensure_friend_room(db, user.id, FULL_ME)
    ensure_friend_room(db, target.id, FULL_THEM)

    friendship = CatFriendship(
        requester_id=user.id, receiver_id=target.id, status="pending"
    )
    db.add(friendship)
    db.commit()
    db.refresh(friendship)
    return {
        "friendship_id": friendship.id,
        "status": friendship.status,
        **user_card(target),
    }


@router.post("/friends/{friendship_id}/accept")
def accept_friend(
    friendship_id: int,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """친구 신청 수락 — 받은 사람만 할 수 있어요."""
    user = require_user(db, user_email)

    friendship = db.get(CatFriendship, friendship_id)
    # 내가 받은 신청이 아니면 "없다" 고 해요.
    # 403 이라고 하면 "그 번호의 신청은 있구나" 를 알려주는 셈이거든요.
    if friendship is None or friendship.receiver_id != user.id:
        raise HTTPException(status_code=404, detail="그런 친구 신청이 없어요")
    if friendship.status == "accepted":
        raise HTTPException(status_code=409, detail="이미 친구예요")

    # 신청할 땐 자리가 있었어도 그 사이에 찼을 수 있어서 양쪽 다 다시 봐요 (D-22)
    ensure_friend_room(db, user.id, FULL_ME)
    ensure_friend_room(db, friendship.requester_id, FULL_THEM)

    friendship.status = "accepted"
    db.commit()
    return {
        "friendship_id": friendship.id,
        "status": "accepted",
        **user_card(db.get(CatUser, friendship.requester_id)),
    }


@router.delete("/friends/{friendship_id}", status_code=204)
def remove_friend(
    friendship_id: int,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """거절 · 친구 끊기 — 신청한 쪽도 받은 쪽도 지울 수 있어요."""
    user = require_user(db, user_email)

    friendship = db.get(CatFriendship, friendship_id)
    if friendship is None or user.id not in (
        friendship.requester_id,
        friendship.receiver_id,
    ):
        raise HTTPException(status_code=404, detail="그런 친구가 없어요")

    db.delete(friendship)
    db.commit()


@router.get("/friends/feed")
def read_friend_feed(
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """친구들의 **오늘** 수첩. 오늘 아직 시작 안 한 친구는 안 나와요."""
    user = require_user(db, user_email)

    ids = friend_ids(db, user.id)
    if not ids:
        return {"feed": []}

    rows = db.execute(
        select(CatEntry, CatUser)
        .join(CatUser, CatEntry.cat_user_id == CatUser.id)
        .where(CatEntry.cat_user_id.in_(ids), CatEntry.entry_date == date.today())
        .order_by(CatEntry.id)
    ).all()

    feed = []
    for entry, friend in rows:
        sentences = sentences_of(db, entry)
        praise_count = db.scalar(
            select(func.count(CatPraise.id)).where(CatPraise.entry_id == entry.id)
        )
        mine = db.scalar(
            select(func.count(CatPraise.id)).where(
                CatPraise.entry_id == entry.id, CatPraise.giver_id == user.id
            )
        )
        moment = entry.completed_at or entry.created_at
        feed.append(
            {
                "entry_id": entry.id,
                **user_card(friend),
                "learning_language": friend.learning_language,
                "status": "complete" if entry.is_complete else "writing",
                "progress": f"{len(sentences)}/{SENTENCES_PER_ENTRY}",
                # 시각만 내려주고 "10분 전" 같은 말은 화면에서 만들어요.
                # 앱이 4개 언어라 서버가 문구를 만들면 번역까지 서버 몫이 되거든요.
                "written_at": moment.isoformat(timespec="seconds") if moment else None,
                # 친구에게는 **쓴 그대로** 보여줘요. 교정본이 아니라요.
                "sentences": [s.original_text for s in sentences],
                "praise_count": praise_count or 0,
                "i_praised": bool(mine),
            }
        )
    return {"feed": feed}


@router.post("/entries/{entry_id}/praises", status_code=201)
def give_praise(
    entry_id: int,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """칭찬도장 💛 — 한 수첩에 한 번만."""
    user = require_user(db, user_email)
    entry = friend_entry(db, entry_id, user)

    already = db.scalar(
        select(CatPraise).where(
            CatPraise.entry_id == entry.id, CatPraise.giver_id == user.id
        )
    )
    if already is not None:
        raise HTTPException(status_code=409, detail="이미 칭찬도장을 줬어요")

    db.add(CatPraise(entry_id=entry.id, giver_id=user.id))
    db.commit()
    count = db.scalar(
        select(func.count(CatPraise.id)).where(CatPraise.entry_id == entry.id)
    )
    return {"praise_count": count or 0}


@router.get("/entries/{entry_id}/comments")
def read_comments(
    entry_id: int,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """댓글 목록 — 친구 수첩과 **내 수첩** 둘 다 볼 수 있어요."""
    user = require_user(db, user_email)
    entry = friend_entry(db, entry_id, user, allow_own=True)

    rows = db.execute(
        select(CatComment, CatUser)
        .join(CatUser, CatComment.writer_id == CatUser.id)
        .where(CatComment.entry_id == entry.id)
        .order_by(CatComment.id)
    ).all()
    return {"comments": [comment_card(comment, writer) for comment, writer in rows]}


@router.post("/entries/{entry_id}/comments", status_code=201)
def write_comment(
    entry_id: int,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """댓글 쓰기 (200자 이내). 비속어 필터는 2차예요 (D-07)."""
    user = require_user(db, user_email)
    entry = friend_entry(db, entry_id, user, allow_own=True)

    comment = CatComment(entry_id=entry.id, writer_id=user.id, content=payload.content)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment_card(comment, user)


# ══════════════════════════════════════════════════════════
#  5장 — 단어장
# ══════════════════════════════════════════════════════════
#  D-16 으로 화면이 하나로 합쳐져서, 어른 전용이 아니라 모두가 써요.
#  여기 모은 개수가 내 단계를 정해요 (D-23).


def vocab_card(item: CatVocabItem) -> dict:
    return {
        "vocab_id": item.id,
        "expression": item.expression,
        "meaning": item.meaning,
        "correction_id": item.correction_id,
        "created_at": item.created_at.isoformat(timespec="seconds")
        if item.created_at
        else None,
    }


@router.get("/vocab")
def read_vocab(
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """내 단어장 — 최근에 담은 것부터."""
    user = require_user(db, user_email)
    items = db.scalars(
        select(CatVocabItem)
        .where(CatVocabItem.cat_user_id == user.id)
        .order_by(CatVocabItem.id.desc())
    )
    return {"vocab": [vocab_card(item) for item in items]}


@router.post("/vocab", status_code=201)
def save_vocab(
    payload: VocabCreate,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """교정 하나를 단어장에 담아요."""
    user = require_user(db, user_email)

    correction = db.get(CatCorrection, payload.correction_id)
    if correction is None:
        raise HTTPException(status_code=404, detail="그런 교정이 없어요")

    # 이 교정이 정말 내 글에서 나온 건지 확인해요.
    # 교정 → 문장 → 수첩 순서로 거슬러 올라가면 주인이 나와요.
    owner_id = db.scalar(
        select(CatEntry.cat_user_id)
        .join(CatSentence, CatSentence.entry_id == CatEntry.id)
        .where(CatSentence.id == correction.sentence_id)
    )
    if owner_id != user.id:
        raise HTTPException(
            status_code=403, detail="내 수첩에서 나온 표현만 담을 수 있어요"
        )

    already = db.scalar(
        select(CatVocabItem).where(
            CatVocabItem.cat_user_id == user.id,
            CatVocabItem.correction_id == correction.id,
        )
    )
    if already is not None:
        raise HTTPException(status_code=409, detail="이미 단어장에 있어요")

    item = CatVocabItem(
        cat_user_id=user.id,
        correction_id=correction.id,
        expression=correction.right_text,
        # meaning 칸이 200자라 문법 노트가 길면 잘라요.
        # 전체 설명은 그날 수첩(3-2)을 열면 그대로 남아 있어요.
        meaning=(correction.note or "")[:MEANING_MAX] or None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return vocab_card(item)


@router.delete("/vocab/{vocab_id}", status_code=204)
def remove_vocab(
    vocab_id: int,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """단어장에서 빼기."""
    user = require_user(db, user_email)

    item = db.get(CatVocabItem, vocab_id)
    if item is None or item.cat_user_id != user.id:
        raise HTTPException(status_code=404, detail="그런 표현이 없어요")

    db.delete(item)
    db.commit()
