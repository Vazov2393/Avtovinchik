import os
import telebot
from telebot import types
import sqlite3
import math
from geopy.geocoders import Nominatim

# Читаем токен безопасно из переменных окружения BotHost (либо подставляем вручную, если запускаем локально)
TOKEN = os.getenv('BOT_TOKEN') or os.getenv('TOKEN') or 'ВАШ_ТОКЕН_ОТ_BOTFATHER'
bot = telebot.TeleBot(TOKEN)
geolocator = Nominatim(user_agent="avtovinchik_bot_v1")

# --- БАЗА ДАННЫХ ---
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

@bot.message_handler(commands=['start'])
def start(message):
    get_user_filter(message.chat.id)
    bot.send_message(
        message.chat.id,
        "👋 Добро пожаловать в Автовинчик!\nВыберите действие в меню ниже:",
        reply_markup=main_menu()
    )

# ================= ИНТЕРАКТИВНОЕ МЕНЮ ФИЛЬТРОВ =================
def send_filter_menu(chat_id, message_id=None):
    f = get_user_filter(chat_id)
    # f: 0:user_id, 1:brand, 2:model, 3:year_from, 4:year_to, 5:price_from, 6:price_to, 7:city_name, 8:lat, 9:lon, 10:radius, 11:docs
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
    val = 'Любая' if message.text.lower() == 'любая' else message.text.strip()
    update_filter_field(message.chat.id, 'brand', val)
    send_filter_menu(message.chat.id)

def set_f_model(message):
    val = 'Любая' if message.text.lower() == 'любая' else message.text.strip()
    update_filter_field(message.chat.id, 'model', val)
    send_filter_menu(message.chat.id)

def set_f_year(message):
    parts = message.text.strip().split()
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute('UPDATE filters SET year_from = ?, year_to = ? WHERE user_id = ?', (int(parts[0]), int(parts[1]), message.chat.id))
        c.execute('DELETE FROM viewed WHERE user_id = ?', (message.chat.id,))
        conn.commit()
        conn.close()
        send_filter_menu(message.chat.id)
    else:
        msg = bot.send_message(message.chat.id, "❌ Напишите два года через пробел (например: `2008 2016`):", parse_mode='Markdown')
        bot.register_next_step_handler(msg, set_f_year)

def set_f_price(message):
    parts = message.text.strip().split()
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute('UPDATE filters SET price_from = ?, price_to = ? WHERE user_id = ?', (int(parts[0]), int(parts[1]), message.chat.id))
        c.execute('DELETE FROM viewed WHERE user_id = ?', (message.chat.id,))
        conn.commit()
        conn.close()
        send_filter_menu(message.chat.id)
    else:
        msg = bot.send_message(message.chat.id, "❌ Напишите две суммы через пробел без точек и запятых (например: `150000 600000`):", parse_mode='Markdown')
        bot.register_next_step_handler(msg, set_f_price)

def set_f_loc_step1(message):
    lat, lon, city_name = None, None, "Точка на карте"
    if message.location:
        lat, lon = message.location.latitude, message.location.longitude
        try:
            loc = geolocator.reverse(f"{lat}, {lon}", language='ru')
            city_name = loc.raw.get('address', {}).get('city') or loc.raw.get('address', {}).get('town') or "Точка на карте"
        except:
            pass
    elif message.text:
        loc = geolocator.geocode(message.text.strip())
        if loc:
            lat, lon = loc.latitude, loc.longitude
            city_name = message.text.strip().capitalize()
        else:
            msg = bot.send_message(message.chat.id, "❌ Город не найден. Напишите точнее (например: Абинск):")
            bot.register_next_step_handler(msg, set_f_loc_step1)
            return

    temp_data[message.chat.id] = {'lat': lat, 'lon': lon, 'city_name': city_name}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('50', '100', '200', '500')
    msg = bot.send_message(message.chat.id, f"📍 Выбран город: **{city_name}**.\nВыберите или введите **радиус поиска в км**:", parse_mode='Markdown', reply_markup=markup)
    bot.register_next_step_handler(msg, set_f_loc_step2)

def set_f_loc_step2(message):
    if not message.text.isdigit():
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
    msg = bot.send_message(message.chat.id, "📸 Отправьте **фотографию** автомобиля:", parse_mode='Markdown', reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, get_photo)

def get_photo(message):
    if not message.photo:
        msg = bot.send_message(message.chat.id, "❌ Нужно отправить именно фото! Попробуйте еще раз:")
        bot.register_next_step_handler(msg, get_photo)
        return
    temp_data[message.chat.id]['photo'] = message.photo[-1].file_id
    msg = bot.send_message(message.chat.id, "🚘 Напишите **марку** авто (например: Лада, Toyota):")
    bot.register_next_step_handler(msg, get_brand)

