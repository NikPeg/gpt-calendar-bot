# Интеграция с Google Tasks

## Обзор

Бот теперь поддерживает работу с Google Tasks API в дополнение к Google Calendar API. Это позволяет пользователям создавать и управлять задачами прямо из Telegram.

## Архитектура

### Базовый класс GoogleService

Создан базовый класс `GoogleService`, который содержит общую логику для работы с Google APIs:

```python
services/google_service.py
```

**Возможности:**
- Инициализация credentials из JSON сервисного аккаунта
- Создание Google API клиента
- Поддержка различных scopes
- Форматирование дат в RFC3339

### CalendarService

Рефакторен для наследования от `GoogleService`:

```python
services/calendar_service.py
```

**Изменения:**
- Теперь наследуется от `GoogleService`
- Автоматически включает scopes для Calendar и Tasks
- Сохранена вся существующая функциональность

### TasksService

Новый сервис для работы с Google Tasks:

```python
services/tasks_service.py
```

**Методы:**
- `get_tasklists()` - получить все списки задач
- `get_default_tasklist_id()` - получить ID списка по умолчанию
- `create_task()` - создать задачу
- `list_tasks()` - получить список задач
- `get_task()` - получить задачу по ID
- `update_task()` - обновить задачу
- `delete_task()` - удалить задачу
- `complete_task()` - пометить задачу как выполненную

## Настройка

### 1. Включение Google Tasks API

Google Tasks API должен быть включен в вашем Google Cloud проекте:

1. Откройте [Google Cloud Console](https://console.cloud.google.com/)
2. Выберите ваш проект (например, `scribo-410009`)
3. Перейдите в [APIs & Services > Library](https://console.cloud.google.com/apis/library)
4. Найдите "Google Tasks API"
5. Нажмите "ENABLE"

Или используйте прямую ссылку:
```
https://console.cloud.google.com/apis/library/tasks.googleapis.com?project=YOUR_PROJECT_ID
```

### 2. Обновление scopes

Сервисный аккаунт теперь запрашивает следующие scopes:
- `https://www.googleapis.com/auth/calendar` - для работы с календарем
- `https://www.googleapis.com/auth/tasks` - для работы с задачами

## Использование

### Создание задачи

```python
from services.tasks_service import TasksService

# Инициализация сервиса
tasks_service = TasksService(service_account_json)

# Создание задачи
task = tasks_service.create_task(
    title="Купить молоко",
    notes="Не забыть взять обезжиренное",
    due="2026-01-10T12:00:00Z"
)
```

### Получение списка задач

```python
# Получить активные задачи
tasks = tasks_service.list_tasks(max_results=10)

for task in tasks:
    print(f"{task['title']} - {task.get('status', 'unknown')}")
```

### Обновление задачи

```python
# Обновить задачу
updated_task = tasks_service.update_task(
    task_id="task_id_here",
    title="Новое название",
    status="completed"
)
```

### Удаление задачи

```python
# Удалить задачу
success = tasks_service.delete_task(task_id="task_id_here")
```

## Тестирование

Для тестирования интеграции используйте скрипт:

```bash
python scripts/test_tasks.py
```

Скрипт выполнит следующие операции:
1. Инициализация Tasks Service
2. Получение списков задач
3. Создание тестовой задачи
4. Получение списка задач
5. Обновление задачи
6. Пометка задачи как выполненной
7. Удаление задачи

## Важные замечания

### Ограничения Service Account

**Service Account и персональные задачи:**
- Google Tasks тесно связан с личным аккаунтом пользователя
- Service Account имеет свои собственные задачи, отдельные от пользователей
- Для доступа к задачам конкретного пользователя потребуется:
  - OAuth 2.0 flow вместо service account, ИЛИ
  - Domain-wide delegation (для Google Workspace)

### Альтернативные подходы

**Вариант 1: OAuth 2.0 Flow**
- Пользователи авторизуются через свой Google аккаунт
- Бот получает токен доступа к их задачам
- Требует web-интерфейс для авторизации

**Вариант 2: Domain-wide Delegation**
- Только для Google Workspace
- Service Account получает права действовать от имени пользователей домена
- Требует административных прав в Google Workspace

**Вариант 3: Использование Calendar Events как задач**
- Создавать события в календаре с особыми метками
- Не требует дополнительных API
- События видны в календаре пользователя

## Различия между Calendar Events и Tasks

| Аспект | Calendar Events | Google Tasks |
|--------|----------------|--------------|
| Время | Начало и конец события | Только deadline |
| Статус | - | needsAction / completed |
| Расшаривание | Можно делиться календарем | Личные, нельзя шарить |
| Повторения | Поддерживается | Не поддерживается |
| Подзадачи | - | Поддерживается |
| Заметки | Description | Notes |

## Следующие шаги

Для интеграции в бота:

1. **Определить подход:**
   - Service Account (текущий) - задачи будут в аккаунте бота
   - OAuth 2.0 - задачи в аккаунте пользователя

2. **Добавить функции в LLM:**
   - `create_task` - создать задачу
   - `list_tasks` - показать задачи
   - `complete_task` - выполнить задачу
   - `delete_task` - удалить задачу

3. **Обновить систему промптов:**
   - Добавить информацию о работе с задачами
   - Объяснить различия между событиями и задачами

4. **Добавить команды:**
   - `/tasks` - показать активные задачи
   - `/newtask` - создать новую задачу

## API Reference

### TasksService

#### `__init__(service_account_json: str | None)`
Инициализирует сервис с данными сервисного аккаунта.

#### `create_task(title, notes=None, due=None, tasklist_id=None) -> dict | None`
Создает новую задачу.

**Параметры:**
- `title` (str): Название задачи
- `notes` (str, optional): Описание задачи
- `due` (str, optional): Срок в формате RFC3339
- `tasklist_id` (str, optional): ID списка задач

**Возвращает:** Созданная задача или None при ошибке

#### `list_tasks(tasklist_id=None, max_results=10, show_completed=False) -> list`
Получает список задач.

#### `update_task(task_id, title=None, notes=None, due=None, status=None) -> dict | None`
Обновляет задачу.

#### `delete_task(task_id, tasklist_id=None) -> bool`
Удаляет задачу.

#### `complete_task(task_id, tasklist_id=None) -> dict | None`
Помечает задачу как выполненную.

## Troubleshooting

### Tasks API не включен
```
Error: Google Tasks API has not been used in project...
```
**Решение:** Включите Tasks API в Google Cloud Console

### 403 Forbidden
```
Error: Insufficient Permission
```
**Решение:** Проверьте scopes в credentials

### Задачи не найдены
```
No task lists found
```
**Решение:** Это нормально для нового service account. Создайте первую задачу, и список появится автоматически.

## Лицензия

Этот код является частью проекта gpt-calendar-bot.

