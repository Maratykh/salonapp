# keyboards/user_kb.py

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 Записаться",   callback_data="book"),
        InlineKeyboardButton(text="📋 Мои записи",   callback_data="my_appointments"),
    )
    builder.row(
        InlineKeyboardButton(text="💅 Прайсы",       callback_data="prices"),
        InlineKeyboardButton(text="🖼 Портфолио",    callback_data="portfolio"),
    )
    builder.row(
        InlineKeyboardButton(text="📍 Как добраться", callback_data="how_to_get"),
    )
    if is_admin:
        builder.row(
            InlineKeyboardButton(text="🔧 Панель администратора", callback_data="admin_menu")
        )
    return builder.as_markup()


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    ]])


def time_slots_kb(slots: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for slot in slots:
        builder.button(text=f"🕐 {slot}", callback_data=f"slot_{slot}")
    builder.adjust(3)
    builder.row(
        InlineKeyboardButton(text="◀ Назад", callback_data="back_to_calendar"),
        InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu"),
    )
    return builder.as_markup()


def services_kb(services: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for svc in services:
        builder.row(InlineKeyboardButton(
            text=f"{svc['emoji']} {svc['name']} — {svc['price']} руб. ({svc['duration_str']})",
            callback_data=f"service_{svc['key']}"
        ))
    builder.row(
        InlineKeyboardButton(text="◀ Назад", callback_data="back_to_date"),
        InlineKeyboardButton(text="🏠 В меню", callback_data="main_menu"),
    )
    return builder.as_markup()


def confirm_booking_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_booking"),
        InlineKeyboardButton(text="❌ Отменить",    callback_data="cancel_booking_process"),
    )
    return builder.as_markup()


def my_appointment_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отменить запись", callback_data="user_cancel_confirm"))
    builder.row(InlineKeyboardButton(text="🏠 Главное меню",   callback_data="main_menu"))
    return builder.as_markup()


def cancel_confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, отменить",  callback_data="user_cancel_appointment"),
        InlineKeyboardButton(text="◀ Назад",          callback_data="my_appointments"),
    )
    return builder.as_markup()


def portfolio_kb() -> InlineKeyboardMarkup:
    from config import PORTFOLIO_LINK, PORTFOLIO_BUTTON_TEXT
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=PORTFOLIO_BUTTON_TEXT, url=PORTFOLIO_LINK)
    ], [
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    ]])


def cancel_action_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отмена", callback_data="main_menu")
    ]])
