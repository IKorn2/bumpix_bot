FROM python:3.12-slim

# Метадані
LABEL maintainer="Bumpix Parser Bot"
LABEL description="Telegram bot for parsing bumpix.net specialist schedule with Playwright"

# Робоча директорія
WORKDIR /app

# Створення директорії для даних
RUN mkdir -p /app/data

# Встановлення системних залежностей для Playwright (Chromium)
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxcb1 \
    libxkbcommon0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libatk1.0-0 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Встановлення залежностей Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Встановлення браузера Playwright
RUN playwright install chromium
RUN playwright install-deps chromium

# Копіювання коду
COPY config.py .
COPY parser.py .
COPY bot.py .
COPY database.py .
COPY calendar_drawer.py .

# Запуск бота
CMD ["python", "bot.py"]
