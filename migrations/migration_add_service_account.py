"""
Миграция: добавление поля service_account_json в таблицу conversations.
"""

import os

import aiosqlite
from dotenv import load_dotenv

load_dotenv()
DATABASE_NAME = os.environ.get("DATABASE_NAME", "users.db")


async def upgrade():
    """
    Добавляет поле service_account_json в таблицу conversations.
    Это поле будет хранить JSON сервисного аккаунта Google для доступа к календарю.
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.cursor()
        
        # Проверяем, существует ли уже поле
        await cursor.execute("PRAGMA table_info(conversations)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if "service_account_json" not in column_names:
            # Добавляем поле service_account_json
            await cursor.execute(
                """
                ALTER TABLE conversations
                ADD COLUMN service_account_json TEXT DEFAULT NULL
                """
            )
            await db.commit()
            return "Поле service_account_json добавлено в таблицу conversations"
        return "Поле service_account_json уже существует"

