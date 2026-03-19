# handlers/common.py

import logging
from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from config import ADMIN_ID, ADMIN_IDS, STUDIO_NAME, STUDIO_ADDRESS, STUDIO_MAPS_LINK, DEMO_MODE
from keyboards.user_kb import main_menu_kb, back_to_menu_kb, portfolio_kb
from database.db import get_services

router = Router()
logger = logging.getLogger(__name__)


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    return True


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    admin = message.from_user.id in ADMIN_IDS
    # В демо-режиме панель администратора видна всем
    show_admin = admin or DEMO_MODE
    demo_banner = "\n🎭 <b>Это демо-версия бота.</b> Запись не создаётся.\n" if DEMO_MODE else ""
    await message.answer(
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
        f"Добро пожаловать в бот студии <b>{STUDIO_NAME}</b>.\n"
        f"{demo_banner}"
        f"Выберите действие:",
        reply_markup=main_menu_kb(is_admin=show_admin)
    )


@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    admin = callback.from_user.id in ADMIN_IDS
    show_admin = admin or DEMO_MODE
    await callback.message.edit_text(
        f"💅 <b>Главное меню</b>\n\nВыберите действие:",
        reply_markup=main_menu_kb(is_admin=show_admin)
    )
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
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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
