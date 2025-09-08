from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext  # kalau kamu pakai context di tempat lain

# fungsi-fungsi internal proyekmu
from config import MENU          # kamu panggil di url tombol
from db import add_to_cart, get_cart          # atau dari mana pun get_cart berasal
from utils import safe_reply     # kamu panggil di else terakhir

async def kirim_nota(update: Update, user_id: int):
    user = update.effective_user
    username = user.username or user.first_name or "TanpaNama"

    items = get_cart(user_id)
    if not items:
        text = f"👤 *Pemesan:* @{username}\n\nBelum ada pesanan."
        keyboard = [[InlineKeyboardButton("➕ Tambah Pesanan", url=MENU)]]
    else:
        total = sum(h for _, _, h in items)
        daftar = "\n".join([
            f"{i+1}. {nama} - Rp {harga:,}"
            for i, (_, nama, harga) in enumerate(items)
        ])
        text = f"👤 *Pemesan:* @{username}\n\n🧾 *Nota Pesanan:*\n\n{daftar}\n\n💰 *Total:* Rp {total:,}"

        tombol_items = [[
            InlineKeyboardButton(f"❌ Hapus {nama}",
                                 callback_data=f"hapus_{item_id}")
        ] for item_id, nama, _ in items]

        tombol_actions = [[InlineKeyboardButton("➕ Tambah Pesanan", url=MENU)],
                          [
                              InlineKeyboardButton("✅ Cukup, Lanjut Bayar",
                                                   callback_data="bayar")
                          ]]

        keyboard = tombol_items + tombol_actions

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard))
    else:

        await safe_reply(update=update,
                         text=text,
                         parse_mode="Markdown",
                         reply_markup=InlineKeyboardMarkup(keyboard))