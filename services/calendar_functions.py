"""
Функции для работы с Google Calendar через Function Calling.
"""

import json
from datetime import UTC, datetime, timedelta, timezone

from core.config import TIMEZONE_OFFSET, logger
from core.database import Conversation
from services.calendar_service import CalendarService

# Определения функций для LLM
CALENDAR_FUNCTIONS = [
    {
        "name": "create_calendar_event",
        "description": "Создает новое событие в календаре пользователя",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Название события (обязательно)",
                },
                "description": {
                    "type": "string",
                    "description": "Описание события (опционально)",
                },
                "start_datetime": {
                    "type": "string",
                    "description": "Дата и время начала события в формате ISO 8601 (YYYY-MM-DDTHH:MM:SS) или относительное время (например, 'через 2 часа', 'завтра в 15:00'). Если не указано, используется текущее время",
                },
                "end_datetime": {
                    "type": "string",
                    "description": "Дата и время окончания события в формате ISO 8601 (YYYY-MM-DDTHH:MM:SS) или относительное время. Если не указано, событие длится 1 час",
                },
                "location": {
                    "type": "string",
                    "description": "Место проведения события (опционально)",
                },
            },
            "required": ["summary"],
        },
    },
    {
        "name": "list_calendar_events",
        "description": "Получает список событий из календаря пользователя",
        "parameters": {
            "type": "object",
            "properties": {
                "max_results": {
                    "type": "integer",
                    "description": "Максимальное количество событий для отображения (по умолчанию 10)",
                },
                "time_min": {
                    "type": "string",
                    "description": "Минимальное время для фильтрации событий в формате ISO 8601 (опционально)",
                },
                "time_max": {
                    "type": "string",
                    "description": "Максимальное время для фильтрации событий в формате ISO 8601 (опционально)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_calendar_event",
        "description": "Получает информацию о конкретном событии по его ID",
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "ID события в календаре (обязательно)",
                },
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "update_calendar_event",
        "description": "Обновляет существующее событие в календаре",
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "ID события для обновления (обязательно)",
                },
                "summary": {
                    "type": "string",
                    "description": "Новое название события (опционально)",
                },
                "description": {
                    "type": "string",
                    "description": "Новое описание события (опционально)",
                },
                "start_datetime": {
                    "type": "string",
                    "description": "Новое время начала в формате ISO 8601 (опционально)",
                },
                "end_datetime": {
                    "type": "string",
                    "description": "Новое время окончания в формате ISO 8601 (опционально)",
                },
                "location": {
                    "type": "string",
                    "description": "Новое место проведения (опционально)",
                },
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "delete_calendar_event",
        "description": "Удаляет событие из календаря",
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "ID события для удаления (обязательно)",
                },
            },
            "required": ["event_id"],
        },
    },
]


def parse_datetime(datetime_str: str | None, user_timezone_offset: int | None = None) -> str | None:
    """
    Парсит строку с датой/временем в ISO 8601 формат.
    Поддерживает относительные времена (например, "через 2 часа", "завтра в 15:00").
    
    Если datetime_str не содержит информацию о часовом поясе, предполагается,
    что время указано в часовом поясе пользователя и конвертируется в UTC.

    Args:
        datetime_str: Строка с датой/временем
        user_timezone_offset: Смещение часового пояса пользователя от UTC (опционально)

    Returns:
        ISO 8601 строка в UTC или None
    """
    if not datetime_str:
        return None

    # Если уже в формате ISO 8601 с timezone, возвращаем как есть
    try:
        dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
        # Если datetime уже имеет timezone, возвращаем как есть
        if dt.tzinfo is not None:
            # Конвертируем в UTC
            dt_utc = dt.astimezone(UTC)
            return dt_utc.isoformat().replace("+00:00", "Z")
        # Если нет timezone, предполагаем что это время пользователя
        if user_timezone_offset is not None:
            user_tz = timezone(timedelta(hours=user_timezone_offset))
            dt = dt.replace(tzinfo=user_tz)
            dt_utc = dt.astimezone(UTC)
            return dt_utc.isoformat().replace("+00:00", "Z")
        return datetime_str
    except (ValueError, AttributeError):
        pass

    # TODO: Добавить парсинг относительных времен
    # Пока просто возвращаем None для относительных времен
    # В будущем можно добавить библиотеку для парсинга естественного языка

    return None


