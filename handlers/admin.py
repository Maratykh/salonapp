# handlers/admin.py

import asyncio
import logging
from datetime import datetime, date, timedelta

from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from states.states import AdminStates

from config import ADMIN_ID, ADMIN_IDS, SLOT_DURATION, DEMO_MODE
from database.db import (
    add_slot, remove_slot, close_day, open_day,
    get_slots_for_date, get_schedule_for_date, get_available_dates,
    cancel_appointment, get_stats_month, get_stats_alltime,
    create_manual_appointment, get_free_slots, get_free_slots_for_service, add_working_day,
    get_services, get_service_by_key, add_service, update_service, toggle_service,
    get_setting, set_setting, mark_attendance, save_job_ids,
    reschedule_appointment, get_appointment_by_id,
    blacklist_add, blacklist_remove, blacklist_get_all
)
from keyboards.admin_kb import (
    admin_menu_kb, admin_back_kb, admin_settings_kb, admin_content_kb, admin_tweaks_kb,
    admin_stats_kb, admin_schedule_kb, admin_schedule_full_kb, time_picker_kb,
    manual_confirm_kb, manual_free_slots_kb, manual_services_kb,
    weekday_picker_kb, admin_services_kb, admin_service_detail_kb
)
from utils.admin_calendar import build_admin_calendar
from utils.scheduler import cancel_all_jobs, schedule_all_jobs
from handlers.user import format_date_ru, post_schedule_to_channel

router = Router()
logger = logging.getLogger(__name__)

# Описания кнопок для демо-режима
DEMO_DESCRIPTIONS = {
    "admin_view_schedule":  "📅 <b>Расписание на дату</b>\n\nМастер выбирает день и видит все записи: имя клиента, время, услугу. Можно отменить или перенести любую запись.",
    "admin_add_day":        "➕ <b>Добавить рабочий день</b>\n\nМастер выбирает дату, затем начало и конец рабочего дня. Бот автоматически создаёт слоты с нужным шагом (15 мин).",
    "admin_add_by_weekday": "🗓 <b>По дням недели</b>\n\nДобавить рабочие дни сразу на месяц вперёд по расписанию. Например: каждый вт, чт, сб с 10:00 до 18:00.",
    "admin_manual_book":    "📝 <b>Записать клиента вручную</b>\n\nМастер сам записывает клиента — выбирает дату, услугу, время и вводит имя. Удобно для записи по телефону.",
    "admin_settings":       "⚙️ <b>Управление</b>\n\nЗдесь два раздела:\n📋 Контент — услуги, статистика, рассылка, чёрный список.\n🔧 Настройки — тумблеры напоминаний, плотное расписание, лояльность.",
    "admin_content":        "📋 <b>Контент</b>\n\nУслуги, статистика, рассылка клиентам и чёрный список.",
    "admin_tweaks":         "🔧 <b>Настройки</b>\n\nТумблеры: напоминания о коррекции, уведомление за 30 мин, плотное расписание, программа лояльности.",
    "admin_services":       "💄 <b>Услуги</b>\n\nСписок всех услуг. Можно добавить новую, изменить цену, длительность, эмодзи или отключить услугу.",
    "admin_stats":          "📊 <b>Статистика</b>\n\nВыручка, количество записей, явка клиентов, популярные услуги — за месяц или за всё время.",
    "admin_broadcast":      "📣 <b>Рассылка</b>\n\nОтправить сообщение всем клиентам которые хоть раз записывались. Поддерживается текст, фото, видео.",
    "admin_manage_slots":   "⏰ <b>Управление слотами</b>\n\nУдалить отдельные временные окна из расписания, не закрывая весь день.",
    "admin_close_day":      "🔒 <b>Закрыть день</b>\n\nЗакрыть день для новых записей. Клиенты у которых уже есть записи получат уведомление об отмене.",
    "admin_open_day":       "🔓 <b>Открыть день</b>\n\nОткрыть ранее закрытый день — слоты снова станут доступны для записи.",
    "toggle_repeat_reminders": "🔁 <b>Напоминания о коррекции</b>\n\nВключить/выключить автоматические напоминания клиентам записаться на коррекцию через N дней после визита.",
    "toggle_master_30min":  "⏰ <b>Уведомление мастеру за 30 мин</b>\n\nВключить/выключить напоминание мастеру о предстоящем клиенте за 30 минут.",
    "toggle_dense_schedule":"🧲 <b>Плотное расписание</b>\n\nКогда включено — клиенты видят только слоты вплотную к уже существующим записям. Помогает избежать 'дырок' в расписании.",
    "admin_blacklist":      "🚫 <b>Чёрный список</b>\n\nСписок заблокированных клиентов. Они не смогут записаться через бота.",
}






def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def get_admin_calendar(action: str, available: list):
    today = date.today()
    return build_admin_calendar(today.year, today.month, available, action)


def add_another_window_kb(date_str: str):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить ещё окно на этот день",
                              callback_data=f"adm_add_window_{date_str}")],
        [InlineKeyboardButton(text="✅ Готово", callback_data="admin_menu")]
    ])


async def send_schedule(callback: CallbackQuery, date_str: str, page: int = 0):
    slots = await get_schedule_for_date(date_str)
    date_formatted = format_date_ru(date_str)
    if not slots:
        await callback.message.edit_text(
            f"<b>{date_formatted}</b>\n\nНа этот день нет слотов.",
            reply_markup=admin_menu_kb()
        )
        return
    seen = set()
    unique = [s for s in slots if s["is_booked"] and s["appt_id"]
              and not seen.add(s["appt_id"])]
    free = [s["time"] for s in slots if not s["is_booked"] and not s["is_closed"]]
    text = (f"<b>{date_formatted}</b>\n"
            f"🔴 Записано: {len(unique)}  |  🟢 Свободно с: {free[0] if free else '—'}\n\n")
    text += "Нажмите на клиента чтобы <b>отменить запись</b>:" if unique else "Записей нет."
    await callback.message.edit_text(text, reply_markup=admin_schedule_kb(date_str, slots, page))


# ================================================================
# /admin
# ================================================================

