FROM python:3.10-slim-bullseye

# Рабочая директория приложения
WORKDIR /app

# Устанавливаем переменные окружения для логирования:
# PYTHONUNBUFFERED: отключает буферизацию вывода (все логи сразу в stdout)
ENV PYTHONUNBUFFERED=1

# Копируем файл с зависимостями и устанавливаем их
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# (При необходимости можно установить дополнительные системные пакеты, например curl для healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Копируем исходный код приложения
COPY . /app

# Открываем порт для приложения (FastAPI по умолчанию на 8000)
EXPOSE 8000

# Добавляем инструкцию Healthcheck: пытаемся получить ответ от сервиса
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD curl -f http://localhost:8000/health || exit 1

# Запускаем приложение через bash (для явного контроля и отладки)
# Предполагается, что в приложении определена FastAPI-приложение "app" (например, в файле main.py)
CMD ["bash", "-c", "uvicorn main:app --host 0.0.0.0 --port 8000"]