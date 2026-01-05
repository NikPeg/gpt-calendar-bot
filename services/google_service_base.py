"""
Абстрактный базовый класс для работы с Google APIs.
"""

from abc import ABC, abstractmethod

from googleapiclient.discovery import Resource


class GoogleServiceBase(ABC):
    """Абстрактный базовый класс для работы с Google API."""

    def __init__(self, service_name: str, version: str, scopes: list[str]):
        """
        Инициализирует базовый сервис.

        Args:
            service_name: Название сервиса (например, 'calendar', 'tasks')
            version: Версия API (например, 'v3', 'v1')
            scopes: Список необходимых scope для API
        """
        self.service_name = service_name
        self.version = version
        self.scopes = scopes
        self.service: Resource | None = None

    @abstractmethod
    def _build_service(self) -> Resource | None:
        """
        Создает Google API сервис с конкретной реализацией авторизации.

        Returns:
            Google API Resource или None при ошибке
        """

    def is_configured(self) -> bool:
        """Проверяет, настроен ли сервис."""
        return self.service is not None

    @staticmethod
    def _ensure_rfc3339_format(datetime_str: str) -> str:
        """
        Убеждается, что дата в формате RFC3339 с timezone для Google API.

        Args:
            datetime_str: Строка с датой в формате ISO 8601

        Returns:
            Строка в формате RFC3339
        """
        # Если уже есть Z или timezone, возвращаем как есть
        if "Z" in datetime_str or "+" in datetime_str or datetime_str.count("-") > 2:
            # Заменяем +00:00 на Z для UTC
            return datetime_str.replace("+00:00", "Z")
        # Если нет timezone, добавляем Z (предполагаем UTC)
        if "T" in datetime_str:
            return datetime_str + "Z"
        return datetime_str
