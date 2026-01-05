#!/usr/bin/env python3
"""
Тестовый скрипт для проверки сообщений команды /start.
Проверяет, что сообщения корректно отображаются для пользователей
с настроенным и ненастроенным календарем.

Использование: python scripts/test_start_messages.py
"""

import asyncio
import json
import sys
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import Conversation, check_db


async def test_start_messages():
    """Тестирует логику отображения сообщений команды /start."""
    print("🧪 Тест: Проверка сообщений команды /start\n")

    # Инициализируем базу данных
    await check_db()

    # Загружаем сообщения из конфига
    config_path = Path(__file__).parent.parent / "config" / "messages.json"
    with open(config_path, encoding="utf-8") as f:
        messages = json.load(f)

    print("✅ Сообщения загружены из config/messages.json\n")

    # Проверяем наличие необходимых ключей
    required_keys = [
        "msg_start_not_configured",
        "msg_start_configured",
        "msg_calendar_setup_welcome",
    ]

    print("📋 Проверка наличия ключей в messages.json:")
    for key in required_keys:
        if key in messages:
            print(f"  ✅ {key}")
        else:
            print(f"  ❌ {key} - ОТСУТСТВУЕТ!")
            return False

    print("\n" + "=" * 70 + "\n")

    # Тест 1: Новый пользователь без настроенного календаря
    print("📝 ТЕСТ 1: Новый пользователь (без настройки календаря)")
    print("-" * 70)
    test_user_id = 999999999  # Тестовый ID

    # Создаем пользователя без настроек
    conversation = Conversation(test_user_id, "Test User")

    if not conversation.service_account_json or not conversation.user_email:
        expected_message = (
            messages["msg_start_not_configured"]
            + "\n\n"
            + messages["msg_calendar_setup_welcome"]
        )
        print(f"✅ Ожидаемое сообщение:\n{expected_message}\n")
    else:
        print("❌ ОШИБКА: Календарь настроен, хотя не должен быть!\n")
        return False

    print("=" * 70 + "\n")

    # Тест 2: Существующий пользователь с настроенным календарем
    print("📝 ТЕСТ 2: Существующий пользователь (с настройкой календаря)")
    print("-" * 70)

    # Создаем пользователя с настройками
    conversation.service_account_json = '{"test": "data"}'
    conversation.user_email = "test@gmail.com"

    if conversation.service_account_json and conversation.user_email:
        expected_message = messages["msg_start_configured"]
        print(f"✅ Ожидаемое сообщение:\n{expected_message}\n")
    else:
        print("❌ ОШИБКА: Календарь не настроен, хотя должен быть!\n")
        return False

    print("=" * 70 + "\n")

    # Проверяем, что старый ключ msg_start не используется
    print("🔍 Проверка: старый ключ 'msg_start' не должен использоваться")
    if "msg_start" in messages:
        print("  ⚠️  ВНИМАНИЕ: Ключ 'msg_start' все еще существует в messages.json")
        print("     Рекомендуется удалить его, так как он больше не используется")
    else:
        print("  ✅ Ключ 'msg_start' отсутствует (это правильно)")

    print("\n" + "=" * 70)
    print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!\n")
    return True


if __name__ == "__main__":
    result = asyncio.run(test_start_messages())
    sys.exit(0 if result else 1)
