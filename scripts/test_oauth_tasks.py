#!/usr/bin/env python3
"""
Тестовый скрипт для создания задачи в Google Tasks через OAuth 2.0.

Использование:
    1. Получение токенов:
       python scripts/test_oauth_tasks.py --get-tokens
       
    2. Создание задачи с токенами:
       python scripts/test_oauth_tasks.py --create-task
       
    3. Список задач:
       python scripts/test_oauth_tasks.py --list-tasks

Перед использованием:
    1. Настройте OAuth 2.0 Client ID в Google Cloud Console
    2. Добавьте credentials в .env:
       GOOGLE_OAUTH_CLIENT_ID=...
       GOOGLE_OAUTH_CLIENT_SECRET=...
       GOOGLE_OAUTH_REDIRECT_URI=http://127.0.0.1:8080/oauth/callback
"""

import argparse
import asyncio
import json
import os
import sys
import webbrowser
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Добавляем родительскую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from services.google_service_oauth import GoogleServiceOAuth
from services.tasks_service import TasksService

# Загружаем переменные окружения
load_dotenv()

try:
    from aiohttp import web
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


# Файл для хранения токенов
TOKENS_FILE = Path(__file__).parent / ".oauth_tokens.json"


def save_tokens(tokens: dict):
    """Сохраняет токены в файл."""
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=2)
    print(f"\n✅ Токены сохранены в {TOKENS_FILE}")


