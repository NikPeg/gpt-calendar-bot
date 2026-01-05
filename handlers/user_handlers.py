"""
Обработчики пользовательских команд.
"""

import asyncio

from aiogram import F, types
from aiogram.filters.command import Command
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
)

from core.bot_instance import bot, dp
from core.config import ADMIN_CHAT, MESSAGES, REQUIRED_CHANNELS, logger
from core.database import Conversation, delete_chat_data
from core.filters import OldMessage, UserNotInDB
from core.utils import (
    forward_to_debug,
    keep_typing,
    send_message_with_fallback,
)
from handlers.subscription_handlers import send_subscription_request
from services.llm_service import (
    get_llm_response,
    save_to_context_and_format,
)


@dp.message(OldMessage())
async def spam(message: types.Message):
    """Игнорирует старые сообщения (старше 1 минуты)."""


@dp.message(F.new_chat_members)
async def bot_added_to_chat(message: types.Message):
    """Обработчик добавления бота в групповой чат."""
    # Проверяем, что бот был добавлен в чат
    bot_info = await bot.get_me()
    bot_added = any(member.id == bot_info.id for member in message.new_chat_members)

    if bot_added:
        chat_id = message.chat.id
        chat_title = message.chat.title or "этот чат"
        logger.info(f"CHAT{chat_id}: бот добавлен в чат '{chat_title}'")

        # Создаем запись чата в БД, чтобы обработчик registration не сработал
        chat_conversation = Conversation(chat_id, chat_title)
        await chat_conversation.save_for_db()
        logger.info(f"CHAT{chat_id}: запись создана в БД")

        # Отправляем приветственное сообщение
        welcome_text = MESSAGES["msg_bot_added_to_chat"].format(
            chat_title=chat_title, bot_username=bot_info.username
        )

        await message.answer(welcome_text)

        # Если есть обязательные каналы, отправляем запрос на подписку
        if REQUIRED_CHANNELS:
            logger.info(f"CHAT{chat_id}: bot_added_to_chat отправляет запрос подписки")
            await send_subscription_request(chat_id, message.message_id, is_chat=True)


@dp.message(F.left_chat_member)
async def bot_removed_from_chat(message: types.Message):
    """Обработчик удаления бота из группового чата."""
    # Проверяем, что бот был удален из чата
    bot_info = await bot.get_me()
    bot_removed = message.left_chat_member.id == bot_info.id

    if bot_removed:
        chat_id = message.chat.id
        chat_title = message.chat.title or "чат"
        logger.info(f"CHAT{chat_id}: бот удален из чата '{chat_title}'")

        # Удаляем все данные чата из БД
        try:
            await delete_chat_data(chat_id)
            logger.info(f"CHAT{chat_id}: все данные успешно удалены")
        except Exception as e:
            logger.error(
                f"CHAT{chat_id}: ошибка при удалении данных - {e}", exc_info=True
            )


