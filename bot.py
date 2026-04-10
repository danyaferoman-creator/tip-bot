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

# --- загрузка ---
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
        [KeyboardButton(text="➕ Добавить к выручке"), KeyboardButton(text="🧹 Очистить выручку")],
        [KeyboardButton(text="⚙️ Профиль")],
        [KeyboardButton(text="🗑 Очистить историю")]
    ],
    resize_keyboard=True
)

keyboard_shift_type = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🌞 Дневной"), KeyboardButton(text="🌙 Ночной")],
        [KeyboardButton(text="⬅️ Назад")]
    ],
    resize_keyboard=True
)

keyboard_confirm = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Подтвердить очистку"), KeyboardButton(text="❌ Отмена")]
    ],
    resize_keyboard=True
)

# --- парсер ---
def extract_amount(text):
    match = re.search(r"оставили\s+([\d\s]+[.,]?\d*)\s*RUB", text)
    if match:
        return float(match.group(1).replace(" ", "").replace(",", "."))
    return None

# --- проценты ---
def get_percent(revenue, shift_type="day"):
    if shift_type == "night":
        if revenue < 200000: return 2.04, 200000
        elif revenue < 300000: return 2.24, 300000
        elif revenue < 400000: return 2.64, 400000
        elif revenue < 600000: return 2.84, 600000
        elif revenue < 800000: return 3.00, 800000
        elif revenue < 1000000: return 3.24, 1000000
        elif revenue < 1300000: return 3.60, 1300000
        else: return 4.20, None
    else:
        if revenue < 200000: return 1.70, 200000
        elif revenue < 300000: return 2.00, 300000
        elif revenue < 400000: return 2.20, 400000
        elif revenue < 600000: return 2.30, 600000
        elif revenue < 800000: return 2.50, 800000
        elif revenue < 1000000: return 2.70, 1000000
        elif revenue < 1300000: return 3.00, 1300000
        else: return 3.50, None

# --- месяц ---
def check_month(user):
    current_month = datetime.now().strftime("%Y-%m")
    if user.get("last_update") != current_month:
        user["month_revenue"] = 0
        user["last_update"] = current_month

# --- пользователь ---
def get_user(user_id):
    user_id = str(user_id)

    if user_id not in users:
        users[user_id] = {}

    user = users[user_id]

    user.setdefault("current", 0)
    user.setdefault("history", [])
    user.setdefault("await_clear_confirm", False)
    user.setdefault("await_add_revenue", False)
    user.setdefault("await_revenue", False)
    user.setdefault("month_revenue", 0)
    user.setdefault("last_update", datetime.now().strftime("%Y-%m"))
    user.setdefault("shift_type", "day")

    return user

# --- профиль ---
@dp.message(lambda m: m.text == "⚙️ Профиль")
async def profile(message: types.Message):
    user = get_user(message.from_user.id)
    shift = "🌞 Дневной" if user["shift_type"] == "day" else "🌙 Ночной"

    await message.answer(
        f"⚙️ Профиль\n\nТекущий тип: {shift}",
        reply_markup=keyboard_shift_type
    )

@dp.message(lambda m: m.text in ["🌞 Дневной", "🌙 Ночной"])
async def set_shift_type(message: types.Message):
    user = get_user(message.from_user.id)

    user["shift_type"] = "day" if message.text == "🌞 Дневной" else "night"
    save_data(users)

    await message.answer("Тип смены сохранен ✅", reply_markup=keyboard_main)

@dp.message(lambda m: m.text == "⬅️ Назад")
async def back(message: types.Message):
    await message.answer("Главное меню", reply_markup=keyboard_main)

# --- команды ---
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

# --- история ---
@dp.message(lambda m: m.text == "📜 История")
async def history(message: types.Message):
    user = get_user(message.from_user.id)

    if not user["history"]:
        await message.answer("История пустая", reply_markup=keyboard_main)
        return

    text = "📜 Последние смены:\n\n"
    for shift in user["history"][-5:][::-1]:
        date = shift.get("date", "неизвестно")
        tips = shift.get("tips", shift.get("total", 0))
        revenue = shift.get("revenue", 0)

        text += f"{date} — Чаевые: {tips}, Выручка: {revenue}\n"

    await message.answer(text, reply_markup=keyboard_main)

