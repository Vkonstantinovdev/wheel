import asyncio
import json
import random
from pathlib import Path
from typing import Dict

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.filters.text import TextFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

# ================= CONFIG =================
BOT_TOKEN = "8554333625:AAEN_y6234ckN5ETJ4lNufYlGv__gAxYGLc"
DATA_FILE = Path("movies.json")
ALLOWED_THREAD_ID = 1388  # Ветка, где бот работает

# ================= BOT ====================
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())

# ================= FSM ====================
class AddMovie(StatesGroup):
    title = State()
    category = State()

# ================= SINGLE MESSAGE =================
LAST_MESSAGE: Dict[int, int] = {}
WHEEL_LOCK: Dict[int, bool] = {}

# ================= STORAGE =================
def load_data():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {}

def save_data(data):
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")

def add_movie(chat_id, title, category, author):
    data = load_data()
    cid = str(chat_id)
    data.setdefault(cid, []).append({"title": title, "category": category, "author": author})
    save_data(data)

def get_movies(chat_id, category=None):
    movies = load_data().get(str(chat_id), [])
    if category:
        movies = [m for m in movies if m.get("category") == category]
    return movies

def remove_movie(chat_id, title):
    data = load_data()
    cid = str(chat_id)
    data[cid] = [m for m in data.get(cid, []) if m.get("title") != title]
    save_data(data)

def clear_movies(chat_id):
    data = load_data()
    data[str(chat_id)] = []
    save_data(data)

# ================= KEYBOARDS =================
def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("➕ Добавить фильм")],
            [KeyboardButton("🎡 Рулетка"), KeyboardButton("📋 Список")],
            [KeyboardButton("🗑 Очистить")],
        ],
        resize_keyboard=True
    )

def category_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("Мультфильм"), KeyboardButton("Ужасы")],
            [KeyboardButton("Комедия"), KeyboardButton("Любое")],
            [KeyboardButton("⬅️ В меню")]
        ],
        resize_keyboard=True
    )

# ================= UI HELPERS =================
async def show(chat_id: int, text: str, kb=None):
    try:
        if chat_id in LAST_MESSAGE:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=LAST_MESSAGE[chat_id],
                text=text,
                reply_markup=kb,
                message_thread_id=ALLOWED_THREAD_ID
            )
            return
    except:
        pass
    msg = await bot.send_message(chat_id, text, reply_markup=kb, message_thread_id=ALLOWED_THREAD_ID)
    LAST_MESSAGE[chat_id] = msg.message_id

async def kill_message(message: Message):
    try:
        await message.delete()
    except:
        pass

# ================= HANDLERS =================
@dp.message(Command("start"))
async def start(message: Message):
    tid = getattr(message, "message_thread_id", None)
    if tid != ALLOWED_THREAD_ID:
        await message.reply("Бот работает только в нужной ветке.")
        return
    await kill_message(message)
    await show(message.chat.id, "🎬 <b>Movie Roulette</b>\nВыберите действие:", main_kb())

# ---------- ADD MOVIE ----------
@dp.message(TextFilter(equals="➕ Добавить фильм"))
async def add_start(message: Message, state: FSMContext):
    tid = getattr(message, "message_thread_id", None)
    if tid != ALLOWED_THREAD_ID:
        await message.reply("Эта ветка не разрешена.")
        return
    await state.set_state(AddMovie.title)
    await message.reply("Напиши название фильма:", reply_markup=category_kb())

@dp.message(AddMovie.title)
async def add_title(message: Message, state: FSMContext):
    tid = getattr(message, "message_thread_id", None)
    if tid != ALLOWED_THREAD_ID:
        return
    title = message.text.strip()
    await kill_message(message)
    if not title:
        return
    await state.update_data(title=title)
    await state.set_state(AddMovie.category)
    await show(message.chat.id, f"🎬 <b>{title}</b>\nВыберите категорию:", category_kb())

