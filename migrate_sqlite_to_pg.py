#!/usr/bin/env python3
"""
migrate_sqlite_to_pg.py — Переносит данные из SQLite в PostgreSQL.

Использование:
    python migrate_sqlite_to_pg.py

Переменные окружения должны быть заданы:
    DATABASE_URL или DB_HOST, DB_NAME, DB_USER, DB_PASSWORD
    DB_PATH — путь к SQLite файлу (по умолчанию: manicure_bot.db)
"""

import asyncio
import os
import sys


async def migrate():
    import sqlite3
    import asyncpg

    sqlite_path = os.getenv("DB_PATH", "manicure_bot.db")
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5432")
        name = os.getenv("DB_NAME", "salonapp")
        user = os.getenv("DB_USER", "postgres")
        pw   = os.getenv("DB_PASSWORD", "")
        database_url = f"postgresql://{user}:{pw}@{host}:{port}/{name}"

    if not os.path.exists(sqlite_path):
        print(f"❌ SQLite файл не найден: {sqlite_path}")
        sys.exit(1)

    print(f"📂 SQLite: {sqlite_path}")
    print(f"🐘 PostgreSQL: {database_url.split('@')[-1]}")
    print()

    sl = sqlite3.connect(sqlite_path)
    sl.row_factory = sqlite3.Row
    pg = await asyncpg.connect(database_url)

    tables = ["schedule", "appointments", "services", "settings", "blacklist"]

    for table in tables:
        try:
            rows = sl.execute(f"SELECT * FROM {table}").fetchall()
        except Exception as e:
            print(f"⚠️  {table}: пропущена ({e})")
            continue

        if not rows:
            print(f"  {table}: пусто, пропускаем")
            continue

        cols = list(rows[0].keys())
        count = 0
        errors = 0

        for row in rows:
            values = [row[c] for c in cols]
            placeholders = ", ".join(f"${i+1}" for i in range(len(cols)))
            col_list = ", ".join(cols)
            sql = (f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
                   f"ON CONFLICT DO NOTHING")
            try:
                await pg.execute(sql, *values)
                count += 1
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"    ⚠️  ошибка строки: {e}")

        status = "✅" if errors == 0 else "⚠️ "
        print(f"  {status} {table}: перенесено {count}/{len(rows)}"
              + (f", ошибок {errors}" if errors else ""))

    # Сбрасываем sequences в PostgreSQL после вставки данных
    for table in ["schedule", "appointments", "services"]:
        try:
            await pg.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                f"COALESCE(MAX(id), 1)) FROM {table}"
            )
        except Exception:
            pass

    sl.close()
    await pg.close()
    print()
    print("✅ Миграция завершена!")


if __name__ == "__main__":
    asyncio.run(migrate())
