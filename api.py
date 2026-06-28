from fastapi import FastAPI, Request, Form, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional
import json

from database import AsyncSessionLocal, User, Profile, Post, Comment, Like
from config import OWNER_ID

app = FastAPI(title="MLBB Team Finder")

# CORS для доступа с любых устройств
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# Вспомогательные функции
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def get_or_create_user(telegram_id: int, username: str = None, first_name: str = "Игрок", db: AsyncSession) -> User:
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user

# ============= ЭНДПОИНТЫ =============

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/auth")
async def auth(
    telegram_id: int = Form(...),
    username: Optional[str] = Form(None),
    first_name: str = Form("Игрок"),
    db: AsyncSession = Depends(get_db)
):
    user = await get_or_create_user(telegram_id, username, first_name, db)
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "is_owner": user.telegram_id == OWNER_ID
    }

@app.get("/api/profile/{telegram_id}")
async def get_profile(telegram_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.telegram_id == telegram_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    
    stmt = select(Profile).where(Profile.user_id == user.id)
    res = await db.execute(stmt)
    profile = res.scalar_one_or_none()
    
    if not profile:
        return None
    
    return {
        "nickname_mlbb": profile.nickname_mlbb,
        "role": profile.role,
        "rank": profile.rank,
        "description": profile.description,
        "photo_url": profile.photo_url,
        "updated_at": profile.updated_at.isoformat()
    }

@app.post("/api/profile")
async def update_profile(
    telegram_id: int = Form(...),
    nickname_mlbb: str = Form(...),
    role: str = Form(...),
    rank: str = Form(...),
    description: Optional[str] = Form(None),
    photo_url: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(User).where(User.telegram_id == telegram_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    
    stmt = select(Profile).where(Profile.user_id == user.id)
    res = await db.execute(stmt)
    profile = res.scalar_one_or_none()
    
    if not profile:
        profile = Profile(user_id=user.id)
        db.add(profile)
    
    profile.nickname_mlbb = nickname_mlbb
    profile.role = role
    profile.rank = rank
    profile.description = description
    if photo_url:
        profile.photo_url = photo_url
    
    await db.commit()
    return {"status": "ok"}

@app.get("/api/posts")
async def get_posts(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    telegram_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Post)
    
    if telegram_id:
        user_stmt = select(User).where(User.telegram_id == telegram_id)
        user_res = await db.execute(user_stmt)
        user = user_res.scalar_one_or_none()
        if user:
            stmt = stmt.where(Post.author_id == user.id)
    
    stmt = stmt.order_by(Post.created_at.desc()).limit(limit).offset(offset)
    res = await db.execute(stmt)
    posts = res.scalars().all()
    
    result = []
    for p in posts:
        # Лайки
        likes_count = await db.execute(select(func.count()).where(Like.post_id == p.id))
        likes = likes_count.scalar() or 0
        
        # Комментарии
        comments_count = await db.execute(select(func.count()).where(Comment.post_id == p.id))
        comments = comments_count.scalar() or 0
        
        # Автор
        auth_stmt = select(User).where(User.id == p.author_id)
        auth_res = await db.execute(auth_stmt)
        author = auth_res.scalar_one_or_none()
        
        result.append({
            "id": p.id,
            "author_id": p.author_id,
            "author_telegram_id": author.telegram_id if author else None,
            "author_name": f"{author.first_name} {author.last_name or ''}" if author else "Unknown",
            "content": p.content,
            "photo_url": p.photo_url,
            "created_at": p.created_at.isoformat(),
            "likes_count": likes,
            "comments_count": comments,
            "is_owner": author.telegram_id == OWNER_ID if author else False
        })
    return result

@app.post("/api/posts")
async def create_post(
    telegram_id: int = Form(...),
    content: str = Form(...),
    photo_url: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(User).where(User.telegram_id == telegram_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    
    post = Post(author_id=user.id, content=content, photo_url=photo_url)
    db.add(post)
    await db.commit()
    return {"id": post.id}

@app.delete("/api/posts/{post_id}")
async def delete_post(post_id: int, telegram_id: int = Form(...), db: AsyncSession = Depends(get_db)):
    stmt = select(Post).where(Post.id == post_id)
    res = await db.execute(stmt)
    post = res.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "Post not found")
    
    # Проверка прав
    user_stmt = select(User).where(User.telegram_id == telegram_id)
    user_res = await db.execute(user_stmt)
    user = user_res.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    
    if post.author_id != user.id and user.telegram_id != OWNER_ID:
        raise HTTPException(403, "Not allowed")
    
    await db.delete(post)
    await db.commit()
    return {"status": "deleted"}

@app.post("/api/like")
async def toggle_like(
    post_id: int = Form(...),
    telegram_id: int = Form(...),
    db: AsyncSession = Depends(get_db)
):
    # Проверим пост
    stmt = select(Post).where(Post.id == post_id)
    res = await db.execute(stmt)
    if not res.scalar_one_or_none():
        raise HTTPException(404, "Post not found")
    
    # Проверим пользователя
    user_stmt = select(User).where(User.telegram_id == telegram_id)
    user_res = await db.execute(user_stmt)
    user = user_res.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    
    # Проверим лайк
    stmt = select(Like).where(and_(Like.user_id == user.id, Like.post_id == post_id))
    res = await db.execute(stmt)
    like = res.scalar_one_or_none()
    
    if like:
        await db.delete(like)
        await db.commit()
        return {"liked": False}
    else:
        new_like = Like(user_id=user.id, post_id=post_id)
        db.add(new_like)
        await db.commit()
        return {"liked": True}

@app.get("/api/posts/{post_id}/comments")
async def get_comments(post_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Comment).where(Comment.post_id == post_id).order_by(Comment.created_at)
    res = await db.execute(stmt)
    comments = res.scalars().all()
    
    result = []
    for c in comments:
        auth_stmt = select(User).where(User.id == c.author_id)
        auth_res = await db.execute(auth_stmt)
        author = auth_res.scalar_one_or_none()
        result.append({
            "id": c.id,
            "author_name": f"{author.first_name} {author.last_name or ''}" if author else "Unknown",
            "author_telegram_id": author.telegram_id if author else None,
            "content": c.content,
            "created_at": c.created_at.isoformat(),
            "is_owner": author.telegram_id == OWNER_ID if author else False
        })
    return result

@app.post("/api/comments")
async def create_comment(
    post_id: int = Form(...),
    telegram_id: int = Form(...),
    content: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    # Проверим пост
    stmt = select(Post).where(Post.id == post_id)
    res = await db.execute(stmt)
    if not res.scalar_one_or_none():
        raise HTTPException(404, "Post not found")
    
    # Проверим пользователя
    user_stmt = select(User).where(User.telegram_id == telegram_id)
    user_res = await db.execute(user_stmt)
    user = user_res.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    
    comment = Comment(post_id=post_id, author_id=user.id, content=content)
    db.add(comment)
    await db.commit()
    return {"id": comment.id}

@app.delete("/api/comments/{comment_id}")
async def delete_comment(comment_id: int, telegram_id: int = Form(...), db: AsyncSession = Depends(get_db)):
    stmt = select(Comment).where(Comment.id == comment_id)
    res = await db.execute(stmt)
    comment = res.scalar_one_or_none()
    if not comment:
        raise HTTPException(404, "Comment not found")
    
    user_stmt = select(User).where(User.telegram_id == telegram_id)
    user_res = await db.execute(user_stmt)
    user = user_res.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    
    if comment.author_id != user.id and user.telegram_id != OWNER_ID:
        raise HTTPException(403, "Not allowed")
    
    await db.delete(comment)
    await db.commit()
    return {"status": "deleted"}