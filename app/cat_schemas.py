from typing import Literal

from pydantic import BaseModel, Field


class CatUserCreate(BaseModel):
    """계정 만들기 요청 — POST /me"""

    partner: Literal["kongi", "cheese", "meokmul", "sikppang"]
    note_id: str = Field(min_length=4, max_length=15, pattern="^[a-zA-Z0-9]+$")
    nickname: str = Field(min_length=1, max_length=10)
    learning_language: str = "ko"
