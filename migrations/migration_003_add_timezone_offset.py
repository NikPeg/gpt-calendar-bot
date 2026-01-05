"""
Миграция: добавление поля timezone_offset в таблицу conversations.
Это поле хранит смещение часового пояса пользователя от UTC в часах.
"""

import os

import aiosqlite
from dotenv import load_dotenv

load_dotenv()
DATABASE_NAME = os.environ.get("DATABASE_NAME", "data/users.db")


async def upgrade():
    """
    Добавляет поле timezone_offset в таблицу conversations.
    Это поле будет хранить смещение часового пояса пользователя от UTC в часах.
    Например, для Москвы (UTC+3) значение будет 3, для Нью-Йорка (UTC-5) будет -5.
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

        if "timezone_offset" not in column_names:
            # Добавляем поле timezone_offset
            await cursor.execute(
                """
                ALTER TABLE conversations
                ADD COLUMN timezone_offset INTEGER DEFAULT NULL
                """
            )
            await db.commit()
            return "Поле timezone_offset добавлено в таблицу conversations"
        return "Поле timezone_offset уже существует"
