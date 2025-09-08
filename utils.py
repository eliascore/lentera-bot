import requests
import time
from telegram import Update
from telegram.ext import ContextTypes
from config import KEYWORDS

# fungsi OCR
def ocr_image_bytes_mode(img_bytes, mode="merchant", keywords=None):
    """
    OCR image dan verifikasi kata kunci berbeda tergantung mode.
    mode:
        - "merchant": cari kata kunci merchant (MORK / WR Bu Ipat)
        - "kode_bayar": cari kode bayar unik user
    """
    if mode == "merchant":
        # default merchant keywords
        if keywords is None:
            keywords = keywords
    elif mode == "kode_bayar":
        if not keywords:
            raise ValueError(
                "Untuk mode kode_bayar, harus ada keywords (kode bayar user)")
    else:
        raise ValueError("Mode OCR tidak valid")

    # Panggil OCR API
    api_key = "helloworld"
    url = "https://api.ocr.space/parse/image"
    r = requests.post(
        url,
        files={"filename": ("image.jpg", img_bytes, "image/jpeg")},
        data={
            "apikey": api_key,
            "language": "eng",
            "scale": True
        },
        timeout=15)
    result = r.json()
    if result.get("IsErroredOnProcessing"):
        raise ValueError(f"OCR gagal: {result.get('ErrorMessage')}")

    parsed_text = ""
    for p in result.get("ParsedResults", []):
        parsed_text += p.get("ParsedText", "")

    parsed_text_clean = parsed_text.upper()

    # Verifikasi minimal satu keyword ada
    if not any(k.upper() in parsed_text_clean for k in keywords):
        raise ValueError(
            f"OCR tidak valid: minimal salah satu kata kunci {keywords} tidak ditemukan."
        )

    return parsed_text


# Solusi aman update message
# Versi super fleksibel safe_reply
async def safe_reply(*,
                     update=None,
                     context=None,
                     text="",
                     chat_id=None,
                     **kwargs):
    """
    Flexible safe reply:
    - Bisa dipanggil hanya dengan text + optional kwargs (reply_markup, parse_mode, etc.)
    - Jika update/context tersedia, gunakan update.message atau context.bot
    - Jika chat_id diberikan, kirim langsung ke chat_id
    """
    try:
        target_chat_id = chat_id
        if update:
            target_chat_id = getattr(update.effective_chat, "id", None)

        if update and getattr(update, "message", None):
            await update.message.reply_text(text, **kwargs)
        elif context and target_chat_id:
            await context.bot.send_message(chat_id=target_chat_id,
                                           text=text,
                                           **kwargs)
        elif target_chat_id:
            # fallback jika context tidak ada
            from telegram import Bot
            import os
            bot = Bot(token=os.environ["TOKEN"])
            await bot.send_message(chat_id=target_chat_id, text=text, **kwargs)
        else:
            print(
                "safe_reply: Tidak ada chat_id atau context, pesan tidak dikirim:",
                text)
    except Exception as e:
        print("safe_reply: Gagal mengirim pesan:", e)


#untuk generate kode bayar yang masuk deskripsi
from datetime import datetime
import hashlib


def generate_kode_bayar(nominal, secret="MYS3CR3T"):
    """
    Generate kode bayar lebih aman:
    - kombinasi tanggal + nominal + secret key
    - hash SHA256
    - ambil 8 karakter pertama hex
    """
    now = datetime.now()
    tanggal = now.strftime("%y%m%d%H%M")  # YYMMDD + jam menit

    data = f"{tanggal}{nominal}{secret}"
    kode_hash = hashlib.sha256(data.encode()).hexdigest()  # hash SHA256
    kode_bayar = kode_hash[:8].upper()  # ambil 8 karakter, uppercase

    return kode_bayar


def obfuscate_kode(kode):
    # Ganti beberapa huruf dengan angka mirip
    mapping = {"A": "4", "E": "3", "I": "1", "O": "0", "S": "5"}
    return "".join(mapping.get(c, c) for c in kode)


#dapatkan grup id dengan /debuggroup
async def debug_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    print(f"[DEBUG] Chat ID: {chat.id}")
    print(f"[DEBUG] Chat type: {chat.type}"
          )  # group, supergroup, private, channel
    print(f"[DEBUG] Chat title: {chat.title}")
    print(f"[DEBUG] From user: {user.id} - {user.username}")

    # Kirim balik ke chat agar bisa lihat di Telegram
    await update.message.reply_text(
        f"[DEBUG] Chat ID: {chat.id}\nChat type: {chat.type}\nChat title: {chat.title}"
    )


#monitor hasil OCR untuk ekstraksi angka rupiah
import re


def extract_rp_amounts(ocr_text):
    # Normalisasi O/o -> 0
    normalized_text = re.sub(r'[oO]', '0', ocr_text)
    print(f"[DEBUG] Normalized OCR Text:\n{normalized_text}")

    # Tangkap semua teks setelah Rp sampai spasi/baris berikutnya
    matches = re.findall(r"Rp[\s\.]*([0-9.,Oo]+)",
                         normalized_text,
                         flags=re.IGNORECASE)

    hasil = []
    for m in matches:
        clean = m.upper().replace("O", "0")  # sekali lagi pastikan O jadi 0
        clean = clean.replace(".", "").replace(",", ".")
        try:
            angka = float(clean)
            if angka >= 100:  # minimal Rp100 biar gak tangkap angka kecil random
                hasil.append(angka)
        except ValueError:
            continue

    print(f"[DEBUG] OCR Detected Nominals: {hasil}")
    return hasil


def create_order_id(user_id: int) -> str:
    # format gampang dilacak: UNIXTIME-USERID
    return f"INV-{int(time.time())}-{user_id}"