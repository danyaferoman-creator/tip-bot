import asyncio
import re
import json
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

TOKEN = os.getenv("8752019740:AAE9vWg4RCC6QYUGaoy5TOvz6Res0_eX4Ns")

bot = Bot(token=TOKEN)
dp = Dispatcher()

DATA_FILE = "data.json"

# --- загрузка ---
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

# --- сохранение ---
def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

users = load_data()

# --- кнопки ---
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="▶️ Начать смену")],
        [KeyboardButton(text="📊 Итог"), KeyboardButton(text="📜 История")],
        [KeyboardButton(text="⛔ Закончить смену")]
    ],
    resize_keyboard=True
)

# --- парсер ---
def extract_amount(text):
    match = re.search(r"оставили\s+(\d+[.,]?\d*)\s*RUB", text)
    if match:
        return float(match.group(1).replace(",", "."))
    return None


def get_user(user_id):
    user_id = str(user_id)
    if user_id not in users:
        users[user_id] = {
            "current": 0,
            "history": []
        }
    return users[user_id]


@dp.message(commands=["start"])
async def start(message: types.Message):
    await message.answer("Готов считать чаевые 👌", reply_markup=keyboard)


@dp.message(lambda m: m.text == "▶️ Начать смену")
async def start_shift(message: types.Message):
    user = get_user(message.from_user.id)
    user["current"] = 0
    save_data(users)

    await message.answer("Смена началась 💸")


@dp.message(lambda m: m.text == "📊 Итог")
async def total(message: types.Message):
    user = get_user(message.from_user.id)
    await message.answer(f"Сейчас: {round(user['current'], 2)}")


@dp.message(lambda m: m.text == "⛔ Закончить смену")
async def end_shift(message: types.Message):
    user = get_user(message.from_user.id)

    total = user["current"]

    # сохраняем в историю
    user["history"].append({
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": round(total, 2)
    })

    user["current"] = 0
    save_data(users)

    await message.answer(f"Итог за смену: {round(total, 2)} 🔥")


@dp.message(lambda m: m.text == "📜 История")
async def history(message: types.Message):
    user = get_user(message.from_user.id)
    history = user["history"]

    if not history:
        await message.answer("История пустая")
        return

    text = "📜 Последние смены:\n\n"

    # последние 5 смен
    for shift in history[-5:][::-1]:
        text += f"{shift['date']} — {shift['total']}\n"

    await message.answer(text)


@dp.message()
async def handle_message(message: types.Message):
    text = message.text or ""

    amount = extract_amount(text)

    if amount is None:
        try:
            amount = float(text.replace(",", "."))
        except:
            return

    net = amount / 1.25

    user = get_user(message.from_user.id)
    user["current"] += net

    save_data(users)

    await message.answer(
        f"💸 Чаевые: {amount}\n"
        f"+ {round(net, 2)}\n"
        f"Итого: {round(user['current'], 2)}"
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
