# ========================================
# utils/calendar_kb.py — Генератор inline-календаря
# ========================================

import calendar
from datetime import date, timedelta
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData


# CallbackData для кнопок календаря
class CalendarCallback(CallbackData, prefix="cal"):
    action: str   # "day" | "prev" | "next" | "ignore"
    year: int
    month: int
    day: int      # 0 если действие не "day"


MONTHS_RU = [
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
]
WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def build_calendar(
    year: int,
    month: int,
    available_dates: list[str]   # список строк "YYYY-MM-DD"
) -> InlineKeyboardMarkup:
    """
    Строит inline-клавиатуру-календарь.
    Выделяет доступные даты (✅), недоступные показывает серыми точками.
    """
    today = date.today()
    avail_set = set(available_dates)

    buttons = []

    # ---- Шапка: навигация по месяцам ----
    nav_row = []

    # Кнопка "предыдущий месяц" (не раньше текущего)
    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1
    # Показываем только если предыдущий месяц >= текущий
    if (prev_year, prev_month) >= (today.year, today.month):
        nav_row.append(InlineKeyboardButton(
            text="◀",
            callback_data=CalendarCallback(
                action="prev", year=prev_year, month=prev_month, day=0
            ).pack()
        ))
    else:
        nav_row.append(InlineKeyboardButton(
            text=" ", callback_data=CalendarCallback(
                action="ignore", year=year, month=month, day=0).pack()
        ))

    nav_row.append(InlineKeyboardButton(
        text=f"{MONTHS_RU[month]} {year}",
        callback_data=CalendarCallback(action="ignore", year=year, month=month, day=0).pack()
    ))

    # Кнопка "следующий месяц" (не дальше +1 месяц от текущего)
    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1
    max_date = today + timedelta(days=31)
    if date(next_year, next_month, 1) <= max_date:
        nav_row.append(InlineKeyboardButton(
            text="▶",
            callback_data=CalendarCallback(
                action="next", year=next_year, month=next_month, day=0
            ).pack()
        ))
    else:
        nav_row.append(InlineKeyboardButton(
            text=" ", callback_data=CalendarCallback(
                action="ignore", year=year, month=month, day=0).pack()
        ))

    buttons.append(nav_row)

    # ---- Дни недели ----
    buttons.append([
        InlineKeyboardButton(
            text=d,
            callback_data=CalendarCallback(action="ignore", year=year, month=month, day=0).pack()
        )
        for d in WEEKDAYS_RU
    ])

    # ---- Дни месяца ----
    cal = calendar.monthcalendar(year, month)
    for week in cal:
        row = []
        for day_num in week:
            if day_num == 0:
                row.append(InlineKeyboardButton(
                    text=" ",
                    callback_data=CalendarCallback(
                        action="ignore", year=year, month=month, day=0).pack()
                ))
            else:
                day_date = date(year, month, day_num)
                date_str = day_date.strftime("%Y-%m-%d")

                if day_date < today:
                    # Прошедший день
                    row.append(InlineKeyboardButton(
                        text=f"·",
                        callback_data=CalendarCallback(
                            action="ignore", year=year, month=month, day=day_num).pack()
                    ))
                elif date_str in avail_set:
                    # Доступная дата ✅
                    row.append(InlineKeyboardButton(
                        text=f"✅{day_num}",
                        callback_data=CalendarCallback(
                            action="day", year=year, month=month, day=day_num).pack()
                    ))
                else:
                    # Нет слотов — серая цифра (нажатие игнорируется)
                    row.append(InlineKeyboardButton(
                        text=f"{day_num}",
                        callback_data=CalendarCallback(
                            action="ignore", year=year, month=month, day=day_num).pack()
                    ))
        buttons.append(row)

    # ---- Кнопка выхода в меню ----
    buttons.append([
        InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
