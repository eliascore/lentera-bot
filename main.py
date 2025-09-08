# main.py
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import BOT_TOKEN
from handlers.forwarder import forward_user_message, handle_group_reply, button_handler, defgroupid, handle_group_id_input, debuggroup, waiting_for_group_id, handle_private_message
from db import init_db, get_admin_group_id, is_user_in_chat

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
    user_id = update.effective_user.id
    logger.debug(f"/start called by user {update.effective_user.id}")

    if not is_user_in_chat(user_id):
        keyboard = [[InlineKeyboardButton("Chat dengan Admin", callback_data="start_chat")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Selamat datang! Pilih opsi:", reply_markup=reply_markup)
    else:
        keyboard = [[InlineKeyboardButton("Keluar dari mode chat", callback_data="exit_chat")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Halo! Kamu dalam mode chat dengan admin.", reply_markup=reply_markup)

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("debuggroup", debuggroup))
app.add_handler(CommandHandler("defgroupid", defgroupid))
app.add_handler(CallbackQueryHandler(button_handler))

app.add_handler(MessageHandler(filters.ALL, handle_private_message, block=False))

# ---------------- RUN ----------------
logger.info("Bot starting polling...")
app.run_polling()

