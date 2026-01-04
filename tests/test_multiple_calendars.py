"""
Тесты для работы с множественными календарями.

Проверяет функциональность добавления и использования нескольких календарей,
включая публичные календари (праздники).
"""

import asyncio
import os
import sys

import pytest

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import UserCalendar, check_db
from core.public_calendars import RUSSIAN_HOLIDAYS


@pytest.fixture(scope="function", autouse=True)
def setup_database():
    """Инициализирует БД перед тестами."""
    import aiosqlite

    async def init_db():
        await check_db()
        # Создаем таблицу user_calendars
        async with aiosqlite.connect(
            os.environ.get("DATABASE_NAME", "users.db")
        ) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS user_calendars (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    calendar_id TEXT NOT NULL,
                    calendar_name TEXT,
                    calendar_type TEXT NOT NULL,
                    is_readonly INTEGER NOT NULL DEFAULT 0,
                    is_enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    UNIQUE(user_id, calendar_id)
                )
                """
            )
            await db.commit()

    asyncio.run(init_db())
    yield


@pytest.mark.asyncio
async def test_user_calendar_creation():
    """Тест создания календаря пользователя."""
    calendar = UserCalendar(
        user_id=999999,
        calendar_id="test@example.com",
        calendar_name="Test Calendar",
        calendar_type=UserCalendar.TYPE_PRIMARY,
        is_readonly=False,
        is_enabled=True,
    )

    await calendar.save_to_db()
    assert calendar.id is not None

    # Очистка
    await calendar.delete_from_db()


@pytest.mark.asyncio
async def test_add_public_calendar():
    """Тест добавления публичного календаря."""
    user_id = 999998

    # Добавляем публичный календарь
    calendar = await UserCalendar.add_public_calendar(
        user_id=user_id,
        calendar_id=RUSSIAN_HOLIDAYS.calendar_id,
        calendar_name=RUSSIAN_HOLIDAYS.name,
    )

    assert calendar.id is not None
    assert calendar.calendar_type == UserCalendar.TYPE_PUBLIC
    assert calendar.is_readonly is True
    assert calendar.is_enabled is True

    # Проверяем, что календарь сохранился
    calendars = await UserCalendar.get_user_calendars(user_id)
    assert len(calendars) > 0
    assert any(c.calendar_id == RUSSIAN_HOLIDAYS.calendar_id for c in calendars)

    # Очистка
    await calendar.delete_from_db()


@pytest.mark.asyncio
async def test_get_primary_calendar():
    """Тест получения основного календаря."""
    user_id = 999997

    # Создаем основной календарь
    primary = UserCalendar(
        user_id=user_id,
        calendar_id="primary@example.com",
        calendar_name="Primary",
        calendar_type=UserCalendar.TYPE_PRIMARY,
        is_readonly=False,
        is_enabled=True,
    )
    await primary.save_to_db()

    # Создаем публичный календарь
    public = await UserCalendar.add_public_calendar(
        user_id=user_id,
        calendar_id=RUSSIAN_HOLIDAYS.calendar_id,
        calendar_name=RUSSIAN_HOLIDAYS.name,
    )

    # Получаем основной календарь
    retrieved_primary = await UserCalendar.get_primary_calendar(user_id)
    assert retrieved_primary is not None
    assert retrieved_primary.calendar_id == "primary@example.com"
    assert retrieved_primary.calendar_type == UserCalendar.TYPE_PRIMARY

    # Очистка
    await primary.delete_from_db()
    await public.delete_from_db()


@pytest.mark.asyncio
async def test_get_enabled_calendar_ids():
    """Тест получения списка включенных календарей."""
    user_id = 999996

    # Создаем несколько календарей
    cal1 = UserCalendar(
        user_id=user_id,
        calendar_id="cal1@example.com",
        calendar_name="Calendar 1",
        calendar_type=UserCalendar.TYPE_PRIMARY,
        is_enabled=True,
    )
    await cal1.save_to_db()

    cal2 = await UserCalendar.add_public_calendar(
        user_id=user_id,
        calendar_id=RUSSIAN_HOLIDAYS.calendar_id,
        calendar_name=RUSSIAN_HOLIDAYS.name,
    )

    cal3 = UserCalendar(
        user_id=user_id,
        calendar_id="cal3@example.com",
        calendar_name="Calendar 3",
        calendar_type=UserCalendar.TYPE_SHARED,
        is_enabled=False,  # Отключен
    )
    await cal3.save_to_db()

    # Получаем только включенные
    calendar_ids = await UserCalendar.get_enabled_calendar_ids(user_id)
    assert len(calendar_ids) == 2
    assert "cal1@example.com" in calendar_ids
    assert RUSSIAN_HOLIDAYS.calendar_id in calendar_ids
    assert "cal3@example.com" not in calendar_ids

    # Очистка
    await cal1.delete_from_db()
    await cal2.delete_from_db()
    await cal3.delete_from_db()


@pytest.mark.asyncio
async def test_calendar_update():
    """Тест обновления календаря."""
    user_id = 999995

    calendar = UserCalendar(
        user_id=user_id,
        calendar_id="test@example.com",
        calendar_name="Original Name",
        calendar_type=UserCalendar.TYPE_PRIMARY,
        is_enabled=True,
    )
    await calendar.save_to_db()

    # Обновляем
    calendar.calendar_name = "Updated Name"
    calendar.is_enabled = False
    await calendar.update_in_db()

    # Проверяем
    calendars = await UserCalendar.get_user_calendars(user_id, enabled_only=False)
    updated = next((c for c in calendars if c.id == calendar.id), None)

    assert updated is not None
    assert updated.calendar_name == "Updated Name"
    assert updated.is_enabled is False

    # Очистка
    await calendar.delete_from_db()


@pytest.mark.asyncio
async def test_public_calendars_constants():
    """Тест констант публичных календарей."""
    from core.public_calendars import PUBLIC_CALENDARS, get_public_calendar

    # Проверяем, что праздники России доступны
    assert "ru_holidays" in PUBLIC_CALENDARS

    holidays = get_public_calendar("ru_holidays")
    assert holidays is not None
    assert holidays.calendar_id == "ru.russian#holiday@group.v.calendar.google.com"
    assert holidays.name == "Праздники России"
    assert holidays.locale == "ru"


if __name__ == "__main__":
    # Запуск тестов напрямую
    pytest.main([__file__, "-v"])

