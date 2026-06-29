import os
import datetime
import json
from typing import Optional, List
from fastapi import FastAPI, Request, Form, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Boolean,
    UniqueConstraint, create_engine, func, and_, or_, desc
)
from sqlalchemy.orm import relationship, declarative_base, sessionmaker, Session
import uvicorn

# ===================== КОНФИГ =====================
OWNER_ID = 5391287151  # Ваш Telegram ID (администратор)
DATABASE_URL = "sqlite:///mlbb.db"

# ===================== БАЗА ДАННЫХ =====================
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# ---------------------- МОДЕЛИ (ПОЛНАЯ ВЕРСИЯ) ----------------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=False, default="Игрок")
    last_name = Column(String(255), nullable=True)
    is_admin = Column(Boolean, default=False)
    is_premium = Column(Boolean, default=False)
    premium_until = Column(DateTime, nullable=True)
    is_banned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    profile = relationship("Profile", back_populates="user", uselist=False)
    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="author", cascade="all, delete-orphan")
    likes = relationship("Like", back_populates="user", cascade="all, delete-orphan")
    reposts = relationship("Repost", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    messages_sent = relationship("Message", foreign_keys="Message.sender_id", back_populates="sender")
    messages_received = relationship("Message", foreign_keys="Message.receiver_id", back_populates="receiver")
    reports_sent = relationship("Report", foreign_keys="Report.reporter_id", back_populates="reporter", cascade="all, delete-orphan")
    reports_resolved = relationship("Report", foreign_keys="Report.resolved_by", back_populates="resolver", cascade="all, delete-orphan")
    achievements = relationship("Achievement", back_populates="user", cascade="all, delete-orphan")
    poll_votes = relationship("PollVote", back_populates="user", cascade="all, delete-orphan")
    chat_members = relationship("ChatMember", back_populates="user", cascade="all, delete-orphan")
    swipe_likes = relationship("SwipeLike", foreign_keys="SwipeLike.from_user_id", back_populates="from_user", cascade="all, delete-orphan")
    swipe_received = relationship("SwipeLike", foreign_keys="SwipeLike.to_user_id", back_populates="to_user", cascade="all, delete-orphan")

class Profile(Base):
    __tablename__ = "profiles"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    nickname_mlbb = Column(String(255), nullable=False)
    role = Column(String(100), nullable=False)
    rank = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    photo_url = Column(String(500), nullable=True)
    country = Column(String(100), nullable=True)
    preferred_language = Column(String(50), nullable=True)
    looking_for = Column(String(100), nullable=True)
    play_style = Column(String(100), nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)
    is_visible_for_swipe = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    user = relationship("User", back_populates="profile")

class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    author_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    photo_url = Column(String(500), nullable=True)
    tags = Column(String(255), nullable=True)
    is_pinned = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    has_poll = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    author = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    likes = relationship("Like", back_populates="post", cascade="all, delete-orphan")
    reposts = relationship("Repost", back_populates="post", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="post", cascade="all, delete-orphan")
    poll = relationship("Poll", back_populates="post", uselist=False, cascade="all, delete-orphan")

class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id"))
    author_id = Column(Integer, ForeignKey("users.id"))
    content = Column(Text, nullable=False)
    is_edited = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    post = relationship("Post", back_populates="comments")
    author = relationship("User", back_populates="comments")
    reports = relationship("Report", back_populates="comment", cascade="all, delete-orphan")

class Like(Base):
    __tablename__ = "likes"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    post_id = Column(Integer, ForeignKey("posts.id"))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    __table_args__ = (UniqueConstraint('user_id', 'post_id', name='unique_like'),)
    user = relationship("User", back_populates="likes")
    post = relationship("Post", back_populates="likes")

class Repost(Base):
    __tablename__ = "reposts"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    post_id = Column(Integer, ForeignKey("posts.id"))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    __table_args__ = (UniqueConstraint('user_id', 'post_id', name='unique_repost'),)
    user = relationship("User", back_populates="reposts")
    post = relationship("Post", back_populates="reposts")

class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True)
    reporter_id = Column(Integer, ForeignKey("users.id"))
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    comment_id = Column(Integer, ForeignKey("comments.id"), nullable=True)
    reason = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_resolved = Column(Boolean, default=False)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    reporter = relationship("User", foreign_keys=[reporter_id], back_populates="reports_sent")
    resolver = relationship("User", foreign_keys=[resolved_by], back_populates="reports_resolved")
    post = relationship("Post", back_populates="reports")
    comment = relationship("Comment", back_populates="reports")

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    link = Column(String(500), nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    user = relationship("User", back_populates="notifications")

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    sender_id = Column(Integer, ForeignKey("users.id"))
    receiver_id = Column(Integer, ForeignKey("users.id"))
    content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    sender = relationship("User", foreign_keys=[sender_id], back_populates="messages_sent")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="messages_received")

class Poll(Base):
    __tablename__ = "polls"
    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id"), unique=True)
    question = Column(String(255), nullable=False)
    options = Column(Text, nullable=False)  # JSON-массив
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    post = relationship("Post", back_populates="poll")
    votes = relationship("PollVote", back_populates="poll", cascade="all, delete-orphan")

