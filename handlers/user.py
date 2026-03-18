# handlers/user.py

import logging
from datetime import date, datetime

from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from config import ADMIN_ID, ADMIN_IDS, SCHEDULE_CHANNEL_ID, SLOT_DURATION
from config import MSG_BOOKING_CREATED, STUDIO_NAME
from database.db import (
    get_available_dates, get_free_slots, get_free_slots_for_service,
    get_slots_for_date, create_appointment, get_user_appointment,
    get_appointments_for_date, get_services, get_service_by_key, get_setting
)
from keyboards.user_kb import (
    main_menu_kb as _main_menu_kb, services_kb, time_slots_kb,
    confirm_booking_kb, my_appointment_kb, cancel_action_kb, cancel_confirm_kb
)
from utils.calendar_kb import build_calendar, CalendarCallback
from utils.scheduler import schedule_all_jobs, cancel_all_jobs
from states.states import BookingStates

router = Router()
logger = logging.getLogger(__name__)


def main_menu_kb(user_id: int = 0):
    return _main_menu_kb(is_admin=(user_id in ADMIN_IDS))


def format_date_ru(date_str: str) -> str:
    months = ["","января","февраля","марта","апреля","мая","июня",
              "июля","августа","сентября","октября","ноября","декабря"]
    weekdays = ["понедельник","вторник","среда","четверг","пятница","суббота","воскресенье"]
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{d.day} {months[d.month]} {d.year} ({weekdays[d.weekday()]})"


async def post_schedule_to_channel(bot: Bot, date_str: str):
    if not SCHEDULE_CHANNEL_ID or "@your" in SCHEDULE_CHANNEL_ID:
        return
    appointments = await get_appointments_for_date(date_str)
    free_slots = await get_free_slots(date_str)
    date_formatted = format_date_ru(date_str)
    text = f"<b>Расписание на {date_formatted}</b>\n\n"
    if appointments:
        text += "<b>Записаны:</b>\n"
        for appt in appointments:
            svc = f" ({appt['service_name']})" if appt.get("service_name") else ""
            text += f"  {appt['time']} — {appt['client_name']}{svc}\n"
        text += "\n"
    if free_slots:
        text += f"<b>Свободно с:</b> {free_slots[0]}\n"
    else:
        text += "<i>Все слоты заняты</i>"

    from database.db import get_setting, set_setting
    setting_key = f"schedule_msg_{date_str}"
    existing_msg_id = await get_setting(setting_key)

    try:
        if existing_msg_id and existing_msg_id != "0":
            try:
                await bot.edit_message_text(
                    text, chat_id=SCHEDULE_CHANNEL_ID,
                    message_id=int(existing_msg_id), parse_mode="HTML"
                )
                return
            except Exception:
                pass  # Сообщение удалено — отправим новое
        msg = await bot.send_message(SCHEDULE_CHANNEL_ID, text, parse_mode="HTML")
        await set_setting(setting_key, str(msg.message_id))
    except Exception as e:
        logger.warning(f"Канал расписания: {e}")


# ================================================================
# Мои записи
# ================================================================

@router.callback_query(F.data == "my_appointments")
async def show_my_appointments(callback: CallbackQuery):
    appt = await get_user_appointment(callback.from_user.id)
    if not appt:
        await callback.message.edit_text(
            "<b>Ваши записи</b>\n\nУ вас нет активных записей.",
            reply_markup=main_menu_kb(callback.from_user.id)
        )
    else:
        h, m = map(int, appt["time_slot"].split(":"))
        end_total = h * 60 + m + (appt.get("slots_count") or 1) * SLOT_DURATION
        end_time = f"{end_total // 60:02d}:{end_total % 60:02d}"
        svc_line = f"Услуга: <b>{appt['service_name']}</b> — {appt['service_price']} руб.\n" if appt.get("service_name") else ""
        await callback.message.edit_text(
            f"<b>Ваша запись</b>\n\n"
            f"📅 <b>{format_date_ru(appt['date'])}</b>\n"
            f"🕐 <b>{appt['time_slot']} – {end_time}</b>\n"
            f"{svc_line}"
            f"👤 <b>{appt['client_name']}</b>\n\n"
            f"Хотите отменить запись?",
            reply_markup=my_appointment_kb()
        )
    await callback.answer()


