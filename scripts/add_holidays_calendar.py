"""
Утилита для управления календарями пользователей.

Этот скрипт позволяет добавлять публичные календари (например, праздники)
всем существующим пользователям или конкретному пользователю.
"""

import asyncio
import os
import sys

# Добавляем корневую директорию в путь для импорта
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Загружаем переменные окружения из .env файла в корне проекта
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(project_root, ".env"))

# Устанавливаем правильный путь к базе данных
# Если DATABASE_NAME относительный, делаем его абсолютным относительно корня проекта
database_name = os.environ.get("DATABASE_NAME", "data/users.db")
if not os.path.isabs(database_name):
    database_name = os.path.join(project_root, database_name)
    os.environ["DATABASE_NAME"] = database_name

from core.database import Conversation, UserCalendar  # noqa: E402
from core.public_calendars import RUSSIAN_HOLIDAYS  # noqa: E402


def check_database_permissions() -> tuple[bool, str]:
    """
    Проверяет права доступа к базе данных.

    Returns:
        Кортеж (успешно, сообщение об ошибке)
    """
    db_path = os.environ.get("DATABASE_NAME", "data/users.db")
    db_dir = os.path.dirname(db_path)

    # Проверяем существование директории
    if not os.path.exists(db_dir):
        return False, f"Директория {db_dir} не существует"

    # Проверяем права на запись в директорию
    if not os.access(db_dir, os.W_OK):
        return (
            False,
            f"Нет прав на запись в директорию {db_dir}. Выполните: chmod 755 {db_dir}",
        )

    # Проверяем существование файла базы данных и права на запись
    if os.path.exists(db_path) and not os.access(db_path, os.W_OK):
        return (
            False,
            f"Нет прав на запись в файл {db_path}. Выполните: chmod 644 {db_path}",
        )

    return True, ""


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
        error_msg = str(e)
        if "readonly" in error_msg.lower() or "read-only" in error_msg.lower():
            print(
                f"✗ USER{user_id}: Ошибка доступа к базе данных (readonly).\n"
                f"  Проверьте права доступа к файлу базы данных.\n"
                f"  Выполните на сервере:\n"
                f"    chmod 644 {os.environ.get('DATABASE_NAME', 'data/users.db')}\n"
                f"    chmod 755 {os.path.dirname(os.environ.get('DATABASE_NAME', 'data/users.db'))}"
            )
        else:
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

        # Проверяем наличие OAuth токенов (новый формат авторизации)
        if not conversation.oauth_access_token:
            print(
                f"⊘ USER{user_id}: Календарь не настроен (нет OAuth токенов), пропускаем"
            )
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

    # Проверяем права доступа к базе данных
    can_write, error_msg = check_database_permissions()
    if not can_write:
        print(f"❌ Ошибка: {error_msg}")
        sys.exit(1)

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
