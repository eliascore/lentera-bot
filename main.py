# main.py
import logging
import asyncio
import os
import sqlite3

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import BOT_TOKEN, MENU, RENDER_EXTERNAL_HOSTNAME
from handlers.forwarder import (
    forward_user_message,
    handle_group_reply,
    defgroupid,
    handle_group_id_input,
    debuggroup,
    waiting_for_group_id,
    handle_private_message,
)
from db import init_db, get_admin_group_id, is_user_in_chat, add_to_cart, get_cart
from produk import produk
from utils import safe_reply
from handlers.nota import kirim_nota
from handlers.tombol import tombol_handler

# ---------------- LOGGING ----------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# ---------------- DATABASE ----------------
init_db()
logger.info("Database initialized")

# ---------------- APPLICATION ----------------
app = Application.builder().token(BOT_TOKEN).build()

# ---------------- HANDLERS ----------------


# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.debug(f"/start called by user {update.effective_user.id}")
    username = (
        update.effective_user.username
        or update.effective_user.first_name
        or "TanpaNama"
    )

    # kalau ini dipicu dari tombol, edit pesan lama
    if update.callback_query:
        query = update.callback_query
        await query.answer()  # supaya loading di tombol hilang

        keyboard = [
            [InlineKeyboardButton("Mau Lihat Katalog 📖", url=MENU)],
            [InlineKeyboardButton("Chat dengan Admin", callback_data="start_chat")],
        ]
        await query.edit_message_text(
            text="Halo! Apa yang kamu butuhkan? 😸",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # kalau dipicu dari /start langsung
    args = context.args
    if args:
        item = args[0]
        if item in produk:
            nama_produk, harga = produk[item]
            add_to_cart(user_id, username, nama_produk, harga)
            await kirim_nota(update, user_id)
            return

    if is_user_in_chat(user_id):
        keyboard = [[InlineKeyboardButton("Keluar dari mode chat", callback_data="exit_chat")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Halo! Kamu dalam mode chat dengan admin.", reply_markup=reply_markup
        )
        return

    keyboard = [
        [InlineKeyboardButton("Mau Lihat Katalog 📖", url=MENU)],
        [InlineKeyboardButton("Chat dengan Admin", callback_data="start_chat")],
    ]
    await safe_reply(
        update=update,
        text="Halo! Apa yang kamu butuhkan? 😸",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ---------------- REGISTER HANDLERS ----------------
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("debuggroup", debuggroup))
app.add_handler(CommandHandler("defgroupid", defgroupid))
app.add_handler(CallbackQueryHandler(start, pattern="^start$"))
app.add_handler(CallbackQueryHandler(tombol_handler))
app.add_handler(MessageHandler(filters.ALL, handle_private_message, block=False))


# ---------------- ENTRYPOINT ----------------
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", "8443"))
    HOST = os.environ.get("HOST", "lentera-bot.onrender.com")  # domain render
    WEBHOOK_PATH = "webhook"
    WEBHOOK_URL = f"https://{HOST}/{WEBHOOK_PATH}"

    logger.info(f"Starting webhook on port {PORT} with URL {WEBHOOK_URL}")
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_PATH,
        webhook_url=WEBHOOK_URL,
        max_connections=40,
    )