# --- месяц ---
@dp.message(lambda m: m.text == "📈 Месяц")
async def month_stats(message: types.Message):
    user = get_user(message.from_user.id)
    check_month(user)

    revenue = user["month_revenue"]
    percent, next_target = get_percent(revenue, user["shift_type"])
    salary = revenue * percent / 100

    shift = "🌞 День" if user["shift_type"] == "day" else "🌙 Ночь"

    text = (
        f"📅 Текущий месяц ({shift}):\n\n"
        f"💰 Выручка: {round(revenue,2)}\n"
        f"📊 Процент: {percent}%\n"
        f"💸 Бонус: {round(salary,2)}\n"
    )

    if next_target:
        text += f"\n📈 До следующего уровня: {round(next_target - revenue,2)}"

    await message.answer(text, reply_markup=keyboard_main)

# --- завершение смены ---
@dp.message(lambda m: m.text == "⛔ Закончить смену")
async def end_shift(message: types.Message):
    user = get_user(message.from_user.id)

    user["await_revenue"] = True
    user["temp_total"] = user["current"]

    await message.answer("Введите выручку за смену 💰")

# --- добавить к выручке ---
@dp.message(lambda m: m.text == "➕ Добавить к выручке")
async def add_revenue_start(message: types.Message):
    user = get_user(message.from_user.id)
    user["await_add_revenue"] = True
    save_data(users)

    await message.answer("Введите сумму для добавления 💰")

# --- очистить выручку ---
@dp.message(lambda m: m.text == "🧹 Очистить выручку")
async def clear_revenue(message: types.Message):
    user = get_user(message.from_user.id)
    user["month_revenue"] = 0
    save_data(users)

    await message.answer("Выручка очищена ✅", reply_markup=keyboard_main)

# --- очистка истории ---
@dp.message(lambda m: m.text == "🗑 Очистить историю")
async def clear_history_start(message: types.Message):
    user = get_user(message.from_user.id)
    user["await_clear_confirm"] = True
    save_data(users)

    await message.answer("Подтвердите очистку", reply_markup=keyboard_confirm)

# --- основной обработчик ---
@dp.message(lambda m: True)
async def handle_text(message: types.Message):
    user = get_user(message.from_user.id)

    # --- добавление к выручке ---
    if user.get("await_add_revenue"):
        try:
            amount = float(message.text.replace(" ", "").replace(",", "."))
        except:
            await message.answer("Введите число")
            return

        check_month(user)
        user["month_revenue"] += amount
        user["await_add_revenue"] = False
        save_data(users)

        await message.answer(f"Добавлено {amount} 💰", reply_markup=keyboard_main)
        return

    # --- подтверждение очистки ---
    if user.get("await_clear_confirm"):
        if message.text == "✅ Подтвердить очистку":
            user["history"] = []
            user["await_clear_confirm"] = False
            save_data(users)
            await message.answer("История очищена ✅", reply_markup=keyboard_main)
        else:
            user["await_clear_confirm"] = False
            save_data(users)
            await message.answer("Отменено ❌", reply_markup=keyboard_main)
        return

    # --- ввод выручки ---
    if user.get("await_revenue"):
        try:
            revenue = float(message.text.replace(" ", "").replace(",", "."))
        except:
            await message.answer("Введите число")
            return

        check_month(user)
        user["month_revenue"] += revenue

        total_amount = user.get("temp_total", 0)
        to_bar = round(total_amount * 0.2, 2)

        # сохраняем в историю
        user["history"].append({
            "date": datetime.now().strftime("%d.%m.%y"),
            "tips": round(total_amount, 2),
            "revenue": revenue
        })

        user["current"] = 0
        user["await_revenue"] = False
        save_data(users)

        await message.answer(
            f"🔥 Итог за смену: {round(total_amount, 2)}\n"
            f"🍹 На бар: {to_bar}\n\n"
            f"💰 Выручка: {revenue}",
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
        f"💸 Чаевые: {amount}\n+ {round(net,2)}\nИтого: {round(user['current'],2)}",
        reply_markup=keyboard_main
    )

# --- запуск ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
