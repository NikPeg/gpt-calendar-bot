"""
Главный файл приложения - точка входа для запуска бота.
"""

# ruff: noqa: I001 - порядок импортов handlers критичен для работы бота
import asyncio
import contextlib

from aiogram.types import BotCommand

import core.database as database
from core.bot_instance import bot, dp
from core.config import ADMIN_CHAT, add_telegram_handler, logger
from core.middlewares import SubscriptionMiddleware
from migrations.migration_manager import run_migrations
from oauth_server import start_oauth_server
from services.subscription_service import subscription_check_loop

# Импортируем все обработчики (чтобы они зарегистрировались)
# ВАЖНО: порядок имеет значение! Сначала специфичные (команды), потом общие
# isort: off - не сортировать этот блок, порядок критичен!
from handlers import user_handlers  # noqa: F401
from handlers import subscription_handlers  # noqa: F401
from handlers import admin_handlers  # noqa: F401
from handlers import setup_handlers  # noqa: F401
from handlers import message_handlers  # noqa: F401
# isort: on


async def set_bot_commands():
    """Устанавливает список команд бота в меню Telegram."""
    commands = [
        BotCommand(command="start", description="🚀 Информация о боте"),
        BotCommand(command="help", description="💡 Справка по командам"),
        BotCommand(
            command="forget",
            description="🔄 Сбросить историю диалога и начать общение с чистого листа",
        ),
        BotCommand(
            command="today",
            description="📅 Показать события и задачи на сегодня",
        ),
        BotCommand(
            command="tomorrow",
            description="📅 Показать события и задачи на завтра",
        ),
        BotCommand(
            command="week",
            description="📅 Показать события и задачи на эту неделю",
        ),
    ]

    await bot.set_my_commands(commands)
    logger.info("Команды бота установлены в меню Telegram")


async def main():
    """Главная функция запуска бота."""
    # Инициализация базы данных
    db_status = await database.check_db()

    # Применяем миграции
    await run_migrations()

    # Устанавливаем команды бота в меню Telegram
    await set_bot_commands()

    # Добавляем middleware для проверки подписки
    dp.message.middleware(SubscriptionMiddleware())

    # Добавляем Telegram handler после инициализации бота
    add_telegram_handler(logger, bot)

    # Простые сообщения для docker logs (в консоль)
    print("=" * 50)
    print("🤖 БОТ ЗАПУЩЕН")
    print("=" * 50)
    print(f"Database: {db_status}")
    print(f"Admin chat: {ADMIN_CHAT}")
    print("Нажмите Ctrl-C для остановки бота")
    print("=" * 50 + "\n")

    # Создаем задачу для проверки подписок
    subscription_task = asyncio.create_task(subscription_check_loop(bot))

    # Запускаем OAuth сервер в фоне
    oauth_task = asyncio.create_task(start_oauth_server())

    try:
        # Запускаем polling - он сам обрабатывает сигналы
        await dp.start_polling(bot)
    except (KeyboardInterrupt, SystemExit):
        print("\n🛑 Получен сигнал остановки")
    except Exception as e:
        logger.critical(f"CRITICAL_ERROR: {e}", exc_info=True)
        raise  # Пробрасываем ошибку дальше для перезапуска Docker'ом
    finally:
        print("Останавливаем бота...")

        # Отменяем фоновые задачи
        subscription_task.cancel()
        oauth_task.cancel()

        # Дожидаемся их завершения
        with contextlib.suppress(asyncio.CancelledError):
            await subscription_task
            await oauth_task

        # Закрываем сессию бота
        await bot.session.close()

        # Принудительно завершаем все оставшиеся asyncio задачи
        pending = [
            task for task in asyncio.all_tasks() if task is not asyncio.current_task()
        ]
        if pending:
            print(f"Отменяем {len(pending)} оставшихся задач...")
            for task in pending:
                task.cancel()
            # Ждем завершения с подавлением ошибок отмены
            await asyncio.gather(*pending, return_exceptions=True)

        print("✅ Бот остановлен")


if __name__ == "__main__":
    try:
        # Убрали run_with_restart() - перезапуск теперь на уровне Docker
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("👋 Программа завершена")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        # При любой ошибке контейнер завершается с кодом 1,
        # и Docker перезапустит его благодаря restart: unless-stopped
        exit(1)
