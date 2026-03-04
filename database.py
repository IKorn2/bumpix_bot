import sqlite3
import os

# Використовуємо абсолютний шлях або змінну оточення
DB_DIR = os.getenv("DB_DIR", "/app/data")
DB_PATH = os.path.join(DB_DIR, "subscriptions.db")

def init_db():
    """Створює таблицю для підписок, якщо вона не існує."""
    # Створюємо директорію, якщо вона не існує
    os.makedirs(DB_DIR, exist_ok=True)
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                chat_id INTEGER PRIMARY KEY
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS last_slots (
                date_label TEXT PRIMARY KEY,
                slots_json TEXT
            )
        """)
        conn.commit()

def add_subscription(chat_id: int):
    """Додає чат до списку розсилки."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR IGNORE INTO subscriptions (chat_id) VALUES (?)", (chat_id,))
        conn.commit()

def remove_subscription(chat_id: int):
    """Видаляє чат зі списку розсилки."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM subscriptions WHERE chat_id = ?", (chat_id,))
        conn.commit()

def get_subscriptions() -> set[int]:
    """Повертає набір всіх ID чатів, що підписані."""
    if not os.path.exists(DB_PATH):
        return set()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT chat_id FROM subscriptions")
        return {row[0] for row in cursor.fetchall()}

def get_last_known_slots() -> dict[str, set[str]]:
    """Завантажує останній відомий стан слотів з БД."""
    if not os.path.exists(DB_PATH):
        return {}
    
    slots = {}
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT date_label, slots_json FROM last_slots")
        for row in cursor.fetchall():
            date_label, slots_json = row
            # Оскільки ми зберігаємо просто список через кому для простоти
            if slots_json:
                slots[date_label] = set(slots_json.split(","))
            else:
                slots[date_label] = set()
    return slots

def update_last_known_slots(current_slots: dict[str, set[str]]):
    """Оновлює стан слотів у БД (повна синхронізація)."""
    with sqlite3.connect(DB_PATH) as conn:
        # Очищаємо старі дані (або можна робити REPLACE INTO для кожного дня)
        conn.execute("DELETE FROM last_slots")
        
        for date_label, slot_set in current_slots.items():
            slots_json = ",".join(sorted(list(slot_set)))
            conn.execute(
                "INSERT INTO last_slots (date_label, slots_json) VALUES (?, ?)",
                (date_label, slots_json)
            )
        conn.commit()
