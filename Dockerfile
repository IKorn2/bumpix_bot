FROM python:3.12-slim

# Метадані
LABEL maintainer="Bumpix Parser Bot"
LABEL description="Telegram bot for parsing bumpix.net specialist schedule"

# Робоча директорія
WORKDIR /app

# Встановлення залежностей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіювання коду
COPY config.py .
COPY parser.py .
COPY bot.py .

# Запуск бота
CMD ["python", "bot.py"]