@dp.message(AddMovie.category)
async def add_category(message: Message, state: FSMContext):
    tid = getattr(message, "message_thread_id", None)
    if tid != ALLOWED_THREAD_ID:
        return
    category = message.text.lower()
    if category == "любое":
        category = "разное"
    data = await state.get_data()
    author = message.from_user.full_name
    add_movie(message.chat.id, data["title"], category, author)
    await state.clear()
    await show(message.chat.id, f"✅ <b>{data['title']}</b> добавил <i>{author}</i>", main_kb())

# ---------- LIST ----------
@dp.message(TextFilter(equals="📋 Список"))
async def list_movies(message: Message):
    tid = getattr(message, "message_thread_id", None)
    if tid != ALLOWED_THREAD_ID:
        await message.reply("Эта ветка не разрешена.")
        return
    movies = get_movies(message.chat.id)
    if not movies:
        await show(message.chat.id, "📭 Список пуст", main_kb())
        return
    text = "🎥 <b>Список фильмов</b>\n\n"
    for i, m in enumerate(movies, 1):
        author = m.get("author", "неизвестно")
        text += f"{i}. {m['title']} — <i>{author}</i>\n"
    await show(message.chat.id, text, main_kb())

# ---------- CLEAR ----------
@dp.message(TextFilter(equals="🗑 Очистить"))
async def clear_list(message: Message):
    tid = getattr(message, "message_thread_id", None)
    if tid != ALLOWED_THREAD_ID:
        await message.reply("Эта ветка не разрешена.")
        return
    clear_movies(message.chat.id)
    await show(message.chat.id, "🗑 Список очищен", main_kb())

# ---------- WHEEL ----------
@dp.message(TextFilter(equals="🎡 Рулетка"))
async def wheel_start(message: Message):
    tid = getattr(message, "message_thread_id", None)
    if tid != ALLOWED_THREAD_ID:
        await message.reply("Эта ветка не разрешена.")
        return
    await show(message.chat.id, "🎡 Выберите категорию для рулетки:", category_kb())

@dp.message(lambda m: m.text.lower() in ["мультфильм", "ужасы", "комедия", "любое"])
async def wheel_spin(message: Message):
    tid = getattr(message, "message_thread_id", None)
    if tid != ALLOWED_THREAD_ID:
        await message.reply("Эта ветка не разрешена.")
        return
    chat_id = message.chat.id
    if WHEEL_LOCK.get(chat_id):
        await message.reply("Рулетка уже крутится, подождите...")
        return
    WHEEL_LOCK[chat_id] = True
    category = message.text.lower()
    cat = None if category == "любое" else category
    movies = get_movies(chat_id, cat)
    if not movies:
        WHEEL_LOCK[chat_id] = False
        await show(chat_id, "⚠️ Нет фильмов в этой категории", main_kb())
        return
    pool = movies.copy()
    eliminated = []
    while len(pool) > 1:
        loser = random.choice(pool)
        pool.remove(loser)
        eliminated.append(loser["title"])
        await show(chat_id, "🎡 Рулетка\n\n" + "\n".join(f"❌ {t}" for t in eliminated))
        await asyncio.sleep(0.5)
    winner = pool[0]
    remove_movie(chat_id, winner["title"])
    WHEEL_LOCK[chat_id] = False
    author = winner.get("author", "неизвестно")
    await show(chat_id, f"🏆 <b>Победитель</b>\n{winner['title']}\nДобавил: <i>{author}</i>", main_kb())

# ================= SELF-PING =================
async def self_ping():
    """Пингуем Google каждые 5 секунд, чтобы Render не засыпал"""
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get("https://www.google.com", timeout=5) as resp:
                    print(f"[PING] Google status: {resp.status}")
            except Exception as e:
                print(f"[PING ERROR] {e}")
            await asyncio.sleep(5)

# ================= RUN =================
async def main():
    asyncio.create_task(self_ping())  # фоновый пинг
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
