import os
import asyncio
import json
import base64
from datetime import datetime
from typing import Optional, List
from urllib.parse import urlparse

# ===================== ЗАВИСИМОСТИ =====================
from fastapi import FastAPI, Request, Form, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, UniqueConstraint, create_engine, select, func, and_, or_
from sqlalchemy.orm import relationship, declarative_base, sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from pydantic import BaseModel
from dotenv import load_dotenv
import uvicorn

# ===================== КОНФИГУРАЦИЯ =====================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SITE_URL = os.getenv("SITE_URL", "https://mlbb-team-bot-2.onrender.com")
OWNER_ID = int(os.getenv("OWNER_ID", 5391287151))

# Используем SQLite для простоты (легко переключить на PostgreSQL)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///mlbb.db")

# Если используется PostgreSQL - заменяем драйвер
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg://")

# ===================== БАЗА ДАННЫХ =====================
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255))
    last_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    profile = relationship("Profile", back_populates="user", uselist=False)
    posts = relationship("Post", back_populates="author")
    comments = relationship("Comment", back_populates="author")
    likes = relationship("Like", back_populates="user")

class Profile(Base):
    __tablename__ = "profiles"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    nickname_mlbb = Column(String(255))
    role = Column(String(100))
    rank = Column(String(100))
    description = Column(Text, nullable=True)
    photo_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="profile")

class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    author_id = Column(Integer, ForeignKey("users.id"))
    content = Column(Text)
    photo_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    author = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    likes = relationship("Like", back_populates="post", cascade="all, delete-orphan")

class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id"))
    author_id = Column(Integer, ForeignKey("users.id"))
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    post = relationship("Post", back_populates="comments")
    author = relationship("User", back_populates="comments")

