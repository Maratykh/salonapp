# ================================================================
# config.py — Главный конфиг. Всё что нужно менять — здесь.
# ================================================================

import os

# ---- Telegram ----
BOT_TOKEN  = os.getenv("BOT_TOKEN", "")
_admin_ids = os.getenv("ADMIN_IDS", os.getenv("ADMIN_ID", "0"))
ADMIN_IDS  = [int(x.strip()) for x in _admin_ids.split(",") if x.strip()]
ADMIN_ID   = ADMIN_IDS[0] if ADMIN_IDS else 0

# ---- База данных ----
DB_PATH = os.getenv("DB_PATH", "data/manicure_bot.db")

# ---- Бэкап ----
BACKUP_CHANNEL_ID   = os.getenv("BACKUP_CHANNEL_ID", "")
BACKUP_HOUR         = int(os.getenv("BACKUP_HOUR", "3"))
SCHEDULE_CHANNEL_ID = os.getenv("SCHEDULE_CHANNEL_ID", "")

# ---- Демо-режим ----
DEMO_MODE    = os.getenv("DEMO_MODE", "False").lower() == "true"
DEMO_CONTACT = os.getenv("DEMO_CONTACT", "@ваш_username")

# ---- Согласие на обработку персональных данных ----
PRIVACY_POLICY_URL = os.getenv("PRIVACY_POLICY_URL", "https://docs.google.com/document/d/1gAaFWm72Jh-s-5TDS0zsH4tZvdw_c3bZ3wUFhyKRdfs/edit?usp=sharing")

# ---- Расписание ----
SLOT_DURATION = int(os.getenv("SLOT_DURATION", "15"))
TIMEZONE      = os.getenv("TIMEZONE", "Europe/Minsk")

# ---- Портфолио ----
PORTFOLIO_LINK        = os.getenv("PORTFOLIO_LINK", "https://www.instagram.com/oy_brow_pmu/")
PORTFOLIO_BUTTON_TEXT = os.getenv("PORTFOLIO_BUTTON_TEXT", "📸 Смотреть в Instagram")

# ---- Студия ----
STUDIO_NAME      = os.getenv("STUDIO_NAME",      "Oy_Brow_Pmu")
STUDIO_ADDRESS   = os.getenv("STUDIO_ADDRESS",   "г. Островец, ул. Школьная, 3 к1")
STUDIO_MAPS_LINK = os.getenv("STUDIO_MAPS_LINK", "https://maps.app.goo.gl/eNa2Mo9VSnmeKL626")

# ---- Услуги по умолчанию ----
DEFAULT_SERVICES = [
    {"key": "brows",           "name": "Брови",                          "price": 35,  "slots": 3,  "duration_str": "~45 мин",  "emoji": "✏️",  "repeat_days": 21},
    {"key": "brows_styling",   "name": "Долговременная укладка бровей",  "price": 45,  "slots": 4,  "duration_str": "~1 час",   "emoji": "✨",  "repeat_days": 30},
    {"key": "makeup",          "name": "Макияж",                         "price": 75,  "slots": 6,  "duration_str": "~1.5 часа","emoji": "💋",  "repeat_days": 0},
    {"key": "perm_2h",         "name": "Перманентный макияж (2 часа)",   "price": 200, "slots": 8,  "duration_str": "~2 часа",  "emoji": "💄",  "repeat_days": 30},
    {"key": "perm_3h",         "name": "Перманентный макияж (3 часа)",   "price": 200, "slots": 12, "duration_str": "~3 часа",  "emoji": "💄",  "repeat_days": 30},
    {"key": "perm_correction", "name": "Коррекция перманента",           "price": 100, "slots": 8,  "duration_str": "~2 часа",  "emoji": "🔧",  "repeat_days": 0},
]

# ---- Тексты сообщений ----
MSG_WELCOME = (
    "👋 Привет, <b>{name}</b>!\n\n"
    "Добро пожаловать в бот студии <b>{studio}</b>.\n"
    "Выберите действие:"
)
MSG_BOOKING_CREATED = (
    "✅ <b>Запись создана!</b>\n\n"
    "📅 {date}\n"
    "🕐 {time_start} – {time_end}\n"
    "{emoji} {service} — {price} руб.\n\n"
    "Ждём вас! 💄"
)
MSG_REMINDER_24H = (
    "⏰ <b>Напоминание о записи</b>\n\n"
    "Завтра в <b>{time}</b> вас ждём в студии <b>{studio}</b>.\n"
    "Адрес: {address}\n\n"
    "Ждём вас! 💄"
)
MSG_REPEAT_REMINDER = (
    "💅 Привет, <b>{name}</b>!\n\n"
    "Прошло {days} дней после вашего визита.\n"
    "Пора записаться на коррекцию <b>{service}</b>!\n\n"
    "Нажмите кнопку ниже чтобы записаться 👇"
)
MSG_MASTER_30MIN = (
    "⏰ <b>Через 30 минут</b> клиент:\n\n"
    "👤 {client}\n"
    "💄 {service}\n"
    "🕐 {time}"
)
MSG_ATTENDANCE_CHECK = (
    "❓ <b>Клиент пришёл?</b>\n\n"
    "👤 {client} — {service}\n"
    "🕐 {time}"
)
