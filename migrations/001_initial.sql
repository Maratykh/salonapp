-- migrations/001_initial.sql
-- Начальная схема базы данных для SalonApp (PostgreSQL)

CREATE TABLE IF NOT EXISTS schedule (
    id        SERIAL PRIMARY KEY,
    date      TEXT NOT NULL,
    time_slot TEXT NOT NULL,
    is_booked BOOLEAN DEFAULT FALSE,
    is_closed BOOLEAN DEFAULT FALSE,
    UNIQUE(date, time_slot)
);

CREATE INDEX IF NOT EXISTS idx_schedule_date ON schedule(date);
CREATE INDEX IF NOT EXISTS idx_schedule_date_booked ON schedule(date, is_booked, is_closed);

CREATE TABLE IF NOT EXISTS appointments (
    id               SERIAL PRIMARY KEY,
    user_id          BIGINT NOT NULL,
    username         TEXT,
    client_name      TEXT NOT NULL,
    phone            TEXT NOT NULL DEFAULT '—',
    date             TEXT NOT NULL,
    time_slot        TEXT NOT NULL,
    service_key      TEXT DEFAULT '',
    service_name     TEXT DEFAULT '',
    service_price    INTEGER DEFAULT 0,
    slots_count      INTEGER DEFAULT 1,
    attended         SMALLINT DEFAULT NULL,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    reminder_job_id  TEXT,
    repeat_job_id    TEXT,
    master_job_id    TEXT
);

CREATE INDEX IF NOT EXISTS idx_appointments_date     ON appointments(date);
CREATE INDEX IF NOT EXISTS idx_appointments_user_id  ON appointments(user_id);
CREATE INDEX IF NOT EXISTS idx_appointments_date_slot ON appointments(date, time_slot);

CREATE TABLE IF NOT EXISTS services (
    id           SERIAL PRIMARY KEY,
    key          TEXT UNIQUE NOT NULL,
    name         TEXT NOT NULL,
    price        INTEGER NOT NULL DEFAULT 0,
    slots        INTEGER NOT NULL DEFAULT 1,
    duration_str TEXT DEFAULT '',
    emoji        TEXT DEFAULT '💅',
    repeat_days  INTEGER DEFAULT 0,
    is_active    BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS blacklist (
    user_id     BIGINT PRIMARY KEY,
    username    TEXT,
    client_name TEXT,
    reason      TEXT DEFAULT '',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_blacklist_user_id ON blacklist(user_id);
