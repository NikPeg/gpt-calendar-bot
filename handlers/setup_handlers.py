"""
Обработчики для настройки Google Calendar через OAuth 2.0.
"""

import secrets

from aiogram import F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core.bot_instance import dp
from core.config import (
    GOOGLE_OAUTH_CLIENT_ID,
    GOOGLE_OAUTH_CLIENT_SECRET,
    GOOGLE_OAUTH_REDIRECT_URI,
    MESSAGES,
    logger,
)
from core.database import Conversation

# Импортируем хранилище state токенов из OAuth сервера
# В продакшене использовать Redis
from oauth_server import pending_states
from services.google_service_oauth import GoogleServiceOAuth


class SetupStates(StatesGroup):
    """Состояния для процесса настройки."""

    waiting_for_setup_confirmation = State()


@dp.callback_query(F.data == "setup_calendar")
async def start_setup(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс настройки календаря через OAuth."""
    await callback.answer()

    # Проверяем наличие OAuth credentials
    if not GOOGLE_OAUTH_CLIENT_ID or not GOOGLE_OAUTH_CLIENT_SECRET:
        await callback.message.edit_text(
            "❌ OAuth не настроен на сервере. "
            "Пожалуйста, обратитесь к администратору бота.",
            reply_markup=None,
        )
        return

    instruction_text = MESSAGES["msg_oauth_setup_instruction"]

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔐 Авторизоваться через Google",
                    callback_data="oauth_authorize",
                )
            ],
            [InlineKeyboardButton(text="Отмена", callback_data="setup_cancel")],
        ]
    )

    await callback.message.edit_text(instruction_text, reply_markup=keyboard)
    await state.set_state(SetupStates.waiting_for_setup_confirmation)


@dp.callback_query(F.data == "oauth_authorize")
async def oauth_authorize(callback: types.CallbackQuery, state: FSMContext):
    """Генерирует OAuth URL и отправляет пользователю."""
    await callback.answer()

    user_id = callback.from_user.id

    try:
        # Генерируем случайный state token для защиты от CSRF
        state_token = secrets.token_urlsafe(32)

        # Сохраняем state token с user_id
        pending_states[state_token] = user_id

        # Создаем OAuth URL
        auth_url, _ = GoogleServiceOAuth.create_authorization_url(
            client_id=GOOGLE_OAUTH_CLIENT_ID,
            client_secret=GOOGLE_OAUTH_CLIENT_SECRET,
            redirect_uri=GOOGLE_OAUTH_REDIRECT_URI,
            scopes=[
                "https://www.googleapis.com/auth/calendar",
                "https://www.googleapis.com/auth/tasks",
            ],
            state=state_token,
        )

        # Создаем кнопку с ссылкой на авторизацию
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔐 Перейти к авторизации", url=auth_url
                    )
                ],
                [InlineKeyboardButton(text="Отмена", callback_data="setup_cancel")],
            ]
        )

        await callback.message.edit_text(
            MESSAGES["msg_oauth_authorization_link"], reply_markup=keyboard
        )

        logger.info(f"USER{user_id}: OAuth authorization URL generated")

        # Очищаем состояние - дальше процесс продолжится в OAuth callback
        await state.clear()

    except Exception as e:
        logger.error(f"Error generating OAuth URL: {e}", exc_info=True)
        await callback.message.edit_text(
            "❌ Произошла ошибка при создании ссылки для авторизации. "
            "Пожалуйста, попробуйте позже.",
            reply_markup=None,
        )
        await state.clear()


@dp.callback_query(F.data == "setup_cancel")
async def cancel_setup(callback: types.CallbackQuery, state: FSMContext):
    """Отменяет настройку."""
    await callback.answer("Настройка отменена")
    await callback.message.edit_text(
        "Настройка отменена. Вы можете начать её позже командой /start",
        reply_markup=None,
    )
    await state.clear()


@dp.callback_query(F.data == "reconfigure_calendar")
async def reconfigure_calendar(callback: types.CallbackQuery, state: FSMContext):
    """Начинает перенастройку календаря."""
    await callback.answer()

    # Предупреждаем пользователя
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, перенастроить", callback_data="setup_calendar"
                )
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="setup_cancel")],
        ]
    )

    await callback.message.edit_text(
        "⚠️ Перенастройка календаря\n\n"
        "Вы уверены, что хотите перенастроить доступ к Google Calendar?\n\n"
        "Текущие настройки будут заменены новыми.",
        reply_markup=keyboard,
    )


@dp.callback_query(F.data == "oauth_success")
async def oauth_success_handler(callback: types.CallbackQuery):
    """Обработчик успешной OAuth авторизации (вызывается из oauth_server)."""
    await callback.answer()

    user_id = callback.from_user.id

    # Проверяем, что токены действительно сохранены
    conversation = Conversation(user_id)
    await conversation.get_from_db()

    if conversation.oauth_access_token:
        await callback.message.edit_text(
            MESSAGES["msg_oauth_success"], reply_markup=None
        )
        logger.info(f"USER{user_id}: OAuth setup completed successfully")
    else:
        await callback.message.edit_text(
            "❌ Не удалось завершить настройку. Попробуйте снова командой /start",
            reply_markup=None,
        )
        logger.error(f"USER{user_id}: OAuth tokens not found after callback")
