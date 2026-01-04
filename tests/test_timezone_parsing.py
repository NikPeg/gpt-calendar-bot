"""
Тесты для проверки корректности работы с часовыми поясами.
"""

import sys
from pathlib import Path

# Добавляем корневую директорию проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from datetime import UTC, datetime, timedelta, timezone

from services.calendar_functions import parse_datetime


def test_parse_datetime_with_timezone():
    """Тест парсинга даты с указанным часовым поясом."""
    # Время уже с timezone - должно конвертироваться в UTC
    dt_str = "2026-01-04T12:00:00+03:00"
    result = parse_datetime(dt_str, user_timezone_offset=3)
    
    # Ожидаем 09:00 UTC (12:00 - 3 часа)
    expected = "2026-01-04T09:00:00Z"
    assert result == expected, f"Expected {expected}, got {result}"


def test_parse_datetime_without_timezone():
    """Тест парсинга даты БЕЗ часового пояса с user_timezone_offset."""
    # Время без timezone - должно интерпретироваться как время пользователя
    dt_str = "2026-01-04T12:00:00"
    result = parse_datetime(dt_str, user_timezone_offset=3)
    
    # Ожидаем 09:00 UTC (12:00 в UTC+3 = 09:00 в UTC)
    expected = "2026-01-04T09:00:00Z"
    assert result == expected, f"Expected {expected}, got {result}"


def test_parse_datetime_without_offset():
    """Тест парсинга даты БЕЗ часового пояса БЕЗ user_timezone_offset."""
    # Время без timezone и без offset - должно вернуться как есть
    dt_str = "2026-01-04T12:00:00"
    result = parse_datetime(dt_str, user_timezone_offset=None)
    
    # Ожидаем исходную строку
    expected = dt_str
    assert result == expected, f"Expected {expected}, got {result}"


def test_parse_datetime_negative_offset():
    """Тест парсинга даты с отрицательным смещением."""
    # Нью-Йорк (UTC-5)
    dt_str = "2026-01-04T12:00:00"
    result = parse_datetime(dt_str, user_timezone_offset=-5)
    
    # Ожидаем 17:00 UTC (12:00 в UTC-5 = 17:00 в UTC)
    expected = "2026-01-04T17:00:00Z"
    assert result == expected, f"Expected {expected}, got {result}"


def test_parse_datetime_with_z_suffix():
    """Тест парсинга даты с Z суффиксом (UTC)."""
    dt_str = "2026-01-04T12:00:00Z"
    result = parse_datetime(dt_str, user_timezone_offset=3)
    
    # Z означает UTC, время не должно меняться
    expected = "2026-01-04T12:00:00Z"
    assert result == expected, f"Expected {expected}, got {result}"


def test_parse_datetime_none():
    """Тест парсинга None."""
    result = parse_datetime(None, user_timezone_offset=3)
    assert result is None, f"Expected None, got {result}"


def test_parse_datetime_empty_string():
    """Тест парсинга пустой строки."""
    result = parse_datetime("", user_timezone_offset=3)
    assert result is None, f"Expected None, got {result}"


if __name__ == "__main__":
    print("Запуск тестов...")
    
    test_parse_datetime_with_timezone()
    print("✅ test_parse_datetime_with_timezone")
    
    test_parse_datetime_without_timezone()
    print("✅ test_parse_datetime_without_timezone")
    
    test_parse_datetime_without_offset()
    print("✅ test_parse_datetime_without_offset")
    
    test_parse_datetime_negative_offset()
    print("✅ test_parse_datetime_negative_offset")
    
    test_parse_datetime_with_z_suffix()
    print("✅ test_parse_datetime_with_z_suffix")
    
    test_parse_datetime_none()
    print("✅ test_parse_datetime_none")
    
    test_parse_datetime_empty_string()
    print("✅ test_parse_datetime_empty_string")
    
    print("\n🎉 Все тесты пройдены успешно!")

