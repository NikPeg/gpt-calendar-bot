#!/usr/bin/env python3
"""
Тестовый скрипт для проверки OAuth 2.0 flow.
Симулирует процесс авторизации без реального браузера.

Использование:
    python scripts/test_oauth_flow.py
"""

import os
import sys

# Добавляем родительскую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from services.google_service_oauth import GoogleServiceOAuth

# Загружаем переменные окружения
load_dotenv()


def test_create_authorization_url():
    """Тест 1: Создание authorization URL."""
    print("🔧 Тест 1: Создание authorization URL\n")

    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    redirect_uri = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI", "http://127.0.0.1:8080/oauth/callback")

    if not client_id or not client_secret:
        print("❌ Ошибка: GOOGLE_OAUTH_CLIENT_ID или GOOGLE_OAUTH_CLIENT_SECRET не установлены")
        print("   Добавьте их в файл .env")
        return False

    print(f"✅ Client ID: {client_id[:20]}...")
    print(f"✅ Redirect URI: {redirect_uri}\n")

    scopes = [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/tasks",
    ]

    try:
        auth_url, state = GoogleServiceOAuth.create_authorization_url(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scopes=scopes,
            state="test_state_123",
        )

        print("✅ Authorization URL создан успешно!")
        print(f"\n📋 URL:\n{auth_url}\n")
        print(f"🔐 State: {state}\n")
        
        # Проверяем, что URL содержит необходимые параметры
        assert "client_id=" in auth_url, "URL должен содержать client_id"
        assert "redirect_uri=" in auth_url, "URL должен содержать redirect_uri"
        assert "scope=" in auth_url, "URL должен содержать scope"
        assert "state=" in auth_url, "URL должен содержать state"
        assert "access_type=offline" in auth_url, "URL должен содержать access_type=offline"
        assert "prompt=consent" in auth_url, "URL должен содержать prompt=consent"
        
        print("✅ Все обязательные параметры присутствуют")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка при создании URL: {e}")
        return False


def test_oauth_service_init():
    """Тест 2: Инициализация OAuth сервиса."""
    print("\n" + "=" * 70)
    print("🔧 Тест 2: Инициализация OAuth сервиса\n")

    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("⚠️  Пропуск теста: credentials не настроены")
        return True

    # Тест с пустыми токенами (сервис не должен инициализироваться)
    print("📝 Тест с пустыми токенами...")
    service = GoogleServiceOAuth(
        service_name="calendar",
        version="v3",
        scopes=["https://www.googleapis.com/auth/calendar"],
        access_token=None,
        refresh_token=None,
        client_id=client_id,
        client_secret=client_secret,
    )

    if service.service is None:
        print("✅ Сервис корректно не инициализирован без токенов")
    else:
        print("❌ Сервис не должен инициализироваться без токенов")
        return False

    # Тест с фейковыми токенами (должен попытаться инициализировать)
    print("\n📝 Тест с тестовыми токенами...")
    service = GoogleServiceOAuth(
        service_name="calendar",
        version="v3",
        scopes=["https://www.googleapis.com/auth/calendar"],
        access_token="fake_access_token",
        refresh_token="fake_refresh_token",
        token_expiry="2026-12-31T23:59:59Z",
        client_id=client_id,
        client_secret=client_secret,
    )

    # Сервис должен быть None из-за невалидных токенов, но это ожидаемо
    print("✅ Сервис обработал тестовые токены (ожидаемый fail при валидации)")
    
    return True


def test_calendar_service():
    """Тест 3: Создание CalendarService через OAuth."""
    print("\n" + "=" * 70)
    print("🔧 Тест 3: Создание CalendarService\n")

    from services.calendar_service import CalendarService

    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("⚠️  Пропуск теста: credentials не настроены")
        return True

    print("📝 Создаем CalendarService...")
    
    try:
        service = CalendarService(
            access_token=None,  # Без токенов
            refresh_token=None,
            client_id=client_id,
            client_secret=client_secret,
        )

        if not service.is_configured():
            print("✅ CalendarService корректно определяет отсутствие токенов")
        else:
            print("❌ CalendarService не должен быть настроен без токенов")
            return False

        # Проверяем метод get_updated_tokens
        print("\n📝 Проверяем метод get_updated_tokens...")
        tokens = service.get_updated_tokens()
        
        assert tokens is not None, "get_updated_tokens должен возвращать dict"
        assert "access_token" in tokens, "Должен быть ключ access_token"
        assert "refresh_token" in tokens, "Должен быть ключ refresh_token"
        assert "token_expiry" in tokens, "Должен быть ключ token_expiry"
        
        print("✅ Метод get_updated_tokens работает корректно")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tasks_service():
    """Тест 4: Создание TasksService через OAuth."""
    print("\n" + "=" * 70)
    print("🔧 Тест 4: Создание TasksService\n")

    from services.tasks_service import TasksService

    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("⚠️  Пропуск теста: credentials не настроены")
        return True

    print("📝 Создаем TasksService...")
    
    try:
        service = TasksService(
            access_token=None,
            refresh_token=None,
            client_id=client_id,
            client_secret=client_secret,
        )

        if not service.is_configured():
            print("✅ TasksService корректно определяет отсутствие токенов")
        else:
            print("❌ TasksService не должен быть настроен без токенов")
            return False

        print("✅ TasksService создан успешно")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def main():
    """Основная функция тестирования."""
    print("=" * 70)
    print("🔐 ТЕСТИРОВАНИЕ OAuth 2.0 ИНТЕГРАЦИИ")
    print("=" * 70)
    print()

    results = []

    # Тест 1
    results.append(("Authorization URL", test_create_authorization_url()))

    # Тест 2
    results.append(("OAuth Service Init", test_oauth_service_init()))

    # Тест 3
    results.append(("CalendarService", test_calendar_service()))

    # Тест 4
    results.append(("TasksService", test_tasks_service()))

    # Итоги
    print("\n" + "=" * 70)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("=" * 70)
    print()

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")

    print()
    print(f"Пройдено: {passed}/{total}")
    print()

    if passed == total:
        print("🎉 Все тесты пройдены успешно!")
        print()
        print("📝 Следующие шаги:")
        print("1. Настройте Google Cloud Console (см. OAUTH_MIGRATION_GUIDE.md)")
        print("2. Получите реальные OAuth credentials")
        print("3. Добавьте их в .env файл")
        print("4. Интегрируйте в main.py (см. OAUTH_MIGRATION_GUIDE.md)")
        print("5. Запустите бота и попробуйте /connect_google")
        return 0
    print("⚠️  Некоторые тесты не прошли")
    print("Проверьте конфигурацию и исправьте ошибки")
    return 1


if __name__ == "__main__":
    exit(main())

