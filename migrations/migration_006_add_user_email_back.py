"""
Миграция: добавление поля user_email обратно.

После миграции на OAuth поле user_email всё ещё нужно для кеширования
email пользователя, полученного из primary календаря через OAuth API.
"""

import aiosqlite


def get_migration_id() -> str:
    """Возвращает уникальный ID миграции."""
    return "006_add_user_email_back"


def get_migration_description() -> str:
    """Возвращает описание миграции."""
    return "Добавление поля user_email для кеширования email пользователя"


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

        # Проверяем, есть ли уже поле user_email
        if "user_email" in columns:
            return "✅ Поле user_email уже существует"

        # Добавляем поле user_email
        await conn.execute("""
            ALTER TABLE conversations
            ADD COLUMN user_email TEXT DEFAULT NULL
        """)

        await conn.commit()

        return "✅ Добавлено поле user_email в таблицу conversations"

    except Exception as e:
        await conn.rollback()
        return f"❌ Ошибка миграции: {e}"


async def rollback(conn: aiosqlite.Connection) -> str:
    """
    Откатывает миграцию.

    SQLite не поддерживает DROP COLUMN напрямую, поэтому откат требует
    пересоздания таблицы. Обычно откат не нужен для добавления колонки.

    Args:
        conn: Подключение к базе данных

    Returns:
        Сообщение о результате отката
    """
    return "⚠️ Откат не требуется - поле user_email можно оставить в таблице"
