"""
Базовый класс для работы с Google API через Service Account (устаревший, для обратной совместимости).
Используйте GoogleServiceOAuth для новых реализаций.
"""

import json

from google.oauth2 import service_account
from googleapiclient.discovery import Resource, build

from core.config import logger
from services.google_service_base import GoogleServiceBase


class GoogleService(GoogleServiceBase):
    """Базовый класс для работы с Google API через сервисный аккаунт (deprecated)."""

    def __init__(self, service_account_json: str | None, service_name: str, version: str, scopes: list[str]):
        """
        Инициализирует Google API сервис.

        Args:
            service_account_json: JSON строка с данными сервисного аккаунта
            service_name: Название сервиса (например, 'calendar', 'tasks')
            version: Версия API (например, 'v3', 'v1')
            scopes: Список необходимых scope для API
        """
        super().__init__(service_name, version, scopes)
        self.service_account_json = service_account_json
        self.service = self._build_service()

    def _build_service(self) -> Resource | None:
        """Создает Google API сервис с Service Account."""
        if not self.service_account_json:
            return None

        try:
            # Парсим JSON
            credentials_info = json.loads(self.service_account_json)

            # Создаем credentials из сервисного аккаунта
            credentials = service_account.Credentials.from_service_account_info(
                credentials_info,
                scopes=self.scopes,
            )

            # Создаем сервис
            service = build(self.service_name, self.version, credentials=credentials)
            logger.debug(f"Google {self.service_name.title()} service initialized successfully")
            return service
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in service_account_json: {e}")
            return None
        except Exception as e:
            logger.error(f"Error initializing Google {self.service_name.title()} service: {e}")
            return None

