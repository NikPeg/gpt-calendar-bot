"""
Тесты для проверки ООП структуры calendar_functions.
Тестируем только логику без зависимостей от config и БД.
"""

import sys
from datetime import datetime
from pathlib import Path

# Добавляем корневую директорию проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Импортируем только классы, не требующие инициализации config
from services.calendar_functions import DateTimeParser  # noqa: E402


def test_datetime_parser_with_timezone():
    """Тест парсинга даты с указанным часовым поясом."""
    parser = DateTimeParser()

    # Время уже с timezone - должно конвертироваться в UTC
    dt_str = "2026-01-04T12:00:00+03:00"
    result = parser.parse(dt_str, user_timezone_offset=3)

    # Ожидаем 09:00 UTC (12:00 - 3 часа)
    expected = "2026-01-04T09:00:00Z"
    assert result == expected, f"Expected {expected}, got {result}"


def test_datetime_parser_without_timezone():
    """Тест парсинга даты БЕЗ часового пояса с user_timezone_offset."""
    parser = DateTimeParser()

    # Время без timezone - должно интерпретироваться как время пользователя
    dt_str = "2026-01-04T12:00:00"
    result = parser.parse(dt_str, user_timezone_offset=3)

    # Ожидаем 09:00 UTC (12:00 в UTC+3 = 09:00 в UTC)
    expected = "2026-01-04T09:00:00Z"
    assert result == expected, f"Expected {expected}, got {result}"


def test_datetime_parser_without_offset():
    """Тест парсинга даты БЕЗ часового пояса БЕЗ user_timezone_offset."""
    parser = DateTimeParser()

    # Время без timezone и без offset - должно вернуться как есть
    dt_str = "2026-01-04T12:00:00"
    result = parser.parse(dt_str, user_timezone_offset=None)

    # Ожидаем исходную строку
    expected = dt_str
    assert result == expected, f"Expected {expected}, got {result}"


def test_datetime_parser_negative_offset():
    """Тест парсинга даты с отрицательным смещением."""
    parser = DateTimeParser()

    # Нью-Йорк (UTC-5)
    dt_str = "2026-01-04T12:00:00"
    result = parser.parse(dt_str, user_timezone_offset=-5)

    # Ожидаем 17:00 UTC (12:00 в UTC-5 = 17:00 в UTC)
    expected = "2026-01-04T17:00:00Z"
    assert result == expected, f"Expected {expected}, got {result}"


def test_datetime_parser_with_z_suffix():
    """Тест парсинга даты с Z суффиксом (UTC)."""
    parser = DateTimeParser()

    dt_str = "2026-01-04T12:00:00Z"
    result = parser.parse(dt_str, user_timezone_offset=3)

    # Z означает UTC, время не должно меняться
    expected = "2026-01-04T12:00:00Z"
    assert result == expected, f"Expected {expected}, got {result}"


def test_datetime_parser_none():
    """Тест парсинга None."""
    parser = DateTimeParser()

    result = parser.parse(None, user_timezone_offset=3)
    assert result is None, f"Expected None, got {result}"


def test_datetime_parser_empty_string():
    """Тест парсинга пустой строки."""
    parser = DateTimeParser()

    result = parser.parse("", user_timezone_offset=3)
    assert result is None, f"Expected None, got {result}"


def test_get_current_datetime_for_user():
    """Тест получения текущего времени для пользователя."""
    parser = DateTimeParser()

    # Москва (UTC+3)
    result = parser.get_current_datetime_for_user(3)

    # Проверяем, что вернулась строка в формате ISO
    assert isinstance(result, str)
    assert "T" in result
    # Проверяем, что можно распарсить обратно
    dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
    assert dt is not None


def test_datetime_parser_static_methods():
    """Тест статических методов DateTimeParser."""
    # Статические методы должны работать без создания экземпляра

    # Тест parse
    dt_str = "2026-01-04T12:00:00+03:00"
    result = DateTimeParser.parse(dt_str, user_timezone_offset=3)
    expected = "2026-01-04T09:00:00Z"
    assert result == expected, f"Expected {expected}, got {result}"

    # Тест get_current_datetime_for_user
    result = DateTimeParser.get_current_datetime_for_user(3)
    assert isinstance(result, str)
    assert "T" in result


if __name__ == "__main__":
    print("Запуск тестов ООП структуры calendar_functions...\n")

    test_datetime_parser_with_timezone()
    print("✅ test_datetime_parser_with_timezone")

    test_datetime_parser_without_timezone()
    print("✅ test_datetime_parser_without_timezone")

    test_datetime_parser_without_offset()
    print("✅ test_datetime_parser_without_offset")

    test_datetime_parser_negative_offset()
    print("✅ test_datetime_parser_negative_offset")

    test_datetime_parser_with_z_suffix()
    print("✅ test_datetime_parser_with_z_suffix")

    test_datetime_parser_none()
    print("✅ test_datetime_parser_none")

    test_datetime_parser_empty_string()
    print("✅ test_datetime_parser_empty_string")

    test_get_current_datetime_for_user()
    print("✅ test_get_current_datetime_for_user")

    test_datetime_parser_static_methods()
    print("✅ test_datetime_parser_static_methods")

    print("\n🎉 Все тесты ООП структуры пройдены успешно!")
