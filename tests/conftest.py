"""
Конфигурация pytest для всех тестов.
Настраивает окружение перед импортом модулей проекта.
"""

import os
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Настраиваем переменные окружения до импорта модулей
os.environ.setdefault("LOG_DIR", str(project_root / "logs"))
os.environ.setdefault("DATABASE_NAME", str(project_root / "data" / "users.db"))
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_token")
os.environ.setdefault("GOOGLE_OAUTH_CLIENT_ID", "test_client_id")
os.environ.setdefault("GOOGLE_OAUTH_CLIENT_SECRET", "test_client_secret")
os.environ.setdefault("OAUTH_REDIRECT_URI", "http://localhost:8080/oauth/callback")

# Убеждаемся что директория для логов существует
log_dir = Path(os.environ["LOG_DIR"])
log_dir.mkdir(parents=True, exist_ok=True)

