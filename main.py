import os
import telebot
from telebot import types
import sqlite3
import math
from geopy.geocoders import Nominatim

TOKEN = os.environ.get('BOT_TOKEN') or os.environ.get('TOKEN') or 'ВАШ_ТОКЕН_ОТ_BOTFATHER'
bot = telebot.TeleBot(TOKEN)
geolocator = Nominatim(user_agent="avtovinchik_bot_v3")

CAR_CATALOG = {
    "Лада (ВАЗ)": ["Приора", "Гранта", "Веста", "Калина", "Нива 4x4 / Legend", "2114 / 2115", "2107 / Классика", "Ларгус", "XRAY"],
    "Toyota": ["Camry", "Corolla", "RAV4", "Land Cruiser", "Land Cruiser Prado", "Avensis", "Mark II", "Chaser", "Solaris / Vitz"],
    "Hyundai": ["Solaris", "Creta", "Elantra", "Sonata", "Tucson", "Santa Fe", "Accent", "Getz"],
    "Kia": ["Rio", "Ceed", "Sportage", "Optima", "K5", "Cerato", "Sorento", "Spectra"],
    "Volkswagen": ["Polo", "Tiguan", "Passat", "Golf", "Jetta", "Touareg", "Transporter"],
    "Skoda": ["Octavia", "Rapid", "Kodiaq", "Superb", "Fabia", "Yeti"],
    "Nissan": ["Qashqai", "X-Trail", "Almera", "Teana", "Juke", "Note", "Murano"],
    "Ford": ["Focus", "Mondeo", "Kuga", "Fiesta", "Fusion", "Transit"],
    "Renault": ["Logan", "Duster", "Sandero", "Megane", "Kaptur", "Arkana"],
    "Chevrolet": ["Cruze", "Lacetti", "Aveo", "Niva", "Cobalt", "Tahoe"],
    "BMW": ["3 серия", "5 серия", "7 серия", "X5", "X3", "X6"],
    "Mercedes-Benz": ["C-класс", "E-класс", "S-класс", "GLC", "GLE", "Sprinter"],
    "Mazda": ["Mazda 3", "Mazda 6", "CX-5", "CX-7", "CX-9"],
    "Mitsubishi": ["Lancer", "Outlander", "Pajero", "ASX", "L200"],
    "Honda": ["Civic", "Accord", "CR-V", "Fit / Jazz"],
    "Audi": ["A4", "A6", "A3", "Q5", "Q7"],
    "ГАЗ": ["Газель Бизнес", "Газель NEXT", "Волга 3110 / 31105", "Соболь"],
    "Chery": ["Tiggo 7 Pro", "Tiggo 4 / 4 Pro", "Tiggo 8 Pro", "Amulet"],
    "Haval": ["Jolion", "F7 / F7x", "H9", "Dargo"],
    "Geely": ["Coolray", "Monjaro", "Atlas / Atlas Pro", "Emgrand"]
}

