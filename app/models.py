from datetime import date

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class HeadacheEntry(Base):
    """두통 기록 한 건."""

    __tablename__ = "headache_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)  # 날짜
    menstruating: Mapped[bool] = mapped_column(Boolean, default=False)  # 생리기간 유무
    took_painkiller: Mapped[bool] = mapped_column(Boolean, default=False)  # 통증약 복용여부
    medication: Mapped[str] = mapped_column(String(100), nullable=True)  # 약 종류
    effective: Mapped[bool] = mapped_column(Boolean, nullable=True)  # 효과여부
    dose_count: Mapped[int] = mapped_column(Integer, nullable=True)  # 복용횟수
    trigger: Mapped[str] = mapped_column(Text, nullable=True)  # 촉발요인
    bp_systolic: Mapped[int] = mapped_column(Integer, nullable=True)  # 혈압-수축기
    bp_diastolic: Mapped[int] = mapped_column(Integer, nullable=True)  # 혈압-이완기
    bp_pulse: Mapped[int] = mapped_column(Integer, nullable=True)  # 혈압-맥박수
    # Google 로그인 붙이면 사용자 구분에 사용
    user_email: Mapped[str] = mapped_column(String(255), nullable=True, index=True)


class FavoriteMedication(Base):
    """자주 복용하는 약 (사용자당 최대 3개, 백엔드에서 강제).

    약 이름뿐 아니라 즐겨찾기로 등록할 당시의 기록 내용(복용횟수, 효과,
    촉발요인, 혈압 등)을 통째로 저장해요. 메인 화면 버튼을 누르면
    이 내용 그대로 오늘 날짜로 저장돼요.
    """

    __tablename__ = "favorite_medications"
    __table_args__ = (UniqueConstraint("user_email", "name", name="uq_favorite_user_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    menstruating: Mapped[bool] = mapped_column(Boolean, default=False)
    effective: Mapped[bool] = mapped_column(Boolean, nullable=True)
    dose_count: Mapped[int] = mapped_column(Integer, nullable=True)
    trigger: Mapped[str] = mapped_column(Text, nullable=True)
    bp_systolic: Mapped[int] = mapped_column(Integer, nullable=True)
    bp_diastolic: Mapped[int] = mapped_column(Integer, nullable=True)
    bp_pulse: Mapped[int] = mapped_column(Integer, nullable=True)


class CatUser(Base):
    """고양이 수첩 사용자.

    구글 로그인한 사람이 고양이 수첩에 처음 들어와
    짝꿍과 수첩 아이디를 정하면 한 줄이 생겨요.
    비밀번호 칸이 없는 건 로그인을 구글이 처리하기 때문이에요.
    """

    __tablename__ = "cat_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 기존 백엔드와 같은 방식 — 구글 이메일로 사용자를 구분해요
    user_email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    # 친구가 나를 찾을 때 쓰는 아이디 (영문+숫자 4~15자, 소문자로 저장)
    note_id: Mapped[str] = mapped_column(String(15), nullable=False, unique=True, index=True)
    # 짝꿍 — 말투를 정해요 (화면은 모두 같아요)
    partner: Mapped[str] = mapped_column(
        Enum("kongi", "cheese", "meokmul", "sikppang", name="partner_kind"),
        nullable=False,
    )
    nickname: Mapped[str] = mapped_column(String(20), nullable=False)  # 별명
    bio: Mapped[str] = mapped_column(String(100), nullable=True)  # 소개 한 문장
    avatar: Mapped[str] = mapped_column(
        Enum("cat", "dog", "rabbit", "dino", name="avatar_kind"), default="cat"
    )
    learning_language: Mapped[str] = mapped_column(String(2), default="ko")  # 배우는 언어
    feedback_language: Mapped[str] = mapped_column(String(2), nullable=True)  # 설명받을 언어
    writing_stage: Mapped[int] = mapped_column(SmallInteger, default=1)  # 내 단계
    daily_reminder: Mapped[bool] = mapped_column(Boolean, default=False)  # 매일 알림
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())


class CatEntry(Base):
    """하루치 수첩 — 하루에 한 줄.

    '오늘 5문장 다 썼나?'를 여기서 관리해요.
    """

    __tablename__ = "cat_entries"
    # 한 사람이 같은 날짜에 수첩을 두 개 만들 수 없게 막아요
    __table_args__ = (UniqueConstraint("cat_user_id", "entry_date", name="uq_cat_entry_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cat_user_id: Mapped[int] = mapped_column(ForeignKey("cat_users.id"), nullable=False, index=True)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)  # 며칠 것인지
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False)  # 5문장 다 썼는지
    completed_at: Mapped[str] = mapped_column(DateTime, nullable=True)  # 완성한 시각
    accuracy: Mapped[int] = mapped_column(SmallInteger, nullable=True)  # 정확도 %
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())


class CatSentence(Base):
    """문장 한 개. 하루에 5개(position 1~5)."""

    __tablename__ = "cat_sentences"
    # 세 번째 문장이 두 개일 수 없게!
    __table_args__ = (UniqueConstraint("entry_id", "position", name="uq_cat_sentence_entry_pos"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("cat_entries.id"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 몇 번째 문장 (1~5)
    # 사용자가 원래 쓴 그대로 — 절대 덮어쓰지 않아요!
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    # AI가 고친 문장 (고칠 게 없으면 비어 있어요)
    corrected_text: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())


class CatCorrection(Base):
    """교정 한 건. 한 문장에 틀린 곳이 여러 개일 수 있어서 따로 뒀어요."""

    __tablename__ = "cat_corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sentence_id: Mapped[int] = mapped_column(
        ForeignKey("cat_sentences.id"), nullable=False, index=True
    )
    wrong_text: Mapped[str] = mapped_column(String(100), nullable=False)  # 틀린 부분 "조아요"
    right_text: Mapped[str] = mapped_column(String(100), nullable=False)  # 고친 것 "좋아요"
    note: Mapped[str] = mapped_column(Text, nullable=True)  # 문법 노트 (짝꿍 말투로)
    pronunciation: Mapped[str] = mapped_column(String(100), nullable=True)  # 발음 "[조아요]"
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())


class CatFriendship(Base):
    """친구 관계. 수첩 아이디로 찾아서 신청해요."""

    __tablename__ = "cat_friendships"
    # 같은 사람에게 두 번 신청 못 하게
    __table_args__ = (
        UniqueConstraint("requester_id", "receiver_id", name="uq_cat_friendship_pair"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    requester_id: Mapped[int] = mapped_column(
        ForeignKey("cat_users.id"), nullable=False, index=True
    )  # 신청한 사람
    receiver_id: Mapped[int] = mapped_column(
        ForeignKey("cat_users.id"), nullable=False, index=True
    )  # 받은 사람
    status: Mapped[str] = mapped_column(
        Enum("pending", "accepted", name="friendship_status"), default="pending"
    )
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())


class CatPraise(Base):
    """칭찬도장 💛 — 한 수첩에 한 사람이 하나만."""

    __tablename__ = "cat_praises"
    __table_args__ = (UniqueConstraint("entry_id", "giver_id", name="uq_cat_praise_entry_giver"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("cat_entries.id"), nullable=False, index=True)
    giver_id: Mapped[int] = mapped_column(ForeignKey("cat_users.id"), nullable=False, index=True)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())


class CatComment(Base):
    """친구 수첩에 남긴 댓글 💬 (비속어 필터는 2차)."""

    __tablename__ = "cat_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("cat_entries.id"), nullable=False, index=True)
    writer_id: Mapped[int] = mapped_column(ForeignKey("cat_users.id"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())


class CatVocabItem(Base):
    """단어장 — 배운 표현을 저장해둬요."""

    __tablename__ = "cat_vocab_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cat_user_id: Mapped[int] = mapped_column(ForeignKey("cat_users.id"), nullable=False, index=True)
    correction_id: Mapped[int] = mapped_column(
        ForeignKey("cat_corrections.id"), nullable=True
    )  # 어느 교정에서 저장했는지
    expression: Mapped[str] = mapped_column(String(100), nullable=False)  # 배운 표현
    meaning: Mapped[str] = mapped_column(String(200), nullable=True)  # 뜻·설명
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())
