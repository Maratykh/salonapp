# keyboards/admin_kb.py

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def admin_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📅 Расписание на дату",      callback_data="admin_view_schedule"))
    builder.row(
        InlineKeyboardButton(text="➕ Добавить рабочий день",           callback_data="admin_add_day"),
        InlineKeyboardButton(text="🗓 По дням недели",                  callback_data="admin_add_by_weekday"),
    )
    builder.row(InlineKeyboardButton(text="📝 Записать клиента",        callback_data="admin_manual_book"))
    builder.row(InlineKeyboardButton(text="⚙️ Управление",              callback_data="admin_settings"))
    return builder.as_markup()


def admin_settings_kb(repeat_on: bool, master_on: bool, dense_on: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💄 Услуги",     callback_data="admin_services"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
    )
    builder.row(InlineKeyboardButton(text="📣 Рассылка", callback_data="admin_broadcast"))
    builder.row(InlineKeyboardButton(text="⏰ Управление слотами", callback_data="admin_manage_slots"))
    builder.row(
        InlineKeyboardButton(text="🔒 Закрыть день", callback_data="admin_close_day"),
        InlineKeyboardButton(text="🔓 Открыть день", callback_data="admin_open_day"),
    )
    repeat_icon = "✅" if repeat_on else "❌"
    master_icon = "✅" if master_on else "❌"
    dense_icon  = "✅" if dense_on  else "❌"
    builder.row(InlineKeyboardButton(
        text=f"{repeat_icon} Напоминания о коррекции",
        callback_data="toggle_repeat_reminders"
    ))
    builder.row(InlineKeyboardButton(
        text=f"{master_icon} Уведомление мастеру за 30 мин",
        callback_data="toggle_master_30min"
    ))
    builder.row(InlineKeyboardButton(
        text=f"{dense_icon} Плотное расписание",
        callback_data="toggle_dense_schedule"
    ))
    builder.row(InlineKeyboardButton(text="◀ Назад", callback_data="admin_menu"))
    return builder.as_markup()


def admin_stats_kb() -> InlineKeyboardMarkup:
    from datetime import date
    now = date.today()
    prev_month = now.month - 1 if now.month > 1 else 12
    prev_year  = now.year if now.month > 1 else now.year - 1
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📈 За всё время", callback_data="stats_alltime"))
    builder.row(InlineKeyboardButton(
        text=f"📅 Этот месяц ({now.month:02d}.{now.year})",
        callback_data=f"stats_month_{now.year}_{now.month}"
    ))
    builder.row(InlineKeyboardButton(
        text=f"📅 Прошлый месяц ({prev_month:02d}.{prev_year})",
        callback_data=f"stats_month_{prev_year}_{prev_month}"
    ))
    builder.row(InlineKeyboardButton(text="◀ Назад", callback_data="admin_menu"))
    return builder.as_markup()


def admin_services_kb(services: list) -> InlineKeyboardMarkup:
    """Список услуг для управления."""
    builder = InlineKeyboardBuilder()
    for svc in services:
        status = "✅" if svc["is_active"] else "❌"
        builder.row(InlineKeyboardButton(
            text=f"{status} {svc['emoji']} {svc['name']} — {svc['price']} руб.",
            callback_data=f"svc_edit_{svc['id']}"
        ))
    builder.row(InlineKeyboardButton(text="➕ Добавить услугу", callback_data="svc_add"))
    builder.row(InlineKeyboardButton(text="◀ Назад",            callback_data="admin_menu"))
    return builder.as_markup()


def admin_service_detail_kb(svc_id: int, is_active: bool) -> InlineKeyboardMarkup:
    """Кнопки управления одной услугой."""
    toggle_text = "❌ Отключить" if is_active else "✅ Включить"
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✏️ Изменить название", callback_data=f"svc_field_name_{svc_id}"))
    builder.row(
        InlineKeyboardButton(text="💰 Цену",         callback_data=f"svc_field_price_{svc_id}"),
        InlineKeyboardButton(text="⏱ Длительность", callback_data=f"svc_field_slots_{svc_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="😀 Эмодзи",        callback_data=f"svc_field_emoji_{svc_id}"),
        InlineKeyboardButton(text="🔁 Напомнить через", callback_data=f"svc_field_repeat_{svc_id}"),
    )
    builder.row(InlineKeyboardButton(text=toggle_text, callback_data=f"svc_toggle_{svc_id}"))
    builder.row(InlineKeyboardButton(text="◀ Назад к услугам", callback_data="admin_services"))
    return builder.as_markup()


def time_picker_kb(action: str, date_str: str = "") -> InlineKeyboardMarkup:
    from config import SLOT_DURATION
    builder = InlineKeyboardBuilder()
    # Генерируем слоты с 08:00 до 21:00 с шагом SLOT_DURATION
    current = 8 * 60
    end     = 21 * 60
    while current <= end:
        h, m = divmod(current, 60)
        t = f"{h:02d}:{m:02d}"
        builder.button(text=t, callback_data=f"adm_t_{action}_{date_str}_{t}")
        current += SLOT_DURATION
    builder.adjust(5)
    builder.row(InlineKeyboardButton(text="◀ Назад в меню", callback_data="admin_menu"))
    return builder.as_markup()


def admin_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀ Назад в меню", callback_data="admin_menu")
    ]])


