# handlers/common.py

import logging
from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from config import ADMIN_ID, ADMIN_IDS, STUDIO_NAME, STUDIO_ADDRESS, STUDIO_MAPS_LINK, DEMO_MODE, PRIVACY_POLICY_URL
from keyboards.user_kb import main_menu_kb, back_to_menu_kb, portfolio_kb
from database.db import get_services, consent_check, consent_save

router = Router()
logger = logging.getLogger(__name__)


def _consent_kb() -> InlineKeyboardMarkup:
    buttons = []
    if PRIVACY_POLICY_URL:
        buttons.append([InlineKeyboardButton(
            text="📄 Читать документ", url=PRIVACY_POLICY_URL
        )])
    buttons.append([
        InlineKeyboardButton(text="✅ Даю согласие",    callback_data="consent_yes"),
        InlineKeyboardButton(text="❌ Не даю согласие", callback_data="consent_no"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _consent_text(name: str) -> str:
    return (
        f"👋 Привет, <b>{name}</b>!\n\n"
        f"Перед началом работы нам необходимо ваше согласие на обработку персональных данных.\n\n"
        f"Мы собираем: имя, номер телефона и информацию о записях.\n"
        f"Данные используются только для организации записи к мастеру.\n\n"
        f"Ознакомьтесь с политикой конфиденциальности и дайте согласие:"
    )


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    return True


async def _show_main_menu(target, state: FSMContext, user_id: int, is_edit: bool = False):
    admin = user_id in ADMIN_IDS
    show_admin = admin or DEMO_MODE
    text = f"💅 <b>Главное меню</b>\n\nВыберите действие:"
    kb = main_menu_kb(is_admin=show_admin)
    if is_edit:
        await target.edit_text(text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id

    # Админы и демо-режим — без проверки согласия
    if user_id in ADMIN_IDS or DEMO_MODE:
        admin = user_id in ADMIN_IDS
        show_admin = admin or DEMO_MODE
        demo_banner = "\n🎭 <b>Это демо-версия бота.</b> Запись не создаётся.\n" if DEMO_MODE else ""
        await message.answer(
            f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
            f"Добро пожаловать в бот студии <b>{STUDIO_NAME}</b>.\n"
            f"{demo_banner}"
            f"Выберите действие:",
            reply_markup=main_menu_kb(is_admin=show_admin)
        )
        return

    # Проверяем согласие
    has_consent = await consent_check(user_id)
    if has_consent:
        await _show_main_menu(message, state, user_id, is_edit=False)
        return

    # Показываем запрос согласия
    await message.answer(_consent_text(message.from_user.first_name), reply_markup=_consent_kb())


@router.callback_query(F.data == "consent_yes")
async def consent_given(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await consent_save(user_id, True)
    await callback.message.edit_text(
        f"✅ Спасибо! Согласие получено.\n\n"
        f"Добро пожаловать в бот студии <b>{STUDIO_NAME}</b>!",
    )
    await callback.answer()
    # Показываем главное меню новым сообщением
    admin = user_id in ADMIN_IDS
    await callback.message.answer(
        "💅 <b>Главное меню</b>\n\nВыберите действие:",
        reply_markup=main_menu_kb(is_admin=admin)
    )


@router.callback_query(F.data == "consent_no")
async def consent_denied(callback: CallbackQuery):
    await consent_save(callback.from_user.id, False)
    await callback.message.edit_text(
        "❌ <b>Вы отказали в обработке персональных данных.</b>\n\n"
        "К сожалению, запись через бот невозможна без согласия.\n\n"
        "Если передумаете — нажмите /start.",
    )
    await callback.answer()


@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _show_main_menu(callback.message, state, callback.from_user.id, is_edit=True)
    await callback.answer()


@router.callback_query(F.data == "prices")
async def show_prices(callback: CallbackQuery):
    services = await get_services(active_only=True)
    lines = ""
    for svc in services:
        lines += f"  {svc['emoji']} <b>{svc['name']}</b> — {svc['price']} руб. ({svc['duration_str']})\n"
    await callback.message.edit_text(
        f"💅 <b>Прайс-лист</b>\n\n{lines}\n📩 Для записи нажмите «Записаться»",
        reply_markup=back_to_menu_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "portfolio")
async def show_portfolio(callback: CallbackQuery):
    await callback.message.edit_text(
        "🖼 <b>Моё портфолио</b>\n\nПосмотрите мои работы!\nНажмите кнопку ниже 👇",
        reply_markup=portfolio_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "how_to_get")
async def how_to_get(callback: CallbackQuery):
    text = (
        f"📍 <b>Как добраться</b>\n\n"
        f"🏠 Студия: <b>{STUDIO_NAME}</b>\n"
        f"📌 Адрес: <b>{STUDIO_ADDRESS}</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗺 Открыть на карте", url=STUDIO_MAPS_LINK)],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "❓ <b>Помощь</b>\n\n"
        "🔹 Используйте кнопки меню для навигации.\n"
        "🔹 Для записи нажмите «📅 Записаться».\n"
        "🔹 По вопросам пишите администратору.",
        reply_markup=back_to_menu_kb()
    )
