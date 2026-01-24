
# Movie Roulette Bot — Production Ready (aiogram 3.x)
# ================================================
# Features:
# - 10 popular genres + Streamers
# - Single-message roulette (no chat spam)
# - Max roulette limit protection
# - Confirmation for clear & roulette
# - Back button everywhere
# - Pin winner
# - FSM-safe handlers
# ================================================


import asyncio
import json
import random
from pathlib import Path
from typing import Dict, Tuple
import aiohttp
import logging

# ======= PING SERVER вставляем сюда =======
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
# ===========================================



import asyncio
import json
import random
from pathlib import Path
from typing import Dict, Tuple

import aiohttp

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("movie_roulette")

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

# ================= CONFIG =================
BOT_TOKEN = "8554333625:AAEN_y6234ckN5ETJ4lNufYlGv__gAxYGLc"
DATA_FILE = Path("movies.json")

ALLOWED_THREAD_IDS = {3, 1388}

MAX_ROULETTE = 100

CATEGORIES = [
    "🎬 Боевик",
    "😂 Комедия",
    "😱 Ужасы",
    "🎭 Драма",
    "💔 Поплакать",
    "🧙 Фэнтези",
    "🚀 Фантастика",
    "🕵️ Триллер",
    "🎨 Мультфильмы",
    "🎥 Стримеры",
]

# ================= BOT ====================
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# ================= FSM ====================
class AddMovie(StatesGroup):
    title = State()
    category = State()

class Confirm(StatesGroup):
    clear = State()
    roulette = State()

# ================= STORAGE =================
LAST_MESSAGE: Dict[Tuple[int, int], int] = {}
LOCK: Dict[Tuple[int, int], bool] = {}

# ================= UTILS =================
def load_data():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {}

def save_data(data):
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def add_movie(chat_id, title, category, author):
    data = load_data()
    cid = str(chat_id)
    data.setdefault(cid, []).append({
        "title": title,
        "category": category,
        "author": author
    })
    save_data(data)

def get_movies(chat_id, category=None):
    movies = load_data().get(str(chat_id), [])
    if category:
        movies = [m for m in movies if m["category"] == category]
    return movies

def remove_movie(chat_id, title):
    data = load_data()
    cid = str(chat_id)
    data[cid] = [m for m in data.get(cid, []) if m["title"] != title]
    save_data(data)

def clear_movies(chat_id):
    data = load_data()
    data[str(chat_id)] = []
    save_data(data)

async def show(chat_id, thread_id, text, kb=None):
    key = (chat_id, thread_id)
    try:
        if key in LAST_MESSAGE:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=LAST_MESSAGE[key],
                text=text,
                reply_markup=kb,
                message_thread_id=thread_id
            )
            return
    except:
        LAST_MESSAGE.pop(key, None)

    msg = await bot.send_message(chat_id, text, reply_markup=kb, message_thread_id=thread_id)
    LAST_MESSAGE[key] = msg.message_id

async def eat(message: Message):
    try:
        await message.delete()
    except:
        pass

def allowed(message: Message):
    return message.message_thread_id in ALLOWED_THREAD_IDS

# ================= KEYBOARDS =================
def main_kb():
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="➕ Добавить фильм")],
        [KeyboardButton(text="🎡 Рулетка"), KeyboardButton(text="📋 Список")],
        [KeyboardButton(text="🗑 Очистить")]
    ])

def back_kb():
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="⬅️ Назад")]
    ])

def category_kb():
    rows = [[KeyboardButton(text=c)] for c in CATEGORIES]
    rows.append([KeyboardButton(text="⬅️ Назад")])
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=rows)

def confirm_kb():
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="✅ Да"), KeyboardButton(text="❌ Нет")]
    ])

# ================= HANDLERS =================
@router.message(CommandStart())
async def start(message: Message):
    if not allowed(message):
        return
    await show(message.chat.id, message.message_thread_id, "🎬 <b>Movie Roulette</b>", main_kb())
    logger.info("Bot started in chat %s thread %s", message.chat.id, message.message_thread_id)

# ---------- ADD ----------
@router.message(F.text == "➕ Добавить фильм")
async def add_start(message: Message, state: FSMContext):
    if not allowed(message):
        return
    await eat(message)
    await state.set_state(AddMovie.title)
    await show(message.chat.id, message.message_thread_id, "✍️ Напиши название фильма:", back_kb())

@router.message(AddMovie.title)
async def add_title(message: Message, state: FSMContext):
    if not allowed(message):
        return
    await eat(message)

    if message.text == "⬅️ Назад":
        await state.clear()
        await show(message.chat.id, message.message_thread_id, "Отменено", main_kb())
        return

    await state.update_data(title=message.text.strip())
    await state.set_state(AddMovie.category)
    await show(message.chat.id, message.message_thread_id, "🎭 Выбери жанр:", category_kb())

