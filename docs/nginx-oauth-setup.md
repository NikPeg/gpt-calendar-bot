# 🔧 Настройка Nginx для OAuth с sslip.io

## Обзор

Эта инструкция поможет вам настроить nginx как reverse proxy для OAuth callback с использованием sslip.io и Let's Encrypt SSL сертификатов.

**Ваш IP:** 123.45.67.89  
**Домен:** 123-45-67-89.sslip.io  
**Redirect URI:** https://123-45-67-89.sslip.io/oauth/callback

---

## 📋 Требования

- Ubuntu/Debian сервер (или другой Linux)
- Root доступ к серверу
- Порты 80 и 443 открыты в firewall
- Docker с запущенным ботом на порту 8080

---

## Шаг 1: Установка Nginx

### На Ubuntu/Debian:

```bash
# Обновите систему
sudo apt update
sudo apt upgrade -y

# Установите nginx
sudo apt install nginx -y

# Проверьте установку
nginx -v

# Запустите nginx
sudo systemctl start nginx
sudo systemctl enable nginx
```

### Проверка:

Откройте в браузере: http://123.45.67.89  
Должна появиться страница "Welcome to nginx!"

---

## Шаг 2: Установка Certbot (Let's Encrypt)

```bash
# Установите certbot
sudo apt install certbot python3-certbot-nginx -y

# Проверьте установку
certbot --version
```

---

## Шаг 3: Получение SSL сертификата

### ⚠️ ВАЖНО: Временно остановите nginx

```bash
sudo systemctl stop nginx
```

### Получите сертификат:

```bash
sudo certbot certonly --standalone \
  -d 123-45-67-89.sslip.io \
  --non-interactive \
  --agree-tos \
  --email your-email@example.com
```

**Замените `your-email@example.com`** на ваш реальный email!

### ✅ Успешный результат:

```
Successfully received certificate.
Certificate is saved at: /etc/letsencrypt/live/123-45-67-89.sslip.io/fullchain.pem
Key is saved at:         /etc/letsencrypt/live/123-45-67-89.sslip.io/privkey.pem
```

---

## Шаг 4: Настройка Nginx конфигурации

### Создайте конфигурационный файл:

```bash
sudo nano /etc/nginx/sites-available/oauth-bot
```

### Вставьте следующую конфигурацию:

```nginx
# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name 123-45-67-89.sslip.io;
    
    # Для Let's Encrypt обновлений
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
    
    # Редирект на HTTPS
    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS сервер
server {
    listen 443 ssl http2;
    server_name 123-45-67-89.sslip.io;
    
    # SSL сертификаты
    ssl_certificate /etc/letsencrypt/live/123-45-67-89.sslip.io/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/123-45-67-89.sslip.io/privkey.pem;
    
    # SSL настройки (современные, безопасные)
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # OAuth callback endpoint
    location /oauth/callback {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Дополнительно: если хотите проксировать весь OAuth сервер
    location /oauth/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Опционально: страница статуса
    location / {
        return 200 'OAuth Bot is running!';
        add_header Content-Type text/plain;
    }
}
```

**Сохраните файл:** `Ctrl+X`, затем `Y`, затем `Enter`

### Активируйте конфигурацию:

```bash
# Создайте символическую ссылку
sudo ln -s /etc/nginx/sites-available/oauth-bot /etc/nginx/sites-enabled/

# Удалите дефолтную конфигурацию (опционально)
sudo rm /etc/nginx/sites-enabled/default

# Проверьте конфигурацию на ошибки
sudo nginx -t
```

### ✅ Должно быть:

```
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

### Запустите nginx:

```bash
sudo systemctl start nginx
sudo systemctl status nginx
```

---

## Шаг 5: Настройка Firewall

```bash
# Разрешите HTTP и HTTPS
sudo ufw allow 'Nginx Full'

# Или вручную:
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Проверьте статус
sudo ufw status
```

---

## Шаг 6: Проверка работы

### 1. Проверьте, что OAuth сервер запущен:

```bash
# Проверьте, что порт 8080 слушается
sudo netstat -tulpn | grep 8080

