# 💅 SalonApp — Telegram-бот для записи клиентов

Универсальный бот для мастеров которые работают по записи: маникюр, барбер, массаж, косметология, фотографы, репетиторы и другие.

---

## ⚙️ Функционал

### Клиент
- 📅 Запись через инлайн-календарь — дата → услуга → время → имя → телефон
- 📋 Просмотр и отмена своей записи (с подтверждением)
- 💅 Прайс-лист услуг
- 🖼 Портфолио
- 📍 Как добраться
- 🔔 Автонапоминание за 24 часа до визита

### Мастер (`/admin`)
- 📅 Просмотр расписания на любую дату с пагинацией
- ➕ Добавить рабочий день — выбор начала и конца через тайм-пикер
- 🗓 Добавить рабочие дни по дням недели сразу на месяц вперёд
- 📝 Записать клиента вручную
- ⏰ Управление слотами — удаление отдельных окон
- 🔒 Закрыть / 🔓 Открыть день
- ❌ Отмена любой записи из расписания
- 💄 Управление услугами — добавить, редактировать, включить/отключить
- 📊 Статистика — за месяц и за всё время, выручка, явка, популярные услуги
- 📣 Рассылка всем клиентам
- ✅ Отметка явки клиента

### Автоматически
- ⏰ Напоминание клиенту за 24 часа
- ⏰ Уведомление мастеру за 30 минут до визита
- 🔁 Напоминание о коррекции через N дней после услуги
- ❓ Запрос явки мастеру после окончания приёма
- 📢 Обновление расписания в канале (редактирует одно сообщение)

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
ADMIN_ID         = 123456789
STUDIO_NAME      = "Название студии"
STUDIO_ADDRESS   = "Город, улица, дом"
STUDIO_MAPS_LINK = "ссылка на карту"
PORTFOLIO_LINK   = "ссылка на портфолио"
SCHEDULE_CHANNEL_ID = "@ваш_канал"  # опционально
```

### 5. Запуск
```bash
python bot.py
```

---

## 🚀 Деплой на VPS

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
├── bot.py
├── config.py
├── database/
│   └── db.py
├── handlers/
│   ├── common.py
│   ├── user.py
│   └── admin.py
├── keyboards/
│   ├── user_kb.py
│   └── admin_kb.py
├── states/
│   └── states.py
├── utils/
│   ├── calendar_kb.py
│   ├── admin_calendar.py
│   └── scheduler.py
└── middlewares/
```

---

## 📦 Зависимости

```
aiogram==3.13.1
aiosqlite==0.20.0
APScheduler==3.10.4
```

---

## 🔐 Безопасность

Не публикуйте токен в открытом репозитории. Используйте переменные окружения:
```python
import os
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID  = int(os.getenv("ADMIN_ID", "0"))
```

---

## 📝 Лицензия

MIT — свободное использование и модификация.
