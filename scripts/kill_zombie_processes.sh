#!/bin/bash
# Скрипт для очистки процессов-зомби бота на сервере
# Используется при проблемах с множественными запусками бота

set -e

echo "🔍 Ищем процессы python -u main.py..."

# Находим все процессы
PIDS=$(pgrep -f "python -u main.py" || true)

if [ -z "$PIDS" ]; then
  echo "✅ Процессы-зомби не найдены"
  exit 0
fi

echo "⚠️  Найдены процессы-зомби:"
ps aux | grep "python -u main.py" | grep -v grep

echo ""
read -p "Убить все эти процессы? (y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Отменено"
  exit 0
fi

# Убиваем процессы
for PID in $PIDS; do
  echo "  Убиваем процесс PID: $PID..."
  sudo kill -9 "$PID" 2>/dev/null || true
done

sleep 2

# Проверяем результат
REMAINING=$(pgrep -f "python -u main.py" || true)
if [ -z "$REMAINING" ]; then
  echo "✅ Все процессы-зомби уничтожены"
else
  echo "⚠️  Остались процессы: $REMAINING"
  exit 1
fi

