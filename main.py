import os
import datetime
import hashlib
import json
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Request, Form, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Boolean, 
    UniqueConstraint, create_engine, func, and_, or_, desc, asc, event
)
from sqlalchemy.orm import relationship, declarative_base, sessionmaker, Session
from pydantic import BaseModel
from dotenv import load_dotenv
import uvicorn

# ===================== КОНФИГ =====================
load_dotenv()

SITE_URL = os.getenv("SITE_URL", "https://ваш-сайт.onrender.com")
OWNER_ID = int(os.getenv("OWNER_ID", 5391287151))  # Ваш Telegram ID
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey123")

# База данных (SQLite для простоты, можно заменить на PostgreSQL)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///mlbb.db")
if DATABASE_URL.startswith("sqlite"):
    DATABASE_URL_SYNC = DATABASE_URL
else:
    DATABASE_URL_SYNC = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg://", "postgresql://")

# ===================== БАЗА ДАННЫХ =====================
engine = create_engine(
    DATABASE_URL_SYNC,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL_SYNC else {}
)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# ---------------------- МОДЕЛИ ----------------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=False, default="Игрок")
    last_name = Column(String(255), nullable=True)
    is_admin = Column(Boolean, default=False)
    is_banned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    profile = relationship("Profile", back_populates="user", uselist=False)
    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="author", cascade="all, delete-orphan")
    likes = relationship("Like", back_populates="user", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="reporter", foreign_keys="Report.reporter_id")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")

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
    looking_for = Column(String(100), nullable=True)  # team, duo, squad
    play_style = Column(String(100), nullable=True)  # aggressive, passive, balanced
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
    tags = Column(String(255), nullable=True)  # коммандой через запятую
    is_pinned = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    author = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    likes = relationship("Like", back_populates="post", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="post", cascade="all, delete-orphan")

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

class Like(Base):
    __tablename__ = "likes"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    post_id = Column(Integer, ForeignKey("posts.id"))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    __table_args__ = (UniqueConstraint('user_id', 'post_id', name='unique_like'),)
    
    user = relationship("User", back_populates="likes")
    post = relationship("Post", back_populates="likes")

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
    
    reporter = relationship("User", foreign_keys=[reporter_id], back_populates="reports")
    post = relationship("Post", back_populates="reports")
    comment = relationship("Comment", back_populates="reports")
    resolver = relationship("User", foreign_keys=[resolved_by])

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(String(50), nullable=False)  # comment, like, report_resolved, mention
    message = Column(Text, nullable=False)
    link = Column(String(500), nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="notifications")

# Создаём таблицы
Base.metadata.create_all(engine)

# ===================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_or_create_user(telegram_id: int, username: str = None, first_name: str = "Игрок", db: Session = None) -> User:
    if db is None:
        db = SessionLocal()
        close_db = True
    else:
        close_db = False
    
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