@dp.message(UserNotInDB())
async def registration(message: types.Message):
    """Регистрация нового пользователя."""
    chat_id = message.chat.id
    logger.info(
        f"{'CHAT' if chat_id < 0 else 'USER'}{chat_id}: регистрация нового пользователя/чата"
    )

    # Извлекаем реферальный код только из команды /start
    referral_code = None
    if message.text and message.text.startswith("/start"):
        args = message.text.split()
        if len(args) > 1:
            referral_code = args[1]
            logger.info(
                f"{'CHAT' if chat_id < 0 else 'USER'}{chat_id}: переход по реф.ссылке, код: {referral_code}"
            )

    # Определяем имя в зависимости от типа чата
    if chat_id < 0:
        # Для групповых чатов используем название чата
        user_name = message.chat.title or ""
    else:
        # Для личных чатов используем имя пользователя
        user = message.from_user
        user_name = (
            user.first_name
            if user and user.first_name
            else (user.username if user and user.username else "")
        )

    conversation = Conversation(
        int(message.chat.id), user_name, referral_code=referral_code
    )
    await conversation.save_for_db()

    # Проверяем, настроен ли календарь (для новых пользователей всегда не настроен)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔐 Авторизоваться через Google",
                    callback_data="setup_calendar",
                )
            ],
        ]
    )
    sent_msg = await message.answer(
        MESSAGES["msg_start_not_configured"],
        reply_markup=keyboard,
    )

    # Если есть обязательные каналы, показываем сообщение о подписке
    if REQUIRED_CHANNELS and message.chat.id != ADMIN_CHAT:
        logger.info(
            f"{'CHAT' if chat_id < 0 else 'USER'}{chat_id}: регистрация отправляет запрос подписки"
        )
        await send_subscription_request(message.chat.id)

    # Не пересылаем сообщения из админ-чата в админ-чат
    if message.chat.id != ADMIN_CHAT:
        await forward_to_debug(message.chat.id, message.message_id)
        await forward_to_debug(message.chat.id, sent_msg.message_id)


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Команда /start - приветствие и настройка календаря."""
    user_id = message.chat.id

    # Получаем информацию о пользователе
    conversation = Conversation(user_id)
    await conversation.get_from_db()

    # Проверяем, настроен ли календарь (OAuth)
    if not conversation.oauth_access_token:
        # Календарь не настроен - показываем инструкцию по настройке
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔐 Авторизоваться через Google",
                        callback_data="setup_calendar",
                    )
                ],
            ]
        )
        sent_msg = await message.answer(
            MESSAGES["msg_start_not_configured"],
            reply_markup=keyboard,
        )
    else:
        # Календарь уже настроен - показываем приветствие для настроенного пользователя
        sent_msg = await message.answer(
            MESSAGES["msg_start_configured"],
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )

    # Проверяем статус подписки, если есть обязательные каналы
    if (
        REQUIRED_CHANNELS
        and user_id != ADMIN_CHAT
        and conversation.subscription_verified != 1
    ):
        # Если пользователь не подписан (0) или подписка не проверялась (None), показываем сообщение
        await send_subscription_request(user_id)

    # Не пересылаем сообщения из админ-чата в админ-чат
    if user_id != ADMIN_CHAT:
        await forward_to_debug(user_id, message.message_id)
        await forward_to_debug(user_id, sent_msg.message_id)


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Команда /help - справка (обычная или админская)."""
    # Проверяем, является ли пользователь администратором
    is_admin = message.chat.id == ADMIN_CHAT

    # Логируем вызов команды
    if is_admin:
        logger.info(f"Команда /help получена от администратора {message.chat.id}")
    else:
        logger.debug(f"Команда /help получена от пользователя {message.chat.id}")

    # Выбираем соответствующее сообщение
    help_message = MESSAGES["msg_help_admin"] if is_admin else MESSAGES["msg_help"]

    try:
        # Для админа отправляем без Markdown (только эмодзи и структурированный текст)
        if is_admin:
            sent_msg = await message.answer(
                help_message, reply_markup=ReplyKeyboardRemove()
            )
        else:
            # Для обычных пользователей используем Markdown
            sent_msg = await message.answer(
                help_message, reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown"
            )
        logger.info(
            f"Сообщение /help успешно отправлено пользователю {message.chat.id}"
        )
    except Exception as e:
        # Если не получилось, пробуем без форматирования
        logger.error(
            f"Ошибка при отправке /help для USER{message.chat.id}: {e}", exc_info=True
        )
        try:
            sent_msg = await message.answer(
                help_message, reply_markup=ReplyKeyboardRemove()
            )
            logger.info(
                f"Сообщение /help отправлено без форматирования пользователю {message.chat.id}"
            )
        except Exception as e2:
            logger.error(
                f"Критическая ошибка при отправке /help для USER{message.chat.id}: {e2}",
                exc_info=True,
            )
            return

    # Не пересылаем сообщения из админ-чата в админ-чат
    if not is_admin:
        await forward_to_debug(message.chat.id, message.message_id)
        await forward_to_debug(message.chat.id, sent_msg.message_id)


@dp.message(Command("forget"))
async def cmd_forget(message: types.Message):
    """
    Команда /forget - сброс контекста диалога.
    Сообщения сохраняются в БД для статистики, но не передаются в LLM.
    """
    sent_msg = await message.answer(
        MESSAGES["msg_forget"], reply_markup=ReplyKeyboardRemove()
    )
    conversation = Conversation(message.chat.id)
    await conversation.get_from_db()
    conversation.active_messages_count = 0  # Не передавать сообщения в контекст
    await conversation.update_in_db()

    # Не пересылаем сообщения из админ-чата в админ-чат
    if message.chat.id != ADMIN_CHAT:
        await forward_to_debug(message.chat.id, message.message_id)
        await forward_to_debug(message.chat.id, sent_msg.message_id)


