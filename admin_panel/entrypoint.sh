#!/bin/sh

# Выход из скрипта при любой ошибке, чтобы сразу видеть проблему
set -e

# Применение миграций базы данных
echo "Applying database migrations..."
python manage.py migrate

# Запуск сервера
echo "Starting Django server on 0.0.0.0:8000"
python manage.py runserver 0.0.0.0:8000