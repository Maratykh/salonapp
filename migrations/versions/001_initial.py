"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-01-01
"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS schedule (
            id        SERIAL PRIMARY KEY,
            date      TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            is_booked BOOLEAN DEFAULT FALSE,
            is_closed BOOLEAN DEFAULT FALSE,
            UNIQUE(date, time_slot)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_schedule_date ON schedule(date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_schedule_date_booked ON schedule(date, is_booked, is_closed)")

    op.execute("""
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
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_appointments_date     ON appointments(date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_appointments_user_id  ON appointments(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_appointments_date_slot ON appointments(date, time_slot)")

    op.execute("""
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
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS blacklist (
            user_id     BIGINT PRIMARY KEY,
            username    TEXT,
            client_name TEXT,
            reason      TEXT DEFAULT '',
            created_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_blacklist_user_id ON blacklist(user_id)")


def downgrade():
    op.execute("DROP TABLE IF EXISTS blacklist")
    op.execute("DROP TABLE IF EXISTS settings")
    op.execute("DROP TABLE IF EXISTS services")
    op.execute("DROP TABLE IF EXISTS appointments")
    op.execute("DROP TABLE IF EXISTS schedule")