@dp.message(Command("timezone"))
async def cmd_timezone(message: types.Message):
    """
    Команда /timezone - установка часового пояса пользователя.
    Использование: /timezone <offset>
    Например: /timezone 3 (для Москвы, UTC+3) или /timezone -5 (для Нью-Йорка, UTC-5)
    """
    user_id = message.chat.id
    conversation = Conversation(user_id)
    await conversation.get_from_db()

    # Получаем аргументы команды
    args = message.text.split() if message.text else []

    if len(args) < 2:
        # Показываем текущий часовой пояс и инструкцию
        current_offset = conversation.timezone_offset
        if current_offset is not None:
            offset_str = (
                f"+{current_offset}" if current_offset >= 0 else str(current_offset)
            )
            response = (
                f"🕐 Текущий часовой пояс: UTC{offset_str}\n\n"
                f"Чтобы изменить часовой пояс, используйте:\n"
                f"/timezone <смещение>\n\n"
                f"Примеры:\n"
                f"• /timezone 3 (Москва, UTC+3)\n"
                f"• /timezone -5 (Нью-Йорк, UTC-5)\n"
                f"• /timezone 0 (Лондон, UTC+0)\n"
                f"• /timezone 9 (Токио, UTC+9)"
            )
        else:
            from core.config import TIMEZONE_OFFSET

            default_offset = TIMEZONE_OFFSET
            offset_str = (
                f"+{default_offset}" if default_offset >= 0 else str(default_offset)
            )
            response = (
                f"🕐 Часовой пояс не установлен (используется значение по умолчанию: UTC{offset_str})\n\n"
                f"Чтобы установить свой часовой пояс, используйте:\n"
                f"/timezone <смещение>\n\n"
                f"Примеры:\n"
                f"• /timezone 3 (Москва, UTC+3)\n"
                f"• /timezone -5 (Нью-Йорк, UTC-5)\n"
                f"• /timezone 0 (Лондон, UTC+0)\n"
                f"• /timezone 9 (Токио, UTC+9)"
            )
        sent_msg = await message.answer(response, reply_markup=ReplyKeyboardRemove())
    else:
        # Пытаемся распарсить смещение
        try:
            offset = int(args[1])
            # Проверяем разумные пределы (от -12 до +14)
            if offset < -12 or offset > 14:
                sent_msg = await message.answer(
                    "❌ Неверное смещение. Используйте значение от -12 до +14.\n\n"
                    "Примеры:\n"
                    "• /timezone 3 (Москва, UTC+3)\n"
                    "• /timezone -5 (Нью-Йорк, UTC-5)",
                    reply_markup=ReplyKeyboardRemove(),
                )
            else:
                conversation.timezone_offset = offset
                await conversation.update_in_db()
                offset_str = f"+{offset}" if offset >= 0 else str(offset)
                sent_msg = await message.answer(
                    f"✅ Часовой пояс установлен: UTC{offset_str}",
                    reply_markup=ReplyKeyboardRemove(),
                )
                logger.info(f"USER{user_id}: timezone_offset установлен на {offset}")
        except ValueError:
                sent_msg = await message.answer(
                    "❌ Неверный формат. Используйте число.\n\n"
                    "Примеры:\n"
                    "• /timezone 3 (Москва, UTC+3)\n"
                    "• /timezone -5 (Нью-Йорк, UTC-5)",
                    reply_markup=ReplyKeyboardRemove(),
                )

    # Не пересылаем сообщения из админ-чата в админ-чат
    if user_id != ADMIN_CHAT:
        await forward_to_debug(user_id, message.message_id)
        await forward_to_debug(user_id, sent_msg.message_id)


