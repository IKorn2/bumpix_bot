FROM python:3.12-slim

# Метадані
LABEL maintainer="Bumpix Parser Bot"
LABEL description="Telegram bot for parsing bumpix.net specialist schedule"

# Робоча директорія
WORKDIR /app

# Створення директорії для даних
RUN mkdir -p /app/data

# Встановлення залежностей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіювання коду
COPY config.py .
COPY parser.py .
COPY bot.py .
COPY database.py .
COPY calendar_drawer.py .
COPY test_image.py .

# Запуск бота
CMD ["python", "bot.py"]