# ================================================================
# Шаг 1: Календарь
# ================================================================

@router.callback_query(F.data == "book")
async def start_booking(callback: CallbackQuery, state: FSMContext):
    existing = await get_user_appointment(callback.from_user.id)
    if existing:
        await callback.message.edit_text(
            f"<b>У вас уже есть запись</b>\n\n"
            f"{format_date_ru(existing['date'])}, {existing['time_slot']}\n\n"
            f"Для новой записи сначала отмените текущую.",
            reply_markup=main_menu_kb(callback.from_user.id)
        )
        await callback.answer()
        return
    await show_calendar(callback, state)


async def show_calendar(callback: CallbackQuery, state: FSMContext):
    today = date.today()
    available = await get_available_dates()
    if not available:
        await state.clear()
        await callback.message.edit_text(
            "<b>Нет доступных дат для записи</b>\n\nПопробуйте зайти позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")
            ]])
        )
        await callback.answer()
        return
    await state.update_data(cal_year=today.year, cal_month=today.month)
    await state.set_state(BookingStates.choosing_date)
    kb = build_calendar(today.year, today.month, available)
    await callback.message.edit_text(
        "<b>Шаг 1 из 4</b> — выберите <b>дату</b>:", reply_markup=kb
    )
    await callback.answer()


@router.callback_query(CalendarCallback.filter(F.action.in_(["prev","next"])),
                       BookingStates.choosing_date)
async def navigate_calendar(callback: CallbackQuery, callback_data: CalendarCallback,
                             state: FSMContext):
    available = await get_available_dates()
    kb = build_calendar(callback_data.year, callback_data.month, available)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@router.callback_query(CalendarCallback.filter(F.action == "ignore"))
