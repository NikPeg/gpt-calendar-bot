"""
Сервис для автоматической ежедневной рассылки событий и задач.

Отправляет пользователям сводку событий и задач на день в указанное время
с учетом их часового пояса.
"""

import asyncio
import contextlib

from aiogram.exceptions import TelegramForbiddenError

from core.bot_instance import bot
from core.config import ADMIN_CHAT, logger
from core.database import Conversation
from core.utils import keep_typing
from services.llm_service import get_llm_response


async def send_daily_digest_to_user(user_id: int) -> tuple[bool, str]:
    """
    Отправляет ежедневную сводку одному пользователю.

    Args:
        user_id: ID пользователя

    Returns:
        Tuple (успех, сообщение об ошибке если есть)
    """
    try:
        # Получаем данные пользователя
        conversation = Conversation(user_id)
        await conversation.get_from_db()

        # Проверяем, что у пользователя настроен OAuth
        if not conversation.oauth_access_token:
            logger.debug(f"USER{user_id}: пропущен (нет OAuth токена)")
            return False, "no_oauth"

        # Проверяем, что рассылка включена
        if conversation.daily_digest_enabled == 0:
            logger.debug(f"USER{user_id}: рассылка отключена")
            return False, "disabled"

        # Запускаем индикатор печати
        typing_task = asyncio.create_task(keep_typing(user_id))

        try:
            # Формируем запрос к LLM
            query = "перечисли мои события и задачи на сегодня"

            # Получаем ответ от LLM (не сохраняем в историю!)
            llm_response, _ = await get_llm_response(user_id, query)

            if not llm_response:
                logger.warning(f"USER{user_id}: LLM вернул пустой ответ")
                return False, "empty_response"

            # Форматируем ответ с приветствием
            user_name = conversation.name or "друг"
            message_text = (
                f"🌅 Доброе утро, {user_name}!\n\n"
                f"Вот твои события и задачи на сегодня:\n\n{llm_response}"
            )

            # Отправляем сообщение (с разбивкой на части если нужно)
            start = 0
            while start < len(message_text):
                chunk = message_text[start : start + 4096]
                try:
                    await bot.send_message(
                        user_id,
                        chunk,
                        parse_mode="Markdown",
                        disable_web_page_preview=True,
                    )
                except Exception:
                    # Если Markdown не работает, пробуем без форматирования
                    logger.warning(
                        f"USER{user_id}: ошибка отправки с Markdown, пробуем без форматирования"
                    )
                    await bot.send_message(
                        user_id, chunk, disable_web_page_preview=True
                    )

                start += 4096

            logger.info(f"USER{user_id}: ежедневная сводка отправлена успешно")
            return True, None

        finally:
            typing_task.cancel()

    except TelegramForbiddenError:
        # Пользователь заблокировал бота - удаляем из БД
        logger.info(f"USER{user_id}: заблокировал бота, удаляем из БД")
        conversation = Conversation(user_id)
        await conversation.delete_from_db()
        return False, "blocked"

    except Exception as e:
        logger.error(
            f"USER{user_id}: ошибка при отправке ежедневной сводки: {e}", exc_info=True
        )
        return False, str(e)


async def send_daily_digest_to_all():
    """
    Проверяет всех пользователей и отправляет ежедневную сводку тем,
    у кого наступило время для получения (с учетом часового пояса).

    Эта функция должна вызываться каждый час планировщиком.
    """
    try:
        from datetime import UTC, datetime

        current_utc = datetime.now(UTC)
        current_utc_hour = current_utc.hour

        logger.info(f"🕐 Проверка ежедневных рассылок для UTC час: {current_utc_hour}")

        # Получаем всех пользователей
        all_ids = await Conversation.get_ids_from_table()
        # Фильтруем только личных пользователей (положительные ID)
        user_ids = [uid for uid in all_ids if uid > 0]

        success_count = 0
        skipped_no_oauth = 0
        skipped_disabled = 0
        skipped_wrong_time = 0
        blocked_count = 0
        error_count = 0

        for user_id in user_ids:
            try:
                # Получаем данные пользователя
                conversation = Conversation(user_id)
                await conversation.get_from_db()

                # Проверяем, что рассылка включена
                if conversation.daily_digest_enabled == 0:
                    skipped_disabled += 1
                    continue

                # Проверяем наличие OAuth токена
                if not conversation.oauth_access_token:
                    skipped_no_oauth += 1
                    continue

                # Вычисляем локальное время пользователя
                user_offset = conversation.timezone_offset or 0
                user_local_hour = (current_utc_hour + user_offset) % 24

                # Получаем настроенный час отправки (по умолчанию 9)
                target_hour = (
                    conversation.daily_digest_hour
                    if conversation.daily_digest_hour is not None
                    else 9
                )

                # Проверяем, пришло ли время отправки для этого пользователя
                if user_local_hour != target_hour:
                    skipped_wrong_time += 1
                    logger.debug(
                        f"USER{user_id}: локальное время {user_local_hour}:xx, "
                        f"целевое {target_hour}:00, пропускаем"
                    )
                    continue

                logger.info(
                    f"USER{user_id}: локальное время {user_local_hour}:xx = целевое {target_hour}:00, отправляем"
                )

                # Отправляем сводку
                success, error_msg = await send_daily_digest_to_user(user_id)

                if success:
                    success_count += 1
                else:
                    if error_msg == "blocked":
                        blocked_count += 1
                    elif error_msg == "no_oauth":
                        skipped_no_oauth += 1
                    elif error_msg == "disabled":
                        skipped_disabled += 1
                    else:
                        error_count += 1

                # Небольшая задержка между отправками (чтобы не спамить API)
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(
                    f"USER{user_id}: неожиданная ошибка при обработке: {e}",
                    exc_info=True,
                )
                error_count += 1
                continue

        # Формируем отчет
        result_msg = (
            f"📊 Проверка ежедневных рассылок завершена (UTC час {current_utc_hour}):\n"
            f"✅ Отправлено успешно: {success_count}\n"
            f"⏰ Пропущено (не время): {skipped_wrong_time}\n"
            f"🔒 Пропущено (нет OAuth): {skipped_no_oauth}\n"
            f"🔕 Пропущено (отключено): {skipped_disabled}\n"
            f"🚫 Заблокировали бота: {blocked_count}\n"
            f"❌ Ошибки: {error_count}\n"
            f"📋 Всего пользователей: {len(user_ids)}"
        )

        logger.info(result_msg)

        # Отправляем отчет админу только если были отправки или ошибки
        if success_count > 0 or blocked_count > 0 or error_count > 0:
            try:
                await bot.send_message(ADMIN_CHAT, result_msg)
            except Exception as e:
                logger.warning(f"Не удалось отправить отчет в ADMIN_CHAT: {e}")

    except Exception as e:
        error_msg = f"❌ Критическая ошибка в send_daily_digest_to_all: {e}"
        logger.error(error_msg, exc_info=True)
        with contextlib.suppress(Exception):
            await bot.send_message(ADMIN_CHAT, error_msg)
