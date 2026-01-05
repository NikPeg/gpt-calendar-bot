"""
Сервис для работы с Google APIs через OAuth 2.0.
"""

from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import Resource, build

from core.config import logger
from services.google_service_base import GoogleServiceBase


class GoogleServiceOAuth(GoogleServiceBase):
    """Сервис для работы с Google API через OAuth 2.0."""

    def __init__(
        self,
        service_name: str,
        version: str,
        scopes: list[str],
        access_token: str | None = None,
        refresh_token: str | None = None,
        token_expiry: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
    ):
        """
        Инициализирует сервис с OAuth 2.0 токенами.

        Args:
            service_name: Название сервиса
            version: Версия API
            scopes: Список scope
            access_token: Токен доступа
            refresh_token: Токен для обновления
            token_expiry: Время истечения токена (ISO format)
            client_id: OAuth Client ID
            client_secret: OAuth Client Secret
        """
        super().__init__(service_name, version, scopes)
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_expiry = token_expiry
        self.client_id = client_id
        self.client_secret = client_secret
        self.credentials: Credentials | None = None
        
        self.service = self._build_service()

    def _build_service(self) -> Resource | None:
        """Создает Google API сервис с OAuth credentials."""
        if not self.access_token or not self.refresh_token:
            logger.warning(f"Missing OAuth tokens for {self.service_name} service")
            return None

        if not self.client_id or not self.client_secret:
            logger.warning(f"Missing OAuth client credentials for {self.service_name}")
            return None

        try:
            # Парсим expiry если есть
            expiry = None
            if self.token_expiry:
                try:
                    expiry = datetime.fromisoformat(self.token_expiry.replace("Z", "+00:00"))
                except Exception as e:
                    logger.warning(f"Could not parse token_expiry: {e}")

            # Создаем credentials
            self.credentials = Credentials(
                token=self.access_token,
                refresh_token=self.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.client_id,
                client_secret=self.client_secret,
                scopes=self.scopes,
                expiry=expiry,
            )

            # Проверяем и обновляем токен если нужно
            if self.credentials.expired and self.credentials.refresh_token:
                logger.info(f"Refreshing expired OAuth token for {self.service_name}")
                self.credentials.refresh(Request())
                # Обновляем access_token для сохранения в БД
                self.access_token = self.credentials.token
                if self.credentials.expiry:
                    self.token_expiry = self.credentials.expiry.isoformat()

            # Создаем сервис
            service = build(self.service_name, self.version, credentials=self.credentials)
            logger.debug(f"Google {self.service_name.title()} OAuth service initialized successfully")
            return service
        except Exception as e:
            logger.error(f"Error initializing Google {self.service_name.title()} OAuth service: {e}")
            return None

    def get_updated_tokens(self) -> dict[str, str | None]:
        """
        Получает обновленные токены (если были обновлены).
        
        Returns:
            dict с access_token, refresh_token, token_expiry
        """
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_expiry": self.token_expiry,
        }

    @staticmethod
    def create_authorization_url(
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scopes: list[str],
        state: str | None = None,
    ) -> tuple[str, str]:
        """
        Создает URL для авторизации пользователя.

        Args:
            client_id: OAuth Client ID
            client_secret: OAuth Client Secret
            redirect_uri: URI для callback
            scopes: Список scope
            state: CSRF state token (опционально)

        Returns:
            Tuple (authorization_url, state)
        """
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri],
                }
            },
            scopes=scopes,
            redirect_uri=redirect_uri,
        )

        authorization_url, state = flow.authorization_url(
            access_type="offline",  # Для получения refresh token
            include_granted_scopes="true",
            prompt="consent",  # Принудительный consent для refresh token
            state=state,
        )

        return authorization_url, state

    @staticmethod
    def exchange_code_for_tokens(
        code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scopes: list[str],
    ) -> dict[str, str]:
        """
        Обменивает authorization code на токены.

        Args:
            code: Authorization code от Google
            client_id: OAuth Client ID
            client_secret: OAuth Client Secret
            redirect_uri: URI для callback
            scopes: Список scope

        Returns:
            dict с access_token, refresh_token, token_expiry
        """
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri],
                }
            },
            scopes=scopes,
            redirect_uri=redirect_uri,
        )

        flow.fetch_token(code=code)
        credentials = flow.credentials

        return {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_expiry": credentials.expiry.isoformat() if credentials.expiry else None,
        }

