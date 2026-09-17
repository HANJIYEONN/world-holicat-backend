"""운영 블로그에 처음 한 번만 넣는 샘플 이야기."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine
from .models import BlogPost, BlogUser

SAMPLE_AUTHOR_EMAIL = "sample-writer@world-holicat.com"
SAMPLE_AUTHOR_NICKNAME = "수염지기"

SAMPLE_POSTS = (
    (
        "비 오는 날의 창가",
        "아침부터 창문에 빗방울이 오래 매달려 있었다.\n\n"
        "따뜻한 차를 한 잔 내려두고 창가에 앉으니, 평소에는 들리지 않던 "
        "시계 소리와 고양이의 작은 숨소리가 또렷해졌다.\n\n"
        "아무 일도 일어나지 않은 날이었지만 그래서 오래 기억하고 싶은 날이 되었다.",
    ),
    (
        "서랍 속 오래된 책갈피",
        "책상 서랍을 정리하다 몇 년 전 기차표를 발견했다. 책갈피 대신 꽂아둔 채 "
        "잊어버린 표였다.\n\n"
        "도착지는 기억나는데 그날 무슨 이야기를 나눴는지는 잘 떠오르지 않았다. "
        "그래도 종이 한 장 덕분에 그때의 바람 냄새만은 잠깐 돌아왔다.\n\n"
        "다시 책 사이에 넣어두었다. 이번에는 잊지 않기 위해서가 아니라, 언젠가 또 발견하기 위해서.",
    ),
    (
        "밤 산책에서 주운 것",
        "늦은 밤 골목을 걷다가 담장 위에 나란히 앉은 고양이 두 마리를 만났다.\n\n"
        "내가 지나가도 도망치지 않고 빤히 바라보길래 조용히 인사를 건넸다. "
        "대답은 없었지만 둘 중 한 마리가 천천히 눈을 감아주었다.\n\n"
        "집으로 돌아오는 길에는 손에 든 것이 없었는데도 작은 행운을 주운 기분이었다.",
    ),
)


def seed_blog_samples(db: Session) -> int:
    """샘플 작성자와 세 글을 만들고, 이미 있는 글은 건너뛰어요."""
    author = db.scalar(select(BlogUser).where(BlogUser.user_email == SAMPLE_AUTHOR_EMAIL))
    if author is None:
        author = BlogUser(
            user_email=SAMPLE_AUTHOR_EMAIL,
            nickname=SAMPLE_AUTHOR_NICKNAME,
        )
        db.add(author)
        db.flush()

    existing_titles = set(
        db.scalars(select(BlogPost.title).where(BlogPost.blog_user_id == author.id)).all()
    )
    added = 0
    for title, content in SAMPLE_POSTS:
        if title in existing_titles:
            continue
        db.add(BlogPost(blog_user_id=author.id, title=title, content=content))
        added += 1

    db.commit()
    return added


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        added = seed_blog_samples(db)
    print(f"Blog sample posts added: {added}")


if __name__ == "__main__":
    main()
