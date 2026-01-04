"""
Миграция: добавление таблицы user_calendars для поддержки множественных календарей.

Эта таблица позволяет пользователям работать с несколькими календарями одновременно:
- Основной календарь пользователя (для записи событий)
- Публичные календари (например, праздники России) - read-only
- Расшаренные календари от других пользователей
"""

import os
from datetime import UTC, datetime

import aiosqlite
from dotenv import load_dotenv

load_dotenv()
DATABASE_NAME = os.environ.get("DATABASE_NAME", "users.db")


async def upgrade():
    """
    Создает таблицу user_calendars и заполняет её данными из существующих пользователей.
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.cursor()

        # Проверяем, существует ли таблица conversations
        await cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'"
        )
        conversations_exists = await cursor.fetchone()

        if not conversations_exists:
            return "Таблица conversations не существует, миграция пропущена"

        # Проверяем, существует ли уже таблица user_calendars
        await cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user_calendars'"
        )
        table_exists = await cursor.fetchone()

        if table_exists:
            return "Таблица user_calendars уже существует"

        # Создаем таблицу user_calendars
        await cursor.execute(
            """
            CREATE TABLE user_calendars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                calendar_id TEXT NOT NULL,
                calendar_name TEXT,
                calendar_type TEXT NOT NULL,
                is_readonly INTEGER NOT NULL DEFAULT 0,
                is_enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES conversations(id) ON DELETE CASCADE,
                UNIQUE(user_id, calendar_id)
            )
            """
        )

        # Создаем индексы для быстрого поиска
        await cursor.execute(
            """
            CREATE INDEX idx_user_calendars_user_id
            ON user_calendars(user_id)
            """
        )

        await cursor.execute(
            """
            CREATE INDEX idx_user_calendars_enabled
            ON user_calendars(user_id, is_enabled)
            """
        )

        await db.commit()

        # Мигрируем данные: добавляем основные календари и праздники существующих пользователей
        await cursor.execute(
            """
            SELECT id, user_email, service_account_json
            FROM conversations
            WHERE service_account_json IS NOT NULL
            """
        )
        users = await cursor.fetchall()

        current_time = datetime.now(UTC).isoformat()
        migrated_primary_count = 0
        migrated_holidays_count = 0

        # ID календаря праздников России (публичный календарь Google)
        russian_holidays_id = "ru.russian#holiday@group.v.calendar.google.com"

        for user_id, user_email, service_account_json in users:
            if user_email and service_account_json:
                # Добавляем основной календарь пользователя
                await cursor.execute(
                    """
                    INSERT INTO user_calendars
                    (user_id, calendar_id, calendar_name, calendar_type, is_readonly, is_enabled, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        user_email,
                        "Основной календарь",
                        "primary",
                        0,  # Не read-only
                        1,  # Включен
                        current_time,
                    ),
                )
                migrated_primary_count += 1

                # Добавляем календарь праздников России (публичный, read-only)
                await cursor.execute(
                    """
                    INSERT INTO user_calendars
                    (user_id, calendar_id, calendar_name, calendar_type, is_readonly, is_enabled, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        russian_holidays_id,
                        "Праздники России",
                        "public",
                        1,  # Read-only
                        1,  # Включен по умолчанию
                        current_time,
                    ),
                )
                migrated_holidays_count += 1

        await db.commit()

        return (
            f"Таблица user_calendars создана. "
            f"Добавлено основных календарей: {migrated_primary_count}, "
            f"календарей праздников: {migrated_holidays_count}"
        )

