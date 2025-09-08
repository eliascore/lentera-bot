import sqlite3, asyncio
from io import BytesIO
from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_GROUP_ID, KEYWORDS as keywords
from utils import safe_reply, ocr_image_bytes_mode, extract_rp_amounts
from db import (get_pending_payment, get_cart_total, get_cart, mark_cart_done,
                clear_pending_payment, simpan_message_map,
                ambil_kode_dan_metode_bayar)
from config import DB_FILE


# =======================
# MONITOR FEEDBACK
# =======================
async def monitor_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_name = user.first_name
    from_user = update.message.from_user  # ✅ inisialisasi dulu
    user_id = from_user.id
    username = from_user.username or from_user.full_name

    # Ambil pending payment
    pending = get_pending_payment(user_id)
    if not pending:
        await safe_reply(update=update,
                         text="Tidak ada pembayaran yang sedang ditunggu.")
        return
    order_id, expected_nominal, status = pending

    # Ambil file bukti pembayaran
    if update.message.photo:
        file = await context.bot.get_file(update.message.photo[-1].file_id)
    elif update.message.document:
        file = await context.bot.get_file(update.message.document.file_id)
    else:
        await safe_reply(
            update=update,
            text="⚠️ Tolong kirim gambar atau file bukti pembayaran.")
        return

    file_bytes = await file.download_as_bytearray()

    # 🔧 CEK jika file kosong
    if not file_bytes or len(file_bytes) == 0:
        await safe_reply(
            update=update,
            text="❌ Bukti pembayaran gagal diunduh. Silakan kirim ulang.")
        return

    photo_stream = BytesIO(file_bytes)
    photo_stream.name = "bukti.jpg"
    photo_stream.seek(0)

    #Ambil metode pembayaran dari cart / pending (misal ambil pertama yang pending)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT kode_bayar FROM cart WHERE user_id=? AND status='pending' LIMIT 1",
        (user_id, ))
    row = c.fetchone()
    kode_bayar = row[0] if row else None
    conn.close()

    # Tentukan mode OCR lebih awal
    if kode_bayar and any(m in kode_bayar.upper()
                          for m in ["QRIS", "DANA", "GOPAY"]):
        ocr_mode = "merchant"
    elif not kode_bayar:
        # fallback untuk merchant tanpa kode
        ocr_mode = "merchant"
    else:
        ocr_mode = "kode_bayar"

    # Hanya enforce kode bayar kalau bukan merchant
    if not kode_bayar and ocr_mode != "merchant":
        await safe_reply(
            update=update,
            text="⚠️ Kode bayar tidak ditemukan. Pastikan sudah generate kode."
        )
        return

    # Panggil OCR sekali saja
    try:
        ocr_text = await asyncio.to_thread(ocr_image_bytes_mode,
                                           file_bytes,
                                           mode=ocr_mode,
                                           keywords=keywords)
    except ValueError as e:
        await safe_reply(update=update,
                         text=f"❌ Bukti pembayaran tidak valid.\n{e}")
        return

    # Parsing nominal dari OCR
    rp_amounts = extract_rp_amounts(ocr_text)
    ocr_nominal = max(rp_amounts) if rp_amounts else None
    warning = False

    # Hitung total nominal dari cart (sekali saja)
    total_cart = get_cart_total(user_id)

    if ocr_nominal and abs(ocr_nominal - total_cart) > 100:
        warning = True
        await safe_reply(
            update=update,
            text="⚠️ Mohon upload bukti yang sesuai dengan nominal pesanan.")

    # Ambil rincian cart
    items = get_cart(user_id)
    item_lines = [f"- {nama}: Rp{harga:,.0f}" for _, nama, harga in items]
    rincian_cart_text = "\n".join(item_lines)
    kode_bayar, metode_bayar = ambil_kode_dan_metode_bayar(user_id)

    # Buat caption
    if ocr_nominal:
        caption = (f"📷 Bukti pembayaran dari @{username}\n"
                   f"Dibayar Melalui: {metode_bayar or 'Tidak diketahui'}\n"
                   f"Nominal Pembayaran: Rp{ocr_nominal:,.0f}\n"
                   f"Nominal yang Seharusnya Dibayar: Rp{total_cart:,.0f}\n\n"
                   f"🧾 Rincian Pesanan:\n{rincian_cart_text}")
    else:
        caption = (f"📷 Bukti pembayaran dari @{username}\n"
                   f"Dibayar Melalui: {metode_bayar or 'Tidak diketahui'}\n"
                   f"Nominal tidak terbaca\n\n"
                   f"🧾 Rincian Pesanan:\n{rincian_cart_text}")

    if warning:
        caption = "🚨 !!!PERINGATAN!!! TERDETEKSI FRAUDULENT BUYER\n" + caption

    # Forward ke grup admin
    photo_stream = BytesIO(file_bytes)
    photo_stream.name = "bukti.jpg"
    photo_stream.seek(0)

    # Kirim ke grup admin & simpan message_id
    try:
        sent_msg = await context.bot.send_photo(chat_id=ADMIN_GROUP_ID,
                                                photo=photo_stream,
                                                caption=caption)
        session_id = simpan_message_map(
            group_message_id=sent_msg.message_id,
            user_message_id=update.message.message_id,
            user_id=user_id)
        print(f"[DEBUG] Session ID tersimpan: {session_id}")
        await safe_reply(update=update,
                         text="Sukses! Mohon Tunggu Balasan Admin.")
    except Exception as e:
        await safe_reply(update=update,
                         text=f"❌ Gagal kirim bukti ke admin: {e}")
        return

    # Tandai cart done & hapus pending payment
    mark_cart_done(user_id)
    clear_pending_payment(user_id)