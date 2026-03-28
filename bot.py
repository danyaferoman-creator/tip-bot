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
        [KeyboardButton(text="⛔ Закончить смену"), KeyboardButton(text="📈 Месяц")],
        [KeyboardButton(text="🗑 Очистить историю")]
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

# --- проценты ---
def get_percent(revenue):
    if revenue < 200000:
        return 1.70, 200000
    elif revenue < 300000:
        return 2.00, 300000
    elif revenue < 400000:
        return 2.20, 400000
    elif revenue < 600000:
        return 2.30, 600000
    elif revenue < 800000:
        return 2.50, 800000
    elif revenue < 1000000:
        return 2.70, 1000000
    elif revenue < 1300000:
        return 3.00, 1300000
    else:
        return 3.50, None

# --- месяц ---
def check_month(user):
    current_month = datetime.now().strftime("%Y-%m")
    if user.get("last_update") != current_month:
        user["month_revenue"] = 0
        user["last_update"] = current_month

def get_user(user_id):
    user_id = str(user_id)
    if user_id not in users:
        users[user_id] = {
            "current": 0,
            "history": [],
            "await_clear_confirm": False,
            "month_revenue": 0,
            "last_update": datetime.now().strftime("%Y-%m")
        }
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

# --- обновили завершение смены ---
@dp.message(lambda m: m.text == "⛔ Закончить смену")
async def end_shift(message: types.Message):
    user = get_user(message.from_user.id)
    total_amount = user["current"]

    to_bar = round(total_amount * 0.2, 2)

    # просим ввести выручку
    user["await_revenue"] = True
    user["temp_total"] = total_amount
    user["temp_bar"] = to_bar
    save_data(users)

    await message.answer("Введите выручку за смену 💰")

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

# --- месяц ---
@dp.message(lambda m: m.text == "📈 Месяц")
async def month_stats(message: types.Message):
    user = get_user(message.from_user.id)

    check_month(user)

    revenue = user["month_revenue"]
    percent, next_target = get_percent(revenue)
    salary = revenue * percent / 100

    text = (
        f"📅 Текущий месяц:\n\n"
        f"💰 Выручка: {round(revenue, 2)}\n"
        f"📊 Процент: {percent}%\n"
        f"💸 Бонус: {round(salary, 2)}\n"
    )

    if next_target:
        remaining = next_target - revenue
        text += f"\n📈 До следующего уровня: {round(remaining, 2)}"

    await message.answer(text, reply_markup=keyboard_main)

# --- очистка истории ---
@dp.message(lambda m: m.text == "🗑 Очистить историю")
async def start_clear_history(message: types.Message):
    user = get_user(message.from_user.id)
    user["await_clear_confirm"] = True
    save_data(users)
    await message.answer(
        "Вы уверены, что хотите очистить историю? ❌ Отмена / ✅ Подтвердить очистку",
        reply_markup=keyboard_confirm
    )

# --- основной обработчик ---
@dp.message(lambda m: True)
async def handle_confirmation_or_other(message: types.Message):
    user = get_user(message.from_user.id)

    # --- подтверждение очистки ---
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
            await message.answer("Используйте кнопки ✅ / ❌", reply_markup=keyboard_confirm)
        return

    # --- ввод выручки ---
    if user.get("await_revenue", False):
        try:
            revenue = float(message.text.replace(" ", "").replace(",", "."))
        except:
            await message.answer("Введите корректную сумму")
            return

        check_month(user)
        user["month_revenue"] += revenue

        # сохраняем смену
        user["history"].append({
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "total": round(user["temp_total"], 2)
        })

        total_amount = user["temp_total"]
        to_bar = user["temp_bar"]

        user["current"] = 0
        user["await_revenue"] = False

        save_data(users)

        await message.answer(
            f"Итог за смену: {round(total_amount, 2)} 🔥\n"
            f"🍹 На бар: {to_bar}\n\n"
            f"💰 Выручка добавлена: {revenue}",
            reply_markup=keyboard_main
        )
        return

    # --- чаевые ---
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
