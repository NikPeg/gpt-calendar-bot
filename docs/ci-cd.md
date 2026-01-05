# 🚀 CI/CD: Автоматический деплой на Yandex Cloud

Руководство по настройке автоматического развертывания бота на сервер Yandex Cloud при каждом push в ветку `main`.

## 📋 Содержание

- [Что происходит автоматически](#что-происходит-автоматически)
- [Предварительные требования](#предварительные-требования)
- [Настройка Yandex Cloud](#настройка-yandex-cloud)
- [Настройка GitHub Secrets](#настройка-github-secrets)
- [Настройка сервера](#настройка-сервера)
- [Первый деплой](#первый-деплой)
- [Мониторинг и логи](#мониторинг-и-логи)
- [Решение проблем](#решение-проблем)

---

## Что происходит автоматически

При каждом `git push` в ветку `main`:

1. ✅ **Тесты** — проверка синтаксиса Python и валидация JSON
2. 🏗️ **Сборка** — создание Docker образа и загрузка в Yandex Container Registry
3. 🚀 **Деплой** — автоматическое развертывание на сервере
4. ✅ **Проверка** — автоматическая верификация, что бот запустился

Весь процесс занимает **3-5 минут**.

---

## Предварительные требования

### В Yandex Cloud:

- ☁️ Активированный аккаунт Yandex Cloud
- 💳 Привязанная платежная карта (можно использовать бесплатный грант)
- 🖥️ Виртуальная машина (минимум 1 vCPU, 2 GB RAM)
- 🐳 Docker установлен на VM

### В GitHub:

- 📦 Репозиторий проекта gpt-calendar-bot
- 🔑 Права на добавление Secrets в репозиторий

---

## Настройка Yandex Cloud

### 1. Создание Container Registry

```bash
# Создайте реестр контейнеров
yc container registry create --name gpt-calendar-bot-registry

# Получите ID реестра
yc container registry list
```

Сохраните **Registry ID** (вида `crp123abc456def`).

### 2. Создание Service Account

```bash
# Создайте сервисный аккаунт
yc iam service-account create --name github-actions-sa

# Назначьте роли
SA_ID=$(yc iam service-account get github-actions-sa --format json | jq -r .id)
REGISTRY_ID="ваш_registry_id"

yc container registry add-access-binding \
  --id $REGISTRY_ID \
  --service-account-id $SA_ID \
  --role container-registry.images.pusher

# Создайте ключ для аутентификации
yc iam key create \
  --service-account-id $SA_ID \
  --output key.json
```

Сохраните содержимое файла `key.json` — он понадобится для GitHub Secrets.

### 3. Получение Cloud и Folder ID

```bash
# Cloud ID
yc config list | grep cloud-id

# Folder ID
yc config list | grep folder-id
```

### 4. Создание виртуальной машины

```bash
# Создайте VM с Docker
yc compute instance create \
  --name gpt-calendar-bot-server \
  --zone ru-central1-a \
  --network-interface subnet-name=default-ru-central1-a,nat-ip-version=ipv4 \
  --create-boot-disk image-folder-id=standard-images,image-family=ubuntu-2204-lts,size=20 \
  --memory 2 \
  --cores 2 \
  --ssh-key ~/.ssh/id_rsa.pub

# Получите IP адрес
yc compute instance get gpt-calendar-bot-server --format json | jq -r .network_interfaces[0].primary_v4_address.one_to_one_nat.address
```

### 5. Установка Docker на сервере

```bash
# Подключитесь к серверу
ssh ubuntu@<your_server_ip>

# Установите Docker
sudo apt-get update
sudo apt-get install -y docker.io docker-compose
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER

# Перелогиньтесь для применения изменений
exit
```

---

## Настройка GitHub Secrets

### 🚀 Быстрый способ (рекомендуется)

Используйте автоматический скрипт для подготовки всех секретов:

```bash
./scripts/prepare_github_secrets.sh
```

Скрипт автоматически:
- ✅ Получит Cloud ID и Folder ID из `yc` конфигурации
- ✅ Предложит выбрать Container Registry или создаст новый
- ✅ Создаст Service Account (если нужно) и настроит права
- ✅ Сгенерирует JSON ключ для Service Account
- ✅ Найдёт SSH ключ автоматически
- ✅ Выведет все готовые значения для копирования

📖 **Подробнее:** [scripts/README.md](../scripts/README.md#prepare_github_secretssh)

---

### 📝 Ручной способ

Перейдите в **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

### Обязательные Secrets:

| Secret | Описание | Где получить |
|--------|----------|--------------|
| `YC_SA_JSON_CREDENTIALS` | Содержимое `key.json` | Весь JSON из файла `key.json` |
| `YC_REGISTRY_ID` | ID Container Registry | `yc container registry list` |
| `YC_CLOUD_ID` | ID облака | `yc config list` |
| `YC_FOLDER_ID` | ID каталога | `yc config list` |
| `YC_INSTANCE_IP` | **Публичный** IP адрес сервера | `yc compute instance get <name>` (поле `one_to_one_nat.address`) |
| `YC_INSTANCE_USER` | Пользователь SSH на сервере | Для YC обычно `yc-user` или имя пользователя из метаданных |
| `SSH_PRIVATE_KEY` | Приватный SSH ключ | Файл из `~/.ssh/` (например `yc-organization-id-...-<user>`) |
| `TG_TOKEN` | Токен Telegram бота | @BotFather |
| `LLM_TOKEN` | Токен OpenRouter | https://openrouter.ai/ |
| `ADMIN_CHAT` | ID чата для администрирования | @userinfobot |

### Опциональные Secrets (есть значения по умолчанию):

| Secret | По умолчанию | Описание |
|--------|--------------|----------|
| `MODEL` | `google/gemini-2.0-flash-exp:free` | Модель LLM |
| `MAX_CONTEXT` | `20` | Размер контекста для модели |
| `MAX_STORAGE` | `100` | Размер хранилища сообщений в БД |
| `FEEDBACK_FORM_URL` | `` (пусто) | Ссылка на Google форму для обратной связи |

---

## Настройка сервера

### Подготовка директорий

SSH на сервер и выполните:

```bash
# Создайте директории для данных
sudo mkdir -p /opt/gpt-calendar-bot/data /opt/gpt-calendar-bot/logs
sudo chmod -R 755 /opt/gpt-calendar-bot
```

### Настройка Docker для работы без sudo

Уже сделано на шаге 5 выше, но если нужно:

```bash
sudo usermod -aG docker $USER
newgrp docker
```

---

## Первый деплой

### 1. Проверьте workflow файл

Убедитесь, что файл `.github/workflows/deploy.yml` есть в репозитории.

### 2. Добавьте все Secrets

Проверьте, что все обязательные secrets добавлены в GitHub.

### 3. Сделайте push

```bash
git add .
git commit -m "Setup CI/CD for Yandex Cloud"
git push origin main
```

### 4. Отследите процесс

1. Перейдите в **Actions** на GitHub
2. Выберите последний workflow run
3. Наблюдайте за выполнением этапов:
   - ✅ Test
   - ✅ Build and push
   - ✅ Deploy

### 5. Проверьте деплой

После успешного деплоя:

```bash
# SSH на сервер
ssh ubuntu@<your_server_ip>

# Проверьте статус контейнера
docker ps | grep gpt-calendar-bot

# Посмотрите логи
docker logs gpt-calendar-bot

# Проверьте, что бот отвечает
# Напишите боту в Telegram
```

---

## Мониторинг и логи

### Просмотр логов на сервере

```bash
# Последние 50 строк
docker logs --tail 50 gpt-calendar-bot

# В реальном времени
docker logs -f gpt-calendar-bot

# Логи из файла
ssh ubuntu@<your_server_ip> 'cat /opt/gpt-calendar-bot/logs/debug.log | tail -50'
```

### Проверка статуса

```bash
# Статус контейнера
docker ps -a | grep gpt-calendar-bot

# Использование ресурсов
docker stats gpt-calendar-bot

# Информация о контейнере
docker inspect gpt-calendar-bot
```

### GitHub Actions логи

1. Перейдите в **Actions** → выберите workflow run
2. Раскройте любой step для детальных логов
3. Загрузите полные логи через **"Download log archive"**

---

## Решение проблем

### Build failed

**Проблема:** Ошибка при сборке Docker образа

**Решение:**
1. Проверьте синтаксис в `Dockerfile`
2. Убедитесь, что все файлы есть в репозитории
3. Проверьте логи в GitHub Actions

### Push to registry failed

**Проблема:** Не удается загрузить образ в Registry

**Решение:**
1. Проверьте `YC_SA_JSON_CREDENTIALS` — должен быть валидный JSON
2. Проверьте `YC_REGISTRY_ID`
3. Убедитесь, что у Service Account есть права `container-registry.images.pusher`

### Deployment failed - SSH connection

**Проблема:** Не удается подключиться к серверу

**Решение:**
1. Проверьте `YC_INSTANCE_IP` — правильный ли IP
2. Проверьте `SSH_PRIVATE_KEY` — весь ключ, включая `-----BEGIN` и `-----END`
3. Проверьте, что на сервере разрешен SSH доступ:
   ```bash
   yc compute instance add-one-to-one-nat <instance-name> --network-interface-index 0
   ```

### Container не запускается

**Проблема:** Контейнер падает сразу после запуска

**Решение:**
1. Посмотрите логи: `docker logs gpt-calendar-bot`
2. Проверьте все Secrets — особенно `TG_TOKEN` и `LLM_TOKEN`
3. Проверьте, что директории созданы: `ls -la /opt/gpt-calendar-bot/`

### Бот не отвечает

**Проблема:** Контейнер работает, но бот молчит

**Решение:**
1. Проверьте логи бота: `docker logs gpt-calendar-bot`
2. Проверьте `TG_TOKEN` — правильный ли токен
3. Проверьте `LLM_TOKEN` и баланс на OpenRouter
4. Проверьте переменные окружения в контейнере:
   ```bash
   docker exec gpt-calendar-bot env | grep -E 'TG_TOKEN|LLM_TOKEN'
   ```

### База данных потеряна после деплоя

**Проблема:** После обновления бота база данных пустая

**Решение:**
- База сохраняется в volume `/opt/gpt-calendar-bot/data`
- Убедитесь, что в deploy.sh правильно смонтирован volume:
  ```bash
  -v /opt/gpt-calendar-bot/data:/data
  ```

### Workflow запускается, но ничего не происходит

**Проблема:** Workflow показывает успех, но на сервере ничего не меняется

**Решение:**
1. Проверьте логи в шаге "Deploy to Yandex Cloud"
2. Проверьте права пользователя на сервере: `sudo usermod -aG docker ubuntu`
3. Проверьте, что Docker работает: `systemctl status docker`

### Деплой откатывается хотя бот работает

**Проблема:** Бот запускается и работает нормально, но деплой считается неуспешным и происходит откат

**Причина:** Скрипт деплоя проверяет логи на наличие ошибок запуска, проблем с миграциями и критических ошибок.

**Что проверяется:**
1. **Миграции БД** — если в логах есть `❌.*миграци` или `Ошибка при применении миграции`, деплой откатывается
   - Сообщения `✅ Все миграции применены успешно` и `✅ Миграций не найдено` считаются успешными
2. **Критические ошибки** — если в логах есть `CRITICAL`, `ERROR.*Failed to`, `Exception.*startup`
3. **Healthcheck** — контейнер должен стать `healthy` в течение 60 секунд (или просто запуститься, если healthcheck не настроен)

**Решение:**
1. Проверьте логи деплоя в GitHub Actions, найдите раздел "Проверяем логи на наличие критических ошибок"
2. Посмотрите какие именно сообщения вызвали откат
3. Если это ложное срабатывание (например, ERROR в выводе модели), измените регулярное выражение в workflow файле
4. Если проблема реальная — исправьте код и сделайте новый push

---

## Мониторинг деплоя

### Проверка статуса в GitHub Actions

После каждого push в `main`:

1. Перейдите в раздел **Actions** на GitHub
2. Выберите последний workflow run
3. Проверьте статус каждого этапа:
   - ✅ Test - должен быть зеленым
   - ✅ Build and push - должен быть зеленым
   - ✅ Deploy - должен быть зеленым

### Проверка на сервере

После успешного деплоя проверьте работу бота:

```bash
# Проверьте статус контейнера
docker ps | grep gpt-calendar-bot

# Проверьте логи
docker logs --tail=50 gpt-calendar-bot

# Проверьте использование ресурсов
docker stats gpt-calendar-bot --no-stream
```

### Проверка работоспособности бота

- Отправьте тестовое сообщение боту в Telegram
- Проверьте, что бот отвечает корректно
- Проверьте работу команд `/start`, `/help`

### Уведомления

Уведомления о статусе деплоя отправляются автоматически в Telegram чат `ADMIN_CHAT`:
- ✅ При успешном деплое
- ❌ При ошибке деплоя

---

## Ручной откат

Если что-то пошло не так, можно откатить деплой:

```bash
# SSH на сервер
ssh ubuntu@<your_server_ip>

# Остановите текущий контейнер
docker stop gpt-calendar-bot
docker rm gpt-calendar-bot

# Посмотрите доступные образы
docker images | grep gpt-calendar-bot

# Запустите предыдущую версию
docker run -d \
  --name gpt-calendar-bot \
  --restart unless-stopped \
  --env-file /opt/gpt-calendar-bot/.env \
  -v /opt/gpt-calendar-bot/data:/data \
  cr.yandex/<registry-id>/gpt-calendar-bot:<старый-тег>
```

### Быстрый откат через GitHub

Если нужно вернуться к предыдущему коммиту:

```bash
# Локально
git log --oneline  # Найдите хороший коммит

# Откатитесь к нему
git revert <bad-commit-hash>

# Или создайте новый коммит с исправлениями
git push origin main

# Деплой запустится автоматически
```

---

**Готово!** 🎉 Теперь при каждом push в `main` бот автоматически обновляется на сервере.

## Дополнительно

Для получения дополнительной информации см. другие разделы документации.

