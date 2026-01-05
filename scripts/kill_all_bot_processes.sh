#!/bin/bash
# Полная очистка всех процессов и контейнеров бота
# Используется когда нужно полностью остановить бот

set -e

echo "🔍 Полная очистка бота..."
echo ""

# 1. Останавливаем и удаляем Docker контейнеры
echo "1️⃣ Останавливаем Docker контейнеры..."
CONTAINERS=$(docker ps -aq --filter name=gpt-calendar-bot 2>/dev/null || true)
if [ -n "$CONTAINERS" ]; then
  echo "   Найдены контейнеры: $CONTAINERS"
  docker stop $CONTAINERS 2>/dev/null || true
  docker rm -f $CONTAINERS 2>/dev/null || true
  echo "   ✅ Контейнеры удалены"
else
  echo "   ℹ️  Docker контейнеры не найдены"
fi

# 2. docker-compose down
echo ""
echo "2️⃣ Останавливаем через docker-compose..."
if [ -f "/root/gpt-calendar-bot/deployment/docker-compose.prod.yml" ]; then
  cd /root/gpt-calendar-bot/deployment
  docker-compose -f docker-compose.prod.yml down 2>/dev/null || true
  echo "   ✅ docker-compose остановлен"
else
  echo "   ℹ️  docker-compose.prod.yml не найден"
fi

# 3. Убиваем процессы на порту 8080
echo ""
echo "3️⃣ Освобождаем порт 8080..."
PORT_PIDS=$(sudo lsof -ti:8080 2>/dev/null || true)
if [ -n "$PORT_PIDS" ]; then
  echo "   Найдены процессы: $PORT_PIDS"
  for PID in $PORT_PIDS; do
    echo "   Убиваем PID: $PID"
    sudo kill -9 "$PID" 2>/dev/null || true
  done
  sleep 2
  echo "   ✅ Порт 8080 освобожден"
else
  echo "   ℹ️  Порт 8080 свободен"
fi

# 4. Убиваем Python процессы бота (рекурсивно всё дерево)
echo ""
echo "4️⃣ Убиваем Python процессы (рекурсивно)..."
PYTHON_PIDS=$(pgrep -f "python.*main.py" 2>/dev/null || true)
if [ -n "$PYTHON_PIDS" ]; then
  echo "   Найдены процессы: $PYTHON_PIDS"
  # Убиваем все процессы main.py рекурсивно
  sudo pkill -9 -f "python.*main.py" 2>/dev/null || true
  sleep 2
  # Проверяем и убиваем оставшиеся по PID
  REMAINING_PIDS=$(pgrep -f "python.*main.py" 2>/dev/null || true)
  if [ -n "$REMAINING_PIDS" ]; then
    echo "   Убиваем оставшиеся процессы: $REMAINING_PIDS"
    for PID in $REMAINING_PIDS; do
      sudo kill -9 "$PID" 2>/dev/null || true
    done
  fi
  sleep 2
  echo "   ✅ Python процессы убиты"
else
  echo "   ℹ️  Python процессы не найдены"
fi

# 5. Проверяем результат
echo ""
echo "📊 Проверка результата:"
echo ""

echo "Docker контейнеры:"
REMAINING_CONTAINERS=$(docker ps -a --filter name=gpt-calendar-bot 2>/dev/null || true)
if [ -z "$REMAINING_CONTAINERS" ]; then
  echo "   ✅ Контейнеры отсутствуют"
else
  echo "   ⚠️  Остались контейнеры:"
  docker ps -a --filter name=gpt-calendar-bot
fi

echo ""
echo "Порт 8080:"
REMAINING_PORT=$(sudo lsof -ti:8080 2>/dev/null || true)
if [ -z "$REMAINING_PORT" ]; then
  echo "   ✅ Порт свободен"
else
  echo "   ⚠️  Порт занят процессами: $REMAINING_PORT"
  sudo lsof -i:8080
fi

echo ""
echo "Python процессы:"
REMAINING_PYTHON=$(pgrep -f "python.*main.py" 2>/dev/null || true)
if [ -z "$REMAINING_PYTHON" ]; then
  echo "   ✅ Python процессы отсутствуют"
else
  echo "   ⚠️  Остались процессы: $REMAINING_PYTHON"
  ps aux | grep "python.*main.py" | grep -v grep
fi

echo ""
echo "✅ Очистка завершена!"

