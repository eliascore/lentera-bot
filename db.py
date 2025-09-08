# db.py
import sqlite3
import time
from datetime import datetime
from config import DB_FILE
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

       # Tabel cart + kode bayar
    c.execute("""
    CREATE TABLE IF NOT EXISTS cart (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        nama_produk TEXT,
        harga INTEGER,
        status TEXT DEFAULT 'pending',
        kode_bayar TEXT,       -- kode bayar unik per user
        metode_bayar TEXT,     -- simpan metode pembayaran (QRIS, DANA, GOPAY, dll)
        created_at TEXT        -- timestamp generate kode
    )
    """)

   # Tabel pending_payment untuk hold status pembayaran
    c.execute("""
        CREATE TABLE IF NOT EXISTS pending_payment (
            user_id INTEGER PRIMARY KEY,
            order_id TEXT,
            expected_nominal REAL,
            status TEXT
        )
    """)

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

def save_pending_payment(user_id, order_id, expected_nominal):
   conn = sqlite3.connect(DB_FILE)
   c = conn.cursor()
   c.execute(
       """
        INSERT OR REPLACE INTO pending_payment (user_id, order_id, expected_nominal, status)
        VALUES (?, ?, ?, ?)
    """, (user_id, order_id, expected_nominal, "WAITING_PROOF"))
   conn.commit()
   conn.close()


# Menyimpan kode bayar + timestamp ke cart
def simpan_kode_bayar_di_cart(user_id, username, kode_bayar):
   created_at = datetime.now().isoformat()
   conn = sqlite3.connect(DB_FILE)
   c = conn.cursor()
   c.execute(
       """
        UPDATE cart
        SET kode_bayar = ?, created_at = ?
        WHERE user_id = ? AND status = 'pending'
    """, (kode_bayar, created_at, user_id))
   conn.commit()
   conn.close()


# Menyimpan metode bayar ke cart (dipanggil saat user pilih metode)
def simpan_metode_bayar_di_cart(user_id, metode_bayar):
   conn = sqlite3.connect(DB_FILE)
   c = conn.cursor()
   c.execute(
       """
        UPDATE cart
        SET metode_bayar = ?
        WHERE user_id = ? AND status = 'pending'
    """, (metode_bayar, user_id))
   conn.commit()
   conn.close()


# Ambil kode bayar + metode bayar sekaligus
def ambil_kode_dan_metode_bayar(user_id):
   conn = sqlite3.connect(DB_FILE)
   c = conn.cursor()
   c.execute(
       """
        SELECT kode_bayar, metode_bayar 
        FROM cart 
        WHERE user_id = ? AND status = 'pending' 
        LIMIT 1
    """, (user_id, ))
   row = c.fetchone()
   conn.close()
   return (row[0], row[1]) if row else (None, None)


def get_pending_payment(user_id):
   conn = sqlite3.connect(DB_FILE)
   c = conn.cursor()
   c.execute(
       """
        SELECT order_id, expected_nominal, status 
        FROM pending_payment 
        WHERE user_id = ?
    """, (user_id, ))
   row = c.fetchone()
   conn.close()
   return row


def clear_pending_payment(user_id):
   conn = sqlite3.connect(DB_FILE)
   c = conn.cursor()
   c.execute("DELETE FROM pending_payment WHERE user_id = ?", (user_id, ))
   conn.commit()
   conn.close()


# Ambil cart pending
def get_cart(user_id):
   conn = sqlite3.connect(DB_FILE)
   c = conn.cursor()
   c.execute(
       """
        SELECT id, nama_produk, harga 
        FROM cart 
        WHERE user_id = ? AND status = 'pending'
    """, (user_id, ))
   items = c.fetchall()
   conn.close()
   return items


def get_cart_total(user_id: int) -> int:
   conn = sqlite3.connect(DB_FILE)
   c = conn.cursor()
   c.execute(
       """
        SELECT COALESCE(SUM(harga), 0)
        FROM cart
        WHERE user_id = ? AND status = 'pending'
    """, (user_id, ))
   total = c.fetchone()[0] or 0
   conn.close()
   return int(total)


def delete_item(item_id):
   conn = sqlite3.connect(DB_FILE)
   c = conn.cursor()
   c.execute("DELETE FROM cart WHERE id = ?", (item_id, ))
   conn.commit()
   conn.close()


def clear_cart(user_id):
   conn = sqlite3.connect(DB_FILE)
   c = conn.cursor()
   c.execute("DELETE FROM cart WHERE user_id = ? AND status = 'pending'",
             (user_id, ))
   conn.commit()
   conn.close()


def mark_cart_done(user_id):
   conn = sqlite3.connect(DB_FILE)
   c = conn.cursor()
   c.execute(
       """
        UPDATE cart 
        SET status = 'done' 
        WHERE user_id = ? AND status = 'pending'
    """, (user_id, ))
   conn.commit()
   conn.close()


# Fungsi memasukkan ke cart
def add_to_cart(user_id, username, nama_produk, harga, metode_bayar=None):
   conn = sqlite3.connect(DB_FILE)
   c = conn.cursor()
   c.execute(
       """
        INSERT INTO cart (user_id, username, nama_produk, harga, status, metode_bayar)
        VALUES (?, ?, ?, ?, 'pending', ?)
    """, (user_id, username, nama_produk, harga, metode_bayar))
   conn.commit()
   conn.close()
