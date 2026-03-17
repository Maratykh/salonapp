from aiogram.fsm.state import StatesGroup, State


class BookingStates(StatesGroup):
    choosing_date    = State()
    choosing_service = State()
    choosing_time    = State()
    entering_name    = State()
    entering_phone   = State()
    confirming       = State()


class AdminStates(StatesGroup):
    # Рабочий день
    add_day_start  = State()
    add_day_end    = State()
    add_by_weekday = State()
    add_wd_start   = State()
    add_wd_end     = State()
    # Слоты
    remove_slot_time = State()
    add_slot_time    = State()
    # Ручная запись
    manual_service = State()
    manual_name    = State()
    manual_confirm = State()
    # Управление услугами
    svc_name       = State()
    svc_price      = State()
    svc_slots      = State()
    svc_emoji      = State()
    svc_repeat     = State()
    # Рассылка
    broadcast_text    = State()
    broadcast_confirm = State()
