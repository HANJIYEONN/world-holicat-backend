from typing import Literal

from pydantic import BaseModel, Field

# ── 수첩 아이디 규칙 (D-10) ──────────────────────────────
# 규칙을 여기 한 곳에만 적어두고, 검사 API(GET /note-id/check)와
# 생성 API(POST /me)가 같이 써요.
# 두 곳에 따로 적으면 "검사는 통과했는데 저장이 안 되는" 일이 생겨요.
NOTE_ID_MIN = 4
NOTE_ID_MAX = 15
NOTE_ID_PATTERN = r"^[a-zA-Z0-9]+$"  # 영문·숫자만 (전세계 어느 키보드에서든 칠 수 있게)


class CatUserCreate(BaseModel):
    """계정 만들기 요청 — POST /me"""

    partner: Literal["kongi", "cheese", "meokmul", "sikppang"]
    note_id: str = Field(
        min_length=NOTE_ID_MIN, max_length=NOTE_ID_MAX, pattern=NOTE_ID_PATTERN
    )
    nickname: str = Field(min_length=1, max_length=10)
    learning_language: str = "ko"
