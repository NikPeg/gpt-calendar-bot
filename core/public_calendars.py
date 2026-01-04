"""
Константы для публичных календарей.

Этот модуль содержит определения популярных публичных календарей,
которые могут быть добавлены пользователям для отображения праздников,
спортивных событий и других общественных мероприятий.
"""

from dataclasses import dataclass


@dataclass
class PublicCalendar:
    """
    Описание публичного календаря.

    Attributes:
        calendar_id: ID календаря в Google Calendar
        name: Отображаемое название
        description: Описание календаря
        locale: Локаль календаря (ru, en и т.д.)
    """

    calendar_id: str
    name: str
    description: str
    locale: str = "ru"


# Публичные календари России
RUSSIAN_HOLIDAYS = PublicCalendar(
    calendar_id="ru.russian#holiday@group.v.calendar.google.com",
    name="Праздники России",
    description="Официальные праздники и выходные дни Российской Федерации",
    locale="ru",
)

# Словарь всех доступных публичных календарей
PUBLIC_CALENDARS = {
    "ru_holidays": RUSSIAN_HOLIDAYS,
    # Здесь можно добавлять новые публичные календари:
    # "ru_orthodox": PublicCalendar(...),
    # "ru_sports": PublicCalendar(...),
}


def get_public_calendar(key: str) -> PublicCalendar | None:
    """
    Получает публичный календарь по ключу.

    Args:
        key: Ключ календаря (например, "ru_holidays")

    Returns:
        Объект PublicCalendar или None, если не найден
    """
    return PUBLIC_CALENDARS.get(key)


def list_public_calendars() -> list[tuple[str, PublicCalendar]]:
    """
    Возвращает список всех доступных публичных календарей.

    Returns:
        Список кортежей (ключ, PublicCalendar)
    """
    return list(PUBLIC_CALENDARS.items())

