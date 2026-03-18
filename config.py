# ================================================================
# config.py — Главный конфиг. Всё что нужно менять — здесь.
# ================================================================

import os

# ---- Telegram ----
BOT_TOKEN  = os.getenv("BOT_TOKEN", "")
# Несколько админов через запятую: "123456,789012"
_admin_ids = os.getenv("ADMIN_IDS", os.getenv("ADMIN_ID", "0"))
ADMIN_IDS  = [int(x.strip()) for x in _admin_ids.split(",") if x.strip()]
ADMIN_ID   = ADMIN_IDS[0] if ADMIN_IDS else 0  # первый — главный (для обратной совместимости)
CHANNEL_ID   = "@manicur1234"
CHANNEL_LINK = "https://t.me/manicur1234"
SCHEDULE_CHANNEL_ID = "@manicur1234"

# ---- База данных ----
DB_PATH = "manicure_bot.db"

# ---- Демо-режим ----
DEMO_MODE    = os.getenv("DEMO_MODE", "False").lower() == "true"
DEMO_CONTACT = os.getenv("DEMO_CONTACT", "@ваш_username")
SLOT_DURATION = 15   # длительность одного слота в минутах
TIMEZONE      = "Europe/Minsk"  # таймзона мастера (Europe/Moscow, Europe/Minsk, Asia/Almaty и т.д.)

# ---- Портфолио ----
PORTFOLIO_LINK = "https://www.instagram.com/oy_brow_pmu/"
PORTFOLIO_BUTTON_TEXT = "📸 Смотреть в Instagram"

# ---- Студия ----
STUDIO_NAME      = "Oy_Brow_Pmu"
STUDIO_ADDRESS   = "г. Островец, ул. Школьная, 3 к1"
STUDIO_MAPS_LINK = "https://maps.app.goo.gl/eNa2Mo9VSnmeKL626"

# ---- Услуги по умолчанию (загружаются в БД при первом запуске) ----
DEFAULT_SERVICES = [
    {
        "key":          "brows",
        "name":         "Брови",
        "price":        35,
        "slots":        3,        # 3 × 15 мин = 45 мин
        "duration_str": "~45 мин",
        "emoji":        "✏️",
        "repeat_days":  21,
    },
    {
        "key":          "brows_styling",
        "name":         "Долговременная укладка бровей",
        "price":        45,
        "slots":        4,        # 4 × 15 мин = 1 час
        "duration_str": "~1 час",
        "emoji":        "✨",
        "repeat_days":  30,
    },
    {
        "key":          "makeup",
        "name":         "Макияж",
        "price":        75,
        "slots":        6,        # 6 × 15 мин = 1.5 часа
        "duration_str": "~1.5 часа",
        "emoji":        "💋",
        "repeat_days":  0,
    },
    {
        "key":          "perm_2h",
        "name":         "Перманентный макияж (2 часа)",
        "price":        200,
        "slots":        8,        # 8 × 15 мин = 2 часа
        "duration_str": "~2 часа",
        "emoji":        "💄",
        "repeat_days":  30,
    },
    {
        "key":          "perm_3h",
        "name":         "Перманентный макияж (3 часа)",
        "price":        200,
        "slots":        12,       # 12 × 15 мин = 3 часа
        "duration_str": "~3 часа",
        "emoji":        "💄",
        "repeat_days":  30,
    },
    {
        "key":          "perm_correction",
        "name":         "Коррекция перманента",
        "price":        100,
        "slots":        8,        # 8 × 15 мин = 2 часа
        "duration_str": "~2 часа",
        "emoji":        "🔧",
        "repeat_days":  0,
    },
]

# ---- Тексты сообщений (можно менять) ----
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
