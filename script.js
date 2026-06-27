let currentUser = null;
let currentUserId = null;
let isOwner = false;

// Инициализация Telegram WebApp
const tg = window.Telegram.WebApp;
tg.expand();

// Получение данных пользователя
async function initUser() {
    try {
        const response = await fetch('/api/me', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({ init_data: tg.initData })
        });
        
        if (!response.ok) throw new Error('Auth failed');
        currentUser = await response.json();
        currentUserId = currentUser.id;
        isOwner = currentUser.is_owner || false;
        
        document.getElementById('user-info').innerHTML = `
            <span>${currentUser.first_name}</span>
            <div class="user-avatar">${currentUser.first_name[0]}</div>
        `;
        
        await loadNews();
        await loadFeed();
    } catch (error) {
        console.error('Init error:', error);
        document.getElementById('content').innerHTML = `
            <div class="empty-state">
                <span class="emoji">❌</span>
                <h3>Ошибка авторизации</h3>
                <p>Пожалуйста, откройте бота через Telegram</p>
            </div>
        `;
    }
}

// Загрузка новостей
async function loadNews() {
    try {
        const response = await fetch('/api/news?limit=3');
        const news = await response.json();
        const banner = document.querySelector('.news-content');
        
        if (news.length > 0) {
            const latest = news[0];
            banner.innerHTML = `
                <span>📢</span>
                <span><strong>${latest.title}</strong> — ${latest.content}</span>
                <span style="font-size:11px;opacity:0.7;margin-left:auto;">
                    ${new Date(latest.created_at).toLocaleDateString()}
                </span>
            `;
        } else {
            banner.innerHTML = '🌟 Добро пожаловать в MLBB Team Finder!';
        }
    } catch (error) {
        console.error('News load error:', error);
    }
}

// Загрузка ленты
async function loadFeed() {
    const content = document.getElementById('content');
    content.innerHTML = `
        <div class="loading">
            <div class="spinner"></div>
            <p>Загрузка постов...</p>
        </div>
    `;
    
    try {
        const response = await fetch(`/api/posts?user_id=${currentUserId}`);
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
        
        // Добавляем обработчики событий
        document.querySelectorAll('.action-btn.like-btn').forEach(btn => {
            btn.addEventListener('click', handleLike);
        });
        
        document.querySelectorAll('.action-btn.comment-btn').forEach(btn => {
            btn.addEventListener('click', handleCommentToggle);
        });
        
        document.querySelectorAll('.comment-submit').forEach(btn => {
            btn.addEventListener('click', handleCommentSubmit);
        });
        
        document.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', handleDelete);
        });
        
    } catch (error) {
        console.error('Feed load error:', error);
        content.innerHTML = `
            <div class="empty-state">
                <span class="emoji">⚠️</span>
                <h3>Ошибка загрузки</h3>
                <p>Попробуйте обновить страницу</p>
            </div>
        `;
    }
}

// Рендер поста
function renderPost(post) {
    const canDelete = (currentUserId === post.author_id || isOwner);
    const photoHtml = post.photo ? `<img src="data:image/jpeg;base64,${post.photo}" alt="Post photo" class="post-photo">` : '';
    const commentsHtml = post.comments_count > 0 ? `
        <div class="comments-section" data-post-id="${post.id}" style="display:none;">
            <div class="comments-list"></div>
            <div class="comment-input">
                <input type="text" placeholder="Написать комментарий..." class="comment-input-field" data-post-id="${post.id}">
                <button class="comment-submit" data-post-id="${post.id}">➤</button>
            </div>
        </div>
    ` : `
        <div class="comments-section" data-post-id="${post.id}" style="display:none;">
            <div class="comments-list"></div>
            <div class="comment-input">
                <input type="text" placeholder="Написать комментарий..." class="comment-input-field" data-post-id="${post.id}">
                <button class="comment-submit" data-post-id="${post.id}">➤</button>
            </div>
        </div>
    `;
    
    return `
        <div class="post-card" data-post-id="${post.id}">
            <div class="post-header">
                <span class="post-author">${post.author.first_name} ${post.author.last_name || ''}</span>
                <span class="post-time">${new Date(post.created_at).toLocaleString('ru-RU')}</span>
                ${canDelete ? `<button class="delete-btn" data-post-id="${post.id}">🗑️</button>` : ''}
            </div>
            <div class="post-content">${post.content}</div>
            ${photoHtml}
            <div class="post-actions">
                <button class="action-btn like-btn ${post.user_liked ? 'liked' : ''}" data-post-id="${post.id}">
                    <span class="heart">${post.user_liked ? '❤️' : '🤍'}</span>
                    <span>${post.likes_count}</span>
                </button>
                <button class="action-btn comment-btn" data-post-id="${post.id}">
                    💬 <span>${post.comments_count}</span>
                </button>
            </div>
            ${commentsHtml}
        </div>
    `;
}

// Обработка лайков
async function handleLike(e) {
    const btn = e.currentTarget;
    const postId = btn.dataset.postId;
    const heart = btn.querySelector('.heart');
    const countSpan = btn.querySelector('span:last-child');
    
    try {
        const response = await fetch('/api/like', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({ post_id: postId, user_id: currentUserId })
        });
        
        const data = await response.json();
        
        if (data.liked) {
            btn.classList.add('liked');
            heart.textContent = '❤️';
            countSpan.textContent = parseInt(countSpan.textContent) + 1;
        } else {
            btn.classList.remove('liked');
            heart.textContent = '🤍';
            countSpan.textContent = parseInt(countSpan.textContent) - 1;
        }
    } catch (error) {
        console.error('Like error:', error);
    }
}

