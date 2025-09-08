# db.py
import sqlite3
import logging

# ---------------- LOGGING ----------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# ---------------- DATABASE CONNECTION ----------------
conn = sqlite3.connect("chat.db", check_same_thread=False)
c = conn.cursor()

# ---------------- INITIALIZATION ----------------
def init_db():
    logger.debug("Initializing database tables...")
    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_mode (
            user_id INTEGER PRIMARY KEY,
            active INTEGER
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            user_id INTEGER,
            user_message_id INTEGER,
            group_message_id INTEGER,
            content TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    conn.commit()
    logger.debug("Database initialized successfully.")

# ---------------- ADMIN GROUP ID ----------------
def set_admin_group_id(group_id: int):
    try:
        logger.debug(f"Setting ADMIN_GROUP_ID = {group_id}")
        c.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", ("ADMIN_GROUP_ID", str(group_id)))
        conn.commit()
        logger.debug("ADMIN_GROUP_ID saved in database.")
    except Exception as e:
        logger.error(f"Failed to set ADMIN_GROUP_ID: {e}")

def get_admin_group_id():
    try:
        c.execute("SELECT value FROM settings WHERE key='ADMIN_GROUP_ID'")
        row = c.fetchone()
        if row:
            logger.debug(f"Retrieved ADMIN_GROUP_ID = {row[0]}")
            return int(row[0])
        return None
    except Exception as e:
        logger.error(f"Failed to get ADMIN_GROUP_ID: {e}")
        return None

# ---------------- CHAT MODE ----------------
def is_user_in_chat(user_id: int) -> bool:
    try:
        c.execute("SELECT active FROM chat_mode WHERE user_id=?", (user_id,))
        row = c.fetchone()
        in_chat = row is not None and row[0] == 1
        logger.debug(f"User {user_id} in_chat={in_chat}")
        return in_chat
    except Exception as e:
        logger.error(f"Failed to check chat mode for user {user_id}: {e}")
        return False

# ---------------- MESSAGE MAPPING ----------------
def save_message_mapping(user_id: int, user_message_id: int, group_message_id: int, content: str):
    try:
        c.execute("INSERT INTO messages(user_id, user_message_id, group_message_id, content) VALUES (?, ?, ?, ?)",
                  (user_id, user_message_id, group_message_id, content))
        conn.commit()
        logger.debug(f"Saved message mapping: user {user_id}, user_msg {user_message_id}, group_msg {group_message_id}")
    except Exception as e:
        logger.error(f"Failed to save message mapping for user {user_id}: {e}")

def get_user_by_group_message_id(group_message_id: int):
    try:
        c.execute("SELECT user_id, user_message_id FROM messages WHERE group_message_id=?", (group_message_id,))
        row = c.fetchone()
        if row:
            logger.debug(f"Found mapping for group_message_id {group_message_id}: user_id={row[0]}, user_message_id={row[1]}")
            return row
        return None
    except Exception as e:
        logger.error(f"Failed to get user by group_message_id {group_message_id}: {e}")
        return None
