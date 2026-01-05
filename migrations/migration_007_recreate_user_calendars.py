"""
Миграция: восстановление таблицы user_calendars после ошибочного удаления в миграции 005.

Эта миграция пересоздаёт таблицу user_calendars для пользователей с OAuth токенами.
"""

import aiosqlite


def get_migration_id() -> str:
    """Возвращает уникальный ID миграции."""
    return "007_recreate_user_calendars"


def get_migration_description() -> str:
    """Возвращает описание миграции."""
    return "Восстановление таблицы user_calendars после ошибочного удаления"


async def migrate(conn: aiosqlite.Connection) -> str:
    """
    Выполняет миграцию.

    Args:
        conn: Подключение к базе данных

    Returns:
        Сообщение о результате миграции
    """
    try:
        # Проверяем, существует ли таблица user_calendars
        async with conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='user_calendars'
        """) as cursor:
            table_exists = await cursor.fetchone()

        if table_exists:
            return "✅ Таблица user_calendars уже существует"

        # Создаем таблицу user_calendars
        await conn.execute("""
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
        """)

        # Создаем индексы для быстрого поиска
        await conn.execute("""
            CREATE INDEX idx_user_calendars_user_id
            ON user_calendars(user_id)
        """)

        await conn.execute("""
            CREATE INDEX idx_user_calendars_enabled
            ON user_calendars(user_id, is_enabled)
        """)

        await conn.commit()

        # Добавляем основные календари для пользователей с OAuth токенами
        async with conn.execute("""
            SELECT id, user_email, oauth_access_token
            FROM conversations
            WHERE oauth_access_token IS NOT NULL AND oauth_access_token != ''
        """) as cursor:
            users = await cursor.fetchall()

        migrated_count = 0
        from datetime import UTC, datetime

        current_time = datetime.now(UTC).isoformat()

        for user_id, user_email, oauth_token in users:
            if user_email and oauth_token:
                # Добавляем основной календарь пользователя
                await conn.execute(
                    """
                    INSERT OR IGNORE INTO user_calendars
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
                migrated_count += 1

        await conn.commit()

        return f"✅ Таблица user_calendars восстановлена. Добавлено календарей: {migrated_count}"

    except Exception as e:
        await conn.rollback()
        return f"❌ Ошибка миграции: {e}"


async def rollback(conn: aiosqlite.Connection) -> str:
    """
    Откатывает миграцию.

    Args:
        conn: Подключение к базе данных

    Returns:
        Сообщение о результате отката
    """
    try:
        await conn.execute("DROP TABLE IF EXISTS user_calendars")
        await conn.commit()
        return "✅ Таблица user_calendars удалена"
    except Exception as e:
        await conn.rollback()
        return f"❌ Ошибка отката: {e}"
