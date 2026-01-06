"""
Сервис для работы с Google Calendar API.
"""

import json
from datetime import UTC, datetime
from typing import Any

from googleapiclient.errors import HttpError

from core.config import logger
from services.google_service_base import GoogleServiceBase
from services.google_service_oauth import GoogleServiceOAuth


class CalendarService(GoogleServiceBase):
    """Сервис для работы с Google Calendar через OAuth 2.0."""

    # Scope для Calendar API (Tasks scope добавлен для совместимости)
    SCOPES = [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/tasks",
    ]

    @staticmethod
    def _is_insufficient_permissions_error(e: HttpError) -> bool:
        """
        Проверяет, является ли ошибка ошибкой недостаточных прав доступа.

        Args:
            e: HttpError от Google API

        Returns:
            True если это ошибка недостаточных прав (403)
        """
        if e.resp.status != 403:
            return False

        error_details = e.error_details if hasattr(e, "error_details") else []
        for detail in error_details:
            if detail.get("reason") == "insufficientPermissions":
                return True
        return False

    def __init__(
        self,
        access_token: str | None = None,
        refresh_token: str | None = None,
        token_expiry: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
    ):
        """
        Инициализирует сервис календаря через OAuth 2.0.

        Args:
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            token_expiry: Время истечения токена
            client_id: OAuth Client ID
            client_secret: OAuth Client Secret
        """
        super().__init__(service_name="calendar", version="v3", scopes=self.SCOPES)

        # Создаем OAuth сервис
        self._oauth_service = GoogleServiceOAuth(
            service_name="calendar",
            version="v3",
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
            # Для Gmail аккаунтов, календарь может быть доступен напрямую по email
            # если он был расшарен с сервисным аккаунтом
            # Сначала пробуем получить календарь напрямую по email
            if (
                "@gmail.com" in user_email.lower()
                or "@googlemail.com" in user_email.lower()
            ):
                try:
                    # Для Gmail, ID календаря обычно это сам email
                    calendar = (
                        self.service.calendars().get(calendarId=user_email).execute()
                    )
                    logger.debug(
                        f"Successfully accessed calendar directly by email: {user_email}"
                    )
                    return user_email
                except HttpError:
                    # Если прямой доступ не работает, продолжаем со списком календарей
                    logger.debug(
                        f"Direct access to {user_email} failed, trying calendar list"
                    )
                except Exception:
                    # Игнорируем ошибки и продолжаем
                    pass

            # Используем календарь пользователя через делегирование или расшаренный календарь
            # Для этого нужно, чтобы сервисный аккаунт имел доступ к календарю пользователя
            calendar_list = self.service.calendarList().list().execute()
            calendars = calendar_list.get("items", [])

            # Ищем календарь пользователя по email в списке доступных календарей
            for calendar in calendars:
                calendar_id = calendar.get("id", "")
                # Проверяем, соответствует ли ID календаря email пользователя
                if user_email.lower() in calendar_id.lower():
                    logger.debug(f"Found user calendar in list: {calendar_id}")
                    return calendar_id

                # Также проверяем по summary (название календаря)
                summary = calendar.get("summary", "").lower()
                email_prefix = user_email.split("@")[0].lower()
                if email_prefix in summary or user_email.lower() in summary:
                    logger.debug(
                        f"Found user calendar by summary: {calendar.get('summary')}"
                    )
                    return calendar_id

            # Ищем основной календарь
            for calendar in calendars:
                if calendar.get("primary", False):
                    logger.debug(f"Found primary calendar: {calendar.get('id')}")
                    return calendar["id"]

            # Если не нашли, возвращаем первый доступный
            if calendars:
                calendar_id = calendars[0].get("id")
                logger.debug(f"Using first available calendar: {calendar_id}")
                return calendar_id

            # Если календарей нет, создаем новый
            logger.warning("No calendars found, creating new one")
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
            created_calendar = self.service.calendars().insert(body=calendar).execute()
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
        recurrence: list[str] | None = None,
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
            recurrence: Список правил повторения в формате RRULE (опционально)

        Returns:
            Созданное событие или None при ошибке
        """
        if not self.service:
            logger.error("GOOGLE_API: Calendar service not initialized")
            return None

        try:
            calendar_id = self.get_calendar_id(user_email)
            if not calendar_id:
                logger.error(f"GOOGLE_API: Could not get calendar_id for {user_email}")
                return None

            # Формируем событие
            event = {
                "summary": summary,
            }

            if description:
                event["description"] = description

            if location:
                event["location"] = location

            if recurrence:
                event["recurrence"] = recurrence

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

            # Логируем вызов API
            logger.info(
                f"GOOGLE_API: Creating event in calendar '{calendar_id}': "
                f"summary='{summary}', start={start_datetime}, end={end_datetime}, "
                f"recurrence={recurrence}"
            )

            # Создаем событие
            created_event = (
                self.service.events()
                .insert(calendarId=calendar_id, body=event)
                .execute()
            )

            event_id = created_event.get("id", "")
            logger.info(f"GOOGLE_API: ✅ Event created successfully: id={event_id}")
            return created_event
        except HttpError as e:
            if self._is_insufficient_permissions_error(e):
                logger.error(
                    f"GOOGLE_API: ❌ Insufficient permissions creating event: {e}"
                )
                # Возвращаем специальный маркер ошибки
                return {"_error": "insufficient_permissions"}
            logger.error(f"GOOGLE_API: ❌ HTTP Error creating event: {e}")
            return None
        except Exception as e:
            logger.error(f"GOOGLE_API: ❌ Unexpected error creating event: {e}")
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
            logger.error("GOOGLE_API: Calendar service not initialized")
            return []

        try:
            calendar_id = self.get_calendar_id(user_email)
            if not calendar_id:
                logger.error(f"GOOGLE_API: Could not get calendar_id for {user_email}")
                return []

            # Параметры запроса
            params = {
                "calendarId": calendar_id,
                "maxResults": max_results,
                "singleEvents": True,
                "orderBy": "startTime",
            }

            if time_min:
                # Убеждаемся, что дата в формате RFC3339 с timezone
                params["timeMin"] = self._ensure_rfc3339_format(time_min)
            else:
                # По умолчанию показываем события с текущего момента
                now = datetime.now(UTC)
                params["timeMin"] = now.isoformat().replace("+00:00", "Z")

            if time_max:
                # Убеждаемся, что дата в формате RFC3339 с timezone
                params["timeMax"] = self._ensure_rfc3339_format(time_max)

            # Логируем вызов API
            logger.info(
                f"GOOGLE_API: Listing events from calendar '{calendar_id}': "
                f"max_results={max_results}, time_min={params.get('timeMin')}, "
                f"time_max={params.get('timeMax')}"
            )

            # Получаем события
            events_result = self.service.events().list(**params).execute()
            # Логируем сырой ответ от Google API
            logger.debug(
                f"GOOGLE_API: Raw response from calendar '{calendar_id}': "
                f"{json.dumps(events_result, ensure_ascii=False, default=str)[:1000]}"
            )
            events = events_result.get("items", [])
            logger.info(f"GOOGLE_API: ✅ Found {len(events)} events")
            return events
        except HttpError as e:
            logger.error(f"GOOGLE_API: ❌ HTTP Error listing events: {e}")
            return []
        except Exception as e:
            logger.error(f"GOOGLE_API: ❌ Unexpected error listing events: {e}")
            return []

    def list_events_from_calendar(
        self,
        calendar_id: str,
        max_results: int = 10,
        time_min: str | None = None,
        time_max: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Получает список событий из конкретного календаря по его ID.

        Args:
            calendar_id: ID календаря
            max_results: Максимальное количество событий
            time_min: Минимальное время в формате ISO 8601
            time_max: Максимальное время в формате ISO 8601

        Returns:
            Список событий
        """
        if not self.service:
            return []

        try:
            # Параметры запроса
            params = {
                "calendarId": calendar_id,
                "maxResults": max_results,
                "singleEvents": True,
                "orderBy": "startTime",
            }

            if time_min:
                params["timeMin"] = self._ensure_rfc3339_format(time_min)
            else:
                now = datetime.now(UTC)
                params["timeMin"] = now.isoformat().replace("+00:00", "Z")

            if time_max:
                params["timeMax"] = self._ensure_rfc3339_format(time_max)

            # Получаем события
            events_result = self.service.events().list(**params).execute()
            # Логируем сырой ответ от Google API
            logger.debug(
                f"GOOGLE_API: Raw response from calendar '{calendar_id}': "
                f"{json.dumps(events_result, ensure_ascii=False, default=str)[:1000]}"
            )
            events = events_result.get("items", [])

            # Помечаем источник календаря для каждого события
            for event in events:
                event["_source_calendar_id"] = calendar_id

            return events
        except HttpError as e:
            # Проверяем ошибку недостаточных прав доступа
            if self._is_insufficient_permissions_error(e):
                logger.error(
                    f"Error listing events from calendar {calendar_id}: "
                    f"Insufficient permissions (403). User needs to re-authorize with Calendar scope."
                )
                # Возвращаем специальный маркер ошибки
                return [
                    {"_error": "insufficient_permissions", "_calendar_id": calendar_id}
                ]

            logger.error(f"Error listing events from calendar {calendar_id}: {e}")
            return []
        except Exception as e:
            logger.error(
                f"Unexpected error listing events from calendar {calendar_id}: {e}"
            )
            return []

    def list_events_from_multiple_calendars(
        self,
        calendar_ids: list[str],
        max_results: int = 10,
        time_min: str | None = None,
        time_max: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Получает события из нескольких календарей и объединяет их.

        Args:
            calendar_ids: Список ID календарей
            max_results: Максимальное количество событий в итоговом списке
            time_min: Минимальное время в формате ISO 8601
            time_max: Максимальное время в формате ISO 8601

        Returns:
            Объединенный отсортированный список событий из всех календарей
        """
        if not self.service or not calendar_ids:
            return []

        all_events = []
        has_permission_error = False

        # Получаем события из каждого календаря
        for calendar_id in calendar_ids:
            events = self.list_events_from_calendar(
                calendar_id=calendar_id,
                max_results=max_results,
                time_min=time_min,
                time_max=time_max,
            )

            # Проверяем наличие ошибки недостаточных прав
            if (
                events
                and isinstance(events, list)
                and len(events) > 0
                and isinstance(events[0], dict)
                and events[0].get("_error") == "insufficient_permissions"
            ):
                has_permission_error = True
                # Убираем маркер ошибки из списка
                continue

            all_events.extend(events)

        # Сортируем все события по времени начала
        all_events.sort(
            key=lambda e: e.get("start", {}).get("dateTime")
            or e.get("start", {}).get("date", "")
        )

        # Ограничиваем количество
        result = all_events[:max_results]

        # Добавляем маркер ошибки, если была ошибка прав доступа
        if has_permission_error:
            result.append({"_error": "insufficient_permissions"})

        return result

    def get_event(self, user_email: str, event_id: str) -> dict[str, Any] | None:
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
            logger.error("GOOGLE_API: Calendar service not initialized")
            return None

        try:
            calendar_id = self.get_calendar_id(user_email)
            if not calendar_id:
                logger.error(f"GOOGLE_API: Could not get calendar_id for {user_email}")
                return None

            # Получаем существующее событие
            event = self.get_event(user_email, event_id)
            if not event:
                logger.error(f"GOOGLE_API: Event {event_id} not found")
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

            # Логируем вызов API
            logger.info(
                f"GOOGLE_API: Updating event {event_id} in calendar '{calendar_id}': "
                f"summary={summary}, start={start_datetime}, end={end_datetime}"
            )

            # Обновляем событие
            updated_event = (
                self.service.events()
                .update(calendarId=calendar_id, eventId=event_id, body=event)
                .execute()
            )

            logger.info(f"GOOGLE_API: ✅ Event updated successfully: id={event_id}")
            return updated_event
        except HttpError as e:
            if self._is_insufficient_permissions_error(e):
                logger.error(
                    f"GOOGLE_API: ❌ Insufficient permissions updating event {event_id}: {e}"
                )
                return {"_error": "insufficient_permissions"}
            logger.error(f"GOOGLE_API: ❌ HTTP Error updating event {event_id}: {e}")
            return None
        except Exception as e:
            logger.error(
                f"GOOGLE_API: ❌ Unexpected error updating event {event_id}: {e}"
            )
            return None

    def delete_event(self, user_email: str, event_id: str) -> bool:
        """
        Удаляет событие из календаря.

        Args:
            user_email: Email пользователя
            event_id: ID события

        Returns:
            True если успешно, False при ошибке
        """
        if not self.service:
            logger.error("GOOGLE_API: Calendar service not initialized")
            return False

        try:
            calendar_id = self.get_calendar_id(user_email)
            if not calendar_id:
                logger.error(f"GOOGLE_API: Could not get calendar_id for {user_email}")
                return False

            # Логируем вызов API
            logger.info(
                f"GOOGLE_API: Deleting event {event_id} from calendar '{calendar_id}'"
            )

            self.service.events().delete(
                calendarId=calendar_id, eventId=event_id
            ).execute()

            logger.info(f"GOOGLE_API: ✅ Event deleted successfully: id={event_id}")
            return True
        except HttpError as e:
            if self._is_insufficient_permissions_error(e):
                logger.error(
                    f"GOOGLE_API: ❌ Insufficient permissions deleting event {event_id}: {e}"
                )
                # Возвращаем специальное значение для ошибки прав
                return None  # None вместо False для отличия от обычной ошибки
            logger.error(f"GOOGLE_API: ❌ HTTP Error deleting event {event_id}: {e}")
            return False
        except Exception as e:
            logger.error(
                f"GOOGLE_API: ❌ Unexpected error deleting event {event_id}: {e}"
            )
            return False
