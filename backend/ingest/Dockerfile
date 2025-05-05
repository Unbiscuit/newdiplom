FROM python:3.10-slim-bullseye

# Устанавливаем рабочую директорию
WORKDIR /app

# Отключаем буферизацию Python (все логи сразу в stdout)
ENV PYTHONUNBUFFERED=1

# Копируем и устанавливаем зависимости
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# (Опционально) устанавливаем curl для healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Копируем исходники приложения
COPY . /app

# Открываем порт 8100
EXPOSE 8100

# Healthcheck: проверяем эндпойнт /health
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD curl -f http://localhost:8100/health || exit 1

# Запуск сервиса ingest на 8100 порту
CMD ["bash", "-c", "uvicorn ingest_app:app --host 0.0.0.0 --port 8100"]