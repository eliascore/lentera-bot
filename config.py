import os
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")

if not BOT_TOKEN:
  raise ValueError("❌ TOKEN Telegram belum diatur di environment variable.")
MENU = "https://t.me/lenteraword/208"

DB_FILE = "chat.db"

# kata kunci OCR
KEYWORDS = ["WR BU IPAT", "MORK"]