@router.message(AddMovie.category)
async def add_category(message: Message, state: FSMContext):
    if not allowed(message):
        return
    await eat(message)

    if message.text == "⬅️ Назад":
        await state.set_state(AddMovie.title)
        await show(message.chat.id, message.message_thread_id, "✍️ Напиши название фильма:", back_kb())
        return

    if message.text not in CATEGORIES:
        return

    data = await state.get_data()
    add_movie(message.chat.id, data["title"], message.text, message.from_user.full_name)
    logger.info("Movie added: %s (%s) by %s", data["title"], message.text, message.from_user.full_name)
    await state.clear()

    await show(message.chat.id, message.message_thread_id, "✅ Фильм добавлен", main_kb())

# ---------- LIST ----------
@router.message(F.text == "📋 Список")
async def list_movies(message: Message):
    if not allowed(message):
        return
    await eat(message)
    movies = get_movies(message.chat.id)

    if not movies:
        await show(message.chat.id, message.message_thread_id, "📭 Пусто", main_kb())
        return

    text = "🎥 <b>Список:</b>\n\n"
    for i, m in enumerate(movies, 1):
        text += f"{i}. {m['title']} — <i>{m['category']}</i>\n"

    await show(message.chat.id, message.message_thread_id, text, main_kb())

# ---------- CLEAR ----------
@router.message(F.text == "🗑 Очистить")
async def clear_confirm(message: Message, state: FSMContext):
    if not allowed(message):
        return
    await eat(message)
    await state.set_state(Confirm.clear)
    await show(message.chat.id, message.message_thread_id, "⚠️ Очистить список?", confirm_kb())

@router.message(Confirm.clear)
async def clear_apply(message: Message, state: FSMContext):
    if not allowed(message):
        return
    await eat(message)

    if message.text == "✅ Да":
        clear_movies(message.chat.id)
        logger.warning("Movie list cleared in chat %s", message.chat.id)
        await show(message.chat.id, message.message_thread_id, "🗑 Очищено", main_kb())
    else:
        await show(message.chat.id, message.message_thread_id, "Отменено", main_kb())

    await state.clear()

# ---------- ROULETTE ----------
@router.message(F.text == "🎡 Рулетка")
async def roulette_confirm(message: Message, state: FSMContext):
    if not allowed(message):
        return
    await eat(message)
    await state.set_state(Confirm.roulette)
    await show(message.chat.id, message.message_thread_id, "🎡 Запустить рулетку?", confirm_kb())

@router.message(Confirm.roulette)
async def roulette_start(message: Message, state: FSMContext):
    if not allowed(message):
        return
    await eat(message)

    if message.text != "✅ Да":
        await show(message.chat.id, message.message_thread_id, "Отменено", main_kb())
        await state.clear()
        return

    await state.clear()
    await show(message.chat.id, message.message_thread_id, "🎭 Выбери жанр:", category_kb())

@router.message(F.text.in_(CATEGORIES) | (F.text == "⬅️ Назад"))
async def roulette_spin(message: Message):
    if not allowed(message):
        return
    await eat(message)

    key = (message.chat.id, message.message_thread_id)
    if LOCK.get(key):
        return
    LOCK[key] = True

    try:
        if message.text == "⬅️ Назад":
            await show(message.chat.id, message.message_thread_id, "Отменено", main_kb())
            return

        movies = get_movies(message.chat.id, message.text)
        if len(movies) < 2:
            await show(message.chat.id, message.message_thread_id, "⚠️ Недостаточно фильмов", main_kb())
            return

        if len(movies) > MAX_ROULETTE:
            await show(message.chat.id, message.message_thread_id, f"⚠️ Лимит {MAX_ROULETTE} фильмов", main_kb())
            return

        pool = movies.copy()
        eliminated = []

        while len(pool) > 1:
            loser = random.choice(pool)
            pool.remove(loser)
            eliminated.append(loser["title"])

            await show(
                message.chat.id,
                message.message_thread_id,
                "🎡 Рулетка\n\n" + "\n".join(f"❌ {t}" for t in eliminated[-10:]),
                None
            )
            await asyncio.sleep(0.4)

        winner = pool[0]
        logger.info("Roulette winner: %s (%s)", winner["title"], winner["category"])
        remove_movie(message.chat.id, winner["title"])

        msg = await bot.send_message(
            message.chat.id,
            f"🏆 <b>Победитель</b>\n{winner['title']}",
            message_thread_id=message.message_thread_id
        )
        await bot.pin_chat_message(message.chat.id, msg.message_id, disable_notification=True)

        await show(message.chat.id, message.message_thread_id, "Готово", main_kb())

    finally:
        LOCK[key] = False

# ================= RUN =================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
