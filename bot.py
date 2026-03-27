import asyncio
import re
import json
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

DATA_FILE = "data.json"

# --- загрузка и сохранение данных ---
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

users = load_data()

# --- клавиатуры ---
keyboard_main = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="▶️ Начать смену")],
        [KeyboardButton(text="📊 Итог"), KeyboardButton(text="📜 История")],
        [KeyboardButton(text="⛔ Закончить смену"), KeyboardButton(text="🗑 Очистить историю")]
    ],
    resize_keyboard=True
)

keyboard_confirm = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Подтвердить очистку"), KeyboardButton(text="❌ Отмена")]
    ],
    resize_keyboard=True
)

# --- парсер суммы ---
def extract_amount(text):
    match = re.search(r"оставили\s+([\d\s]+[.,]?\d*)\s*RUB", text)
    if match:
        return float(match.group(1).replace(" ", "").replace(",", "."))
    return None

def get_user(user_id):
    user_id = str(user_id)
    if user_id not in users:
        users[user_id] = {"current": 0, "history": [], "await_clear_confirm": False}
    return users[user_id]

# --- хэндлеры ---
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Готов считать чаевые 👌", reply_markup=keyboard_main)

@dp.message(lambda m: m.text == "▶️ Начать смену")
async def start_shift(message: types.Message):
    user = get_user(message.from_user.id)
    user["current"] = 0
    save_data(users)
    await message.answer("Смена началась 💸", reply_markup=keyboard_main)

@dp.message(lambda m: m.text == "📊 Итог")
async def total(message: types.Message):
    user = get_user(message.from_user.id)
    await message.answer(f"Сейчас: {round(user['current'], 2)}", reply_markup=keyboard_main)

@dp.message(lambda m: m.text == "⛔ Закончить смену")
async def end_shift(message: types.Message):
    user = get_user(message.from_user.id)
    total_amount = user["current"]

    # считаем сумму для бара
    to_bar = round(total_amount * 0.2, 2)

    # сохраняем в историю
    user["history"].append({
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": round(total_amount, 2)
    })

    user["current"] = 0
    save_data(users)

    await message.answer(
        f"Итог за смену: {round(total_amount, 2)} 🔥\n"
        f"Нужно отдать на бар: {to_bar} 🍹",
        reply_markup=keyboard_main
    )

@dp.message(lambda m: m.text == "📜 История")
async def history(message: types.Message):
    user = get_user(message.from_user.id)
    history = user["history"]
    if not history:
        await message.answer("История пустая", reply_markup=keyboard_main)
        return
    text = "📜 Последние смены:\n\n"
    for shift in history[-5:][::-1]:
        text += f"{shift['date']} — {shift['total']}\n"
    await message.answer(text, reply_markup=keyboard_main)

# --- запуск подтверждения очистки ---
@dp.message(lambda m: m.text == "🗑 Очистить историю")
async def start_clear_history(message: types.Message):
    user = get_user(message.from_user.id)
    user["await_clear_confirm"] = True
    save_data(users)
    await message.answer(
        "Вы уверены, что хотите очистить историю? ❌ Отмена / ✅ Подтвердить очистку",
        reply_markup=keyboard_confirm
    )

# --- обработка подтверждения или обычных сообщений ---
@dp.message(lambda m: True)
async def handle_confirmation_or_other(message: types.Message):
    user = get_user(message.from_user.id)

    # если ждём подтверждения очистки
    if user.get("await_clear_confirm", False):
        if message.text == "✅ Подтвердить очистку":
            user["history"] = []
            user["await_clear_confirm"] = False
            save_data(users)
            await message.answer("История смен очищена ✅", reply_markup=keyboard_main)
        elif message.text == "❌ Отмена":
            user["await_clear_confirm"] = False
            save_data(users)
            await message.answer("Очистка отменена ❌", reply_markup=keyboard_main)
        else:
            await message.answer("Пожалуйста, используйте кнопки подтверждения ✅ / ❌", reply_markup=keyboard_confirm)
        return

    # обработка обычных сообщений с суммами
    text = message.text or ""
    amount = extract_amount(text)
    if amount is None:
        try:
            amount = float(text.replace(" ", "").replace(",", "."))
        except:
            return
    net = amount / 1.25
    user["current"] += net
    save_data(users)
    await message.answer(
        f"💸 Чаевые: {amount}\n"
        f"+ {round(net, 2)}\n"
        f"Итого: {round(user['current'], 2)}",
        reply_markup=keyboard_main
    )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
