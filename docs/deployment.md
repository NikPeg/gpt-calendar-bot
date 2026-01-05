# 🚀 Руководство по развертыванию Telegram GPT Bot

Два простых способа запуска бота: локально или в Docker Compose.

## 📋 Содержание

- [Предварительные требования](#предварительные-требования)
- [Метод 1: Локальный запуск (Python)](#метод-1-локальный-запуск-python)
- [Метод 2: Docker Compose (рекомендуется)](#метод-2-docker-compose-рекомендуется)
- [Настройка переменных окружения](#настройка-переменных-окружения)
- [Управление ботом](#управление-ботом)
- [Решение проблем](#решение-проблем)
- [Автоматический деплой](#автоматический-деплой)

---

## Предварительные требования

### Обязательно:
- Токен Telegram бота от [@BotFather](https://t.me/BotFather)
- API ключ от [OpenRouter](https://openrouter.ai/)
- Ваш Telegram chat ID (получите через [@userinfobot](https://t.me/userinfobot))

### Выберите способ запуска:

**Локально:** Python 3.10+ и pip

**Docker Compose (рекомендуется):** Docker и Docker Compose

---

## Метод 1: Локальный запуск (Python)

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd gpt-calendar-bot
```

### 2. Создание виртуального окружения

```bash
python -m venv venv

# Активация на macOS/Linux:
source venv/bin/activate

# Активация на Windows:
venv\Scripts\activate
```

### 3. Установка зависимостей

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Настройка переменных окружения

Скопируйте `.env.example` в `.env`:

```bash
cp .env.example .env
```

Отредактируйте `.env` файл и заполните необходимые значения:

```bash
nano .env  # или используйте любой текстовый редактор
```

### 5. Запуск бота

```bash
python main.py
```

Вывод в консоли:

```
Бд подгружена успешно
Основная часть запущена
Нажмите Ctrl-C для остановки бота
```

### 6. Остановка бота

Нажмите **Ctrl-C** в терминале. Бот корректно завершит работу и закроет все соединения.

---

## Метод 2: Docker Compose (рекомендуется)

Самый простой способ - Docker Compose всё сделает автоматически.

### Первый запуск

```bash
# 1. Клонируйте репозиторий
git clone <repository-url>
cd gpt-calendar-bot

# 2. Настройте переменные окружения
cp .env.example .env
nano .env  # Заполните TG_TOKEN, LLM_TOKEN, MODEL, ADMIN_CHAT

# 3. Запустите - всё!
docker-compose up -d
```

Вот и всё! 🎉 Бот запущен и работает в фоне.

### Базовые команды

```bash
# Просмотр логов
docker-compose logs -f

# Остановка бота
docker-compose down

# Перезапуск бота
docker-compose restart

# Обновление кода
git pull
docker-compose up -d --build
```

### Дополнительно

```bash
# Просмотр статуса
docker-compose ps

# Просмотр последних 50 строк логов
docker-compose logs --tail=50

# Полная очистка (удаляет базу данных!)
docker-compose down -v
```

---

## Настройка переменных окружения

### Обязательные параметры

```env
# Telegram Bot
TG_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# OpenRouter API
LLM_TOKEN=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MODEL=google/gemini-2.0-flash-exp:free

# Admin
ADMIN_CHAT=123456789

# Database
DATABASE_NAME=users.db
MAX_CONTEXT=20
MAX_STORAGE=100
```

### Опциональные параметры (OAuth для Google Calendar/Tasks)

Для работы с Google Calendar и Google Tasks нужно настроить OAuth 2.0. Подробная инструкция в [docs/oauth-setup.md](oauth-setup.md).

```env
# OAuth 2.0 Configuration (опционально)
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxxxxxx
GOOGLE_OAUTH_REDIRECT_URI=https://yourdomain.com/oauth/callback
OAUTH_SERVER_PORT=8080
```

**Примечание:** Если OAuth не настроен, бот будет работать без функций Google Calendar и Google Tasks, но все остальные функции будут доступны.

### Рекомендуемые модели LLM

| Модель | Тип | Описание |
|--------|-----|----------|
| `google/gemini-2.0-flash-exp:free` | Бесплатная | Быстрая, хорошее качество |
| `openai/gpt-4o-mini` | Платная | Отличное качество, доступная цена |
| `anthropic/claude-3.5-sonnet` | Платная | Высочайшее качество |

Полный список: https://openrouter.ai/models

---

## Настройка поведения бота

### Конфигурационные файлы

Бот использует JSON файлы для хранения конфигурации:

- **`config/messages.json`** — текстовые шаблоны сообщений бота

### Параметры контекста и базы данных

```env
# Контекст и БД
MAX_CONTEXT=20                  # Количество сообщений, передаваемых в контекст модели
MAX_STORAGE=100                 # Количество сообщений, хранимых в базе данных
DATABASE_NAME=users.db          # Имя файла базы данных
```

**MAX_CONTEXT** определяет, сколько последних сообщений из истории диалога будет отправлено в LLM. Чем больше значение, тем лучше модель помнит контекст, но тем выше стоимость и время обработки.

**MAX_STORAGE** ограничивает общее количество сообщений в БД. Когда лимит превышен, старые сообщения автоматически удаляются.


### Параметры подписки на каналы

```env
# Подписка на каналы (опционально)
REQUIRED_CHANNELS=@channel1,@channel2   # Список обязательных каналов через запятую
                                         # Оставьте пустым, чтобы отключить систему подписки
```

**Важно:**
- Каналы указываются с `@` и через запятую без пробелов
- Бот должен быть администратором в каждом канале
- Оставьте поле пустым для отключения проверки подписки

### Параметры логирования

```env
# Логирование в файл debug.log
FILE_LOG_LEVEL=INFO

# Логирование в Telegram чат (опционально)
TELEGRAM_LOG_LEVEL=DISABLED

# ID чата для debug логов
ADMIN_CHAT=123456789
```

📖 **[Подробнее о логировании →](logging.md)**

---

## Управление ботом

### Проверка статуса

```bash
# Локально
ps aux | grep "python main.py"

# Docker Compose
docker-compose ps
```

### Просмотр логов

```bash
# Локально
tail -f debug.log

# Docker Compose
docker-compose logs -f

# Docker (по имени контейнера)
docker logs gpt-calendar-bot --tail=100
docker logs -f gpt-calendar-bot  # в реальном времени
```

---

## Решение проблем

### Множественные запуски бота (процессы-зомби)

**Симптомы:**
- В логах появляются ошибки `TelegramConflictError: Conflict: terminated by other getUpdates request`
- На сервере запущено несколько процессов `python -u main.py`
- Бот продолжает работать даже после остановки контейнера

**Причина:**
При использовании `network_mode: host` в docker-compose процессы контейнера видны на хосте как обычные процессы. При остановке/перезапуске контейнера эти процессы могут остаться висеть на хосте, создавая конфликты.

**Решение:**

1. **Автоматическое (рекомендуется):** Скрипт деплоя автоматически убивает процессы-зомби при каждом деплое.

2. **Ручная очистка:**
   ```bash
   # Найти процессы-зомби
   ps aux | grep "python -u main.py"
   
   # Убить все процессы-зомби
   sudo pkill -f "python -u main.py"
   
   # Или использовать скрипт
   ./scripts/kill_zombie_processes.sh
   ```

3. **Проверка после очистки:**
   ```bash
   # Убедитесь, что процессы убиты
   pgrep -f "python -u main.py" || echo "Процессы не найдены"
   
   # Перезапустите контейнер
   cd ~/gpt-calendar-bot
   docker-compose -f docker-compose.prod.yml restart
   ```

### Другие проблемы

При возникновении других проблем проверьте логи и настройки окружения.

---

## Рекомендации для Production

### Используйте Docker Compose

Самый простой и надежный способ. Автоматический перезапуск уже настроен.

### Регулярные бэкапы

Сохраняйте базу данных:

```bash
# Создайте cron задачу:
0 3 * * * cp /path/to/gpt-calendar-bot/data/users.db /backups/users-$(date +\%Y\%m\%d).db
```

### Обновления

```bash
# Обновите код и перезапустите
cd gpt-calendar-bot
git pull
docker-compose up -d --build
```

### Безопасность

- ✅ Никогда не коммитьте `.env`
- ✅ Храните токены в секрете
- ✅ Регулярно обновляйте зависимости

---

## Дополнительные команды

### Бэкап базы данных

```bash
# Экспорт
sqlite3 data/users.db .dump > backup.sql

# Импорт
sqlite3 data/users.db < backup.sql
```

### Очистка Docker

```bash
# Удалить старые образы и освободить место
docker system prune -a
```

---

## Автоматический деплой

Хотите, чтобы бот автоматически обновлялся на сервере при каждом `git push`?

📖 **[Настроить CI/CD с GitHub Actions →](ci-cd.md)**

---

## Полезные ссылки

- [Документация Docker](https://docs.docker.com/)
- [Документация Docker Compose](https://docs.docker.com/compose/)
- [Документация aiogram](https://docs.aiogram.dev/)
- [OpenRouter API](https://openrouter.ai/docs)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [GitHub Actions](https://docs.github.com/en/actions)
- [Yandex Cloud](https://cloud.yandex.ru/docs)

---

Если возникли вопросы или проблемы, создайте Issue в репозитории проекта.