class Like(Base):
    __tablename__ = "likes"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    post_id = Column(Integer, ForeignKey("posts.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (UniqueConstraint('user_id', 'post_id', name='unique_like'),)
    
    user = relationship("User", back_populates="likes")
    post = relationship("Post", back_populates="likes")

# Создаем движок
try:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    
    # Пытаемся использовать асинхронный движок
    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async def get_db():
        async with AsyncSessionLocal() as session:
            yield session
    
    # Создаем таблицы
    async def init_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
except Exception as e:
    # Если асинхронный не работает - используем синхронный (для SQLite)
    print(f"Using sync engine: {e}")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    sync_engine = create_engine(DATABASE_URL.replace("+aiosqlite", ""), echo=False)
    SyncSessionLocal = sessionmaker(bind=sync_engine)
    
    def get_db_sync():
        db = SyncSessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    # Создаем таблицы синхронно
    Base.metadata.create_all(sync_engine)
    
    # Обертка для асинхронного использования
    async def get_db():
        return get_db_sync()

# ===================== FASTAPI APP =====================
app = FastAPI(title="MLBB Team Finder")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====================
async def get_or_create_user(telegram_id: int, username: str = None, first_name: str = "Игрок", db=None):
    if db is None:
        async for session in get_db():
            db = session
            break
    
    # Для синхронной работы
    if hasattr(db, 'execute'):
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
    else:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
    
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name
        )
        if hasattr(db, 'add'):
            db.add(user)
            await db.commit()
            await db.refresh(user)
        else:
            db.add(user)
            db.commit()
            db.refresh(user)
    return user

# ===================== ЭНДПОИНТЫ =====================
@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_TEMPLATE

@app.get("/style.css", response_class=HTMLResponse)
async def style():
    return CSS_TEMPLATE

@app.get("/script.js", response_class=HTMLResponse)
async def script():
    return JS_TEMPLATE

@app.post("/api/auth")
async def auth(
    telegram_id: int = Form(...),
    username: Optional[str] = Form(None),
    first_name: str = Form("Игрок")
):
    # Для простоты используем синхронный доступ
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        sync_engine = create_engine(DATABASE_URL.replace("+aiosqlite", "").replace("postgresql+psycopg://", "postgresql://"), echo=False)
        SyncSessionLocal = sessionmaker(bind=sync_engine)
        db = SyncSessionLocal()
        
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        db.close()
        
        return {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "is_owner": user.telegram_id == OWNER_ID
        }
    except Exception as e:
        print(f"Auth error: {e}")
        raise HTTPException(500, f"Auth error: {str(e)}")

@app.get("/api/profile/{telegram_id}")
async def get_profile(telegram_id: int):
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        sync_engine = create_engine(DATABASE_URL.replace("+aiosqlite", "").replace("postgresql+psycopg://", "postgresql://"), echo=False)
        SyncSessionLocal = sessionmaker(bind=sync_engine)
        db = SyncSessionLocal()
        
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            db.close()
            return None
        
        profile = db.query(Profile).filter(Profile.user_id == user.id).first()
        db.close()
        
        if not profile:
            return None
        
        return {
            "nickname_mlbb": profile.nickname_mlbb,
            "role": profile.role,
            "rank": profile.rank,
            "description": profile.description,
            "photo_url": profile.photo_url,
            "updated_at": profile.updated_at.isoformat() if profile.updated_at else None
        }
    except Exception as e:
        print(f"Profile error: {e}")
        return None

@app.post("/api/profile")
async def update_profile(
    telegram_id: int = Form(...),
    nickname_mlbb: str = Form(...),
    role: str = Form(...),
    rank: str = Form(...),
    description: Optional[str] = Form(None),
    photo_url: Optional[str] = Form(None)
):
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        sync_engine = create_engine(DATABASE_URL.replace("+aiosqlite", "").replace("postgresql+psycopg://", "postgresql://"), echo=False)
        SyncSessionLocal = sessionmaker(bind=sync_engine)
        db = SyncSessionLocal()
        
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            db.close()
            raise HTTPException(404, "User not found")
        
        profile = db.query(Profile).filter(Profile.user_id == user.id).first()
        if not profile:
            profile = Profile(user_id=user.id)
            db.add(profile)
        
        profile.nickname_mlbb = nickname_mlbb
        profile.role = role
        profile.rank = rank
        profile.description = description
        if photo_url:
            profile.photo_url = photo_url
        
        db.commit()
        db.close()
        return {"status": "ok"}
    except Exception as e:
        print(f"Update profile error: {e}")
        raise HTTPException(500, str(e))

@app.get("/api/posts")
async def get_posts(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    telegram_id: Optional[int] = None
):
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        sync_engine = create_engine(DATABASE_URL.replace("+aiosqlite", "").replace("postgresql+psycopg://", "postgresql://"), echo=False)
        SyncSessionLocal = sessionmaker(bind=sync_engine)
        db = SyncSessionLocal()
        
        query = db.query(Post)
        
        if telegram_id:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                query = query.filter(Post.author_id == user.id)
        
        posts = query.order_by(Post.created_at.desc()).limit(limit).offset(offset).all()
        
        result = []
        for p in posts:
            likes_count = db.query(Like).filter(Like.post_id == p.id).count()
            comments_count = db.query(Comment).filter(Comment.post_id == p.id).count()
            author = db.query(User).filter(User.id == p.author_id).first()
            
            result.append({
                "id": p.id,
                "author_id": p.author_id,
                "author_telegram_id": author.telegram_id if author else None,
                "author_name": f"{author.first_name} {author.last_name or ''}" if author else "Unknown",
                "content": p.content,
                "photo_url": p.photo_url,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "likes_count": likes_count,
                "comments_count": comments_count,
                "is_owner": author.telegram_id == OWNER_ID if author else False
            })
        
        db.close()
        return result
    except Exception as e:
        print(f"Posts error: {e}")
        return []

@app.post("/api/posts")
async def create_post(
    telegram_id: int = Form(...),
    content: str = Form(...),
    photo_url: Optional[str] = Form(None)
):
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        sync_engine = create_engine(DATABASE_URL.replace("+aiosqlite", "").replace("postgresql+psycopg://", "postgresql://"), echo=False)
        SyncSessionLocal = sessionmaker(bind=sync_engine)
        db = SyncSessionLocal()
        
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            db.close()
            raise HTTPException(404, "User not found")
        
        post = Post(author_id=user.id, content=content, photo_url=photo_url)
        db.add(post)
        db.commit()
        db.refresh(post)
        db.close()
        
        return {"id": post.id}
    except Exception as e:
        print(f"Create post error: {e}")
        raise HTTPException(500, str(e))

@app.delete("/api/posts/{post_id}")
async def delete_post(post_id: int, telegram_id: int = Form(...)):
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        sync_engine = create_engine(DATABASE_URL.replace("+aiosqlite", "").replace("postgresql+psycopg://", "postgresql://"), echo=False)
        SyncSessionLocal = sessionmaker(bind=sync_engine)
        db = SyncSessionLocal()
        
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            db.close()
            raise HTTPException(404, "Post not found")
        
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            db.close()
            raise HTTPException(404, "User not found")
        
        if post.author_id != user.id and user.telegram_id != OWNER_ID:
            db.close()
            raise HTTPException(403, "Not allowed")
        
        db.delete(post)
        db.commit()
        db.close()
        return {"status": "deleted"}
    except Exception as e:
        print(f"Delete post error: {e}")
        raise HTTPException(500, str(e))

@app.post("/api/like")
async def toggle_like(post_id: int = Form(...), telegram_id: int = Form(...)):
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        sync_engine = create_engine(DATABASE_URL.replace("+aiosqlite", "").replace("postgresql+psycopg://", "postgresql://"), echo=False)
        SyncSessionLocal = sessionmaker(bind=sync_engine)
        db = SyncSessionLocal()
        
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            db.close()
            raise HTTPException(404, "Post not found")
        
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            db.close()
            raise HTTPException(404, "User not found")
        
        like = db.query(Like).filter(and_(Like.user_id == user.id, Like.post_id == post_id)).first()
        
        if like:
            db.delete(like)
            db.commit()
            db.close()
            return {"liked": False}
        else:
            new_like = Like(user_id=user.id, post_id=post_id)
            db.add(new_like)
            db.commit()
            db.close()
            return {"liked": True}
    except Exception as e:
        print(f"Like error: {e}")
        raise HTTPException(500, str(e))

@app.get("/api/posts/{post_id}/comments")
async def get_comments(post_id: int):
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        sync_engine = create_engine(DATABASE_URL.replace("+aiosqlite", "").replace("postgresql+psycopg://", "postgresql://"), echo=False)
        SyncSessionLocal = sessionmaker(bind=sync_engine)
        db = SyncSessionLocal()
        
        comments = db.query(Comment).filter(Comment.post_id == post_id).order_by(Comment.created_at).all()
        
        result = []
        for c in comments:
            author = db.query(User).filter(User.id == c.author_id).first()
            result.append({
                "id": c.id,
                "author_name": f"{author.first_name} {author.last_name or ''}" if author else "Unknown",
                "author_telegram_id": author.telegram_id if author else None,
                "content": c.content,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "is_owner": author.telegram_id == OWNER_ID if author else False
            })
        
        db.close()
        return result
    except Exception as e:
        print(f"Comments error: {e}")
        return []

@app.post("/api/comments")
async def create_comment(
    post_id: int = Form(...),
    telegram_id: int = Form(...),
    content: str = Form(...)
):
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        sync_engine = create_engine(DATABASE_URL.replace("+aiosqlite", "").replace("postgresql+psycopg://", "postgresql://"), echo=False)
        SyncSessionLocal = sessionmaker(bind=sync_engine)
        db = SyncSessionLocal()
        
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            db.close()
            raise HTTPException(404, "Post not found")
        
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            db.close()
            raise HTTPException(404, "User not found")
        
        comment = Comment(post_id=post_id, author_id=user.id, content=content)
        db.add(comment)
        db.commit()
        db.refresh(comment)
        db.close()
        
        return {"id": comment.id}
    except Exception as e:
        print(f"Create comment error: {e}")
        raise HTTPException(500, str(e))

@app.delete("/api/comments/{comment_id}")
async def delete_comment(comment_id: int, telegram_id: int = Form(...)):
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        sync_engine = create_engine(DATABASE_URL.replace("+aiosqlite", "").replace("postgresql+psycopg://", "postgresql://"), echo=False)
        SyncSessionLocal = sessionmaker(bind=sync_engine)
        db = SyncSessionLocal()
        
        comment = db.query(Comment).filter(Comment.id == comment_id).first()
        if not comment:
            db.close()
            raise HTTPException(404, "Comment not found")
        
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            db.close()
            raise HTTPException(404, "User not found")
        
        if comment.author_id != user.id and user.telegram_id != OWNER_ID:
            db.close()
            raise HTTPException(403, "Not allowed")
        
        db.delete(comment)
        db.commit()
        db.close()
        return {"status": "deleted"}
    except Exception as e:
        print(f"Delete comment error: {e}")
        raise HTTPException(500, str(e))

# ===================== HTML ШАБЛОН =====================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
    <title>MLBB Team Finder</title>
    <link rel="stylesheet" href="/style.css">
</head>
<body>
    <div id="app">
        <header>
            <div class="header-top">
                <h1>🎮 MLBB Team</h1>
                <div class="user-info" id="user-info">
                    <span id="user-name">Гость</span>
                    <div class="user-avatar" id="user-avatar">👤</div>
                </div>
            </div>
        </header>
        
        <nav>
            <button class="tab-btn active" data-tab="feed">📋 Лента</button>
            <button class="tab-btn" data-tab="profile">👤 Профиль</button>
            <button class="tab-btn" data-tab="newpost">✏️ Пост</button>
        </nav>
        
        <main id="content" class="content">
            <div class="loading">
                <div class="spinner"></div>
                <p>Загрузка...</p>
            </div>
        </main>
    </div>
    
    <div id="auth-modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2>🔐 Вход</h2>
            </div>
            <div class="modal-body">
                <p>Введите ваш Telegram ID для входа:</p>
                <input type="number" id="telegram-id-input" placeholder="Ваш Telegram ID" class="modal-input">
                <button onclick="login()" class="modal-btn">Войти</button>
                <p style="font-size:12px;color:#8e8e93;margin-top:12px;">
                    Как узнать ID? Напишите <a href="https://t.me/userinfobot" target="_blank">@userinfobot</a>
                </p>
            </div>
        </div>
    </div>
    
    <script src="/script.js"></script>
</body>
</html>
'''

# ===================== CSS ШАБЛОН =====================
CSS_TEMPLATE = '''
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #f0f2f5;
    color: #1c1c1e;
    padding-bottom: 80px;
}

