#!/usr/bin/env python3
"""
Скрипт для тестирования доступности моделей через OpenRouter.
Использует тот же подход, что и основной код бота.
"""

import asyncio
import json
import os
import sys

import aiohttp
from dotenv import load_dotenv

# Добавляем корневую директорию проекта в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()
LLM_TOKEN = os.environ.get("LLM_TOKEN")


async def test_model(model_name: str, api_key: str = LLM_TOKEN) -> tuple[bool, str]:
    """
    Тестирует доступность модели через OpenRouter.

    Args:
        model_name: Название модели для тестирования
        api_key: API ключ OpenRouter

    Returns:
        Кортеж (успех, сообщение/ошибка)
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Простой тестовый запрос
    data = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": "Привет! Это тестовый запрос. Ответь коротко: работает ли модель?",
            }
        ],
    }

    try:
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                url,
                headers=headers,
                data=json.dumps(data),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response,
        ):
            response_text = await response.text()

            # Если статус не 200, значит ошибка
            if response.status != 200:
                try:
                    error_json = json.loads(response_text)
                    error_message = error_json.get("error", {}).get(
                        "message", response_text
                    )
                    return False, f"HTTP {response.status}: {error_message}"
                except json.JSONDecodeError:
                    return False, f"HTTP {response.status}: {response_text[:200]}"

            # Парсим успешный ответ
            try:
                response_json = json.loads(response_text)

                if "choices" in response_json and len(response_json["choices"]) > 0:
                    content = response_json["choices"][0]["message"]["content"]
                    if content is None or content.strip() == "":
                        return False, "Модель вернула пустой ответ"
                    return True, content
                return False, f"Нет choices в ответе: {response_json}"

            except json.JSONDecodeError as e:
                return (
                    False,
                    f"Ошибка парсинга JSON ответа: {e}\nОтвет: {response_text[:200]}",
                )

    except aiohttp.ClientResponseError as e:
        return False, f"HTTP ошибка: {e}"
    except aiohttp.ClientError as e:
        return False, f"Сетевая ошибка: {e}"
    except TimeoutError:
        return False, "Превышено время ожидания ответа (30 сек)"
    except Exception as e:
        return False, f"Неожиданная ошибка: {type(e).__name__}: {e}"


async def main():
    """Главная функция скрипта."""

    # Проверяем наличие API ключа
    if not LLM_TOKEN:
        print("❌ Ошибка: не найден LLM_TOKEN в переменных окружения")
        print("Убедитесь, что файл .env содержит переменную LLM_TOKEN")
        return

    print("=" * 60)
    print("Скрипт тестирования моделей OpenRouter")
    print("=" * 60)
    print()
    print("Примеры моделей:")
    print("  - deepseek/deepseek-chat")
    print("  - anthropic/claude-3.5-sonnet")
    print("  - openai/gpt-4o")
    print("  - google/gemini-2.0-flash-001")
    print()
    print("Для выхода введите: exit")
    print("=" * 60)

    # Бесконечный цикл для тестирования моделей
    while True:
        print()
        model_name = input("Модель: ").strip()

        # Проверка на выход
        if model_name.lower() == "exit":
            print()
            print("👋 Выход из программы")
            break

        # Проверка на пустой ввод
        if not model_name:
            print("⚠️ Название модели не может быть пустым")
            continue

        print()
        print(f"🔄 Отправляю тестовый запрос к модели: {model_name}")
        print()

        # Тестируем модель
        success, message = await test_model(model_name)

        # Выводим результат
        print("-" * 60)
        if success:
            print("✅ УСПЕХ! Модель доступна и работает")
            print()
            print("Ответ модели:")
            print(message)
        else:
            print("❌ ОШИБКА! Модель недоступна")
            print()
            print("Описание ошибки:")
            print(message)
        print("-" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ Прервано пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback

        traceback.print_exc()
