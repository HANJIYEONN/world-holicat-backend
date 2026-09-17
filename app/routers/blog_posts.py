from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..blog_schemas import BlogPostCreate
from ..database import get_db
from ..korea_time import to_iso
from ..models import BlogPost, BlogUser
from .auth import get_current_user_email

router = APIRouter(prefix="/api/v1/blog/posts", tags=["blog-posts"])


def post_response(post: BlogPost, author: BlogUser, current_email: str) -> dict:
    return {
        "id": post.id,
        "title": post.title,
        "content": post.content,
        "author_nickname": author.nickname,
        "is_author": author.user_email == current_email,
        "created_at": to_iso(post.created_at),
        "updated_at": to_iso(post.updated_at),
    }


def find_post_and_author(db: Session, post_id: int) -> tuple[BlogPost, BlogUser]:
    row = db.execute(
        select(BlogPost, BlogUser)
        .join(BlogUser, BlogPost.blog_user_id == BlogUser.id)
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
        select(BlogPost, BlogUser)
        .join(BlogUser, BlogPost.blog_user_id == BlogUser.id)
        .order_by(BlogPost.created_at.desc(), BlogPost.id.desc())
    ).all()
    return [post_response(post, author, user_email) for post, author in rows]


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
    post, author = find_post_and_author(db, post_id)
    return post_response(post, author, user_email)


@router.put("/{post_id}")
def update_post(
    post_id: int,
    payload: BlogPostCreate,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    post, author = find_post_and_author(db, post_id)
    if author.user_email != user_email:
        raise HTTPException(status_code=403, detail="내 글만 수정할 수 있어요")

    post.title = payload.title
    post.content = payload.content
    db.commit()
    db.refresh(post)
    return post_response(post, author, user_email)


@router.delete("/{post_id}", status_code=204)
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    post, author = find_post_and_author(db, post_id)
    if author.user_email != user_email:
        raise HTTPException(status_code=403, detail="내 글만 삭제할 수 있어요")

    db.delete(post)
    db.commit()