#app {
    max-width: 500px;
    margin: 0 auto;
    background: #ffffff;
    min-height: 100vh;
    box-shadow: 0 0 20px rgba(0,0,0,0.05);
}

header {
    background: linear-gradient(135deg, #007aff, #5856d6);
    padding: 20px 16px 12px;
    position: sticky;
    top: 0;
    z-index: 100;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

.header-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

header h1 {
    color: white;
    font-size: 20px;
    font-weight: 700;
}

.user-info {
    color: rgba(255,255,255,0.9);
    font-size: 13px;
    display: flex;
    align-items: center;
    gap: 8px;
}

.user-avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: rgba(255,255,255,0.2);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
}

nav {
    display: flex;
    background: #f8f9fc;
    border-bottom: 1px solid #e5e5ea;
    position: sticky;
    top: 78px;
    z-index: 99;
}

.tab-btn {
    flex: 1;
    padding: 12px 0;
    border: none;
    background: transparent;
    font-size: 14px;
    font-weight: 500;
    color: #8e8e93;
    cursor: pointer;
    transition: all 0.3s ease;
    position: relative;
}

.tab-btn.active {
    color: #007aff;
}

.tab-btn.active::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 50%;
    transform: translateX(-50%);
    width: 30px;
    height: 3px;
    background: #007aff;
    border-radius: 3px;
}

