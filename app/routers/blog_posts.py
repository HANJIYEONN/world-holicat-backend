from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..blog_schemas import BlogPostCreate
from ..database import get_db
from ..korea_time import to_iso
from ..models import BlogPost, BlogPostView, BlogUser
from .auth import get_current_user_email

router = APIRouter(prefix="/api/v1/blog/posts", tags=["blog-posts"])


def post_response(
    post: BlogPost,
    author: BlogUser,
    current_email: str,
    view_count: int = 0,
) -> dict:
    return {
        "id": post.id,
        "title": post.title,
        "content": post.content,
        "author_nickname": author.nickname,
        "is_author": author.user_email == current_email,
        "view_count": view_count,
        "created_at": to_iso(post.created_at),
        "updated_at": to_iso(post.updated_at),
    }


def find_post_and_author(db: Session, post_id: int) -> tuple[BlogPost, BlogUser, int]:
    row = db.execute(
        select(BlogPost, BlogUser, BlogPostView.view_count)
        .join(BlogUser, BlogPost.blog_user_id == BlogUser.id)
        .outerjoin(BlogPostView, BlogPost.id == BlogPostView.post_id)
        .where(BlogPost.id == post_id)
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="글을 찾을 수 없어요")
    return row


@router.get("")
def list_posts(
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """작성자와 관계없이 모든 글을 최신순으로 보여줘요."""
    rows = db.execute(
        select(BlogPost, BlogUser, BlogPostView.view_count)
        .join(BlogUser, BlogPost.blog_user_id == BlogUser.id)
        .outerjoin(BlogPostView, BlogPost.id == BlogPostView.post_id)
        .order_by(BlogPost.created_at.desc(), BlogPost.id.desc())
    ).all()
    return [
        post_response(post, author, user_email, view_count or 0)
        for post, author, view_count in rows
    ]


@router.post("", status_code=201)
def create_post(
    payload: BlogPostCreate,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """블로그 닉네임을 정한 사용자만 글을 쓸 수 있어요."""
    author = db.scalar(select(BlogUser).where(BlogUser.user_email == user_email))
    if author is None:
        raise HTTPException(status_code=403, detail="블로그 닉네임을 먼저 정해주세요")

    post = BlogPost(blog_user_id=author.id, title=payload.title, content=payload.content)
    db.add(post)
    db.commit()
    db.refresh(post)
    return post_response(post, author, user_email)


@router.get("/{post_id}")
def read_post(
    post_id: int,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    post, author, view_count = find_post_and_author(db, post_id)
    return post_response(post, author, user_email, view_count or 0)


@router.post("/{post_id}/view")
def record_post_view(
    post_id: int,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    """상세 화면 방문 한 번을 조회수 한 번으로 기록해요."""
    post, author, view_count = find_post_and_author(db, post_id)
    views = db.get(BlogPostView, post.id)
    if views is None:
        views = BlogPostView(post_id=post.id, view_count=1)
        db.add(views)
    else:
        views.view_count += 1
    db.commit()
    return post_response(post, author, user_email, (view_count or 0) + 1)


@router.put("/{post_id}")
def update_post(
    post_id: int,
    payload: BlogPostCreate,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    post, author, view_count = find_post_and_author(db, post_id)
    if author.user_email != user_email:
        raise HTTPException(status_code=403, detail="내 글만 수정할 수 있어요")

    post.title = payload.title
    post.content = payload.content
    db.commit()
    db.refresh(post)
    return post_response(post, author, user_email, view_count or 0)


@router.delete("/{post_id}", status_code=204)
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    post, author, _ = find_post_and_author(db, post_id)
    if author.user_email != user_email:
        raise HTTPException(status_code=403, detail="내 글만 삭제할 수 있어요")

    views = db.get(BlogPostView, post.id)
    if views is not None:
        db.delete(views)
    db.delete(post)
    db.commit()
