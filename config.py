"""
Конфігурація бота Bumpix Parser
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token (отримати через @BotFather)
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Bumpix API
BUMPIX_API_URL = "https://bumpix.net/data/api/site_get_data_for_appointment"
BUMPIX_PAGE_URL = "https://bumpix.net/uk/waxhubstudio"

# Спеціаліст: Анна Карпова (WaxHubStudio)
GENERAL_ID = int(os.getenv("GENERAL_ID", "378544"))
INSIDE_ID = os.getenv("INSIDE_ID", "1.1")

# Скільки днів наперед перевіряти
DAYS_AHEAD = int(os.getenv("DAYS_AHEAD", "14"))

# Тривалість послуги в хвилинах (інтервал вільного часу)
SERVICE_DURATION = int(os.getenv("SERVICE_DURATION", "60"))

# Інтервал автоматичної перевірки (в секундах), 0 = вимкнено
AUTO_CHECK_INTERVAL = int(os.getenv("AUTO_CHECK_INTERVAL", "900"))

# ID чатів для автоматичних повідомлень (через кому)
NOTIFY_CHAT_IDS = [
    int(x.strip()) for x in os.getenv("NOTIFY_CHAT_IDS", "").split(",") if x.strip()
]
