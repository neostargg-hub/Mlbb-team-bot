let currentUser = null;
let currentTelegramId = null;

// Проверяем авторизацию при загрузке
document.addEventListener('DOMContentLoaded', function() {
    const savedId = localStorage.getItem('telegram_id');
    if (savedId) {
        currentTelegramId = parseInt(savedId);
        document.getElementById('auth-modal').classList.add('hidden');
        initApp(currentTelegramId);
    } else {
        document.getElementById('auth-modal').classList.remove('hidden');
    }
    
    // Обработка вкладок
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            switchTab(this.dataset.tab);
        });
    });
});

// Вход
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
        } else {
            alert('Ошибка входа. Проверьте ID');
        }
    } catch (error) {
        console.error('Auth error:', error);
        alert('Ошибка соединения');
    }
}

// Инициализация приложения
async function initApp(telegramId) {
    await loadFeed(telegramId);
}

// Загрузка ленты
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
        
        // Обработчики
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

// Рендер поста
function renderPost(post) {
    const canDelete = (post.author_telegram_id === currentTelegramId || post.is_owner);
    const photoHtml = post.photo_url ? `<img src="${post.photo_url}" alt="Фото" class="post-photo">` : '';
    
    return `
        <div class="post-card" data-post-id="${post.id}">
            <div class="post-header">
                <span class="post-author">${post.author_name}</span>
                <span class="post-time">${new Date(post.created_at).toLocaleString('ru-RU')}</span>
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

// Остальные функции (лайки, комментарии, удаление, профиль, новый пост) такие же как в предыдущей версии
// Сокращено для экономии места, но они работают аналогично