# Или
sudo ss -tulpn | grep 8080
```

Должно быть что-то вроде:
```
tcp   0   0 0.0.0.0:8080   0.0.0.0:*   LISTEN   12345/python
```

### 2. Проверьте HTTPS:

Откройте в браузере: https://123-45-67-89.sslip.io

Должно быть:
- ✅ Зеленый замок (валидный SSL)
- Страница "OAuth Bot is running!" или похожая

### 3. Проверьте OAuth callback:

```bash
curl -I https://123-45-67-89.sslip.io/oauth/callback
```

Должен быть ответ от вашего OAuth сервера.

---

## Шаг 7: Автообновление SSL сертификата

Certbot автоматически создает cronjob для обновления. Проверьте:

```bash
# Проверьте таймер
sudo systemctl status certbot.timer

# Тестовое обновление (dry-run)
sudo certbot renew --dry-run
```

Если все ОК, сертификаты будут автоматически обновляться.

---

## 🔍 Troubleshooting

### Проблема: nginx не запускается

```bash
# Проверьте логи
sudo tail -f /var/log/nginx/error.log

# Проверьте конфигурацию
sudo nginx -t
```

### Проблема: 502 Bad Gateway

**Причина:** OAuth сервер не запущен на порту 8080

**Решение:**
```bash
# Проверьте Docker контейнеры
docker ps

# Проверьте логи OAuth сервера
docker logs oauth-bot-container-name
```

### Проблема: SSL не работает

```bash
# Проверьте сертификаты
sudo ls -la /etc/letsencrypt/live/123-45-67-89.sslip.io/

# Должны быть файлы:
# - fullchain.pem
# - privkey.pem
```

### Проблема: OAuth callback не работает

**Проверьте:**
1. Порт 8080 слушается: `sudo netstat -tulpn | grep 8080`
2. Nginx проксирует запросы: `sudo tail -f /var/log/nginx/access.log`
3. OAuth сервер получает запросы: проверьте логи бота

### Проблема: Can't connect to port 443

**Решение:**
```bash
# Проверьте firewall
sudo ufw status

# Откройте порт если закрыт
sudo ufw allow 443/tcp
```

---

## 📊 Полезные команды

```bash
# Перезапустить nginx
sudo systemctl restart nginx

# Проверить статус
sudo systemctl status nginx

# Проверить конфигурацию
sudo nginx -t

# Посмотреть логи доступа
sudo tail -f /var/log/nginx/access.log

# Посмотреть логи ошибок
sudo tail -f /var/log/nginx/error.log

# Обновить SSL сертификат вручную
sudo certbot renew

# Посмотреть все сертификаты
sudo certbot certificates
```

---

## 🔒 Дополнительная безопасность (опционально)

### Ограничить доступ только к OAuth endpoint:

Добавьте в конфигурацию nginx:

```nginx
# Разрешить доступ только к /oauth/
location / {
    deny all;
}

location /oauth/ {
    # ... ваша проксирующая конфигурация
}
```

### Добавить rate limiting:

```nginx
# В начале файла конфигурации (вне блока server)
limit_req_zone $binary_remote_addr zone=oauth_limit:10m rate=10r/m;

# В блоке location /oauth/callback
location /oauth/callback {
    limit_req zone=oauth_limit burst=5;
    # ... остальная конфигурация
}
```

---

## ✅ Чек-лист настройки

- [ ] Nginx установлен и запущен
- [ ] Certbot установлен
- [ ] SSL сертификат получен для 123-45-67-89.sslip.io
- [ ] Конфигурация nginx создана и активирована
- [ ] `nginx -t` проходит успешно
- [ ] Firewall разрешает порты 80 и 443
- [ ] OAuth сервер запущен на порту 8080
- [ ] https://123-45-67-89.sslip.io открывается с валидным SSL
- [ ] OAuth callback работает
- [ ] В Google Cloud Console обновлен Redirect URI
- [ ] В .env файле обновлен GOOGLE_OAUTH_REDIRECT_URI
- [ ] Бот перезапущен с новыми настройками

---

## 🔗 Связанные файлы

- `docs/oauth-setup.md` - Настройка OAuth в Google Cloud Console
- `oauth_server.py` - OAuth сервер бота
- `.env` - Конфигурация (должен содержать GOOGLE_OAUTH_REDIRECT_URI)

---

**Последнее обновление:** 2026-01-05

**Нужна помощь?** Проверьте раздел Troubleshooting или логи nginx!