class PollVote(Base):
    __tablename__ = "poll_votes"
    id = Column(Integer, primary_key=True)
    poll_id = Column(Integer, ForeignKey("polls.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    option_index = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    __table_args__ = (UniqueConstraint('poll_id', 'user_id', name='unique_poll_vote'),)
    poll = relationship("Poll", back_populates="votes")
    user = relationship("User", back_populates="poll_votes")

class Achievement(Base):
    __tablename__ = "achievements"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(String(50), nullable=False)
    level = Column(Integer, default=1)
    unlocked_at = Column(DateTime, default=datetime.datetime.utcnow)
    user = relationship("User", back_populates="achievements")

class Chat(Base):
    __tablename__ = "chats"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_private = Column(Boolean, default=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    members = relationship("ChatMember", back_populates="chat", cascade="all, delete-orphan")
    messages = relationship("ChatMessage", back_populates="chat", cascade="all, delete-orphan")

class ChatMember(Base):
    __tablename__ = "chat_members"
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    joined_at = Column(DateTime, default=datetime.datetime.utcnow)
    chat = relationship("Chat", back_populates="members")
    user = relationship("User", back_populates="chat_members")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    chat = relationship("Chat", back_populates="messages")
    user = relationship("User")

class SwipeLike(Base):
    __tablename__ = "swipe_likes"
    id = Column(Integer, primary_key=True)
    from_user_id = Column(Integer, ForeignKey("users.id"))
    to_user_id = Column(Integer, ForeignKey("users.id"))
    liked = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    __table_args__ = (UniqueConstraint('from_user_id', 'to_user_id', name='unique_swipe'),)
    from_user = relationship("User", foreign_keys=[from_user_id], back_populates="swipe_likes")
    to_user = relationship("User", foreign_keys=[to_user_id], back_populates="swipe_received")

Base.metadata.create_all(engine)

# ===================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_or_create_user(telegram_id: int, username: str = None, first_name: str = "Игрок", db: Session = None) -> User:
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            is_admin=(telegram_id == OWNER_ID)
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        ach = Achievement(user_id=user.id, type="welcome", level=1)
        db.add(ach)
        db.commit()
    if close_db:
        db.close()
    return user

def create_notification(user_id: int, type: str, message: str, link: str = None, db: Session = None):
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    notif = Notification(user_id=user_id, type=type, message=message, link=link)
    db.add(notif)
    db.commit()
    if close_db:
        db.close()

def is_premium(user: User) -> bool:
    if not user.is_premium:
        return False
    if user.premium_until and user.premium_until < datetime.datetime.utcnow():
        user.is_premium = False
        user.premium_until = None
        db = SessionLocal()
        db.add(user)
        db.commit()
        db.close()
        return False
    return True

def check_achievements(user_id: int, db: Session):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return
    posts_count = db.query(Post).filter(Post.author_id == user_id).count()
    likes_count = db.query(Like).filter(Like.user_id == user_id).count()
    comments_count = db.query(Comment).filter(Comment.author_id == user_id).count()
    reposts_count = db.query(Repost).filter(Repost.user_id == user_id).count()

    types = [
        ("posts", posts_count),
        ("likes", likes_count),
        ("comments", comments_count),
        ("reposts", reposts_count)
    ]
    for ach_type, count in types:
        if count >= 1:
            existing = db.query(Achievement).filter(and_(Achievement.user_id == user_id, Achievement.type == ach_type, Achievement.level == 1)).first()
            if not existing:
                ach = Achievement(user_id=user_id, type=ach_type, level=1)
                db.add(ach)
                create_notification(user_id, "achievement", f"🏆 Достижение: {ach_type.capitalize()}!", None, db)
                db.commit()
        if count >= 10:
            existing = db.query(Achievement).filter(and_(Achievement.user_id == user_id, Achievement.type == ach_type, Achievement.level == 2)).first()
            if not existing:
                ach = Achievement(user_id=user_id, type=ach_type, level=2)
                db.add(ach)
                create_notification(user_id, "achievement", f"🏆 Новый уровень: {ach_type.capitalize()} (10+)!", None, db)
                db.commit()
        if count >= 50:
            existing = db.query(Achievement).filter(and_(Achievement.user_id == user_id, Achievement.type == ach_type, Achievement.level == 3)).first()
            if not existing:
                ach = Achievement(user_id=user_id, type=ach_type, level=3)
                db.add(ach)
                create_notification(user_id, "achievement", f"🏆 Максимум: {ach_type.capitalize()} (50+)!", None, db)
                db.commit()

# ===================== FASTAPI =====================
app = FastAPI(title="MLBB Nexus")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===================== HTML (НОВЫЙ ДИЗАЙН) =====================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>MLBB Nexus</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #6C63FF;
            --primary-light: #8B83FF;
            --primary-dark: #4A42CC;
            --gradient: linear-gradient(135deg, #6C63FF, #3F3D56);
            --bg: #F8F9FE;
            --card-bg: #FFFFFF;
            --text-primary: #1A1A2E;
            --text-secondary: #6B7280;
            --border: #E5E7EB;
            --shadow: 0 8px 30px rgba(108, 99, 255, 0.08);
            --radius: 20px;
            --transition: 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg);
            color: var(--text-primary);
            padding-bottom: 80px;
            -webkit-font-smoothing: antialiased;
        }
        #app { max-width: 640px; margin: 0 auto; background: var(--bg); min-height: 100vh; }
        header {
            background: var(--gradient);
            padding: 20px 20px 14px;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: 0 4px 20px rgba(108, 99, 255, 0.25);
            border-radius: 0 0 30px 30px;
        }
        .header-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }
        header h1 {
            color: white;
            font-size: 24px;
            font-weight: 800;
            letter-spacing: -0.5px;
            text-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        header h1 span { font-weight: 400; opacity: 0.8; }
        .user-info {
            display: flex;
            align-items: center;
            gap: 12px;
            color: rgba(255,255,255,0.95);
            font-size: 14px;
            font-weight: 500;
        }
        .user-avatar {
            width: 38px;
            height: 38px;
            border-radius: 50%;
            background: rgba(255,255,255,0.2);
            backdrop-filter: blur(6px);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            color: white;
            border: 2px solid rgba(255,255,255,0.4);
            transition: var(--transition);
        }
        .user-avatar:hover { transform: scale(1.05); }
        .notif-btn {
            background: rgba(255,255,255,0.15);
            border: none;
            color: white;
            font-size: 20px;
            padding: 6px 12px;
            border-radius: 30px;
            cursor: pointer;
            position: relative;
            backdrop-filter: blur(6px);
            transition: var(--transition);
        }
        .notif-btn:hover { background: rgba(255,255,255,0.25); }
        .notif-count {
            position: absolute;
            top: -4px;
            right: -4px;
            background: #FF6B6B;
            color: white;
            border-radius: 50%;
            padding: 2px 6px;
            font-size: 11px;
            font-weight: 700;
            min-width: 18px;
            text-align: center;
        }
        .search-bar {
            display: flex;
            gap: 8px;
            background: rgba(255,255,255,0.15);
            padding: 4px;
            border-radius: 30px;
            backdrop-filter: blur(6px);
        }
        .search-bar input {
            flex: 1;
            padding: 10px 18px;
            border: none;
            border-radius: 30px;
            background: rgba(255,255,255,0.9);
            font-size: 14px;
            outline: none;
            transition: var(--transition);
            color: var(--text-primary);
        }
        .search-bar input:focus { background: white; box-shadow: 0 0 0 2px rgba(255,255,255,0.5); }
        .search-bar button {
            padding: 10px 24px;
            border: none;
            border-radius: 30px;
            background: white;
            color: var(--primary);
            font-weight: 600;
            cursor: pointer;
            transition: var(--transition);
        }
        .search-bar button:hover { background: #f0f2ff; }
        nav {
            display: flex;
            background: white;
            border-bottom: 1px solid var(--border);
            position: sticky;
            top: 128px;
            z-index: 99;
            overflow-x: auto;
            padding: 0 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.02);
            border-radius: 20px 20px 0 0;
            margin-top: -8px;
        }
        .tab-btn {
            flex: 0 0 auto;
            padding: 14px 18px;
            border: none;
            background: transparent;
            font-size: 14px;
            font-weight: 500;
            color: var(--text-secondary);
            cursor: pointer;
            transition: var(--transition);
            position: relative;
            white-space: nowrap;
        }
        .tab-btn.active {
            color: var(--primary);
            font-weight: 600;
        }
        .tab-btn.active::after {
            content: '';
            position: absolute;
            bottom: 0;
            left: 50%;
            transform: translateX(-50%);
            width: 32px;
            height: 3px;
            background: var(--primary);
            border-radius: 3px;
        }
        .tab-btn:hover { color: var(--primary); }
        .content {
            padding: 16px;
            animation: fadeIn 0.4s ease;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .post-card {
            background: var(--card-bg);
            border-radius: var(--radius);
            padding: 20px;
            margin-bottom: 16px;
            box-shadow: var(--shadow);
            transition: var(--transition);
            border: 1px solid rgba(108, 99, 255, 0.04);
        }
        .post-card:hover { box-shadow: 0 12px 40px rgba(108, 99, 255, 0.12); transform: translateY(-2px); }
        .post-header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 10px;
            flex-wrap: wrap;
        }
        .post-title {
            font-size: 18px;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 4px;
        }
        .post-author {
            font-weight: 500;
            font-size: 14px;
            color: var(--primary);
            cursor: pointer;
            transition: var(--transition);
        }
        .post-author:hover { opacity: 0.7; }
        .premium-name {
            background: linear-gradient(90deg, #FF6B6B, #FFD93D, #6BCB77, #4D96FF, #FF6B6B);
            background-size: 200%;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 700;
            animation: shimmer 4s linear infinite;
        }
        @keyframes shimmer {
            0% { background-position: 0% 50%; }
            100% { background-position: 200% 50%; }
        }
        .premium-frame {
            border: 2px solid transparent;
            border-image: linear-gradient(45deg, #FF6B6B, #FFD93D, #6BCB77, #4D96FF) 1;
            border-radius: var(--radius);
            padding: 4px;
        }
        .post-time {
            color: var(--text-secondary);
            font-size: 12px;
            margin-left: auto;
        }
        .post-content {
            font-size: 15px;
            line-height: 1.7;
            margin: 8px 0 12px;
            white-space: pre-wrap;
            word-break: break-word;
        }
        .post-tags { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; }
        .tag {
            background: #EEF2FF;
            padding: 3px 14px;
            border-radius: 30px;
            font-size: 12px;
            color: var(--primary);
            font-weight: 500;
        }
        .post-photo {
            max-width: 100%;
            border-radius: 16px;
            margin-bottom: 12px;
            max-height: 400px;
            object-fit: cover;
            box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        }
        .post-actions {
            display: flex;
            gap: 20px;
            padding-top: 12px;
            border-top: 1px solid #F0F2FF;
            flex-wrap: wrap;
        }
        .action-btn {
            background: none;
            border: none;
            font-size: 14px;
            color: var(--text-secondary);
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 6px 14px;
            border-radius: 30px;
            transition: var(--transition);
            font-weight: 500;
        }
        .action-btn:hover { background: #F0F2FF; }
        .action-btn.liked { color: #FF6B6B; }
        .action-btn.liked .heart { animation: heartBeat 0.5s ease; }
        @keyframes heartBeat {
            0% { transform: scale(1); }
            20% { transform: scale(1.3); }
            40% { transform: scale(1); }
            60% { transform: scale(1.2); }
            80% { transform: scale(1); }
            100% { transform: scale(1); }
        }
        .comments-section {
            margin-top: 14px;
            padding-top: 14px;
            border-top: 1px solid #F0F2FF;
        }
        .comment {
            padding: 8px 0;
            display: flex;
            gap: 10px;
            align-items: flex-start;
        }
        .comment-author {
            font-weight: 600;
            font-size: 13px;
            color: var(--primary);
        }
        .comment-text {
            font-size: 14px;
            color: var(--text-primary);
        }
        .comment-time {
            font-size: 11px;
            color: var(--text-secondary);
            margin-left: 8px;
        }
        .comment-input {
            display: flex;
            gap: 8px;
            margin-top: 10px;
        }
        .comment-input input {
            flex: 1;
            padding: 10px 18px;
            border: 1px solid var(--border);
            border-radius: 30px;
            font-size: 14px;
            outline: none;
            transition: var(--transition);
            background: #F8F9FE;
        }
        .comment-input input:focus { border-color: var(--primary); background: white; }
        .comment-input button {
            padding: 10px 24px;
            background: var(--primary);
            color: white;
            border: none;
            border-radius: 30px;
            cursor: pointer;
            font-weight: 600;
            transition: var(--transition);
        }
        .comment-input button:hover { background: var(--primary-dark); transform: scale(1.02); }
        .comment-delete, .post-delete, .report-btn {
            background: none;
            border: none;
            color: #FF6B6B;
            cursor: pointer;
            font-size: 12px;
            margin-left: auto;
            opacity: 0.5;
            padding: 2px 10px;
            border-radius: 30px;
            transition: var(--transition);
        }
        .comment-delete:hover, .post-delete:hover { opacity: 1; background: rgba(255,107,107,0.08); }
        .report-btn { color: #FFB347; }
        .report-btn:hover { opacity: 1; background: rgba(255,179,71,0.08); }
        .repost-btn { color: #4D96FF; }
        .repost-btn:hover { opacity: 1; background: rgba(77,150,255,0.08); }
        .msg-btn {
            background: none;
            border: none;
            color: var(--primary);
            cursor: pointer;
            font-size: 14px;
            padding: 4px 12px;
            border-radius: 30px;
            transition: var(--transition);
        }
        .msg-btn:hover { background: rgba(108,99,255,0.08); }
        .profile-form, .new-post-form, .admin-panel {
            background: var(--card-bg);
            border-radius: var(--radius);
            padding: 24px;
            box-shadow: var(--shadow);
        }
        .form-group { margin-bottom: 20px; }
        .form-group label {
            display: block;
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 6px;
            color: var(--text-primary);
        }
        .form-group input, .form-group textarea, .form-group select {
            width: 100%;
            padding: 12px 16px;
            border: 1px solid var(--border);
            border-radius: 14px;
            font-size: 15px;
            background: #F8F9FE;
            transition: var(--transition);
            font-family: inherit;
        }
        .form-group input:focus, .form-group textarea:focus, .form-group select:focus {
            outline: none;
            border-color: var(--primary);
            background: white;
            box-shadow: 0 0 0 3px rgba(108,99,255,0.1);
        }
        .btn-submit, .btn-post {
            width: 100%;
            padding: 14px;
            background: var(--gradient);
            color: white;
            border: none;
            border-radius: 16px;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            transition: var(--transition);
            box-shadow: 0 4px 16px rgba(108,99,255,0.25);
        }
        .btn-submit:hover, .btn-post:hover {
            transform: scale(1.02);
            box-shadow: 0 6px 24px rgba(108,99,255,0.35);
        }
        .btn-submit:active, .btn-post:active { transform: scale(0.98); }
        .loading {
            text-align: center;
            padding: 60px 20px;
            color: var(--text-secondary);
        }
        .spinner {
            width: 48px;
            height: 48px;
            border: 4px solid #E5E7EB;
            border-top: 4px solid var(--primary);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin: 0 auto 16px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: var(--text-secondary);
        }
        .empty-state .emoji { font-size: 56px; display: block; margin-bottom: 16px; }
        .modal {
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(26,26,46,0.6);
            backdrop-filter: blur(12px);
            z-index: 999;
            display: flex;
            align-items: center;
            justify-content: center;
            animation: fadeIn 0.25s ease;
        }
        .modal.hidden { display: none; }
        .modal-content {
            background: white;
            border-radius: 28px;
            padding: 32px;
            max-width: 440px;
            width: 92%;
            animation: slideUp 0.3s ease;
            box-shadow: 0 20px 60px rgba(0,0,0,0.15);
        }
        @keyframes slideUp {
            from { transform: translateY(20px) scale(0.96); opacity: 0; }
            to { transform: translateY(0) scale(1); opacity: 1; }
        }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .modal-header h2 { font-size: 20px; font-weight: 700; }
        .modal-input {
            width: 100%;
            padding: 14px 18px;
            border: 1px solid var(--border);
            border-radius: 16px;
            font-size: 16px;
            margin: 8px 0;
            transition: var(--transition);
            background: #F8F9FE;
        }
        .modal-input:focus { outline: none; border-color: var(--primary); background: white; }
        .modal-btn {
            width: 100%;
            padding: 14px;
            background: var(--gradient);
            color: white;
            border: none;
            border-radius: 16px;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            transition: var(--transition);
        }
        .modal-btn:hover { transform: scale(1.02); }
        .notification {
            position: fixed;
            top: 24px;
            left: 50%;
            transform: translateX(-50%);
            padding: 14px 28px;
            background: #34C759;
            color: white;
            border-radius: 30px;
            z-index: 1000;
            animation: slideDown 0.4s ease;
            box-shadow: 0 8px 24px rgba(52,199,89,0.3);
            font-weight: 500;
            backdrop-filter: blur(6px);
        }
        @keyframes slideDown {
            from { transform: translateX(-50%) translateY(-30px); opacity: 0; }
            to { transform: translateX(-50%) translateY(0); opacity: 1; }
        }
        .notifications-panel {
            position: fixed;
            right: 0; top: 0;
            width: 380px;
            max-height: 100vh;
            background: white;
            box-shadow: -4px 0 30px rgba(0,0,0,0.06);
            padding: 20px;
            overflow-y: auto;
            z-index: 200;
            transform: translateX(100%);
            transition: transform 0.35s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .notifications-panel.open { transform: translateX(0); }
        .notif-header {
            display: flex;
            justify-content: space-between;
            font-weight: 700;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border);
        }
        .notif-item {
            padding: 12px 0;
            border-bottom: 1px solid #F0F2FF;
            font-size: 14px;
        }
        .notif-item .notif-time { font-size: 11px; color: var(--text-secondary); }
        .admin-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
            margin-top: 12px;
        }
        .admin-table th, .admin-table td {
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }
        .admin-table th {
            background: #F8F9FE;
            font-weight: 600;
        }
        .admin-btn {
            padding: 4px 16px;
            border: none;
            border-radius: 30px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 600;
            transition: var(--transition);
        }
        .admin-btn.danger { background: #FF6B6B; color: white; }
        .admin-btn.success { background: #34C759; color: white; }
        .admin-btn.primary { background: var(--primary); color: white; }
        .admin-btn:hover { transform: scale(1.05); opacity: 0.9; }
        .swipe-container {
            position: relative;
            height: 540px;
            margin: 0 auto;
            perspective: 1000px;
        }
        .swipe-card {
            position: absolute;
            width: 100%;
            height: 100%;
            background: white;
            border-radius: 28px;
            box-shadow: 0 8px 40px rgba(0,0,0,0.06);
            padding: 24px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            transition: transform 0.4s ease, opacity 0.3s ease;
            border: 1px solid rgba(108,99,255,0.04);
            backface-visibility: hidden;
        }
        .swipe-card .profile-photo {
            width: 140px;
            height: 140px;
            border-radius: 50%;
            object-fit: cover;
            margin-bottom: 16px;
            border: 3px solid white;
            box-shadow: 0 4px 16px rgba(0,0,0,0.06);
        }
        .swipe-card .profile-name { font-size: 26px; font-weight: 800; margin-bottom: 4px; }
        .swipe-card .profile-details { color: var(--text-secondary); font-size: 15px; margin-top: 4px; text-align: center; }
        .swipe-buttons {
            display: flex;
            gap: 40px;
            justify-content: center;
            margin-top: 24px;
        }
        .swipe-btn {
            width: 68px;
            height: 68px;
            border-radius: 50%;
            border: none;
            font-size: 32px;
            cursor: pointer;
            transition: var(--transition);
            box-shadow: 0 4px 16px rgba(0,0,0,0.06);
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .swipe-btn:hover { transform: scale(1.1); }
        .swipe-btn.like { background: #34C759; color: white; }
        .swipe-btn.dislike { background: #FF6B6B; color: white; }
        .swipe-btn:active { transform: scale(0.92); }
        .message-item {
            padding: 10px 18px;
            margin: 6px 0;
            border-radius: 24px;
            max-width: 80%;
            word-break: break-word;
            box-shadow: 0 1px 4px rgba(0,0,0,0.02);
            animation: fadeIn 0.2s ease;
        }
        .message-item.sent {
            background: var(--primary);
            color: white;
            align-self: flex-end;
            border-bottom-right-radius: 4px;
        }
        .message-item.received {
            background: #F0F2FF;
            color: var(--text-primary);
            align-self: flex-start;
            border-bottom-left-radius: 4px;
        }
        .message-time { font-size: 10px; opacity: 0.7; margin-top: 4px; }
        .dialog-card, .chat-card {
            background: var(--card-bg);
            border-radius: var(--radius);
            padding: 16px 20px;
            margin-bottom: 10px;
            box-shadow: var(--shadow);
            cursor: pointer;
            transition: var(--transition);
            border: 1px solid transparent;
        }
        .dialog-card:hover, .chat-card:hover {
            border-color: var(--primary);
            transform: translateX(4px);
        }
        .dialog-name { font-weight: 600; }
        .dialog-last { color: var(--text-secondary); font-size: 14px; }
        .poll-options { margin: 8px 0; }
        .poll-option {
            padding: 10px 14px;
            margin: 4px 0;
            background: #F8F9FE;
            border-radius: 14px;
            cursor: pointer;
            transition: var(--transition);
            font-weight: 500;
        }
        .poll-option:hover { background: #E5E7EB; }
        .poll-option.voted { background: var(--primary); color: white; }
        .poll-option .poll-bar {
            height: 4px;
            background: var(--primary);
            border-radius: 2px;
            margin-top: 4px;
        }
        .poll-option.voted .poll-bar { background: white; }
        .achievement-badge {
            display: inline-block;
            background: #F0F2FF;
            padding: 4px 16px;
            border-radius: 30px;
            font-size: 12px;
            margin: 2px;
            font-weight: 500;
        }
        .achievement-badge .level { color: var(--primary); font-weight: 700; }
        @media (max-width: 480px) {
            .header-top h1 { font-size: 20px; }
            .tab-btn { padding: 10px 14px; font-size: 13px; }
            .notifications-panel { width: 100%; }
            .modal-content { padding: 24px; }
        }
    </style>
</head>
<body>
    <div id="app">
        <header>
            <div class="header-top">
                <h1>MLBB <span>Nexus</span></h1>
                <div class="user-info">
                    <span id="user-name">Гость</span>
                    <div class="user-avatar" id="user-avatar">👤</div>
                    <button id="notif-btn" class="notif-btn">🔔<span id="notif-count" class="notif-count">0</span></button>
                </div>
            </div>
            <div id="search-bar" class="search-bar">
                <input type="text" id="search-input" placeholder="🔍 Поиск по постам, тегам...">
                <button id="search-btn">Найти</button>
            </div>
        </header>
        <nav>
            <button class="tab-btn active" data-tab="feed">📋 Лента</button>
            <button class="tab-btn" data-tab="swipe">💞 Свайп</button>
            <button class="tab-btn" data-tab="profile">👤 Профиль</button>
            <button class="tab-btn" data-tab="newpost">✏️ Пост</button>
            <button class="tab-btn" data-tab="messages">💬 ЛС</button>
            <button class="tab-btn" data-tab="chats">👥 Чаты</button>
            <button class="tab-btn" data-tab="admin" id="admin-tab" style="display:none;">⚙️ Админ</button>
        </nav>
        <main id="content" class="content"><div class="loading"><div class="spinner"></div><p>Загрузка...</p></div></main>
        <div id="notifications-panel" class="notifications-panel">
            <div class="notif-header"><span>🔔 Уведомления</span><button id="notif-close" style="background:none;border:none;font-size:20px;cursor:pointer;">✕</button></div>
            <div id="notif-list"></div>
        </div>
    </div>
    <div id="auth-modal" class="modal">
        <div class="modal-content">
            <div class="modal-header"><h2>🔐 Вход в Nexus</h2></div>
            <div class="modal-body">
                <p style="margin-bottom:12px;">Введите ваш Telegram ID:</p>
                <input type="number" id="telegram-id-input" placeholder="Ваш ID" class="modal-input">
                <input type="text" id="username-input" placeholder="Ваш ник (необязательно)" class="modal-input">
                <button onclick="login()" class="modal-btn">Войти</button>
                <p style="font-size:12px;color:var(--text-secondary);margin-top:16px;">
                    Как узнать ID? Напишите <a href="https://t.me/userinfobot" target="_blank" style="color:var(--primary);">@userinfobot</a>
                </p>
                <p style="font-size:12px;color:var(--text-secondary);margin-top:8px;">
                    💎 Премиум (50 звёзд/мес) — цветной ник, рамка профиля. Оформить у <a href="https://t.me/SuraiWW" target="_blank" style="color:var(--primary);">@SuraiWW</a>
                </p>
            </div>
        </div>
    </div>
    <div id="message-modal" class="modal hidden">
        <div class="modal-content" style="max-width:500px;">
            <div class="modal-header"><h2>💬 Личные сообщения</h2><button onclick="closeMessages()" style="background:none;border:none;font-size:20px;cursor:pointer;">✕</button></div>
            <div id="message-list" style="max-height:400px;overflow-y:auto;margin-bottom:12px;display:flex;flex-direction:column;"></div>
            <div style="display:flex;gap:8px;">
                <input type="text" id="message-input" placeholder="Написать..." style="flex:1;padding:12px 18px;border-radius:30px;border:1px solid var(--border);font-size:15px;outline:none;">
                <button onclick="sendMessage()" style="padding:12px 24px;background:var(--gradient);color:white;border:none;border-radius:30px;font-weight:600;cursor:pointer;">➤</button>
            </div>
        </div>
    </div>
    <div id="repost-modal" class="modal hidden">
        <div class="modal-content">
            <div class="modal-header"><h2>📢 Репост</h2><button onclick="closeRepost()" style="background:none;border:none;font-size:20px;cursor:pointer;">✕</button></div>
            <p style="margin-bottom:16px;">Вы уверены, что хотите репостнуть этот пост?</p>
            <button onclick="confirmRepost()" class="modal-btn">Да, репостнуть</button>
        </div>
    </div>
    <div id="chat-modal" class="modal hidden">
        <div class="modal-content" style="max-width:500px;">
            <div class="modal-header"><h2>👥 Групповой чат</h2><button onclick="closeChat()" style="background:none;border:none;font-size:20px;cursor:pointer;">✕</button></div>
            <div id="chat-messages" style="max-height:400px;overflow-y:auto;margin-bottom:12px;display:flex;flex-direction:column;"></div>
            <div style="display:flex;gap:8px;">
                <input type="text" id="chat-input" placeholder="Написать в чат..." style="flex:1;padding:12px 18px;border-radius:30px;border:1px solid var(--border);font-size:15px;outline:none;">
                <button onclick="sendChatMessage()" style="padding:12px 24px;background:var(--gradient);color:white;border:none;border-radius:30px;font-weight:600;cursor:pointer;">➤</button>
            </div>
        </div>
    </div>
    <script>
        // ===================== ГЛОБАЛЬНЫЕ =====================
        let currentUser = null;
        let currentTelegramId = null;
        let currentPage = 1;
        let currentSearch = '';
        let swipeProfiles = [];
        let swipeIndex = 0;
        let currentRepostPostId = null;
        let currentChatUserId = null;
        let currentChatId = null;
        let chatInterval = null;
        let privateChatInterval = null;

        // ===================== ИНИЦИАЛИЗАЦИЯ =====================
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
            document.getElementById('search-btn').addEventListener('click', function() {
                currentSearch = document.getElementById('search-input').value.trim();
                currentPage = 1;
                loadFeed(currentTelegramId, currentSearch);
            });
            document.getElementById('search-input').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') document.getElementById('search-btn').click();
            });
            document.getElementById('notif-btn').addEventListener('click', function() {
                document.getElementById('notifications-panel').classList.toggle('open');
                loadNotifications();
            });
            document.getElementById('notif-close').addEventListener('click', function() {
                document.getElementById('notifications-panel').classList.remove('open');
            });
        });

        // ===================== АВТОРИЗАЦИЯ =====================
        async function login() {
            const tgId = parseInt(document.getElementById('telegram-id-input').value);
            const username = document.getElementById('username-input').value.trim();
            if (!tgId || isNaN(tgId)) { alert('Введите корректный Telegram ID'); return; }
            try {
                const resp = await fetch('/api/auth', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: new URLSearchParams({ telegram_id: tgId, username: username || '' })
                });
                const data = await resp.json();
                if (resp.ok) {
                    currentUser = data;
                    currentTelegramId = tgId;
                    localStorage.setItem('telegram_id', tgId);
                    document.getElementById('auth-modal').classList.add('hidden');
                    document.getElementById('user-name').textContent = data.first_name || 'Игрок';
                    document.getElementById('user-avatar').textContent = (data.first_name || 'И')[0];
                    if (data.is_admin) document.getElementById('admin-tab').style.display = 'inline-block';
                    initApp(tgId);
                    showNotification('✅ Добро пожаловать в MLBB Nexus!');
                } else {
                    alert('❌ ' + (data.detail || 'Ошибка входа'));
                }
            } catch(e) { alert('❌ Ошибка соединения'); }
        }

        function showNotification(text) {
            const div = document.createElement('div');
            div.className = 'notification';
            div.textContent = text;
            document.body.appendChild(div);
            setTimeout(() => div.remove(), 3000);
        }

        // ===================== УВЕДОМЛЕНИЯ =====================
        async function loadNotifications() {
            if (!currentTelegramId) return;
            try {
                const resp = await fetch(`/api/notifications?telegram_id=${currentTelegramId}`);
                const notifs = await resp.json();
                const list = document.getElementById('notif-list');
                const count = document.getElementById('notif-count');
                const unread = notifs.filter(n => !n.is_read).length;
                count.textContent = unread;
                if (notifs.length === 0) {
                    list.innerHTML = '<p style="color:var(--text-secondary);padding:12px 0;">Нет уведомлений</p>';
                } else {
                    list.innerHTML = notifs.map(n => `
                        <div class="notif-item">
                            <div>${n.message}</div>
                            <div class="notif-time">${new Date(n.created_at).toLocaleString('ru-RU')}</div>
                        </div>
                    `).join('');
                }
            } catch(e) {}
        }

        // ===================== ПЕРЕКЛЮЧЕНИЕ ВКЛАДОК =====================
        function switchTab(tab) {
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.tab === tab);
            });
            switch(tab) {
                case 'feed': loadFeed(currentTelegramId, currentSearch); break;
                case 'swipe': loadSwipe(); break;
                case 'profile': loadProfile(currentTelegramId); break;
                case 'newpost': showNewPost(); break;
                case 'messages': loadDialogs(); break;
                case 'chats': loadChats(); break;
                case 'admin': loadAdminPanel(); break;
            }
        }

        // ===================== ЛЕНТА =====================
        async function loadFeed(telegramId, search = '') {
            const content = document.getElementById('content');
            content.innerHTML = `<div class="loading"><div class="spinner"></div><p>Загрузка...</p></div>`;
            try {
                let url = `/api/posts?limit=20&offset=${(currentPage-1)*20}`;
                if (search) url += `&search=${encodeURIComponent(search)}`;
                if (telegramId) url += `&telegram_id=${telegramId}`;
                const resp = await fetch(url);
                const posts = await resp.json();
                if (posts.length === 0 && currentPage === 1) {
                    content.innerHTML = `<div class="empty-state"><span class="emoji">📭</span><h3>Нет постов</h3><p>Создайте первый пост!</p></div>`;
                    return;
                }
                content.innerHTML = posts.map(p => renderPost(p)).join('');
                attachPostHandlers();
                if (posts.length === 20) {
                    const loadMore = document.createElement('button');
                    loadMore.textContent = 'Загрузить ещё';
                    loadMore.className = 'btn-submit';
                    loadMore.style.marginTop = '16px';
                    loadMore.onclick = () => { currentPage++; loadFeed(telegramId, search); };
                    content.appendChild(loadMore);
                }
            } catch(e) {
                content.innerHTML = `<div class="empty-state"><span class="emoji">⚠️</span><h3>Ошибка загрузки</h3></div>`;
            }
        }

        function renderPost(post) {
            const isOwner = post.author_telegram_id === currentTelegramId || currentUser?.is_admin;
            const photo = post.photo_url ? `<img src="${post.photo_url}" class="post-photo" loading="lazy">` : '';
            const tags = post.tags ? post.tags.split(',').map(t => `<span class="tag">#${t.trim()}</span>`).join('') : '';
            const likeClass = post.user_liked ? 'liked' : '';
            const authorName = post.author_name;
            const isPrem = post.author_is_premium || false;
            const nameHtml = isPrem ? `<span class="premium-name">${authorName}</span>` : authorName;
            const frameClass = isPrem ? 'premium-frame' : '';
            let pollHtml = '';
            if (post.has_poll && post.poll) {
                const poll = post.poll;
                const options = poll.options;
                const totalVotes = poll.total_votes || 0;
                pollHtml = `
                    <div class="poll-options">
                        <div style="font-weight:600;margin-bottom:4px;">${poll.question}</div>
                        ${options.map((opt, idx) => {
                            const voted = poll.user_vote === idx;
                            const count = totalVotes > 0 ? Math.round((opt.votes || 0) / totalVotes * 100) : 0;
                            return `<div class="poll-option ${voted ? 'voted' : ''}" onclick="votePoll(${post.id}, ${idx})">
                                ${opt.text} (${opt.votes || 0} голосов)
                                <div class="poll-bar" style="width:${count}%;"></div>
                            </div>`;
                        }).join('')}
                    </div>
                `;
            }
            return `
                <div class="post-card ${frameClass}" data-post-id="${post.id}">
                    <div class="post-header">
                        <span class="post-author">${nameHtml}</span>
                        <span class="post-time">${new Date(post.created_at).toLocaleString('ru-RU')}</span>
                        ${isOwner ? `<button class="post-delete" data-post-id="${post.id}">🗑️</button>` : ''}
                        <button class="report-btn" data-post-id="${post.id}">⚠️</button>
                        <button class="msg-btn" data-user-id="${post.author_telegram_id}">💬</button>
                    </div>
                    <div class="post-title">${post.title}</div>
                    <div class="post-content">${post.content}</div>
                    ${photo}
                    <div class="post-tags">${tags}</div>
                    ${pollHtml}
                    <div class="post-actions">
                        <button class="action-btn like-btn ${likeClass}" data-post-id="${post.id}">
                            <span class="heart">❤️</span> <span>${post.likes_count}</span>
                        </button>
                        <button class="action-btn comment-btn" data-post-id="${post.id}">
                            💬 <span>${post.comments_count}</span>
                        </button>
                        <button class="action-btn repost-btn" data-post-id="${post.id}">
                            🔄 <span>${post.reposts_count || 0}</span>
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

        function attachPostHandlers() {
            document.querySelectorAll('.like-btn').forEach(b => b.addEventListener('click', handleLike));
            document.querySelectorAll('.comment-btn').forEach(b => b.addEventListener('click', toggleComments));
            document.querySelectorAll('.comment-submit').forEach(b => b.addEventListener('click', submitComment));
            document.querySelectorAll('.post-delete').forEach(b => b.addEventListener('click', deletePost));
            document.querySelectorAll('.report-btn').forEach(b => b.addEventListener('click', reportPost));
            document.querySelectorAll('.repost-btn').forEach(b => b.addEventListener('click', openRepost));
            document.querySelectorAll('.msg-btn').forEach(b => b.addEventListener('click', openChat));
        }

        // ===================== ЛАЙКИ =====================
        async function handleLike(e) {
            const btn = e.currentTarget;
            const postId = btn.dataset.postId;
            const span = btn.querySelector('span');
            try {
                const resp = await fetch('/api/like', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: new URLSearchParams({ post_id: postId, telegram_id: currentTelegramId })
                });
                const data = await resp.json();
                if (data.liked) {
                    btn.classList.add('liked');
                    span.textContent = parseInt(span.textContent) + 1;
                } else {
                    btn.classList.remove('liked');
                    span.textContent = parseInt(span.textContent) - 1;
                }
            } catch(e) {}
        }

        // ===================== КОММЕНТАРИИ =====================
        function toggleComments(e) {
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
                const resp = await fetch(`/api/posts/${postId}/comments`);
                const comments = await resp.json();
                const list = document.querySelector(`.comments-section[data-post-id="${postId}"] .comments-list`);
                if (comments.length === 0) {
                    list.innerHTML = '<p style="color:var(--text-secondary);font-size:13px;padding:8px 0;">Нет комментариев</p>';
                    return;
                }
                list.innerHTML = comments.map(c => `
                    <div class="comment">
                        <span class="comment-author">${c.author_name}</span>
                        <span class="comment-text">${c.content}</span>
                        <span class="comment-time">${new Date(c.created_at).toLocaleString('ru-RU')}</span>
                        ${(c.author_telegram_id === currentTelegramId || currentUser?.is_admin) ? `<button class="comment-delete" data-comment-id="${c.id}">🗑️</button>` : ''}
                    </div>
                `).join('');
                list.querySelectorAll('.comment-delete').forEach(b => b.addEventListener('click', deleteComment));
            } catch(e) {}
        }

        async function submitComment(e) {
            const btn = e.currentTarget;
            const postId = btn.dataset.postId;
            const input = document.querySelector(`.comment-input-field[data-post-id="${postId}"]`);
            const content = input.value.trim();
            if (!content) return;
            try {
                const resp = await fetch('/api/comments', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: new URLSearchParams({ post_id: postId, telegram_id: currentTelegramId, content })
                });
                if (resp.ok) {
                    input.value = '';
                    await loadComments(postId);
                    const count = document.querySelector(`.comment-btn[data-post-id="${postId}"] span`);
                    count.textContent = parseInt(count.textContent) + 1;
                    showNotification('✅ Комментарий добавлен');
                }
            } catch(e) {}
        }

        async function deleteComment(e) {
            const btn = e.currentTarget;
            const commentId = btn.dataset.commentId;
            if (!confirm('Удалить комментарий?')) return;
            try {
                await fetch(`/api/comments/${commentId}`, {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: new URLSearchParams({ telegram_id: currentTelegramId })
                });
                btn.closest('.comment').remove();
                showNotification('✅ Комментарий удалён');
            } catch(e) {}
        }

        // ===================== УДАЛЕНИЕ ПОСТА =====================
        async function deletePost(e) {
            const btn = e.currentTarget;
            const postId = btn.dataset.postId;
            if (!confirm('Удалить пост?')) return;
            try {
                await fetch(`/api/posts/${postId}`, {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: new URLSearchParams({ telegram_id: currentTelegramId })
                });
                btn.closest('.post-card').remove();
                showNotification('✅ Пост удалён');
            } catch(e) {}
        }

        // ===================== ЖАЛОБЫ =====================
        async function reportPost(e) {
            const btn = e.currentTarget;
            const postId = btn.dataset.postId;
            const reason = prompt('Причина жалобы:');
            if (!reason) return;
            try {
                const resp = await fetch('/api/report', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: new URLSearchParams({ post_id: postId, telegram_id: currentTelegramId, reason })
                });
                if (resp.ok) showNotification('✅ Жалоба отправлена');
            } catch(e) {}
        }

        // ===================== ОПРОСЫ =====================
        async function votePoll(postId, optionIndex) {
            try {
                const resp = await fetch('/api/poll/vote', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: new URLSearchParams({ poll_id: postId, telegram_id: currentTelegramId, option_index: optionIndex })
                });
                if (resp.ok) {
                    showNotification('🗳️ Голос учтён');
                    loadFeed(currentTelegramId, currentSearch);
                }
            } catch(e) {}
        }

        // ===================== РЕПОСТЫ =====================
        function openRepost(e) {
            currentRepostPostId = e.currentTarget.dataset.postId;
            document.getElementById('repost-modal').classList.remove('hidden');
        }
        function closeRepost() {
            document.getElementById('repost-modal').classList.add('hidden');
        }
        async function confirmRepost() {
            if (!currentRepostPostId) return;
            try {
                const resp = await fetch('/api/repost', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: new URLSearchParams({ post_id: currentRepostPostId, telegram_id: currentTelegramId })
                });
                if (resp.ok) {
                    showNotification('🔄 Репост сделан!');
                    closeRepost();
                    loadFeed(currentTelegramId, currentSearch);
                }
            } catch(e) {}
        }

        // ===================== ЛИЧНЫЕ СООБЩЕНИЯ =====================
        function openChat(e) {
            const userId = e.currentTarget.dataset.userId;
            currentChatUserId = userId;
            document.getElementById('message-modal').classList.remove('hidden');
            loadMessagesChat(userId);
            if (privateChatInterval) clearInterval(privateChatInterval);
            privateChatInterval = setInterval(() => loadMessagesChat(userId), 5000);
        }
        function closeMessages() {
            document.getElementById('message-modal').classList.add('hidden');
            if (privateChatInterval) clearInterval(privateChatInterval);
        }
        async function loadMessagesChat(userId) {
            try {
                const resp = await fetch(`/api/messages?telegram_id=${currentTelegramId}&with_user=${userId}`);
                const msgs = await resp.json();
                const list = document.getElementById('message-list');
                list.innerHTML = msgs.map(m => `
                    <div class="message-item ${m.sender_telegram_id === currentTelegramId ? 'sent' : 'received'}">
                        <div>${m.content}</div>
                        <div class="message-time">${new Date(m.created_at).toLocaleString('ru-RU')}</div>
                    </div>
                `).join('');
                list.scrollTop = list.scrollHeight;
            } catch(e) {}
        }
        async function sendMessage() {
            const input = document.getElementById('message-input');
            const content = input.value.trim();
            if (!content || !currentChatUserId) return;
            try {
                const resp = await fetch('/api/messages', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: new URLSearchParams({ receiver_id: currentChatUserId, telegram_id: currentTelegramId, content })
                });
                if (resp.ok) {
                    input.value = '';
                    loadMessagesChat(currentChatUserId);
                }
            } catch(e) {}
        }
        async function loadDialogs() {
            const content = document.getElementById('content');
            content.innerHTML = `<div class="loading"><div class="spinner"></div><p>Загрузка диалогов...</p></div>`;
            try {
                const resp = await fetch(`/api/messages/dialogs?telegram_id=${currentTelegramId}`);
                const dialogs = await resp.json();
                if (dialogs.length === 0) {
                    content.innerHTML = `<div class="empty-state"><span class="emoji">💬</span><h3>Нет диалогов</h3></div>`;
                    return;
                }
                content.innerHTML = dialogs.map(d => `
                    <div class="dialog-card" onclick="openChatFromDialog(${d.user_id})">
                        <div class="dialog-name">${d.name}</div>
                        <div class="dialog-last">${d.last_message || 'Нет сообщений'}</div>
                    </div>
                `).join('');
            } catch(e) {}
        }
        function openChatFromDialog(userId) {
            currentChatUserId = userId;
            document.getElementById('message-modal').classList.remove('hidden');
            loadMessagesChat(userId);
            if (privateChatInterval) clearInterval(privateChatInterval);
            privateChatInterval = setInterval(() => loadMessagesChat(userId), 5000);
        }

        // ===================== ГРУППОВЫЕ ЧАТЫ =====================
        async function loadChats() {
            const content = document.getElementById('content');
            content.innerHTML = `<div class="loading"><div class="spinner"></div><p>Загрузка чатов...</p></div>`;
            try {
                const resp = await fetch(`/api/chats?telegram_id=${currentTelegramId}`);
                const chats = await resp.json();
                if (chats.length === 0) {
                    content.innerHTML = `
                        <div class="empty-state"><span class="emoji">👥</span><h3>Нет чатов</h3>
                        <p style="margin-top:12px;"><button onclick="showCreateChat()" class="btn-submit" style="width:auto;padding:8px 20px;">Создать чат</button></p></div>`;
                    return;
                }
                content.innerHTML = `
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
                        <h3>Ваши чаты</h3>
                        <button onclick="showCreateChat()" class="btn-submit" style="width:auto;padding:8px 20px;">+ Создать</button>
                    </div>
                    ${chats.map(c => `
                        <div class="chat-card" onclick="openChatRoom(${c.id})">
                            <div class="dialog-name">${c.name}</div>
                            <div class="dialog-last">${c.description || ''} (${c.member_count} участников)</div>
                        </div>
                    `).join('')}
                `;
            } catch(e) {}
        }

        function showCreateChat() {
            const name = prompt('Название чата:');
            if (!name) return;
            const description = prompt('Описание (необязательно):');
            const isPrivate = confirm('Сделать приватным?');
            createChat(name, description, isPrivate);
        }

        async function createChat(name, description, isPrivate) {
            try {
                const resp = await fetch('/api/chats', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: new URLSearchParams({ telegram_id: currentTelegramId, name, description: description || '', is_private: isPrivate })
                });
                if (resp.ok) {
                    showNotification('✅ Чат создан!');
                    loadChats();
                }
            } catch(e) {}
        }

        async function openChatRoom(chatId) {
            currentChatId = chatId;
            document.getElementById('chat-modal').classList.remove('hidden');
            loadChatMessages(chatId);
            if (chatInterval) clearInterval(chatInterval);
            chatInterval = setInterval(() => loadChatMessages(chatId), 5000);
            try {
                const resp = await fetch('/api/chats/join', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: new URLSearchParams({ chat_id: chatId, telegram_id: currentTelegramId })
                });
                const data = await resp.json();
                if (data.status === 'joined') showNotification('✅ Вы вступили в чат');
            } catch(e) {}
        }

        function closeChat() {
            document.getElementById('chat-modal').classList.add('hidden');
            if (chatInterval) clearInterval(chatInterval);
        }

        async function loadChatMessages(chatId) {
            try {
                const resp = await fetch(`/api/chats/${chatId}/messages`);
                const msgs = await resp.json();
                const list = document.getElementById('chat-messages');
                list.innerHTML = msgs.map(m => `
                    <div class="message-item ${m.user_id === currentUser?.id ? 'sent' : 'received'}">
                        <div><strong>${m.user_name}</strong> ${m.content}</div>
                        <div class="message-time">${new Date(m.created_at).toLocaleString('ru-RU')}</div>
                    </div>
                `).join('');
                list.scrollTop = list.scrollHeight;
            } catch(e) {}
        }

        async function sendChatMessage() {
            const input = document.getElementById('chat-input');
            const content = input.value.trim();
            if (!content || !currentChatId) return;
            try {
                const resp = await fetch(`/api/chats/${currentChatId}/messages`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: new URLSearchParams({ telegram_id: currentTelegramId, content })
                });
                if (resp.ok) {
                    input.value = '';
                    loadChatMessages(currentChatId);
                }
            } catch(e) {}
        }

        // ===================== СВАЙП =====================
        async function loadSwipe() {
            const content = document.getElementById('content');
            content.innerHTML = `<div class="loading"><div class="spinner"></div><p>Загрузка анкет...</p></div>`;
            try {
                const resp = await fetch(`/api/swipe?telegram_id=${currentTelegramId}`);
                const data = await resp.json();
                swipeProfiles = data;
                swipeIndex = 0;
                if (swipeProfiles.length === 0) {
                    content.innerHTML = `<div class="empty-state"><span class="emoji">💞</span><h3>Нет анкет для свайпа</h3></div>`;
                    return;
                }
                renderSwipeCard();
            } catch(e) {}
        }
        function renderSwipeCard() {
            const content = document.getElementById('content');
            if (swipeIndex >= swipeProfiles.length) {
                content.innerHTML = `<div class="empty-state"><span class="emoji">🎉</span><h3>Все анкеты просмотрены</h3></div>`;
                return;
            }
            const p = swipeProfiles[swipeIndex];
            const isPrem = p.is_premium || false;
            const nameHtml = isPrem ? `<span class="premium-name">${p.nickname_mlbb}</span>` : p.nickname_mlbb;
            const frameClass = isPrem ? 'premium-frame' : '';
            content.innerHTML = `
                <div class="swipe-container">
                    <div class="swipe-card ${frameClass}">
                        ${p.photo_url ? `<img src="${p.photo_url}" class="profile-photo">` : '<div class="profile-photo" style="background:#E5E7EB;display:flex;align-items:center;justify-content:center;font-size:60px;">👤</div>'}
                        <div class="profile-name">${nameHtml}</div>
                        <div class="profile-details">${p.role} • ${p.rank}</div>
                        <div class="profile-details">${p.country || ''} ${p.age ? '• '+p.age : ''}</div>
                        <div class="profile-details">${p.description || ''}</div>
                        <div class="swipe-buttons">
                            <button class="swipe-btn dislike" onclick="swipeAction(false)">✕</button>
                            <button class="swipe-btn like" onclick="swipeAction(true)">❤️</button>
                        </div>
                    </div>
                </div>
            `;
        }
        async function swipeAction(liked) {
            const p = swipeProfiles[swipeIndex];
            if (!p) return;
            try {
                await fetch('/api/swipe/action', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: new URLSearchParams({ target_telegram_id: p.telegram_id, liked: liked, telegram_id: currentTelegramId })
                });
                if (liked) showNotification('❤️ Вы лайкнули!');
                swipeIndex++;
                renderSwipeCard();
            } catch(e) {}
        }

        // ===================== ПРОФИЛЬ =====================
        async function loadProfile(telegramId) {
            const content = document.getElementById('content');
            content.innerHTML = `<div class="loading"><div class="spinner"></div><p>Загрузка...</p></div>`;
            try {
                const resp = await fetch(`/api/profile/${telegramId}`);
                const profile = await resp.json();
                if (!profile) {
                    content.innerHTML = showProfileForm(null);
                    document.getElementById('profileForm').addEventListener('submit', saveProfile);
                    return;
                }
                const isPrem = profile.is_premium || false;
                const nameHtml = isPrem ? `<span class="premium-name">${profile.nickname_mlbb}</span>` : profile.nickname_mlbb;
                const frameClass = isPrem ? 'premium-frame' : '';
                const achievements = profile.achievements || [];
                const stats = profile.stats || {};
                content.innerHTML = `
                    <div class="profile-form ${frameClass}">
                        <div style="display:flex;align-items:center;gap:16px;margin-bottom:20px;">
                            ${profile.photo_url ? `<img src="${profile.photo_url}" style="width:80px;height:80px;border-radius:50%;object-fit:cover;border:3px solid white;box-shadow:0 4px 12px rgba(0,0,0,0.06);">` : '<div style="width:80px;height:80px;border-radius:50%;background:#E5E7EB;display:flex;align-items:center;justify-content:center;font-size:36px;">👤</div>'}
                            <div>
                                <div style="font-size:24px;font-weight:800;">${nameHtml}</div>
                                <div style="color:var(--text-secondary);">${profile.role} • ${profile.rank}</div>
                                <div style="font-size:13px;color:var(--text-secondary);">📊 Постов: ${stats.posts || 0}, Лайков: ${stats.likes || 0}</div>
                            </div>
                        </div>
                        <div style="margin-bottom:16px;">
                            <div style="font-weight:600;font-size:14px;">🏆 Достижения:</div>
                            ${achievements.map(a => `<span class="achievement-badge">${a.type} <span class="level">${a.level}</span></span>`).join('') || 'Нет достижений'}
                        </div>
                        ${showProfileForm(profile)}
                    </div>
                `;
                document.getElementById('profileForm').addEventListener('submit', saveProfile);
            } catch(e) {
                content.innerHTML = `<div class="empty-state"><span class="emoji">⚠️</span><h3>Ошибка загрузки</h3></div>`;
            }
        }

        function showProfileForm(profile) {
            const p = profile || {};
            return `
                <form id="profileForm">
                    <div class="form-group"><label>Ник в MLBB</label><input name="nickname_mlbb" value="${p.nickname_mlbb||''}" required></div>
                    <div class="form-group"><label>Роль</label><select name="role">${['Tank','Fighter','Assassin','Mage','Marksman','Support','Flex'].map(r => `<option ${p.role===r?'selected':''}>${r}</option>`).join('')}</select></div>
                    <div class="form-group"><label>Ранг</label><select name="rank">${['Warrior','Elite','Master','Grandmaster','Epic','Legend','Mythic','Mythical Glory'].map(r => `<option ${p.rank===r?'selected':''}>${r}</option>`).join('')}</select></div>
                    <div class="form-group"><label>Страна</label><input name="country" value="${p.country||''}"></div>
                    <div class="form-group"><label>Возраст</label><input name="age" type="number" value="${p.age||''}"></div>
                    <div class="form-group"><label>Пол</label><select name="gender">${['male','female','other'].map(g => `<option ${p.gender===g?'selected':''}>${g}</option>`).join('')}</select></div>
                    <div class="form-group"><label>Язык</label><input name="preferred_language" value="${p.preferred_language||''}"></div>
                    <div class="form-group"><label>Ищу</label><select name="looking_for">${['team','duo','squad'].map(v => `<option ${p.looking_for===v?'selected':''}>${v}</option>`).join('')}</select></div>
                    <div class="form-group"><label>Стиль игры</label><select name="play_style">${['aggressive','passive','balanced'].map(v => `<option ${p.play_style===v?'selected':''}>${v}</option>`).join('')}</select></div>
                    <div class="form-group"><label>О себе</label><textarea name="description">${p.description||''}</textarea></div>
                    <div class="form-group"><label>Ссылка на фото</label><input name="photo_url" value="${p.photo_url||''}" placeholder="https://..."></div>
                    <button type="submit" class="btn-submit">💾 Сохранить</button>
                </form>
                ${!p.is_premium ? '<p style="margin-top:16px;color:var(--text-secondary);">💎 Хотите премиум? Напишите <a href="https://t.me/SuraiWW" target="_blank" style="color:var(--primary);">@SuraiWW</a> (50 звёзд/мес)</p>' : '<p style="margin-top:16px;color:#34C759;font-weight:600;">✅ Вы премиум!</p>'}
            `;
        }

        async function saveProfile(e) {
            e.preventDefault();
            const form = e.target;
            const data = new FormData(form);
            data.append('telegram_id', currentTelegramId);
            try {
                const resp = await fetch('/api/profile', { method: 'POST', body: data });
                if (resp.ok) { showNotification('✅ Профиль сохранён!'); loadProfile(currentTelegramId); }
            } catch(e) { showNotification('❌ Ошибка сохранения'); }
        }

        // ===================== НОВЫЙ ПОСТ =====================
        function showNewPost() {
            const content = document.getElementById('content');
            content.innerHTML = `
                <div class="new-post-form">
                    <h2 style="margin-bottom:16px;">✏️ Новый пост</h2>
                    <form id="newPostForm">
                        <div class="form-group"><label>Заголовок</label><input name="title" required></div>
                        <div class="form-group"><label>Текст</label><textarea name="content" required></textarea></div>
                        <div class="form-group"><label>Теги (через запятую)</label><input name="tags" placeholder="tank, squad"></div>
                        <div class="form-group"><label>Ссылка на фото</label><input name="photo_url" placeholder="https://..."></div>
                        <div class="form-group">
                            <label><input type="checkbox" id="has-poll-checkbox" onchange="togglePollFields()"> Добавить опрос</label>
                        </div>
                        <div id="poll-fields" style="display:none;">
                            <div class="form-group"><label>Вопрос опроса</label><input name="poll_question" placeholder="Ваш вопрос"></div>
                            <div class="form-group"><label>Варианты (через запятую)</label><input name="poll_options" placeholder="Вариант 1, Вариант 2, Вариант 3"></div>
                        </div>
                        <button type="submit" class="btn-post">📤 Опубликовать</button>
                    </form>
                </div>
            `;
            document.getElementById('newPostForm').addEventListener('submit', submitPost);
        }

        function togglePollFields() {
            const checked = document.getElementById('has-poll-checkbox').checked;
            document.getElementById('poll-fields').style.display = checked ? 'block' : 'none';
        }

        async function submitPost(e) {
            e.preventDefault();
            const form = e.target;
            const data = new FormData(form);
            data.append('telegram_id', currentTelegramId);
            const hasPoll = document.getElementById('has-poll-checkbox').checked;
            data.append('has_poll', hasPoll);
            if (hasPoll) {
                const options = document.querySelector('input[name="poll_options"]').value.split(',').map(s => s.trim());
                data.append('poll_options', JSON.stringify(options));
            }
            const btn = form.querySelector('.btn-post');
            btn.textContent = '⏳ Публикация...';
            btn.disabled = true;
            try {
                const resp = await fetch('/api/posts', { method: 'POST', body: data });
                if (resp.ok) {
                    showNotification('✅ Пост опубликован!');
                    btn.textContent = '✅ Готово!';
                    setTimeout(() => { switchTab('feed'); loadFeed(currentTelegramId); }, 1000);
                }
            } catch(e) { showNotification('❌ Ошибка публикации'); btn.textContent = '📤 Опубликовать'; btn.disabled = false; }
        }

        // ===================== АДМИНКА =====================
        async function loadAdminPanel() {
            if (!currentUser?.is_admin) {
                document.getElementById('content').innerHTML = '<div class="empty-state"><span class="emoji">🚫</span><h3>Нет доступа</h3></div>';
                return;
            }
            const content = document.getElementById('content');
            content.innerHTML = `<div class="loading"><div class="spinner"></div><p>Загрузка...</p></div>`;
            try {
                const resp = await fetch('/api/admin/stats?telegram_id=' + currentTelegramId);
                const stats = await resp.json();
                const usersResp = await fetch('/api/admin/users?telegram_id=' + currentTelegramId);
                const users = await usersResp.json();
                content.innerHTML = `
                    <div class="admin-panel">
                        <h2>⚙️ Админ-панель</h2>
                        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:16px 0;">
                            <div style="background:#F8F9FE;padding:16px;border-radius:16px;text-align:center;"><strong>${stats.users}</strong><br>Пользователей</div>
                            <div style="background:#F8F9FE;padding:16px;border-radius:16px;text-align:center;"><strong>${stats.posts}</strong><br>Постов</div>
                            <div style="background:#F8F9FE;padding:16px;border-radius:16px;text-align:center;"><strong>${stats.comments}</strong><br>Комментариев</div>
                        </div>
                        <h3>Жалобы</h3>
                        <div id="reports-list"></div>
                        <h3 style="margin-top:24px;">💎 Управление премиум</h3>
                        <div style="display:flex;gap:8px;margin-bottom:8px;flex-wrap:wrap;">
                            <input id="premium-user-id" type="number" placeholder="Telegram ID" style="flex:1;padding:10px;border-radius:16px;border:1px solid var(--border);min-width:150px;">
                            <button onclick="setPremium()" class="admin-btn success" style="padding:10px 20px;">💎 Дать премиум (30 дней)</button>
                        </div>
                        <h3 style="margin-top:24px;">👥 Пользователи</h3>
                        <div style="overflow-x:auto;">
                            <table class="admin-table">
                                <tr><th>ID</th><th>Имя</th><th>Премиум</th><th>Бан</th><th>Действие</th></tr>
                                ${users.map(u => `
                                    <tr>
                                        <td>${u.telegram_id}</td>
                                        <td>${u.first_name}</td>
                                        <td>${u.is_premium ? '✅' : '❌'}</td>
                                        <td>${u.is_banned ? '🚫' : '✅'}</td>
                                        <td>
                                            <button class="admin-btn danger" onclick="banUser(${u.id})">${u.is_banned ? 'Разбанить' : 'Забанить'}</button>
                                        </td>
                                    </tr>
                                `).join('')}
                            </table>
                        </div>
                    </div>
                `;
                loadReports();
            } catch(e) {}
        }

        async function loadReports() {
            try {
                const resp = await fetch('/api/admin/reports?telegram_id=' + currentTelegramId);
                const reports = await resp.json();
                const list = document.getElementById('reports-list');
                if (reports.length === 0) { list.innerHTML = '<p>Нет жалоб</p>'; return; }
                list.innerHTML = `<table class="admin-table"><tr><th>ID</th><th>Причина</th><th>Статус</th><th>Действие</th></tr>
                    ${reports.map(r => `
                        <tr>
                            <td>${r.id}</td>
                            <td>${r.reason}</td>
                            <td>${r.is_resolved ? '✅ Решена' : '⏳ Ожидает'}</td>
                            <td>
                                ${!r.is_resolved ? `<button class="admin-btn success" onclick="resolveReport(${r.id})">✅ Решить</button>` : ''}
                                <button class="admin-btn danger" onclick="deleteReport(${r.id})">🗑️</button>
                            </td>
                        </tr>
                    `).join('')}</table>`;
            } catch(e) {}
        }

        async function resolveReport(reportId) {
            if (!confirm('Решить жалобу?')) return;
            try {
                await fetch('/api/admin/reports/'+reportId, { method: 'PUT', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: new URLSearchParams({ telegram_id: currentTelegramId }) });
                showNotification('✅ Жалоба решена');
                loadReports();
            } catch(e) {}
        }

        async function deleteReport(reportId) {
            if (!confirm('Удалить жалобу?')) return;
            try {
                await fetch('/api/admin/reports/'+reportId, { method: 'DELETE', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: new URLSearchParams({ telegram_id: currentTelegramId }) });
                showNotification('🗑️ Жалоба удалена');
                loadReports();
            } catch(e) {}
        }

        async function setPremium() {
            const userId = parseInt(document.getElementById('premium-user-id').value);
            if (!userId) { alert('Введите Telegram ID'); return; }
            try {
                const resp = await fetch('/api/admin/premium', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: new URLSearchParams({ target_id: userId, telegram_id: currentTelegramId })
                });
                if (resp.ok) {
                    showNotification('💎 Премиум выдан на 30 дней!');
                    document.getElementById('premium-user-id').value = '';
                    loadAdminPanel();
                } else {
                    const err = await resp.json();
                    showNotification('❌ ' + (err.detail || 'Ошибка'));
                }
            } catch(e) { showNotification('❌ Ошибка'); }
        }

        async function banUser(userId) {
            if (!confirm('Изменить статус бана?')) return;
            try {
                await fetch('/api/admin/ban', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: new URLSearchParams({ target_id: userId, telegram_id: currentTelegramId })
                });
                showNotification('✅ Статус обновлён');
                loadAdminPanel();
            } catch(e) {}
        }

        // ===================== ЗАПУСК =====================
        async function initApp(telegramId) {
            await loadFeed(telegramId);
            await loadNotifications();
            setInterval(loadNotifications, 30000);
        }

        document.getElementById('telegram-id-input')?.addEventListener('keypress', function(e) { if (e.key === 'Enter') login(); });
    </script>
</body>
</html>
"""

# ===================== API ЭНДПОИНТЫ =====================

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_TEMPLATE

# --- АВТОРИЗАЦИЯ ---
@app.post("/api/auth")
async def auth(telegram_id: int = Form(...), username: str = Form(None), db: Session = Depends(get_db)):
    user = get_or_create_user(telegram_id, username, "Игрок", db)
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "is_admin": user.is_admin,
        "is_premium": is_premium(user)
    }

# --- ПРОФИЛЬ ---
@app.get("/api/profile/{telegram_id}")
async def get_profile(telegram_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        return None
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    if not profile:
        return None
    posts_count = db.query(Post).filter(Post.author_id == user.id).count()
    likes_count = db.query(Like).filter(Like.user_id == user.id).count()
    comments_count = db.query(Comment).filter(Comment.author_id == user.id).count()
    reposts_count = db.query(Repost).filter(Repost.user_id == user.id).count()
    achievements = db.query(Achievement).filter(Achievement.user_id == user.id).all()
    return {
        "nickname_mlbb": profile.nickname_mlbb,
        "role": profile.role,
        "rank": profile.rank,
        "description": profile.description,
        "photo_url": profile.photo_url,
        "country": profile.country,
        "preferred_language": profile.preferred_language,
        "looking_for": profile.looking_for,
        "play_style": profile.play_style,
        "age": profile.age,
        "gender": profile.gender,
        "is_premium": is_premium(user),
        "stats": {
            "posts": posts_count,
            "likes": likes_count,
            "comments": comments_count,
            "reposts": reposts_count
        },
        "achievements": [{"type": a.type, "level": a.level} for a in achievements]
    }

@app.post("/api/profile")
async def update_profile(
    telegram_id: int = Form(...),
    nickname_mlbb: str = Form(...),
    role: str = Form(...),
    rank: str = Form(...),
    description: str = Form(None),
    photo_url: str = Form(None),
    country: str = Form(None),
    preferred_language: str = Form(None),
    looking_for: str = Form(None),
    play_style: str = Form(None),
    age: int = Form(None),
    gender: str = Form(None),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    if not profile:
        profile = Profile(user_id=user.id)
        db.add(profile)
    profile.nickname_mlbb = nickname_mlbb
    profile.role = role
    profile.rank = rank
    profile.description = description
    profile.photo_url = photo_url
    profile.country = country
    profile.preferred_language = preferred_language
    profile.looking_for = looking_for
    profile.play_style = play_style
    profile.age = age
    profile.gender = gender
    db.commit()
    check_achievements(user.id, db)
    return {"status": "ok"}

# --- ПОСТЫ ---
@app.get("/api/posts")
async def get_posts(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    telegram_id: Optional[int] = None,
    search: Optional[str] = None,
    role: Optional[str] = None,
    rank: Optional[str] = None,
    tag: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Post).filter(Post.is_archived == False)
    if telegram_id:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if user:
            query = query.filter(Post.author_id == user.id)
    if search:
        query = query.filter(
            or_(
                Post.title.ilike(f"%{search}%"),
                Post.content.ilike(f"%{search}%"),
                Post.tags.ilike(f"%{search}%")
            )
        )
    if role:
        query = query.join(User).join(Profile).filter(Profile.role.ilike(f"%{role}%"))
    if rank:
        query = query.join(User).join(Profile).filter(Profile.rank.ilike(f"%{rank}%"))
    if tag:
        query = query.filter(Post.tags.ilike(f"%{tag}%"))
    query = query.order_by(desc(Post.is_pinned), desc(Post.created_at))
    posts = query.limit(limit).offset(offset).all()
    result = []
    for p in posts:
        likes_count = db.query(Like).filter(Like.post_id == p.id).count()
        comments_count = db.query(Comment).filter(Comment.post_id == p.id).count()
        reposts_count = db.query(Repost).filter(Repost.post_id == p.id).count()
        author = db.query(User).filter(User.id == p.author_id).first()
        user_liked = False
        if telegram_id:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                user_liked = db.query(Like).filter(and_(Like.user_id == user.id, Like.post_id == p.id)).first() is not None
        poll_data = None
        if p.has_poll:
            poll = db.query(Poll).filter(Poll.post_id == p.id).first()
            if poll:
                options = json.loads(poll.options)
                votes = db.query(PollVote).filter(PollVote.poll_id == poll.id).all()
                total_votes = len(votes)
                user_vote = None
                if telegram_id:
                    user = db.query(User).filter(User.telegram_id == telegram_id).first()
                    if user:
                        uv = db.query(PollVote).filter(and_(PollVote.poll_id == poll.id, PollVote.user_id == user.id)).first()
                        if uv:
                            user_vote = uv.option_index
                opt_votes = [0] * len(options)
                for v in votes:
                    opt_votes[v.option_index] += 1
                poll_data = {
                    "question": poll.question,
                    "options": [{"text": opt, "votes": opt_votes[i]} for i, opt in enumerate(options)],
                    "total_votes": total_votes,
                    "user_vote": user_vote
                }
        result.append({
            "id": p.id,
            "author_id": p.author_id,
            "author_telegram_id": author.telegram_id if author else None,
            "author_name": f"{author.first_name} {author.last_name or ''}".strip() if author else "Unknown",
            "author_is_premium": is_premium(author) if author else False,
            "title": p.title,
            "content": p.content,
            "photo_url": p.photo_url,
            "tags": p.tags,
            "is_pinned": p.is_pinned,
            "has_poll": p.has_poll,
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat(),
            "likes_count": likes_count,
            "comments_count": comments_count,
            "reposts_count": reposts_count,
            "user_liked": user_liked,
            "poll": poll_data
        })
    return result

@app.post("/api/posts")
async def create_post(
    telegram_id: int = Form(...),
    title: str = Form(...),
    content: str = Form(...),
    tags: str = Form(None),
    photo_url: str = Form(None),
    has_poll: bool = Form(False),
    poll_question: str = Form(None),
    poll_options: str = Form(None),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user or user.is_banned:
        raise HTTPException(403, "You are banned")
    post = Post(
        author_id=user.id,
        title=title,
        content=content,
        tags=tags,
        photo_url=photo_url,
        has_poll=has_poll
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    if has_poll and poll_question and poll_options:
        try:
            options = json.loads(poll_options)
        except:
            options = [opt.strip() for opt in poll_options.split(',')]
        if not isinstance(options, list):
            options = [poll_options]
        poll = Poll(post_id=post.id, question=poll_question, options=json.dumps(options))
        db.add(poll)
        db.commit()
    check_achievements(user.id, db)
    return {"id": post.id}

@app.put("/api/posts/{post_id}")
async def edit_post(
    post_id: int,
    telegram_id: int = Form(...),
    title: str = Form(...),
    content: str = Form(...),
    tags: str = Form(None),
    photo_url: str = Form(None),
    db: Session = Depends(get_db)
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    if post.author_id != user.id and not user.is_admin:
        raise HTTPException(403, "Not allowed")
    if (datetime.datetime.utcnow() - post.created_at).total_seconds() > 300 and not user.is_admin:
        raise HTTPException(403, "Edit time expired (5 minutes)")
    post.title = title
    post.content = content
    post.tags = tags
    post.photo_url = photo_url
    post.updated_at = datetime.datetime.utcnow()
    db.commit()
    return {"status": "updated"}

@app.delete("/api/posts/{post_id}")
async def delete_post(post_id: int, telegram_id: int = Form(...), db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    if post.author_id != user.id and not user.is_admin:
        raise HTTPException(403, "Not allowed")
    db.delete(post)
    db.commit()
    return {"status": "deleted"}

# --- ЛАЙКИ ---
@app.post("/api/like")
async def toggle_like(post_id: int = Form(...), telegram_id: int = Form(...), db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    like = db.query(Like).filter(and_(Like.user_id == user.id, Like.post_id == post_id)).first()
    if like:
        db.delete(like)
        db.commit()
        return {"liked": False}
    else:
        new_like = Like(user_id=user.id, post_id=post_id)
        db.add(new_like)
        if post.author_id != user.id:
            create_notification(post.author_id, "like", f"{user.first_name} поставил лайк на ваш пост", None, db)
        check_achievements(user.id, db)
        db.commit()
        return {"liked": True}

# --- КОММЕНТАРИИ ---
@app.get("/api/posts/{post_id}/comments")
async def get_comments(post_id: int, db: Session = Depends(get_db)):
    comments = db.query(Comment).filter(Comment.post_id == post_id).order_by(Comment.created_at).all()
    result = []
    for c in comments:
        author = db.query(User).filter(User.id == c.author_id).first()
        result.append({
            "id": c.id,
            "author_name": f"{author.first_name} {author.last_name or ''}".strip() if author else "Unknown",
            "author_telegram_id": author.telegram_id if author else None,
            "content": c.content,
            "is_edited": c.is_edited,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat()
        })
    return result

@app.post("/api/comments")
async def create_comment(
    post_id: int = Form(...),
    telegram_id: int = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db)
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user or user.is_banned:
        raise HTTPException(403, "You are banned")
    comment = Comment(post_id=post_id, author_id=user.id, content=content)
    db.add(comment)
    if post.author_id != user.id:
        create_notification(post.author_id, "comment", f"{user.first_name} прокомментировал ваш пост", None, db)
    db.commit()
    db.refresh(comment)
    check_achievements(user.id, db)
    return {"id": comment.id}

@app.put("/api/comments/{comment_id}")
async def edit_comment(
    comment_id: int,
    telegram_id: int = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db)
):
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(404, "Comment not found")
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    if comment.author_id != user.id and not user.is_admin:
        raise HTTPException(403, "Not allowed")
    if (datetime.datetime.utcnow() - comment.created_at).total_seconds() > 300 and not user.is_admin:
        raise HTTPException(403, "Edit time expired (5 minutes)")
    comment.content = content
    comment.is_edited = True
    comment.updated_at = datetime.datetime.utcnow()
    db.commit()
    return {"status": "updated"}

@app.delete("/api/comments/{comment_id}")
async def delete_comment(comment_id: int, telegram_id: int = Form(...), db: Session = Depends(get_db)):
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(404, "Comment not found")
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    if comment.author_id != user.id and not user.is_admin:
        raise HTTPException(403, "Not allowed")
    db.delete(comment)
    db.commit()
    return {"status": "deleted"}

# --- РЕПОСТЫ ---
@app.post("/api/repost")
async def repost(post_id: int = Form(...), telegram_id: int = Form(...), db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user or user.is_banned:
        raise HTTPException(403, "You are banned")
    existing = db.query(Repost).filter(and_(Repost.user_id == user.id, Repost.post_id == post_id)).first()
    if existing:
        db.delete(existing)
        db.commit()
        return {"reposted": False}
    rep = Repost(user_id=user.id, post_id=post_id)
    db.add(rep)
    if post.author_id != user.id:
        create_notification(post.author_id, "repost", f"{user.first_name} репостнул ваш пост", None, db)
    db.commit()
    check_achievements(user.id, db)
    return {"reposted": True}

# --- ОПРОСЫ ---
@app.post("/api/poll/vote")
async def vote_poll(
    poll_id: int = Form(...),
    telegram_id: int = Form(...),
    option_index: int = Form(...),
    db: Session = Depends(get_db)
):
    poll = db.query(Poll).filter(Poll.id == poll_id).first()
    if not poll:
        raise HTTPException(404, "Poll not found")
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user or user.is_banned:
        raise HTTPException(403, "You are banned")
    existing = db.query(PollVote).filter(and_(PollVote.poll_id == poll_id, PollVote.user_id == user.id)).first()
    if existing:
        existing.option_index = option_index
    else:
        vote = PollVote(poll_id=poll_id, user_id=user.id, option_index=option_index)
        db.add(vote)
    db.commit()
    return {"status": "voted"}

# --- ЖАЛОБЫ ---
@app.post("/api/report")
async def report_post(
    post_id: int = Form(...),
    telegram_id: int = Form(...),
    reason: str = Form(...),
    description: str = Form(None),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404, "Post not found")
    report = Report(reporter_id=user.id, post_id=post_id, reason=reason, description=description)
    db.add(report)
    db.commit()
    return {"status": "reported"}

# --- УВЕДОМЛЕНИЯ ---
@app.get("/api/notifications")
async def get_notifications(telegram_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        return []
    notifs = db.query(Notification).filter(Notification.user_id == user.id).order_by(desc(Notification.created_at)).limit(50).all()
    result = []
    for n in notifs:
        result.append({
            "id": n.id,
            "type": n.type,
            "message": n.message,
            "link": n.link,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat()
        })
        n.is_read = True
    db.commit()
    return result

# --- ЛИЧНЫЕ СООБЩЕНИЯ ---
@app.get("/api/messages")
async def get_messages(telegram_id: int, with_user: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        return []
    other = db.query(User).filter(User.telegram_id == with_user).first()
    if not other:
        return []
    msgs = db.query(Message).filter(
        or_(
            and_(Message.sender_id == user.id, Message.receiver_id == other.id),
            and_(Message.sender_id == other.id, Message.receiver_id == user.id)
        )
    ).order_by(Message.created_at).all()
    for m in msgs:
        if m.receiver_id == user.id:
            m.is_read = True
    db.commit()
    result = []
    for m in msgs:
        sender = db.query(User).filter(User.id == m.sender_id).first()
        result.append({
            "id": m.id,
            "sender_id": m.sender_id,
            "sender_telegram_id": sender.telegram_id if sender else None,
            "content": m.content,
            "created_at": m.created_at.isoformat()
        })
    return result

@app.post("/api/messages")
async def send_message(
    receiver_id: int = Form(...),
    telegram_id: int = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user or user.is_banned:
        raise HTTPException(403, "You are banned")
    receiver = db.query(User).filter(User.telegram_id == receiver_id).first()
    if not receiver:
        raise HTTPException(404, "Receiver not found")
    msg = Message(sender_id=user.id, receiver_id=receiver.id, content=content)
    db.add(msg)
    create_notification(receiver.id, "message", f"Новое сообщение от {user.first_name}", None, db)
    db.commit()
    return {"status": "sent"}

@app.get("/api/messages/dialogs")
async def get_dialogs(telegram_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        return []
    sent = db.query(Message.receiver_id).filter(Message.sender_id == user.id).distinct().all()
    received = db.query(Message.sender_id).filter(Message.receiver_id == user.id).distinct().all()
    ids = set([r[0] for r in sent] + [r[0] for r in received])
    dialogs = []
    for uid in ids:
        other = db.query(User).filter(User.id == uid).first()
        if not other:
            continue
        last = db.query(Message).filter(
            or_(
                and_(Message.sender_id == user.id, Message.receiver_id == other.id),
                and_(Message.sender_id == other.id, Message.receiver_id == user.id)
            )
        ).order_by(desc(Message.created_at)).first()
        dialogs.append({
            "user_id": other.telegram_id,
            "name": f"{other.first_name} {other.last_name or ''}".strip(),
            "last_message": last.content if last else None,
            "last_message_time": last.created_at.isoformat() if last else None
        })
    return dialogs

# --- ГРУППОВЫЕ ЧАТЫ ---
@app.get("/api/chats")
async def get_chats(telegram_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        return []
    memberships = db.query(ChatMember).filter(ChatMember.user_id == user.id).all()
    chat_ids = [m.chat_id for m in memberships]
    chats = db.query(Chat).filter(Chat.id.in_(chat_ids)).all()
    result = []
    for c in chats:
        result.append({
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "is_private": c.is_private,
            "member_count": db.query(ChatMember).filter(ChatMember.chat_id == c.id).count()
        })
    return result

@app.post("/api/chats")
async def create_chat(
    telegram_id: int = Form(...),
    name: str = Form(...),
    description: str = Form(None),
    is_private: bool = Form(False),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user or user.is_banned:
        raise HTTPException(403, "You are banned")
    chat = Chat(name=name, description=description, is_private=is_private, created_by=user.id)
    db.add(chat)
    db.commit()
    db.refresh(chat)
    member = ChatMember(chat_id=chat.id, user_id=user.id)
    db.add(member)
    db.commit()
    return {"id": chat.id}

@app.post("/api/chats/join")
async def join_chat(
    chat_id: int = Form(...),
    telegram_id: int = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user or user.is_banned:
        raise HTTPException(403, "You are banned")
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(404, "Chat not found")
    existing = db.query(ChatMember).filter(and_(ChatMember.chat_id == chat_id, ChatMember.user_id == user.id)).first()
    if existing:
        return {"status": "already_member"}
    member = ChatMember(chat_id=chat_id, user_id=user.id)
    db.add(member)
    db.commit()
    return {"status": "joined"}

@app.get("/api/chats/{chat_id}/messages")
async def get_chat_messages(chat_id: int, limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    messages = db.query(ChatMessage).filter(ChatMessage.chat_id == chat_id).order_by(desc(ChatMessage.created_at)).limit(limit).offset(offset).all()
    result = []
    for m in messages:
        user = db.query(User).filter(User.id == m.user_id).first()
        result.append({
            "id": m.id,
            "user_id": m.user_id,
            "user_name": f"{user.first_name} {user.last_name or ''}".strip() if user else "Unknown",
            "content": m.content,
            "created_at": m.created_at.isoformat()
        })
    return result[::-1]

@app.post("/api/chats/{chat_id}/messages")
async def send_chat_message(
    chat_id: int,
    telegram_id: int = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user or user.is_banned:
        raise HTTPException(403, "You are banned")
    member = db.query(ChatMember).filter(and_(ChatMember.chat_id == chat_id, ChatMember.user_id == user.id)).first()
    if not member:
        raise HTTPException(403, "You are not a member of this chat")
    msg = ChatMessage(chat_id=chat_id, user_id=user.id, content=content)
    db.add(msg)
    db.commit()
    return {"id": msg.id}

# --- СВАЙП ---
@app.get("/api/swipe")
async def get_swipe_profiles(telegram_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        return []
    profiles = db.query(Profile).filter(Profile.is_visible_for_swipe == True).all()
    result = []
    for p in profiles:
        if p.user_id == user.id:
            continue
        target_user = db.query(User).filter(User.id == p.user_id).first()
        if not target_user:
            continue
        existing = db.query(SwipeLike).filter(and_(SwipeLike.from_user_id == user.id, SwipeLike.to_user_id == target_user.id)).first()
        if existing:
            continue
        result.append({
            "telegram_id": target_user.telegram_id,
            "nickname_mlbb": p.nickname_mlbb,
            "role": p.role,
            "rank": p.rank,
            "photo_url": p.photo_url,
            "description": p.description,
            "country": p.country,
            "age": p.age,
            "is_premium": is_premium(target_user)
        })
    return result

@app.post("/api/swipe/action")
async def swipe_action(
    target_telegram_id: int = Form(...),
    liked: bool = Form(...),
    telegram_id: int = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    target_user = db.query(User).filter(User.telegram_id == target_telegram_id).first()
    if not target_user:
        raise HTTPException(404, "Target user not found")
    existing = db.query(SwipeLike).filter(and_(SwipeLike.from_user_id == user.id, SwipeLike.to_user_id == target_user.id)).first()
    if existing:
        existing.liked = liked
    else:
        swipe = SwipeLike(from_user_id=user.id, to_user_id=target_user.id, liked=liked)
        db.add(swipe)
    db.commit()
    mutual = db.query(SwipeLike).filter(and_(SwipeLike.from_user_id == target_user.id, SwipeLike.to_user_id == user.id, SwipeLike.liked == True)).first()
    if mutual and liked:
        create_notification(target_user.id, "match", f"💞 Взаимный лайк с {user.first_name}!", None, db)
        create_notification(user.id, "match", f"💞 Взаимный лайк с {target_user.first_name}!", None, db)
    return {"status": "ok"}

# --- АДМИНКА ---
@app.get("/api/admin/stats")
async def admin_stats(telegram_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user or not user.is_admin:
        raise HTTPException(403, "Not admin")
    users = db.query(User).count()
    posts = db.query(Post).count()
    comments = db.query(Comment).count()
    return {"users": users, "posts": posts, "comments": comments}

@app.get("/api/admin/users")
async def admin_users(telegram_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user or not user.is_admin:
        raise HTTPException(403, "Not admin")
    users = db.query(User).all()
    result = []
    for u in users:
        result.append({
            "id": u.id,
            "telegram_id": u.telegram_id,
            "first_name": u.first_name,
            "is_admin": u.is_admin,
            "is_premium": is_premium(u),
            "is_banned": u.is_banned,
            "created_at": u.created_at.isoformat()
        })
    return result

@app.post("/api/admin/ban")
async def ban_user(
    target_id: int = Form(...),
    telegram_id: int = Form(...),
    db: Session = Depends(get_db)
):
    admin = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not admin or not admin.is_admin:
        raise HTTPException(403, "Not admin")
    user = db.query(User).filter(User.id == target_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    user.is_banned = not user.is_banned
    db.commit()
    return {"banned": user.is_banned}

# Эндпоинт для выдачи премиум (был пропущен)
@app.post("/api/admin/premium")
async def give_premium(
    target_id: int = Form(...),
    telegram_id: int = Form(...),
    db: Session = Depends(get_db)
):
    admin = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not admin or not admin.is_admin:
        raise HTTPException(403, "Not admin")
    user = db.query(User).filter(User.id == target_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    user.is_premium = True
    user.premium_until = datetime.datetime.utcnow() + datetime.timedelta(days=30)
    db.commit()
    create_notification(user.id, "premium", "Вам выдан премиум-статус на 30 дней! 🎉", None, db)
    return {"status": "ok"}

@app.get("/api/admin/reports")
async def admin_reports(telegram_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user or not user.is_admin:
        raise HTTPException(403, "Not admin")
    reports = db.query(Report).order_by(desc(Report.created_at)).all()
    result = []
    for r in reports:
        result.append({
            "id": r.id,
            "reporter_id": r.reporter_id,
            "post_id": r.post_id,
            "reason": r.reason,
            "description": r.description,
            "is_resolved": r.is_resolved,
            "created_at": r.created_at.isoformat()
        })
    return result

@app.put("/api/admin/reports/{report_id}")
async def resolve_report(report_id: int, telegram_id: int = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user or not user.is_admin:
        raise HTTPException(403, "Not admin")
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(404, "Report not found")
    report.is_resolved = True
    report.resolved_by = user.id
    report.resolved_at = datetime.datetime.utcnow()
    create_notification(report.reporter_id, "report_resolved", "Ваша жалоба рассмотрена", None, db)
    db.commit()
    return {"status": "resolved"}

@app.delete("/api/admin/reports/{report_id}")
async def delete_report(report_id: int, telegram_id: int = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user or not user.is_admin:
        raise HTTPException(403, "Not admin")
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(404, "Report not found")
    db.delete(report)
    db.commit()
    return {"status": "deleted"}

# ===================== ЗАПУСК =====================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
