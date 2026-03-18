# 💅 SalonApp — Telegram-бот для записи клиентов

Универсальный бот для мастеров которые работают по записи: маникюр, барбер, массаж, косметология, фотографы, репетиторы и другие.

---

## ⚙️ Функционал

### Клиент
- 📅 Запись через инлайн-календарь — дата → услуга → время → имя → телефон
- 📋 Просмотр своей записи и отмена с подтверждением
- 💅 Прайс-лист услуг
- 🖼 Портфолио
- 📍 Как добраться
- 🔔 Автонапоминание за 24 часа до визита

### Мастер (`/admin`)
- 📅 Просмотр расписания на любую дату с пагинацией (по 5 записей)
- ➕ Добавить рабочий день — выбор начала и конца через тайм-пикер
- 🗓 Добавить рабочие дни по дням недели сразу на месяц вперёд
- 📝 Записать клиента вручную — дата → услуга → время (с фильтром) → имя
- 📅 Перенос записи на другую дату и время
- ⏰ Управление слотами — удаление отдельных окон
- 🔒 Закрыть день (клиенты получают уведомление об отмене)
- 🔓 Открыть день
- ❌ Отмена любой записи из расписания
- 💄 Управление услугами — добавить, редактировать, включить/отключить
- 📊 Статистика — за месяц и за всё время, выручка, явка, популярные услуги
- 📣 Рассылка всем клиентам (с защитой от rate limit)
- ✅ Отметка явки клиента
- 🧲 Плотное расписание — клиенты видят только слоты вплотную к существующим записям (в обе стороны)

### Автоматически
- ⏰ Напоминание клиенту за 24 часа
- ⏰ Уведомление мастеру за 30 минут до визита
- 🔁 Напоминание о коррекции через N дней после услуги
- ❓ Запрос явки мастеру после окончания приёма
- 📢 Обновление расписания в канале (редактирует одно сообщение, не засоряет канал)
- 🔄 Восстановление всех напоминаний после перезапуска бота

---

## 🛠 Установка

### 1. Требования
- Python 3.11+
- Ubuntu 22.04 (для сервера)

### 2. Распаковать архив
```bash
unzip manicure_bot.zip -d manicure_bot
cd manicure_bot
```

### 3. Виртуальное окружение
```bash
python3.11 -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows
pip install -r requirements.txt
```

### 4. Настроить config.py
```python
BOT_TOKEN        = "токен от @BotFather"
ADMIN_IDS        = [123456789]           # список ID админов (можно несколько)
STUDIO_NAME      = "Название студии"
STUDIO_ADDRESS   = "Город, улица, дом"
STUDIO_MAPS_LINK = "ссылка на карту"
PORTFOLIO_LINK   = "ссылка на портфолио"
TIMEZONE         = "Europe/Minsk"        # таймзона мастера
SCHEDULE_CHANNEL_ID = "@ваш_канал"      # канал для расписания (опционально)
SLOT_DURATION    = 15                    # длительность слота в минутах
```

**Таймзоны:** `Europe/Minsk`, `Europe/Moscow`, `Europe/Kiev`, `Asia/Almaty`

**Несколько админов** — добавьте через запятую в переменную окружения:
```
ADMIN_IDS=123456789,987654321
```

### 5. Запуск
```bash
python bot.py
```

---

## 🚀 Деплой на VPS

### Загрузить файлы на сервер
```bash
scp manicure_bot.zip root@ВАШ_IP:/root/
ssh root@ВАШ_IP
unzip manicure_bot.zip -d manicure_bot
cd manicure_bot
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Автозапуск через systemd
```bash
nano /etc/systemd/system/manicure_bot.service
```
```ini
[Unit]
Description=Manicure Bot
After=network.target

[Service]
User=root
WorkingDirectory=/root/manicure_bot
ExecStart=/root/manicure_bot/venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
```bash
systemctl daemon-reload
systemctl enable manicure_bot
systemctl start manicure_bot
```

### Полезные команды
```bash
systemctl status manicure_bot      # статус
systemctl restart manicure_bot     # перезапуск
journalctl -u manicure_bot -f      # логи в реальном времени
```

### Обновление бота
```bash
scp manicure_bot.zip root@IP:/root/
ssh root@IP
unzip -o manicure_bot.zip -d manicure_bot
systemctl restart manicure_bot
```

---

## 📁 Структура проекта

```
manicure_bot/
├── bot.py                     # точка входа
├── config.py                  # токен, ID, тексты, услуги, таймзона
├── database/
│   └── db.py                  # все операции с SQLite
├── handlers/
│   ├── common.py              # /start, прайсы, портфолио
│   ├── user.py                # запись, отмена
│   └── admin.py               # панель администратора
├── keyboards/
│   ├── user_kb.py             # кнопки для клиентов
│   └── admin_kb.py            # кнопки для мастера
├── states/
│   └── states.py              # FSM-состояния
├── utils/
│   ├── calendar_kb.py         # инлайн-календарь (клиент)
│   ├── admin_calendar.py      # инлайн-календарь (админ)
│   └── scheduler.py           # APScheduler напоминания
└── middlewares/               # зарезервировано
```

---

## 📦 Зависимости

```
aiogram==3.13.1
aiosqlite==0.20.0
APScheduler==3.10.4
pytz==2024.1
```

---

## 🔐 Безопасность

Не публикуйте токен в открытом репозитории. Используйте переменные окружения:
```python
import os
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "0").split(",")]
```

Ограничьте права на файл базы данных:
```bash
chmod 600 manicure_bot.db
```

---

## 📝 Лицензия

MIT — свободное использование и модификация.
