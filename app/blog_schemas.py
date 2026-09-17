from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

NICKNAME_MAX = 20

Nickname = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=NICKNAME_MAX),
]


class BlogUserCreate(BaseModel):
    """블로그에 처음 들어갈 때 한 번만 받는 닉네임."""

    model_config = ConfigDict(extra="forbid")

    nickname: Nickname


PostTitle = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]
PostContent = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=5000),
]


class BlogPostCreate(BaseModel):
    """블로그 글 작성 요청."""

    model_config = ConfigDict(extra="forbid")

    title: PostTitle
    content: PostContent
