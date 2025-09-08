import logging
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ---------------- CONFIG ----------------
BOT_TOKEN = "8265882511:AAHaDn4aR6DZi8z-QVV9LGVcwQpIiODKhM8"

# ---------------- LOGGING ----------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# ---------------- DATABASE ----------------
conn = sqlite3.connect("chat.db", check_same_thread=False)
c = conn.cursor()

# Chat mode: user in/out
c.execute('''
CREATE TABLE IF NOT EXISTS chat_mode (
    user_id INTEGER PRIMARY KEY,
    active INTEGER
)
''')

# Messages mapping: user_message_id ↔ group_message_id
c.execute('''
CREATE TABLE IF NOT EXISTS messages (
    user_id INTEGER,
    user_message_id INTEGER,
    group_message_id INTEGER,
    content TEXT
)
''')

# Admin group ID
c.execute('''
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)
''')
conn.commit()

def set_admin_group_id(group_id: int):
    logger.debug(f"Setting ADMIN_GROUP_ID = {group_id}")
    c.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", ("ADMIN_GROUP_ID", str(group_id)))
    conn.commit()

def get_admin_group_id():
    c.execute("SELECT value FROM settings WHERE key='ADMIN_GROUP_ID'")
    row = c.fetchone()
    if row:
        return int(row[0])
    return None

# ---------------- HELPERS ----------------
def is_user_in_chat(user_id):
    c.execute("SELECT active FROM chat_mode WHERE user_id=?", (user_id,))
    row = c.fetchone()
    return row is not None and row[0] == 1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug(f"/start called by user {update.effective_user.id}")
    keyboard = [[InlineKeyboardButton("Chat dengan Admin", callback_data="start_chat")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Selamat datang! Pilih opsi:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.debug(f"Button pressed by {user_id} with data={query.data}")

    if query.data == "start_chat":
        c.execute("INSERT OR REPLACE INTO chat_mode(user_id, active) VALUES (?, ?)", (user_id, 1))
        conn.commit()
        logger.debug(f"User {user_id} masuk mode chat")
        keyboard = [[InlineKeyboardButton("Keluar dari mode chat", callback_data="exit_chat")]]
        await query.edit_message_text("Anda sekarang dapat chat dengan Admin.", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "exit_chat":
        c.execute("DELETE FROM chat_mode WHERE user_id=?", (user_id,))
        conn.commit()
        logger.debug(f"User {user_id} keluar dari mode chat")
        await query.edit_message_text("Anda keluar dari mode chat.")

# ---------------- HANDLER PESAN USER ----------------
async def forward_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    message_id = update.message.message_id
    logger.debug(f"Received message from user {user_id} message_id={message_id}")

    if not is_user_in_chat(user_id):
        logger.debug(f"User {user_id} tidak dalam mode chat. Pesan diabaikan.")
        return

    ADMIN_GROUP_ID = get_admin_group_id()
    if not ADMIN_GROUP_ID:
        logger.warning("ADMIN_GROUP_ID belum diset. Tolak forward pesan.")
        return

    msg = update.message

    # Forward semua jenis pesan
    try:
        forwarded = await msg.forward(chat_id=ADMIN_GROUP_ID)
        logger.debug(f"Forwarded message {message_id} from user {user_id} to group {ADMIN_GROUP_ID} as {forwarded.message_id}")
        
        # Simpan mapping di DB
        content_desc = msg.text or msg.caption or "MEDIA"
        c.execute("INSERT INTO messages(user_id, user_message_id, group_message_id, content) VALUES (?, ?, ?, ?)",
                  (user_id, message_id, forwarded.message_id, content_desc))
        conn.commit()
        logger.debug(f"Saved message mapping in DB for user {user_id}, message_id {message_id}")
    except Exception as e:
        logger.error(f"Gagal forward pesan user {user_id} message_id {message_id}: {e}")

# ---------------- HANDLER REPLY ADMIN ----------------
async def handle_group_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ADMIN_GROUP_ID = get_admin_group_id()
    if update.message.chat_id != ADMIN_GROUP_ID or not update.message.reply_to_message:
        return

    reply_to_id = update.message.reply_to_message.message_id
    c.execute("SELECT user_id FROM messages WHERE group_message_id=?", (reply_to_id,))
    row = c.fetchone()
    if row:
        user_id = row[0]
        try:
            await context.bot.send_message(chat_id=user_id, text=update.message.text or "MEDIA")
            logger.debug(f"Forwarded admin reply from group {ADMIN_GROUP_ID} to user {user_id}")
        except Exception as e:
            logger.error(f"Gagal forward reply ke user {user_id}: {e}")

# ---------------- HANDLER DYNAMIC ADMIN GROUP ----------------
async def defgroupid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text("Silakan kirim ID grup yang akan dijadikan ADMIN_GROUP_ID:")
    
    # Tunggu satu pesan dari user
    def check(msg: Update):
        return msg.message.chat.id == user_id
    
    msg = await context.bot.wait_for_message(filters=filters.ALL, timeout=60)
    try:
        new_group_id = int(msg.text)
        set_admin_group_id(new_group_id)
        await msg.reply_text(f"ADMIN_GROUP_ID telah diubah menjadi {new_group_id}")
    except Exception as e:
        logger.error(f"Gagal set ADMIN_GROUP_ID: {e}")
        await msg.reply_text("Gagal menyimpan ADMIN_GROUP_ID. Pastikan format ID benar.")

# ---------------- MAIN ----------------
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(CommandHandler("defgroupid", defgroupid))
app.add_handler(MessageHandler(filters.ALL & ~filters.StatusUpdate.ALL, forward_user_message))
app.add_handler(MessageHandler(filters.ALL & filters.ChatType.GROUP & filters.Reply.ALL, handle_group_reply))

logger.info("Bot starting...")
app.run_polling()

