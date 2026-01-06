"""
Функции для работы с Google Tasks через Function Calling.
Реализация на основе паттерна Command для чистой архитектуры.
"""

import json
from abc import ABC, abstractmethod
from typing import Any

from core.config import GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, logger
from core.database import Conversation
from services.tasks_service import TasksService

# Определения функций для LLM
TASKS_FUNCTIONS = [
    {
        "name": "create_task",
        "description": "Создает новую задачу в Google Tasks пользователя",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Название задачи (обязательно)",
                },
                "notes": {
                    "type": "string",
                    "description": "Описание задачи (опционально)",
                },
                "due": {
                    "type": "string",
                    "description": "Срок выполнения задачи в формате ISO 8601 (YYYY-MM-DDTHH:MM:SSZ) (опционально)",
                },
            },
            "required": ["title"],
        },
    },
    {
        "name": "list_tasks",
        "description": "Получает список задач пользователя из Google Tasks",
        "parameters": {
            "type": "object",
            "properties": {
                "max_results": {
                    "type": "integer",
                    "description": "Максимальное количество задач для отображения (по умолчанию 10)",
                },
                "show_completed": {
                    "type": "boolean",
                    "description": "Показывать ли выполненные задачи (по умолчанию False)",
                },
                "due_min": {
                    "type": "string",
                    "description": "Минимальная дата дедлайна для фильтрации задач в формате ISO 8601 (YYYY-MM-DDTHH:MM:SSZ) (опционально). Используй для фильтрации задач на сегодня или в определенном диапазоне дат",
                },
                "due_max": {
                    "type": "string",
                    "description": "Максимальная дата дедлайна для фильтрации задач в формате ISO 8601 (YYYY-MM-DDTHH:MM:SSZ) (опционально). Используй для фильтрации задач на сегодня или в определенном диапазоне дат",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_task",
        "description": "Получает информацию о конкретной задаче по её ID",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "ID задачи в Google Tasks (обязательно)",
                },
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "update_task",
        "description": "Обновляет существующую задачу",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "ID задачи для обновления (обязательно)",
                },
                "title": {
                    "type": "string",
                    "description": "Новое название задачи (опционально)",
                },
                "notes": {
                    "type": "string",
                    "description": "Новое описание задачи (опционально)",
                },
                "due": {
                    "type": "string",
                    "description": "Новый срок выполнения в формате ISO 8601 (опционально)",
                },
                "status": {
                    "type": "string",
                    "description": "Новый статус: 'needsAction' или 'completed' (опционально)",
                },
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "delete_task",
        "description": "Удаляет задачу из Google Tasks",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "ID задачи для удаления (обязательно)",
                },
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "complete_task",
        "description": "Помечает задачу как выполненную",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "ID задачи для завершения (обязательно)",
                },
            },
            "required": ["task_id"],
        },
    },
]


class TasksContext:
    """Контекст выполнения операций с задачами."""

    def __init__(
        self,
        user_id: int,
        tasks_service: TasksService,
    ):
        """
        Инициализирует контекст задач.

        Args:
            user_id: ID пользователя
            tasks_service: Сервис для работы с Google Tasks
        """
        self.user_id = user_id
        self.tasks_service = tasks_service

    @classmethod
    async def create(cls, user_id: int) -> "TasksContext | None":
        """
        Создает контекст из данных пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            TasksContext или None, если не удалось создать
        """
        # Получаем данные пользователя
        conversation = Conversation(user_id)
        await conversation.get_from_db()

        # Проверяем, настроен ли OAuth
        if not conversation.oauth_access_token:
            logger.error(f"USER{user_id}: Google Tasks not connected via OAuth")
            return None

        # Создаем сервис задач через OAuth
        tasks_service = TasksService(
            access_token=conversation.oauth_access_token,
            refresh_token=conversation.oauth_refresh_token,
            token_expiry=conversation.oauth_token_expiry,
            client_id=GOOGLE_OAUTH_CLIENT_ID,
            client_secret=GOOGLE_OAUTH_CLIENT_SECRET,
        )

        if not tasks_service.is_configured():
            logger.error(f"USER{user_id}: Tasks service not configured properly")
            return None

        # Проверяем и сохраняем обновленные токены если они изменились
        updated_tokens = tasks_service.get_updated_tokens()
        if updated_tokens["access_token"] != conversation.oauth_access_token:
            conversation.oauth_access_token = updated_tokens["access_token"]
            conversation.oauth_token_expiry = updated_tokens["token_expiry"]
            await conversation.update_in_db()
            logger.debug(f"USER{user_id}: OAuth tokens updated in database")

        return cls(user_id, tasks_service)


