# ================================================================
# config.py — Главный конфиг. Всё что нужно менять — здесь.
# ================================================================

import os

# ---- Telegram ----
BOT_TOKEN    = os.getenv("BOT_TOKEN", "")
ADMIN_ID     = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID   = "@manicur1234"
CHANNEL_LINK = "https://t.me/manicur1234"
SCHEDULE_CHANNEL_ID = "@manicur1234"

# ---- База данных ----
DB_PATH = "manicure_bot.db"

# ---- Расписание ----
SLOT_DURATION = 30   # длительность одного слота в минутах




PORTFOLIO_LINK = "https://www.instagram.com/oy_brow_pmu/"
PORTFOLIO_BUTTON_TEXT = "📸 Смотреть в Instagram"
# ---- Студия ----
STUDIO_NAME    = "Oy_Brow_Pmu"
STUDIO_ADDRESS = "г. Островец, ул. Школьная, 1"
STUDIO_MAPS_LINK = "https://maps.app.goo.gl/p3zPtnXfMfPQ6MVR7"  # ссылка на карту

# ---- Услуги по умолчанию (загружаются в БД при первом запуске) ----
# Можно менять прямо через админ-панель — этот список нужен только для
# первичного заполнения БД.
DEFAULT_SERVICES = [
    {
        "key":          "brows",
        "name":         "Брови",
        "price":        35,
        "slots":        1,        # 1 × 30 мин = 30 мин
        "duration_str": "~30 мин",
        "emoji":        "✏️",
        "repeat_days":  21,       # напомнить через 3 недели
    },
    {
        "key":          "perm",
        "name":         "Перманентный макияж",
        "price":        200,
        "slots":        6,        # 6 × 30 мин = 3 часа
        "duration_str": "~3 часа",
        "emoji":        "💄",
        "repeat_days":  35,       # напомнить через 5 недель
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
