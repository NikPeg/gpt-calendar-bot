#!/usr/bin/env python3
"""
Скрипт для тестирования работы с Google Tasks API.

Использование:
    python scripts/test_tasks.py [service_account.json] [user_id]
    
Аргументы:
    service_account.json - путь к файлу с данными сервисного аккаунта (необязательно)
    user_id - ID пользователя из БД (необязательно, если указан service_account.json)
    
Примеры:
    python scripts/test_tasks.py my_service_account.json
    python scripts/test_tasks.py - 123456789  # взять из БД для пользователя 123456789
"""

import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Добавляем родительскую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from services.tasks_service import TasksService

# Загружаем переменные окружения
load_dotenv()

# Устанавливаем путь к логам для локального запуска
os.environ.setdefault("LOG_FILE_PATH", "logs/debug.log")


def main():
    """Основная функция тестирования."""
    print("🔧 Тестирование Google Tasks API\n")

    # Определяем путь к файлу с credentials
    script_dir = Path(__file__).parent
    creds_file = script_dir / "creds.json"
    
    # Читаем данные сервисного аккаунта
    if not creds_file.exists():
        print(f"❌ Ошибка: файл {creds_file} не найден")
        print("   Создайте файл scripts/creds.json с данными сервисного аккаунта")
        return 1
    
    try:
        with open(creds_file, encoding="utf-8") as f:
            service_account_json = f.read()
        print(f"✅ Данные сервисного аккаунта загружены из {creds_file.name}\n")
    except Exception as e:
        print(f"❌ Ошибка при чтении файла: {e}")
        return 1

    # Создаем сервис
    tasks_service = TasksService(service_account_json)

    if not tasks_service.is_configured():
        print("❌ Ошибка: не удалось инициализировать Tasks Service")
        return 1

    print("✅ Tasks Service инициализирован успешно\n")

    # Тест 1: Получение списков задач
    print("📋 Тест 1: Получение списков задач")
    tasklists = tasks_service.get_tasklists()
    
    if not tasklists:
        print("⚠️  Списки задач не найдены")
        print("   Это нормально для сервисного аккаунта - у него нет личных задач")
        print("   Задачи будут создаваться в календаре пользователя, к которому есть доступ\n")
    else:
        print(f"✅ Найдено списков задач: {len(tasklists)}")
        for tasklist in tasklists:
            print(f"   - {tasklist.get('title')} (ID: {tasklist.get('id')})")
        print()

    # Тест 2: Создание задачи
    print("📝 Тест 2: Создание тестовой задачи")
    
    # Срок выполнения - завтра в полдень
    tomorrow = datetime.now(UTC) + timedelta(days=1)
    due_date = tomorrow.replace(hour=12, minute=0, second=0, microsecond=0)
    due_date_str = due_date.isoformat().replace("+00:00", "Z")
    
    task_data = {
        "title": "🤖 Тестовая задача из бота",
        "notes": f"Эта задача создана автоматически для проверки интеграции с Google Tasks API.\n\nСоздана: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "due": due_date_str,
    }
    
    print(f"   Название: {task_data['title']}")
    print(f"   Срок: {tomorrow.strftime('%Y-%m-%d %H:%M UTC')}")
    
    created_task = tasks_service.create_task(**task_data)
    
    if not created_task:
        print("❌ Не удалось создать задачу")
        print("\n" + "=" * 70)
        print("📖 ИНСТРУКЦИЯ: Как включить Google Tasks API")
        print("=" * 70)
        print("\n1. Откройте Google Cloud Console:")
        
        # Пытаемся получить project_id из credentials
        try:
            creds_data = json.loads(service_account_json)
            project_id = creds_data.get("project_id", "YOUR_PROJECT_ID")
            print(f"   https://console.cloud.google.com/apis/library/tasks.googleapis.com?project={project_id}")
        except Exception:
            print("   https://console.cloud.google.com/apis/library/tasks.googleapis.com")
        
        print("\n2. Убедитесь, что выбран правильный проект (scribo-410009)")
        print("\n3. Нажмите кнопку 'ENABLE' (Включить)")
        print("\n4. Подождите несколько минут и запустите скрипт снова")
        print("\n" + "=" * 70)
        return 1
    
    print("✅ Задача создана успешно!")
    print(f"   ID: {created_task.get('id')}")
    print(f"   Статус: {created_task.get('status')}")
    print()
    
    task_id = created_task.get("id")
    
    # Тест 3: Получение списка задач
    print("📖 Тест 3: Получение списка задач")
    tasks = tasks_service.list_tasks(max_results=5)
    
    if tasks:
        print(f"✅ Найдено задач: {len(tasks)}")
        for i, task in enumerate(tasks, 1):
            title = task.get("title", "Без названия")
            status = task.get("status", "unknown")
            status_emoji = "✓" if status == "completed" else "○"
            print(f"   {i}. {status_emoji} {title}")
    else:
        print("⚠️  Задачи не найдены")
    print()
    
    # Тест 4: Обновление задачи
    print("✏️  Тест 4: Обновление задачи")
    updated_task = tasks_service.update_task(
        task_id=task_id,
        notes=f"{task_data['notes']}\n\n✏️ Обновлено: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}",
    )
    
    if updated_task:
        print("✅ Задача обновлена успешно")
    else:
        print("❌ Не удалось обновить задачу")
    print()
    
    # # Тест 5: Пометка задачи как выполненной
    # print("✅ Тест 5: Пометка задачи как выполненной")
    # completed_task = tasks_service.complete_task(task_id=task_id)
    
    # if completed_task:
    #     print(f"✅ Задача помечена как выполненная")
    #     print(f"   Статус: {completed_task.get('status')}")
    # else:
    #     print("❌ Не удалось пометить задачу как выполненную")
    # print()
    
    # # Тест 6: Удаление задачи
    # print("🗑️  Тест 6: Удаление задачи")
    # deleted = tasks_service.delete_task(task_id=task_id)
    
    # if deleted:
    #     print("✅ Задача удалена успешно")
    # else:
    #     print("❌ Не удалось удалить задачу")
    # print()
    
    print("=" * 50)
    print("🎉 Все тесты завершены!")
    print("=" * 50)
    
    return 0


if __name__ == "__main__":
    exit(main())

