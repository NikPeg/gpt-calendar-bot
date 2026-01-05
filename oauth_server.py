"""
Web-сервер для обработки OAuth 2.0 callback от Google.
Запускается параллельно с основным ботом.
"""

import asyncio
import os

from aiohttp import web
from dotenv import load_dotenv

from core.bot_instance import bot
from core.config import logger
from core.database import Conversation
from services.google_service_oauth import GoogleServiceOAuth

load_dotenv()

# OAuth конфигурация
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI")
OAUTH_SERVER_PORT = int(os.environ.get("OAUTH_SERVER_PORT", "8080"))

# Scope для Calendar и Tasks
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
]

# Хранилище для state токенов (в продакшене использовать Redis)
pending_states = {}


async def oauth_callback(request: web.Request) -> web.Response:
    """Обработчик OAuth callback от Google."""
    logger.info(f"OAuth callback received: {request.url}")
    print(f"🔵 OAuth callback received: {request.url}")

    code = request.query.get("code")
    state = request.query.get("state")
    error = request.query.get("error")

    if error:
        logger.error(f"OAuth error: {error}")
        return web.Response(
            text="❌ Ошибка авторизации. Вы можете закрыть это окно и вернуться в Telegram.",
            content_type="text/html",
            charset="utf-8",
            status=400,
        )

    if not code or not state:
        return web.Response(
            text="❌ Неверные параметры. Вы можете закрыть это окно.",
            content_type="text/html",
            charset="utf-8",
            status=400,
        )

    # Проверяем state
    user_id = pending_states.pop(state, None)
    if not user_id:
        logger.warning(f"Invalid or expired state: {state}")
        return web.Response(
            text="❌ Неверный или истекший state token. Попробуйте снова.",
            content_type="text/html",
            charset="utf-8",
            status=400,
        )

    try:
        # Обмениваем code на токены
        # Используем to_thread для синхронного HTTP запроса
        tokens = await asyncio.to_thread(
            GoogleServiceOAuth.exchange_code_for_tokens,
            code=code,
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
            redirect_uri=GOOGLE_REDIRECT_URI,
            scopes=SCOPES,
        )

        # Сохраняем токены в БД
        conversation = Conversation(user_id)
        await conversation.get_from_db()

        conversation.oauth_access_token = tokens["access_token"]
        conversation.oauth_refresh_token = tokens["refresh_token"]
        conversation.oauth_token_expiry = tokens["token_expiry"]

        await conversation.update_in_db()

        logger.info(f"OAuth successful for user {user_id}")

        # Отправляем уведомление в Telegram в фоновой задаче
        async def send_notification():
            try:
                await bot.send_message(
                    user_id,
                    "✅ Google Calendar и Tasks успешно подключены!\n\n"
                    "Теперь я могу:\n"
                    "• Создавать события в вашем календаре\n"
                    "• Создавать задачи в Google Tasks\n"
                    "• Показывать ваши события и задачи\n\n"
                    "Попробуйте спросить: 'Покажи мои события на неделю' или 'Создай задачу купить молоко'",
                )
            except Exception as e:
                logger.error(f"Failed to send notification to user {user_id}: {e}")

        # Запускаем в фоне, не дожидаясь завершения
        asyncio.create_task(send_notification())

        return web.Response(
            text="""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Авторизация успешна</title>
                <style>
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    }
                    .container {
                        text-align: center;
                        background: white;
                        padding: 40px;
                        border-radius: 10px;
                        box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                    }
                    h1 { color: #4CAF50; margin-bottom: 20px; }
                    p { color: #666; line-height: 1.6; }
                    .emoji { font-size: 64px; margin-bottom: 20px; }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="emoji">✅</div>
                    <h1>Авторизация успешна!</h1>
                    <p>Вы можете закрыть это окно и вернуться в Telegram.</p>
                    <p>Проверьте сообщение от бота.</p>
                </div>
            </body>
            </html>
            """,
            content_type="text/html",
            charset="utf-8",
        )

    except Exception as e:
        logger.error(f"Error processing OAuth callback: {e}", exc_info=True)
        return web.Response(
            text=f"❌ Ошибка при обработке авторизации: {str(e)}",
            content_type="text/html",
            charset="utf-8",
            status=500,
        )


async def health_check(request: web.Request) -> web.Response:
    """Health check endpoint."""
    return web.json_response({"status": "ok", "service": "oauth-server"})


async def test_endpoint(request: web.Request) -> web.Response:
    """Тестовый endpoint для проверки работы сервера."""
    logger.info("Test endpoint called")
    print("🔵 Test endpoint called")
    return web.Response(text="OAuth server is working!", content_type="text/plain")


def create_app() -> web.Application:
    """Создает aiohttp приложение."""
    app = web.Application()
    app.router.add_get("/oauth/callback", oauth_callback)
    app.router.add_get("/health", health_check)
    app.router.add_get("/test", test_endpoint)
    app.router.add_get("/", test_endpoint)  # Для корня тоже
    return app


async def start_oauth_server():
    """Запускает OAuth сервер."""
    # Проверяем OAuth credentials
    oauth_enabled = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI)
    
    if not oauth_enabled:
        if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
            logger.warning(
                "OAuth credentials not configured. "
                "Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET in .env"
            )
            print("⚠️  OAuth credentials not configured")
        
        if not GOOGLE_REDIRECT_URI:
            logger.warning(
                "GOOGLE_OAUTH_REDIRECT_URI not configured. "
                "Set GOOGLE_OAUTH_REDIRECT_URI in .env"
            )
            print("⚠️  OAuth redirect URI not configured")
        
        print(f"ℹ️  OAuth server starting in health-check-only mode on port {OAUTH_SERVER_PORT}")
        logger.info("OAuth server starting in health-check-only mode")

    # Всегда запускаем сервер (для healthcheck)
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", OAUTH_SERVER_PORT)
    await site.start()

    if oauth_enabled:
        logger.info(f"OAuth server started on http://0.0.0.0:{OAUTH_SERVER_PORT}")
        logger.info(f"Callback URL: {GOOGLE_REDIRECT_URI}")
        # Логируем в консоль для Docker logs
        print(f"✅ OAuth server started on http://0.0.0.0:{OAUTH_SERVER_PORT}")
        print(f"📋 Callback URL: {GOOGLE_REDIRECT_URI}")
    else:
        logger.info(f"Health-check server started on http://0.0.0.0:{OAUTH_SERVER_PORT}")
        print(f"✅ Health-check server started on http://0.0.0.0:{OAUTH_SERVER_PORT}")

    # Держим сервер запущенным
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        logger.info("OAuth server stopping...")
        await runner.cleanup()
        raise


if __name__ == "__main__":
    # Запуск standalone сервера для разработки
    async def main():
        await start_oauth_server()
        # Держим сервер запущенным
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("OAuth server stopped")

    asyncio.run(main())