@router.message(Command("backup"))
async def cmd_backup(message: Message):
    if not is_admin(message.from_user.id):
        return
    from utils.scheduler import send_backup
    from config import BACKUP_CHANNEL_ID, DB_PATH
    import os
    try:
        if not os.path.exists(DB_PATH):
            await message.answer("❌ Файл базы данных не найден.")
            return
        from aiogram.types import FSInputFile
        from utils.scheduler import now_local
        now = now_local()
        date_str = now.strftime("%Y-%m-%d_%H-%M")
        db_file = FSInputFile(DB_PATH, filename=f"backup_{date_str}.db")
        await message.answer_document(
            db_file,
            caption=f"🗄 <b>Бэкап базы данных</b>\n📅 {now.strftime('%d.%m.%Y %H:%M')}",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к панели администратора.")
        return
    await state.clear()
    today = date.today().strftime("%Y-%m-%d")
    slots = await get_schedule_for_date(today)
    seen = set()
    booked = sum(1 for s in slots if s["is_booked"] and s["appt_id"] and not seen.add(s["appt_id"]))
    free = [s["time"] for s in slots if not s["is_booked"] and not s["is_closed"]]
    await message.answer(
        f"<b>Панель администратора</b>\n\n"
        f"Сегодня: 🔴 {booked} записей, 🟢 свободно {f'с {free[0]}' if free else 'нет'}\n\n"
        f"Выберите действие:",
        reply_markup=admin_menu_kb()
    )


@router.callback_query(F.data == "admin_menu")
async def admin_menu_cb(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id) and not DEMO_MODE:
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.clear()

    # В демо-режиме для не-админов — показываем демо-панель
    if DEMO_MODE and not is_admin(callback.from_user.id):
        await callback.message.edit_text(
            "🎭 <b>Демо — Панель администратора</b>\n\n"
            "Здесь мастер управляет всем расписанием.\n"
            "Нажмите на любую кнопку чтобы узнать что она делает:",
            reply_markup=admin_menu_kb()
        )
        await callback.answer()
        return

    today = date.today().strftime("%Y-%m-%d")
    slots = await get_schedule_for_date(today)
    seen = set()
    booked = sum(1 for s in slots if s["is_booked"] and s["appt_id"] and not seen.add(s["appt_id"]))
    free = [s["time"] for s in slots if not s["is_booked"] and not s["is_closed"]]
    await callback.message.edit_text(
        f"<b>Панель администратора</b>\n\n"
        f"Сегодня: 🔴 {booked} записей, 🟢 свободно {f'с {free[0]}' if free else 'нет'}\n\n"
        f"Выберите действие:",
        reply_markup=admin_menu_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_ignore")
async def admin_ignore(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    await callback.answer()


@router.callback_query(lambda c: DEMO_MODE and not is_admin(c.from_user.id) and c.data in DEMO_DESCRIPTIONS)
async def demo_button_description(callback: CallbackQuery):
    """В демо-режиме показывает описание кнопки вместо действия."""
    desc = DEMO_DESCRIPTIONS.get(callback.data, "")
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀ Назад в меню", callback_data="admin_menu")
    ]])
    await callback.message.edit_text(desc, reply_markup=kb)
    await callback.answer()


# ================================================================
# Управление (настройки)
# ================================================================

