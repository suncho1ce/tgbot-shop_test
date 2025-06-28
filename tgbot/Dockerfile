FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir aiogram[fast] asyncpg python-dotenv openpyxl
CMD ["python", "bot.py"]
