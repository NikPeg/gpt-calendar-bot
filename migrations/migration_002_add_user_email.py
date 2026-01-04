"""
Миграция: добавление поля user_email в таблицу conversations.
Это поле хранит email пользователя Google Calendar для доступа к его календарю.
"""

import os

import aiosqlite
from dotenv import load_dotenv

load_dotenv()
DATABASE_NAME = os.environ.get("DATABASE_NAME", "users.db")


async def upgrade():
    """
    Добавляет поле user_email в таблицу conversations.
    Это поле будет хранить email пользователя Google Calendar (например, Gmail).
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.cursor()

        # Проверяем, существует ли таблица
        await cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'"
        )
        table_exists = await cursor.fetchone()

        if not table_exists:
            return "Таблица conversations не существует, миграция пропущена"

        # Проверяем, существует ли уже поле
        await cursor.execute("PRAGMA table_info(conversations)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]

        if "user_email" not in column_names:
            # Добавляем поле user_email
            await cursor.execute(
                """
                ALTER TABLE conversations
                ADD COLUMN user_email TEXT DEFAULT NULL
                """
            )
            await db.commit()
            return "Поле user_email добавлено в таблицу conversations"
        return "Поле user_email уже существует"
