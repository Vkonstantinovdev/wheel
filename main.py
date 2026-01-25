# ================= Movie Roulette (SQLite version) =================
import asyncio
import random
import logging
import sqlite3
from pathlib import Path
from typing import Dict, Tuple

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties




# ================= KEEP ALIVE (Railway) =================
from flask import Flask
from threading import Thread
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "OK", 200

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

Thread(target=run_web, daemon=True).start()
# ========================================================


# ================= LOG =================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("movie_roulette")

# ================= PATHS =================
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "movies.db"

# ================= CONFIG =================
BOT_TOKEN = "8554333625:AAEN_y6234ckN5ETJ4lNufYlGv__gAxYGLc"
ALLOWED_THREAD_IDS = {3, 1388}
MAX_ROULETTE = 100

CATEGORIES = [
    "🎬 Боевик", "😂 Комедия", "😱 Ужасы", "🎭 Драма / Поплакать",
    "🧙 Фэнтези", "🚀 Фантастика", "🕵️ Триллер", "🎨 Мультфильмы"
]

# ================= DB =================
def get_db():
    return sqlite3.connect(DB_PATH)

def init_db():
    with get_db() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            title TEXT,
            category TEXT,
            author TEXT
        )
        """)

# ================= BOT =================
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# ================= FSM =================
class AddMovie(StatesGroup):
    title = State()
    category = State()

# ================= UTILS =================
def allowed(message: Message) -> bool:
    return message.message_thread_id in ALLOWED_THREAD_IDS

def add_movie(chat_id, title, category, author):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO movies (chat_id, title, category, author) VALUES (?, ?, ?, ?)",
            (str(chat_id), title, category, author)
        )

def get_movies(chat_id):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT title, category FROM movies WHERE chat_id = ?",
            (str(chat_id),)
        )
        return cur.fetchall()

def clear_movies(chat_id):
    with get_db() as conn:
        conn.execute("DELETE FROM movies WHERE chat_id = ?", (str(chat_id),))

# ================= KEYBOARDS =================
def main_kb():
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="➕ Добавить фильм")],
        [KeyboardButton(text="🎡 Рулетка"), KeyboardButton(text="📋 Список")],
        [KeyboardButton(text="🗑 Очистить")]
    ])

def category_kb():
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text=c)] for c in CATEGORIES
    ])

# ================= HANDLERS =================
@router.message(CommandStart())
async def start(message: Message):
    if not allowed(message):
        return
    await message.answer("🎬 <b>Movie Roulette</b>", reply_markup=main_kb())

@router.message(F.text == "➕ Добавить фильм")
async def add_start(message: Message, state: FSMContext):
    if not allowed(message):
        return
    await state.set_state(AddMovie.title)
    await message.answer("Название фильма:")

@router.message(AddMovie.title)
async def add_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(AddMovie.category)
    await message.answer("Выбери жанр:", reply_markup=category_kb())

@router.message(AddMovie.category)
async def add_category(message: Message, state: FSMContext):
    data = await state.get_data()
    add_movie(message.chat.id, data["title"], message.text, message.from_user.full_name)
    await state.clear()
    await message.answer("✅ Добавлено", reply_markup=main_kb())

@router.message(F.text == "📋 Список")
async def list_movies(message: Message):
    movies = get_movies(message.chat.id)
    if not movies:
        await message.answer("📭 Пусто")
        return
    text = "\n".join(f"{i+1}. {t} — {c}" for i, (t, c) in enumerate(movies))
    await message.answer(text)

@router.message(F.text == "🗑 Очистить")
async def clear(message: Message):
    clear_movies(message.chat.id)
    await message.answer("🗑 Очищено")

@router.message(F.text == "🎡 Рулетка")
async def roulette(message: Message):
    movies = get_movies(message.chat.id)
    if len(movies) < 2:
        await message.answer("⚠️ Недостаточно фильмов")
        return
    winner = random.choice(movies)
    await message.answer(f"🏆 Победитель: <b>{winner[0]}</b>")

# ================= RUN =================
async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
