# 📅 Bumpix Parser Bot

Telegram-бот для моніторингу вільних слотів запису до спеціаліста **Анна Карпова (WaxHubStudio)** на [bumpix.net](https://bumpix.net/uk/waxhubstudio).

## 🚀 Можливості

- **`/check`** — перевірити вільні слоти на найближчі 14 днів (тільки доступні)
- **`/full`** — повний розклад (включно з вихідними та зайнятими днями)
- **`/notify`** — увімкнути/вимкнути автоматичні сповіщення про нові слоти
- **`/help`** — довідка

## ⚙️ Налаштування

### 1. Створити бота в Telegram

1. Відкрийте [@BotFather](https://t.me/BotFather) у Telegram
2. Надішліть `/newbot` та дотримуйтесь інструкцій
3. Скопіюйте отриманий **токен**

### 2. Налаштувати .env файл

```bash
cp .env.example .env
```

Відредагуйте `.env`:

```env
BOT_TOKEN=123456789:ABCDefGhIjKlMnOpQrStUvWxYz
DAYS_AHEAD=14
AUTO_CHECK_INTERVAL=1800   # перевірка кожні 30 хв (0 = вимкнено)
NOTIFY_CHAT_IDS=           # ваш chat_id (дізнатись через @userinfobot)
```

## 🐳 Запуск у Docker

```bash
# Зібрати та запустити
docker compose up -d --build

# Переглянути логи
docker compose logs -f

# Зупинити
docker compose down
```

## 💻 Локальний запуск (без Docker)

```bash
# Створити віртуальне середовище
python -m venv .venv

# Активувати (Windows)
.venv\Scripts\activate

# Встановити залежності
pip install -r requirements.txt

# Запустити бота
python bot.py
```

## 📐 Архітектура

```
Bumpix_Parser/
├── bot.py              # Telegram-бот (aiogram 3)
├── parser.py           # Парсер API bumpix.net
├── config.py           # Конфігурація
├── requirements.txt    # Залежності Python
├── Dockerfile          # Docker образ
├── docker-compose.yml  # Docker Compose
├── .env.example        # Шаблон змінних оточення
└── .dockerignore       # Docker ігнор
```

## 🔧 Як працює

1. Бот робить POST-запит до `https://bumpix.net/data/api/site_get_data_for_appointment`
2. Передає `generalId` (ID спеціаліста), `insideId`, та діапазон дат
3. API повертає JSON з робочими годинами, перервами та існуючими записами
4. Бот обчислює вільні слоти за тим же алгоритмом, що й веб-сайт
5. Результат форматується та відправляється в Telegram
