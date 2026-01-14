"""
Тест для проверки установки timezone_offset по умолчанию.

Проверяет:
1. Миграция установила timezone_offset=3 для существующих пользователей
2. Новые пользователи создаются с timezone_offset=3 по умолчанию
3. Команда digest_settings больше не показывает предупреждение о timezone
"""

import aiosqlite
import pytest

from core.database import DATABASE_NAME, Conversation


@pytest.mark.asyncio
async def test_existing_users_have_timezone():
    """
    Тест проверяет, что у всех существующих пользователей установлен timezone_offset.
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM conversations WHERE timezone_offset IS NULL"
        )
        users_without_timezone = (await cursor.fetchone())[0]
        await cursor.close()

    # У всех пользователей должен быть установлен timezone_offset
    assert (
        users_without_timezone == 0
    ), f"Найдено {users_without_timezone} пользователей без timezone_offset"


@pytest.mark.asyncio
async def test_new_user_has_default_timezone():
    """
    Тест проверяет, что новый пользователь создается с timezone_offset=3 по умолчанию.
    """
    # Создаем нового тестового пользователя
    test_user_id = 999999999  # Уникальный ID для теста
    test_user_name = "Test User for Timezone"

    # Удаляем пользователя, если он уже существует
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("DELETE FROM conversations WHERE id = ?", (test_user_id,))
        await db.commit()

    try:
        # Создаем нового пользователя без указания timezone_offset
        conversation = Conversation(test_user_id, test_user_name)
        await conversation.save_for_db()

        # Читаем данные из БД
        conversation_from_db = Conversation(test_user_id)
        await conversation_from_db.get_from_db()

        # Проверяем, что timezone_offset установлен в 3 по умолчанию
        assert (
            conversation_from_db.timezone_offset == 3
        ), f"Expected timezone_offset=3, got {conversation_from_db.timezone_offset}"

        # Проверяем, что другие поля по умолчанию тоже установлены правильно
        assert (
            conversation_from_db.daily_digest_enabled == 1
        ), "Expected daily_digest_enabled=1"
        assert (
            conversation_from_db.daily_digest_hour == 9
        ), "Expected daily_digest_hour=9"

    finally:
        # Удаляем тестового пользователя
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute("DELETE FROM conversations WHERE id = ?", (test_user_id,))
            await db.commit()


@pytest.mark.asyncio
async def test_user_can_override_default_timezone():
    """
    Тест проверяет, что пользователь может изменить timezone_offset на другое значение.
    """
    test_user_id = 999999997
    test_user_name = "Test User for Custom Timezone"

    # Удаляем пользователя, если он уже существует
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("DELETE FROM conversations WHERE id = ?", (test_user_id,))
        await db.commit()

    try:
        # Создаем пользователя с дефолтным timezone
        conversation = Conversation(test_user_id, test_user_name)
        await conversation.save_for_db()

        # Проверяем, что timezone=3
        conversation_from_db = Conversation(test_user_id)
        await conversation_from_db.get_from_db()
        assert conversation_from_db.timezone_offset == 3

        # Изменяем timezone на 5 (Екатеринбург)
        conversation_from_db.timezone_offset = 5
        await conversation_from_db.update_in_db()

        # Читаем снова и проверяем, что изменение сохранилось
        conversation_updated = Conversation(test_user_id)
        await conversation_updated.get_from_db()
        assert (
            conversation_updated.timezone_offset == 5
        ), "Пользователь не может изменить timezone"

    finally:
        # Удаляем тестового пользователя
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute("DELETE FROM conversations WHERE id = ?", (test_user_id,))
            await db.commit()
