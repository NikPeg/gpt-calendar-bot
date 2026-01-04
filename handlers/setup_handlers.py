"""
Обработчики для настройки Google Calendar сервисного аккаунта.
"""

import json

from aiogram import F, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core.bot_instance import dp
from core.config import MESSAGES, logger
from core.database import Conversation
from services.calendar_service import CalendarService


class SetupStates(StatesGroup):
    """Состояния для процесса настройки."""

    waiting_for_setup_confirmation = State()
    waiting_for_service_account_json = State()
    waiting_for_user_email = State()


@dp.callback_query(F.data == "setup_calendar")
async def start_setup(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс настройки календаря."""
    await callback.answer()

    instruction_text = MESSAGES["msg_calendar_setup_instruction"]

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Продолжить", callback_data="setup_continue")],
            [InlineKeyboardButton(text="Отмена", callback_data="setup_cancel")],
        ]
    )

    await callback.message.edit_text(instruction_text, reply_markup=keyboard)
    await state.set_state(SetupStates.waiting_for_setup_confirmation)


@dp.callback_query(F.data == "setup_continue")
async def continue_setup(callback: types.CallbackQuery, state: FSMContext):
    """Продолжает настройку - запрашивает JSON."""
    await callback.answer()

    await callback.message.edit_text(
        MESSAGES["msg_send_service_account_json"],
        reply_markup=None,
    )
    await state.set_state(SetupStates.waiting_for_service_account_json)


@dp.callback_query(F.data == "setup_cancel")
async def cancel_setup(callback: types.CallbackQuery, state: FSMContext):
    """Отменяет настройку."""
    await callback.answer("Настройка отменена")
    await callback.message.edit_text(
        "Настройка отменена. Вы можете начать её позже командой /start",
        reply_markup=None,
    )
    await state.clear()


@dp.message(StateFilter(SetupStates.waiting_for_service_account_json))
async def process_service_account_json(message: types.Message, state: FSMContext):
    """Обрабатывает JSON сервисного аккаунта."""
    try:
        # Пытаемся распарсить JSON
        json_text = message.text.strip()

        # Убираем markdown code blocks если есть
        if json_text.startswith("```"):
            lines = json_text.split("\n")
            json_text = "\n".join(lines[1:-1])

        # Парсим JSON
        service_account_data = json.loads(json_text)

        # Проверяем наличие обязательных полей
        required_fields = [
            "type",
            "project_id",
            "private_key_id",
            "private_key",
            "client_email",
        ]
        missing_fields = [
            field for field in required_fields if field not in service_account_data
        ]

        if missing_fields:
            await message.answer(
                f"❌ В JSON отсутствуют обязательные поля: {', '.join(missing_fields)}\n\n"
                "Пожалуйста, отправьте полный JSON файл сервисного аккаунта."
            )
            return

        # Сохраняем JSON во временное хранилище состояния
        await state.update_data(service_account_json=json_text)

        # Проверяем доступ к календарю
        calendar_service = CalendarService(json_text)
        if not calendar_service.is_configured():
            await message.answer(
                "❌ Не удалось инициализировать сервис календаря. "
                "Проверьте правильность JSON и попробуйте снова."
            )
            return

        # Запрашиваем email пользователя
        await message.answer(
            "✅ JSON сервисного аккаунта принят!\n\n"
            "📧 Теперь отправьте ваш email адрес Google Calendar (Gmail):\n\n"
            "Например: your.email@gmail.com\n\n"
            "⚠️ Важно: Убедитесь, что вы расшарили свой календарь с сервисным аккаунтом:\n"
            f"`{service_account_data.get('client_email', '')}`\n\n"
            "Как расшарить календарь:\n"
            "1. Откройте calendar.google.com\n"
            "2. Настройки → Расшарить с определенными людьми\n"
            "3. Добавьте email сервисного аккаунта\n"
            "4. Дайте права 'Вносить изменения в события'"
        )
        await state.set_state(SetupStates.waiting_for_user_email)

    except json.JSONDecodeError:
        await message.answer(
            "❌ Неверный формат JSON. Пожалуйста, отправьте корректный JSON файл сервисного аккаунта."
        )
    except Exception as e:
        logger.error(f"Error processing service account JSON: {e}", exc_info=True)
        await message.answer(
            "❌ Произошла ошибка при обработке JSON. Попробуйте снова."
        )


@dp.message(StateFilter(SetupStates.waiting_for_user_email))
async def process_user_email(message: types.Message, state: FSMContext):
    """Обрабатывает email пользователя."""
    user_id = message.chat.id
    user_email = message.text.strip()

    # Простая валидация email
    if "@" not in user_email or "." not in user_email.split("@")[1]:
        await message.answer(
            "❌ Неверный формат email. Пожалуйста, отправьте корректный email адрес.\n\n"
            "Пример: your.email@gmail.com"
        )
        return

    try:
        # Получаем сохраненный JSON из состояния
        data = await state.get_data()
        json_text = data.get("service_account_json")

        if not json_text:
            await message.answer(
                "❌ Ошибка: JSON сервисного аккаунта не найден. "
                "Пожалуйста, начните настройку заново командой /start"
            )
            await state.clear()
            return

        # Сохраняем в БД
        conversation = Conversation(user_id)
        await conversation.get_from_db()
        conversation.service_account_json = json_text
        conversation.user_email = user_email
        await conversation.update_in_db()

        # Проверяем доступ к календарю
        calendar_service = CalendarService(json_text)
        if not calendar_service.is_configured():
            await message.answer(
                "❌ Не удалось инициализировать сервис календаря. "
                "Проверьте правильность JSON и попробуйте снова."
            )
            await state.clear()
            return

        # Проверяем доступ к календарю пользователя
        calendar_id = calendar_service.get_calendar_id(user_email)
        if not calendar_id:
            await message.answer(
                "❌ Не удалось получить доступ к календарю.\n\n"
                "Убедитесь, что:\n"
                "1. Сервисный аккаунт имеет доступ к Google Calendar API\n"
                "2. Вы расшарили свой календарь с сервисным аккаунтом:\n"
                f"   `{json.loads(json_text).get('client_email', '')}`\n\n"
                "Как расшарить календарь:\n"
                "1. Откройте calendar.google.com\n"
                "2. Настройки → Расшарить с определенными людьми\n"
                "3. Добавьте email сервисного аккаунта\n"
                "4. Дайте права 'Вносить изменения в события'\n\n"
                "Попробуйте снова пройти настройку командой /start"
            )
            await state.clear()
            return

        await message.answer(
            f"✅ Настройка завершена успешно!\n\n"
            f"📧 Ваш email: {user_email}\n"
            f"🔑 Сервисный аккаунт: {json.loads(json_text).get('client_email', '')}\n"
            f"📅 Календарь настроен и готов к использованию.\n\n"
            "Теперь вы можете управлять своим календарем через бота!"
        )

        await state.clear()
        logger.info(
            f"USER{user_id}: Calendar setup completed successfully with email {user_email}"
        )

    except Exception as e:
        logger.error(f"Error processing user email: {e}", exc_info=True)
        await message.answer(
            "❌ Произошла ошибка при обработке email. Попробуйте снова."
        )
        await state.clear()


@dp.callback_query(F.data == "reconfigure_calendar")
async def reconfigure_calendar(callback: types.CallbackQuery, state: FSMContext):
    """Начинает перенастройку календаря."""
    await callback.answer()
    await start_setup(callback, state)
