"""
Обработчики команд для OAuth 2.0 авторизации Google.
"""

import os
import secrets

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv

from core.database import Conversation
from services.google_service_oauth import GoogleServiceOAuth

load_dotenv()

# OAuth конфигурация
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI")

# Scope для Calendar и Tasks
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
]

router = Router()


@router.message(Command("connect_google"))
async def connect_google(message: types.Message):
    """Команда для подключения Google Calendar и Tasks."""
    user_id = message.from_user.id
    
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET or not GOOGLE_REDIRECT_URI:
        await message.answer(
            "⚠️ OAuth не настроен.\n\n"
            "Администратор должен настроить GOOGLE_OAUTH_CLIENT_ID, "
            "GOOGLE_OAUTH_CLIENT_SECRET и GOOGLE_OAUTH_REDIRECT_URI в конфигурации бота."
        )
        return
    
    # Проверяем, уже подключен ли пользователь
    conversation = Conversation(user_id)
    await conversation.get_from_db()
    
    if conversation.oauth_access_token:
        await message.answer(
            "✅ Ваш Google аккаунт уже подключен!\n\n"
            "Если хотите переподключить, используйте /reconnect_google"
        )
        return
    
    # Генерируем state для CSRF protection
    state = f"{user_id}_{secrets.token_urlsafe(16)}"
    
    # Сохраняем state (в продакшене использовать Redis с TTL)
    from oauth_server import pending_states
    pending_states[state] = user_id
    
    # Создаем authorization URL
    auth_url, _ = GoogleServiceOAuth.create_authorization_url(
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        redirect_uri=GOOGLE_REDIRECT_URI,
        scopes=SCOPES,
        state=state,
    )
    
    # Отправляем кнопку с ссылкой
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔗 Подключить Google Calendar",
            url=auth_url
        )]
    ])
    
    await message.answer(
        "🔐 **Подключение Google Calendar и Tasks**\n\n"
        "Для подключения нажмите кнопку ниже и разрешите доступ к:\n"
        "• 📅 Google Calendar (создание и просмотр событий)\n"
        "• ✅ Google Tasks (создание и управление задачами)\n\n"
        "После авторизации вы вернетесь сюда автоматически.",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


@router.message(Command("reconnect_google"))
async def reconnect_google(message: types.Message):
    """Переподключение Google аккаунта."""
    user_id = message.from_user.id
    
    # Удаляем старые токены
    conversation = Conversation(user_id)
    await conversation.get_from_db()
    
    conversation.oauth_access_token = None
    conversation.oauth_refresh_token = None
    conversation.oauth_token_expiry = None
    
    await conversation.update_in_db()
    
    await message.answer("🔄 Старые токены удалены.\n\nИспользуйте /connect_google для нового подключения.")


@router.message(Command("disconnect_google"))
async def disconnect_google(message: types.Message):
    """Отключение Google аккаунта."""
    user_id = message.from_user.id
    
    conversation = Conversation(user_id)
    await conversation.get_from_db()
    
    if not conversation.oauth_access_token:
        await message.answer("⚠️ Google аккаунт не подключен.")
        return
    
    # Удаляем токены
    conversation.oauth_access_token = None
    conversation.oauth_refresh_token = None
    conversation.oauth_token_expiry = None
    
    await conversation.update_in_db()
    
    await message.answer(
        "✅ Google аккаунт отключен.\n\n"
        "Бот больше не имеет доступа к вашему календарю и задачам.\n"
        "Для повторного подключения используйте /connect_google"
    )


@router.message(Command("google_status"))
async def google_status(message: types.Message):
    """Проверка статуса подключения Google."""
    user_id = message.from_user.id
    
    conversation = Conversation(user_id)
    await conversation.get_from_db()
    
    if conversation.oauth_access_token:
        status = "✅ Подключен"
        expiry = conversation.oauth_token_expiry or "Не указано"
        await message.answer(
            f"**Статус Google подключения:**\n\n"
            f"Статус: {status}\n"
            f"Срок действия токена: {expiry}\n\n"
            f"Доступные функции:\n"
            f"• 📅 Google Calendar\n"
            f"• ✅ Google Tasks",
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            "**Статус Google подключения:**\n\n"
            "Статус: ❌ Не подключен\n\n"
            "Используйте /connect_google для подключения.",
            parse_mode="Markdown"
        )

