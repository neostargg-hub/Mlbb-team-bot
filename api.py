import os
from fastapi import FastAPI, Request, UploadFile, File, Form, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import base64
import json
from typing import Optional, List

from database import AsyncSessionLocal, User, Profile, Post, Comment, Like, News
from utils import validate_telegram_data, can_manage, parse_user_from_init_data
from config import OWNER_ID, WEBAPP_URL

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# Вспомогательные функции
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def get_or_create_user(telegram_user: dict, db: AsyncSession) -> User:
    user_id = telegram_user.get("id")
    if not user_id:
        raise HTTPException(400, "No user id")
    
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(
            id=user_id,
            username=telegram_user.get("username"),
            first_name=telegram_user.get("first_name", ""),
            last_name=telegram_user.get("last_name")
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user

# Эндпоинты
@app.get("/webapp", response_class=HTMLResponse)
async def webapp_page():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/api/me")
async def me(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.body()
    init_data = data.decode()
    if not validate_telegram_data(init_data):
        raise HTTPException(403, "Invalid telegram data")
    
    user_data = parse_user_from_init_data(init_data)
    user = await get_or_create_user(user_data, db)
    
    return {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "is_owner": user.id == OWNER_ID
    }

@app.get("/api/profile/{user_id}")
async def get_profile(user_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Profile).where(Profile.user_id == user_id)
    res = await db.execute(stmt)
    profile = res.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(404, "Profile not found")
    
    return {
        "user_id": profile.user_id,
        "nickname_mlbb": profile.nickname_mlbb,
        "role": profile.role,
        "rank": profile.rank,
        "description": profile.description,
        "notifications": profile.notifications,
        "updated_at": profile.updated_at.isoformat(),
        "photo": base64.b64encode(profile.photo).decode() if profile.photo else None
    }

@app.post("/api/profile")
async def update_profile(
    user_id: int = Form(...),
    nickname_mlbb: str = Form(...),
    role: str = Form(...),
    rank: str = Form(...),
    description: Optional[str] = Form(None),
    notifications: bool = Form(True),
    photo: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    if not res.scalar_one_or_none():
        raise HTTPException(404, "User not found")
    
    stmt = select(Profile).where(Profile.user_id == user_id)
    res = await db.execute(stmt)
    profile = res.scalar_one_or_none()
    
    if not profile:
        profile = Profile(user_id=user_id)
        db.add(profile)
    
    profile.nickname_mlbb = nickname_mlbb
    profile.role = role
    profile.rank = rank
    profile.description = description
    profile.notifications = notifications
    
    if photo and photo.filename:
        profile.photo = await photo.read()
    
    await db.commit()
    return {"status": "ok"}

@app.get("/api/posts")
async def get_posts(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    role: Optional[str] = None,
    rank: Optional[str] = None,
    search: Optional[str] = None,
    user_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    # Базовый запрос
    stmt = select(Post)
    
    # Фильтры
    if user_id:
        stmt = stmt.where(Post.author_id == user_id)
    
    if role or rank or search:
        # Подзапрос для поиска по профилям
        from sqlalchemy import or_
        subquery = select(Post)
        if role:
            subquery = subquery.join(Profile, Post.author_id == Profile.user_id).where(Profile.role.ilike(f"%{role}%"))
        if rank:
            subquery = subquery.join(Profile, Post.author_id == Profile.user_id).where(Profile.rank.ilike(f"%{rank}%"))
        if search:
            subquery = subquery.where(Post.content.ilike(f"%{search}%"))
        stmt = stmt.where(Post.id.in_(subquery.subquery()))
    
    stmt = stmt.order_by(Post.created_at.desc()).limit(limit).offset(offset)
    res = await db.execute(stmt)
    posts = res.scalars().all()
    
    result = []
    for p in posts:
        # Кол-во лайков
        likes_count = await db.execute(select(func.count()).where(Like.post_id == p.id))
        likes = likes_count.scalar() or 0
        
        # Проверка лайка текущего пользователя (если передан)
        user_liked = False
        if user_id:
            like_check = await db.execute(select(Like).where(and_(Like.user_id == user_id, Like.post_id == p.id)))
            user_liked = like_check.scalar_one_or_none() is not None
        
        # Кол-во комментариев
        comments_count = await db.execute(select(func.count()).where(Comment.post_id == p.id))
        comments = comments_count.scalar() or 0
        
        # Автор
        auth_stmt = select(User).where(User.id == p.author_id)
        auth_res = await db.execute(auth_stmt)
        author = auth_res.scalar_one_or_none()
        
        result.append({
            "id": p.id,
            "author_id": p.author_id,
            "content": p.content,
            "photo": base64.b64encode(p.photo).decode() if p.photo else None,
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat(),
            "likes_count": likes,
            "comments_count": comments,
            "user_liked": user_liked,
            "author": {
                "id": author.id,
                "username": author.username,
                "first_name": author.first_name,
                "last_name": author.last_name
            } if author else None
        })
    return result

@app.post("/api/posts")
async def create_post(
    user_id: int = Form(...),
    content: str = Form(...),
    photo: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    if not res.scalar_one_or_none():
        raise HTTPException(404, "User not found")
    
    post = Post(author_id=user_id, content=content)
    if photo and photo.filename:
        post.photo = await photo.read()
    
    db.add(post)
    await db.commit()
    return {"id": post.id}

@app.delete("/api/posts/{post_id}")
async def delete_post(post_id: int, user_id: int = Form(...), db: AsyncSession = Depends(get_db)):
    stmt = select(Post).where(Post.id == post_id)
    res = await db.execute(stmt)
    post = res.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "Post not found")
    if not can_manage(user_id, post.author_id):
        raise HTTPException(403, "Not allowed")
    
    await db.delete(post)
    await db.commit()
    return {"status": "deleted"}

@app.post("/api/like")
async def toggle_like(
    post_id: int = Form(...),
    user_id: int = Form(...),
    db: AsyncSession = Depends(get_db)
):
    # Проверим пост
    stmt = select(Post).where(Post.id == post_id)
    res = await db.execute(stmt)
    if not res.scalar_one_or_none():
        raise HTTPException(404, "Post not found")
    
    # Проверим лайк
    stmt = select(Like).where(and_(Like.user_id == user_id, Like.post_id == post_id))
    res = await db.execute(stmt)
    like = res.scalar_one_or_none()
    
    if like:
        await db.delete(like)
        await db.commit()
        return {"liked": False}
    else:
        new_like = Like(user_id=user_id, post_id=post_id)
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
            "post_id": c.post_id,
            "author_id": c.author_id,
            "content": c.content,
            "created_at": c.created_at.isoformat(),
            "author": {
                "id": author.id,
                "username": author.username,
                "first_name": author.first_name,
                "last_name": author.last_name
            } if author else None
        })
    return result

@app.post("/api/comments")
async def create_comment(
    post_id: int = Form(...),
    user_id: int = Form(...),
    content: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    # Проверим пост
    stmt = select(Post).where(Post.id == post_id)
    res = await db.execute(stmt)
    post = res.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "Post not found")
    
    # Проверим пользователя
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    
    comment = Comment(post_id=post_id, author_id=user_id, content=content)
    db.add(comment)
    await db.commit()
    
    # Уведомление автору поста (если включено)
    if post.author_id != user_id:
        profile_stmt = select(Profile).where(Profile.user_id == post.author_id)
        profile_res = await db.execute(profile_stmt)
        profile = profile_res.scalar_one_or_none()
        if profile and profile.notifications:
            # Здесь можно отправить уведомление через бота
            # Оставлю заглушку, так как бот в отдельном потоке
            pass
    
    return {"id": comment.id}

@app.delete("/api/comments/{comment_id}")
async def delete_comment(comment_id: int, user_id: int = Form(...), db: AsyncSession = Depends(get_db)):
    stmt = select(Comment).where(Comment.id == comment_id)
    res = await db.execute(stmt)
    comment = res.scalar_one_or_none()
    if not comment:
        raise HTTPException(404, "Comment not found")
    if not can_manage(user_id, comment.author_id):
        raise HTTPException(403, "Not allowed")
    
    await db.delete(comment)
    await db.commit()
    return {"status": "deleted"}

@app.get("/api/news")
async def get_news(limit: int = 10, db: AsyncSession = Depends(get_db)):
    stmt = select(News).where(News.is_active == True).order_by(News.created_at.desc()).limit(limit)
    res = await db.execute(stmt)
    news_list = res.scalars().all()
    
    return [{
        "id": n.id,
        "title": n.title,
        "content": n.content,
        "created_at": n.created_at.isoformat()
    } for n in news_list]