.content {
    padding: 16px;
    animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

.post-card {
    background: white;
    border-radius: 16px;
    padding: 16px;
    margin-bottom: 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    transition: all 0.2s ease;
}

.post-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}

.post-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
}

.post-author {
    font-weight: 600;
    font-size: 15px;
}

.post-time {
    color: #8e8e93;
    font-size: 12px;
    margin-left: auto;
}

.post-content {
    font-size: 15px;
    line-height: 1.5;
    margin-bottom: 10px;
    white-space: pre-wrap;
}

.post-photo {
    max-width: 100%;
    border-radius: 12px;
    margin-bottom: 12px;
    max-height: 300px;
    object-fit: cover;
}

.post-actions {
    display: flex;
    gap: 20px;
    padding-top: 12px;
    border-top: 1px solid #f0f2f5;
}

.action-btn {
    background: none;
    border: none;
    font-size: 14px;
    color: #8e8e93;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
    border-radius: 8px;
    transition: all 0.2s ease;
}

.action-btn:hover {
    background: #f0f2f5;
}

.action-btn.liked {
    color: #ff3b30;
}

.comments-section {
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid #f0f2f5;
}

.comment {
    padding: 8px 0;
    display: flex;
    gap: 8px;
    align-items: flex-start;
}

.comment-author {
    font-weight: 600;
    font-size: 13px;
    color: #007aff;
}

.comment-text {
    font-size: 14px;
    color: #1c1c1e;
}

.comment-input {
    display: flex;
    gap: 8px;
    margin-top: 8px;
}

.comment-input input {
    flex: 1;
    padding: 8px 12px;
    border: 1px solid #e5e5ea;
    border-radius: 20px;
    font-size: 14px;
    outline: none;
}

.comment-input input:focus {
    border-color: #007aff;
}

.comment-input button {
    padding: 8px 16px;
    background: #007aff;
    color: white;
    border: none;
    border-radius: 20px;
    cursor: pointer;
    font-weight: 600;
}

.comment-delete {
    background: none;
    border: none;
    color: #ff3b30;
    cursor: pointer;
    font-size: 12px;
    margin-left: auto;
    opacity: 0.6;
}

.comment-delete:hover {
    opacity: 1;
}