def load_tokens() -> dict | None:
    """Загружает токены из файла."""
    if not TOKENS_FILE.exists():
        return None
    
    try:
        with open(TOKENS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Ошибка при чтении токенов: {e}")
        return None


async def run_callback_server(client_id: str, client_secret: str, scopes: list[str], port: int = 8080):
    """Запускает временный callback сервер для получения authorization code."""
    received_code = None
    received_error = None
    
    async def oauth_callback(request):
        nonlocal received_code, received_error
        
        # Получаем параметры из URL
        code = request.query.get("code")
        error = request.query.get("error")
        
        if error:
            received_error = error
            return web.Response(
                text=f"<html><body><h1>❌ Ошибка авторизации</h1><p>{error}</p></body></html>",
                content_type="text/html"
            )
        
        if code:
            received_code = code
            # Обмениваем код на токены
            try:
                redirect_uri = f"http://127.0.0.1:{port}/oauth/callback"
                tokens = GoogleServiceOAuth.exchange_code_for_tokens(
                    code=code,
                    client_id=client_id,
                    client_secret=client_secret,
                    redirect_uri=redirect_uri,
                    scopes=scopes,
                )
                
                # Сохраняем токены
                save_tokens(tokens)
                
                return web.Response(
                    text="""
                    <html>
                    <head><title>Успешно!</title></head>
                    <body style="font-family: Arial; text-align: center; padding: 50px;">
                        <h1 style="color: green;">✅ Авторизация успешна!</h1>
                        <p>Токены сохранены. Теперь можете закрыть это окно.</p>
                        <p style="margin-top: 30px;">
                            <a href="https://tasks.google.com/" style="color: #4285f4; text-decoration: none;">
                                🔗 Открыть Google Tasks
                            </a>
                        </p>
                    </body>
                    </html>
                    """,
                    content_type="text/html"
                )
            except Exception as e:
                received_error = str(e)
                return web.Response(
                    text=f"<html><body><h1>❌ Ошибка при обмене кода на токены</h1><p>{str(e)}</p></body></html>",
                    content_type="text/html"
                )
        
        return web.Response(text="<html><body><h1>❌ Код не получен</h1></body></html>", content_type="text/html")
    
    # Создаем приложение
    app = web.Application()
    app.router.add_get("/oauth/callback", oauth_callback)
    
    # Запускаем сервер
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", port)
    
    print(f"🌐 Локальный сервер запущен на http://127.0.0.1:{port}")
    print("   Ожидание callback от Google...")
    print()
    
    await site.start()
    
    # Ждем получения кода или ошибки
    while received_code is None and received_error is None:
        await asyncio.sleep(0.1)
    
    # Останавливаем сервер
    await runner.cleanup()
    
    if received_error:
        print(f"\n❌ Ошибка: {received_error}")
        return None
    
    return received_code


def get_tokens():
    """Интерактивный процесс получения OAuth токенов."""
    print("=" * 70)
    print("🔐 ПОЛУЧЕНИЕ OAuth 2.0 ТОКЕНОВ")
    print("=" * 70)
    print()
    
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    port = int(os.environ.get("OAUTH_SERVER_PORT", "8080"))
    redirect_uri = f"http://127.0.0.1:{port}/oauth/callback"
    
    if not client_id or not client_secret:
        print("❌ Ошибка: GOOGLE_OAUTH_CLIENT_ID или GOOGLE_OAUTH_CLIENT_SECRET не установлены")
        print("\nДобавьте их в файл .env:")
        print("  GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com")
        print("  GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret")
        print("\nИнструкции по настройке: см. OAUTH_MIGRATION_GUIDE.md")
        return 1
    
    print(f"✅ Client ID: {client_id[:30]}...")
    print(f"✅ Redirect URI: {redirect_uri}")
    print()
    
    # Scopes для Calendar и Tasks
    scopes = [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/tasks",
    ]
    
    # Создаем authorization URL
    auth_url, state = GoogleServiceOAuth.create_authorization_url(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scopes=scopes,
    )
    
    print("📋 Шаг 1: Авторизация через браузер")
    print("-" * 70)
    
    if AIOHTTP_AVAILABLE:
        print("\n✅ Используется автоматический режим с локальным сервером")
        print("\nОткрывается браузер для авторизации...")
        print("\nЕсли браузер не открылся, перейдите по ссылке:")
        print(f"\n{auth_url}\n")
        
        # Открываем браузер
        webbrowser.open(auth_url)
        
        # Запускаем локальный callback сервер
        try:
            code = asyncio.run(run_callback_server(client_id, client_secret, scopes, port))
            if code:
                print("\n✅ Токены получены и сохранены!")
                print("\n" + "=" * 70)
                print("🎉 Готово! Теперь вы можете создавать задачи:")
                print("   python scripts/test_oauth_tasks.py --create-task")
                print("=" * 70)
                return 0
            return 1
        except Exception as e:
            print(f"\n❌ Ошибка при запуске сервера: {e}")
            print("\nПопробуйте ручной режим:")
            print("   pip install aiohttp")
            return 1
    else:
        print("\n⚠️  aiohttp не установлен - используется ручной режим")
        print("\nОткрывается браузер для авторизации...")
        print("\nЕсли браузер не открылся, перейдите по ссылке:")
        print(f"\n{auth_url}\n")
        
        # Открываем браузер
        webbrowser.open(auth_url)
        
        print("=" * 70)
        print("📋 Шаг 2: Получение кода")
        print("-" * 70)
        print("\n1. Авторизуйтесь в Google")
        print("2. Разрешите доступ к Calendar и Tasks")
        print("3. После успешной авторизации вы будете перенаправлены на redirect_uri")
        print("4. Скопируйте 'code' из URL (параметр после ?code=...)")
        print()
        
        # Запрашиваем код у пользователя
        code = input("Введите authorization code: ").strip()
        
        if not code:
            print("❌ Код не введен")
            return 1
        
        print("\n📋 Шаг 3: Обмен кода на токены")
        print("-" * 70)
        
        try:
            tokens = GoogleServiceOAuth.exchange_code_for_tokens(
                code=code,
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scopes=scopes,
            )
            
            print("✅ Токены получены успешно!")
            print(f"\n🔑 Access Token: {tokens['access_token'][:30]}...")
            print(f"🔄 Refresh Token: {tokens['refresh_token'][:30]}...")
            print(f"⏰ Expiry: {tokens['token_expiry']}")
            
            # Сохраняем токены
            save_tokens(tokens)
            
            print("\n" + "=" * 70)
            print("🎉 Готово! Теперь вы можете создавать задачи:")
            print("   python scripts/test_oauth_tasks.py --create-task")
            print("=" * 70)
            
            return 0
        except Exception as e:
            print(f"❌ Ошибка при обмене кода на токены: {e}")
            import traceback
            traceback.print_exc()
            return 1


def create_task():
    """Создает тестовую задачу в Google Tasks."""
    print("=" * 70)
    print("📝 СОЗДАНИЕ ЗАДАЧИ В GOOGLE TASKS")
    print("=" * 70)
    print()
    
    # Загружаем токены
    tokens = load_tokens()
    if not tokens:
        print("❌ Токены не найдены!")
        print("\nСначала получите токены:")
        print("   python scripts/test_oauth_tasks.py --get-tokens")
        return 1
    
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        print("❌ OAuth credentials не настроены в .env")
        return 1
    
    print(f"✅ Токены загружены из {TOKENS_FILE}")
    print()
    
    # Создаем TasksService
    print("📋 Инициализация TasksService...")
    tasks_service = TasksService(
        access_token=tokens.get("access_token"),
        refresh_token=tokens.get("refresh_token"),
        token_expiry=tokens.get("token_expiry"),
        client_id=client_id,
        client_secret=client_secret,
    )
    
    if not tasks_service.is_configured():
        print("❌ Не удалось инициализировать TasksService")
        print("   Проверьте токены и credentials")
        return 1
    
    print("✅ TasksService инициализирован")
    print()
    
    # Получаем списки задач
    print("📋 Получение списков задач...")
    tasklists = tasks_service.get_tasklists()
    
    if tasklists:
        print(f"✅ Найдено списков задач: {len(tasklists)}")
        for tasklist in tasklists:
            print(f"   - {tasklist.get('title')} (ID: {tasklist.get('id')})")
    else:
        print("⚠️  Списки задач не найдены")
    print()
    
    # Создаем задачу
    print("📝 Создание тестовой задачи...")
    
    # Срок выполнения - завтра в 12:00
    tomorrow = datetime.now(UTC) + timedelta(days=1)
    due_date = tomorrow.replace(hour=12, minute=0, second=0, microsecond=0)
    due_date_str = due_date.isoformat().replace("+00:00", "Z")
    
    task_data = {
        "title": "🤖 Тестовая задача через OAuth",
        "notes": f"Создана через test_oauth_tasks.py\n\nВремя: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n✅ OAuth 2.0 работает!",
        "due": due_date_str,
    }
    
    print(f"   Название: {task_data['title']}")
    print(f"   Срок: {tomorrow.strftime('%Y-%m-%d %H:%M UTC')}")
    print()
    
    created_task = tasks_service.create_task(**task_data)
    
    if not created_task:
        print("❌ Не удалось создать задачу")
        print("\nВозможные причины:")
        print("1. Google Tasks API не включен в проекте")
        print("2. Токены истекли")
        print("3. Нет доступа к Tasks")
        print("\nПопробуйте получить новые токены:")
        print("   python scripts/test_oauth_tasks.py --get-tokens")
        return 1
    
    print("✅ Задача создана успешно!")
    print(f"   ID: {created_task.get('id')}")
    print(f"   Статус: {created_task.get('status')}")
    print("   URL: https://tasks.google.com/")
    print()
    
    # Проверяем обновленные токены
    updated_tokens = tasks_service.get_updated_tokens()
    if updated_tokens["access_token"] != tokens["access_token"]:
        print("🔄 Токены были обновлены")
        save_tokens(updated_tokens)
    
    print("=" * 70)
    print("🎉 Успешно! Проверьте задачу в Google Tasks:")
    print("   https://tasks.google.com/")
    print("=" * 70)
    
    return 0


def list_tasks():
    """Показывает список задач из Google Tasks."""
    print("=" * 70)
    print("📋 СПИСОК ЗАДАЧ ИЗ GOOGLE TASKS")
    print("=" * 70)
    print()
    
    # Загружаем токены
    tokens = load_tokens()
    if not tokens:
        print("❌ Токены не найдены!")
        print("\nСначала получите токены:")
        print("   python scripts/test_oauth_tasks.py --get-tokens")
        return 1
    
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        print("❌ OAuth credentials не настроены в .env")
        return 1
    
    # Создаем TasksService
    tasks_service = TasksService(
        access_token=tokens.get("access_token"),
        refresh_token=tokens.get("refresh_token"),
        token_expiry=tokens.get("token_expiry"),
        client_id=client_id,
        client_secret=client_secret,
    )
    
    if not tasks_service.is_configured():
        print("❌ Не удалось инициализировать TasksService")
        return 1
    
    # Получаем задачи
    tasks = tasks_service.list_tasks(max_results=10, show_completed=True)
    
    if not tasks:
        print("📭 Задачи не найдены")
        print("\nСоздайте задачу:")
        print("   python scripts/test_oauth_tasks.py --create-task")
        return 0
    
    print(f"✅ Найдено задач: {len(tasks)}\n")
    
    for i, task in enumerate(tasks, 1):
        title = task.get("title", "Без названия")
        status = task.get("status", "unknown")
        status_emoji = "✅" if status == "completed" else "⭕"
        
        due = task.get("due")
        due_str = ""
        if due:
            try:
                due_dt = datetime.fromisoformat(due.replace("Z", "+00:00"))
                due_str = f" (до {due_dt.strftime('%Y-%m-%d %H:%M')})"
            except Exception:
                pass
        
        print(f"{i}. {status_emoji} {title}{due_str}")
        
        notes = task.get("notes")
        if notes:
            # Показываем первую строку описания
            first_line = notes.split("\n")[0]
            if len(first_line) > 60:
                first_line = first_line[:60] + "..."
            print(f"   📝 {first_line}")
    
    print()
    print("=" * 70)
    print(f"Всего задач: {len(tasks)}")
    print("=" * 70)
    
    return 0


def main():
    """Основная функция."""
    parser = argparse.ArgumentParser(
        description="Тестовый скрипт для работы с Google Tasks через OAuth 2.0"
    )
    parser.add_argument(
        "--get-tokens",
        action="store_true",
        help="Получить OAuth токены через браузер"
    )
    parser.add_argument(
        "--create-task",
        action="store_true",
        help="Создать тестовую задачу"
    )
    parser.add_argument(
        "--list-tasks",
        action="store_true",
        help="Показать список задач"
    )
    
    args = parser.parse_args()
    
    if args.get_tokens:
        return get_tokens()
    if args.create_task:
        return create_task()
    if args.list_tasks:
        return list_tasks()
    parser.print_help()
    print("\n" + "=" * 70)
    print("💡 БЫСТРЫЙ СТАРТ")
    print("=" * 70)
    print("\n1. Получите OAuth токены:")
    print("   python scripts/test_oauth_tasks.py --get-tokens")
    print("\n2. Создайте задачу:")
    print("   python scripts/test_oauth_tasks.py --create-task")
    print("\n3. Просмотрите список задач:")
    print("   python scripts/test_oauth_tasks.py --list-tasks")
    print("\n" + "=" * 70)
    return 0


if __name__ == "__main__":
    exit(main())