async def calendar_ignore(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(CalendarCallback.filter(F.action == "day"), BookingStates.choosing_date)
async def select_date(callback: CallbackQuery, callback_data: CalendarCallback, state: FSMContext):
    selected_date = f"{callback_data.year:04d}-{callback_data.month:02d}-{callback_data.day:02d}"
    free = await get_free_slots(selected_date)
    if not free:
        await callback.answer("Нет свободных слотов на эту дату", show_alert=True)
        return
    await state.update_data(selected_date=selected_date)
    await state.set_state(BookingStates.choosing_service)
    services = await get_services(active_only=True)
    await callback.message.edit_text(
        f"<b>Шаг 2 из 4</b> — выберите <b>услугу</b>:\n\n"
        f"📅 {format_date_ru(selected_date)}",
        reply_markup=services_kb(services)
    )
    await callback.answer()


# ================================================================
# Шаг 2: Услуга
# ================================================================

@router.callback_query(F.data.startswith("service_"), BookingStates.choosing_service)
async def select_service(callback: CallbackQuery, state: FSMContext):
    service_key = callback.data.removeprefix("service_")
    svc = await get_service_by_key(service_key)
    if not svc:
        await callback.answer("Услуга недоступна", show_alert=True)
        return
    data = await state.get_data()
    available_slots = await get_free_slots_for_service(data["selected_date"], svc["slots"])
    if not available_slots:
        await callback.answer(
            f"Нет свободного окна для «{svc['name']}» ({svc['duration_str']}) на эту дату.",
            show_alert=True
        )
        return

    # Плотное расписание — показываем только слоты вплотную к существующим записям
    dense = await get_setting("dense_schedule")
    if dense == "1":
        booked = await get_appointments_for_date(data["selected_date"])
        if booked:
            # Получаем реально занятые слоты из расписания
            all_slots = await get_slots_for_date(data["selected_date"])
            occupied = {s["time"] for s in all_slots if s["is_booked"]}

            # Оставляем только свободные слоты вплотную к занятому блоку
            dense_slots = []
            for slot in available_slots:
                h, m = map(int, slot.split(":"))
                prev_total = h * 60 + m - SLOT_DURATION
                prev_slot = f"{prev_total // 60:02d}:{prev_total % 60:02d}"
                if prev_slot in occupied:
                    dense_slots.append(slot)
            if dense_slots:
                available_slots = dense_slots

    await state.update_data(
        service_key=service_key, service_name=svc["name"],
        service_price=svc["price"], service_slots=svc["slots"], service_emoji=svc["emoji"]
    )
    await state.set_state(BookingStates.choosing_time)
    await callback.message.edit_text(
        f"<b>Шаг 3 из 4</b> — выберите <b>время</b>:\n\n"
        f"📅 {format_date_ru(data['selected_date'])}\n"
        f"{svc['emoji']} {svc['name']} — {svc['price']} руб. ({svc['duration_str']})",
        reply_markup=time_slots_kb(available_slots)
    )
    await callback.answer()


# ================================================================
# Шаг 3: Время
# ================================================================

@router.callback_query(F.data == "back_to_date", BookingStates.choosing_service)
async def back_to_date(callback: CallbackQuery, state: FSMContext):
    await show_calendar(callback, state)


@router.callback_query(F.data == "back_to_calendar", BookingStates.choosing_time)
async def back_to_service(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.set_state(BookingStates.choosing_service)
    services = await get_services(active_only=True)
    await callback.message.edit_text(
        f"<b>Шаг 2 из 4</b> — выберите <b>услугу</b>:\n\n"
        f"📅 {format_date_ru(data['selected_date'])}",
        reply_markup=services_kb(services)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("slot_"), BookingStates.choosing_time)
async def select_time(callback: CallbackQuery, state: FSMContext):
    time_slot = callback.data.removeprefix("slot_")
    data = await state.get_data()
    h, m = map(int, time_slot.split(":"))
    end_total = h * 60 + m + data["service_slots"] * SLOT_DURATION
    end_time = f"{end_total // 60:02d}:{end_total % 60:02d}"
    await state.update_data(selected_time=time_slot, end_time=end_time)
    await state.set_state(BookingStates.entering_name)
    await callback.message.edit_text(
        f"<b>Шаг 4 из 4</b> — введите ваше <b>имя</b>:\n\n"
        f"📅 {format_date_ru(data['selected_date'])}\n"
        f"🕐 {time_slot} – {end_time}\n"
        f"{data['service_emoji']} {data['service_name']} — {data['service_price']} руб.",
        reply_markup=cancel_action_kb()
    )
    await callback.answer()


# ================================================================
# Шаг 4: Имя и телефон
# ================================================================

@router.message(BookingStates.entering_name)
async def enter_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2 or len(name) > 50:
        await message.answer("Имя должно быть от 2 до 50 символов:", reply_markup=cancel_action_kb())
        return
    await state.update_data(client_name=name)
    await state.set_state(BookingStates.entering_phone)
    await message.answer(
        f"Имя: <b>{name}</b>\n\nВведите <b>номер телефона</b>:",
        reply_markup=cancel_action_kb()
    )


@router.message(BookingStates.entering_phone)
async def enter_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 10 or len(digits) > 12:
        await message.answer("Номер должен содержать 10–12 цифр:", reply_markup=cancel_action_kb())
        return
    await state.update_data(phone=phone)
    await state.set_state(BookingStates.confirming)
    data = await state.get_data()
    await message.answer(
        f"<b>Подтвердите запись</b>\n\n"
        f"📅 <b>{format_date_ru(data['selected_date'])}</b>\n"
        f"🕐 <b>{data['selected_time']} – {data['end_time']}</b>\n"
        f"{data['service_emoji']} <b>{data['service_name']}</b> — {data['service_price']} руб.\n"
        f"👤 <b>{data['client_name']}</b>\n"
        f"📞 <b>{phone}</b>\n\nВсё верно?",
        reply_markup=confirm_booking_kb()
    )


# ================================================================
# Подтверждение
# ================================================================

@router.callback_query(F.data == "confirm_booking", BookingStates.confirming)
async def confirm_booking(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    user = callback.from_user

    appt_id = await create_appointment(
        user_id=user.id, username=user.username or "",
        client_name=data["client_name"], phone=data["phone"],
        date=data["selected_date"], time_slot=data["selected_time"],
        service_key=data["service_key"], service_name=data["service_name"],
        service_price=data["service_price"], slots_count=data["service_slots"],
    )

    if not appt_id:
        await callback.message.edit_text(
            "<b>Ошибка!</b> Слот уже занят, попробуйте снова.",
            reply_markup=main_menu_kb(user.id)
        )
        await state.clear()
        await callback.answer()
        return

    await state.clear()

    await callback.message.edit_text(
        MSG_BOOKING_CREATED.format(
            date=format_date_ru(data["selected_date"]),
            time_start=data["selected_time"], time_end=data["end_time"],
            emoji=data["service_emoji"], service=data["service_name"],
            price=data["service_price"]
        ),
        reply_markup=main_menu_kb(user.id)
    )

    try:
        username_line = f"@{user.username}" if user.username else f'<a href="tg://user?id={user.id}">профиль</a>'
        text = (
            f"🔔 <b>Новая запись!</b>\n\n"
            f"📅 {format_date_ru(data['selected_date'])}\n"
            f"🕐 {data['selected_time']} – {data['end_time']}\n"
            f"{data['service_emoji']} {data['service_name']} — {data['service_price']} руб.\n"
            f"👤 {data['client_name']}\n"
            f"📞 {data['phone']}\n"
            f"✈️ {username_line}\n"
            f"ID: <code>{appt_id}</code>"
        )
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, text)
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Уведомление мастеру: {e}")

    await post_schedule_to_channel(bot, data["selected_date"])
    await schedule_all_jobs(
        bot=bot, appointment_id=appt_id, user_id=user.id,
        date_str=data["selected_date"], time_slot=data["selected_time"],
        service_key=data["service_key"], service_name=data["service_name"],
        slots_count=data["service_slots"], client_name=data["client_name"],
    )
    await callback.answer()


# ================================================================
# Отмена
# ================================================================

@router.callback_query(F.data == "cancel_booking_process")
async def cancel_booking_process(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Запись отменена.", reply_markup=main_menu_kb(callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data == "user_cancel_confirm")
async def user_cancel_confirm(callback: CallbackQuery):
    appt = await get_user_appointment(callback.from_user.id)
    if not appt:
        await callback.answer("У вас нет активных записей", show_alert=True)
        return
    h, m = map(int, appt["time_slot"].split(":"))
    end_total = h * 60 + m + (appt.get("slots_count") or 1) * SLOT_DURATION
    end_time = f"{end_total // 60:02d}:{end_total % 60:02d}"
    await callback.message.edit_text(
        f"<b>Вы уверены?</b>\n\n"
        f"📅 <b>{format_date_ru(appt['date'])}</b>\n"
        f"🕐 <b>{appt['time_slot']} – {end_time}</b>\n\n"
        f"Запись будет отменена безвозвратно.",
        reply_markup=cancel_confirm_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "user_cancel_appointment")
async def user_cancel_appointment(callback: CallbackQuery, bot: Bot):
    appt = await get_user_appointment(callback.from_user.id)
    if not appt:
        await callback.answer("У вас нет активных записей", show_alert=True)
        return
    from database.db import cancel_appointment
    result = await cancel_appointment(appt["id"])
    if not result:
        await callback.answer("Ошибка при отмене", show_alert=True)
        return

    cancel_all_jobs(appt["id"], result)

    await callback.message.edit_text(
        f"<b>Запись отменена</b>\n\n{format_date_ru(result['date'])}, {result['time_slot']}",
        reply_markup=main_menu_kb(callback.from_user.id)
    )
    try:
        text = (
            f"⚠️ <b>Клиент отменил запись</b>\n\n"
            f"{format_date_ru(result['date'])}, {result['time_slot']}\n"
            f"@{callback.from_user.username or 'нет'} (ID: {callback.from_user.id})"
        )
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, text)
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Уведомление: {e}")
    await post_schedule_to_channel(bot, result["date"])
    await callback.answer()
