from sqlalchemy import func, select

from app.blog_seed import (
    SAMPLE_AUTHOR_EMAIL,
    SAMPLE_AUTHOR_NICKNAME,
    SAMPLE_POSTS,
    seed_blog_samples,
)
from app.database import SessionLocal
from app.models import BlogPost, BlogUser


def test_샘플_이야기_세_개를_한_번만_넣는다():
    with SessionLocal() as db:
        assert seed_blog_samples(db) == 3
        assert seed_blog_samples(db) == 0

        author = db.scalar(select(BlogUser).where(BlogUser.user_email == SAMPLE_AUTHOR_EMAIL))
        assert author is not None
        assert author.nickname == SAMPLE_AUTHOR_NICKNAME
        assert db.scalar(select(func.count()).select_from(BlogPost)) == 3
        assert set(db.scalars(select(BlogPost.title)).all()) == {
            title for title, _ in SAMPLE_POSTS
        }
