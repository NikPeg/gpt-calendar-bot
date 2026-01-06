"""
Сервис для работы с Google Tasks API.
"""

from datetime import UTC, datetime
from typing import Any

from googleapiclient.errors import HttpError

from core.config import logger
from services.google_service_base import GoogleServiceBase
from services.google_service_oauth import GoogleServiceOAuth


class TasksService(GoogleServiceBase):
    """Сервис для работы с Google Tasks через OAuth 2.0."""

    # Scope для Tasks API
    SCOPES = [
        "https://www.googleapis.com/auth/tasks",
    ]

    def __init__(
        self,
        access_token: str | None = None,
        refresh_token: str | None = None,
        token_expiry: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
    ):
        """
        Инициализирует сервис задач через OAuth 2.0.

        Args:
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            token_expiry: Время истечения токена
            client_id: OAuth Client ID
            client_secret: OAuth Client Secret
        """
        super().__init__(service_name="tasks", version="v1", scopes=self.SCOPES)

        # Создаем OAuth сервис
        self._oauth_service = GoogleServiceOAuth(
            service_name="tasks",
            version="v1",
            scopes=self.SCOPES,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expiry=token_expiry,
            client_id=client_id,
            client_secret=client_secret,
        )

        self.service = self._oauth_service.service

    def _build_service(self):
        """OAuth service создается в __init__."""
        return self.service

    def get_updated_tokens(self) -> dict[str, str | None]:
        """
        Получает обновленные OAuth токены.

        Returns:
            dict с access_token, refresh_token, token_expiry
        """
        return self._oauth_service.get_updated_tokens()

    def get_tasklists(self) -> list[dict[str, Any]]:
        """
        Получает список всех списков задач.

        Returns:
            Список списков задач
        """
        if not self.service:
            return []

        try:
            results = self.service.tasklists().list().execute()
            return results.get("items", [])
        except HttpError as e:
            logger.error(f"Error getting task lists: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting task lists: {e}")
            return []

    def get_default_tasklist_id(self) -> str | None:
        """
        Получает ID списка задач по умолчанию.

        Returns:
            ID списка задач или None при ошибке
        """
        if not self.service:
            return None

        try:
            # Получаем список всех списков задач
            tasklists = self.get_tasklists()

            if not tasklists:
                logger.warning("No task lists found")
                return None

            # Ищем список с title "My Tasks" или используем первый доступный
            for tasklist in tasklists:
                if tasklist.get("title") == "My Tasks":
                    return tasklist["id"]

            # Возвращаем первый доступный
            return tasklists[0]["id"]
        except Exception as e:
            logger.error(f"Error getting default task list ID: {e}")
            return None

    def create_task(
        self,
        title: str,
        notes: str | None = None,
        due: str | None = None,
        tasklist_id: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Создает задачу в указанном списке задач.

        Args:
            title: Название задачи
            notes: Описание задачи
            due: Срок выполнения в формате RFC3339 (YYYY-MM-DDTHH:MM:SSZ)
            tasklist_id: ID списка задач (если None, используется список по умолчанию)

        Returns:
            Созданная задача или None при ошибке
        """
        if not self.service:
            logger.error("GOOGLE_API: Tasks service not initialized")
            return None

        try:
            # Получаем ID списка задач
            if not tasklist_id:
                tasklist_id = self.get_default_tasklist_id()
                if not tasklist_id:
                    logger.error("GOOGLE_API: Could not get default tasklist_id")
                    return None

            # Формируем задачу
            task = {"title": title}

            if notes:
                task["notes"] = notes

            if due:
                # Убеждаемся, что дата в формате RFC3339
                task["due"] = self._ensure_rfc3339_format(due)

            # Логируем вызов API
            logger.info(
                f"GOOGLE_API: Creating task in tasklist '{tasklist_id}': "
                f"title='{title}', due={due}"
            )

            # Создаем задачу
            created_task = (
                self.service.tasks().insert(tasklist=tasklist_id, body=task).execute()
            )

            task_id = created_task.get("id", "")
            logger.info(f"GOOGLE_API: ✅ Task created successfully: id={task_id}")
            return created_task
        except HttpError as e:
            logger.error(f"GOOGLE_API: ❌ HTTP Error creating task: {e}")
            return None
        except Exception as e:
            logger.error(f"GOOGLE_API: ❌ Unexpected error creating task: {e}")
            return None

    def list_tasks(
        self,
        tasklist_id: str | None = None,
        max_results: int = 10,
        show_completed: bool = False,
        show_hidden: bool = False,
        due_min: str | None = None,
        due_max: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Получает список задач из указанного списка.

        Args:
            tasklist_id: ID списка задач (если None, используется список по умолчанию)
            max_results: Максимальное количество задач
            show_completed: Показывать ли выполненные задачи
            show_hidden: Показывать ли скрытые задачи
            due_min: Минимальная дата дедлайна для фильтрации (RFC3339)
            due_max: Максимальная дата дедлайна для фильтрации (RFC3339)

        Returns:
            Список задач
        """
        if not self.service:
            logger.error("GOOGLE_API: Tasks service not initialized")
            return []

        try:
            # Получаем ID списка задач
            if not tasklist_id:
                tasklist_id = self.get_default_tasklist_id()
                if not tasklist_id:
                    logger.error("GOOGLE_API: Could not get default tasklist_id")
                    return []

            # Параметры запроса
            params = {
                "tasklist": tasklist_id,
                "maxResults": max_results,
            }

            if show_completed:
                params["showCompleted"] = True

            if show_hidden:
                params["showHidden"] = True

            # Логируем вызов API
            logger.info(
                f"GOOGLE_API: Listing tasks from tasklist '{tasklist_id}': "
                f"max_results={max_results}, show_completed={show_completed}, "
                f"due_min={due_min}, due_max={due_max}"
            )

            # Получаем задачи
            results = self.service.tasks().list(**params).execute()
            tasks = results.get("items", [])

            # Фильтруем по дате дедлайна, если указаны параметры
            if due_min or due_max:
                filtered_tasks = []

                def parse_datetime(dt_str: str) -> datetime:
                    """
                    Парсит дату в формате ISO 8601/RFC3339 и возвращает offset-aware datetime в UTC.
                    """
                    # Убираем Z и заменяем на +00:00 для корректного парсинга
                    if dt_str.endswith("Z"):
                        dt_str = dt_str.replace("Z", "+00:00")

                    # Парсим дату
                    dt = datetime.fromisoformat(dt_str)

                    # Если дата без timezone, считаем её UTC
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=UTC)

                    # Приводим к UTC для консистентности
                    return dt.astimezone(UTC)

                for task in tasks:
                    task_due = task.get("due")
                    if not task_due:
                        # Если у задачи нет дедлайна, пропускаем её при фильтрации
                        continue

                    # Парсим дату дедлайна задачи
                    try:
                        task_due_dt = parse_datetime(task_due)

                        # Проверяем фильтры
                        if due_min:
                            min_dt = parse_datetime(due_min)
                            if task_due_dt < min_dt:
                                continue

                        if due_max:
                            max_dt = parse_datetime(due_max)
                            if task_due_dt > max_dt:
                                continue

                        filtered_tasks.append(task)
                    except (ValueError, AttributeError) as e:
                        logger.warning(
                            f"GOOGLE_API: Could not parse task due date '{task_due}': {e}"
                        )
                        continue

                tasks = filtered_tasks

            logger.info(f"GOOGLE_API: ✅ Found {len(tasks)} tasks")
            return tasks
        except HttpError as e:
            logger.error(f"GOOGLE_API: ❌ HTTP Error listing tasks: {e}")
            return []
        except Exception as e:
            logger.error(f"GOOGLE_API: ❌ Unexpected error listing tasks: {e}")
            return []

    def get_task(
        self, task_id: str, tasklist_id: str | None = None
    ) -> dict[str, Any] | None:
        """
        Получает задачу по ID.

        Args:
            task_id: ID задачи
            tasklist_id: ID списка задач (если None, используется список по умолчанию)

        Returns:
            Задача или None при ошибке
        """
        if not self.service:
            return None

        try:
            # Получаем ID списка задач
            if not tasklist_id:
                tasklist_id = self.get_default_tasklist_id()
                if not tasklist_id:
                    return None

            return (
                self.service.tasks().get(tasklist=tasklist_id, task=task_id).execute()
            )
        except HttpError as e:
            logger.error(f"Error getting task: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting task: {e}")
            return None

    def update_task(
        self,
        task_id: str,
        title: str | None = None,
        notes: str | None = None,
        due: str | None = None,
        status: str | None = None,
        tasklist_id: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Обновляет задачу.

        Args:
            task_id: ID задачи
            title: Новое название задачи
            notes: Новое описание задачи
            due: Новый срок выполнения
            status: Новый статус ('needsAction' или 'completed')
            tasklist_id: ID списка задач (если None, используется список по умолчанию)

        Returns:
            Обновленная задача или None при ошибке
        """
        if not self.service:
            logger.error("GOOGLE_API: Tasks service not initialized")
            return None

        try:
            # Получаем ID списка задач
            if not tasklist_id:
                tasklist_id = self.get_default_tasklist_id()
                if not tasklist_id:
                    logger.error("GOOGLE_API: Could not get default tasklist_id")
                    return None

            # Получаем существующую задачу
            task = self.get_task(task_id, tasklist_id)
            if not task:
                logger.error(f"GOOGLE_API: Task {task_id} not found")
                return None

            # Обновляем поля
            if title is not None:
                task["title"] = title
            if notes is not None:
                task["notes"] = notes
            if due is not None:
                task["due"] = self._ensure_rfc3339_format(due)
            if status is not None:
                task["status"] = status

            # Логируем вызов API
            logger.info(
                f"GOOGLE_API: Updating task {task_id} in tasklist '{tasklist_id}': "
                f"title={title}, status={status}, due={due}"
            )

            # Обновляем задачу
            updated_task = (
                self.service.tasks()
                .update(tasklist=tasklist_id, task=task_id, body=task)
                .execute()
            )

            logger.info(f"GOOGLE_API: ✅ Task updated successfully: id={task_id}")
            return updated_task
        except HttpError as e:
            logger.error(f"GOOGLE_API: ❌ HTTP Error updating task {task_id}: {e}")
            return None
        except Exception as e:
            logger.error(
                f"GOOGLE_API: ❌ Unexpected error updating task {task_id}: {e}"
            )
            return None

    def delete_task(self, task_id: str, tasklist_id: str | None = None) -> bool:
        """
        Удаляет задачу.

        Args:
            task_id: ID задачи
            tasklist_id: ID списка задач (если None, используется список по умолчанию)

        Returns:
            True если успешно, False при ошибке
        """
        if not self.service:
            logger.error("GOOGLE_API: Tasks service not initialized")
            return False

        try:
            # Получаем ID списка задач
            if not tasklist_id:
                tasklist_id = self.get_default_tasklist_id()
                if not tasklist_id:
                    logger.error("GOOGLE_API: Could not get default tasklist_id")
                    return False

            # Логируем вызов API
            logger.info(
                f"GOOGLE_API: Deleting task {task_id} from tasklist '{tasklist_id}'"
            )

            self.service.tasks().delete(tasklist=tasklist_id, task=task_id).execute()

            logger.info(f"GOOGLE_API: ✅ Task deleted successfully: id={task_id}")
            return True
        except HttpError as e:
            logger.error(f"GOOGLE_API: ❌ HTTP Error deleting task {task_id}: {e}")
            return False
        except Exception as e:
            logger.error(
                f"GOOGLE_API: ❌ Unexpected error deleting task {task_id}: {e}"
            )
            return False

    def complete_task(
        self, task_id: str, tasklist_id: str | None = None
    ) -> dict[str, Any] | None:
        """
        Помечает задачу как выполненную.

        Args:
            task_id: ID задачи
            tasklist_id: ID списка задач (если None, используется список по умолчанию)

        Returns:
            Обновленная задача или None при ошибке
        """
        return self.update_task(
            task_id=task_id,
            status="completed",
            tasklist_id=tasklist_id,
        )
