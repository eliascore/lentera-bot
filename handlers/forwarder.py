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
    if update.message.chat_id != ADMIN_GROUP_ID or not update.message.reply_to_message:
        return
    
    msg = update.message

    original = msg.reply_to_message
    forwarded_from = original.forward_origin
    if not forwarded_from:
        return

    # Cek apakah ini pesan dari user hidden/forward
    if forwarded_from.type != "hidden_user":
        return

    # Ambil username/nama asli user dari forward origin
    sender_name = forwarded_from.sender_user_name
    logger.debug(f"Admin reply to {sender_name}: {msg.text}")

    # Cari user_id dari mapping message (wajib ada fungsi mapping di sistem)
    user_id = get_user_by_group_message_id(original.message_id)  # asumsi ada fungsi ini
    if not user_id:
        logger.warning("Tidak bisa menemukan user_id dari reply admin.")
        return
    
    if isinstance(user_id, tuple):
        user_id = user_id[0]

    # Jika admin ketik "/end", akhiri mode chat
    if msg.text.strip() == "/end":
        from db import conn
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_mode WHERE user_id=?", (user_id,))
        conn.commit()
        logger.debug(f"Mode chat user {user_id} dihapus (admin mengakhiri).")

        keyboard = [[InlineKeyboardButton("🏠 Menu Utama", callback_data="start")]]
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ Admin mengakhiri chat.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Gagal kirim pesan akhir ke user {user_id}: {e}")
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

# -------------------- /debuggroup --------------------
async def debuggroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    chat_type = chat.type
    chat_id = chat.id
    logger.debug(f"/debuggroup called in chat_id={chat_id} type={chat_type}")
    await update.message.reply_text(
        f"Chat info:\nType: {chat_type}\nID: {chat_id}"
    )