# Используем образ с предустановленными научными библиотеками
FROM python:3.13-slim

WORKDIR /app

# Устанавливаем только runtime библиотеки (минимальный набор для opencv-headless)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл зависимостей
COPY requirements/requirements.txt .

# Устанавливаем зависимости с использованием wheels (без компиляции)
# Используем --only-binary для всех пакетов, чтобы избежать компиляции
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --only-binary :all: -r requirements.txt

# Копируем весь код приложения
COPY . .

# Создаем директорию для базы данных и логов
RUN mkdir -p /data

# Запускаем бота
CMD ["python", "-u", "main.py"]

