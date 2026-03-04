import sqlite3
import os

DB_PATH = "subscriptions.db"

def init_db():
    """Створює таблицю для підписок, якщо вона не існує."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                chat_id INTEGER PRIMARY KEY
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