.profile-form, .new-post-form {
    background: white;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

.form-group {
    margin-bottom: 16px;
}

.form-group label {
    display: block;
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 4px;
    color: #1c1c1e;
}

.form-group input,
.form-group textarea,
.form-group select {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid #e5e5ea;
    border-radius: 10px;
    font-size: 15px;
    transition: border-color 0.2s ease;
    background: #f8f9fc;
}

.form-group input:focus,
.form-group textarea:focus,
.form-group select:focus {
    outline: none;
    border-color: #007aff;
    background: white;
}

.btn-submit, .btn-post {
    width: 100%;
    padding: 12px;
    background: linear-gradient(135deg, #007aff, #5856d6);
    color: white;
    border: none;
    border-radius: 12px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s ease;
}

.btn-submit:hover, .btn-post:hover {
    transform: scale(1.02);
    box-shadow: 0 4px 12px rgba(0,122,255,0.3);
}

.loading {
    text-align: center;
    padding: 40px;
    color: #8e8e93;
}

.spinner {
    width: 40px;
    height: 40px;
    border: 4px solid #f0f2f5;
    border-top: 4px solid #007aff;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin: 0 auto 12px;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

.empty-state {
    text-align: center;
    padding: 40px 20px;
    color: #8e8e93;
}

.empty-state .emoji {
    font-size: 48px;
    display: block;
    margin-bottom: 12px;
}

.delete-btn {
    background: none;
    border: none;
    color: #ff3b30;
    cursor: pointer;
    padding: 4px 8px;
    border-radius: 6px;
    font-size: 14px;
    opacity: 0.6;
    transition: all 0.2s ease;
}

.delete-btn:hover {
    opacity: 1;
    background: rgba(255,59,48,0.1);
}

.modal {
    display: block;
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.5);
    z-index: 999;
    animation: fadeIn 0.3s ease;
}

.modal-content {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: white;
    border-radius: 20px;
    padding: 30px;
    max-width: 400px;
    width: 90%;
    animation: slideUp 0.3s ease;
}

@keyframes slideUp {
    from { transform: translate(-50%, -40%); opacity: 0; }
    to { transform: translate(-50%, -50%); opacity: 1; }
}

.modal-header h2 {
    margin-bottom: 16px;
    color: #1c1c1e;
}

.modal-input {
    width: 100%;
    padding: 12px;
    border: 1px solid #e5e5ea;
    border-radius: 10px;
    font-size: 16px;
    margin: 12px 0;
}

.modal-btn {
    width: 100%;
    padding: 12px;
    background: #007aff;
    color: white;
    border: none;
    border-radius: 12px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
}

.modal-btn:hover {
    background: #0055b3;
}

.hidden {
    display: none !important;
}

.notification {
    position: fixed;
    top: 20px;
    left: 50%;
    transform: translateX(-50%);
    padding: 12px 24px;
    background: #34c759;
    color: white;
    border-radius: 12px;
    z-index: 1000;
    animation: slideDown 0.3s ease;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

@keyframes slideDown {
    from { transform: translateX(-50%) translateY(-20px); opacity: 0; }
    to { transform: translateX(-50%) translateY(0); opacity: 1; }
}
'''

# ===================== JAVASCRIPT ШАБЛОН =====================
JS_TEMPLATE = '''
let currentUser = null;
let currentTelegramId = null;

document.addEventListener('DOMContentLoaded', function() {
    const savedId = localStorage.getItem('telegram_id');
    if (savedId) {
        currentTelegramId = parseInt(savedId);
        document.getElementById('auth-modal').classList.add('hidden');
        initApp(currentTelegramId);
    }
    
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            switchTab(this.dataset.tab);
        });
    });
});

async function login() {
    const input = document.getElementById('telegram-id-input');
    const telegramId = parseInt(input.value);
    
    if (!telegramId || isNaN(telegramId)) {
        alert('Введите корректный Telegram ID');
        return;
    }
    
    try {
        const response = await fetch('/api/auth', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({
                telegram_id: telegramId,
                first_name: 'Игрок'
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            currentUser = data;
            currentTelegramId = telegramId;
            localStorage.setItem('telegram_id', telegramId);
            document.getElementById('auth-modal').classList.add('hidden');
            document.getElementById('user-name').textContent = data.first_name;
            initApp(telegramId);
            showNotification('✅ Добро пожаловать!');
        } else {
            alert('❌ Ошибка входа. Проверьте ID');
        }
    } catch (error) {
        console.error('Auth error:', error);
        alert('❌ Ошибка соединения');
    }
}

function showNotification(text) {
    const div = document.createElement('div');
    div.className = 'notification';
    div.textContent = text;
    document.body.appendChild(div);
    setTimeout(() => div.remove(), 3000);
}

async function initApp(telegramId) {
    await loadFeed(telegramId);
}

function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
    });
    
    switch(tab) {
        case 'feed': loadFeed(currentTelegramId); break;
        case 'profile': loadProfile(currentTelegramId); break;
        case 'newpost': showNewPost(); break;
    }
}

