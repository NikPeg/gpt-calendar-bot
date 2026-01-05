"""
Функции для работы с Google Calendar через Function Calling.
Реализация на основе паттерна Command для чистой архитектуры.
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from core.config import TIMEZONE_OFFSET, logger
from core.database import Conversation
from services.calendar_service import CalendarService

# Определения функций для LLM
CALENDAR_FUNCTIONS = [
    {
        "name": "create_calendar_event",
        "description": "Создает новое событие в календаре пользователя. Поддерживает создание повторяющихся событий (еженедельных, ежемесячных)",
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
                "recurrence_rule": {
                    "type": "string",
                    "description": "Правило повторения события (опционально). Используй значения: 'weekly' для еженедельных событий или 'monthly' для ежемесячных событий. Если параметр не указан, событие будет одноразовым",
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


class DateTimeParser:
    """Парсер дат и времени с поддержкой часовых поясов."""

    @staticmethod
    def parse(
        datetime_str: str | None, user_timezone_offset: int | None = None
    ) -> str | None:
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

    @staticmethod
    def get_current_datetime_for_user(user_timezone_offset: int) -> str:
        """
        Возвращает текущее время в формате ISO для указанного часового пояса.

        Args:
            user_timezone_offset: Смещение часового пояса от UTC

        Returns:
            Текущее время в формате ISO
        """
        now = datetime.now(timezone(timedelta(hours=user_timezone_offset)))
        return now.isoformat().replace("+00:00", "Z")


class CalendarContext:
    """Контекст выполнения операций с календарем."""

    def __init__(
        self,
        user_id: int,
        calendar_service: CalendarService,
        primary_calendar_id: str,
        all_calendar_ids: list[str],
        timezone_offset: int,
    ):
        """
        Инициализирует контекст календаря.

        Args:
            user_id: ID пользователя
            calendar_service: Сервис для работы с Google Calendar
            primary_calendar_id: ID основного календаря (для записи)
            all_calendar_ids: Список ID всех включенных календарей (для чтения)
            timezone_offset: Смещение часового пояса пользователя
        """
        self.user_id = user_id
        self.calendar_service = calendar_service
        self.primary_calendar_id = primary_calendar_id
        self.all_calendar_ids = all_calendar_ids
        self.timezone_offset = timezone_offset

    @classmethod
    async def create(cls, user_id: int) -> "CalendarContext | None":
        """
        Создает контекст из данных пользователя.

        Args:
            user_id: ID пользователя

        Returns:
            CalendarContext или None, если не удалось создать
        """
        from core.database import UserCalendar

        # Получаем данные пользователя
        conversation = Conversation(user_id)
        await conversation.get_from_db()

        # Проверяем, настроен ли OAuth
        if not conversation.oauth_access_token:
            logger.error(f"USER{user_id}: Google Calendar not connected via OAuth")
            return None

        # Создаем сервис календаря через OAuth
        from core.config import GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET

        calendar_service = CalendarService(
            access_token=conversation.oauth_access_token,
            refresh_token=conversation.oauth_refresh_token,
            token_expiry=conversation.oauth_token_expiry,
            client_id=GOOGLE_OAUTH_CLIENT_ID,
            client_secret=GOOGLE_OAUTH_CLIENT_SECRET,
        )

        if not calendar_service.is_configured():
            logger.error(f"USER{user_id}: Calendar service not configured properly")
            return None

        # Проверяем и сохраняем обновленные токены если они изменились
        updated_tokens = calendar_service.get_updated_tokens()
        if updated_tokens["access_token"] != conversation.oauth_access_token:
            conversation.oauth_access_token = updated_tokens["access_token"]
            conversation.oauth_token_expiry = updated_tokens["token_expiry"]
            await conversation.update_in_db()
            logger.debug(f"USER{user_id}: OAuth tokens updated in database")

        # Получаем основной календарь
        primary_calendar = await UserCalendar.get_primary_calendar(user_id)
        if not primary_calendar:
            # Если нет записи в user_calendars, пытаемся создать из user_email
            user_email = await cls._get_user_email(
                user_id, conversation, calendar_service
            )
            if not user_email:
                logger.error(f"USER{user_id}: Could not determine user email")
                return None

            # Создаем запись основного календаря
            primary_calendar = await UserCalendar.add_public_calendar(
                user_id=user_id,
                calendar_id=user_email,
                calendar_name="Основной календарь",
            )
            # Меняем тип на primary
            primary_calendar.calendar_type = UserCalendar.TYPE_PRIMARY
            primary_calendar.is_readonly = False
            await primary_calendar.update_in_db()

        # Получаем все включенные календари
        all_calendar_ids = await UserCalendar.get_enabled_calendar_ids(user_id)

        # Определяем часовой пояс
        timezone_offset = (
            conversation.timezone_offset
            if conversation.timezone_offset is not None
            else TIMEZONE_OFFSET
        )

        return cls(
            user_id,
            calendar_service,
            primary_calendar.calendar_id,
            all_calendar_ids,
            timezone_offset,
        )

    @staticmethod
    async def _get_user_email(
        user_id: int, conversation: Conversation, calendar_service: CalendarService
    ) -> str | None:
        """
        Определяет email пользователя через OAuth.

        Args:
            user_id: ID пользователя
            conversation: Объект разговора с пользователем
            calendar_service: Сервис календаря

        Returns:
            Email пользователя или None
        """
        try:
            # Пытаемся получить primary календарь через OAuth
            # Primary календарь всегда доступен и его ID - это email пользователя
            if calendar_service.service:
                try:
                    calendar_list = (
                        calendar_service.service.calendarList().list().execute()
                    )
                    calendars = calendar_list.get("items", [])

                    # Ищем primary календарь
                    for cal in calendars:
                        if cal.get("primary", False):
                            user_email = cal.get("id")
                            logger.info(
                                f"USER{user_id}: Detected user email from primary calendar: {user_email}"
                            )
                            # Сохраняем email в БД если его там нет
                            if not conversation.user_email:
                                conversation.user_email = user_email
                                await conversation.update_in_db()
                            return user_email

                    # Если primary не найден, берем первый доступный
                    if calendars:
                        user_email = calendars[0].get("id")
                        logger.info(
                            f"USER{user_id}: Using first available calendar: {user_email}"
                        )
                        if not conversation.user_email:
                            conversation.user_email = user_email
                            await conversation.update_in_db()
                        return user_email

                except Exception as e:
                    logger.error(f"USER{user_id}: Error getting calendar list: {e}")

            logger.error(f"USER{user_id}: Could not determine user email")
            return None

        except Exception as e:
            logger.error(f"Error getting user email: {e}")
            return None


class CalendarCommand(ABC):
    """Абстрактный базовый класс для команд работы с календарем."""

    def __init__(self, context: CalendarContext, arguments: dict[str, Any]):
        self.context = context
        self.arguments = arguments
        self.datetime_parser = DateTimeParser()

    @abstractmethod
    async def execute(self) -> str:
        """Выполняет команду и возвращает результат."""
        ...

    def _parse_datetime(self, datetime_str: str | None) -> str | None:
        """Парсит дату/время с учетом часового пояса пользователя."""
        return self.datetime_parser.parse(datetime_str, self.context.timezone_offset)

    def _get_current_datetime(self) -> str:
        """Возвращает текущее время для пользователя."""
        return self.datetime_parser.get_current_datetime_for_user(
            self.context.timezone_offset
        )


class CreateEventCommand(CalendarCommand):
    """Команда создания события в календаре."""

    async def execute(self) -> str:
        summary = self.arguments.get("summary", "")
        if not summary:
            return "❌ Не указано название события"

        description = self.arguments.get("description")
        start_datetime = self._parse_datetime(self.arguments.get("start_datetime"))
        end_datetime = self._parse_datetime(self.arguments.get("end_datetime"))
        location = self.arguments.get("location")
        recurrence_rule = self.arguments.get("recurrence_rule")

        # Если время не указано, используем текущее время
        if not start_datetime:
            start_datetime = self._get_current_datetime()

        # Обрабатываем правило повторения
        recurrence = None
        if recurrence_rule:
            recurrence = self._parse_recurrence_rule(recurrence_rule)

        # Создаем событие в основном календаре
        event = self.context.calendar_service.create_event(
            user_email=self.context.primary_calendar_id,
            summary=summary,
            description=description,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            location=location,
            recurrence=recurrence,
        )

        if event:
            event_id = event.get("id", "")
            start = event.get("start", {}).get("dateTime", "")
            recurrence_info = " (повторяющееся)" if recurrence else ""
            return f"✅ Событие создано успешно{recurrence_info}!\n\nID: {event_id}\nВремя: {start}"
        return "❌ Не удалось создать событие"

    @staticmethod
    def _parse_recurrence_rule(recurrence_rule: str) -> list[str] | None:
        """
        Преобразует строковое правило повторения в формат RRULE для Google Calendar API.

        Args:
            recurrence_rule: Строковое правило ('weekly', 'monthly')

        Returns:
            Список строк RRULE или None
        """
        rule_lower = recurrence_rule.lower().strip()

        if rule_lower == "weekly":
            # Еженедельное повторение без даты окончания
            return ["RRULE:FREQ=WEEKLY;INTERVAL=1"]
        if rule_lower == "monthly":
            # Ежемесячное повторение без даты окончания
            return ["RRULE:FREQ=MONTHLY;INTERVAL=1"]
        logger.warning(
            f"Unknown recurrence rule: {recurrence_rule}. Supported: 'weekly', 'monthly'"
        )
        return None


class ListEventsCommand(CalendarCommand):
    """Команда получения списка событий из всех календарей пользователя."""

    async def execute(self) -> str:
        max_results = self.arguments.get("max_results", 10)
        time_min = self._parse_datetime(self.arguments.get("time_min"))
        time_max = self._parse_datetime(self.arguments.get("time_max"))

        # Получаем события из всех календарей пользователя
        events = self.context.calendar_service.list_events_from_multiple_calendars(
            calendar_ids=self.context.all_calendar_ids,
            max_results=max_results,
            time_min=time_min,
            time_max=time_max,
        )

        if not events:
            return "📅 Событий не найдено"

        result = f"📅 Найдено событий: {len(events)}\n\n"
        for i, event in enumerate(events, 1):
            summary = event.get("summary", "Без названия")
            start = event.get("start", {}).get("dateTime") or event.get(
                "start", {}
            ).get("date", "Время не указано")
            event_id = event.get("id", "")
            source_calendar = event.get("_source_calendar_id", "")

            result += f"{i}. {summary}\n   Время: {start}\n   ID: {event_id}\n"

            # Добавляем информацию об источнике, если событие не из основного календаря
            if source_calendar and source_calendar != self.context.primary_calendar_id:
                # Упрощаем отображение для публичных календарей
                if "holiday" in source_calendar.lower():
                    result += "   📌 Праздник\n"
                elif "public" in source_calendar.lower():
                    result += "   📌 Публичный календарь\n"

            result += "\n"

        return result.strip()


class GetEventCommand(CalendarCommand):
    """Команда получения информации о событии."""

    async def execute(self) -> str:
        event_id = self.arguments.get("event_id")
        if not event_id:
            return "❌ Не указан ID события"

        # Пробуем найти событие в основном календаре
        event = self.context.calendar_service.get_event(
            self.context.primary_calendar_id, event_id
        )

        if not event:
            return f"❌ Событие с ID {event_id} не найдено"

        return self._format_event_details(event, event_id)

    @staticmethod
    def _format_event_details(event: dict[str, Any], event_id: str) -> str:
        """Форматирует детали события для отображения."""
        summary = event.get("summary", "Без названия")
        description = event.get("description", "")
        start = event.get("start", {}).get("dateTime") or event.get("start", {}).get(
            "date", "Время не указано"
        )
        end = event.get("end", {}).get("dateTime") or event.get("end", {}).get(
            "date", "Время не указано"
        )
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


class UpdateEventCommand(CalendarCommand):
    """Команда обновления события."""

    async def execute(self) -> str:
        event_id = self.arguments.get("event_id")
        if not event_id:
            return "❌ Не указан ID события"

        summary = self.arguments.get("summary")
        description = self.arguments.get("description")
        start_datetime = self._parse_datetime(self.arguments.get("start_datetime"))
        end_datetime = self._parse_datetime(self.arguments.get("end_datetime"))
        location = self.arguments.get("location")

        # Обновляем событие в основном календаре
        event = self.context.calendar_service.update_event(
            user_email=self.context.primary_calendar_id,
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


class DeleteEventCommand(CalendarCommand):
    """Команда удаления события."""

    async def execute(self) -> str:
        event_id = self.arguments.get("event_id")
        if not event_id:
            return "❌ Не указан ID события"

        # Удаляем событие из основного календаря
        success = self.context.calendar_service.delete_event(
            self.context.primary_calendar_id, event_id
        )

        if success:
            return f"✅ Событие удалено успешно!\n\nID: {event_id}"
        return f"❌ Не удалось удалить событие с ID {event_id}"


class CalendarCommandFactory:
    """Фабрика для создания команд работы с календарем."""

    _commands: dict[str, type[CalendarCommand]] = {
        "create_calendar_event": CreateEventCommand,
        "list_calendar_events": ListEventsCommand,
        "get_calendar_event": GetEventCommand,
        "update_calendar_event": UpdateEventCommand,
        "delete_calendar_event": DeleteEventCommand,
    }

    @classmethod
    def create(
        cls, function_name: str, context: CalendarContext, arguments: dict[str, Any]
    ) -> CalendarCommand | None:
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
    try:
        # Создаем контекст
        context = await CalendarContext.create(user_id)
        if not context:
            return "❌ Календарь не настроен. Пожалуйста, настройте календарь командой /start"

        # Создаем и выполняем команду
        command = CalendarCommandFactory.create(function_name, context, arguments)
        if not command:
            return f"❌ Неизвестная функция: {function_name}"

        return await command.execute()

    except Exception as e:
        logger.error(
            f"Error executing calendar function {function_name}: {e}", exc_info=True
        )
        return f"❌ Произошла ошибка при выполнении операции: {str(e)}"


# Для обратной совместимости экспортируем parse_datetime
def parse_datetime(
    datetime_str: str | None, user_timezone_offset: int | None = None
) -> str | None:
    """
    Парсит строку с датой/временем в ISO 8601 формат.
    Обертка над DateTimeParser для обратной совместимости.

    Args:
        datetime_str: Строка с датой/временем
        user_timezone_offset: Смещение часового пояса пользователя от UTC (опционально)

    Returns:
        ISO 8601 строка в UTC или None
    """
    return DateTimeParser.parse(datetime_str, user_timezone_offset)