@router.callback_query(F.data == "admin_settings")
async def admin_settings(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        "<b>Управление</b>\n\nВыберите раздел:",
        reply_markup=admin_settings_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_content")
async def admin_content(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await callback.message.edit_text(
        "<b>📋 Контент</b>",
        reply_markup=admin_content_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_tweaks")
async def admin_tweaks(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    repeat_on  = await get_setting("repeat_reminders_enabled") == "1"
    master_on  = await get_setting("master_30min_enabled") == "1"
    dense_on   = await get_setting("dense_schedule") == "1"
    loyalty_on = await get_setting("loyalty_enabled") == "1"
    await callback.message.edit_text(
        "<b>🔧 Настройки</b>",
        reply_markup=admin_tweaks_kb(repeat_on, master_on, dense_on, loyalty_on)
    )
    await callback.answer()


@router.callback_query(F.data == "toggle_repeat_reminders")
async def toggle_repeat(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    current = await get_setting("repeat_reminders_enabled")
    await set_setting("repeat_reminders_enabled", "0" if current == "1" else "1")
    repeat_on = await get_setting("repeat_reminders_enabled") == "1"
    master_on = await get_setting("master_30min_enabled") == "1"
    dense_on  = await get_setting("dense_schedule") == "1"
    loyalty_on  = await get_setting("loyalty_enabled") == "1"
    await callback.message.edit_reply_markup(reply_markup=admin_tweaks_kb(repeat_on, master_on, dense_on, loyalty_on))
    await callback.answer("Напоминания о коррекции: " + ("включены ✅" if repeat_on else "выключены ❌"))


@router.callback_query(F.data == "toggle_dense_schedule")
async def toggle_dense(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    current = await get_setting("dense_schedule")
    await set_setting("dense_schedule", "0" if current == "1" else "1")
    repeat_on = await get_setting("repeat_reminders_enabled") == "1"
    master_on = await get_setting("master_30min_enabled") == "1"
    dense_on  = await get_setting("dense_schedule") == "1"
    loyalty_on  = await get_setting("loyalty_enabled") == "1"
    await callback.message.edit_reply_markup(reply_markup=admin_tweaks_kb(repeat_on, master_on, dense_on, loyalty_on))
    await callback.answer("Плотное расписание: " + ("включено ✅" if dense_on else "выключено ❌"))


@router.callback_query(F.data == "toggle_master_30min")
async def toggle_master(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    current = await get_setting("master_30min_enabled")
    await set_setting("master_30min_enabled", "0" if current == "1" else "1")
    repeat_on = await get_setting("repeat_reminders_enabled") == "1"
    master_on = await get_setting("master_30min_enabled") == "1"
    dense_on  = await get_setting("dense_schedule") == "1"
    loyalty_on  = await get_setting("loyalty_enabled") == "1"
    await callback.message.edit_reply_markup(reply_markup=admin_tweaks_kb(repeat_on, master_on, dense_on, loyalty_on))
    await callback.answer("Уведомление за 30 мин: " + ("включено ✅" if master_on else "выключено ❌"))


# ================================================================
# Программа лояльности
# ================================================================

@router.callback_query(F.data == "loyalty_settings")
async def loyalty_settings_view(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    loyalty_on  = await get_setting("loyalty_enabled") == "1"
    mode        = await get_setting("loyalty_mode") or "discount"
    visits      = await get_setting("loyalty_visits") or "3"
    discount    = await get_setting("loyalty_discount") or "10"
    icon        = "✅" if loyalty_on else "❌"
    mode_icon   = "💰" if mode == "discount" else "🎁"

    if mode == "discount":
        mode_text = f"Режим: {mode_icon} <b>Скидка {discount}%</b> после {visits} визитов"
    else:
        mode_text = f"Режим: {mode_icon} <b>Бесплатный визит</b> каждые {visits} походов"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{icon} Включить/выключить", callback_data="loyalty_toggle")],
        [
            InlineKeyboardButton(
                text=f"{'💰 Скидка' if mode == 'discount' else '💰 Переключить на скидку'}",
                callback_data="loyalty_mode_discount"
            ),
            InlineKeyboardButton(
                text=f"{'🎁 Бесплатный' if mode == 'free_visit' else '🎁 Переключить на бесплатный'}",
                callback_data="loyalty_mode_free"
            ),
        ],
        [
            InlineKeyboardButton(text=f"Каждые визитов: {visits}", callback_data="loyalty_edit_visits"),
        ],
        [
            InlineKeyboardButton(text=f"Скидка: {discount}%", callback_data="loyalty_edit_discount"),
        ] if mode == "discount" else [],
        [InlineKeyboardButton(text="◀ Назад", callback_data="admin_tweaks")],
    ])
    await callback.message.edit_text(
        f"⭐ <b>Программа лояльности</b>\n\n"
        f"Статус: {'включена ✅' if loyalty_on else 'выключена ❌'}\n"
        f"{mode_text}\n\n"
        f"Клиент видит в уведомлении:\n"
        f"• 🆕 Новый клиент — ещё не приходил\n"
        f"• ✅ Проверенный — пришёл хотя бы 1 раз\n"
        f"• ⭐ Постоянный — достиг порога\n"
        f"  {'→ получает скидку' if mode == 'discount' else '→ следующий визит бесплатный'}",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data == "loyalty_toggle")
async def loyalty_toggle(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    current = await get_setting("loyalty_enabled")
    await set_setting("loyalty_enabled", "0" if current == "1" else "1")
    await loyalty_settings_view(callback)


@router.callback_query(F.data == "loyalty_mode_discount")
async def loyalty_mode_discount(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await set_setting("loyalty_mode", "discount")
    await callback.answer("Режим: скидка % ✅")
    await loyalty_settings_view(callback)


@router.callback_query(F.data == "loyalty_mode_free")
async def loyalty_mode_free(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await set_setting("loyalty_mode", "free_visit")
    await callback.answer("Режим: бесплатный визит ✅")
    await loyalty_settings_view(callback)


@router.callback_query(F.data == "loyalty_edit_visits")
async def loyalty_edit_visits(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.loyalty_visits)
    mode    = await get_setting("loyalty_mode") or "discount"
    current = await get_setting("loyalty_visits") or "3"
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀ Отмена", callback_data="loyalty_settings")
    ]])
    label = "скидки" if mode == "discount" else "бесплатного визита"
    await callback.message.edit_text(
        f"⭐ Сейчас: каждые <b>{current}</b> визитов\n\n"
        f"Введите через сколько визитов давать {label} (1-50):",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data == "loyalty_edit_discount")
async def loyalty_edit_discount(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.loyalty_discount)
    current = await get_setting("loyalty_discount") or "10"
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀ Отмена", callback_data="loyalty_settings")
    ]])
    await callback.message.edit_text(
        f"⭐ Сейчас: <b>{current}%</b>\n\nВведите размер скидки в % (1-99):",
        reply_markup=kb
    )
    await callback.answer()


@router.message(AdminStates.loyalty_visits)
async def loyalty_save_visits(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        n = int(message.text.strip())
        if n < 1 or n > 50: raise ValueError
    except ValueError:
        await message.answer("Введите число от 1 до 50:")
        return
    await set_setting("loyalty_visits", str(n))
    await state.clear()
    mode = await get_setting("loyalty_mode") or "discount"
    label = "скидка" if mode == "discount" else "бесплатный визит"
    await message.answer(
        f"✅ {label.capitalize()} — каждые <b>{n}</b> визитов",
        reply_markup=admin_back_kb()
    )


@router.message(AdminStates.loyalty_discount)
async def loyalty_save_discount(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    try:
        n = int(message.text.strip())
        if n < 1 or n > 99: raise ValueError
    except ValueError:
        await message.answer("Введите число от 1 до 99:")
        return
    await set_setting("loyalty_discount", str(n))
    await state.clear()
    await message.answer(f"✅ Скидка установлена: <b>{n}%</b>", reply_markup=admin_back_kb())


# ================================================================
# Расписание
# ================================================================

@router.callback_query(F.data == "admin_view_schedule")
async def admin_view_schedule_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.clear()
    all_dates = await get_available_dates()
    kb = get_admin_calendar("view", all_dates)
    await callback.message.edit_text("<b>Расписание на дату</b>\n\nВыберите дату:", reply_markup=kb)
    await callback.answer()


# ================================================================
# Добавить рабочий день
# ================================================================

@router.callback_query(F.data == "admin_add_day")
async def admin_add_day_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.clear()
    existing = await get_available_dates()
    kb = get_admin_calendar("add_day", existing)
    await callback.message.edit_text(
        "<b>Добавить рабочий день</b>\n\n✅ — уже добавлен  |  цифра — нажать чтобы добавить",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data == "admin_add_by_weekday")
async def admin_add_by_weekday_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.add_by_weekday)
    await state.update_data(selected_weekdays=[])
    await callback.message.edit_text(
        "<b>Добавить по дням недели</b>\n\nОтметьте дни недели:",
        reply_markup=weekday_picker_kb([])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_wd_"), AdminStates.add_by_weekday)
async def admin_weekday_toggle(callback: CallbackQuery, state: FSMContext):
    part = callback.data.removeprefix("adm_wd_")
    if part == "confirm":
        data = await state.get_data()
        selected = data.get("selected_weekdays", [])
        if not selected:
            await callback.answer("Выберите хотя бы один день", show_alert=True)
            return
        await state.update_data(weekday_dates_to_add=selected)
        await state.set_state(AdminStates.add_wd_start)
        weekday_names = ["пн","вт","ср","чт","пт","сб","вс"]
        names = ", ".join(weekday_names[w] for w in sorted(selected))
        await callback.message.edit_text(
            f"Дни: <b>{names}</b>\n\nВыберите <b>начало</b> рабочего дня:",
            reply_markup=time_picker_kb("wd_start", "")
        )
        await callback.answer()
        return
    num = int(part)
    data = await state.get_data()
    selected = list(data.get("selected_weekdays", []))
    if num in selected:
        selected.remove(num)
    else:
        selected.append(num)
    await state.update_data(selected_weekdays=selected)
    await callback.message.edit_reply_markup(reply_markup=weekday_picker_kb(selected))
    await callback.answer()


@router.callback_query(F.data.startswith("adm_t_wd_start__"), AdminStates.add_wd_start)
async def admin_wd_start_picked(callback: CallbackQuery, state: FSMContext):
    start_time = callback.data.split("_")[-1]
    await state.update_data(wd_start=start_time)
    await state.set_state(AdminStates.add_wd_end)
    await callback.message.edit_text(
        f"Начало: <b>{start_time}</b>\n\nВыберите <b>конец</b> рабочего дня:",
        reply_markup=time_picker_kb("wd_end", "")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_t_wd_end__"), AdminStates.add_wd_end)
async def admin_wd_end_picked(callback: CallbackQuery, state: FSMContext, bot: Bot):
    end_time = callback.data.split("_")[-1]
    data = await state.get_data()
    start_time = data["wd_start"]
    selected = data["weekday_dates_to_add"]
    await state.clear()
    if end_time <= start_time:
        await callback.answer("Конец должен быть позже начала!", show_alert=True)
        return
    today = date.today()
    added_days = 0
    already_days = 0
    for i in range(1, 32):
        d = today + timedelta(days=i)
        if d.weekday() in selected:
            n = await add_working_day(d.strftime("%Y-%m-%d"), start_time, end_time)
            if n > 0:
                added_days += 1
            else:
                already_days += 1
    weekday_names = ["пн","вт","ср","чт","пт","сб","вс"]
    names = ", ".join(weekday_names[w] for w in sorted(selected))
    already_str = f"\nУже существовало: <b>{already_days}</b>" if already_days else ""
    await callback.message.edit_text(
        f"<b>Готово!</b>\n\nДни: <b>{names}</b>\nВремя: {start_time}–{end_time}\n"
        f"Добавлено: <b>{added_days}</b>{already_str}",
        reply_markup=admin_menu_kb()
    )
    await callback.answer()


# ================================================================
# Управление слотами
# ================================================================

@router.callback_query(F.data == "admin_manage_slots")
async def admin_manage_slots_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.clear()
    all_dates = await get_available_dates()
    kb = get_admin_calendar("manage", all_dates)
    await callback.message.edit_text("<b>Управление слотами</b>\n\nВыберите дату:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("del_slot_"))
async def admin_delete_slot_cb(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    parts = callback.data.removeprefix("del_slot_").split("_")
    date_str, time_str = parts[0], parts[1]
    success = await remove_slot(date_str, time_str)
    if success:
        await callback.answer(f"Слот {time_str} удалён")
    else:
        await callback.answer("Не удалось удалить", show_alert=True)
    slots = await get_slots_for_date(date_str)
    if slots:
        await callback.message.edit_reply_markup(reply_markup=admin_schedule_full_kb(date_str, slots))
    else:
        await callback.message.edit_text("Все слоты удалены.", reply_markup=admin_menu_kb())
        await state.clear()


# ================================================================
# Закрыть / открыть день
# ================================================================

@router.callback_query(F.data == "admin_close_day")
async def admin_close_day_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.clear()
    all_dates = await get_available_dates()
    kb = get_admin_calendar("close", all_dates)
    await callback.message.edit_text("<b>Закрыть день</b>\n\nВыберите дату:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "admin_open_day")
async def admin_open_day_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.clear()
    all_dates = await get_available_dates()
    kb = get_admin_calendar("open", all_dates)
    await callback.message.edit_text("<b>Открыть день</b>\n\nВыберите дату:", reply_markup=kb)
    await callback.answer()


# ================================================================
# Ручная запись
# ================================================================

@router.callback_query(F.data == "admin_manual_book")
async def admin_manual_book_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.clear()
    all_dates = await get_available_dates()
    kb = get_admin_calendar("manual", all_dates)
    await callback.message.edit_text(
        "<b>Записать клиента вручную</b>\n\nШаг 1: выберите дату", reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("manual_slot_"), AdminStates.manual_service)
async def admin_manual_time_picked(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    time_slot = callback.data.removeprefix("manual_slot_")
    await state.update_data(manual_time=time_slot)
    await state.set_state(AdminStates.manual_name)
    data = await state.get_data()
    await callback.message.edit_text(
        f"Дата: <b>{format_date_ru(data['manual_date'])}</b>\n"
        f"Услуга: <b>{data['manual_service_name']}</b>\n"
        f"Время: <b>{time_slot}</b>\n\nВведите имя клиента:",
        reply_markup=admin_back_kb()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("manual_svc_"), AdminStates.manual_service)
async def admin_manual_service_picked(callback: CallbackQuery, state: FSMContext):
    service_key = callback.data.removeprefix("manual_svc_")
    svc = await get_service_by_key(service_key)
    if not svc:
        await callback.answer("Услуга не найдена", show_alert=True)
        return
    await state.update_data(
        manual_service_key=service_key, manual_service_name=svc["name"],
        manual_service_price=svc["price"], manual_service_slots=svc["slots"],
    )
    data = await state.get_data()
    free = await get_free_slots_for_service(data["manual_date"], svc["slots"])
    if not free:
        await callback.answer(
            f"Нет свободного окна для «{svc['name']}» ({svc['duration_str']}) на эту дату.",
            show_alert=True
        )
        return
    await callback.message.edit_text(
        f"Дата: <b>{format_date_ru(data['manual_date'])}</b>\n"
        f"Услуга: <b>{svc['name']}</b> ({svc['duration_str']})\n\nВыберите время:",
        reply_markup=manual_free_slots_kb(data["manual_date"], free)
    )
    await callback.answer()


@router.message(AdminStates.manual_name)
async def admin_manual_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Имя слишком короткое:")
        return
    await state.update_data(manual_name=name, manual_phone="—")
    await state.set_state(AdminStates.manual_confirm)
    data = await state.get_data()
    svc_line = f"Услуга: <b>{data.get('manual_service_name','')}</b> — {data.get('manual_service_price',0)} руб.\n" if data.get("manual_service_name") else ""
    await message.answer(
        f"<b>Проверьте запись</b>\n\n"
        f"Дата: <b>{format_date_ru(data['manual_date'])}</b>\n"
        f"Время: <b>{data['manual_time']}</b>\n"
        f"{svc_line}"
        f"Имя: <b>{name}</b>\n\nВсё верно?",
        reply_markup=manual_confirm_kb()
    )


@router.callback_query(F.data == "manual_confirm", AdminStates.manual_confirm)
async def admin_manual_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    data = await state.get_data()
    appt_id = await create_manual_appointment(
        client_name=data["manual_name"], phone=data["manual_phone"],
        date=data["manual_date"], time_slot=data["manual_time"],
        service_key=data.get("manual_service_key",""),
        service_name=data.get("manual_service_name",""),
        service_price=data.get("manual_service_price",0),
        slots_count=data.get("manual_service_slots",1),
    )
    await state.clear()
    if not appt_id:
        await callback.message.edit_text("Ошибка: слот занят.", reply_markup=admin_menu_kb())
        await callback.answer()
        return
    await callback.message.edit_text(
        f"<b>Запись добавлена!</b>\n\n"
        f"{format_date_ru(data['manual_date'])}, {data['manual_time']}\n"
        f"{data['manual_name']}",
        reply_markup=admin_menu_kb()
    )
    await schedule_all_jobs(
        bot=bot, appointment_id=appt_id, user_id=0,
        date_str=data["manual_date"], time_slot=data["manual_time"],
        service_key=data.get("manual_service_key", ""),
        service_name=data.get("manual_service_name", ""),
        slots_count=data.get("manual_service_slots", 1),
        client_name=data["manual_name"],
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_sched_page_"))
async def admin_schedule_page(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    parts = callback.data.removeprefix("adm_sched_page_").rsplit("_", 1)
    date_str, page = parts[0], int(parts[1])
    await send_schedule(callback, date_str, page)
    await callback.answer()


# ================================================================
# Отмена записи из расписания
# ================================================================

@router.callback_query(F.data.startswith("adm_cancel_"))
async def admin_cancel_from_schedule(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    appt_id = int(callback.data.removeprefix("adm_cancel_"))
    result = await cancel_appointment(appt_id)
    if not result:
        await callback.answer("Запись не найдена", show_alert=True)
        return
    cancel_all_jobs(appt_id, result)
    date_str = result["date"]
    await callback.answer(f"Запись на {result['time_slot']} отменена")
    if result["user_id"] != 0:
        try:
            await bot.send_message(
                result["user_id"],
                f"<b>Ваша запись отменена</b>\n\n"
                f"{format_date_ru(date_str)}, {result['time_slot']}\n\nДля новой записи нажмите «Записаться»."
            )
        except Exception as e:
            logger.warning(f"Уведомление: {e}")
    await send_schedule(callback, date_str)


# ================================================================
# Перенос записи
# ================================================================

@router.callback_query(F.data.startswith("adm_reschedule_"))
async def admin_reschedule_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    appt_id = int(callback.data.removeprefix("adm_reschedule_"))
    await state.update_data(reschedule_appt_id=appt_id)
    await state.set_state(AdminStates.reschedule_date)
    available = await get_available_dates()
    kb = get_admin_calendar("reschedule", available)
    await callback.message.edit_text(
        "<b>Перенос записи</b>\n\nВыберите новую дату:",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_cal_day_reschedule_"), AdminStates.reschedule_date)
async def admin_reschedule_date_picked(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.removeprefix("adm_cal_day_reschedule_")
    data = await state.get_data()
    appt_id = data["reschedule_appt_id"]

    # Получаем слоты нужной длины для услуги
    appt = await get_appointment_by_id(appt_id)
    if not appt:
        await callback.answer("Запись не найдена", show_alert=True)
        await state.clear()
        return

    free = await get_free_slots_for_service(date_str, appt["slots_count"])
    if not free:
        await callback.answer("Нет свободных слотов на эту дату", show_alert=True)
        return

    await state.update_data(reschedule_new_date=date_str)
    await state.set_state(AdminStates.reschedule_time)
    await callback.message.edit_text(
        f"<b>Перенос записи</b>\n\n"
        f"Новая дата: <b>{format_date_ru(date_str)}</b>\n\n"
        f"Выберите время:",
        reply_markup=manual_free_slots_kb(date_str, free)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("manual_slot_"), AdminStates.reschedule_time)
async def admin_reschedule_time_picked(callback: CallbackQuery, state: FSMContext, bot: Bot):
    new_time = callback.data.removeprefix("manual_slot_")
    data = await state.get_data()
    appt_id = data["reschedule_appt_id"]
    new_date = data["reschedule_new_date"]
    await state.clear()

    result = await reschedule_appointment(appt_id, new_date, new_time)
    if not result:
        await callback.message.edit_text(
            "❌ Не удалось перенести — слот уже занят.",
            reply_markup=admin_menu_kb()
        )
        await callback.answer()
        return

    # Отменяем старые задачи планировщика
    cancel_all_jobs(appt_id, result)

    # Уведомляем клиента
    if result["user_id"] != 0:
        try:
            h, m = map(int, new_time.split(":"))
            end_total = h * 60 + m + result["slots_count"] * SLOT_DURATION
            end_time = f"{end_total // 60:02d}:{end_total % 60:02d}"
            await bot.send_message(
                result["user_id"],
                f"📅 <b>Ваша запись перенесена</b>\n\n"
                f"Было: {format_date_ru(result['old_date'])}, {result['old_slot']}\n"
                f"Стало: <b>{format_date_ru(new_date)}, {new_time} – {end_time}</b>"
            )
        except Exception as e:
            logger.warning(f"Уведомление о переносе: {e}")

    # Планируем новые задачи
    await schedule_all_jobs(
        bot=bot, appointment_id=appt_id, user_id=result["user_id"],
        date_str=new_date, time_slot=new_time,
        service_key="", service_name=result["service_name"],
        slots_count=result["slots_count"], client_name=result["client_name"],
    )

    await callback.message.edit_text(
        f"✅ <b>Запись перенесена!</b>\n\n"
        f"👤 {result['client_name']}\n"
        f"Было: {format_date_ru(result['old_date'])}, {result['old_slot']}\n"
        f"Стало: <b>{format_date_ru(new_date)}, {new_time}</b>",
        reply_markup=admin_menu_kb()
    )
    await callback.answer()


# ================================================================
# Отметка явки клиента
# ================================================================

@router.callback_query(F.data.startswith("attend_yes_"))
async def attend_yes(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    appt_id = int(callback.data.removeprefix("attend_yes_"))
    await mark_attendance(appt_id, True)
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ <b>Клиент пришёл</b> — отмечено в статистике.",
        parse_mode="HTML"
    )
    await callback.answer("✅ Явка отмечена")


@router.callback_query(F.data.startswith("attend_no_"))
async def attend_no(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    appt_id = int(callback.data.removeprefix("attend_no_"))
    await mark_attendance(appt_id, False)
    await callback.message.edit_text(
        callback.message.text + "\n\n❌ <b>Клиент не пришёл</b> — отмечено в статистике.",
        parse_mode="HTML"
    )
    await callback.answer("❌ Неявка отмечена")


    await callback.answer("❌ Неявка отмечена")


# ================================================================
# ЧЁРНЫЙ СПИСОК
# ================================================================

@router.callback_query(F.data == "admin_blacklist")
async def admin_blacklist_view(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.clear()
    blocked = await blacklist_get_all()
    if not blocked:
        text = "<b>🚫 Чёрный список</b>\n\nСписок пуст."
    else:
        text = f"<b>🚫 Чёрный список</b> — {len(blocked)} чел.\n\n"
        for b in blocked:
            name = b["client_name"] or b["username"] or f"ID {b['user_id']}"
            reason = f" — {b['reason']}" if b["reason"] else ""
            text += f"• {name}{reason} /unban_{b['user_id']}\n"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀ Назад", callback_data="admin_content")
    ]])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("adm_ban_"))
async def admin_ban_from_schedule(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    appt_id = int(callback.data.removeprefix("adm_ban_"))
    appt = await get_appointment_by_id(appt_id)
    if not appt or appt["user_id"] == 0:
        await callback.answer("Нельзя заблокировать — ручная запись без Telegram", show_alert=True)
        return
    if appt["user_id"] in ADMIN_IDS:
        await callback.answer("Нельзя заблокировать администратора", show_alert=True)
        return

    await blacklist_add(
        user_id=appt["user_id"],
        client_name=appt["client_name"],
        reason="заблокирован из расписания"
    )

    # Отменяем текущую запись
    result = await cancel_appointment(appt_id)
    if result:
        cancel_all_jobs(appt_id, result)
        try:
            await bot.send_message(
                appt["user_id"],
                "К сожалению, ваша запись отменена и запись через бота для вас недоступна."
            )
        except Exception:
            pass
        await post_schedule_to_channel(bot, result["date"])

    await callback.answer(f"✅ {appt['client_name']} заблокирован", show_alert=True)
    date_str = appt["date"]
    if date_str:
        await send_schedule(callback, date_str)


@router.message(Command("unban"))
async def cmd_unban(message: Message):
    if not is_admin(message.from_user.id):
        return
    try:
        user_id = int(message.text.split("_", 1)[1])
    except (IndexError, ValueError):
        await message.answer("Неверный формат. Используйте /unban_123456789")
        return
    await blacklist_remove(user_id)
    await message.answer(f"✅ Пользователь {user_id} разблокирован.")


# ================================================================
# УПРАВЛЕНИЕ УСЛУГАМИ
# ================================================================

@router.callback_query(F.data == "admin_services")
async def admin_services_list(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.clear()
    services = await get_services(active_only=False)
    await callback.message.edit_text(
        "<b>Управление услугами</b>\n\n"
        "✅ — активна  |  ❌ — отключена\n"
        "Нажмите на услугу для редактирования:",
        reply_markup=admin_services_kb(services)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("svc_edit_"))
async def svc_edit(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    svc_id = int(callback.data.removeprefix("svc_edit_"))
    services = await get_services(active_only=False)
    svc = next((s for s in services if s["id"] == svc_id), None)
    if not svc:
        await callback.answer("Услуга не найдена", show_alert=True)
        return
    await state.update_data(edit_svc_id=svc_id)
    repeat_str = f"{svc['repeat_days']} дн." if svc["repeat_days"] else "выкл"
    await callback.message.edit_text(
        f"<b>{svc['emoji']} {svc['name']}</b>\n\n"
        f"💰 Цена: {svc['price']} руб.\n"
        f"⏱ Длительность: {svc['duration_str']} ({svc['slots']} слотов по {SLOT_DURATION} мин)\n"
        f"🔁 Напомнить через: {repeat_str}\n"
        f"Статус: {'✅ активна' if svc['is_active'] else '❌ отключена'}",
        reply_markup=admin_service_detail_kb(svc_id, svc["is_active"])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("svc_toggle_"))
async def svc_toggle(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    svc_id = int(callback.data.removeprefix("svc_toggle_"))
    await toggle_service(svc_id)
    await callback.answer("Статус услуги изменён")
    # Обновить отображение
    services = await get_services(active_only=False)
    svc = next((s for s in services if s["id"] == svc_id), None)
    if svc:
        repeat_str = f"{svc['repeat_days']} дн." if svc["repeat_days"] else "выкл"
        await callback.message.edit_text(
            f"<b>{svc['emoji']} {svc['name']}</b>\n\n"
            f"💰 Цена: {svc['price']} руб.\n"
            f"⏱ Длительность: {svc['duration_str']} ({svc['slots']} слотов по {SLOT_DURATION} мин)\n"
            f"🔁 Напомнить через: {repeat_str}\n"
            f"Статус: {'✅ активна' if svc['is_active'] else '❌ отключена'}",
            reply_markup=admin_service_detail_kb(svc_id, svc["is_active"])
        )


# Редактирование полей услуги
@router.callback_query(F.data.startswith("svc_field_"))
async def svc_field_edit(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    parts = callback.data.removeprefix("svc_field_").split("_", 1)
    field, svc_id = parts[0], int(parts[1])
    await state.update_data(edit_svc_id=svc_id, edit_field=field)

    prompts = {
        "name":   ("AdminStates.svc_name",   "Введите новое <b>название</b> услуги:"),
        "price":  ("AdminStates.svc_price",  "Введите новую <b>цену</b> (только число):"),
        "slots":  ("AdminStates.svc_slots",  f"Введите <b>количество слотов</b> по {SLOT_DURATION} мин\n(1={SLOT_DURATION}мин, 2={SLOT_DURATION*2}мин, {60//SLOT_DURATION}={60}мин):"),
        "emoji":  ("AdminStates.svc_emoji",  "Введите <b>эмодзи</b> для услуги:"),
        "repeat": ("AdminStates.svc_repeat", "Через сколько <b>дней</b> напомнить о коррекции?\n(0 — не напоминать):"),
    }

    state_map = {
        "name":   AdminStates.svc_name,
        "price":  AdminStates.svc_price,
        "slots":  AdminStates.svc_slots,
        "emoji":  AdminStates.svc_emoji,
        "repeat": AdminStates.svc_repeat,
    }

    _, prompt = prompts.get(field, ("", "Введите значение:"))
    await state.set_state(state_map[field])
    await callback.message.edit_text(prompt, reply_markup=admin_back_kb())
    await callback.answer()


async def _save_svc_field(message: Message, state: FSMContext, field: str, value):
    data = await state.get_data()
    svc_id = data["edit_svc_id"]
    services = await get_services(active_only=False)
    svc = next((s for s in services if s["id"] == svc_id), None)
    if not svc:
        await state.clear()
        return
    # Обновить нужное поле
    kwargs = {
        "name":        svc["name"],
        "price":       svc["price"],
        "slots":       svc["slots"],
        "duration_str":svc["duration_str"],
        "emoji":       svc["emoji"],
        "repeat_days": svc["repeat_days"],
    }
    if field == "slots":
        kwargs["slots"] = value
        kwargs["duration_str"] = f"~{value * SLOT_DURATION} мин" if value * SLOT_DURATION < 60 else f"~{value * SLOT_DURATION // 60} ч"
    else:
        kwargs[field] = value
    await update_service(svc_id, **kwargs)
    await state.clear()
    # Показать обновлённую услугу
    services = await get_services(active_only=False)
    svc = next((s for s in services if s["id"] == svc_id), None)
    repeat_str = f"{svc['repeat_days']} дн." if svc["repeat_days"] else "выкл"
    await message.answer(
        f"✅ Изменено!\n\n"
        f"<b>{svc['emoji']} {svc['name']}</b>\n\n"
        f"💰 Цена: {svc['price']} руб.\n"
        f"⏱ Длительность: {svc['duration_str']} ({svc['slots']} слотов)\n"
        f"🔁 Напомнить через: {repeat_str}",
        reply_markup=admin_service_detail_kb(svc_id, svc["is_active"])
    )



# Добавить новую услугу
@router.callback_query(F.data == "svc_add")
async def svc_add_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.update_data(edit_svc_id=None, adding_new=True,
                             new_svc={"emoji":"💅","price":0,"slots":1,"duration_str":f"~{SLOT_DURATION} мин","repeat_days":0})
    await state.set_state(AdminStates.svc_name)
    await callback.message.edit_text(
        "<b>Новая услуга</b>\n\nВведите <b>название</b>:", reply_markup=admin_back_kb()
    )
    await callback.answer()


@router.message(AdminStates.svc_name)
async def svc_new_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    if data.get("adding_new"):
        name = message.text.strip()
        if len(name) < 2:
            await message.answer("Название слишком короткое:")
            return
        new_svc = data.get("new_svc", {})
        new_svc["name"] = name
        import re, unicodedata
        key = re.sub(r'[^a-z0-9_]', '', name.lower().replace(' ','_'))[:20] or f"svc_{len(name)}"
        new_svc["key"] = key
        await state.update_data(new_svc=new_svc)
        await state.set_state(AdminStates.svc_price)
        await message.answer(f"Название: <b>{name}</b>\n\nВведите <b>цену</b> в рублях:",
                             reply_markup=admin_back_kb())
        return
    # Если редактирование существующей
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Название слишком короткое:")
        return
    await _save_svc_field(message, state, "name", name)


@router.message(AdminStates.svc_price)
async def svc_new_price(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    if data.get("adding_new"):
        try:
            price = int(message.text.strip())
            if price < 0: raise ValueError
        except ValueError:
            await message.answer("Введите целое число:")
            return
        new_svc = data.get("new_svc", {})
        new_svc["price"] = price
        await state.update_data(new_svc=new_svc)
        await state.set_state(AdminStates.svc_slots)
        await message.answer(
            f"Цена: <b>{price} руб.</b>\n\nВведите <b>кол-во слотов</b> по {SLOT_DURATION} мин\n(1={SLOT_DURATION}мин, {60//SLOT_DURATION}=1час):",
            reply_markup=admin_back_kb()
        )
        return
    try:
        price = int(message.text.strip())
        if price < 0: raise ValueError
    except ValueError:
        await message.answer("Введите целое число (цена в рублях):")
        return
    await _save_svc_field(message, state, "price", price)


@router.message(AdminStates.svc_slots)
async def svc_new_slots(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    if data.get("adding_new"):
        try:
            slots = int(message.text.strip())
            if slots < 1 or slots > 20: raise ValueError
        except ValueError:
            await message.answer("Введите число от 1 до 20:")
            return
        new_svc = data.get("new_svc", {})
        new_svc["slots"] = slots
        new_svc["duration_str"] = f"~{slots*SLOT_DURATION} мин" if slots*SLOT_DURATION < 60 else f"~{slots*SLOT_DURATION//60} ч"
        await state.update_data(new_svc=new_svc)
        await state.set_state(AdminStates.svc_repeat)
        await message.answer(
            f"Длительность: <b>{new_svc['duration_str']}</b>\n\n"
            f"Через сколько <b>дней</b> напомнить о коррекции? (0 = не напоминать):",
            reply_markup=admin_back_kb()
        )
        return
    try:
        slots = int(message.text.strip())
        if slots < 1 or slots > 20: raise ValueError
    except ValueError:
        await message.answer("Введите число от 1 до 20:")
        return
    await _save_svc_field(message, state, "slots", slots)


@router.message(AdminStates.svc_repeat)
async def svc_new_repeat(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    data = await state.get_data()
    if data.get("adding_new"):
        try:
            days = int(message.text.strip())
            if days < 0: raise ValueError
        except ValueError:
            await message.answer("Введите число дней (0 = не напоминать):")
            return
        new_svc = data.get("new_svc", {})
        new_svc["repeat_days"] = days
        # Сохранить услугу
        success = await add_service(
            key=new_svc["key"], name=new_svc["name"],
            price=new_svc["price"], slots=new_svc["slots"],
            duration_str=new_svc["duration_str"], emoji=new_svc.get("emoji","💅"),
            repeat_days=days
        )
        await state.clear()
        if success:
            await message.answer(
                f"✅ <b>Услуга добавлена!</b>\n\n"
                f"💅 {new_svc['name']} — {new_svc['price']} руб.\n"
                f"⏱ {new_svc['duration_str']}",
                reply_markup=admin_menu_kb()
            )
        else:
            await message.answer("Ошибка: возможно услуга с таким ключом уже существует.",
                                 reply_markup=admin_menu_kb())
        return
    try:
        days = int(message.text.strip())
        if days < 0: raise ValueError
    except ValueError:
        await message.answer("Введите число дней (0 = не напоминать):")
        return
    await _save_svc_field(message, state, "repeat_days", days)


@router.message(AdminStates.svc_emoji)
async def svc_save_emoji(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    emoji = message.text.strip()
    await _save_svc_field(message, state, "emoji", emoji)


# ================================================================
# Единый обработчик нажатия на день (adm_cal_day_)
# ================================================================

@router.callback_query(F.data.startswith("adm_cal_day_"))
async def admin_cal_day(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    rest = callback.data.removeprefix("adm_cal_day_")
    date_str = rest[-10:]
    action = rest[:-11]

    if action == "view":
        await state.clear()
        await send_schedule(callback, date_str)

    elif action == "add_day":
        d = date.fromisoformat(date_str)
        if d < date.today():
            await callback.answer("Нельзя добавить прошедшую дату", show_alert=True)
            return
        await state.update_data(new_day_date=date_str)
        await state.set_state(AdminStates.add_day_start)
        await callback.message.edit_text(
            f"<b>{format_date_ru(date_str)}</b>\n\nВыберите <b>начало</b> рабочего дня:",
            reply_markup=time_picker_kb("daystart", date_str)
        )

    elif action == "manage":
        slots = await get_slots_for_date(date_str)
        if not slots:
            await callback.message.edit_text(
                f"<b>{format_date_ru(date_str)}</b>\n\nНа этот день нет слотов.",
                reply_markup=admin_menu_kb()
            )
        else:
            await callback.message.edit_text(
                f"<b>{format_date_ru(date_str)}</b>\n\n🟢 ✕ — нажать чтобы удалить",
                reply_markup=admin_schedule_full_kb(date_str, slots)
            )
        await state.set_state(AdminStates.remove_slot_time)

    elif action == "close":
        # Получаем записи на этот день перед закрытием
        booked_slots = await get_schedule_for_date(date_str)
        seen = set()
        booked_appts = [s for s in booked_slots if s["is_booked"] and s["appt_id"]
                        and not seen.add(s["appt_id"])]

        await close_day(date_str)
        await state.clear()
        await callback.message.edit_text(
            f"<b>День закрыт</b>\n\n{format_date_ru(date_str)}", reply_markup=admin_menu_kb()
        )

        # Уведомляем клиентов у которых есть записи
        for appt in booked_appts:
            if appt["user_id"] and appt["user_id"] != 0:
                try:
                    await bot.send_message(
                        appt["user_id"],
                        f"⚠️ <b>Ваша запись отменена</b>\n\n"
                        f"К сожалению, {format_date_ru(date_str)} мастер не работает.\n"
                        f"Пожалуйста, запишитесь на другое время.",
                    )
                except Exception as e:
                    logger.warning(f"Уведомление при закрытии дня: {e}")

    elif action == "open":
        await open_day(date_str)
        await state.clear()
        await callback.message.edit_text(
            f"<b>День открыт</b>\n\n{format_date_ru(date_str)}", reply_markup=admin_menu_kb()
        )

    elif action == "manual":
        free = await get_free_slots(date_str)
        if not free:
            await callback.answer("Нет свободных слотов", show_alert=True)
            return
        await state.update_data(manual_date=date_str)
        await state.set_state(AdminStates.manual_service)
        services = await get_services(active_only=True)
        await callback.message.edit_text(
            f"<b>Записать клиента</b>\n\nДата: <b>{format_date_ru(date_str)}</b>\n\nВыберите услугу:",
            reply_markup=manual_services_kb(services)
        )

    await callback.answer()


# ================================================================
# Выбор начала/конца рабочего дня
# ================================================================

@router.callback_query(F.data.startswith("adm_t_daystart_"), AdminStates.add_day_start)
async def admin_day_start_picked(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    parts = callback.data.removeprefix("adm_t_daystart_").rsplit("_", 1)
    date_str, start_time = parts[0], parts[1]
    await state.update_data(new_day_start=start_time)
    await state.set_state(AdminStates.add_day_end)
    await callback.message.edit_text(
        f"<b>{format_date_ru(date_str)}</b>\nНачало: <b>{start_time}</b>\n\nВыберите <b>конец</b>:",
        reply_markup=time_picker_kb("dayend", date_str)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_t_dayend_"), AdminStates.add_day_end)
async def admin_day_end_picked(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    parts = callback.data.removeprefix("adm_t_dayend_").rsplit("_", 1)
    date_str, end_time = parts[0], parts[1]
    data = await state.get_data()
    start_time = data["new_day_start"]
    await state.clear()
    if end_time <= start_time:
        await callback.answer("Конец должен быть позже начала!", show_alert=True)
        return
    added = await add_working_day(date_str, start_time, end_time)
    await callback.message.edit_text(
        f"<b>Окно добавлено!</b>\n\n"
        f"📅 {format_date_ru(date_str)}\n"
        f"🕐 {start_time} – {end_time}\n"
        f"⏰ Слотов добавлено: <b>{added}</b>\n\n"
        f"Хотите добавить ещё одно окно на этот день?",
        reply_markup=add_another_window_kb(date_str)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_add_window_"))
async def admin_add_another_window(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    date_str = callback.data.removeprefix("adm_add_window_")
    await state.update_data(new_day_date=date_str)
    await state.set_state(AdminStates.add_day_start)
    slots = await get_slots_for_date(date_str)
    busy = [s["time"] for s in slots if not s["is_closed"]]
    busy_str = f"Уже добавлено: {busy[0]}–{busy[-1]}\n" if busy else ""
    await callback.message.edit_text(
        f"<b>{format_date_ru(date_str)}</b>\n{busy_str}\nВыберите <b>начало</b> нового окна:",
        reply_markup=time_picker_kb("daystart", date_str)
    )
    await callback.answer()


# ================================================================
# Навигация по календарю
# ================================================================

@router.callback_query(F.data.startswith("adm_cal_nav_"))
async def admin_cal_nav(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    parts = callback.data.removeprefix("adm_cal_nav_").rsplit("_", 2)
    action, year_s, month_s = parts[0], parts[1], parts[2]
    year, month = int(year_s), int(month_s)
    existing = await get_available_dates()
    kb = build_admin_calendar(year, month, existing, action)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


# ================================================================
# Статистика
# ================================================================

MONTHS_RU = ["","январь","февраль","март","апрель","май","июнь",
             "июль","август","сентябрь","октябрь","ноябрь","декабрь"]


@router.callback_query(F.data == "admin_stats")
async def admin_stats_menu(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text("<b>Статистика</b>\n\nВыберите период:", reply_markup=admin_stats_kb())
    await callback.answer()


@router.callback_query(F.data == "stats_alltime")
async def stats_alltime(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    s = await get_stats_alltime()
    text = "<b>За всё время</b>\n\n"
    text += f"Записей: <b>{s['total']}</b>\n"
    text += f"Клиентов: <b>{s['unique_clients']}</b>\n"
    text += f"Выручка: <b>{s['revenue']} руб.</b>\n"
    if s["attended"] or s["no_show"]:
        text += f"Явка: ✅ {s['attended']} / ❌ {s['no_show']}\n"
    if s["by_service"]:
        text += "\n<b>По услугам:</b>\n"
        for n, c in s["by_service"]:
            text += f"  • {n}: {c}\n"
    if s["by_month"]:
        text += "\n<b>По месяцам:</b>\n"
        for ms, c in s["by_month"]:
            y, m = ms.split("-")
            text += f"  {MONTHS_RU[int(m)]} {y}: {'▓'*min(c,15)} <b>{c}</b>\n"
    await callback.message.edit_text(text, reply_markup=admin_stats_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("stats_month_"))
async def stats_month(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    _, _, year_str, month_str = callback.data.split("_")
    year, month = int(year_str), int(month_str)
    s = await get_stats_month(year, month)
    text = f"<b>{MONTHS_RU[month]} {year}</b>\n\n"
    text += f"Записей: <b>{s['total']}</b>\n"
    text += f"Клиентов: <b>{s['unique_clients']}</b>\n"
    text += f"Новых: <b>{s['new_clients']}</b>\n"
    text += f"Выручка: <b>{s['revenue']} руб.</b>\n"
    if s["attended"] or s["no_show"]:
        text += f"Явка: ✅ {s['attended']} пришли / ❌ {s['no_show']} нет\n"
    if s["by_service"]:
        text += "\n<b>По услугам:</b>\n"
        for n, c in s["by_service"]:
            text += f"  • {n}: {c}\n"
    await callback.message.edit_text(text, reply_markup=admin_stats_kb())
    await callback.answer()


# ================================================================
# РАССЫЛКА ВСЕМ КЛИЕНТАМ
# ================================================================

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    from database.db import get_all_user_ids
    user_ids = await get_all_user_ids()
    await state.set_state(AdminStates.broadcast_text)
    await state.update_data(broadcast_user_ids=user_ids)
    await callback.message.edit_text(
        f"📣 <b>Рассылка</b>\n\n"
        f"Получателей: <b>{len(user_ids)}</b> клиентов\n\n"
        f"Напишите сообщение для рассылки.\n"
        f"Поддерживается текст, фото, видео — просто отправьте нужное.",
        reply_markup=admin_back_kb()
    )
    await callback.answer()


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    from database.db import get_all_user_ids
    user_ids = await get_all_user_ids()
    await state.set_state(AdminStates.broadcast_text)
    await state.update_data(broadcast_user_ids=user_ids)
    await message.answer(
        f"📣 <b>Рассылка</b>\n\n"
        f"Получателей: <b>{len(user_ids)}</b> клиентов\n\n"
        f"Напишите сообщение для рассылки.\n"
        f"Поддерживается текст, фото, видео — просто отправьте нужное.",
        reply_markup=admin_back_kb()
    )


@router.message(AdminStates.broadcast_text)
async def admin_broadcast_preview(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    # Сохраняем message_id для последующей пересылки
    await state.update_data(
        broadcast_message_id=message.message_id,
        broadcast_chat_id=message.chat.id
    )
    await state.set_state(AdminStates.broadcast_confirm)

    data = await state.get_data()
    count = len(data.get("broadcast_user_ids", []))

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"✅ Отправить {count} клиентам",
                                 callback_data="broadcast_send"),
            InlineKeyboardButton(text="❌ Отменить",
                                 callback_data="broadcast_cancel"),
        ]
    ])
    await message.answer(
        f"👆 <b>Предпросмотр сообщения выше</b>\n\n"
        f"Отправить <b>{count}</b> клиентам?",
        reply_markup=kb
    )


@router.callback_query(F.data == "broadcast_send", AdminStates.broadcast_confirm)
async def admin_broadcast_send(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    user_ids = data.get("broadcast_user_ids", [])
    message_id = data.get("broadcast_message_id")
    chat_id = data.get("broadcast_chat_id")
    await state.clear()

    await callback.message.edit_text(
        f"📤 Отправляю рассылку <b>{len(user_ids)}</b> клиентам..."
    )

    sent = 0
    failed = 0
    for user_id in user_ids:
        try:
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=chat_id,
                message_id=message_id
            )
            sent += 1
        except Exception as e:
            err = str(e)
            if "RetryAfter" in err or "Too Many Requests" in err:
                # Извлекаем время ожидания и делаем паузу
                import re
                wait = int(re.search(r'\d+', err).group() or 5)
                await asyncio.sleep(wait)
                try:
                    await bot.copy_message(chat_id=user_id, from_chat_id=chat_id, message_id=message_id)
                    sent += 1
                except Exception:
                    failed += 1
            else:
                failed += 1
        await asyncio.sleep(0.05)

    await callback.message.edit_text(
        f"📣 <b>Рассылка завершена</b>\n\n"
        f"✅ Отправлено: <b>{sent}</b>\n"
        f"❌ Не доставлено: <b>{failed}</b>\n\n"
        f"<i>Не доставлено — клиенты заблокировали бота.</i>",
        reply_markup=admin_menu_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "broadcast_cancel")
async def admin_broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    await callback.message.edit_text(
        "❌ Рассылка отменена.", reply_markup=admin_menu_kb()
    )
    await callback.answer()
