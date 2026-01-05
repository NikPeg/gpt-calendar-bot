"""
Тесты для функции _parse_recurrence_rule из calendar_functions.
"""

import os
import sys
from pathlib import Path

# Настраиваем переменные окружения ДО импорта модулей проекта
project_root = Path(__file__).parent.parent
os.environ.setdefault("LOG_FILE_PATH", str(project_root / "logs" / "debug.log"))
os.environ.setdefault("DATABASE_NAME", str(project_root / "data" / "users.db"))
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_token")
os.environ.setdefault("GOOGLE_OAUTH_CLIENT_ID", "test_client_id")
os.environ.setdefault("GOOGLE_OAUTH_CLIENT_SECRET", "test_client_secret")

# Добавляем корневую директорию в путь
sys.path.insert(0, str(project_root))

from services.calendar_functions import CreateEventCommand  # noqa: E402


class TestRecurrenceRule:
    """Тесты для парсинга правил повторения событий."""

    def test_weekly_recurrence(self):
        """Тест еженедельного повторения."""
        result = CreateEventCommand._parse_recurrence_rule("weekly")
        assert result == ["RRULE:FREQ=WEEKLY;INTERVAL=1"]

    def test_biweekly_recurrence(self):
        """Тест повторения раз в две недели."""
        result = CreateEventCommand._parse_recurrence_rule("biweekly")
        assert result == ["RRULE:FREQ=WEEKLY;INTERVAL=2"]

    def test_weekdays_recurrence(self):
        """Тест повторения в будние дни."""
        result = CreateEventCommand._parse_recurrence_rule("weekdays")
        assert result == ["RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"]

    def test_monthly_recurrence(self):
        """Тест ежемесячного повторения."""
        result = CreateEventCommand._parse_recurrence_rule("monthly")
        assert result == ["RRULE:FREQ=MONTHLY;INTERVAL=1"]

    def test_case_insensitive(self):
        """Тест регистронезависимости."""
        assert CreateEventCommand._parse_recurrence_rule("WEEKLY") == [
            "RRULE:FREQ=WEEKLY;INTERVAL=1"
        ]
        assert CreateEventCommand._parse_recurrence_rule("BiWeekly") == [
            "RRULE:FREQ=WEEKLY;INTERVAL=2"
        ]
        assert CreateEventCommand._parse_recurrence_rule("WeekDays") == [
            "RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"
        ]
        assert CreateEventCommand._parse_recurrence_rule("MONTHLY") == [
            "RRULE:FREQ=MONTHLY;INTERVAL=1"
        ]

    def test_with_whitespace(self):
        """Тест обработки пробелов."""
        assert CreateEventCommand._parse_recurrence_rule("  weekly  ") == [
            "RRULE:FREQ=WEEKLY;INTERVAL=1"
        ]
        assert CreateEventCommand._parse_recurrence_rule(" biweekly ") == [
            "RRULE:FREQ=WEEKLY;INTERVAL=2"
        ]

    def test_unknown_rule(self):
        """Тест неизвестного правила."""
        result = CreateEventCommand._parse_recurrence_rule("daily")
        assert result is None

    def test_empty_string(self):
        """Тест пустой строки."""
        result = CreateEventCommand._parse_recurrence_rule("")
        assert result is None

    def test_invalid_rule(self):
        """Тест невалидного правила."""
        result = CreateEventCommand._parse_recurrence_rule("invalid_rule")
        assert result is None
