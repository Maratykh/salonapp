# utils/scheduler.py

import logging
from datetime import datetime, timedelta
import pytz

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from aiogram import Bot

from database.db import (
    get_all_future_appointments, save_job_ids,
    get_setting, get_service_by_key
)
from config import ADMIN_ID, ADMIN_IDS, SLOT_DURATION, MSG_REMINDER_24H, MSG_REPEAT_REMINDER, MSG_MASTER_30MIN
from config import STUDIO_NAME, STUDIO_ADDRESS, TIMEZONE, BACKUP_CHANNEL_ID, BACKUP_HOUR, DB_PATH

logger = logging.getLogger(__name__)
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    return _scheduler


def now_local() -> datetime:
    """Текущее время в таймзоне мастера."""
    tz = pytz.timezone(TIMEZONE)
    return datetime.now(tz).replace(tzinfo=None)


async def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    global _scheduler
    tz = pytz.timezone(TIMEZONE)
    _scheduler = AsyncIOScheduler(
        jobstores={"default": MemoryJobStore()},
        job_defaults={"misfire_grace_time": 3600},
        timezone=tz,
    )
    _scheduler.start()

    # Ежедневный бэкап базы данных
    if BACKUP_CHANNEL_ID:
        _scheduler.add_job(
            send_backup, trigger="cron", hour=BACKUP_HOUR, minute=0,
            args=[bot], id="daily_backup", replace_existing=True
        )
        logger.info(f"Бэкап БД запланирован на {BACKUP_HOUR}:00 каждый день")

    return _scheduler


async def restore_jobs(bot: Bot, scheduler: AsyncIOScheduler):
    appointments = await get_all_future_appointments()
    now = now_local()
    for appt in appointments:
        visit_dt = datetime.strptime(f"{appt['date']} {appt['time_slot']}", "%Y-%m-%d %H:%M")

        # Напоминание за 24 часа
        remind_dt = visit_dt - timedelta(hours=24)
        if remind_dt > now:
            job_id = f"reminder_{appt['id']}"
            if not scheduler.get_job(job_id):
                scheduler.add_job(
                    send_reminder, trigger="date", run_date=remind_dt,
                    args=[bot, appt["user_id"], appt["time_slot"]],
                    id=job_id, replace_existing=True
                )

        # Уведомление мастеру за 30 мин
        master_dt = visit_dt - timedelta(minutes=30)
        if master_dt > now:
            job_id = f"master_{appt['id']}"
            if not scheduler.get_job(job_id):
                scheduler.add_job(
                    send_master_notification, trigger="date", run_date=master_dt,
                    args=[bot, appt["client_name"], appt["service_name"], appt["time_slot"]],
                    id=job_id, replace_existing=True
                )

        # Проверка явки (через slots_count × SLOT_DURATION минут после начала)
        slots = appt.get("slots_count") or 1
        check_dt = visit_dt + timedelta(minutes=slots * SLOT_DURATION + 5)
        if check_dt > now:
            job_id = f"attend_{appt['id']}"
            if not scheduler.get_job(job_id):
                scheduler.add_job(
                    ask_attendance, trigger="date", run_date=check_dt,
                    args=[bot, appt["id"], appt["client_name"],
                          appt["service_name"], appt["time_slot"]],
                    id=job_id, replace_existing=True
                )


async def schedule_all_jobs(
    bot: Bot, appointment_id: int, user_id: int,
    date_str: str, time_slot: str,
    service_key: str, service_name: str, slots_count: int,
    client_name: str = "",
):
    """Запланировать все задачи для новой записи."""
    scheduler = get_scheduler()
    if not scheduler:
        return

    now = now_local()
    visit_dt = datetime.strptime(f"{date_str} {time_slot}", "%Y-%m-%d %H:%M")

    reminder_job_id = None
    master_job_id = None
    repeat_job_id = None

    # 1. Напоминание клиенту за 24 часа
    remind_dt = visit_dt - timedelta(hours=24)
    if remind_dt > now:
        job_id = f"reminder_{appointment_id}"
        scheduler.add_job(
            send_reminder, trigger="date", run_date=remind_dt,
            args=[bot, user_id, time_slot],
            id=job_id, replace_existing=True
        )
        reminder_job_id = job_id

    # 2. Уведомление мастеру за 30 мин
    master_dt = visit_dt - timedelta(minutes=30)
    if master_dt > now:
        job_id = f"master_{appointment_id}"
        scheduler.add_job(
            send_master_notification, trigger="date", run_date=master_dt,
            args=[bot, client_name, service_name, time_slot],
            id=job_id, replace_existing=True
        )
        master_job_id = job_id

    # 3. Проверка явки
    check_dt = visit_dt + timedelta(minutes=slots_count * SLOT_DURATION + 5)
    if check_dt > now:
        job_id = f"attend_{appointment_id}"
        scheduler.add_job(
            ask_attendance, trigger="date", run_date=check_dt,
            args=[bot, appointment_id, client_name, service_name, time_slot],
            id=job_id, replace_existing=True
        )

    # 4. Повторное напоминание (через repeat_days после визита)
    if user_id != 0:
        svc = await get_service_by_key(service_key)
        repeat_days = svc["repeat_days"] if svc else 0
        if repeat_days and repeat_days > 0:
            repeat_dt = visit_dt + timedelta(days=repeat_days)
            if repeat_dt > now:
                job_id = f"repeat_{appointment_id}"
                scheduler.add_job(
                    send_repeat_reminder, trigger="date", run_date=repeat_dt,
                    args=[bot, user_id, client_name, service_name, repeat_days],
                    id=job_id, replace_existing=True
                )
                repeat_job_id = job_id

    await save_job_ids(appointment_id,
                       reminder_job_id=reminder_job_id,
                       repeat_job_id=repeat_job_id,
                       master_job_id=master_job_id)


