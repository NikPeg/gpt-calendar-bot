"""
Миграция: переход на OAuth 2.0 для Google API.

Удаляет поле service_account_json (больше не используется).
Сохраняет поле user_email (для кеширования email пользователя).
Добавляет новые поля для OAuth токенов.
"""

import aiosqlite


def get_migration_id() -> str:
    """Возвращает уникальный ID миграции."""
    return "005_oauth_tokens"


def get_migration_description() -> str:
    """Возвращает описание миграции."""
    return "Переход на OAuth 2.0 для Google Calendar и Tasks API"


async def migrate(conn: aiosqlite.Connection) -> str:
    """
    Выполняет миграцию.

    Args:
        conn: Подключение к базе данных

    Returns:
        Сообщение о результате миграции
    """
    try:
        # Получаем список существующих колонок
        async with conn.execute("PRAGMA table_info(conversations)") as cursor:
            rows = await cursor.fetchall()
            columns = {row[1] for row in rows}

        messages = []

        # Удаляем старые поля (SQLite не поддерживает DROP COLUMN напрямую)
        # Нужно пересоздать таблицу
        if "service_account_json" in columns or "user_email" in columns:
            # Создаем временную таблицу с новой структурой
            await conn.execute("""
                CREATE TABLE conversations_new (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    active_messages_count INTEGER,
                    subscription_verified INTEGER,
                    referral_code TEXT,
                    timezone_offset INTEGER DEFAULT 3,
                    user_email TEXT,
                    oauth_access_token TEXT,
                    oauth_refresh_token TEXT,
                    oauth_token_expiry TEXT
                )
            """)

            # Копируем данные (сохраняем user_email, удаляем только service_account_json)
            await conn.execute("""
                INSERT INTO conversations_new (
                    id, name, active_messages_count,
                    subscription_verified, referral_code, timezone_offset, user_email
                )
                SELECT
                    id, name, active_messages_count,
                    subscription_verified, referral_code,
                    COALESCE(timezone_offset, 3),
                    user_email
                FROM conversations
            """)

            # Удаляем старую таблицу и переименовываем новую
            await conn.execute("DROP TABLE conversations")
            await conn.execute("ALTER TABLE conversations_new RENAME TO conversations")

            messages.append("✅ Удалено поле service_account_json")
            messages.append("✅ Сохранено поле user_email")
            messages.append("✅ Добавлены поля для OAuth токенов")
        else:
            # Просто добавляем новые поля если старых нет
            if "oauth_access_token" not in columns:
                await conn.execute("""
                    ALTER TABLE conversations
                    ADD COLUMN oauth_access_token TEXT DEFAULT NULL
                """)
                messages.append("✅ Добавлено поле oauth_access_token")

            if "oauth_refresh_token" not in columns:
                await conn.execute("""
                    ALTER TABLE conversations
                    ADD COLUMN oauth_refresh_token TEXT DEFAULT NULL
                """)
                messages.append("✅ Добавлено поле oauth_refresh_token")

            if "oauth_token_expiry" not in columns:
                await conn.execute("""
                    ALTER TABLE conversations
                    ADD COLUMN oauth_token_expiry TEXT DEFAULT NULL
                """)
                messages.append("✅ Добавлено поле oauth_token_expiry")

        # Также удаляем таблицу user_calendars если она существует
        async with conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='user_calendars'
        """) as cursor:
            result = await cursor.fetchone()
            if result:
                await conn.execute("DROP TABLE user_calendars")
                messages.append("✅ Удалена таблица user_calendars (больше не нужна)")

        await conn.commit()

        if not messages:
            return "✅ Миграция уже применена"

        return "\n".join(messages)

    except Exception as e:
        await conn.rollback()
        return f"❌ Ошибка миграции: {e}"


async def rollback(conn: aiosqlite.Connection) -> str:
    """
    Откатывает миграцию (невозможно полностью).

    Args:
        conn: Подключение к базе данных

    Returns:
        Сообщение о результате отката
    """
    return "⚠️ Откат этой миграции невозможен - данные service_account были удалены"

