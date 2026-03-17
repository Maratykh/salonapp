# utils/admin_calendar.py — Отдельный календарь для админки
# Использует prefix "adm_cal_" чтобы не конфликтовать с пользовательским

import calendar
from datetime import date, timedelta
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

MONTHS_RU = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
             "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def build_admin_calendar(
    year: int, month: int,
    available_dates: list,  # даты которые подсвечиваются ✅
    action: str             # передаётся в callback чтобы знать что делать
) -> InlineKeyboardMarkup:
    today = date.today()
    avail_set = set(available_dates)
    buttons = []

    # Навигация
    nav_row = []
    prev_m, prev_y = (month - 1, year) if month > 1 else (12, year - 1)
    next_m, next_y = (month + 1, year) if month < 12 else (1, year + 1)

    if (prev_y, prev_m) >= (today.year, today.month):
        nav_row.append(InlineKeyboardButton(
            text="◀",
            callback_data=f"adm_cal_nav_{action}_{prev_y}_{prev_m}"
        ))
    else:
        nav_row.append(InlineKeyboardButton(text=" ", callback_data="admin_ignore"))

    nav_row.append(InlineKeyboardButton(
        text=f"{MONTHS_RU[month]} {year}", callback_data="admin_ignore"
    ))

    max_date = today + timedelta(days=31)
    if date(next_y, next_m, 1) <= max_date:
        nav_row.append(InlineKeyboardButton(
            text="▶",
            callback_data=f"adm_cal_nav_{action}_{next_y}_{next_m}"
        ))
    else:
        nav_row.append(InlineKeyboardButton(text=" ", callback_data="admin_ignore"))

    buttons.append(nav_row)

    # Дни недели
    buttons.append([
        InlineKeyboardButton(text=d, callback_data="admin_ignore")
        for d in WEEKDAYS_RU
    ])

    # Дни
    cal = calendar.monthcalendar(year, month)
    for week in cal:
        row = []
        for day_num in week:
            if day_num == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="admin_ignore"))
            else:
                day_date = date(year, month, day_num)
                date_str = day_date.strftime("%Y-%m-%d")
                if day_date < today:
                    # Прошедшие — серая точка, некликабельно
                    row.append(InlineKeyboardButton(text="·", callback_data="admin_ignore"))
                elif date_str in avail_set:
                    # Уже есть слоты — зелёная галочка, кликабельно
                    row.append(InlineKeyboardButton(
                        text=f"✅{day_num}",
                        callback_data=f"adm_cal_day_{action}_{date_str}"
                    ))
                else:
                    # Будущий день без слотов — просто цифра, но тоже кликабельно
                    row.append(InlineKeyboardButton(
                        text=f"{day_num}",
                        callback_data=f"adm_cal_day_{action}_{date_str}"
                    ))
        buttons.append(row)

    buttons.append([
        InlineKeyboardButton(text="◀ Назад в меню", callback_data="admin_menu")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