def cancel_all_jobs(appointment_id: int, result: dict):
    """Отменить все задачи при отмене записи."""
    scheduler = get_scheduler()
    if not scheduler:
        return
    for prefix in ["reminder", "master", "attend", "repeat"]:
        job_id = f"{prefix}_{appointment_id}"
        job = scheduler.get_job(job_id)
        if job:
            job.remove()


def cancel_reminder(appointment_id: int):
    cancel_all_jobs(appointment_id, {})


# ------------------------------------------------------------------
# Задачи
# ------------------------------------------------------------------

async def send_reminder(bot: Bot, user_id: int, time_slot: str):
    """Напоминание клиенту за 24 часа."""
    try:
        text = MSG_REMINDER_24H.format(
            time=time_slot, studio=STUDIO_NAME, address=STUDIO_ADDRESS
        )
        await bot.send_message(user_id, text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка отправки напоминания: {e}")


async def send_master_notification(bot: Bot, client_name: str,
                                    service_name: str, time_slot: str):
    """Уведомление мастеру за 30 минут."""
    enabled = await get_setting("master_30min_enabled")
    if enabled != "1":
        return
    try:
        text = MSG_MASTER_30MIN.format(
            client=client_name, service=service_name, time=time_slot
        )
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, text, parse_mode="HTML")
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Ошибка уведомления мастеру: {e}")


async def send_repeat_reminder(bot: Bot, user_id: int, client_name: str,
                                service_name: str, days: int):
    """Повторное напоминание клиенту о коррекции."""
    enabled = await get_setting("repeat_reminders_enabled")
    if enabled != "1":
        return
    try:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        text = MSG_REPEAT_REMINDER.format(
            name=client_name, days=days, service=service_name
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📅 Записаться", callback_data="book")
        ]])
        await bot.send_message(user_id, text, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка повторного напоминания: {e}")


async def ask_attendance(bot: Bot, appointment_id: int, client_name: str,
                          service_name: str, time_slot: str):
    """Спросить мастера о явке клиента."""
    try:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from config import MSG_ATTENDANCE_CHECK
        text = MSG_ATTENDANCE_CHECK.format(
            client=client_name, service=service_name, time=time_slot
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Да, пришёл",  callback_data=f"attend_yes_{appointment_id}"),
            InlineKeyboardButton(text="❌ Не пришёл",   callback_data=f"attend_no_{appointment_id}"),
        ]])
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Ошибка запроса явки: {e}")


async def send_backup(bot: Bot):
    """Отправить бэкап базы данных в канал."""
    if not BACKUP_CHANNEL_ID:
        return
    import os
    try:
        if not os.path.exists(DB_PATH):
            logger.warning("Файл БД не найден для бэкапа")
            return
        now = now_local()
        date_str = now.strftime("%Y-%m-%d_%H-%M")
        from aiogram.types import FSInputFile
        db_file = FSInputFile(DB_PATH, filename=f"backup_{date_str}.db")
        await bot.send_document(
            BACKUP_CHANNEL_ID,
            db_file,
            caption=f"🗄 <b>Бэкап базы данных</b>\n📅 {now.strftime('%d.%m.%Y %H:%M')}",
            parse_mode="HTML"
        )
        logger.info(f"Бэкап отправлен в {BACKUP_CHANNEL_ID}")
    except Exception as e:
        logger.error(f"Ошибка отправки бэкапа: {e}")
