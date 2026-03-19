# database/db.py

import aiosqlite
from config import DB_PATH, SLOT_DURATION, DEFAULT_SERVICES, TIMEZONE
from datetime import datetime
import pytz


def _now_local() -> str:
    """Текущее время в таймзоне мастера в формате для SQLite."""
    tz = pytz.timezone(TIMEZONE)
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")


def _today_local() -> str:
    """Сегодняшняя дата в таймзоне мастера."""
    tz = pytz.timezone(TIMEZONE)
    return datetime.now(tz).strftime("%Y-%m-%d")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:

        # Расписание
        await db.execute("""
            CREATE TABLE IF NOT EXISTS schedule (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                date      TEXT NOT NULL,
                time_slot TEXT NOT NULL,
                is_booked INTEGER DEFAULT 0,
                is_closed INTEGER DEFAULT 0,
                UNIQUE(date, time_slot)
            )
        """)

        # Записи клиентов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id          INTEGER NOT NULL,
                username         TEXT,
                client_name      TEXT NOT NULL,
                phone            TEXT NOT NULL DEFAULT '—',
                date             TEXT NOT NULL,
                time_slot        TEXT NOT NULL,
                service_key      TEXT DEFAULT '',
                service_name     TEXT DEFAULT '',
                service_price    INTEGER DEFAULT 0,
                slots_count      INTEGER DEFAULT 1,
                attended         INTEGER DEFAULT NULL,  -- NULL=не отмечено, 1=пришёл, 0=не пришёл
                created_at       TEXT DEFAULT (datetime('now','localtime')),
                reminder_job_id  TEXT,
                repeat_job_id    TEXT,
                master_job_id    TEXT
            )
        """)

        # Услуги (управляются через админку)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                key          TEXT UNIQUE NOT NULL,
                name         TEXT NOT NULL,
                price        INTEGER NOT NULL DEFAULT 0,
                slots        INTEGER NOT NULL DEFAULT 1,
                duration_str TEXT DEFAULT '',
                emoji        TEXT DEFAULT '💅',
                repeat_days  INTEGER DEFAULT 0,    -- 0 = отключено
                is_active    INTEGER DEFAULT 1
            )
        """)

        # Настройки бота
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # Чёрный список
        await db.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                user_id    INTEGER PRIMARY KEY,
                username   TEXT,
                client_name TEXT,
                reason     TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )
        """)

        # Миграции для старых БД
        for col, definition in [
            ("phone",         "TEXT NOT NULL DEFAULT '—'"),
            ("attended",      "INTEGER DEFAULT NULL"),
            ("repeat_job_id", "TEXT"),
            ("master_job_id", "TEXT"),
        ]:
            try:
                await db.execute(f"ALTER TABLE appointments ADD COLUMN {col} {definition}")
            except Exception:
                pass

        await db.commit()

    # Заполнить услуги по умолчанию если таблица пустая
    await seed_services()
    # Заполнить настройки по умолчанию
    await seed_settings()


async def seed_services():
    """Добавить услуги по умолчанию если их ещё нет."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM services")
        count = (await cur.fetchone())[0]
        if count == 0:
            for svc in DEFAULT_SERVICES:
                await db.execute("""
                    INSERT OR IGNORE INTO services
                    (key, name, price, slots, duration_str, emoji, repeat_days)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (svc["key"], svc["name"], svc["price"], svc["slots"],
                      svc["duration_str"], svc["emoji"], svc.get("repeat_days", 0)))
            await db.commit()


async def seed_settings():
    """Установить настройки по умолчанию."""
    defaults = {
        "repeat_reminders_enabled": "1",
        "master_30min_enabled":     "1",
        "dense_schedule":           "0",
        "loyalty_enabled":          "0",   # программа лояльности выкл
        "loyalty_visits":           "3",   # скидка после N визитов
        "loyalty_discount":         "10",  # скидка %
    }
    async with aiosqlite.connect(DB_PATH) as db:
        for key, value in defaults.items():
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value)
            )
        await db.commit()


# ------------------------------------------------------------------
# Настройки
# ------------------------------------------------------------------

async def get_setting(key: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = await cur.fetchone()
    return row[0] if row else "0"


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )
        await db.commit()


# ------------------------------------------------------------------
# Услуги
# ------------------------------------------------------------------

async def get_services(active_only: bool = True) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        q = "SELECT id, key, name, price, slots, duration_str, emoji, repeat_days, is_active FROM services"
        if active_only:
            q += " WHERE is_active=1"
        q += " ORDER BY id"
        cur = await db.execute(q)
        rows = await cur.fetchall()
    return [
        {"id": r[0], "key": r[1], "name": r[2], "price": r[3],
         "slots": r[4], "duration_str": r[5], "emoji": r[6],
         "repeat_days": r[7], "is_active": bool(r[8])}
        for r in rows
    ]


async def get_service_by_key(key: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, key, name, price, slots, duration_str, emoji, repeat_days, is_active "
            "FROM services WHERE key=?", (key,)
        )
        row = await cur.fetchone()
    if not row:
        return None
    return {"id": row[0], "key": row[1], "name": row[2], "price": row[3],
            "slots": row[4], "duration_str": row[5], "emoji": row[6],
            "repeat_days": row[7], "is_active": bool(row[8])}


async def add_service(key: str, name: str, price: int, slots: int,
                      duration_str: str, emoji: str, repeat_days: int) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO services (key, name, price, slots, duration_str, emoji, repeat_days) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (key, name, price, slots, duration_str, emoji, repeat_days)
            )
            await db.commit()
        return True
    except Exception:
        return False


async def update_service(svc_id: int, name: str, price: int, slots: int,
                         duration_str: str, emoji: str, repeat_days: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE services SET name=?, price=?, slots=?, duration_str=?, "
            "emoji=?, repeat_days=? WHERE id=?",
            (name, price, slots, duration_str, emoji, repeat_days, svc_id)
        )
        await db.commit()


async def toggle_service(svc_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE services SET is_active = CASE WHEN is_active=1 THEN 0 ELSE 1 END WHERE id=?",
            (svc_id,)
        )
        await db.commit()


# ------------------------------------------------------------------
# Слоты расписания
# ------------------------------------------------------------------

def generate_slots(start_time: str, end_time: str) -> list:
    slots = []
    sh, sm = map(int, start_time.split(":"))
    eh, em = map(int, end_time.split(":"))
    current = sh * 60 + sm
    end = eh * 60 + em
    while current < end:
        h, m = divmod(current, 60)
        slots.append(f"{h:02d}:{m:02d}")
        current += SLOT_DURATION
    return slots


async def add_working_day(date: str, start_time: str, end_time: str) -> int:
    slots = generate_slots(start_time, end_time)
    added = 0
    async with aiosqlite.connect(DB_PATH) as db:
        for slot in slots:
            try:
                await db.execute(
                    "INSERT OR IGNORE INTO schedule (date, time_slot) VALUES (?, ?)",
                    (date, slot)
                )
                added += 1
            except Exception:
                pass
        await db.commit()
    return added


async def add_slot(date: str, time_slot: str) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO schedule (date, time_slot) VALUES (?, ?)",
                (date, time_slot)
            )
            await db.commit()
        return True
    except Exception:
        return False


async def remove_slot(date: str, time_slot: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT is_booked FROM schedule WHERE date=? AND time_slot=?",
            (date, time_slot)
        )
        row = await cur.fetchone()
        if not row or row[0] == 1:
            return False
        await db.execute("DELETE FROM schedule WHERE date=? AND time_slot=?", (date, time_slot))
        await db.commit()
    return True


async def close_day(date: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE schedule SET is_closed=1 WHERE date=? AND is_booked=0", (date,))
        await db.commit()


async def open_day(date: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE schedule SET is_closed=0 WHERE date=?", (date,))
        await db.commit()


async def get_available_dates() -> list:
    now = _now_local()
    today = _today_local()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT DISTINCT date FROM schedule
            WHERE is_booked=0 AND is_closed=0
              AND (date || ' ' || time_slot) > ?
              AND date < date(?, '+31 days')
            ORDER BY date
        """, (now, today))
        rows = await cur.fetchall()
    return [r[0] for r in rows]