async function loadFeed(telegramId) {
    const content = document.getElementById('content');
    content.innerHTML = `
        <div class="loading">
            <div class="spinner"></div>
            <p>Загрузка постов...</p>
        </div>
    `;
    
    try {
        const response = await fetch(`/api/posts?telegram_id=${telegramId}`);
        const posts = await response.json();
        
        if (posts.length === 0) {
            content.innerHTML = `
                <div class="empty-state">
                    <span class="emoji">📭</span>
                    <h3>Пока нет постов</h3>
                    <p>Будьте первым, кто найдёт команду!</p>
                </div>
            `;
            return;
        }
        
        content.innerHTML = posts.map(post => renderPost(post)).join('');
        
        document.querySelectorAll('.like-btn').forEach(btn => {
            btn.addEventListener('click', handleLike);
        });
        
        document.querySelectorAll('.comment-btn').forEach(btn => {
            btn.addEventListener('click', handleCommentToggle);
        });
        
        document.querySelectorAll('.comment-submit').forEach(btn => {
            btn.addEventListener('click', handleCommentSubmit);
        });
        
        document.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', handleDelete);
        });
        
    } catch (error) {
        console.error('Feed error:', error);
        content.innerHTML = `
            <div class="empty-state">
                <span class="emoji">⚠️</span>
                <h3>Ошибка загрузки</h3>
                <p>Обновите страницу</p>
            </div>
        `;
    }
}

function renderPost(post) {
    const canDelete = (post.author_telegram_id === currentTelegramId || post.is_owner);
    const photoHtml = post.photo_url ? `<img src="${post.photo_url}" alt="Фото" class="post-photo">` : '';
    
    return `
        <div class="post-card" data-post-id="${post.id}">
            <div class="post-header">
                <span class="post-author">${post.author_name}</span>
                <span class="post-time">${post.created_at ? new Date(post.created_at).toLocaleString('ru-RU') : ''}</span>
                ${canDelete ? `<button class="delete-btn" data-post-id="${post.id}">🗑️</button>` : ''}
            </div>
            <div class="post-content">${post.content}</div>
            ${photoHtml}
            <div class="post-actions">
                <button class="action-btn like-btn" data-post-id="${post.id}">
                    ❤️ <span>${post.likes_count}</span>
                </button>
                <button class="action-btn comment-btn" data-post-id="${post.id}">
                    💬 <span>${post.comments_count}</span>
                </button>
            </div>
            <div class="comments-section" data-post-id="${post.id}" style="display:none;">
                <div class="comments-list"></div>
                <div class="comment-input">
                    <input type="text" placeholder="Написать комментарий..." class="comment-input-field" data-post-id="${post.id}">
                    <button class="comment-submit" data-post-id="${post.id}">➤</button>
                </div>
            </div>
        </div>
    `;
}

async function handleLike(e) {
    const btn = e.currentTarget;
    const postId = btn.dataset.postId;
    const span = btn.querySelector('span');
    
    try {
        const response = await fetch('/api/like', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({ post_id: postId, telegram_id: currentTelegramId })
        });
        
        const data = await response.json();
        if (data.liked) {
            btn.classList.add('liked');
            span.textContent = parseInt(span.textContent) + 1;
        } else {
            btn.classList.remove('liked');
            span.textContent = parseInt(span.textContent) - 1;
        }
    } catch (error) {
        console.error('Like error:', error);
    }
}

function handleCommentToggle(e) {
    const postId = e.currentTarget.dataset.postId;
    const section = document.querySelector(`.comments-section[data-post-id="${postId}"]`);
    
    if (section.style.display === 'none') {
        section.style.display = 'block';
        loadComments(postId);
    } else {
        section.style.display = 'none';
    }
}

async function loadComments(postId) {
    try {
        const response = await fetch(`/api/posts/${postId}/comments`);
        const comments = await response.json();
        const list = document.querySelector(`.comments-section[data-post-id="${postId}"] .comments-list`);
        
        if (comments.length === 0) {
            list.innerHTML = '<p style="color:#8e8e93;font-size:13px;padding:8px 0;">Нет комментариев</p>';
            return;
        }
        
        list.innerHTML = comments.map(c => `
            <div class="comment">
                <span class="comment-author">${c.author_name}</span>
                <span class="comment-text">${c.content}</span>
                ${(c.author_telegram_id === currentTelegramId || c.is_owner) ? `<button class="comment-delete" data-comment-id="${c.id}">🗑️</button>` : ''}
            </div>
        `).join('');
        
        list.querySelectorAll('.comment-delete').forEach(btn => {
            btn.addEventListener('click', handleCommentDelete);
        });
        
    } catch (error) {
        console.error('Comments load error:', error);
    }
}

