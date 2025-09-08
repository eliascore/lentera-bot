# handlers/forwarder.py
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from db import is_user_in_chat, get_admin_group_id, save_message_mapping, get_user_by_group_message_id, set_admin_group_id
from telegram.ext import CallbackQueryHandler

# ---------------- LOGGING ----------------
logger = logging.getLogger(__name__)

# ---------------- BUTTON HANDLER ----------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    logger.debug(f"Button pressed by {user_id} with data={query.data}")

    if query.data == "start_chat":
        from db import conn
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO chat_mode(user_id, active) VALUES (?, ?)", (user_id, 1))
        conn.commit()
        logger.debug(f"User {user_id} masuk mode chat")
        keyboard = [[InlineKeyboardButton("Keluar dari mode chat", callback_data="exit_chat")]]
        await query.edit_message_text("Anda sekarang dapat chat dengan Admin.", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "exit_chat":
        from db import conn
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_mode WHERE user_id=?", (user_id,))
        conn.commit()
        logger.debug(f"User {user_id} keluar dari mode chat")
        await query.edit_message_text("Anda keluar dari mode chat.")

# ---------------- FORWARD USER MESSAGE ----------------
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

    try:
        forwarded = await msg.forward(chat_id=ADMIN_GROUP_ID)
        logger.debug(f"Forwarded message {message_id} from user {user_id} to group {ADMIN_GROUP_ID} as {forwarded.message_id}")
        
        content_desc = msg.text or msg.caption or "MEDIA"
        save_message_mapping(user_id, message_id, forwarded.message_id, content_desc)
    except Exception as e:
        logger.error(f"Gagal forward pesan user {user_id} message_id {message_id}: {e}")

# ---------------- HANDLE ADMIN REPLY ----------------
async def handle_group_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ADMIN_GROUP_ID = get_admin_group_id()
    if update.message.chat_id != ADMIN_GROUP_ID or not update.message.reply_to_message:
        return

    reply_to_id = update.message.reply_to_message.message_id
    row = get_user_by_group_message_id(reply_to_id)
    if row:
        user_id, user_message_id = row
        try:
            if update.message.text:
                await context.bot.send_message(chat_id=user_id, text=update.message.text)
            elif update.message.sticker:
                await context.bot.send_sticker(chat_id=user_id, sticker=update.message.sticker.file_id)
            elif update.message.photo:
                photo = update.message.photo[-1].file_id
                await context.bot.send_photo(chat_id=user_id, photo=photo, caption=update.message.caption)
            elif update.message.video:
                await context.bot.send_video(chat_id=user_id, video=update.message.video.file_id, caption=update.message.caption)
            elif update.message.document:
                await context.bot.send_document(chat_id=user_id, document=update.message.document.file_id, caption=update.message.caption)
            elif update.message.audio:
                await context.bot.send_audio(chat_id=user_id, audio=update.message.audio.file_id)
            elif update.message.voice:
                await context.bot.send_voice(chat_id=user_id, voice=update.message.voice.file_id)
            else:
                await context.bot.send_message(chat_id=user_id, text="MEDIA")
            logger.debug(f"Forwarded admin reply from group {ADMIN_GROUP_ID} to user {user_id}")
        except Exception as e:
            logger.error(f"Gagal forward reply ke user {user_id}: {e}")