async def get_slots_for_date(date: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT time_slot, is_booked, is_closed FROM schedule "
            "WHERE date=? ORDER BY time_slot", (date,)
        )
        rows = await cur.fetchall()
    return [{"time": r[0], "is_booked": bool(r[1]), "is_closed": bool(r[2])} for r in rows]


async def get_free_slots(date: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT time_slot FROM schedule "
            "WHERE date=? AND is_booked=0 AND is_closed=0 ORDER BY time_slot", (date,)
        )
        rows = await cur.fetchall()
    return [r[0] for r in rows]


async def get_free_slots_for_service(date: str, slots_needed: int) -> list:
    free = await get_free_slots(date)
    if slots_needed <= 1:
        return free
    free_set = set(free)
    result = []
    for start in free:
        h, m = map(int, start.split(":"))
        ok = True
        for i in range(1, slots_needed):
            total = h * 60 + m + i * SLOT_DURATION
            slot = f"{total // 60:02d}:{total % 60:02d}"
            if slot not in free_set:
                ok = False
                break
        if ok:
            result.append(start)
    return result


async def get_next_consecutive_slot(date: str, slots_needed: int) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT a.time_slot, a.slots_count FROM appointments a
            WHERE a.date=? ORDER BY a.time_slot DESC LIMIT 1
        """, (date,))
        last = await cur.fetchone()
        cur = await db.execute(
            "SELECT time_slot FROM schedule "
            "WHERE date=? AND is_booked=0 AND is_closed=0 ORDER BY time_slot", (date,)
        )
        free_rows = await cur.fetchall()

    free = [r[0] for r in free_rows]
    if not free:
        return None
    free_set = set(free)

    after_time = None
    if last:
        h, m = map(int, last[0].split(":"))
        total = h * 60 + m + (last[1] or 1) * SLOT_DURATION
        after_h, after_m = divmod(total, 60)
        after_time = f"{after_h:02d}:{after_m:02d}"

    candidates = [s for s in free if s >= after_time] if after_time else free
    if not candidates:
        candidates = free

    for start in candidates:
        h, m = map(int, start.split(":"))
        ok = True
        for i in range(1, slots_needed):
            total = h * 60 + m + i * SLOT_DURATION
            slot = f"{total // 60:02d}:{total % 60:02d}"
            if slot not in free_set:
                ok = False
                break
        if ok:
            return start
    return None


# ------------------------------------------------------------------
# Записи
# ------------------------------------------------------------------

async def get_user_appointment(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, date, time_slot, client_name, phone, reminder_job_id, "
            "service_name, service_price, slots_count, service_key "
            "FROM appointments WHERE user_id=? "
            "AND (date || ' ' || time_slot) >= ? "
            "ORDER BY date, time_slot LIMIT 1",
            (user_id, _now_local())
        )
        row = await cur.fetchone()
    if row:
        return {"id": row[0], "date": row[1], "time_slot": row[2],
                "client_name": row[3], "phone": row[4], "reminder_job_id": row[5],
                "service_name": row[6], "service_price": row[7],
                "slots_count": row[8], "service_key": row[9]}
    return None


async def create_appointment(
    user_id: int, username: str, client_name: str, phone: str,
    date: str, time_slot: str,
    service_key: str = "", service_name: str = "",
    service_price: int = 0, slots_count: int = 1
) -> int | None:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("BEGIN EXCLUSIVE")
            h, m = map(int, time_slot.split(":"))
            # Проверяем что все нужные слоты свободны
            for i in range(slots_count):
                total = h * 60 + m + i * SLOT_DURATION
                slot = f"{total // 60:02d}:{total % 60:02d}"
                cur = await db.execute(
                    "SELECT is_booked, is_closed FROM schedule "
                    "WHERE date=? AND time_slot=?",
                    (date, slot)
                )
                row = await cur.fetchone()
                if not row or row[0] == 1 or row[1] == 1:
                    await db.execute("ROLLBACK")
                    return None
            for i in range(slots_count):
                total = h * 60 + m + i * SLOT_DURATION
                slot = f"{total // 60:02d}:{total % 60:02d}"
                await db.execute(
                    "UPDATE schedule SET is_booked=1 "
                    "WHERE date=? AND time_slot=?",
                    (date, slot)
                )
            cur = await db.execute(
                "INSERT INTO appointments "
                "(user_id, username, client_name, phone, date, time_slot, "
                "service_key, service_name, service_price, slots_count) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, username, client_name, phone, date, time_slot,
                 service_key, service_name, service_price, slots_count)
            )
            appt_id = cur.lastrowid
            await db.execute("COMMIT")
        return appt_id
    except Exception:
        return None


async def cancel_appointment(appointment_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("BEGIN EXCLUSIVE")
        cur = await db.execute(
            "SELECT user_id, date, time_slot, reminder_job_id, slots_count, "
            "repeat_job_id, master_job_id "
            "FROM appointments WHERE id=?", (appointment_id,)
        )
        row = await cur.fetchone()
        if not row:
            await db.execute("ROLLBACK")
            return None
        user_id, date, time_slot, reminder_job_id, slots_count, repeat_job_id, master_job_id = row
        slots_count = slots_count or 1
        h, m = map(int, time_slot.split(":"))
        for i in range(slots_count):
            total = h * 60 + m + i * SLOT_DURATION
            slot = f"{total // 60:02d}:{total % 60:02d}"
            await db.execute(
                "UPDATE schedule SET is_booked=0 WHERE date=? AND time_slot=?", (date, slot)
            )
        await db.execute("DELETE FROM appointments WHERE id=?", (appointment_id,))
        await db.execute("COMMIT")
    return {"user_id": user_id, "date": date, "time_slot": time_slot,
            "reminder_job_id": reminder_job_id, "repeat_job_id": repeat_job_id,
            "master_job_id": master_job_id}


async def get_appointment_by_id(appointment_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, user_id, date, time_slot, client_name, service_name, "
            "service_key, slots_count FROM appointments WHERE id=?",
            (appointment_id,)
        )
        row = await cur.fetchone()
    if not row:
        return None
    return {"id": row[0], "user_id": row[1], "date": row[2], "time_slot": row[3],
            "client_name": row[4], "service_name": row[5],
            "service_key": row[6], "slots_count": row[7] or 1}


async def cancel_appointment_by_user(user_id: int) -> dict | None:
    appt = await get_user_appointment(user_id)
    if not appt:
        return None
    return await cancel_appointment(appt["id"])


async def reschedule_appointment(appointment_id: int, new_date: str, new_time_slot: str) -> dict | None:
    """Перенести запись на новую дату и время. Возвращает dict с old/new данными или None при ошибке."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("BEGIN EXCLUSIVE")
            # Получаем текущую запись
            cur = await db.execute(
                "SELECT user_id, date, time_slot, slots_count, reminder_job_id, "
                "repeat_job_id, master_job_id, client_name, service_name "
                "FROM appointments WHERE id=?", (appointment_id,)
            )
            row = await cur.fetchone()
            if not row:
                await db.execute("ROLLBACK")
                return None
            user_id, old_date, old_slot, slots_count, reminder_job_id, \
                repeat_job_id, master_job_id, client_name, service_name = row
            slots_count = slots_count or 1

            # Проверяем что новые слоты свободны
            h, m = map(int, new_time_slot.split(":"))
            for i in range(slots_count):
                total = h * 60 + m + i * SLOT_DURATION
                slot = f"{total // 60:02d}:{total % 60:02d}"
                cur = await db.execute(
                    "SELECT is_booked, is_closed FROM schedule WHERE date=? AND time_slot=?",
                    (new_date, slot)
                )
                r = await cur.fetchone()
                if not r or r[0] == 1 or r[1] == 1:
                    await db.execute("ROLLBACK")
                    return None

            # Освобождаем старые слоты
            oh, om = map(int, old_slot.split(":"))
            for i in range(slots_count):
                total = oh * 60 + om + i * SLOT_DURATION
                slot = f"{total // 60:02d}:{total % 60:02d}"
                await db.execute(
                    "UPDATE schedule SET is_booked=0 WHERE date=? AND time_slot=?",
                    (old_date, slot)
                )

            # Занимаем новые слоты
            for i in range(slots_count):
                total = h * 60 + m + i * SLOT_DURATION
                slot = f"{total // 60:02d}:{total % 60:02d}"
                await db.execute(
                    "UPDATE schedule SET is_booked=1 WHERE date=? AND time_slot=?",
                    (new_date, slot)
                )

            # Обновляем запись
            await db.execute(
                "UPDATE appointments SET date=?, time_slot=? WHERE id=?",
                (new_date, new_time_slot, appointment_id)
            )
            await db.execute("COMMIT")

        return {
            "user_id": user_id, "slots_count": slots_count,
            "old_date": old_date, "old_slot": old_slot,
            "new_date": new_date, "new_slot": new_time_slot,
            "reminder_job_id": reminder_job_id, "repeat_job_id": repeat_job_id,
            "master_job_id": master_job_id,
            "client_name": client_name, "service_name": service_name,
        }
    except Exception:
        return None


