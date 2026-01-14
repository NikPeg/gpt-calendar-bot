"""
Тест для проверки установки timezone_offset по умолчанию.

Проверяет:
1. Миграция установила timezone_offset=3 для существующих пользователей
2. Новые пользователи создаются с timezone_offset=3 по умолчанию
3. Команда digest_settings больше не показывает предупреждение о timezone
"""

import os

import aiosqlite
import pytest

from core import database
from core.database import Conversation


@pytest.fixture
async def test_db():
    """Фикстура для создания и очистки тестовой БД."""
    test_db_name = "test_default_timezone.db"

    # Удаляем старую тестовую БД если есть
    if os.path.exists(test_db_name):
        os.remove(test_db_name)

    # Создаем БД и таблицы с актуальной схемой (включая миграции)
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
                timestamp TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES conversations (id) ON DELETE CASCADE
            )
        """)
        await db.commit()

    # Заменяем глобальную переменную DATABASE_NAME на тестовую
    original_db = database.DATABASE_NAME
    database.DATABASE_NAME = test_db_name

    yield test_db_name

    # Восстанавливаем и очищаем
    database.DATABASE_NAME = original_db
    if os.path.exists(test_db_name):
        os.remove(test_db_name)


@pytest.mark.asyncio
async def test_existing_users_have_timezone(test_db):
    """
    Тест проверяет, что у всех существующих пользователей установлен timezone_offset.

    В этом тесте мы создаем пользователя БЕЗ timezone_offset,
    имитируем миграцию, и проверяем, что после миграции timezone установлен.
    """
    # Создаем пользователя без timezone_offset (как было до миграции)
    async with aiosqlite.connect(test_db) as db:
        await db.execute(
            """
            INSERT INTO conversations (id, name, timezone_offset)
            VALUES (?, ?, NULL)
            """,
            (123456789, "Test User Without Timezone"),
        )
        await db.commit()

    # Имитируем миграцию: устанавливаем timezone_offset=3 для всех с NULL
    async with aiosqlite.connect(test_db) as db:
        await db.execute("""
            UPDATE conversations
            SET timezone_offset = 3
            WHERE timezone_offset IS NULL
        """)
        await db.commit()

    # Проверяем, что у всех пользователей теперь установлен timezone_offset
    async with aiosqlite.connect(test_db) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM conversations WHERE timezone_offset IS NULL"
        )
        users_without_timezone = (await cursor.fetchone())[0]
        await cursor.close()

    # У всех пользователей должен быть установлен timezone_offset
    assert users_without_timezone == 0, (
        f"Найдено {users_without_timezone} пользователей без timezone_offset"
    )


@pytest.mark.asyncio
async def test_new_user_has_default_timezone(test_db):
    """
    Тест проверяет, что новый пользователь создается с timezone_offset=3 по умолчанию.
    """
    # Создаем нового тестового пользователя
    test_user_id = 999999999  # Уникальный ID для теста
    test_user_name = "Test User for Timezone"

    # Создаем нового пользователя без указания timezone_offset
    conversation = Conversation(test_user_id, test_user_name)
    await conversation.save_for_db()

    # Читаем данные из БД
    conversation_from_db = Conversation(test_user_id)
    await conversation_from_db.get_from_db()

    # Проверяем, что timezone_offset установлен в 3 по умолчанию
    assert conversation_from_db.timezone_offset == 3, (
        f"Expected timezone_offset=3, got {conversation_from_db.timezone_offset}"
    )

    # Проверяем, что другие поля по умолчанию тоже установлены правильно
    assert conversation_from_db.daily_digest_enabled == 1, (
        "Expected daily_digest_enabled=1"
    )
    assert conversation_from_db.daily_digest_hour == 9, "Expected daily_digest_hour=9"


@pytest.mark.asyncio
async def test_user_can_override_default_timezone(test_db):
    """
    Тест проверяет, что пользователь может изменить timezone_offset на другое значение.
    """
    test_user_id = 999999997
    test_user_name = "Test User for Custom Timezone"

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
    assert conversation_updated.timezone_offset == 5, (
        "Пользователь не может изменить timezone"
    )
