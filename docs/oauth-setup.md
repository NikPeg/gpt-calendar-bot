# 🔐 Настройка OAuth 2.0 для Google Calendar Bot

## Обзор

OAuth 2.0 позволяет боту работать с Google Calendar и Google Tasks пользователя от его имени, без необходимости делиться service account файлами. Это современный и безопасный способ авторизации.

---

## 📋 Быстрый старт

### Шаг 1: Настройка Google Cloud Console

**Ваш проект:** scribo-410009

#### 1.1. Включите необходимые APIs

- **Google Calendar API:** https://console.cloud.google.com/apis/library/calendar-json.googleapis.com?project=scribo-410009
- **Google Tasks API:** https://console.cloud.google.com/apis/library/tasks.googleapis.com?project=scribo-410009

Нажмите **ENABLE** если API не включен.

#### 1.2. Настройте OAuth Consent Screen

🔗 https://console.cloud.google.com/apis/credentials/consent?project=scribo-410009

1. Выберите **External** (или Internal для Google Workspace)
2. Заполните:
   - **App name:** Calendar Bot
   - **User support email:** ваш email
   - **Developer contact:** ваш email
3. На странице **Scopes** добавьте:
   - `https://www.googleapis.com/auth/calendar`
   - `https://www.googleapis.com/auth/tasks`
4. На странице **Test users** добавьте свой email
5. Сохраните

#### 1.3. Создайте OAuth Client ID

🔗 https://console.cloud.google.com/apis/credentials?project=scribo-410009

1. Нажмите **+ CREATE CREDENTIALS** → **OAuth client ID**
2. **Application type:** Web application
3. **Name:** Calendar Bot OAuth
4. **Authorized redirect URIs:** `http://localhost:8080/oauth/callback`
5. Нажмите **CREATE**
6. Скопируйте **Client ID** и **Client secret**

### Шаг 2: Настройка .env файла

Добавьте в `.env`:

```bash
# OAuth 2.0 Configuration
GOOGLE_OAUTH_CLIENT_ID=ваш-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=ваш-client-secret
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8080/oauth/callback
```

### Шаг 3: Тестирование OAuth

#### Получение токенов

```bash
export LOG_FILE_PATH=logs/debug.log
python scripts/test_oauth_tasks.py --get-tokens
```

Откроется браузер для авторизации. После успешной авторизации токены сохранятся автоматически.

#### Создание тестовой задачи

```bash
export LOG_FILE_PATH=logs/debug.log
python scripts/test_oauth_tasks.py --create-task
```

#### Просмотр задач

```bash
export LOG_FILE_PATH=logs/debug.log
python scripts/test_oauth_tasks.py --list-tasks
```

---

## 🐛 Решение проблем

### Ошибка 403: access_denied

**Причина:** Вы не добавлены в Test users

**Решение:**
1. Откройте OAuth consent screen
2. В разделе **Test users** нажмите **+ ADD USERS**
3. Добавьте ваш email
4. Повторите авторизацию

### redirect_uri_mismatch

**Причина:** Несоответствие redirect URI

**Решение:**
- В Google Cloud Console должен быть: `http://localhost:8080/oauth/callback`
- В .env должно быть: `GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8080/oauth/callback`

### invalid_client

**Причина:** Неверные Client ID или Client Secret

**Решение:**
- Проверьте правильность credentials в .env
- Убедитесь, что нет лишних пробелов

---

## 🏗️ Архитектура

### Основные компоненты

```
services/
├── google_service_base.py       # Абстрактный базовый класс
├── google_service_oauth.py      # OAuth 2.0 реализация
├── calendar_service.py          # Работа с Calendar API
└── tasks_service.py             # Работа с Tasks API

handlers/
└── oauth_handlers.py            # Telegram команды OAuth

oauth_server.py                  # Web-сервер для OAuth callback
```

### Команды бота

- `/connect_google` — Подключить Google аккаунт
- `/disconnect_google` — Отключить Google аккаунт
- `/reconnect_google` — Переподключить аккаунт
- `/google_status` — Проверить статус подключения

### База данных

OAuth токены хранятся в таблице `conversations`:
- `oauth_access_token` — Токен доступа
- `oauth_refresh_token` — Токен обновления
- `oauth_token_expiry` — Время истечения

---

## 🔒 Безопасность

### CSRF Protection

- Используется state token для защиты от CSRF
- State проверяется при OAuth callback

### Token Storage

- Токены хранятся в SQLite БД
- Автоматическое обновление при истечении
- Токены не логируются

### HTTPS

⚠️ **Для продакшена:** используйте HTTPS для redirect_uri

---

## 📚 Дополнительные материалы

- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Google Calendar API](https://developers.google.com/calendar/api)
- [Google Tasks API](https://developers.google.com/tasks)

---

## ✅ Чек-лист настройки

- [ ] Включил Google Calendar API
- [ ] Включил Google Tasks API
- [ ] Настроил OAuth consent screen
- [ ] Добавил scopes для Calendar и Tasks
- [ ] Добавил свой email в Test users
- [ ] Создал OAuth Client ID
- [ ] Добавил redirect URI
- [ ] Скопировал credentials в .env
- [ ] Успешно получил токены через `--get-tokens`
- [ ] Создал тестовую задачу через `--create-task`

---

**Последнее обновление:** 2026-01-05