async def save_job_ids(appointment_id: int, reminder_job_id: str = None,
                       repeat_job_id: str = None, master_job_id: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if reminder_job_id is not None:
            await db.execute("UPDATE appointments SET reminder_job_id=? WHERE id=?",
                             (reminder_job_id, appointment_id))
        if repeat_job_id is not None:
            await db.execute("UPDATE appointments SET repeat_job_id=? WHERE id=?",
                             (repeat_job_id, appointment_id))
        if master_job_id is not None:
            await db.execute("UPDATE appointments SET master_job_id=? WHERE id=?",
                             (master_job_id, appointment_id))
        await db.commit()



async def mark_attendance(appointment_id: int, attended: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE appointments SET attended=? WHERE id=?", (int(attended), appointment_id)
        )
        await db.commit()


async def get_schedule_for_date(date: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT s.time_slot, s.is_booked, s.is_closed,
                   a.client_name, a.phone, a.username, a.user_id, a.id,
                   a.service_name, a.service_price
            FROM schedule s
            LEFT JOIN appointments a ON a.date=s.date AND a.time_slot=s.time_slot
            WHERE s.date=? ORDER BY s.time_slot
        """, (date,))
        rows = await cur.fetchall()
    return [{"time": r[0], "is_booked": bool(r[1]), "is_closed": bool(r[2]),
             "client_name": r[3], "phone": r[4], "username": r[5],
             "user_id": r[6], "appt_id": r[7],
             "service_name": r[8] or "", "service_price": r[9] or 0}
            for r in rows]


async def get_all_future_appointments() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT id, user_id, client_name, date, time_slot, reminder_job_id,
                   slots_count, service_name, service_key
            FROM appointments
            WHERE date >= ? ORDER BY date, time_slot
        """, (_today_local(),))
        rows = await cur.fetchall()
    return [{"id": r[0], "user_id": r[1], "client_name": r[2], "date": r[3],
             "time_slot": r[4], "reminder_job_id": r[5], "slots_count": r[6],
             "service_name": r[7], "service_key": r[8]}
            for r in rows]


async def get_appointments_for_date(date: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT time_slot, client_name, phone, service_name FROM appointments "
            "WHERE date=? ORDER BY time_slot", (date,)
        )
        rows = await cur.fetchall()
    return [{"time": r[0], "client_name": r[1], "phone": r[2], "service_name": r[3] or ""}
            for r in rows]


async def create_manual_appointment(
    client_name: str, phone: str, date: str, time_slot: str,
    service_key: str = "", service_name: str = "",
    service_price: int = 0, slots_count: int = 1
) -> int | None:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("BEGIN EXCLUSIVE")
            h, m = map(int, time_slot.split(":"))
            for i in range(slots_count):
                total = h * 60 + m + i * SLOT_DURATION
                slot = f"{total // 60:02d}:{total % 60:02d}"
                cur = await db.execute(
                    "SELECT is_booked FROM schedule WHERE date=? AND time_slot=?",
                    (date, slot)
                )
                row = await cur.fetchone()
                if not row or row[0] == 1:
                    await db.execute("ROLLBACK")
                    return None
            for i in range(slots_count):
                total = h * 60 + m + i * SLOT_DURATION
                slot = f"{total // 60:02d}:{total % 60:02d}"
                await db.execute(
                    "UPDATE schedule SET is_booked=1 WHERE date=? AND time_slot=?",
                    (date, slot)
                )
            cur = await db.execute(
                "INSERT INTO appointments "
                "(user_id, username, client_name, phone, date, time_slot, "
                "service_key, service_name, service_price, slots_count) "
                "VALUES (0, 'manual', ?, ?, ?, ?, ?, ?, ?, ?)",
                (client_name, phone, date, time_slot,
                 service_key, service_name, service_price, slots_count)
            )
            appt_id = cur.lastrowid
            await db.execute("COMMIT")
        return appt_id
    except Exception:
        return None


# ------------------------------------------------------------------
# Статистика
# ------------------------------------------------------------------

async def get_stats_month(year: int, month: int) -> dict:
    month_str = f"{year:04d}-{month:02d}"
    pattern = f"{month_str}-%"
    async with aiosqlite.connect(DB_PATH) as db:
        # Один запрос — основные агрегаты
        cur = await db.execute("""
            SELECT
                COUNT(*)                                        AS total,
                COUNT(DISTINCT CASE WHEN user_id!=0 THEN user_id END) AS unique_clients,
                SUM(service_price)                              AS revenue,
                SUM(CASE WHEN attended=1 THEN 1 ELSE 0 END)    AS attended,
                SUM(CASE WHEN attended=0 THEN 1 ELSE 0 END)    AS no_show
            FROM appointments WHERE date LIKE ?
        """, (pattern,))
        row = await cur.fetchone()
        total, unique_clients, revenue, attended, no_show = (
            row[0], row[1], row[2] or 0, row[3], row[4]
        )
        # Новые клиенты в этом месяце
        cur = await db.execute("""
            SELECT COUNT(*) FROM (
                SELECT user_id, MIN(date) AS first_date FROM appointments
                WHERE user_id!=0 GROUP BY user_id HAVING first_date LIKE ?)
        """, (pattern,))
        new_clients = (await cur.fetchone())[0]
        # Загруженность по дням + самый загруженный день
        cur = await db.execute(
            "SELECT date, COUNT(*) FROM appointments WHERE date LIKE ? "
            "GROUP BY date ORDER BY date", (pattern,))
        by_day = await cur.fetchall()
        busiest_day = max(by_day, key=lambda x: x[1]) if by_day else None
        # По услугам
        cur = await db.execute(
            "SELECT service_name, COUNT(*) FROM appointments "
            "WHERE date LIKE ? AND service_name!='' GROUP BY service_name ORDER BY 2 DESC",
            (pattern,))
        by_service = await cur.fetchall()
        # Всего клиентов за всё время
        cur = await db.execute(
            "SELECT COUNT(DISTINCT user_id) FROM appointments WHERE user_id!=0")
        total_clients = (await cur.fetchone())[0]
    return {
        "total": total, "unique_clients": unique_clients, "new_clients": new_clients,
        "busiest_day": busiest_day, "total_clients_ever": total_clients,
        "by_day": by_day, "revenue": revenue, "by_service": by_service,
        "attended": attended, "no_show": no_show,
    }


async def get_stats_alltime() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        # Один запрос — основные агрегаты
        cur = await db.execute("""
            SELECT
                COUNT(*)                                        AS total,
                COUNT(DISTINCT CASE WHEN user_id!=0 THEN user_id END) AS unique_clients,
                SUM(service_price)                              AS revenue,
                SUM(CASE WHEN attended=1 THEN 1 ELSE 0 END)    AS attended,
                SUM(CASE WHEN attended=0 THEN 1 ELSE 0 END)    AS no_show
            FROM appointments
        """)
        row = await cur.fetchone()
        total, unique_clients, revenue, attended, no_show = (
            row[0], row[1], row[2] or 0, row[3], row[4]
        )
        # Самый загруженный день
        cur = await db.execute(
            "SELECT date, COUNT(*) FROM appointments "
            "GROUP BY date ORDER BY COUNT(*) DESC LIMIT 1")
        busiest = await cur.fetchone()
        # По месяцам
        cur = await db.execute(
            "SELECT strftime('%Y-%m', date) AS m, COUNT(*) FROM appointments "
            "GROUP BY m ORDER BY m DESC LIMIT 6")
        by_month = await cur.fetchall()
        # По услугам
        cur = await db.execute(
            "SELECT service_name, COUNT(*) FROM appointments WHERE service_name!='' "
            "GROUP BY service_name ORDER BY 2 DESC")
        by_service = await cur.fetchall()
    return {
        "total": total, "unique_clients": unique_clients,
        "busiest_day": busiest, "by_month": by_month,
        "revenue": revenue, "by_service": by_service,
        "attended": attended, "no_show": no_show,
    }


async def get_all_user_ids() -> list:
    """Все уникальные user_id клиентов которые хоть раз записывались."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT DISTINCT user_id FROM appointments WHERE user_id != 0"
        )
        rows = await cur.fetchall()
    return [r[0] for r in rows]


async def get_client_stats(user_id: int) -> dict:
    """Статистика клиента: всего визитов, подтверждённых, последний визит."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT
                COUNT(*)                                     AS total,
                SUM(CASE WHEN attended=1 THEN 1 ELSE 0 END) AS confirmed,
                MAX(date)                                    AS last_date
            FROM appointments
            WHERE user_id=? AND (date || ' ' || time_slot) < ?
        """, (user_id, _now_local()))
        row = await cur.fetchone()
    return {
        "total":     row[0] or 0,
        "confirmed": row[1] or 0,
        "last_date": row[2] or "",
    }


# ------------------------------------------------------------------
# Чёрный список
# ------------------------------------------------------------------

async def blacklist_add(user_id: int, username: str = "", client_name: str = "", reason: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO blacklist (user_id, username, client_name, reason) "
            "VALUES (?, ?, ?, ?)",
            (user_id, username, client_name, reason)
        )
        await db.commit()


async def blacklist_remove(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM blacklist WHERE user_id=?", (user_id,))
        await db.commit()


async def blacklist_check(user_id: int) -> bool:
    """Вернуть True если пользователь заблокирован."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM blacklist WHERE user_id=?", (user_id,)
        )
        row = await cur.fetchone()
    return row is not None


async def blacklist_get_all() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT user_id, username, client_name, reason FROM blacklist ORDER BY created_at DESC"
        )
        rows = await cur.fetchall()
    return [{"user_id": r[0], "username": r[1], "client_name": r[2], "reason": r[3]}
            for r in rows]

