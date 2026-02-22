import sqlite3
from typing import Optional, Tuple

DB_NAME = "users.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            language TEXT DEFAULT 'en',
            verification_status INTEGER DEFAULT 0,
            verification_pending INTEGER DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()

def user_exists(user_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def add_user(user_id: int, username: Optional[str], language: str):
    """language: two-letter code (en, ru, es, ar)."""
    lang = (language or "en").strip().lower()[:2]
    if lang not in ("en", "ru", "es", "ar"):
        lang = "en"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO users (user_id, username, language, verification_status, verification_pending) VALUES (?, ?, ?, 0, 0)",
        (user_id, username, lang)
    )
    conn.commit()
    conn.close()

def update_user_language(user_id: int, username: Optional[str], language: str):
    """Обновляет язык (двухбуквенный код) и username без изменения статуса верификации."""
    lang = (language or "en").strip().lower()[:2]
    if lang not in ("en", "ru", "es", "ar"):
        lang = "en"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT verification_status, verification_pending FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if result:
        cursor.execute(
            "UPDATE users SET username = ?, language = ? WHERE user_id = ?",
            (username, lang, user_id)
        )
    else:
        cursor.execute(
            "INSERT INTO users (user_id, username, language, verification_status, verification_pending) VALUES (?, ?, ?, 0, 0)",
            (user_id, username, lang)
        )
    
    conn.commit()
    conn.close()

def update_language(user_id: int, language: str):
    lang = (language or "en").strip().lower()[:2]
    if lang not in ("en", "ru", "es", "ar"):
        lang = "en"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, user_id))
    conn.commit()
    conn.close()

def get_user_language(user_id: int) -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    raw = result[0] if result else "en"
    raw = (raw or "en").strip().lower()
    code_map = {"english": "en", "russian": "ru", "spanish": "es", "hindi": "en", "arabic": "ar"}
    if raw in ("en", "ru", "es", "ar"):
        return raw
    return code_map.get(raw, "en")

def is_verification_pending(user_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT verification_pending FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] == 1 if result else False

def set_verification_pending(user_id: int, pending: bool):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET verification_pending = ? WHERE user_id = ?", (1 if pending else 0, user_id))
    conn.commit()
    conn.close()

def update_verification_status(user_id: int, status: bool):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET verification_status = ? WHERE user_id = ?", (1 if status else 0, user_id))
    conn.commit()
    conn.close()

def is_verified(user_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT verification_status FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] == 1 if result else False

def get_user_info(user_id: int) -> Optional[Tuple]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result