class TasksCommand(ABC):
    """Абстрактный базовый класс для команд работы с задачами."""

    def __init__(self, context: TasksContext, arguments: dict[str, Any]):
        self.context = context
        self.arguments = arguments

    @abstractmethod
    async def execute(self) -> str:
        """Выполняет команду и возвращает результат."""
        ...


class CreateTaskCommand(TasksCommand):
    """Команда создания задачи."""

    async def execute(self) -> str:
        title = self.arguments.get("title", "")
        if not title:
            return '{"status": "error", "message": "❌ Не указано название задачи"}'

        notes = self.arguments.get("notes")
        due = self.arguments.get("due")

        # Создаем задачу
        task = self.context.tasks_service.create_task(
            title=title,
            notes=notes,
            due=due,
        )

        if task:
            task_id = task.get("id", "")
            task_title = task.get("title", "")
            due_str = task.get("due", "")

            message = f'✅ Задача "{task_title}" создана успешно!\n\nID: {task_id}'
            if due_str:
                message += f"\nСрок: {due_str}"

            return json.dumps(
                {"status": "success", "task_id": task_id, "message": message},
                ensure_ascii=False,
            )

        return json.dumps(
            {
                "status": "error",
                "message": "❌ Не удалось создать задачу в Google Tasks",
            },
            ensure_ascii=False,
        )


class ListTasksCommand(TasksCommand):
    """Команда получения списка задач."""

    async def execute(self) -> str:
        max_results = self.arguments.get("max_results", 10)
        show_completed = self.arguments.get("show_completed", False)
        due_min = self.arguments.get("due_min")
        due_max = self.arguments.get("due_max")

        # Получаем задачи
        tasks = self.context.tasks_service.list_tasks(
            max_results=max_results,
            show_completed=show_completed,
            due_min=due_min,
            due_max=due_max,
        )

        if not tasks:
            return "📝 Задач не найдено"

        result = f"📝 Найдено задач: {len(tasks)}\n\n"
        for i, task in enumerate(tasks, 1):
            title = task.get("title", "Без названия")
            task_id = task.get("id", "")
            status = task.get("status", "")
            due = task.get("due", "")
            notes = task.get("notes", "")

            # Иконка статуса
            status_icon = "✅" if status == "completed" else "⏳"

            result += f"{i}. {status_icon} {title}\n   ID: {task_id}\n"

            if due:
                result += f"   Срок: {due}\n"
            if notes:
                # Показываем только начало описания если оно длинное
                notes_preview = notes[:50] + "..." if len(notes) > 50 else notes
                result += f"   Описание: {notes_preview}\n"

            result += "\n"

        return result.strip()


class GetTaskCommand(TasksCommand):
    """Команда получения информации о задаче."""

    async def execute(self) -> str:
        task_id = self.arguments.get("task_id")
        if not task_id:
            return "❌ Не указан ID задачи"

        # Получаем задачу
        task = self.context.tasks_service.get_task(task_id)

        if not task:
            return f"❌ Задача с ID {task_id} не найдена"

        return self._format_task_details(task, task_id)

    @staticmethod
    def _format_task_details(task: dict[str, Any], task_id: str) -> str:
        """Форматирует детали задачи для отображения."""
        title = task.get("title", "Без названия")
        notes = task.get("notes", "")
        due = task.get("due", "")
        status = task.get("status", "needsAction")
        updated = task.get("updated", "")

        status_text = "✅ Выполнена" if status == "completed" else "⏳ В работе"

        result = f"📝 {title}\n\n"
        result += f"Статус: {status_text}\n"
        if notes:
            result += f"Описание: {notes}\n"
        if due:
            result += f"Срок: {due}\n"
        if updated:
            result += f"Обновлено: {updated}\n"
        result += f"\nID: {task_id}"

        return result


