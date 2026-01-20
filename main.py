import asyncio
import random
import json
from pathlib import Path
from typing import Dict

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

# ================= CONFIG =================
BOT_TOKEN = "8554333625:AAEN_y6234ckN5ETJ4lNufYlGv__gAxYGLc"
DATA_FILE = Path("movies.json")
ALLOWED_THREAD_ID = 1388  # ID ветки/топика чата, где бот работает

# ================= BOT ====================
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)

dp = Dispatcher(storage=MemoryStorage())

# ================= FSM ====================
class AddMovie(StatesGroup):
    title = State()
    category = State()

# ================= SINGLE MESSAGE PER CHAT =================
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

# ================= UI HELPERS =================
async def show(chat_id: int, text: str, kb: InlineKeyboardMarkup):
    if chat_id in LAST_MESSAGE:
        try:
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

# ================= KEYBOARDS =================
def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить фильм", callback_data="add")],
        [InlineKeyboardButton(text="🎡 Рулетка", callback_data="wheel")],
        [InlineKeyboardButton(text="📋 Список", callback_data="list")],
        [InlineKeyboardButton(text="🗑 Очистить", callback_data="clear")],
    ])


def category_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Мультфильм", callback_data="cat_мультфильм")],
        [InlineKeyboardButton(text="Ужасы", callback_data="cat_ужасы")],
        [InlineKeyboardButton(text="Комедия", callback_data="cat_комедия")],
        [InlineKeyboardButton(text="Любое", callback_data="cat_любое")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")],
    ])

# ================= THREAD CHECK =================
def check_thread(message_or_query):
    tid = getattr(message_or_query, "message_thread_id", None)
    if tid != ALLOWED_THREAD_ID:
        return False
    return True

# ================= HANDLERS =================
@dp.message(Command("start"))
async def start(message: Message):
    if getattr(message, "message_thread_id", None) != ALLOWED_THREAD_ID:
        await message.reply("Бот работает только в этой ветке.")
        return
    await kill_message(message)
    await show(
        message.chat.id,
        "🎬 <b>Movie Roulette</b>\nОдно сообщение — много людей",
        main_kb()
    )


@dp.callback_query(F.data == "menu")
async def back_menu(query: CallbackQuery):
    if getattr(query.message, "message_thread_id", None) != ALLOWED_THREAD_ID:
        await query.answer("Эта ветка не разрешена", show_alert=True)
        return
    await query.answer()
    await show(query.message.chat.id, "🎬 Главное меню", main_kb())

# ---------- ADD MOVIE (MULTIUSER SAFE) ----------
@dp.callback_query(F.data == "add")
async def add_start(query: CallbackQuery, state: FSMContext):
    if getattr(query.message, "message_thread_id", None) != ALLOWED_THREAD_ID:
        await query.answer("Эта ветка не разрешена", show_alert=True)
        return
    await query.answer("Пиши название фильма")
    await state.set_state(AddMovie.title)

@dp.message(AddMovie.title)
async def add_title(message: Message, state: FSMContext):
    if getattr(message, "message_thread_id", None) != ALLOWED_THREAD_ID:
        return
    title = message.text.strip()
    await kill_message(message)
    if not title:
        return
    await state.update_data(title=title)
    await state.set_state(AddMovie.category)
    await show(
        message.chat.id,
        f"🎬 <b>{title}</b>\nВыбери категорию",
        category_kb()
    )

@dp.callback_query(AddMovie.category, F.data.startswith("cat_"))
async def add_category(query: CallbackQuery, state: FSMContext):
    if getattr(query.message, "message_thread_id", None) != ALLOWED_THREAD_ID:
        await query.answer("Эта ветка не разрешена", show_alert=True)
        return
    data = await state.get_data()
    category = query.data.replace("cat_", "")
    if category == "любое":
        category = "разное"
    author = query.from_user.full_name
    add_movie(query.message.chat.id, data["title"], category, author)
    await state.clear()
    await query.answer("Фильм добавлен")
    await show(
        query.message.chat.id,
        f"✅ <b>{data['title']}</b> добавил <i>{author}</i>",
        main_kb()
    )

# ---------- OTHER HANDLERS (LIST, WHEEL, CLEAR) ----------
# Везде проверка message_thread_id через getattr(query.message, "message_thread_id", None) == ALLOWED_THREAD_ID
# (аналогично как выше)

# ================= RUN =================
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