def admin_schedule_kb(date_str: str, slots: list, page: int = 0) -> InlineKeyboardMarkup:
    PER_PAGE = 5
    builder = InlineKeyboardBuilder()
    seen = set()
    unique = []
    for s in slots:
        if s["is_booked"] and s["appt_id"] and s["appt_id"] not in seen:
            seen.add(s["appt_id"])
            unique.append(s)

    total = len(unique)
    start = page * PER_PAGE
    page_items = unique[start:start + PER_PAGE]

    for s in page_items:
        svc = f" ({s['service_name']})" if s.get("service_name") else ""
        builder.row(InlineKeyboardButton(
            text=f"🔴 {s['time']} — {s['client_name']}{svc}",
            callback_data="admin_ignore"
        ))
        builder.row(
            InlineKeyboardButton(text="📅 Перенести", callback_data=f"adm_reschedule_{s['appt_id']}"),
            InlineKeyboardButton(text="✕ Отменить",  callback_data=f"adm_cancel_{s['appt_id']}"),
        )

    if not unique:
        builder.row(InlineKeyboardButton(text="— записей нет —", callback_data="admin_ignore"))

    # Навигация по страницам
    if total > PER_PAGE:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀", callback_data=f"adm_sched_page_{date_str}_{page - 1}"))
        nav.append(InlineKeyboardButton(
            text=f"{page + 1}/{(total + PER_PAGE - 1) // PER_PAGE}",
            callback_data="admin_ignore"
        ))
        if start + PER_PAGE < total:
            nav.append(InlineKeyboardButton(text="▶", callback_data=f"adm_sched_page_{date_str}_{page + 1}"))
        builder.row(*nav)

    builder.row(InlineKeyboardButton(text="◀ Назад в меню", callback_data="admin_menu"))
    return builder.as_markup()


def admin_schedule_full_kb(date_str: str, slots: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for slot in slots:
        if not slot["is_booked"] and not slot["is_closed"]:
            builder.button(text=f"🟢 {slot['time']} ✕", callback_data=f"del_slot_{date_str}_{slot['time']}")
        elif slot["is_booked"]:
            builder.button(text=f"🔴 {slot['time']}", callback_data="admin_ignore")
        else:
            builder.button(text=f"⚫ {slot['time']}", callback_data="admin_ignore")
    builder.adjust(4)
    builder.row(InlineKeyboardButton(text="◀ Назад в меню", callback_data="admin_menu"))
    return builder.as_markup()


def manual_confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="manual_confirm"),
        InlineKeyboardButton(text="❌ Отменить",    callback_data="admin_menu"),
    )
    return builder.as_markup()


def manual_free_slots_kb(date_str: str, slots: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for slot in slots:
        builder.button(text=f"🕐 {slot}", callback_data=f"manual_slot_{slot}")
    builder.adjust(4)
    builder.row(InlineKeyboardButton(text="◀ Назад", callback_data="admin_manual_book"))
    return builder.as_markup()


def manual_services_kb(services: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for svc in services:
        builder.row(InlineKeyboardButton(
            text=f"{svc['emoji']} {svc['name']} — {svc['price']} руб. ({svc['duration_str']})",
            callback_data=f"manual_svc_{svc['key']}"
        ))
    builder.row(InlineKeyboardButton(text="◀ Назад в меню", callback_data="admin_menu"))
    return builder.as_markup()


def weekday_picker_kb(selected: list) -> InlineKeyboardMarkup:
    days = [("Пн",0),("Вт",1),("Ср",2),("Чт",3),("Пт",4),("Сб",5),("Вс",6)]
    builder = InlineKeyboardBuilder()
    for name, num in days:
        mark = "✅" if num in selected else "◻️"
        builder.button(text=f"{mark} {name}", callback_data=f"adm_wd_{num}")
    builder.adjust(4)
    if selected:
        builder.row(InlineKeyboardButton(text="✔️ Добавить выбранные", callback_data="adm_wd_confirm"))
    builder.row(InlineKeyboardButton(text="◀ Назад", callback_data="admin_menu"))
    return builder.as_markup()
