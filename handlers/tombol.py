import sqlite3
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, CallbackQueryHandler

from config import DB_FILE, MENU
from handlers.nota import kirim_nota
from db import is_user_in_chat, get_admin_group_id, save_message_mapping, get_user_by_group_message_id, set_admin_group_id, delete_item, get_cart, simpan_metode_bayar_di_cart, simpan_kode_bayar_di_cart, save_pending_payment
from utils import generate_kode_bayar, obfuscate_kode, create_order_id
from config import DB_FILE

# ---------------- LOGGING ----------------
logger = logging.getLogger(__name__)

async def tombol_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.effective_user.username or update.effective_user.first_name or "TanpaNama"
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

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
        keyboard = [[InlineKeyboardButton("🏠 Menu Utama", callback_data="start")]]
        await query.edit_message_text("Anda keluar dari mode chat.", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("hapus_"):
        item_id = int(query.data.split("_")[1])
        delete_item(item_id)
        await kirim_nota(update, query.from_user.id)

    elif query.data == "bayar":
        items = get_cart(query.from_user.id)
        if not items:
            await query.message.reply_text("Belum ada pesanan.")
            return

        total = sum(harga for _, _, harga in items)
        daftar = "\n".join([
            f"{i+1}. {nama} - Rp {harga:,}"
            for i, (_, nama, harga) in enumerate(items)
        ])
        text = f"🧾 *Nota Pesanan:*\n\n{daftar}\n\n💰 *Total:* Rp {total:,}"

        keyboard = [
            [InlineKeyboardButton("QRIS", callback_data="pay_qris")],
            [InlineKeyboardButton("ShopeePay", callback_data="pay_shopeepay")],
            [InlineKeyboardButton("DANA", callback_data="pay_dana")],
            [InlineKeyboardButton("OVO", callback_data="pay_ovo")],
            [InlineKeyboardButton("GoPay", callback_data="pay_gopay")],
        ]
        await query.message.reply_text(
            text=f"{text}\n\n💵 Silakan pilih metode pembayaran:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("pay_"):
        metode = query.data.replace("pay_", "").upper()

        # Kirim QR code atau nomor sesuai metode
        if metode == "QRIS" or metode == "DANA":
            # 1️⃣ Ambil total nominal
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute(
                "SELECT SUM(harga) FROM cart WHERE user_id=? AND status='pending'",
                (user_id, ))
            row = c.fetchone()
            conn.close()
            nominal = row[0] if row and row[0] is not None else 0

            if nominal <= 0:
                await query.message.reply_text(
                    "Keranjangmu kosong atau tidak ada yang perlu dibayar.")
                return

            save_pending_payment(user_id, create_order_id(user_id), nominal)
            simpan_metode_bayar_di_cart(user_id, metode)

            file_path = "QRIS.jpg"
            with open(file_path, "rb") as f:
                await query.message.reply_photo(
                    photo=f,
                    caption=
                    "Scan QR Code untuk pembayaran, lalu kirim bukti dengan caption 'Bukti Pembayaran' tanpa tanda kutip."
                )

        elif metode == "GOPAY":
            # 1️⃣ Ambil total nominal
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute(
                "SELECT SUM(harga) FROM cart WHERE user_id=? AND status='pending'",
                (user_id, ))
            row = c.fetchone()
            conn.close()
            nominal = row[0] if row and row[0] is not None else 0

            if nominal <= 0:
                await query.message.reply_text(
                    "Keranjangmu kosong atau tidak ada yang perlu dibayar.")
                return

            save_pending_payment(user_id, create_order_id(user_id), nominal)
            simpan_metode_bayar_di_cart(user_id, metode)

            file_path = "QR_GOPAY.png"
            with open(file_path, "rb") as f:
                await query.message.reply_photo(
                    photo=f,
                    caption=
                    "Scan QR Code untuk pembayaran, lalu kirim bukti dengan caption 'Bukti Pembayaran' tanpa tanda kutip."
                )

        elif metode in ["SHOPEEPAY", "OVO"]:
            # 1️⃣ Ambil total nominal
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute(
                "SELECT SUM(harga) FROM cart WHERE user_id=? AND status='pending'",
                (user_id, ))
            row = c.fetchone()
            conn.close()
            nominal = row[0] if row and row[0] is not None else 0

            if nominal <= 0:
                await query.message.reply_text(
                    "Keranjangmu kosong atau tidak ada yang perlu dibayar.")
                return

            # Generate kode bayar rumit
            kode_bayar = obfuscate_kode(generate_kode_bayar(nominal))

            # Safe username: pakai username kalau ada, kalau tidak pakai nama depan
            username_safe = username if username else user.first_name
            kode_bayar_str = f"@{username_safe}{kode_bayar}"

            # Simpan ke cart
            simpan_kode_bayar_di_cart(user_id, username_safe, kode_bayar_str)
            save_pending_payment(user_id, create_order_id(user_id), nominal)
            simpan_metode_bayar_di_cart(user_id, metode)

            nomor = "+6285713869358"
            await query.message.reply_text(
                f"💰 Bayarkan ke nomor berikut: {nomor}\n"
                f"🆔 Kode Bayar: {kode_bayar_str}\n\n"
                f"⚠️ Pastikan menuliskan Kode Bayar ini di bukti pembayaran agar otomatis terdeteksi.",
                parse_mode="Markdown")