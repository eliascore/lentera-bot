# main.py
import logging
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import BOT_TOKEN
from handlers.forwarder import forward_user_message, handle_group_reply, button_handler
from db import init_db, get_admin_group_id

# ---------------- LOGGING ----------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# ---------------- DATABASE ----------------
init_db()
logger.info("Database initialized")

# ---------------- APPLICATION ----------------
app = ApplicationBuilder().token(BOT_TOKEN).build()

# ---------------- HANDLERS ----------------
from telegram import Update
from telegram.ext import ContextTypes

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.debug(f"/start called by user {update.effective_user.id}")
    keyboard = [[InlineKeyboardButton("Chat dengan Admin", callback_data="start_chat")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Selamat datang! Pilih opsi:", reply_markup=reply_markup)

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.ALL & ~filters.StatusUpdate.ALL, forward_user_message))
app.add_handler(MessageHandler(filters.ALL & filters.ChatType.GROUP & filters.Reply.ALL, handle_group_reply))

# ---------------- RUN ----------------
logger.info("Bot starting polling...")
app.run_polling()

