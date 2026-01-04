"""
Сервис для работы с Google Calendar API.
"""

import json
from datetime import UTC, datetime
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from core.config import logger


class CalendarService:
    """Сервис для работы с Google Calendar через сервисный аккаунт."""

    def __init__(self, service_account_json: str | None):
        """
        Инициализирует сервис календаря.

        Args:
            service_account_json: JSON строка с данными сервисного аккаунта
        """
        self.service_account_json = service_account_json
        self.service = None
        self._initialize_service()

    def _initialize_service(self):
        """Инициализирует Google Calendar API сервис."""
        if not self.service_account_json:
            self.service = None
            return

        try:
            # Парсим JSON
            credentials_info = json.loads(self.service_account_json)

            # Создаем credentials из сервисного аккаунта
            credentials = service_account.Credentials.from_service_account_info(
                credentials_info,
                scopes=["https://www.googleapis.com/auth/calendar"],
            )

            # Создаем сервис
            self.service = build("calendar", "v3", credentials=credentials)
            logger.debug("Google Calendar service initialized successfully")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in service_account_json: {e}")
            self.service = None
        except Exception as e:
            logger.error(f"Error initializing Google Calendar service: {e}")
            self.service = None

    def is_configured(self) -> bool:
        """Проверяет, настроен ли сервисный аккаунт."""
        return self.service is not None

    def get_calendar_id(self, user_email: str) -> str | None:
        """
        Получает ID календаря пользователя.

        Args:
            user_email: Email пользователя, календарь которого нужно использовать

        Returns:
            ID календаря или None при ошибке
        """
        if not self.service:
            return None

        try:
            # Используем календарь пользователя через делегирование
            # Для этого нужно, чтобы сервисный аккаунт имел доступ к календарю пользователя
            calendar_list = self.service.calendarList().list().execute()
            
            # Ищем основной календарь пользователя
            for calendar in calendar_list.get("items", []):
                if calendar.get("primary", False):
                    return calendar["id"]
            
            # Если не нашли primary, возвращаем первый доступный
            if calendar_list.get("items"):
                return calendar_list["items"][0]["id"]
            
            # Если календарей нет, создаем новый
            return self._create_primary_calendar(user_email)
        except HttpError as e:
            logger.error(f"Error getting calendar ID: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting calendar ID: {e}")
            return None

    def _create_primary_calendar(self, user_email: str) -> str | None:
        """Создает основной календарь для пользователя."""
        if not self.service:
            return None

        try:
            calendar = {"summary": "Telegram Bot Calendar", "timeZone": "UTC"}
            created_calendar = (
                self.service.calendars().insert(body=calendar).execute()
            )
            return created_calendar["id"]
        except Exception as e:
            logger.error(f"Error creating calendar: {e}")
            return None

    def create_event(
        self,
        user_email: str,
        summary: str,
        description: str | None = None,
        start_datetime: str | None = None,
        end_datetime: str | None = None,
        location: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Создает событие в календаре.

        Args:
            user_email: Email пользователя
            summary: Название события
            description: Описание события
            start_datetime: Дата и время начала в формате ISO 8601 (YYYY-MM-DDTHH:MM:SS)
            end_datetime: Дата и время окончания в формате ISO 8601
            location: Место проведения

        Returns:
            Созданное событие или None при ошибке
        """
        if not self.service:
            return None

        try:
            calendar_id = self.get_calendar_id(user_email)
            if not calendar_id:
                return None

            # Формируем событие
            event = {
                "summary": summary,
            }

            if description:
                event["description"] = description

            if location:
                event["location"] = location

            # Обрабатываем даты
            if start_datetime and end_datetime:
                event["start"] = {"dateTime": start_datetime, "timeZone": "UTC"}
                event["end"] = {"dateTime": end_datetime, "timeZone": "UTC"}
            elif start_datetime:
                # Если указано только время начала, добавляем 1 час
                event["start"] = {"dateTime": start_datetime, "timeZone": "UTC"}
                # Парсим дату и добавляем час
                dt = datetime.fromisoformat(start_datetime.replace("Z", "+00:00"))
                end_dt = dt.replace(hour=dt.hour + 1)
                event["end"] = {
                    "dateTime": end_dt.isoformat(),
                    "timeZone": "UTC",
                }

            # Создаем событие
            created_event = (
                self.service.events()
                .insert(calendarId=calendar_id, body=event)
                .execute()
            )

            logger.info(f"Event created: {created_event.get('id')}")
            return created_event
        except HttpError as e:
            logger.error(f"Error creating event: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating event: {e}")
            return None

    def list_events(
        self,
        user_email: str,
        max_results: int = 10,
        time_min: str | None = None,
        time_max: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Получает список событий из календаря.

        Args:
            user_email: Email пользователя
            max_results: Максимальное количество событий
            time_min: Минимальное время в формате ISO 8601
            time_max: Максимальное время в формате ISO 8601

        Returns:
            Список событий
        """
        if not self.service:
            return []

        try:
            calendar_id = self.get_calendar_id(user_email)
            if not calendar_id:
                return []

            # Параметры запроса
            params = {
                "calendarId": calendar_id,
                "maxResults": max_results,
                "singleEvents": True,
                "orderBy": "startTime",
            }

            if time_min:
                params["timeMin"] = time_min
            else:
                # По умолчанию показываем события с текущего момента
                now = datetime.now(UTC).isoformat()
                params["timeMin"] = now

            if time_max:
                params["timeMax"] = time_max

            # Получаем события
            events_result = (
                self.service.events().list(**params).execute()
            )
            return events_result.get("items", [])
        except HttpError as e:
            logger.error(f"Error listing events: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing events: {e}")
            return []

    def get_event(
        self, user_email: str, event_id: str
    ) -> dict[str, Any] | None:
        """
        Получает событие по ID.

        Args:
            user_email: Email пользователя
            event_id: ID события

        Returns:
            Событие или None при ошибке
        """
        if not self.service:
            return None

        try:
            calendar_id = self.get_calendar_id(user_email)
            if not calendar_id:
                return None

            return (
                self.service.events()
                .get(calendarId=calendar_id, eventId=event_id)
                .execute()
            )
        except HttpError as e:
            logger.error(f"Error getting event: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting event: {e}")
            return None

    def update_event(
        self,
        user_email: str,
        event_id: str,
        summary: str | None = None,
        description: str | None = None,
        start_datetime: str | None = None,
        end_datetime: str | None = None,
        location: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Обновляет событие в календаре.

        Args:
            user_email: Email пользователя
            event_id: ID события
            summary: Новое название события
            description: Новое описание события
            start_datetime: Новое время начала
            end_datetime: Новое время окончания
            location: Новое место проведения

        Returns:
            Обновленное событие или None при ошибке
        """
        if not self.service:
            return None

        try:
            calendar_id = self.get_calendar_id(user_email)
            if not calendar_id:
                return None

            # Получаем существующее событие
            event = self.get_event(user_email, event_id)
            if not event:
                return None

            # Обновляем поля
            if summary is not None:
                event["summary"] = summary
            if description is not None:
                event["description"] = description
            if location is not None:
                event["location"] = location
            if start_datetime:
                event["start"] = {"dateTime": start_datetime, "timeZone": "UTC"}
            if end_datetime:
                event["end"] = {"dateTime": end_datetime, "timeZone": "UTC"}

            # Обновляем событие
            updated_event = (
                self.service.events()
                .update(calendarId=calendar_id, eventId=event_id, body=event)
                .execute()
            )

            logger.info(f"Event updated: {event_id}")
            return updated_event
        except HttpError as e:
            logger.error(f"Error updating event: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error updating event: {e}")
            return None

    def delete_event(
        self, user_email: str, event_id: str
    ) -> bool:
        """
        Удаляет событие из календаря.

        Args:
            user_email: Email пользователя
            event_id: ID события

        Returns:
            True если успешно, False при ошибке
        """
        if not self.service:
            return False

        try:
            calendar_id = self.get_calendar_id(user_email)
            if not calendar_id:
                return False

            self.service.events().delete(
                calendarId=calendar_id, eventId=event_id
            ).execute()

            logger.info(f"Event deleted: {event_id}")
            return True
        except HttpError as e:
            logger.error(f"Error deleting event: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting event: {e}")
            return False

