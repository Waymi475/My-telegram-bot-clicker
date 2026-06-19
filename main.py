# main.py
# Telegram Clicker Bot (aiogram 3 + SQLite)
# pip install -U aiogram

import asyncio
import sqlite3
import time
from datetime import date

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery

TOKEN = "PASTE_BOT_TOKEN_HERE"

db = sqlite3.connect("clicker.db")
db.execute("""
CREATE TABLE IF NOT EXISTS users(
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    coins INTEGER DEFAULT 0,
    click_power INTEGER DEFAULT 1,
    auto_income INTEGER DEFAULT 0,
    referrals INTEGER DEFAULT 0,
    last_daily TEXT DEFAULT '',
    last_seen INTEGER DEFAULT 0
)
""")
db.commit()

SHOP = {
    "cursor": ("🖱 Курсор", 50, 1, 0),
    "mouse": ("🐭 Мышка", 250, 5, 0),
    "auto": ("⚡ Автокликер", 500, 0, 1),
    "farm": ("🌾 Ферма", 2500, 0, 5),
    "factory": ("🏭 Завод", 10000, 0, 25),
}

bot = Bot(TOKEN)
dp = Dispatcher()


def get_user(uid):
    row = db.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
    return row

def create_user(uid, username=""):
    if not get_user(uid):
        db.execute(
            "INSERT INTO users(user_id, username, last_seen) VALUES(?,?,?)",
            (uid, username, int(time.time()))
        )
        db.commit()

def apply_offline_income(uid):
    row = get_user(uid)
    now = int(time.time())
    passed = max(0, now - row[7])
    earned = passed * row[5]
    if earned:
        db.execute(
            "UPDATE users SET coins=coins+?, last_seen=? WHERE user_id=?",
            (earned, now, uid)
        )
    else:
        db.execute("UPDATE users SET last_seen=? WHERE user_id=?", (now, uid))
    db.commit()

def profile(uid):
    apply_offline_income(uid)
    r = get_user(uid)
    return (
        f"📊 Профиль\n\n"
        f"💰 Монеты: {r[2]}\n"
        f"👆 Сила клика: {r[3]}\n"
        f"⚡ Доход/сек: {r[4]}\n"
        f"👥 Рефералы: {r[5]}"
    )

def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Клик", callback_data="click")],
        [InlineKeyboardButton(text="📊 Профиль", callback_data="profile"),
         InlineKeyboardButton(text="🛒 Магазин", callback_data="shop")],
        [InlineKeyboardButton(text="🎁 Daily", callback_data="daily"),
         InlineKeyboardButton(text="🏆 Топ", callback_data="top")],
        [InlineKeyboardButton(text="👥 Рефералы", callback_data="refs")]
    ])

def shop_menu():
    rows = []
    for key, item in SHOP.items():
        rows.append([InlineKeyboardButton(
            text=f"{item[0]} - {item[1]}",
            callback_data=f"buy:{key}")
        ])
    rows.append([InlineKeyboardButton(text="⬅ Назад", callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@dp.message(CommandStart())
async def start(message: Message):
    uid = message.from_user.id
    create_user(uid, message.from_user.username or "")

    parts = message.text.split()
    if len(parts) > 1:
        try:
            ref = int(parts[1])
            if ref != uid and get_user(ref):
                db.execute("UPDATE users SET coins=coins+5000, referrals=referrals+1 WHERE user_id=?", (ref,))
                db.commit()
        except:
            pass

    await message.answer("🚀 Кликер запущен", reply_markup=menu())

@dp.message(Command("top"))
async def top_cmd(message: Message):
    rows = db.execute(
        "SELECT username, coins FROM users ORDER BY coins DESC LIMIT 10"
    ).fetchall()

    text = "🏆 ТОП\n\n"
    for i, row in enumerate(rows, start=1):
        text += f"{i}. {row[0] or 'Игрок'} — {row[1]}\n"

    await message.answer(text)

@dp.callback_query(F.data == "click")
async def click(call: CallbackQuery):
    uid = call.from_user.id
    apply_offline_income(uid)
    power = get_user(uid)[3]
    db.execute("UPDATE users SET coins=coins+? WHERE user_id=?", (power, uid))
    db.commit()
    await call.answer(f"+{power}")
    await call.message.edit_text(profile(uid), reply_markup=menu())

@dp.callback_query(F.data == "profile")
async def prof(call: CallbackQuery):
    await call.message.edit_text(profile(call.from_user.id), reply_markup=menu())

@dp.callback_query(F.data == "shop")
async def shop(call: CallbackQuery):
    await call.message.edit_text("🛒 Магазин", reply_markup=shop_menu())

@dp.callback_query(F.data.startswith("buy:"))
async def buy(call: CallbackQuery):
    uid = call.from_user.id
    key = call.data.split(":")[1]
    item = SHOP[key]

    apply_offline_income(uid)
    coins = get_user(uid)[2]

    if coins < item[1]:
        await call.answer("Недостаточно монет", show_alert=True)
        return

    db.execute("""
    UPDATE users
    SET coins=coins-?,
        click_power=click_power+?,
        auto_income=auto_income+?
    WHERE user_id=?
    """, (item[1], item[2], item[3], uid))
    db.commit()

    await call.answer("Покупка успешна")
    await call.message.edit_text(profile(uid), reply_markup=menu())

@dp.callback_query(F.data == "daily")
async def daily(call: CallbackQuery):
    uid = call.from_user.id
    today = str(date.today())
    row = get_user(uid)

    if row[6] == today:
        await call.answer("Награда уже получена", show_alert=True)
        return

    db.execute(
        "UPDATE users SET coins=coins+1000, last_daily=? WHERE user_id=?",
        (today, uid)
    )
    db.commit()

    await call.answer("Получено 1000 монет!")
    await call.message.edit_text(profile(uid), reply_markup=menu())

@dp.callback_query(F.data == "top")
async def top_inline(call: CallbackQuery):
    rows = db.execute(
        "SELECT username, coins FROM users ORDER BY coins DESC LIMIT 10"
    ).fetchall()

    text = "🏆 ТОП\n\n"
    for i, row in enumerate(rows, start=1):
        text += f"{i}. {row[0] or 'Игрок'} — {row[1]}\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])
    await call.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data == "refs")
async def refs(call: CallbackQuery):
    me = await bot.get_me()
    uid = call.from_user.id

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])

    await call.message.edit_text(
        f"👥 Приглашено: {get_user(uid)[5]}\n\n"
        f"https://t.me/{me.username}?start={uid}",
        reply_markup=kb
    )

@dp.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.message.edit_text(profile(call.from_user.id), reply_markup=menu())

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