// Переключение комментариев
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

// Загрузка комментариев
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
                <span class="comment-author">${c.author.first_name}</span>
                <span class="comment-text">${c.content}</span>
                ${(currentUserId === c.author_id || isOwner) ? `<button class="comment-delete" data-comment-id="${c.id}">🗑️</button>` : ''}
            </div>
        `).join('');
        
        // Добавляем обработчики удаления комментариев
        list.querySelectorAll('.comment-delete').forEach(btn => {
            btn.addEventListener('click', handleCommentDelete);
        });
        
    } catch (error) {
        console.error('Comments load error:', error);
    }
}

// Отправка комментария
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
            body: new URLSearchParams({ post_id: postId, user_id: currentUserId, content })
        });
        
        if (response.ok) {
            input.value = '';
            await loadComments(postId);
            // Обновляем счетчик комментариев
            const commentBtn = document.querySelector(`.comment-btn[data-post-id="${postId}"]`);
            const span = commentBtn.querySelector('span:last-child');
            span.textContent = parseInt(span.textContent) + 1;
        }
    } catch (error) {
        console.error('Comment error:', error);
    }
}

// Удаление поста
async function handleDelete(e) {
    const btn = e.currentTarget;
    const postId = btn.dataset.postId;
    
    if (!confirm('Удалить этот пост?')) return;
    
    try {
        const response = await fetch(`/api/posts/${postId}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({ user_id: currentUserId })
        });
        
        if (response.ok) {
            const card = document.querySelector(`.post-card[data-post-id="${postId}"]`);
            card.style.animation = 'slideUp 0.3s reverse';
            setTimeout(() => card.remove(), 300);
        }
    } catch (error) {
        console.error('Delete error:', error);
    }
}

// Удаление комментария
async function handleCommentDelete(e) {
    const btn = e.currentTarget;
    const commentId = btn.dataset.commentId;
    
    if (!confirm('Удалить комментарий?')) return;
    
    try {
        const response = await fetch(`/api/comments/${commentId}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({ user_id: currentUserId })
        });
        
        if (response.ok) {
            const comment = btn.closest('.comment');
            comment.style.opacity = '0';
            setTimeout(() => comment.remove(), 300);
        }
    } catch (error) {
        console.error('Comment delete error:', error);
    }
}

// Загрузка профиля
async function loadProfile() {
    const content = document.getElementById('content');
    content.innerHTML = `
        <div class="loading">
            <div class="spinner"></div>
            <p>Загрузка профиля...</p>
        </div>
    `;
    
    try {
        const response = await fetch(`/api/profile/${currentUserId}`);
        const profile = await response.json();
        
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
                        <label>Фото профиля</label>
                        <div class="photo-upload">
                            ${profile.photo ? `<img src="data:image/jpeg;base64,${profile.photo}" class="photo-preview">` : '<span style="color:#8e8e93;">Нет фото</span>'}
                            <input type="file" name="photo" accept="image/*" style="flex:1;">
                        </div>
                    </div>
                    <div class="switch-group">
                        <span>🔔 Уведомления</span>
                        <div class="switch ${profile.notifications ? 'active' : ''}" onclick="toggleSwitch(this)">
                            <div class="slider"></div>
                        </div>
                        <input type="hidden" name="notifications" value="${profile.notifications}">
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
                <p>Попробуйте обновить страницу</p>
            </div>
        `;
    }
}

// Переключение уведомлений
function toggleSwitch(el) {
    el.classList.toggle('active');
    const hidden = el.parentElement.querySelector('input[type="hidden"]');
    hidden.value = el.classList.contains('active');
}

// Отправка профиля
async function handleProfileSubmit(e) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);
    formData.append('user_id', currentUserId);
    
    try {
        const response = await fetch('/api/profile', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            alert('✅ Профиль сохранён!');
            await loadProfile();
        }
    } catch (error) {
        console.error('Profile save error:', error);
        alert('❌ Ошибка сохранения профиля');
    }
}

// Создание поста
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
                    <label>Фото (необязательно)</label>
                    <div class="photo-upload">
                        <input type="file" name="photo" accept="image/*">
                    </div>
                </div>
                <button type="submit" class="btn-post">📤 Опубликовать</button>
            </form>
        </div>
    `;
    
    document.getElementById('newPostForm').addEventListener('submit', handlePostSubmit);
}

// Отправка поста
async function handlePostSubmit(e) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);
    formData.append('user_id', currentUserId);
    
    const btn = form.querySelector('.btn-post');
    btn.textContent = '⏳ Публикация...';
    btn.disabled = true;
    
    try {
        const response = await fetch('/api/posts', {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            alert('✅ Пост опубликован!');
            btn.textContent = '✅ Готово!';
            setTimeout(() => {
                switchTab('feed');
                loadFeed();
            }, 1000);
        }
    } catch (error) {
        console.error('Post error:', error);
        alert('❌ Ошибка публикации');
        btn.textContent = '📤 Опубликовать';
        btn.disabled = false;
    }
}

// Навигация по вкладкам
function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
    });
    
    switch(tab) {
        case 'feed':
            loadFeed();
            break;
        case 'profile':
            loadProfile();
            break;
        case 'newpost':
            showNewPost();
            break;
    }
}

// Инициализация
document.addEventListener('DOMContentLoaded', function() {
    // Обработка вкладок
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            switchTab(this.dataset.tab);
        });
    });
    
    // Запуск
    initUser();
});

// Обновление новостей каждые 5 минут
setInterval(loadNews, 300000);