async def execute_calendar_function(
    function_name: str, arguments: dict, user_id: int
) -> str:
    """
    Выполняет функцию работы с календарем.

    Args:
        function_name: Название функции
        arguments: Аргументы функции
        user_id: ID пользователя

    Returns:
        Результат выполнения функции в виде строки
    """
    # Получаем данные пользователя
    conversation = Conversation(user_id)
    await conversation.get_from_db()

    if not conversation.service_account_json:
        return (
            "❌ Календарь не настроен. Пожалуйста, настройте календарь командой /start"
        )

    # Создаем сервис календаря
    calendar_service = CalendarService(conversation.service_account_json)

    if not calendar_service.is_configured():
        return "❌ Ошибка доступа к календарю. Пожалуйста, проверьте настройки."

    # Получаем email пользователя из базы данных
    # Если email не сохранен, пытаемся определить автоматически
    try:
        user_email = conversation.user_email

        # Если email не сохранен, пытаемся определить из доступных календарей
        if not user_email:
            logger.warning(
                f"USER{user_id}: user_email not found in database, trying to detect automatically"
            )
            service_account_data = json.loads(conversation.service_account_json)
            service_account_email = service_account_data.get("client_email", "")

            try:
                # Получаем список доступных календарей
                calendar_list = calendar_service.service.calendarList().list().execute()
                calendars = calendar_list.get("items", [])

                # Ищем календарь пользователя (Gmail календари обычно имеют email как ID)
                for cal in calendars:
                    cal_id = cal.get("id", "")
                    # Если ID календаря - это Gmail адрес (не сервисный аккаунт)
                    if (
                        "@gmail.com" in cal_id.lower()
                        and service_account_email.lower() not in cal_id.lower()
                    ):
                        user_email = cal_id
                        logger.info(
                            f"USER{user_id}: Auto-detected user email: {user_email}"
                        )
                        # Сохраняем найденный email в БД
                        conversation.user_email = user_email
                        await conversation.update_in_db()
                        break
            except Exception as e:
                logger.debug(f"Could not detect user email from calendar list: {e}")

            # Если не нашли, используем email сервисного аккаунта
            if not user_email:
                user_email = service_account_email
                logger.warning(
                    f"USER{user_id}: Using service account email as fallback: {user_email}"
                )
        else:
            logger.debug(f"USER{user_id}: Using saved user email: {user_email}")
    except Exception as e:
        logger.error(f"Error getting user email: {e}")
        return "❌ Ошибка при обработке данных сервисного аккаунта"

    try:
        if function_name == "create_calendar_event":
            summary = arguments.get("summary", "")
            if not summary:
                return "❌ Не указано название события"

            description = arguments.get("description")
            user_timezone_offset = conversation.timezone_offset if conversation.timezone_offset is not None else TIMEZONE_OFFSET
            start_datetime = parse_datetime(arguments.get("start_datetime"), user_timezone_offset)
            end_datetime = parse_datetime(arguments.get("end_datetime"), user_timezone_offset)
            location = arguments.get("location")

            # Если время не указано, используем текущее время
            if not start_datetime:
                # Используем персональный часовой пояс пользователя или значение по умолчанию
                user_timezone_offset = conversation.timezone_offset if conversation.timezone_offset is not None else TIMEZONE_OFFSET
                now = datetime.now(timezone(timedelta(hours=user_timezone_offset)))
                # Форматируем в RFC3339 для Google Calendar API
                start_datetime = now.isoformat().replace("+00:00", "Z")

            event = calendar_service.create_event(
                user_email=user_email,
                summary=summary,
                description=description,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                location=location,
            )

            if event:
                event_id = event.get("id", "")
                start = event.get("start", {}).get("dateTime", "")
                return f"✅ Событие создано успешно!\n\nID: {event_id}\nВремя: {start}"
            return "❌ Не удалось создать событие"

        if function_name == "list_calendar_events":
            max_results = arguments.get("max_results", 10)
            user_timezone_offset = conversation.timezone_offset if conversation.timezone_offset is not None else TIMEZONE_OFFSET
            time_min = parse_datetime(arguments.get("time_min"), user_timezone_offset)
            time_max = parse_datetime(arguments.get("time_max"), user_timezone_offset)

            events = calendar_service.list_events(
                user_email=user_email,
                max_results=max_results,
                time_min=time_min,
                time_max=time_max,
            )

            if not events:
                return "📅 Событий не найдено"

            result = f"📅 Найдено событий: {len(events)}\n\n"
            for i, event in enumerate(events, 1):
                summary = event.get("summary", "Без названия")
                start = event.get("start", {}).get("dateTime", "Время не указано")
                event_id = event.get("id", "")
                result += f"{i}. {summary}\n   Время: {start}\n   ID: {event_id}\n\n"

            return result.strip()

        if function_name == "get_calendar_event":
            event_id = arguments.get("event_id")
            if not event_id:
                return "❌ Не указан ID события"

            event = calendar_service.get_event(user_email, event_id)

            if not event:
                return f"❌ Событие с ID {event_id} не найдено"

            summary = event.get("summary", "Без названия")
            description = event.get("description", "")
            start = event.get("start", {}).get("dateTime", "Время не указано")
            end = event.get("end", {}).get("dateTime", "Время не указано")
            location = event.get("location", "")

            result = f"📅 {summary}\n\n"
            if description:
                result += f"Описание: {description}\n"
            result += f"Начало: {start}\n"
            result += f"Окончание: {end}\n"
            if location:
                result += f"Место: {location}\n"
            result += f"\nID: {event_id}"

            return result

        if function_name == "update_calendar_event":
            event_id = arguments.get("event_id")
            if not event_id:
                return "❌ Не указан ID события"

            summary = arguments.get("summary")
            description = arguments.get("description")
            user_timezone_offset = conversation.timezone_offset if conversation.timezone_offset is not None else TIMEZONE_OFFSET
            start_datetime = parse_datetime(arguments.get("start_datetime"), user_timezone_offset)
            end_datetime = parse_datetime(arguments.get("end_datetime"), user_timezone_offset)
            location = arguments.get("location")

            event = calendar_service.update_event(
                user_email=user_email,
                event_id=event_id,
                summary=summary,
                description=description,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                location=location,
            )

            if event:
                return f"✅ Событие обновлено успешно!\n\nID: {event_id}"
            return f"❌ Не удалось обновить событие с ID {event_id}"

        if function_name == "delete_calendar_event":
            event_id = arguments.get("event_id")
            if not event_id:
                return "❌ Не указан ID события"

            success = calendar_service.delete_event(user_email, event_id)

            if success:
                return f"✅ Событие удалено успешно!\n\nID: {event_id}"
            return f"❌ Не удалось удалить событие с ID {event_id}"

        return f"❌ Неизвестная функция: {function_name}"

    except Exception as e:
        logger.error(
            f"Error executing calendar function {function_name}: {e}", exc_info=True
        )
        return f"❌ Произошла ошибка при выполнении операции: {str(e)}"
