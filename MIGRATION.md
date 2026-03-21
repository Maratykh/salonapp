# Миграция с SQLite на PostgreSQL

## Быстрый старт (Railway)

### 1. Добавить PostgreSQL в Railway

В Railway → ваш проект → **+ New** → **Database** → **PostgreSQL**.
Railway автоматически добавит переменную `DATABASE_URL` в сервис бота.

### 2. Обновить код

```bash
git add .
git commit -m "migrate to postgresql"
git push
```

Railway пересоберёт контейнер. Бот сам создаст таблицы при первом запуске.

### 3. Перенести данные из SQLite (если нужно)

```bash
# Скачать старую базу с сервера
scp root@IP:/root/manicure_bot/manicure_bot.db ./manicure_bot.db

# Запустить скрипт миграции локально
DATABASE_URL="postgresql://..." python migrate_sqlite_to_pg.py
```

---

## VPS — пошаговая инструкция

### 1. Установить PostgreSQL

```bash
apt update && apt install -y postgresql postgresql-contrib
systemctl enable postgresql && systemctl start postgresql
```

### 2. Создать базу и пользователя

```bash
sudo -u postgres psql << 'SQL'
CREATE USER salonapp WITH PASSWORD 'ваш_пароль';
CREATE DATABASE salonapp OWNER salonapp;
GRANT ALL PRIVILEGES ON DATABASE salonapp TO salonapp;
SQL
```

### 3. Обновить переменные окружения

В `/etc/systemd/system/manicure_bot.service` добавить:

```ini
[Service]
Environment="DB_HOST=localhost"
Environment="DB_PORT=5432"
Environment="DB_NAME=salonapp"
Environment="DB_USER=salonapp"
Environment="DB_PASSWORD=ваш_пароль"
```

Или через `DATABASE_URL`:

```ini
Environment="DATABASE_URL=postgresql://salonapp:пароль@localhost:5432/salonapp"
```

### 4. Установить зависимости

```bash
cd /root/manicure_bot
source venv/bin/activate
pip install -r requirements.txt
```

### 5. Перенести данные из SQLite

```bash
cd /root/manicure_bot
source venv/bin/activate

# Указать переменные
export DATABASE_URL="postgresql://salonapp:пароль@localhost:5432/salonapp"
export DB_PATH="manicure_bot.db"

python migrate_sqlite_to_pg.py
```

### 6. Запустить бота

```bash
systemctl daemon-reload
systemctl restart manicure_bot
systemctl status manicure_bot
```

---

## Docker

```yaml
# docker-compose.yml
services:
  bot:
    build: .
    restart: always
    environment:
      - BOT_TOKEN=ваш_токен
      - ADMIN_IDS=ваш_id
      - DATABASE_URL=postgresql://salonapp:пароль@db:5432/salonapp
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:16-alpine
    restart: always
    environment:
      POSTGRES_DB: salonapp
      POSTGRES_USER: salonapp
      POSTGRES_PASSWORD: пароль
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U salonapp"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
```

```bash
docker compose up -d
```

---

## Alembic (управление миграциями)

```bash
# Применить все миграции
alembic upgrade head

# Откатить последнюю
alembic downgrade -1

# Статус
alembic current
```

---

## Как работает автоопределение бэкенда

`USE_POSTGRES = True` если задана хоть одна из переменных:
- `DATABASE_URL`
- `DB_HOST`  
- `DB_PASSWORD`

Иначе бот работает с SQLite как раньше — ничего менять не нужно.

---

## Бэкап PostgreSQL

```bash
# Создать дамп
pg_dump -U salonapp salonapp > backup_$(date +%F).sql

# Восстановить
psql -U salonapp salonapp < backup_2026-03-20.sql
```

Команда `/backup` в боте при PostgreSQL отправит SQL-дамп в Telegram-канал.