async function handleCommentSubmit(e) {
    const btn = e.currentTarget;
    const postId = btn.dataset.postId;
    const input = document.querySelector(`.comment-input-field[data-post-id="${postId}"]`);
    const content = input.value.trim();
    
    if (!content) return;
    
    try {
        const response = await fetch('/api/comments', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({ post_id: postId, telegram_id: currentTelegramId, content })
        });
        
        if (response.ok) {
            input.value = '';
            await loadComments(postId);
            const commentBtn = document.querySelector(`.comment-btn[data-post-id="${postId}"]`);
            const span = commentBtn.querySelector('span:last-child');
            span.textContent = parseInt(span.textContent) + 1;
            showNotification('✅ Комментарий добавлен');
        }
    } catch (error) {
        console.error('Comment error:', error);
        showNotification('❌ Ошибка добавления комментария');
    }
}

async function handleDelete(e) {
    const btn = e.currentTarget;
    const postId = btn.dataset.postId;
    
    if (!confirm('Удалить этот пост?')) return;
    
    try {
        const response = await fetch(`/api/posts/${postId}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({ telegram_id: currentTelegramId })
        });
        
        if (response.ok) {
            const card = document.querySelector(`.post-card[data-post-id="${postId}"]`);
            card.style.opacity = '0';
            setTimeout(() => card.remove(), 300);
            showNotification('✅ Пост удален');
        }
    } catch (error) {
        console.error('Delete error:', error);
        showNotification('❌ Ошибка удаления');
    }
}

async function handleCommentDelete(e) {
    const btn = e.currentTarget;
    const commentId = btn.dataset.commentId;
    
    if (!confirm('Удалить комментарий?')) return;
    
    try {
        const response = await fetch(`/api/comments/${commentId}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({ telegram_id: currentTelegramId })
        });
        
        if (response.ok) {
            const comment = btn.closest('.comment');
            comment.style.opacity = '0';
            setTimeout(() => comment.remove(), 300);
            showNotification('✅ Комментарий удален');
        }
    } catch (error) {
        console.error('Comment delete error:', error);
        showNotification('❌ Ошибка удаления комментария');
    }
}

