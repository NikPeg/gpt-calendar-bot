"""
Миграция: переход на OAuth 2.0 для Google API.

Удаляет старые поля service_account_json и user_email.
Добавляет новые поля для OAuth токенов.
"""

import sqlite3


def get_migration_id() -> str:
    """Возвращает уникальный ID миграции."""
    return "005_oauth_tokens"


def get_migration_description() -> str:
    """Возвращает описание миграции."""
    return "Переход на OAuth 2.0 для Google Calendar и Tasks API"


def migrate(conn: sqlite3.Connection) -> str:
    """
    Выполняет миграцию.

    Args:
        conn: Подключение к базе данных

    Returns:
        Сообщение о результате миграции
    """
    cursor = conn.cursor()

    try:
        # Получаем список существующих колонок
        cursor.execute("PRAGMA table_info(conversations)")
        columns = {row[1] for row in cursor.fetchall()}

        messages = []

        # Удаляем старые поля (SQLite не поддерживает DROP COLUMN напрямую)
        # Нужно пересоздать таблицу
        if "service_account_json" in columns or "user_email" in columns:
            # Создаем временную таблицу с новой структурой
            cursor.execute("""
                CREATE TABLE conversations_new (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    active_messages_count INTEGER,
                    subscription_verified INTEGER,
                    referral_code TEXT,
                    timezone_offset INTEGER DEFAULT 3,
                    oauth_access_token TEXT,
                    oauth_refresh_token TEXT,
                    oauth_token_expiry TEXT
                )
            """)

            # Копируем данные (без старых полей)
            cursor.execute("""
                INSERT INTO conversations_new (
                    id, name, active_messages_count,
                    subscription_verified, referral_code, timezone_offset
                )
                SELECT
                    id, name, active_messages_count,
                    subscription_verified, referral_code,
                    COALESCE(timezone_offset, 3)
                FROM conversations
            """)

            # Удаляем старую таблицу и переименовываем новую
            cursor.execute("DROP TABLE conversations")
            cursor.execute("ALTER TABLE conversations_new RENAME TO conversations")
            
            messages.append("✅ Удалены поля service_account_json и user_email")
            messages.append("✅ Добавлены поля для OAuth токенов")
        else:
            # Просто добавляем новые поля если старых нет
            if "oauth_access_token" not in columns:
                cursor.execute("""
                    ALTER TABLE conversations
                    ADD COLUMN oauth_access_token TEXT DEFAULT NULL
                """)
                messages.append("✅ Добавлено поле oauth_access_token")

            if "oauth_refresh_token" not in columns:
                cursor.execute("""
                    ALTER TABLE conversations
                    ADD COLUMN oauth_refresh_token TEXT DEFAULT NULL
                """)
                messages.append("✅ Добавлено поле oauth_refresh_token")

            if "oauth_token_expiry" not in columns:
                cursor.execute("""
                    ALTER TABLE conversations
                    ADD COLUMN oauth_token_expiry TEXT DEFAULT NULL
                """)
                messages.append("✅ Добавлено поле oauth_token_expiry")

        # Также удаляем таблицу user_calendars если она существует
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='user_calendars'
        """)
        if cursor.fetchone():
            cursor.execute("DROP TABLE user_calendars")
            messages.append("✅ Удалена таблица user_calendars (больше не нужна)")

        conn.commit()
        
        if not messages:
            return "✅ Миграция уже применена"
        
        return "\n".join(messages)

    except Exception as e:
        conn.rollback()
        return f"❌ Ошибка миграции: {e}"


def rollback(conn: sqlite3.Connection) -> str:
    """
    Откатывает миграцию (невозможно полностью).

    Args:
        conn: Подключение к базе данных

    Returns:
        Сообщение о результате отката
    """
    return "⚠️ Откат этой миграции невозможен - данные service_account были удалены"

