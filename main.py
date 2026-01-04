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

    try:
        # Запускаем polling - он сам обрабатывает сигналы
        await dp.start_polling(bot)
    except (KeyboardInterrupt, SystemExit):
        print("\n🛑 Получен сигнал остановки")
    except Exception as e:
        logger.critical(f"CRITICAL_ERROR: {e}", exc_info=True)
    finally:
        print("Останавливаем бота...")
        subscription_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await subscription_task
        await bot.session.close()
        print("✅ Бот остановлен")


async def run_with_restart():
    """Запуск с автоматическим перезапуском при ошибках."""
    while True:
        try:
            await main()
            break  # Нормальное завершение - выходим из цикла
        except (KeyboardInterrupt, SystemExit):
            print("👋 Завершение работы")
            break
        except Exception as e:
            print(f"main() завершился с ошибкой: {e}. Перезапуск через 5 секунд...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(run_with_restart())
    except (KeyboardInterrupt, SystemExit):
        print("👋 Программа завершена")