def get_brand(message):
    temp_data[message.chat.id]['brand'] = message.text.strip()
    msg = bot.send_message(message.chat.id, "📝 Напишите **модель** авто (например: Приора, Camry):")
    bot.register_next_step_handler(msg, get_model)

def get_model(message):
    temp_data[message.chat.id]['model'] = message.text.strip()
    msg = bot.send_message(message.chat.id, "📅 Укажите **год выпуска** (только цифры, например: 2015):")
    bot.register_next_step_handler(msg, get_year)

def get_year(message):
    if not message.text.isdigit():
        msg = bot.send_message(message.chat.id, "❌ Введите год цифрами (например: 2012):")
        bot.register_next_step_handler(msg, get_year)
        return
    temp_data[message.chat.id]['year'] = int(message.text)
    msg = bot.send_message(message.chat.id, "💵 Укажите **цену в рублях** (только цифры, например: 450000):")
    bot.register_next_step_handler(msg, get_price)

def get_price(message):
    if not message.text.isdigit():
        msg = bot.send_message(message.chat.id, "❌ Введите цену только цифрами без пробелов:")
        bot.register_next_step_handler(msg, get_price)
        return
    temp_data[message.chat.id]['price'] = int(message.text)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('Отличное / Не требует вложений', 'На ходу / Есть нюансы')
    markup.row('Требует ремонта / Битая')
    msg = bot.send_message(message.chat.id, "🛠 Выберите **состояние** автомобиля:", reply_markup=markup)
    bot.register_next_step_handler(msg, get_condition)

def get_condition(message):
    temp_data[message.chat.id]['condition'] = message.text.strip()
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('✅ Чистые (без проблем)', '⚠️ Есть проблемы (запрет, утиль, без ПТС)')
    msg = bot.send_message(message.chat.id, "📄 Что с **документами**?", reply_markup=markup)
    bot.register_next_step_handler(msg, get_docs)

def get_docs(message):
    temp_data[message.chat.id]['docs'] = message.text.strip()
    msg = bot.send_message(message.chat.id, "✍️ Напишите **описание** (двигатель, коробка, косяки, торг):", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, get_desc)

def get_desc(message):
    temp_data[message.chat.id]['description'] = message.text.strip()
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_geo = types.KeyboardButton("📍 Отправить мою геопозицию", request_location=True)
    markup.add(btn_geo)
    msg = bot.send_message(message.chat.id, "🌍 Нажмите кнопку ниже, чтобы отправить **геопозицию** авто, или напишите **название города** текстом (например: Абинск):", reply_markup=markup)
    bot.register_next_step_handler(msg, get_location_sell)

def get_location_sell(message):
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
                msg = bot.send_message(message.chat.id, "❌ Город не найден. Напишите точнее (например: Краснодарский край, Абинск):")
                bot.register_next_step_handler(msg, get_location_sell)
                return
        except:
            msg = bot.send_message(message.chat.id, "❌ Ошибка поиска города. Попробуйте отправить геопозицию кнопкой:")
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
    # f: 0:user_id, 1:brand, 2:model, 3:year_from, 4:year_to, 5:price_from, 6:price_to, 7:city_name, 8:lat, 9:lon, 10:radius, 11:docs
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
        # car: 0:id, 1:uid, 2:uname, 3:photo, 4:brand, 5:model, 6:year, 7:price, 8:cond, 9:docs, 10:desc, 11:city, 12:lat, 13:lon
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
        msg = bot.send_message(cid, "🚘 Введите желаемую **марку** (или напишите `Любая` для сброса):", parse_mode='Markdown')
        bot.register_next_step_handler(msg, set_f_brand)
    elif call.data == "f_model":
        msg = bot.send_message(cid, "📝 Введите желаемую **модель** (или напишите `Любая` для сброса):", parse_mode='Markdown')
        bot.register_next_step_handler(msg, set_f_model)
    elif call.data == "f_year":
        msg = bot.send_message(cid, "📅 Введите **год от и до** через пробел (например: `2008 2018`):", parse_mode='Markdown')
        bot.register_next_step_handler(msg, set_f_year)
    elif call.data == "f_price":
        msg = bot.send_message(cid, "💰 Введите **цену от и до** в рублях через пробел (например: `200000 700000`):", parse_mode='Markdown')
        bot.register_next_step_handler(msg, set_f_price)
    elif call.data == "f_loc":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("📍 Моя текущая геопозиция", request_location=True))
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

print("Бот Автовинчик успешно запущен!")
bot.polling(none_stop=True)
