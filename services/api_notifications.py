"""
Модуль для отправки уведомлений о вызовах Google API пользователю.
Помогает отличить реальные вызовы API от галлюцинаций LLM.
"""

import asyncio
from typing import Any

from core.config import logger

# Глобальное хранилище для bot instance (будет установлено при инициализации)
_bot_instance = None


def set_bot_instance(bot):
    """
    Устанавливает bot instance для отправки уведомлений.

    Args:
        bot: Instance aiogram.Bot
    """
    global _bot_instance
    _bot_instance = bot
    logger.debug("Bot instance установлен для API notifications")


async def notify_api_call(
    chat_id: int,
    operation: str,
    details: str | None = None,
    error: bool = False,
) -> None:
    """
    Отправляет уведомление пользователю о вызове Google API.

    Args:
        chat_id: ID чата пользователя
        operation: Название операции (например, "создание события")
        details: Дополнительные детали (например, название события, ID)
        error: True если произошла ошибка
    """
    if _bot_instance is None:
        logger.warning("Bot instance не установлен для API notifications")
        return

    # Формируем иконку в зависимости от типа операции
    icon = "❌" if error else "🔧"

    # Формируем текст уведомления
    if error:
        message = f"{icon} API ERROR: {operation}"
    else:
        message = f"{icon} API CALL: {operation}"

    if details:
        message += f"\n{details}"

    try:
        # Отправляем сообщение в неблокирующем режиме
        # Используем asyncio.create_task чтобы не блокировать выполнение
        asyncio.create_task(
            _bot_instance.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=None,  # Отключаем парсинг чтобы избежать проблем с форматированием
            )
        )
        logger.debug(f"API_NOTIFY{chat_id}: {message}")
    except Exception as e:
        logger.error(f"Error sending API notification to {chat_id}: {e}")


def format_event_details(event_data: dict[str, Any] | None) -> str:
    """
    Форматирует детали события для отображения.

    Args:
        event_data: Данные события

    Returns:
        Отформатированная строка с деталями
    """
    if not event_data:
        return ""

    parts = []

    summary = event_data.get("summary")
    if summary:
        parts.append(f"Название: {summary}")

    event_id = event_data.get("id")
    if event_id:
        parts.append(f"ID: {event_id[:15]}...")  # Обрезаем длинный ID

    start = event_data.get("start", {}).get("dateTime") or event_data.get("start", {}).get("date")
    if start:
        parts.append(f"Время: {start[:16]}")  # YYYY-MM-DDTHH:MM

    return "\n".join(parts) if parts else ""


def format_task_details(task_data: dict[str, Any] | None) -> str:
    """
    Форматирует детали задачи для отображения.

    Args:
        task_data: Данные задачи

    Returns:
        Отформатированная строка с деталями
    """
    if not task_data:
        return ""

    parts = []

    title = task_data.get("title")
    if title:
        parts.append(f"Название: {title}")

    task_id = task_data.get("id")
    if task_id:
        parts.append(f"ID: {task_id[:15]}...")  # Обрезаем длинный ID

    status = task_data.get("status")
    if status:
        status_text = "✅ Выполнена" if status == "completed" else "⏳ Активна"
        parts.append(f"Статус: {status_text}")

    return "\n".join(parts) if parts else ""

