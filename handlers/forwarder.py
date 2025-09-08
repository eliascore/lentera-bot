# handlers/forwarder.py
import logging
import sqlite3

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from db import is_user_in_chat, get_admin_group_id, save_message_mapping, get_user_by_group_message_id, set_admin_group_id
from telegram.ext import CallbackQueryHandler
from handlers.feedback import monitor_feedback

# ---------------- LOGGING ----------------
logger = logging.getLogger(__name__)

# State sementara user yang sedang set group
waiting_for_group_id = set()

#satu handler privat dan cek kondisi di dalam handler
async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_type = update.message.chat.type if update.message else None
    text = update.message.text or ""
    message = update.effective_message

    if text.startswith("/defgroupid"):
        await defgroupid(update, context)
        return

    # 1️⃣ Private chat - user sedang set group_id
    if chat_type == "private" and user_id in waiting_for_group_id:
        await handle_group_id_input(update, context)
        return

    # Private chat - nota pembayaran
    if message.caption and "bukti pembayaran" in message.caption:
        await monitor_feedback(update, context)
        return
    
        # 2️⃣ Private chat - user biasa, forward ke grup
    if chat_type == "private":
        await forward_user_message(update, context)
        return

    # 3️⃣ Grup chat - admin reply user
    if chat_type in ("group", "supergroup") and update.message.reply_to_message:
        await handle_group_reply(update, context)
        return

    if chat_type in ("group", "supergroup") and text.startswith("/debuggroup"):
        await debuggroup(update, context)
        return

# -------------------- /defgroupid --------------------
async def defgroupid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.debug(f"/defgroupid called by user {user_id}")

    waiting_for_group_id.add(user_id)
    await update.message.reply_text(
        "Kirim ID grup yang ingin dijadikan ADMIN_GROUP_ID sekarang.\n"
        "Hanya satu ID grup yang disimpan."
    )

# -------------------- Handle input grup ID --------------------
async def handle_group_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in waiting_for_group_id:
        return  # bukan dalam mode set grup, abaikan
    
    text = update.message.text.strip()
        # validasi angka
    if not text.lstrip("-").isdigit():
        await update.message.reply_text("ID group harus berupa angka, coba lagi.")
        return

    try:
        group_id = int(text)
        set_admin_group_id(group_id)
        logger.debug(f"Set ADMIN_GROUP_ID = {group_id} oleh user {user_id}")
        await update.message.reply_text(f"ADMIN_GROUP_ID berhasil diset ke {group_id}")
    except ValueError:
        await update.message.reply_text("ID grup tidak valid. Harus berupa angka.")
        logger.warning(f"User {user_id} mengirim ID grup tidak valid: {text}")
    finally:
        waiting_for_group_id.discard(user_id)

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
    msg = update.message

    if not msg or msg.chat_id != ADMIN_GROUP_ID or not msg.reply_to_message:
        return

    original = msg.reply_to_message
    row = get_user_by_group_message_id(original.message_id)
    if not row:
        logger.warning("Tidak bisa menemukan user_id dari reply admin.")
        return

    user_id, user_message_id = row

    # Jika admin ketik "/end"
    if msg.text and msg.text.strip() == "/end":
        from db import conn
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_mode WHERE user_id=?", (user_id,))
        conn.commit()

        keyboard = [[InlineKeyboardButton("🏠 Menu Utama", callback_data="start")]]
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Admin mengakhiri chat.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        logger.debug(f"Mode chat user {user_id} dihapus (admin mengakhiri).")
        return

    # Forward balasan admin ke user
    try:
        if msg.text:
            await context.bot.send_message(chat_id=user_id, text=msg.text, reply_to_message_id=user_message_id)
        elif msg.sticker:
            await context.bot.send_sticker(chat_id=user_id, sticker=msg.sticker.file_id)
        elif msg.photo:
            await context.bot.send_photo(chat_id=user_id, photo=msg.photo[-1].file_id, caption=msg.caption)
        elif msg.video:
            await context.bot.send_video(chat_id=user_id, video=msg.video.file_id, caption=msg.caption)
        elif msg.document:
            await context.bot.send_document(chat_id=user_id, document=msg.document.file_id, caption=msg.caption)
        elif msg.audio:
            await context.bot.send_audio(chat_id=user_id, audio=msg.audio.file_id)
        elif msg.voice:
            await context.bot.send_voice(chat_id=user_id, voice=msg.voice.file_id)
        else:
            await context.bot.send_message(chat_id=user_id, text="(media tidak dikenali)")
        logger.debug(f"Forwarded admin reply from group {ADMIN_GROUP_ID} to user {user_id}")
    except Exception as e:
        logger.error(f"Gagal forward reply ke user {user_id}: {e}")

# -------------------- /debuggroup --------------------
async def debuggroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    chat_type = chat.type
    chat_id = chat.id
    logger.debug(f"/debuggroup called in chat_id={chat_id} type={chat_type}")
    await update.message.reply_text(
        f"Chat info:\nType: {chat_type}\nID: {chat_id}"
    )