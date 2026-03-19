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
- 📅 Просмотр расписания на любую дату с пагинацией
- ➕ Добавить рабочий день — выбор начала и конца через тайм-пикер с правильным шагом
- 🗓 Добавить рабочие дни по дням недели сразу на месяц вперёд (со счётчиком новых и существующих)
- 📝 Записать клиента вручную — дата → услуга → время (с фильтром по длительности) → имя
- 📅 Перенос записи на другую дату и время с уведомлением клиента
- ⏰ Управление слотами — удаление отдельных окон
- 🔒 Закрыть день — клиенты с записями получают уведомление об отмене
- 🔓 Открыть день
- ❌ Отмена любой записи из расписания
- 💄 Управление услугами — добавить, редактировать, включить/отключить
- 📊 Статистика — за месяц и за всё время, выручка, явка, популярные услуги
- 📣 Рассылка всем клиентам с защитой от rate limit и повтором при ошибке
- ✅ Отметка явки клиента
- 🧲 Плотное расписание — клиенты видят только слоты вплотную к существующим записям (в обе стороны)
- 🗄 Бэкап БД — `/backup` отправляет файл базы мастеру, ежедневный автобэкап в канал

### Автоматически
- ⏰ Напоминание клиенту за 24 часа
- ⏰ Уведомление мастеру за 30 минут до визита
- 🔁 Напоминание о коррекции через N дней после услуги
- ❓ Запрос явки мастеру после окончания приёма
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
ADMIN_IDS        = [123456789]            # список ID админов, можно несколько
STUDIO_NAME      = "Название студии"
STUDIO_ADDRESS   = "Город, улица, дом"
STUDIO_MAPS_LINK = "ссылка на карту"
PORTFOLIO_LINK   = "ссылка на портфолио"
TIMEZONE         = "Europe/Minsk"         # таймзона мастера
SLOT_DURATION    = 15                     # длительность слота в минутах
BACKUP_CHANNEL_ID = "@ваш_канал"          # канал для ежедневных бэкапов (опционально)
BACKUP_HOUR      = 3                      # час отправки бэкапа
```

**Таймзоны:** `Europe/Minsk`, `Europe/Moscow`, `Europe/Kiev`, `Asia/Almaty`

**Несколько админов** через переменную окружения:
```
ADMIN_IDS=123456789,987654321
```

### 5. Запуск
```bash
python bot.py
```

---

## 🎭 Демо-режим

Для показа бота потенциальным клиентам — включите демо-режим:
```python
DEMO_MODE    = True
DEMO_CONTACT = "@ваш_username"
```
Или через переменные окружения на Railway:
```
DEMO_MODE=True
DEMO_CONTACT=@ваш_username
```
В демо-режиме клиент проходит весь флоу записи, но вместо реальной записи видит что было бы создано и кнопку "Хочу такого бота".

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
Environment="BOT_TOKEN=ваш_токен"
Environment="ADMIN_IDS=ваш_id"

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
cd /root && unzip -o manicure_bot.zip -d manicure_bot
systemctl restart manicure_bot
```

---

## 🗄 Бэкап базы данных

**Ручной бэкап** — напишите боту `/backup`, получите файл БД прямо в чат.

**Автобэкап в канал:**
1. Создайте приватный канал в Telegram
2. Добавьте бота в канал как администратора
3. Укажите `BACKUP_CHANNEL_ID = "@канал"` в config.py или переменных окружения
4. Каждый день в `BACKUP_HOUR` бот отправит файл БД в канал

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
│   └── scheduler.py           # APScheduler напоминания и бэкапы
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

- Не публикуйте токен в открытом репозитории
- Используйте переменные окружения для токена и ID
- Ограничьте права на файл базы данных:
```bash
chmod 600 manicure_bot.db
```
- Регулярно скачивайте бэкапы БД к себе:
```bash
scp root@IP:/root/manicure_bot/manicure_bot.db ./backup.db
```

---

## 📝 Лицензия

MIT — свободное использование и модификация.