async function loadProfile(telegramId) {
    const content = document.getElementById('content');
    content.innerHTML = `
        <div class="loading">
            <div class="spinner"></div>
            <p>Загрузка профиля...</p>
        </div>
    `;
    
    try {
        const response = await fetch(`/api/profile/${telegramId}`);
        const profile = await response.json();
        
        if (!profile) {
            content.innerHTML = `
                <div class="profile-form">
                    <h2 style="margin-bottom:16px;">👤 Создать профиль</h2>
                    <form id="profileForm">
                        <div class="form-group">
                            <label>Ник в MLBB</label>
                            <input type="text" name="nickname_mlbb" required>
                        </div>
                        <div class="form-group">
                            <label>Роль</label>
                            <select name="role" required>
                                <option value="Tank">Tank</option>
                                <option value="Fighter">Fighter</option>
                                <option value="Assassin">Assassin</option>
                                <option value="Mage">Mage</option>
                                <option value="Marksman">Marksman</option>
                                <option value="Support">Support</option>
                                <option value="Flex">Flex</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Ранг</label>
                            <select name="rank" required>
                                <option value="Warrior">Warrior</option>
                                <option value="Elite">Elite</option>
                                <option value="Master">Master</option>
                                <option value="Grandmaster">Grandmaster</option>
                                <option value="Epic">Epic</option>
                                <option value="Legend">Legend</option>
                                <option value="Mythic">Mythic</option>
                                <option value="Mythical Glory">Mythical Glory</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>О себе</label>
                            <textarea name="description"></textarea>
                        </div>
                        <div class="form-group">
                            <label>Ссылка на фото</label>
                            <input type="url" name="photo_url" placeholder="https://example.com/photo.jpg">
                        </div>
                        <button type="submit" class="btn-submit">💾 Сохранить профиль</button>
                    </form>
                </div>
            `;
            document.getElementById('profileForm').addEventListener('submit', handleProfileSubmit);
            return;
        }
        
        content.innerHTML = `
            <div class="profile-form">
                <h2 style="margin-bottom:16px;">👤 Мой профиль</h2>
                <form id="profileForm">
                    <div class="form-group">
                        <label>Ник в MLBB</label>
                        <input type="text" name="nickname_mlbb" value="${profile.nickname_mlbb || ''}" required>
                    </div>
                    <div class="form-group">
                        <label>Роль</label>
                        <select name="role" required>
                            <option value="Tank" ${profile.role === 'Tank' ? 'selected' : ''}>Tank</option>
                            <option value="Fighter" ${profile.role === 'Fighter' ? 'selected' : ''}>Fighter</option>
                            <option value="Assassin" ${profile.role === 'Assassin' ? 'selected' : ''}>Assassin</option>
                            <option value="Mage" ${profile.role === 'Mage' ? 'selected' : ''}>Mage</option>
                            <option value="Marksman" ${profile.role === 'Marksman' ? 'selected' : ''}>Marksman</option>
                            <option value="Support" ${profile.role === 'Support' ? 'selected' : ''}>Support</option>
                            <option value="Flex" ${profile.role === 'Flex' ? 'selected' : ''}>Flex</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Ранг</label>
                        <select name="rank" required>
                            <option value="Warrior" ${profile.rank === 'Warrior' ? 'selected' : ''}>Warrior</option>
                            <option value="Elite" ${profile.rank === 'Elite' ? 'selected' : ''}>Elite</option>
                            <option value="Master" ${profile.rank === 'Master' ? 'selected' : ''}>Master</option>
                            <option value="Grandmaster" ${profile.rank === 'Grandmaster' ? 'selected' : ''}>Grandmaster</option>
                            <option value="Epic" ${profile.rank === 'Epic' ? 'selected' : ''}>Epic</option>
                            <option value="Legend" ${profile.rank === 'Legend' ? 'selected' : ''}>Legend</option>
                            <option value="Mythic" ${profile.rank === 'Mythic' ? 'selected' : ''}>Mythic</option>
                            <option value="Mythical Glory" ${profile.rank === 'Mythical Glory' ? 'selected' : ''}>Mythical Glory</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>О себе</label>
                        <textarea name="description">${profile.description || ''}</textarea>
                    </div>
                    <div class="form-group">
                        <label>Ссылка на фото</label>
                        <input type="url" name="photo_url" value="${profile.photo_url || ''}" placeholder="https://example.com/photo.jpg">
                    </div>
                    <button type="submit" class="btn-submit">💾 Сохранить профиль</button>
                </form>
            </div>
        `;
        document.getElementById('profileForm').addEventListener('submit', handleProfileSubmit);
        
    } catch (error) {
        console.error('Profile load error:', error);
        content.innerHTML = `
            <div class="empty-state">
                <span class="emoji">⚠️</span>
                <h3>Ошибка загрузки профиля</h3>
                <p>Обновите страницу</p>
            </div>
        `;
    }
}

async function handleProfileSubmit(e) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);
    formData.append('telegram_id', currentTelegramId);
    
    try {
        const response = await fetch('/api/profile', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            showNotification('✅ Профиль сохранён!');
            await loadProfile(currentTelegramId);
        } else {
            showNotification('❌ Ошибка сохранения');
        }
    } catch (error) {
        console.error('Profile save error:', error);
        showNotification('❌ Ошибка сохранения профиля');
    }
}

function showNewPost() {
    const content = document.getElementById('content');
    content.innerHTML = `
        <div class="new-post-form">
            <h2 style="margin-bottom:16px;">✏️ Новый пост</h2>
            <form id="newPostForm">
                <div class="form-group">
                    <label>Текст поста</label>
                    <textarea name="content" placeholder="Расскажите, кого ищете в команду..." required></textarea>
                </div>
                <div class="form-group">
                    <label>Ссылка на фото (необязательно)</label>
                    <input type="url" name="photo_url" placeholder="https://example.com/photo.jpg">
                </div>
                <button type="submit" class="btn-post">📤 Опубликовать</button>
            </form>
        </div>
    `;
    
    document.getElementById('newPostForm').addEventListener('submit', handlePostSubmit);
}

async function handlePostSubmit(e) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);
    formData.append('telegram_id', currentTelegramId);
    
    const btn = form.querySelector('.btn-post');
    btn.textContent = '⏳ Публикация...';
    btn.disabled = true;
    
    try {
        const response = await fetch('/api/posts', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            showNotification('✅ Пост опубликован!');
            btn.textContent = '✅ Готово!';
            setTimeout(() => {
                switchTab('feed');
                loadFeed(currentTelegramId);
            }, 1000);
        } else {
            showNotification('❌ Ошибка публикации');
            btn.textContent = '📤 Опубликовать';
            btn.disabled = false;
        }
    } catch (error) {
        console.error('Post error:', error);
        showNotification('❌ Ошибка публикации');
        btn.textContent = '📤 Опубликовать';
        btn.disabled = false;
    }
}

// Вход по Enter
document.getElementById('telegram-id-input')?.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') login();
});
'''

# ===================== ЗАПУСК =====================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
