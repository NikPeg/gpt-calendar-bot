"""
Утилита для управления календарями пользователей.

Этот скрипт позволяет добавлять публичные календари (например, праздники)
всем существующим пользователям или конкретному пользователю.
"""

import asyncio
import os
import sys

# Добавляем корневую директорию в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import Conversation, UserCalendar
from core.public_calendars import RUSSIAN_HOLIDAYS


async def add_holidays_calendar_to_user(user_id: int) -> bool:
    """
    Добавляет календарь праздников России конкретному пользователю.

    Args:
        user_id: ID пользователя

    Returns:
        True если успешно, False при ошибке
    """
    try:
        # Проверяем, есть ли уже такой календарь
        calendars = await UserCalendar.get_user_calendars(user_id, enabled_only=False)
        for cal in calendars:
            if cal.calendar_id == RUSSIAN_HOLIDAYS.calendar_id:
                print(f"✓ USER{user_id}: Календарь праздников уже добавлен")
                return True

        # Добавляем календарь
        calendar = await UserCalendar.add_public_calendar(
            user_id=user_id,
            calendar_id=RUSSIAN_HOLIDAYS.calendar_id,
            calendar_name=RUSSIAN_HOLIDAYS.name,
        )

        print(
            f"✓ USER{user_id}: Добавлен календарь '{RUSSIAN_HOLIDAYS.name}' (ID: {calendar.id})"
        )
        return True

    except Exception as e:
        print(f"✗ USER{user_id}: Ошибка при добавлении календаря: {e}")
        return False


async def add_holidays_calendar_to_all() -> dict[str, int]:
    """
    Добавляет календарь праздников России всем пользователям с настроенным календарем.

    Returns:
        Словарь со статистикой: {'success': N, 'failed': M, 'skipped': K}
    """
    stats = {"success": 0, "failed": 0, "skipped": 0}

    # Получаем всех пользователей
    user_ids = await Conversation.get_ids_from_table()

    print(f"Найдено пользователей: {len(user_ids)}\n")

    for user_id in user_ids:
        # Проверяем, настроен ли у пользователя календарь
        conversation = Conversation(user_id)
        await conversation.get_from_db()

        if not conversation.service_account_json:
            print(f"⊘ USER{user_id}: Календарь не настроен, пропускаем")
            stats["skipped"] += 1
            continue

        # Добавляем календарь
        success = await add_holidays_calendar_to_user(user_id)
        if success:
            stats["success"] += 1
        else:
            stats["failed"] += 1

    return stats


async def main():
    """Главная функция."""
    print("=" * 60)
    print("Утилита добавления календаря праздников России")
    print("=" * 60)
    print()

    # Проверяем аргументы командной строки
    if len(sys.argv) > 1:
        # Добавляем календарь конкретному пользователю
        try:
            user_id = int(sys.argv[1])
            print(f"Режим: добавление календаря пользователю {user_id}\n")
            success = await add_holidays_calendar_to_user(user_id)
            if success:
                print("\n✓ Календарь успешно добавлен")
            else:
                print("\n✗ Не удалось добавить календарь")
        except ValueError:
            print("Ошибка: укажите корректный ID пользователя (число)")
            sys.exit(1)
    else:
        # Добавляем календарь всем пользователям
        print("Режим: добавление календаря всем пользователям\n")

        confirmation = input(
            "Вы уверены, что хотите добавить календарь праздников всем пользователям? (yes/no): "
        )
        if confirmation.lower() not in ["yes", "y", "да"]:
            print("Операция отменена")
            sys.exit(0)

        print()
        stats = await add_holidays_calendar_to_all()

        print()
        print("=" * 60)
        print("Результаты:")
        print(f"  Успешно: {stats['success']}")
        print(f"  Ошибки: {stats['failed']}")
        print(f"  Пропущено: {stats['skipped']}")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

