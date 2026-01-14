"""
Тесты для проверки функциональности ежедневной рассылки.
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

import aiosqlite

from core.database import Conversation


@pytest.fixture
async def test_db():
    """Фикстура для создания и очистки тестовой БД."""
    test_db_name = "test_daily_digest.db"

    # Удаляем старую тестовую БД если есть
    if os.path.exists(test_db_name):
        os.remove(test_db_name)

    # Создаем БД и таблицы с актуальной схемой
    async with aiosqlite.connect(test_db_name) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY,
                name TEXT,
                active_messages_count INTEGER,
                subscription_verified INTEGER,
                referral_code TEXT DEFAULT NULL,
                timezone_offset INTEGER DEFAULT NULL,
                user_email TEXT DEFAULT NULL,
                oauth_access_token TEXT DEFAULT NULL,
                oauth_refresh_token TEXT DEFAULT NULL,
                oauth_token_expiry TEXT DEFAULT NULL,
                daily_digest_enabled INTEGER DEFAULT 1,
                daily_digest_hour INTEGER DEFAULT 9
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)

        await db.commit()

    # Патчим DATABASE_NAME
    from core import database

    original_db = database.DATABASE_NAME
    database.DATABASE_NAME = test_db_name

    yield test_db_name

    # Восстанавливаем и очищаем
    database.DATABASE_NAME = original_db
    if os.path.exists(test_db_name):
        os.remove(test_db_name)


@pytest.mark.asyncio
async def test_daily_digest_default_values(test_db):
    """
    Тест проверяет, что при создании пользователя устанавливаются
    правильные значения по умолчанию для ежедневной рассылки.
    """
    test_user_id = 11111

    # Создаем пользователя без указания полей digest
    conversation = Conversation(test_user_id, name="TestUser")
    await conversation.save_for_db()

    # Загружаем из БД
    loaded_conversation = Conversation(test_user_id)
    await loaded_conversation.get_from_db()

    # Проверяем значения по умолчанию
    assert loaded_conversation.daily_digest_enabled == 1, (
        "Рассылка должна быть включена по умолчанию"
    )
    assert loaded_conversation.daily_digest_hour == 9, (
        "Час отправки должен быть 9 по умолчанию"
    )


@pytest.mark.asyncio
async def test_daily_digest_toggle(test_db):
    """
    Тест проверяет включение и выключение ежедневной рассылки.
    """
    test_user_id = 22222

    # Создаем пользователя
    conversation = Conversation(test_user_id, name="TestUser")
    await conversation.save_for_db()

    # Загружаем из БД
    conversation = Conversation(test_user_id)
    await conversation.get_from_db()

    # Проверяем, что по умолчанию включено
    assert conversation.daily_digest_enabled == 1

    # Отключаем
    conversation.daily_digest_enabled = 0
    await conversation.update_in_db()

    # Загружаем снова и проверяем
    conversation = Conversation(test_user_id)
    await conversation.get_from_db()
    assert conversation.daily_digest_enabled == 0, "Рассылка должна быть отключена"

    # Включаем обратно
    conversation.daily_digest_enabled = 1
    await conversation.update_in_db()

    # Загружаем и проверяем
    conversation = Conversation(test_user_id)
    await conversation.get_from_db()
    assert conversation.daily_digest_enabled == 1, "Рассылка должна быть включена"


@pytest.mark.asyncio
async def test_daily_digest_hour_change(test_db):
    """
    Тест проверяет изменение часа отправки ежедневной рассылки.
    """
    test_user_id = 33333

    # Создаем пользователя
    conversation = Conversation(test_user_id, name="TestUser")
    await conversation.save_for_db()

    # Проверяем значение по умолчанию
    conversation = Conversation(test_user_id)
    await conversation.get_from_db()
    assert conversation.daily_digest_hour == 9

    # Изменяем на 21:00 (9 вечера)
    conversation.daily_digest_hour = 21
    await conversation.update_in_db()

    # Загружаем и проверяем
    conversation = Conversation(test_user_id)
    await conversation.get_from_db()
    assert conversation.daily_digest_hour == 21, "Час должен быть 21"

    # Изменяем на 6:00 утра
    conversation.daily_digest_hour = 6
    await conversation.update_in_db()

    # Загружаем и проверяем
    conversation = Conversation(test_user_id)
    await conversation.get_from_db()
    assert conversation.daily_digest_hour == 6, "Час должен быть 6"


@pytest.mark.asyncio
async def test_send_digest_no_oauth(test_db):
    """
    Тест проверяет, что рассылка не отправляется пользователю без OAuth токена.
    """
    # Импортируем локально, чтобы не влиять на другие тесты
    from services.daily_digest_service import send_daily_digest_to_user

    test_user_id = 44444

    # Создаем пользователя БЕЗ OAuth токена
    conversation = Conversation(test_user_id, name="TestUser", timezone_offset=3)
    await conversation.save_for_db()

    # Пытаемся отправить digest
    with patch("services.daily_digest_service.bot") as mock_bot:
        success, error = await send_daily_digest_to_user(test_user_id)

        # Проверяем, что не отправлено
        assert not success, "Не должно быть успеха без OAuth"
        assert error == "no_oauth", "Ошибка должна быть 'no_oauth'"
        mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_send_digest_disabled(test_db):
    """
    Тест проверяет, что рассылка не отправляется, если она отключена.
    """
    # Импортируем локально, чтобы не влиять на другие тесты
    from services.daily_digest_service import send_daily_digest_to_user

    test_user_id = 55555

    # Создаем пользователя с отключенной рассылкой
    conversation = Conversation(
        test_user_id,
        name="TestUser",
        timezone_offset=3,
        oauth_access_token="test_token",
        daily_digest_enabled=0,  # Отключено
    )
    await conversation.save_for_db()

    # Пытаемся отправить digest
    with patch("services.daily_digest_service.bot") as mock_bot:
        success, error = await send_daily_digest_to_user(test_user_id)

        # Проверяем, что не отправлено
        assert not success, "Не должно быть успеха при отключенной рассылке"
        assert error == "disabled", "Ошибка должна быть 'disabled'"
        mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_send_digest_success(test_db):
    """
    Тест проверяет успешную отправку ежедневной рассылки.
    """
    # Импортируем локально, чтобы не влиять на другие тесты
    from services.daily_digest_service import send_daily_digest_to_user

    test_user_id = 66666

    # Создаем пользователя с OAuth токеном и включенной рассылкой
    conversation = Conversation(
        test_user_id,
        name="TestUser",
        timezone_offset=3,
        oauth_access_token="test_token",
        daily_digest_enabled=1,
        daily_digest_hour=9,
    )
    await conversation.save_for_db()

    # Мокаем зависимости
    with (
        patch("services.daily_digest_service.bot") as mock_bot,
        patch("services.daily_digest_service.get_llm_response") as mock_llm,
        patch("services.daily_digest_service.keep_typing") as mock_typing,
    ):
        # Настраиваем моки
        mock_llm.return_value = (
            "Сегодня у вас 2 события: встреча в 10:00 и обед в 13:00",
            None,
        )
        mock_bot.send_message = AsyncMock()
        mock_typing_task = MagicMock()
        mock_typing_task.cancel = MagicMock()
        mock_typing.return_value = mock_typing_task

        # Отправляем digest
        success, error = await send_daily_digest_to_user(test_user_id)

        # Проверяем результат
        assert success, "Должно быть успешно"
        assert error is None, "Не должно быть ошибки"

        # Проверяем, что send_message был вызван
        assert mock_bot.send_message.called, "Должно было отправиться сообщение"
        call_args = mock_bot.send_message.call_args

        # Проверяем, что в сообщении есть приветствие
        message_text = call_args[0][1]
        assert "Доброе утро" in message_text, "Должно быть приветствие"
        assert "TestUser" in message_text, "Должно быть имя пользователя"


@pytest.mark.asyncio
async def test_timezone_calculation(test_db):
    """
    Тест проверяет правильность вычисления локального времени с учетом часового пояса.
    """
    # Тестовые данные: (UTC час, timezone_offset, ожидаемый локальный час)
    test_cases = [
        (0, 3, 3),  # UTC 0:00 + 3 = 3:00
        (6, 3, 9),  # UTC 6:00 + 3 = 9:00
        (21, 3, 0),  # UTC 21:00 + 3 = 0:00 (следующий день)
        (23, 5, 4),  # UTC 23:00 + 5 = 4:00 (следующий день)
        (12, -5, 7),  # UTC 12:00 - 5 = 7:00
        (3, -8, 19),  # UTC 3:00 - 8 = 19:00 (предыдущий день)
    ]

    for utc_hour, offset, expected_local_hour in test_cases:
        local_hour = (utc_hour + offset) % 24
        assert local_hour == expected_local_hour, (
            f"UTC {utc_hour}:00 + offset {offset} должно быть {expected_local_hour}:00, но получили {local_hour}:00"
        )
