# Многоэтапная сборка для оптимизации
FROM python:3.11-slim AS base

# Устанавливаем переменные окружения
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Создаем рабочую директорию
WORKDIR /app

# Копируем файл с зависимостями
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Этап разработки
FROM base AS development

# Копируем весь код для разработки
COPY . .

# Создаем пользователя для безопасности
RUN useradd --create-home --shell /bin/bash --uid 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Команда для разработки
CMD ["python", "-m", "app.main"]

# Этап продакшена
FROM base AS production

# Копируем только необходимые файлы приложения
COPY app/ ./app/

# Создаем пользователя для безопасности
RUN useradd --create-home --shell /bin/bash --uid 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Health check для продакшена
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Команда для продакшена
CMD ["python", "-m", "app.main"]
