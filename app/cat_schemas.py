from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# ── 수첩 아이디 규칙 (D-10) ──────────────────────────────
# 규칙을 여기 한 곳에만 적어두고, 검사 API(GET /note-id/check)와
# 생성 API(POST /me)가 같이 써요.
# 두 곳에 따로 적으면 "검사는 통과했는데 저장이 안 되는" 일이 생겨요.
NOTE_ID_MIN = 4
NOTE_ID_MAX = 15
NOTE_ID_PATTERN = r"^[a-zA-Z0-9]+$"  # 영문·숫자만 (전세계 어느 키보드에서든 칠 수 있게)

# 별명·소개 길이도 만들기/수정 양쪽이 같은 값을 봐야 해요
NICKNAME_MAX = 10
BIO_MAX = 100

# 짝꿍 4종 (D-13) / 아바타 4종 — 모델의 Enum 과 같은 값이어야 해요
Partner = Literal["kongi", "cheese", "meokmul", "sikppang"]
Avatar = Literal["cat", "dog", "rabbit", "dino"]


class CatUserCreate(BaseModel):
    """계정 만들기 요청 — POST /me"""

    partner: Partner
    note_id: str = Field(
        min_length=NOTE_ID_MIN, max_length=NOTE_ID_MAX, pattern=NOTE_ID_PATTERN
    )
    nickname: str = Field(min_length=1, max_length=NICKNAME_MAX)
    learning_language: str = "ko"


class CatUserUpdate(BaseModel):
    """내 정보 수정 요청 — PATCH /me. **바꿀 것만** 보내면 돼요.

    안 보낸 항목은 그대로 둬요 (None 으로 덮어쓰지 않아요).

    ⚠️ note_id 는 여기 없어요 — 바꾸면 친구가 나를 못 찾게 되니까요 (D-10).
    extra="forbid" 라서 note_id 를 보내면 조용히 무시되지 않고 422 로 알려줘요.
    오타 난 항목도 마찬가지로 바로 잡혀요.
    """

    model_config = ConfigDict(extra="forbid")

    partner: Optional[Partner] = None  # 짝꿍은 나중에 바꿀 수 있어요 (D-17)
    nickname: Optional[str] = Field(default=None, min_length=1, max_length=NICKNAME_MAX)
    bio: Optional[str] = Field(default=None, max_length=BIO_MAX)
    avatar: Optional[Avatar] = None
    learning_language: Optional[str] = Field(default=None, min_length=2, max_length=2)
    feedback_language: Optional[str] = Field(default=None, min_length=2, max_length=2)
    daily_reminder: Optional[bool] = None


# ── 2장 쓰기 규칙 ────────────────────────────────────────
SENTENCES_PER_ENTRY = 5  # 하루 5문장 (D-01)
SENTENCE_MAX = 200  # 문장 하나 길이

# strip_whitespace=True 라서 앞뒤 공백은 저절로 잘려요.
# 그래서 "   " (공백만) 을 보내면 빈 글자가 되고, min_length=1 에 걸려 422 가 나요.
SentenceText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SENTENCE_MAX)
]


class SentenceSave(BaseModel):
    """문장 한 개 저장 — PUT /entries/today/sentences/{position}"""

    model_config = ConfigDict(extra="forbid")

    text: SentenceText


# ── 4장 친구 규칙 ────────────────────────────────────────
FRIEND_LIMIT = 10  # 친구는 최대 10명 (D-22)
COMMENT_MAX = 200  # 댓글 길이

CommentText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=COMMENT_MAX)
]


class FriendRequest(BaseModel):
    """친구 신청 — POST /friends"""

    model_config = ConfigDict(extra="forbid")

    note_id: str = Field(min_length=NOTE_ID_MIN, max_length=NOTE_ID_MAX)


class CommentCreate(BaseModel):
    """댓글 쓰기 — POST /entries/{entry_id}/comments"""

    model_config = ConfigDict(extra="forbid")

    content: CommentText


# ── 5장 단어장 ───────────────────────────────────────────
MEANING_MAX = 200  # cat_vocab_items.meaning 컬럼 길이


class VocabCreate(BaseModel):
    """단어장에 담기 — POST /vocab

    교정에서만 담을 수 있어요. 아무 말이나 적어 넣는 메모장이 아니라
    "내가 오늘 틀려서 배운 것"을 모으는 자리거든요.
    """

    model_config = ConfigDict(extra="forbid")

    correction_id: int
