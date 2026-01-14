"""
Миграция: установка часового пояса по умолчанию.

Устанавливает timezone_offset=3 (Москва, UTC+3) для всех пользователей,
у которых часовой пояс не был установлен (NULL).
"""

import aiosqlite


def get_migration_id() -> str:
    """Возвращает уникальный ID миграции."""
    return "009_set_default_timezone"


def get_migration_description() -> str:
    """Возвращает описание миграции."""
    return "Установка timezone_offset=3 (Москва, UTC+3) для пользователей по умолчанию"


async def migrate(conn: aiosqlite.Connection) -> str:
    """
    Выполняет миграцию.

    Args:
        conn: Подключение к базе данных

    Returns:
        Сообщение о результате миграции
    """
    try:
        # Подсчитываем количество пользователей без timezone
        async with conn.execute(
            "SELECT COUNT(*) FROM conversations WHERE timezone_offset IS NULL"
        ) as cursor:
            users_without_timezone = (await cursor.fetchone())[0]

        if users_without_timezone == 0:
            return "✅ У всех пользователей уже установлен часовой пояс"

        # Устанавливаем timezone_offset=3 для всех пользователей, у которых он NULL
        await conn.execute("""
            UPDATE conversations
            SET timezone_offset = 3
            WHERE timezone_offset IS NULL
        """)

        await conn.commit()

        return (
            f"✅ Установлен часовой пояс по умолчанию (UTC+3, Москва):\n"
            f"  Обновлено пользователей: {users_without_timezone}"
        )

    except Exception as e:
        await conn.rollback()
        return f"❌ Ошибка миграции: {e}"


async def rollback(conn: aiosqlite.Connection) -> str:
    """
    Откатывает миграцию.

    Сбрасывает timezone_offset в NULL для пользователей,
    у которых он был установлен в 3.

    Args:
        conn: Подключение к базе данных

    Returns:
        Сообщение о результате отката
    """
    try:
        # Подсчитываем количество пользователей с timezone=3
        async with conn.execute(
            "SELECT COUNT(*) FROM conversations WHERE timezone_offset = 3"
        ) as cursor:
            users_with_timezone_3 = (await cursor.fetchone())[0]

        if users_with_timezone_3 == 0:
            return "✅ Нет пользователей с timezone_offset=3"

        # Сбрасываем timezone_offset в NULL
        # ВНИМАНИЕ: Это откатит изменения для ВСЕХ пользователей с timezone=3,
        # включая тех, кто установил его вручную
        await conn.execute("""
            UPDATE conversations
            SET timezone_offset = NULL
            WHERE timezone_offset = 3
        """)

        await conn.commit()

        return (
            f"✅ Часовой пояс сброшен в NULL:\n"
            f"  Обновлено пользователей: {users_with_timezone_3}\n"
            f"  ⚠️ Откат затронул всех пользователей с timezone=3"
        )

    except Exception as e:
        await conn.rollback()
        return f"❌ Ошибка отката: {e}"
