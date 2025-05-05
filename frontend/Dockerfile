FROM node:18-slim AS build

# Рабочая папка для сборки фронтенда
WORKDIR /app

# Копируем package.json и lock-файл, устанавливаем зависимости
COPY package*.json ./
RUN npm ci --no-progress --prefer-offline

# Копируем остальной исходный код и выполняем сборку
COPY . .
RUN npm run build

# Этап 2: запуск в среде Nginx для раздачи статического фронтенда
FROM nginx:stable-alpine

# Копируем собранные статические файлы из этапа сборки
COPY --from=build /app/build /usr/share/nginx/html

# (Опционально) Копируем пользовательский конфиг Nginx для SPA (если требуется настроить маршруты)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Открываем порт 80 для веб-сервера
EXPOSE 80

# Устанавливаем curl для healthcheck
RUN apk add --no-cache curl

# Проверка работоспособности: запрос главной страницы
HEALTHCHECK --interval=30s --timeout=5s CMD curl -f http://localhost/ || exit 1

# Стартуем Nginx (в режиме foreground, чтобы контейнер не завершился)
CMD ["nginx", "-g", "daemon off;"]