def init_db():
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS cars (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        photo TEXT,
        brand TEXT,
        model TEXT,
        year INTEGER,
        price INTEGER,
        condition TEXT,
        docs TEXT,
        description TEXT,
        city TEXT,
        lat REAL,
        lon REAL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS filters (
        user_id INTEGER PRIMARY KEY,
        brand TEXT DEFAULT 'Любая',
        model TEXT DEFAULT 'Любая',
        year_from INTEGER DEFAULT 1970,
        year_to INTEGER DEFAULT 2030,
        price_from INTEGER DEFAULT 0,
        price_to INTEGER DEFAULT 99999999,
        city_name TEXT DEFAULT 'Не задан',
        lat REAL,
        lon REAL,
        radius INTEGER DEFAULT 5000,
        docs_only_clean INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS viewed (
        user_id INTEGER,
        car_id INTEGER
    )''')
    conn.commit()
    conn.close()

init_db()
temp_data = {}

def get_user_filter(user_id):
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('SELECT * FROM filters WHERE user_id = ?', (user_id,))
    f = c.fetchone()
    if not f:
        c.execute('INSERT INTO filters (user_id) VALUES (?)', (user_id,))
        conn.commit()
        c.execute('SELECT * FROM filters WHERE user_id = ?', (user_id,))
        f = c.fetchone()
    conn.close()
    return f

def calc_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c)

def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('🚗 Купить авто', '💰 Продать авто')
    markup.row('⚙️ Мой фильтр')
    return markup

def cancel_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add('❌ Отмена')
    return markup

def build_brands_markup(include_any=False):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    if include_any:
        markup.add('Любая')
    brands = list(CAR_CATALOG.keys())
    for i in range(0, len(brands), 2):
        row = brands[i:i+2]
        markup.row(*row)
    markup.row('✍️ Другая марка', '❌ Отмена')
    return markup

def build_models_markup(brand, include_any=False):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    if include_any:
        markup.add('Любая')
    models = CAR_CATALOG.get(brand, [])
    for i in range(0, len(models), 2):
        row = models[i:i+2]
        markup.row(*row)
    markup.row('✍️ Другая модель', '❌ Отмена')
    return markup

def check_cancel(message):
    if message.text == '❌ Отмена':
        if message.chat.id in temp_data:
            del temp_data[message.chat.id]
        bot.send_message(message.chat.id, "Действие отменено. Возвращаемся в главное меню.", reply_markup=main_menu())
        return True
    return False

@bot.message_handler(commands=['start'])
def start(message):
    get_user_filter(message.chat.id)
    bot.send_message(
        message.chat.id,
        "👋 Добро пожаловать на Авторынок!\nВыберите действие в меню ниже:",
        reply_markup=main_menu()
    )

# ================= ИНТЕРАКТИВНОЕ МЕНЮ ФИЛЬТРОВ =================
def send_filter_menu(chat_id, message_id=None):
    f = get_user_filter(chat_id)
    docs_text = "Только чистые" if f[11] == 1 else "Все (включая проблемные)"
    loc_text = f"{f[7]} (+{f[10]} км)" if f[7] != 'Не задан' else "Вся Россия"
    price_to_str = "без потолка" if f[6] >= 99999999 else f"{f[6]:,} ₽".replace(',', ' ')
    price_from_str = f"{f[5]:,} ₽".replace(',', ' ')

    text = (
        "⚙️ **Ваши текущие фильтры поиска:**\n\n"
        f"🚘 **Марка:** {f[1]}\n"
        f"📝 **Модель:** {f[2]}\n"
        f"📅 **Год выпуска:** от {f[3]} до {f[4]}\n"
        f"💰 **Цена:** от {price_from_str} до {price_to_str}\n"
        f"📍 **Локация:** {loc_text}\n"
        f"📄 **Документы:** {docs_text}\n\n"
        "Нажмите на нужный параметр, чтобы изменить его:"
    )

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton(f"🚘 Марка: {f[1]}", callback_data="f_brand"),
        types.InlineKeyboardButton(f"📝 Модель: {f[2]}", callback_data="f_model")
    )
    markup.row(
        types.InlineKeyboardButton(f"📅 Год: {f[3]}-{f[4]}", callback_data="f_year"),
        types.InlineKeyboardButton("💰 Цена от/до", callback_data="f_price")
    )
    markup.row(
        types.InlineKeyboardButton(f"📍 Локация ({f[7]})", callback_data="f_loc"),
        types.InlineKeyboardButton("📄 Документы", callback_data="f_docs")
    )
    markup.row(
        types.InlineKeyboardButton("🔄 Сбросить всё", callback_data="f_reset"),
        types.InlineKeyboardButton("🔍 Показать авто", callback_data="f_search")
    )

    if message_id:
        bot.edit_message_text(text, chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
    else:
        bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == '⚙️ Мой фильтр')
def open_filter_menu(message):
    send_filter_menu(message.chat.id)

def set_f_brand(message):
    if check_cancel(message):
        return
    if not message.text:
        msg = bot.send_message(message.chat.id, "❌ Выберите марку кнопкой или напишите текстом:", reply_markup=build_brands_markup(include_any=True))
        bot.register_next_step_handler(msg, set_f_brand)
        return
    if message.text == '✍️ Другая марка':
        msg = bot.send_message(message.chat.id, "✍️ Напишите название **марки** текстом:", parse_mode='Markdown', reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, set_f_brand_custom)
        return
    val = 'Любая' if message.text.lower() == 'любая' else message.text.strip()
    update_filter_field(message.chat.id, 'brand', val)
    update_filter_field(message.chat.id, 'model', 'Любая')
    bot.send_message(message.chat.id, f"✅ Выбрана марка: **{val}**", parse_mode='Markdown', reply_markup=main_menu())
    send_filter_menu(message.chat.id)

def set_f_brand_custom(message):
    if check_cancel(message):
        return
    if not message.text:
        msg = bot.send_message(message.chat.id, "❌ Напишите марку текстом:", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, set_f_brand_custom)
        return
    val = message.text.strip()
    update_filter_field(message.chat.id, 'brand', val)
    update_filter_field(message.chat.id, 'model', 'Любая')
    bot.send_message(message.chat.id, f"✅ Выбрана марка: **{val}**", parse_mode='Markdown', reply_markup=main_menu())
    send_filter_menu(message.chat.id)

def set_f_model(message):
    if check_cancel(message):
        return
    if not message.text:
        f = get_user_filter(message.chat.id)
        msg = bot.send_message(message.chat.id, "❌ Выберите модель кнопкой:", reply_markup=build_models_markup(f[1], include_any=True))
        bot.register_next_step_handler(msg, set_f_model)
        return
    if message.text == '✍️ Другая модель':
        msg = bot.send_message(message.chat.id, "✍️ Напишите название **модели** текстом:", parse_mode='Markdown', reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, set_f_model_custom)
        return
    val = 'Любая' if message.text.lower() == 'любая' else message.text.strip()
    update_filter_field(message.chat.id, 'model', val)
    bot.send_message(message.chat.id, f"✅ Выбрана модель: **{val}**", parse_mode='Markdown', reply_markup=main_menu())
    send_filter_menu(message.chat.id)

def set_f_model_custom(message):
    if check_cancel(message):
        return
    if not message.text:
        msg = bot.send_message(message.chat.id, "❌ Напишите модель текстом:", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, set_f_model_custom)
        return
    val = message.text.strip()
    update_filter_field(message.chat.id, 'model', val)
    bot.send_message(message.chat.id, f"✅ Выбрана модель: **{val}**", parse_mode='Markdown', reply_markup=main_menu())
    send_filter_menu(message.chat.id)

def set_f_year(message):
    if check_cancel(message):
        return
    if not message.text:
        msg = bot.send_message(message.chat.id, "❌ Напишите два года через пробел (например: `2008 2016`):", parse_mode='Markdown', reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, set_f_year)
        return
    parts = message.text.strip().split()
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute('UPDATE filters SET year_from = ?, year_to = ? WHERE user_id = ?', (int(parts[0]), int(parts[1]), message.chat.id))
        c.execute('DELETE FROM viewed WHERE user_id = ?', (message.chat.id,))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ Годы обновлены!", reply_markup=main_menu())
        send_filter_menu(message.chat.id)
    else:
        msg = bot.send_message(message.chat.id, "❌ Напишите два года через пробел (например: `2008 2016`):", parse_mode='Markdown', reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, set_f_year)

def set_f_price(message):
    if check_cancel(message):
        return
    if not message.text:
        msg = bot.send_message(message.chat.id, "❌ Напишите две суммы через пробел (например: `150000 600000`):", parse_mode='Markdown', reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, set_f_price)
        return
    parts = message.text.strip().split()
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute('UPDATE filters SET price_from = ?, price_to = ? WHERE user_id = ?', (int(parts[0]), int(parts[1]), message.chat.id))
        c.execute('DELETE FROM viewed WHERE user_id = ?', (message.chat.id,))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ Бюджет обновлен!", reply_markup=main_menu())
        send_filter_menu(message.chat.id)
    else:
        msg = bot.send_message(message.chat.id, "❌ Напишите две суммы через пробел без точек и запятых (например: `150000 600000`):", parse_mode='Markdown', reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, set_f_price)

def set_f_loc_step1(message):
    if check_cancel(message):
        return
    lat, lon, city_name = None, None, "Точка на карте"
    if message.location:
        lat, lon = message.location.latitude, message.location.longitude
        try:
            loc = geolocator.reverse(f"{lat}, {lon}", language='ru')
            city_name = loc.raw.get('address', {}).get('city') or loc.raw.get('address', {}).get('town') or "Точка на карте"
        except:
            pass
    elif message.text:
        try:
            loc = geolocator.geocode(message.text.strip())
            if loc:
                lat, lon = loc.latitude, loc.longitude
                city_name = message.text.strip().capitalize()
            else:
                msg = bot.send_message(message.chat.id, "❌ Город не найден. Напишите точнее (например: Абинск):", reply_markup=cancel_markup())
                bot.register_next_step_handler(msg, set_f_loc_step1)
                return
        except:
            msg = bot.send_message(message.chat.id, "❌ Ошибка поиска города. Попробуйте еще раз:", reply_markup=cancel_markup())
            bot.register_next_step_handler(msg, set_f_loc_step1)
            return
    else:
        msg = bot.send_message(message.chat.id, "❌ Отправьте геопозицию или напишите название города:", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, set_f_loc_step1)
        return

    temp_data[message.chat.id] = {'lat': lat, 'lon': lon, 'city_name': city_name}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('50', '100', '200', '500')
    markup.add('❌ Отмена')
    msg = bot.send_message(message.chat.id, f"📍 Выбран город: **{city_name}**.\nВыберите или введите **радиус поиска в км**:", parse_mode='Markdown', reply_markup=markup)
    bot.register_next_step_handler(msg, set_f_loc_step2)

def set_f_loc_step2(message):
    if check_cancel(message):
        return
    if not message.text or not message.text.isdigit():
        msg = bot.send_message(message.chat.id, "❌ Введите радиус цифрами (например: 100):")
        bot.register_next_step_handler(msg, set_f_loc_step2)
        return
    d = temp_data[message.chat.id]
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('UPDATE filters SET city_name = ?, lat = ?, lon = ?, radius = ? WHERE user_id = ?',
              (d['city_name'], d['lat'], d['lon'], int(message.text), message.chat.id))
    c.execute('DELETE FROM viewed WHERE user_id = ?', (message.chat.id,))
    conn.commit()
    conn.close()
    del temp_data[message.chat.id]
    bot.send_message(message.chat.id, "✅ Локация обновлена!", reply_markup=main_menu())
    send_filter_menu(message.chat.id)

def update_filter_field(user_id, field, value):
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute(f'UPDATE filters SET {field} = ? WHERE user_id = ?', (value, user_id))
    c.execute('DELETE FROM viewed WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

# ================= ВЕТКА ПРОДАЖИ =================
@bot.message_handler(func=lambda m: m.text == '💰 Продать авто')
def sell_start(message):
    temp_data[message.chat.id] = {'username': message.from_user.username}
    msg = bot.send_message(message.chat.id, "📸 Отправьте **фотографию** автомобиля:", parse_mode='Markdown', reply_markup=cancel_markup())
    bot.register_next_step_handler(msg, get_photo)

def get_photo(message):
    if check_cancel(message):
        return
    if not message.photo:
        msg = bot.send_message(message.chat.id, "❌ Нужно отправить именно фото! Попробуйте еще раз:", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, get_photo)
        return
    temp_data[message.chat.id]['photo'] = message.photo[-1].file_id
    msg = bot.send_message(message.chat.id, "🚘 Выберите **марку** авто из списка ниже:", parse_mode='Markdown', reply_markup=build_brands_markup(include_any=False))
    bot.register_next_step_handler(msg, get_brand)

def get_brand(message):
    if check_cancel(message):
        return
    if not message.text:
        msg = bot.send_message(message.chat.id, "❌ Пожалуйста, выберите марку кнопкой:", reply_markup=build_brands_markup(include_any=False))
        bot.register_next_step_handler(msg, get_brand)
        return
    if message.text == '✍️ Другая марка':
        msg = bot.send_message(message.chat.id, "✍️ Напишите **марку** авто текстом:", parse_mode='Markdown', reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, get_brand_custom)
        return
    brand = message.text.strip()
    temp_data[message.chat.id]['brand'] = brand
    msg = bot.send_message(message.chat.id, f"📝 Выберите **модель** {brand} из списка:", parse_mode='Markdown', reply_markup=build_models_markup(brand, include_any=False))
    bot.register_next_step_handler(msg, get_model)

def get_brand_custom(message):
    if check_cancel(message):
        return
    if not message.text:
        msg = bot.send_message(message.chat.id, "❌ Напишите марку текстом:", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, get_brand_custom)
        return
    brand = message.text.strip()
    temp_data[message.chat.id]['brand'] = brand
    msg = bot.send_message(message.chat.id, f"📝 Напишите **модель** {brand} текстом:", parse_mode='Markdown', reply_markup=cancel_markup())
    bot.register_next_step_handler(msg, get_model_custom)

def get_model(message):
    if check_cancel(message):
        return
    if not message.text:
        brand = temp_data[message.chat.id].get('brand', '')
        msg = bot.send_message(message.chat.id, "❌ Пожалуйста, выберите модель кнопкой:", reply_markup=build_models_markup(brand, include_any=False))
        bot.register_next_step_handler(msg, get_model)
        return
    if message.text == '✍️ Другая модель':
        msg = bot.send_message(message.chat.id, "✍️ Напишите **модель** авто текстом:", parse_mode='Markdown', reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, get_model_custom)
        return
    temp_data[message.chat.id]['model'] = message.text.strip()
    msg = bot.send_message(message.chat.id, "📅 Укажите **год выпуска** (только цифры, например: 2015):", parse_mode='Markdown', reply_markup=cancel_markup())
    bot.register_next_step_handler(msg, get_year)

def get_model_custom(message):
    if check_cancel(message):
        return
    if not message.text:
        msg = bot.send_message(message.chat.id, "❌ Напишите модель текстом:", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, get_model_custom)
        return
    temp_data[message.chat.id]['model'] = message.text.strip()
    msg = bot.send_message(message.chat.id, "📅 Укажите **год выпуска** (только цифры, например: 2015):", parse_mode='Markdown', reply_markup=cancel_markup())
    bot.register_next_step_handler(msg, get_year)

def get_year(message):
    if check_cancel(message):
        return
    if not message.text or not message.text.isdigit():
        msg = bot.send_message(message.chat.id, "❌ Введите год цифрами (например: 2012):", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, get_year)
        return
    temp_data[message.chat.id]['year'] = int(message.text)
    msg = bot.send_message(message.chat.id, "💵 Укажите **цену в рублях** (только цифры, например: 450000):", parse_mode='Markdown', reply_markup=cancel_markup())
    bot.register_next_step_handler(msg, get_price)

def get_price(message):
    if check_cancel(message):
        return
    if not message.text or not message.text.isdigit():
        msg = bot.send_message(message.chat.id, "❌ Введите цену только цифрами без пробелов:", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, get_price)
        return
    temp_data[message.chat.id]['price'] = int(message.text)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('Отличное / Не требует вложений', 'На ходу / Есть нюансы')
    markup.row('Требует ремонта / Битая', '❌ Отмена')
    msg = bot.send_message(message.chat.id, "🛠 Выберите **состояние** автомобиля:", parse_mode='Markdown', reply_markup=markup)
    bot.register_next_step_handler(msg, get_condition)

def get_condition(message):
    if check_cancel(message):
        return
    if not message.text:
        msg = bot.send_message(message.chat.id, "❌ Выберите состояние кнопкой:")
        bot.register_next_step_handler(msg, get_condition)
        return
    temp_data[message.chat.id]['condition'] = message.text.strip()
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('✅ Чистые (без проблем)', '⚠️ Есть проблемы (запрет, утиль, без ПТС)')
    markup.add('❌ Отмена')
    msg = bot.send_message(message.chat.id, "📄 Что с **документами**?", parse_mode='Markdown', reply_markup=markup)
    bot.register_next_step_handler(msg, get_docs)

def get_docs(message):
    if check_cancel(message):
        return
    if not message.text:
        msg = bot.send_message(message.chat.id, "❌ Выберите статус документов кнопкой:")
        bot.register_next_step_handler(msg, get_docs)
        return
    temp_data[message.chat.id]['docs'] = message.text.strip()
    msg = bot.send_message(message.chat.id, "✍️ Напишите **описание** (двигатель, коробка, косяки, торг):", parse_mode='Markdown', reply_markup=cancel_markup())
    bot.register_next_step_handler(msg, get_desc)

def get_desc(message):
    if check_cancel(message):
        return
    if not message.text:
        msg = bot.send_message(message.chat.id, "❌ Напишите описание текстом:", reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, get_desc)
        return
    temp_data[message.chat.id]['description'] = message.text.strip()
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_geo = types.KeyboardButton("📍 Отправить мою геопозицию", request_location=True)
    markup.add(btn_geo)
    markup.add('❌ Отмена')
    msg = bot.send_message(message.chat.id, "🌍 Нажмите кнопку ниже, чтобы отправить **геопозицию** авто, или напишите **название города** текстом (например: Абинск):", parse_mode='Markdown', reply_markup=markup)
    bot.register_next_step_handler(msg, get_location_sell)

def get_location_sell(message):
    if check_cancel(message):
        return
    lat, lon, city_name = None, None, "Не указан"
    if message.location:
        lat, lon = message.location.latitude, message.location.longitude
        try:
            loc = geolocator.reverse(f"{lat}, {lon}", language='ru')
            city_name = loc.raw.get('address', {}).get('city') or loc.raw.get('address', {}).get('town') or "Точка на карте"
        except:
            city_name = "Точка на карте"
    elif message.text:
        try:
            loc = geolocator.geocode(message.text.strip())
            if loc:
                lat, lon = loc.latitude, loc.longitude
                city_name = message.text.strip().capitalize()
            else:
                msg = bot.send_message(message.chat.id, "❌ Город не найден. Напишите точнее (например: Краснодарский край, Абинск):", reply_markup=cancel_markup())
                bot.register_next_step_handler(msg, get_location_sell)
                return
        except:
            msg = bot.send_message(message.chat.id, "❌ Ошибка поиска города. Попробуйте отправить геопозицию кнопкой:", reply_markup=cancel_markup())
            bot.register_next_step_handler(msg, get_location_sell)
            return
    else:
        msg = bot.send_message(message.chat.id, "❌ Отправьте геопозицию кнопкой или напишите город текстом:")
        bot.register_next_step_handler(msg, get_location_sell)
        return

    d = temp_data[message.chat.id]
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('''INSERT INTO cars (user_id, username, photo, brand, model, year, price, condition, docs, description, city, lat, lon)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (message.chat.id, d['username'], d['photo'], d['brand'], d['model'], d['year'],
               d['price'], d['condition'], d['docs'], d['description'], city_name, lat, lon))
    conn.commit()
    conn.close()
    del temp_data[message.chat.id]

    bot.send_message(message.chat.id, "✅ **Объявление успешно опубликовано!**", parse_mode='Markdown', reply_markup=main_menu())

# ================= ЛЕНТА АНКЕТ (ДАЙВИНЧИК) =================
@bot.message_handler(func=lambda m: m.text == '🚗 Купить авто')
def buy_cars(message):
    show_next_car(message.chat.id)

def show_next_car(user_id):
    f = get_user_filter(user_id)
    _, f_brand, f_model, y_from, y_to, p_from, p_to, city_name, u_lat, u_lon, radius, only_clean = f

    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    query = '''SELECT * FROM cars 
               WHERE year >= ? AND year <= ? 
               AND price >= ? AND price <= ? 
               AND id NOT IN (SELECT car_id FROM viewed WHERE user_id = ?)'''
    params = [y_from, y_to, p_from, p_to, user_id]

    if f_brand != 'Любая':
        query += ' AND LOWER(brand) LIKE ?'
        params.append(f'%{f_brand.lower()}%')
    if f_model != 'Любая':
        query += ' AND LOWER(model) LIKE ?'
        params.append(f'%{f_model.lower()}%')
    if only_clean == 1:
        query += " AND docs LIKE '%Чистые%'"

    c.execute(query, params)
    cars = c.fetchall()
    
    found_car = None
    dist_text = ""
    for car in cars:
        if city_name == 'Не задан' or not u_lat or not u_lon:
            found_car = car
            dist_text = f"📍 Город: {car[11]}"
            break
        elif car[12] and car[13]:
            dist = calc_distance(u_lat, u_lon, car[12], car[13])
            if dist <= radius:
                found_car = car
                dist_text = f"📍 Город: {car[11]} (~{dist} км от вас)"
                break

    if not found_car:
        conn.close()
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⚙️ Изменить фильтры", callback_data="open_filters"))
        bot.send_message(user_id, "🏁 Подходящих машин по вашим фильтрам больше нет!", reply_markup=markup)
        return

    c.execute('INSERT INTO viewed (user_id, car_id) VALUES (?, ?)', (user_id, found_car[0]))
    conn.commit()
    conn.close()

    price_formatted = f"{found_car[7]:,}".replace(',', ' ')
    caption = (
        f"🚘 **{found_car[4]} {found_car[5]}, {found_car[6]} г.**\n"
        f"💰 Цена: **{price_formatted} ₽**\n"
        f"{dist_text}\n"
        f"🛠 Состояние: {found_car[8]}\n"
        f"📄 Документы: {found_car[9]}\n\n"
        f"📝 {found_car[10]}"
    )

    markup = types.InlineKeyboardMarkup()
    btn_like = types.InlineKeyboardButton("❤️ Контакт продавца", callback_data=f"like_{found_car[0]}")
    btn_next = types.InlineKeyboardButton("👎 Дальше", callback_data="next_car")
    btn_filt = types.InlineKeyboardButton("⚙️ Фильтр", callback_data="open_filters")
    markup.row(btn_like, btn_next)
    markup.add(btn_filt)

    bot.send_photo(user_id, found_car[3], caption=caption, parse_mode='Markdown', reply_markup=markup)

# ================= ОБРАБОТКА ВСЕХ ИНЛАЙН-КНОПОК =================
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    cid = call.message.chat.id
    bot.answer_callback_query(call.id)

    if call.data == "open_filters":
        send_filter_menu(cid)
    elif call.data == "f_brand":
        msg = bot.send_message(cid, "🚘 Выберите желаемую **марку** из списка:", parse_mode='Markdown', reply_markup=build_brands_markup(include_any=True))
        bot.register_next_step_handler(msg, set_f_brand)
    elif call.data == "f_model":
        f = get_user_filter(cid)
        if f[1] == 'Любая':
            msg = bot.send_message(cid, "📝 Сначала выберите марку или напишите желаемую **модель** текстом (либо `Любая`):", parse_mode='Markdown', reply_markup=cancel_markup())
            bot.register_next_step_handler(msg, set_f_model)
        else:
            msg = bot.send_message(cid, f"📝 Выберите **модель** {f[1]} из списка:", parse_mode='Markdown', reply_markup=build_models_markup(f[1], include_any=True))
            bot.register_next_step_handler(msg, set_f_model)
    elif call.data == "f_year":
        msg = bot.send_message(cid, "📅 Введите **год от и до** через пробел (например: `2008 2018`):", parse_mode='Markdown', reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, set_f_year)
    elif call.data == "f_price":
        msg = bot.send_message(cid, "💰 Введите **цену от и до** в рублях через пробел (например: `200000 700000`):", parse_mode='Markdown', reply_markup=cancel_markup())
        bot.register_next_step_handler(msg, set_f_price)
    elif call.data == "f_loc":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("📍 Моя текущая геопозиция", request_location=True))
        markup.add('❌ Отмена')
        msg = bot.send_message(cid, "🌍 Отправьте вашу **геопозицию** или напишите **город** (например: Абинск):", parse_mode='Markdown', reply_markup=markup)
        bot.register_next_step_handler(msg, set_f_loc_step1)
    elif call.data == "f_docs":
        f = get_user_filter(cid)
        new_val = 0 if f[11] == 1 else 1
        update_filter_field(cid, 'docs_only_clean', new_val)
        send_filter_menu(cid, call.message.message_id)
    elif call.data == "f_reset":
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute('DELETE FROM filters WHERE user_id = ?', (cid,))
        c.execute('DELETE FROM viewed WHERE user_id = ?', (cid,))
        conn.commit()
        conn.close()
        send_filter_menu(cid, call.message.message_id)
    elif call.data == "f_search" or call.data == "next_car":
        show_next_car(cid)
    elif call.data.startswith("like_"):
        car_id = int(call.data.split("_")[1])
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute('SELECT username, user_id FROM cars WHERE id = ?', (car_id,))
        res = c.fetchone()
        conn.close()
        
        if res and res[0]:
            bot.send_message(cid, f"📞 Напишите продавцу в Telegram: @{res[0]}")
        elif res:
            bot.send_message(cid, f"📞 Ссылка на профиль продавца: [Написать](tg://user?id={res[1]})", parse_mode='Markdown')
        show_next_car(cid)

print("Бот Avtovinchik с каталогом марок и моделей успешно запущен!")
bot.polling(none_stop=True)
