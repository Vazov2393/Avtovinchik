import os
import telebot
from geopy.geocoders import Nominatim

TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("TOKEN") or "ВАШ_ТОКЕН"
MY_ADMIN_ID = 0

bot = telebot.TeleBot(TOKEN)
geolocator = Nominatim(user_agent="avtovinchik_v8", timeout=5)

DB_DIR = os.environ.get("DATA_DIR", ".")
os.makedirs(DB_DIR, exist_ok=True)
DB = os.path.join(DB_DIR, "cars.db")

temp = {}
