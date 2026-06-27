from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command
from config import BOT_TOKEN, WEBAPP_URL
from database import AsyncSessionLocal, News
from sqlalchemy import select

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    webapp_url = f"{WEBAPP_URL}/webapp"
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Найти тимейтов", web_app=WebAppInfo(url=webapp_url))]
        ]
    )
    await message.answer(
        "🌟 Добро пожаловать в MLBB Team Finder!\n\n"
        "Здесь вы можете найти идеальных тимейтов для Mobile Legends.\n"
        "Нажмите кнопку ниже, чтобы открыть приложение и создать анкету.",
        reply_markup=keyboard
    )

@dp.message(Command("news"))
async def news_cmd(message: types.Message):
    async with AsyncSessionLocal() as session:
        stmt = select(News).where(News.is_active == True).order_by(News.created_at.desc()).limit(5)
        result = await session.execute(stmt)
        news_list = result.scalars().all()
        
    if not news_list:
        await message.answer("📭 Новостей пока нет.")
        return
    
    text = "📢 *Последние новости бота:*\n\n"
    for idx, news in enumerate(news_list, 1):
        text += f"*{idx}. {news.title}*\n{news.content}\n"
        text += f"🕐 {news.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
    
    await message.answer(text, parse_mode="Markdown")