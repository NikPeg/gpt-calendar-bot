"""
Функции для работы с Google Calendar через Function Calling.
"""

import json
from datetime import datetime, timedelta, timezone

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


def parse_datetime(datetime_str: str | None) -> str | None:
    """
    Парсит строку с датой/временем в ISO 8601 формат.
    Поддерживает относительные времена (например, "через 2 часа", "завтра в 15:00").
    
    Args:
        datetime_str: Строка с датой/временем
        
    Returns:
        ISO 8601 строка или None
    """
    if not datetime_str:
        return None
    
    # Если уже в формате ISO 8601, возвращаем как есть
    try:
        datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
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
        return "❌ Календарь не настроен. Пожалуйста, настройте календарь командой /start"
    
    # Создаем сервис календаря
    calendar_service = CalendarService(conversation.service_account_json)
    
    if not calendar_service.is_configured():
        return "❌ Ошибка доступа к календарю. Пожалуйста, проверьте настройки."
    
    # Получаем email пользователя из JSON
    try:
        service_account_data = json.loads(conversation.service_account_json)
        user_email = service_account_data.get("client_email", "")
    except Exception as e:
        logger.error(f"Error parsing service account JSON: {e}")
        return "❌ Ошибка при обработке данных сервисного аккаунта"
    
    try:
        if function_name == "create_calendar_event":
            summary = arguments.get("summary", "")
            if not summary:
                return "❌ Не указано название события"
            
            description = arguments.get("description")
            start_datetime = parse_datetime(arguments.get("start_datetime"))
            end_datetime = parse_datetime(arguments.get("end_datetime"))
            location = arguments.get("location")
            
            # Если время не указано, используем текущее время
            if not start_datetime:
                now = datetime.now(timezone(timedelta(hours=TIMEZONE_OFFSET)))
                start_datetime = now.isoformat()
            
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
            else:
                return "❌ Не удалось создать событие"
        
        elif function_name == "list_calendar_events":
            max_results = arguments.get("max_results", 10)
            time_min = parse_datetime(arguments.get("time_min"))
            time_max = parse_datetime(arguments.get("time_max"))
            
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
        
        elif function_name == "get_calendar_event":
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
        
        elif function_name == "update_calendar_event":
            event_id = arguments.get("event_id")
            if not event_id:
                return "❌ Не указан ID события"
            
            summary = arguments.get("summary")
            description = arguments.get("description")
            start_datetime = parse_datetime(arguments.get("start_datetime"))
            end_datetime = parse_datetime(arguments.get("end_datetime"))
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
            else:
                return f"❌ Не удалось обновить событие с ID {event_id}"
        
        elif function_name == "delete_calendar_event":
            event_id = arguments.get("event_id")
            if not event_id:
                return "❌ Не указан ID события"
            
            success = calendar_service.delete_event(user_email, event_id)
            
            if success:
                return f"✅ Событие удалено успешно!\n\nID: {event_id}"
            else:
                return f"❌ Не удалось удалить событие с ID {event_id}"
        
        else:
            return f"❌ Неизвестная функция: {function_name}"
    
    except Exception as e:
        logger.error(f"Error executing calendar function {function_name}: {e}", exc_info=True)
        return f"❌ Произошла ошибка при выполнении операции: {str(e)}"