# ===================== FASTAPI APP =====================
app = FastAPI(title="MLBB Team Finder", description="Найди тимейтов для Mobile Legends")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===================== СТАТИЧЕСКИЕ ШАБЛОНЫ =====================
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
            <div id="search-bar" class="search-bar">
                <input type="text" id="search-input" placeholder="🔍 Поиск по роли, рангу, тексту...">
                <button id="search-btn">Найти</button>
            </div>
        </header>
        
        <nav>
            <button class="tab-btn active" data-tab="feed">📋 Лента</button>
            <button class="tab-btn" data-tab="profile">👤 Профиль</button>
            <button class="tab-btn" data-tab="newpost">✏️ Создать пост</button>
            <button class="tab-btn" data-tab="admin" id="admin-tab" style="display:none;">⚙️ Админ</button>
        </nav>
        
        <main id="content" class="content">
            <div class="loading">
                <div class="spinner"></div>
                <p>Загрузка...</p>
            </div>
        </main>
        
        <div id="notifications-panel" class="notifications-panel">
            <div class="notif-header">
                <span>🔔 Уведомления</span>
                <button id="notif-close">✕</button>
            </div>
            <div id="notif-list"></div>
        </div>
    </div>
    
    <div id="auth-modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2>🔐 Вход</h2>
            </div>
            <div class="modal-body">
                <p>Введите ваш Telegram ID:</p>
                <input type="number" id="telegram-id-input" placeholder="Ваш ID" class="modal-input">
                <input type="text" id="username-input" placeholder="Ваш ник (необязательно)" class="modal-input">
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
    max-width: 600px;
    margin: 0 auto;
    background: #ffffff;
    min-height: 100vh;
    box-shadow: 0 0 20px rgba(0,0,0,0.05);
}
header {
    background: linear-gradient(135deg, #007aff, #5856d6);
    padding: 16px 16px 10px;
    position: sticky;
    top: 0;
    z-index: 100;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}
.header-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
}
header h1 {
    color: white;
    font-size: 22px;
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
    width: 34px;
    height: 34px;
    border-radius: 50%;
    background: rgba(255,255,255,0.25);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    color: white;
}
.search-bar {
    display: flex;
    gap: 8px;
    background: rgba(255,255,255,0.15);
    padding: 6px;
    border-radius: 12px;
}
.search-bar input {
    flex: 1;
    padding: 8px 12px;
    border: none;
    border-radius: 8px;
    background: rgba(255,255,255,0.85);
    font-size: 14px;
    outline: none;
}
.search-bar button {
    padding: 8px 18px;
    border: none;
    border-radius: 8px;
    background: white;
    color: #007aff;
    font-weight: 600;
    cursor: pointer;
}
nav {
    display: flex;
    background: #f8f9fc;
    border-bottom: 1px solid #e5e5ea;
    position: sticky;
    top: 120px;
    z-index: 99;
    overflow-x: auto;
}
.tab-btn {
    flex: 0 0 auto;
    padding: 10px 16px;
    border: none;
    background: transparent;
    font-size: 14px;
    font-weight: 500;
    color: #8e8e93;
    cursor: pointer;
    transition: all 0.3s ease;
    position: relative;
    white-space: nowrap;
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
    width: 24px;
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
    margin-bottom: 8px;
    flex-wrap: wrap;
}
.post-title {
    font-size: 17px;
    font-weight: 600;
    color: #1c1c1e;
}
.post-author {
    font-weight: 500;
    font-size: 14px;
    color: #007aff;
}
.post-time {
    color: #8e8e93;
    font-size: 12px;
    margin-left: auto;
}
.post-content {
    font-size: 15px;
    line-height: 1.5;
    margin: 8px 0 10px;
    white-space: pre-wrap;
}
.post-tags {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-bottom: 10px;
}
.tag {
    background: #e5e5ea;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 12px;
    color: #1c1c1e;
}
.post-photo {
    max-width: 100%;
    border-radius: 12px;
    margin-bottom: 12px;
    max-height: 350px;
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
.action-btn.reported {
    color: #ff9500;
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
.comment-time {
    font-size: 11px;
    color: #8e8e93;
    margin-left: 8px;
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
.comment-delete, .post-delete, .report-btn {
    background: none;
    border: none;
    color: #ff3b30;
    cursor: pointer;
    font-size: 12px;
    margin-left: auto;
    opacity: 0.6;
    padding: 2px 6px;
}
.comment-delete:hover, .post-delete:hover {
    opacity: 1;
}
.report-btn {
    color: #ff9500;
}
.report-btn:hover {
    opacity: 1;
}
.profile-form, .new-post-form, .admin-panel {
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
.form-group input, .form-group textarea, .form-group select {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid #e5e5ea;
    border-radius: 10px;
    font-size: 15px;
    background: #f8f9fc;
    transition: border-color 0.2s ease;
}
.form-group input:focus, .form-group textarea:focus, .form-group select:focus {
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
.modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.5);
    z-index: 999;
    display: flex;
    align-items: center;
    justify-content: center;
}
.modal-content {
    background: white;
    border-radius: 20px;
    padding: 30px;
    max-width: 400px;
    width: 90%;
    animation: slideUp 0.3s ease;
}
@keyframes slideUp {
    from { transform: translateY(20px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
}
.modal-header h2 {
    margin-bottom: 16px;
}
.modal-input {
    width: 100%;
    padding: 12px;
    border: 1px solid #e5e5ea;
    border-radius: 10px;
    font-size: 16px;
    margin: 8px 0;
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
.notifications-panel {
    position: fixed;
    right: 0;
    top: 0;
    width: 350px;
    max-height: 100vh;
    background: white;
    box-shadow: -2px 0 10px rgba(0,0,0,0.1);
    padding: 16px;
    overflow-y: auto;
    z-index: 200;
    transform: translateX(100%);
    transition: transform 0.3s ease;
}
.notifications-panel.open {
    transform: translateX(0);
}
.notif-header {
    display: flex;
    justify-content: space-between;
    font-weight: 600;
    padding-bottom: 12px;
    border-bottom: 1px solid #e5e5ea;
}
.notif-item {
    padding: 10px 0;
    border-bottom: 1px solid #f0f2f5;
    font-size: 14px;
}
.notif-item .notif-time {
    font-size: 11px;
    color: #8e8e93;
}
.admin-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
}
.admin-table th, .admin-table td {
    padding: 8px 12px;
    text-align: left;
    border-bottom: 1px solid #e5e5ea;
}
.admin-table th {
    background: #f8f9fc;
}
.admin-btn {
    padding: 4px 12px;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 12px;
}
.admin-btn.danger {
    background: #ff3b30;
    color: white;
}
.admin-btn.success {
    background: #34c759;
    color: white;
}
.admin-btn.primary {
    background: #007aff;
    color: white;
}
'''

JS_TEMPLATE = '''
// ===================== ГЛОБАЛЬНЫЕ =====================
let currentUser = null;
let currentTelegramId = null;
let currentPage = 1;
let currentSearch = '';

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
    
    document.getElementById('notif-close').addEventListener('click', function() {
        document.getElementById('notifications-panel').classList.remove('open');
    });
});

// ===================== АВТОРИЗАЦИЯ =====================
async function login() {
    const tgId = parseInt(document.getElementById('telegram-id-input').value);
    const username = document.getElementById('username-input').value.trim();
    
    if (!tgId || isNaN(tgId)) {
        alert('Введите корректный Telegram ID');
        return;
    }
    
    try {
        const response = await fetch('/api/auth', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({
                telegram_id: tgId,
                username: username || ''
            })
        });
        
        const data = await response.json();
        if (response.ok) {
            currentUser = data;
            currentTelegramId = tgId;
            localStorage.setItem('telegram_id', tgId);
            document.getElementById('auth-modal').classList.add('hidden');
            document.getElementById('user-name').textContent = data.first_name || 'Игрок';
            document.getElementById('user-avatar').textContent = (data.first_name || 'И')[0];
            if (data.is_admin) {
                document.getElementById('admin-tab').style.display = 'inline-block';
            }
            initApp(tgId);
            showNotification('✅ Добро пожаловать!');
        } else {
            alert('❌ ' + (data.detail || 'Ошибка входа'));
        }
    } catch (error) {
        alert('❌ Ошибка соединения');
    }
}

// ===================== УВЕДОМЛЕНИЯ =====================
function showNotification(text) {
    const div = document.createElement('div');
    div.className = 'notification';
    div.textContent = text;
    document.body.appendChild(div);
    setTimeout(() => div.remove(), 3000);
}

async function loadNotifications() {
    if (!currentTelegramId) return;
    try {
        const resp = await fetch(`/api/notifications?telegram_id=${currentTelegramId}`);
        const notifs = await resp.json();
        const list = document.getElementById('notif-list');
        if (notifs.length === 0) {
            list.innerHTML = '<p style="color:#8e8e93;padding:12px 0;">Нет уведомлений</p>';
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
        case 'profile': loadProfile(currentTelegramId); break;
        case 'newpost': showNewPost(); break;
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
            content.innerHTML = `
                <div class="empty-state">
                    <span class="emoji">📭</span>
                    <h3>Нет постов</h3>
                    <p>Создайте первый пост!</p>
                </div>
            `;
            return;
        }
        
        content.innerHTML = posts.map(p => renderPost(p)).join('');
        
        // Обработчики
        document.querySelectorAll('.like-btn').forEach(b => b.addEventListener('click', handleLike));
        document.querySelectorAll('.comment-btn').forEach(b => b.addEventListener('click', toggleComments));
        document.querySelectorAll('.comment-submit').forEach(b => b.addEventListener('click', submitComment));
        document.querySelectorAll('.post-delete').forEach(b => b.addEventListener('click', deletePost));
        document.querySelectorAll('.report-btn').forEach(b => b.addEventListener('click', reportPost));
        
        // Кнопка "Загрузить ещё"
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
    const photo = post.photo_url ? `<img src="${post.photo_url}" class="post-photo">` : '';
    const tags = post.tags ? post.tags.split(',').map(t => `<span class="tag">#${t.trim()}</span>`).join('') : '';
    const likeClass = post.user_liked ? 'liked' : '';
    
    return `
        <div class="post-card" data-post-id="${post.id}">
            <div class="post-header">
                <span class="post-author">${post.author_name}</span>
                <span class="post-time">${new Date(post.created_at).toLocaleString('ru-RU')}</span>
                ${isOwner ? `<button class="post-delete" data-post-id="${post.id}">🗑️</button>` : ''}
                <button class="report-btn" data-post-id="${post.id}">⚠️</button>
            </div>
            <div class="post-title">${post.title}</div>
            <div class="post-content">${post.content}</div>
            ${photo}
            <div class="post-tags">${tags}</div>
            <div class="post-actions">
                <button class="action-btn like-btn ${likeClass}" data-post-id="${post.id}">
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
            list.innerHTML = '<p style="color:#8e8e93;font-size:13px;padding:8px 0;">Нет комментариев</p>';
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

// ===================== РЕПОРТ =====================
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

// ===================== ПРОФИЛЬ =====================
async function loadProfile(telegramId) {
    const content = document.getElementById('content');
    content.innerHTML = `<div class="loading"><div class="spinner"></div><p>Загрузка...</p></div>`;
    
    try {
        const resp = await fetch(`/api/profile/${telegramId}`);
        const profile = await resp.json();
        
        if (!profile) {
            content.innerHTML = `
                <div class="profile-form">
                    <h2>👤 Создать профиль</h2>
                    <form id="profileForm">
                        <div class="form-group"><label>Ник в MLBB</label><input name="nickname_mlbb" required></div>
                        <div class="form-group"><label>Роль</label><select name="role">
                            <option>Tank</option><option>Fighter</option><option>Assassin</option>
                            <option>Mage</option><option>Marksman</option><option>Support</option><option>Flex</option>
                        </select></div>
                        <div class="form-group"><label>Ранг</label><select name="rank">
                            <option>Warrior</option><option>Elite</option><option>Master</option>
                            <option>Grandmaster</option><option>Epic</option><option>Legend</option>
                            <option>Mythic</option><option>Mythical Glory</option>
                        </select></div>
                        <div class="form-group"><label>Страна</label><input name="country"></div>
                        <div class="form-group"><label>Язык</label><input name="preferred_language"></div>
                        <div class="form-group"><label>Ищу</label><select name="looking_for">
                            <option>team</option><option>duo</option><option>squad</option>
                        </select></div>
                        <div class="form-group"><label>Стиль игры</label><select name="play_style">
                            <option>aggressive</option><option>passive</option><option>balanced</option>
                        </select></div>
                        <div class="form-group"><label>О себе</label><textarea name="description"></textarea></div>
                        <div class="form-group"><label>Ссылка на фото</label><input name="photo_url" placeholder="https://..."></div>
                        <button type="submit" class="btn-submit">💾 Сохранить</button>
                    </form>
                </div>
            `;
            document.getElementById('profileForm').addEventListener('submit', saveProfile);
            return;
        }
        
        content.innerHTML = `
            <div class="profile-form">
                <h2>👤 Профиль</h2>
                <form id="profileForm">
                    <div class="form-group"><label>Ник в MLBB</label><input name="nickname_mlbb" value="${profile.nickname_mlbb||''}" required></div>
                    <div class="form-group"><label>Роль</label><select name="role">
                        ${['Tank','Fighter','Assassin','Mage','Marksman','Support','Flex'].map(r => `<option ${profile.role===r?'selected':''}>${r}</option>`).join('')}
                    </select></div>
                    <div class="form-group"><label>Ранг</label><select name="rank">
                        ${['Warrior','Elite','Master','Grandmaster','Epic','Legend','Mythic','Mythical Glory'].map(r => `<option ${profile.rank===r?'selected':''}>${r}</option>`).join('')}
                    </select></div>
                    <div class="form-group"><label>Страна</label><input name="country" value="${profile.country||''}"></div>
                    <div class="form-group"><label>Язык</label><input name="preferred_language" value="${profile.preferred_language||''}"></div>
                    <div class="form-group"><label>Ищу</label><select name="looking_for">
                        ${['team','duo','squad'].map(v => `<option ${profile.looking_for===v?'selected':''}>${v}</option>`).join('')}
                    </select></div>
                    <div class="form-group"><label>Стиль игры</label><select name="play_style">
                        ${['aggressive','passive','balanced'].map(v => `<option ${profile.play_style===v?'selected':''}>${v}</option>`).join('')}
                    </select></div>
                    <div class="form-group"><label>О себе</label><textarea name="description">${profile.description||''}</textarea></div>
                    <div class="form-group"><label>Ссылка на фото</label><input name="photo_url" value="${profile.photo_url||''}"></div>
                    <button type="submit" class="btn-submit">💾 Обновить</button>
                </form>
            </div>
        `;
        document.getElementById('profileForm').addEventListener('submit', saveProfile);
    } catch(e) {
        content.innerHTML = `<div class="empty-state"><span class="emoji">⚠️</span><h3>Ошибка загрузки</h3></div>`;
    }
}

async function saveProfile(e) {
    e.preventDefault();
    const form = e.target;
    const data = new FormData(form);
    data.append('telegram_id', currentTelegramId);
    try {
        const resp = await fetch('/api/profile', { method: 'POST', body: data });
        if (resp.ok) {
            showNotification('✅ Профиль сохранён!');
            loadProfile(currentTelegramId);
        }
    } catch(e) { showNotification('❌ Ошибка сохранения'); }
}

// ===================== НОВЫЙ ПОСТ =====================
function showNewPost() {
    const content = document.getElementById('content');
    content.innerHTML = `
        <div class="new-post-form">
            <h2>✏️ Новый пост</h2>
            <form id="newPostForm">
                <div class="form-group"><label>Заголовок</label><input name="title" required></div>
                <div class="form-group"><label>Текст</label><textarea name="content" required></textarea></div>
                <div class="form-group"><label>Теги (через запятую)</label><input name="tags" placeholder="tank, squad"></div>
                <div class="form-group"><label>Ссылка на фото</label><input name="photo_url" placeholder="https://..."></div>
                <button type="submit" class="btn-post">📤 Опубликовать</button>
            </form>
        </div>
    `;
    document.getElementById('newPostForm').addEventListener('submit', submitPost);
}

async function submitPost(e) {
    e.preventDefault();
    const form = e.target;
    const data = new FormData(form);
    data.append('telegram_id', currentTelegramId);
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
        content.innerHTML = `
            <div class="admin-panel">
                <h2>⚙️ Админ-панель</h2>
                <div style="display:grid; grid-template-columns: repeat(3,1fr); gap:16px; margin:16px 0;">
                    <div style="background:#f8f9fc;padding:16px;border-radius:12px;"><strong>${stats.users}</strong><br>Пользователей</div>
                    <div style="background:#f8f9fc;padding:16px;border-radius:12px;"><strong>${stats.posts}</strong><br>Постов</div>
                    <div style="background:#f8f9fc;padding:16px;border-radius:12px;"><strong>${stats.comments}</strong><br>Комментариев</div>
                </div>
                <h3>Жалобы</h3>
                <div id="reports-list"></div>
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
        if (reports.length === 0) {
            list.innerHTML = '<p>Нет жалоб</p>';
            return;
        }
        list.innerHTML = `
            <table class="admin-table">
                <tr><th>ID</th><th>Причина</th><th>Статус</th><th>Действие</th></tr>
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
                `).join('')}
            </table>
        `;
    } catch(e) {}
}

async function resolveReport(reportId) {
    if (!confirm('Решить жалобу?')) return;
    try {
        await fetch('/api/admin/reports/'+reportId, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({ telegram_id: currentTelegramId })
        });
        showNotification('✅ Жалоба решена');
        loadReports();
    } catch(e) {}
}

async function deleteReport(reportId) {
    if (!confirm('Удалить жалобу?')) return;
    try {
        await fetch('/api/admin/reports/'+reportId, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({ telegram_id: currentTelegramId })
        });
        showNotification('🗑️ Жалоба удалена');
        loadReports();
    } catch(e) {}
}

// ===================== ЗАПУСК =====================
async function initApp(telegramId) {
    await loadFeed(telegramId);
    await loadNotifications();
    setInterval(loadNotifications, 30000);
}

// Вход по Enter
document.getElementById('telegram-id-input')?.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') login();
});
'''

# ===================== API ЭНДПОИНТЫ =====================
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
    username: str = Form(None),
    first_name: str = Form("Игрок"),
    db: Session = Depends(get_db)
):
    user = get_or_create_user(telegram_id, username, first_name, db)
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "is_admin": user.is_admin
    }

@app.get("/api/profile/{telegram_id}")
async def get_profile(telegram_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        return None
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    if not profile:
        return None
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
        "updated_at": profile.updated_at.isoformat()
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
    db.commit()
    return {"status": "ok"}

@app.get("/api/posts")
async def get_posts(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    telegram_id: Optional[int] = None,
    search: Optional[str] = None,
    role: Optional[str] = None,
    rank: Optional[str] = None,
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
        query = query.join(Profile, Post.author_id == Profile.user_id).filter(Profile.role.ilike(f"%{role}%"))
    if rank:
        query = query.join(Profile, Post.author_id == Profile.user_id).filter(Profile.rank.ilike(f"%{rank}%"))
    
    query = query.order_by(desc(Post.is_pinned), desc(Post.created_at))
    posts = query.limit(limit).offset(offset).all()
    
    result = []
    for p in posts:
        likes_count = db.query(Like).filter(Like.post_id == p.id).count()
        comments_count = db.query(Comment).filter(Comment.post_id == p.id).count()
        author = db.query(User).filter(User.id == p.author_id).first()
        user_liked = False
        if telegram_id:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if user:
                user_liked = db.query(Like).filter(and_(Like.user_id == user.id, Like.post_id == p.id)).first() is not None
        
        result.append({
            "id": p.id,
            "author_id": p.author_id,
            "author_telegram_id": author.telegram_id if author else None,
            "author_name": f"{author.first_name} {author.last_name or ''}".strip() if author else "Unknown",
            "title": p.title,
            "content": p.content,
            "photo_url": p.photo_url,
            "tags": p.tags,
            "is_pinned": p.is_pinned,
            "created_at": p.created_at.isoformat(),
            "likes_count": likes_count,
            "comments_count": comments_count,
            "user_liked": user_liked
        })
    return result

@app.post("/api/posts")
async def create_post(
    telegram_id: int = Form(...),
    title: str = Form(...),
    content: str = Form(...),
    tags: str = Form(None),
    photo_url: str = Form(None),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    if user.is_banned:
        raise HTTPException(403, "You are banned")
    post = Post(
        author_id=user.id,
        title=title,
        content=content,
        tags=tags,
        photo_url=photo_url
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return {"id": post.id}

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
        # Уведомление автору поста
        if post.author_id != user.id:
            create_notification(post.author_id, "like", f"{user.first_name} поставил лайк на ваш пост", f"/post/{post_id}", db)
        db.commit()
        return {"liked": True}

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
            "created_at": c.created_at.isoformat()
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
    if not user:
        raise HTTPException(404, "User not found")
    if user.is_banned:
        raise HTTPException(403, "You are banned")
    
    comment = Comment(post_id=post_id, author_id=user.id, content=content)
    db.add(comment)
    # Уведомление автору поста
    if post.author_id != user.id:
        create_notification(post.author_id, "comment", f"{user.first_name} прокомментировал ваш пост", f"/post/{post_id}", db)
    db.commit()
    db.refresh(comment)
    return {"id": comment.id}

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

@app.get("/api/admin/stats")
async def admin_stats(telegram_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user or not user.is_admin:
        raise HTTPException(403, "Not admin")
    users = db.query(User).count()
    posts = db.query(Post).count()
    comments = db.query(Comment).count()
    return {"users": users, "posts": posts, "comments": comments}

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
    # Уведомление автору жалобы
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
