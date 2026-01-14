"""
Миграция: добавление настроек ежедневной рассылки.

Добавляет поля для управления автоматической ежедневной рассылкой событий и задач:
- daily_digest_enabled: включена/выключена рассылка (по умолчанию True)
- daily_digest_hour: час отправки в локальном времени пользователя (по умолчанию 9)
"""

import aiosqlite


def get_migration_id() -> str:
    """Возвращает уникальный ID миграции."""
    return "008_add_daily_digest"


def get_migration_description() -> str:
    """Возвращает описание миграции."""
    return "Добавление настроек ежедневной рассылки (daily_digest_enabled, daily_digest_hour)"


async def migrate(conn: aiosqlite.Connection) -> str:
    """
    Выполняет миграцию.

    Args:
        conn: Подключение к базе данных

    Returns:
        Сообщение о результате миграции
    """
    try:
        # Проверяем, существует ли уже поле daily_digest_enabled
        async with conn.execute("PRAGMA table_info(conversations)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

        if "daily_digest_enabled" in column_names:
            return "✅ Поля для ежедневной рассылки уже существуют"

        # Добавляем поле daily_digest_enabled (по умолчанию включено)
        await conn.execute("""
            ALTER TABLE conversations
            ADD COLUMN daily_digest_enabled INTEGER DEFAULT 1
        """)

        # Добавляем поле daily_digest_hour (по умолчанию 9 утра)
        await conn.execute("""
            ALTER TABLE conversations
            ADD COLUMN daily_digest_hour INTEGER DEFAULT 9
        """)

        await conn.commit()

        # Подсчитываем количество затронутых пользователей
        async with conn.execute("SELECT COUNT(*) FROM conversations") as cursor:
            user_count = (await cursor.fetchone())[0]

        return (
            f"✅ Добавлены поля для ежедневной рассылки:\n"
            f"  - daily_digest_enabled (по умолчанию: включено)\n"
            f"  - daily_digest_hour (по умолчанию: 9:00)\n"
            f"  Затронуто пользователей: {user_count}"
        )

    except Exception as e:
        await conn.rollback()
        return f"❌ Ошибка миграции: {e}"


async def rollback(conn: aiosqlite.Connection) -> str:
    """
    Откатывает миграцию.

    Note: SQLite не поддерживает DROP COLUMN напрямую в старых версиях,
    поэтому откат требует пересоздания таблицы.

    Args:
        conn: Подключение к базе данных

    Returns:
        Сообщение о результате отката
    """
    try:
        # Проверяем, существует ли поле
        async with conn.execute("PRAGMA table_info(conversations)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]

        if "daily_digest_enabled" not in column_names:
            return "✅ Поля для ежедневной рассылки уже отсутствуют"

        # Создаем временную таблицу без полей daily_digest
        await conn.execute("""
            CREATE TABLE conversations_backup (
                id INTEGER PRIMARY KEY,
                name TEXT,
                active_messages_count INTEGER,
                subscription_verified INTEGER,
                referral_code TEXT DEFAULT NULL,
                timezone_offset INTEGER DEFAULT NULL,
                user_email TEXT DEFAULT NULL,
                oauth_access_token TEXT DEFAULT NULL,
                oauth_refresh_token TEXT DEFAULT NULL,
                oauth_token_expiry TEXT DEFAULT NULL
            )
        """)

        # Копируем данные
        await conn.execute("""
            INSERT INTO conversations_backup
            SELECT id, name, active_messages_count, subscription_verified,
                   referral_code, timezone_offset, user_email,
                   oauth_access_token, oauth_refresh_token, oauth_token_expiry
            FROM conversations
        """)

        # Удаляем старую таблицу
        await conn.execute("DROP TABLE conversations")

        # Переименовываем backup в основную таблицу
        await conn.execute("ALTER TABLE conversations_backup RENAME TO conversations")

        await conn.commit()
        return "✅ Поля ежедневной рассылки удалены"

    except Exception as e:
        await conn.rollback()
        return f"❌ Ошибка отката: {e}"
