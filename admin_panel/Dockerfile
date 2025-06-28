# Используем официальный образ Python
FROM python:3.11-slim

# Устанавливаем переменные окружения, чтобы Python не создавал .pyc файлы и выводил логи сразу
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл с зависимостями и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем остальной код приложения
COPY . .