@dp.message(Command("today"))
async def cmd_today(message: types.Message):
    """
    Команда /today - показать события и задачи на сегодня.
    """
    user_id = message.chat.id
    
    # Игнорируем сообщения из ADMIN_CHAT
    if user_id == ADMIN_CHAT:
        return
    
    logger.info(f"USER{user_id}: команда /today")
    await forward_to_debug(user_id, message.message_id)
    
    # Запускаем индикатор печати
    typing_task = asyncio.create_task(keep_typing(user_id))
    
    try:
        # Формируем запрос к LLM
        query = "перечисли мои события и задачи на сегодня"
        
        # Получаем ответ от LLM
        llm_response, conversation = await get_llm_response(user_id, query)
        
        if llm_response is None:
            await message.answer(
                "Прости, произошла ошибка при получении информации о событиях и задачах на сегодня. "
                "Пожалуйста, попробуй снова."
            )
            return
        
        # Сохраняем в контекст и форматируем
        converted_response = await save_to_context_and_format(
            user_id, conversation, query, llm_response
        )
        
        # Отправляем ответ пользователю (с разбивкой на части если нужно)
        start = 0
        while start < len(converted_response):
            chunk = converted_response[start : start + 4096]
            try:
                sent_msg = await send_message_with_fallback(
                    chat_id=user_id,
                    text=chunk,
                )
                await forward_to_debug(user_id, sent_msg.message_id)
            except Exception as e:
                logger.error(
                    f"USER{user_id}: ошибка при отправке ответа на /today: {e}",
                    exc_info=True,
                )
                break
            
            start += 4096
        
        logger.info(f"LLM{user_id} - ответ на /today отправлен")
    
    finally:
        typing_task.cancel()


@dp.message(Command("tomorrow"))
async def cmd_tomorrow(message: types.Message):
    """
    Команда /tomorrow - показать события и задачи на завтра.
    """
    user_id = message.chat.id
    
    # Игнорируем сообщения из ADMIN_CHAT
    if user_id == ADMIN_CHAT:
        return
    
    logger.info(f"USER{user_id}: команда /tomorrow")
    await forward_to_debug(user_id, message.message_id)
    
    # Запускаем индикатор печати
    typing_task = asyncio.create_task(keep_typing(user_id))
    
    try:
        # Формируем запрос к LLM
        query = "перечисли мои события и задачи на завтра"
        
        # Получаем ответ от LLM
        llm_response, conversation = await get_llm_response(user_id, query)
        
        if llm_response is None:
            await message.answer(
                "Прости, произошла ошибка при получении информации о событиях и задачах на завтра. "
                "Пожалуйста, попробуй снова."
            )
            return
        
        # Сохраняем в контекст и форматируем
        converted_response = await save_to_context_and_format(
            user_id, conversation, query, llm_response
        )
        
        # Отправляем ответ пользователю (с разбивкой на части если нужно)
        start = 0
        while start < len(converted_response):
            chunk = converted_response[start : start + 4096]
            try:
                sent_msg = await send_message_with_fallback(
                    chat_id=user_id,
                    text=chunk,
                )
                await forward_to_debug(user_id, sent_msg.message_id)
            except Exception as e:
                logger.error(
                    f"USER{user_id}: ошибка при отправке ответа на /tomorrow: {e}",
                    exc_info=True,
                )
                break
            
            start += 4096
        
        logger.info(f"LLM{user_id} - ответ на /tomorrow отправлен")
    
    finally:
        typing_task.cancel()


@dp.message(Command("week"))
async def cmd_week(message: types.Message):
    """
    Команда /week - показать события и задачи на эту неделю.
    """
    user_id = message.chat.id
    
    # Игнорируем сообщения из ADMIN_CHAT
    if user_id == ADMIN_CHAT:
        return
    
    logger.info(f"USER{user_id}: команда /week")
    await forward_to_debug(user_id, message.message_id)
    
    # Запускаем индикатор печати
    typing_task = asyncio.create_task(keep_typing(user_id))
    
    try:
        # Формируем запрос к LLM
        query = "перечисли мои события и задачи на этой неделе"
        
        # Получаем ответ от LLM
        llm_response, conversation = await get_llm_response(user_id, query)
        
        if llm_response is None:
            await message.answer(
                "Прости, произошла ошибка при получении информации о событиях и задачах на эту неделю. "
                "Пожалуйста, попробуй снова."
            )
            return
        
        # Сохраняем в контекст и форматируем
        converted_response = await save_to_context_and_format(
            user_id, conversation, query, llm_response
        )
        
        # Отправляем ответ пользователю (с разбивкой на части если нужно)
        start = 0
        while start < len(converted_response):
            chunk = converted_response[start : start + 4096]
            try:
                sent_msg = await send_message_with_fallback(
                    chat_id=user_id,
                    text=chunk,
                )
                await forward_to_debug(user_id, sent_msg.message_id)
            except Exception as e:
                logger.error(
                    f"USER{user_id}: ошибка при отправке ответа на /week: {e}",
                    exc_info=True,
                )
                break
            
            start += 4096
        
        logger.info(f"LLM{user_id} - ответ на /week отправлен")
    
    finally:
        typing_task.cancel()