class UpdateTaskCommand(TasksCommand):
    """Команда обновления задачи."""

    async def execute(self) -> str:
        task_id = self.arguments.get("task_id")
        if not task_id:
            return json.dumps(
                {"status": "error", "message": "❌ Не указан ID задачи"},
                ensure_ascii=False,
            )

        title = self.arguments.get("title")
        notes = self.arguments.get("notes")
        due = self.arguments.get("due")
        status = self.arguments.get("status")

        # Обновляем задачу
        task = self.context.tasks_service.update_task(
            task_id=task_id,
            title=title,
            notes=notes,
            due=due,
            status=status,
        )

        if task:
            return json.dumps(
                {
                    "status": "success",
                    "task_id": task_id,
                    "message": f"✅ Задача обновлена успешно!\n\nID: {task_id}",
                },
                ensure_ascii=False,
            )

        return json.dumps(
            {
                "status": "error",
                "message": f"❌ Не удалось обновить задачу с ID {task_id} в Google Tasks",
            },
            ensure_ascii=False,
        )


class DeleteTaskCommand(TasksCommand):
    """Команда удаления задачи."""

    async def execute(self) -> str:
        task_id = self.arguments.get("task_id")
        if not task_id:
            return json.dumps(
                {"status": "error", "message": "❌ Не указан ID задачи"},
                ensure_ascii=False,
            )

        # Удаляем задачу
        success = self.context.tasks_service.delete_task(task_id)

        if success:
            return json.dumps(
                {
                    "status": "success",
                    "task_id": task_id,
                    "message": f"✅ Задача удалена успешно!\n\nID: {task_id}",
                },
                ensure_ascii=False,
            )

        return json.dumps(
            {
                "status": "error",
                "message": f"❌ Не удалось удалить задачу с ID {task_id} из Google Tasks",
            },
            ensure_ascii=False,
        )


class CompleteTaskCommand(TasksCommand):
    """Команда завершения задачи."""

    async def execute(self) -> str:
        task_id = self.arguments.get("task_id")
        if not task_id:
            return json.dumps(
                {"status": "error", "message": "❌ Не указан ID задачи"},
                ensure_ascii=False,
            )

        # Помечаем задачу как выполненную
        task = self.context.tasks_service.complete_task(task_id)

        if task:
            return json.dumps(
                {
                    "status": "success",
                    "task_id": task_id,
                    "message": f"✅ Задача отмечена как выполненная!\n\nID: {task_id}",
                },
                ensure_ascii=False,
            )

        return json.dumps(
            {
                "status": "error",
                "message": f"❌ Не удалось завершить задачу с ID {task_id} в Google Tasks",
            },
            ensure_ascii=False,
        )


class TasksCommandFactory:
    """Фабрика для создания команд работы с задачами."""

    _commands: dict[str, type[TasksCommand]] = {
        "create_task": CreateTaskCommand,
        "list_tasks": ListTasksCommand,
        "get_task": GetTaskCommand,
        "update_task": UpdateTaskCommand,
        "delete_task": DeleteTaskCommand,
        "complete_task": CompleteTaskCommand,
    }

    @classmethod
    def create(
        cls, function_name: str, context: TasksContext, arguments: dict[str, Any]
    ) -> TasksCommand | None:
        """
        Создает команду по имени функции.

        Args:
            function_name: Название функции
            context: Контекст выполнения
            arguments: Аргументы команды

        Returns:
            Экземпляр команды или None, если команда не найдена
        """
        command_class = cls._commands.get(function_name)
        if command_class:
            return command_class(context, arguments)
        return None


async def execute_tasks_function(
    function_name: str, arguments: dict, user_id: int
) -> str:
    """
    Выполняет функцию работы с задачами.

    Args:
        function_name: Название функции
        arguments: Аргументы функции
        user_id: ID пользователя

    Returns:
        Результат выполнения функции в виде строки
    """
    try:
        # Создаем контекст
        context = await TasksContext.create(user_id)
        if not context:
            return "❌ Google Tasks не настроен. Пожалуйста, настройте доступ командой /start"

        # Создаем и выполняем команду
        command = TasksCommandFactory.create(function_name, context, arguments)
        if not command:
            return f"❌ Неизвестная функция: {function_name}"

        return await command.execute()

    except Exception as e:
        logger.error(
            f"Error executing tasks function {function_name}: {e}", exc_info=True
        )
        return f"❌ Произошла ошибка при выполнении операции: {str(e)}"
