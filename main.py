import os
import math
import sqlite3
import telebot
from telebot import types
from geopy.geocoders import Nominatim

TOKEN = os.environ.get('BOT_TOKEN') or os.environ.get('TOKEN') or 'ВАШ_ТОКЕН_ОТ_BOTFATHER'
ADMIN_ID = 0

bot = telebot.TeleBot(TOKEN)
geolocator = Nominatim(user_agent="avtovinchik_bot_v3")

BRANDS = {
    "Лада (ВАЗ)": ["Приора", "Гранта", "Веста", "Нива", "2114", "2107", "Калина", "Ларгус"],
    "Toyota": ["Camry", "Corolla", "RAV4", "Land Cruiser", "Prius", "Mark II"],
    "Hyundai": ["Solaris", "Creta", "Elantra", "Tucson", "Santa Fe", "Sonata"],
    "Kia": ["Rio", "Sportage", "Ceed", "Optima", "K5", "Cerato"],
    "Volkswagen": ["Polo", "Tiguan", "Passat", "Golf", "Jetta", "Touareg"],
    "Skoda": ["Octavia", "Rapid", "Kodiaq", "Superb", "Yeti"],
    "Nissan": ["Qashqai", "X-Trail", "Almera", "Teana", "Juke"],
    "Ford": ["Focus", "Mondeo", "Kuga", "Fusion", "Fiesta"],
    "Renault": ["Logan", "Duster", "Sandero", "Megane", "Kaptur"],
    "Chevrolet": ["Cruze", "Lacetti", "Niva", "Aveo", "Tahoe"],
    "BMW": ["3 Series", "5 Series", "X5", "X3", "7 Series"],
    "Mercedes-Benz": ["C-Class", "E-Class", "S-Class", "GLE", "GLC"],
    "Mazda": ["3", "6", "CX-5", "CX-7"],
    "Mitsubishi": ["Lancer", "Outlander", "Pajero", "ASX"],
    "Chery": ["Tiggo 7 Pro", "Tiggo 4", "Tiggo 8 Pro", "Amulet"],
    "Haval": ["Jolion", "F7", "Dargo", "H9"]
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
        lon REAL,
        status TEXT DEFAULT 'pending'
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
    c.execute('''CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY
    )''')
    if ADMIN_ID:
        c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (ADMIN_ID,))
    conn.commit()
    conn.close()

init_db()
temp_data = {}

def is_admin(user_id):
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('SELECT user_id FROM admins WHERE user_id = ?', (user_id,))
    res = c.fetchone()
    conn.close()
    return res is not None

def get_all_admins():
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('SELECT user_id FROM admins')
    res = [r[0] for r in c.fetchall()]
    conn.close()
    return res

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

def main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('🚗 Купить авто', '💰 Продать авто')
    markup.row('⚙️ Мой фильтр', '📋 Мои объявления')
    if is_admin(user_id):
        markup.row('👑 Админ-панель')
    return markup

def nav_keyboard(extra_rows=None, back_text='⬅️ Назад'):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if extra_rows:
        for r in extra_rows:
            markup.row(*r)
    markup.row(back_text, '❌ Отмена')
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM admins')
    if c.fetchone()[0] == 0:
        c.execute('INSERT INTO admins (user_id) VALUES (?)', (message.chat.id,))
        conn.commit()
    conn.close()
    get_user_filter(message.chat.id)
    bot.send_message(
        message.chat.id,
        "👋 Добро пожаловать на Авторынок!\nВыберите действие в меню ниже:",
        reply_markup=main_menu(message.chat.id)
    )

@bot.message_handler(commands=['admin'])
def cmd_admin(message):
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM admins')
    if c.fetchone()[0] == 0:
        c.execute('INSERT INTO admins (user_id) VALUES (?)', (message.chat.id,))
        conn.commit()
    conn.close()
    if not is_admin(message.chat.id):
        bot.send_message(message.chat.id, "⛔ У вас нет прав администратора.")
        return
    open_admin_panel(message.chat.id)

@bot.message_handler(func=lambda m: m.text == '👑 Админ-панель')
def btn_admin(message):
    if not is_admin(message.chat.id):
        return
    open_admin_panel(message.chat.id)

def open_admin_panel(chat_id):
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM cars WHERE status = 'pending'")
    pending_cnt = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM cars WHERE status = 'approved'")
    active_cnt = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM filters")
    users_cnt = c.fetchone()[0]
    conn.close()

    text = (
        "👑 Панель администратора\n\n"
        f"👥 Пользователей в базе: {users_cnt}\n"
        f"✅ Активных объявлений: {active_cnt}\n"
        f"⏳ Ожидают проверки: {pending_cnt}"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(f"⏳ На модерации ({pending_cnt})", callback_data="adm_pending"))
    markup.add(types.InlineKeyboardButton(f"📋 Все объявления ({active_cnt})", callback_data="adm_all_0"))
    markup.add(types.InlineKeyboardButton("👥 Управление админами", callback_data="adm_list"))
    bot.send_message(chat_id, text, reply_markup=markup)

# ================= ВЕТКА ПРОДАЖИ =================
@bot.message_handler(func=lambda m: m.text == '💰 Продать авто')
def sell_start(message):
    temp_data[message.chat.id] = {'username': message.from_user.username}
    ask_photo(message.chat.id)

def ask_photo(chat_id):
    msg = bot.send_message(chat_id, "📸 Шаг 1/9: Отправьте фотографию автомобиля:", reply_markup=nav_keyboard(back_text='⬅️ В меню'))
    bot.register_next_step_handler(msg, get_photo)

def get_photo(message):
    if message.text in ['❌ Отмена', '⬅️ В меню']:
        temp_data.pop(message.chat.id, None)
        bot.send_message(message.chat.id, "Возвращаемся в главное меню.", reply_markup=main_menu(message.chat.id))
        return
    if not message.photo:
        msg = bot.send_message(message.chat.id, "❌ Отправьте именно фотографию автомобиля:", reply_markup=nav_keyboard(back_text='⬅️ В меню'))
        bot.register_next_step_handler(msg, get_photo)
        return
    temp_data[message.chat.id]['photo'] = message.photo[-1].file_id
    ask_brand(message.chat.id)

def ask_brand(chat_id):
    brands = list(BRANDS.keys())
    rows = [brands[i:i+2] for i in range(0, len(brands), 2)]
    rows.append(['✍️ Другая марка'])
    msg = bot.send_message(chat_id, "🚘 Шаг 2/9: Выберите марку автомобиля:", reply_markup=nav_keyboard(rows))
    bot.register_next_step_handler(msg, get_brand)

def get_brand(message):
    if not message.text:
        ask_brand(message.chat.id)
        return
    if message.text == '❌ Отмена':
        temp_data.pop(message.chat.id, None)
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    if message.text == '⬅️ Назад':
        ask_photo(message.chat.id)
        return
    if message.text == '✍️ Другая марка':
        msg = bot.send_message(message.chat.id, "✍️ Напишите название марки текстом:", reply_markup=nav_keyboard())
        bot.register_next_step_handler(msg, get_custom_brand)
        return
    temp_data[message.chat.id]['brand'] = message.text.strip()
    ask_model(message.chat.id)

def get_custom_brand(message):
    if not message.text:
        ask_brand(message.chat.id)
        return
    if message.text == '❌ Отмена':
        temp_data.pop(message.chat.id, None)
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    if message.text == '⬅️ Назад':
        ask_brand(message.chat.id)
        return
    temp_data[message.chat.id]['brand'] = message.text.strip()
    ask_model(message.chat.id)

def ask_model(chat_id):
    brand = temp_data[chat_id].get('brand', '')
    models = BRANDS.get(brand, [])
    rows = [models[i:i+2] for i in range(0, len(models), 2)]
    rows.append(['✍️ Другая модель'])
    msg = bot.send_message(chat_id, f"📝 Шаг 3/9: Выберите модель ({brand}):", reply_markup=nav_keyboard(rows))
    bot.register_next_step_handler(msg, get_model)

def get_model(message):
    if not message.text:
        ask_model(message.chat.id)
        return
    if message.text == '❌ Отмена':
        temp_data.pop(message.chat.id, None)
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    if message.text == '⬅️ Назад':
        ask_brand(message.chat.id)
        return
    if message.text == '✍️ Другая модель':
        msg = bot.send_message(message.chat.id, "✍️ Напишите модель текстом:", reply_markup=nav_keyboard())
        bot.register_next_step_handler(msg, get_custom_model)
        return
    temp_data[message.chat.id]['model'] = message.text.strip()
    ask_year(message.chat.id)

def get_custom_model(message):
    if not message.text:
        ask_model(message.chat.id)
        return
    if message.text == '❌ Отмена':
        temp_data.pop(message.chat.id, None)
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    if message.text == '⬅️ Назад':
        ask_model(message.chat.id)
        return
    temp_data[message.chat.id]['model'] = message.text.strip()
    ask_year(message.chat.id)

def ask_year(chat_id):
    msg = bot.send_message(chat_id, "📅 Шаг 4/9: Укажите год выпуска (только цифры, например 2015):", reply_markup=nav_keyboard())
    bot.register_next_step_handler(msg, get_year)

def get_year(message):
    if not message.text:
        ask_year(message.chat.id)
        return
    if message.text == '❌ Отмена':
        temp_data.pop(message.chat.id, None)
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    if message.text == '⬅️ Назад':
        ask_model(message.chat.id)
        return
    if not message.text.isdigit() or not (1950 <= int(message.text) <= 2027):
        msg = bot.send_message(message.chat.id, "❌ Введите корректный год цифрами (например: 2014):", reply_markup=nav_keyboard())
        bot.register_next_step_handler(msg, get_year)
        return
    temp_data[message.chat.id]['year'] = int(message.text)
    ask_price(message.chat.id)

def ask_price(chat_id):
    msg = bot.send_message(chat_id, "💵 Шаг 5/9: Укажите цену в рублях (только цифры, например 450000):", reply_markup=nav_keyboard())
    bot.register_next_step_handler(msg, get_price)

def get_price(message):
    if not message.text:
        ask_price(message.chat.id)
        return
    if message.text == '❌ Отмена':
        temp_data.pop(message.chat.id, None)
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    if message.text == '⬅️ Назад':
        ask_year(message.chat.id)
        return
    clean_p = message.text.replace(' ', '')
    if not clean_p.isdigit():
        msg = bot.send_message(message.chat.id, "❌ Введите цену только цифрами (например: 450000):", reply_markup=nav_keyboard())
        bot.register_next_step_handler(msg, get_price)
        return
    temp_data[message.chat.id]['price'] = int(clean_p)
    ask_condition(message.chat.id)

def ask_condition(chat_id):
    rows = [
        ['Отличное / Без вложений'],
        ['На ходу / Есть нюансы'],
        ['Требует ремонта / Битая']
    ]
    msg = bot.send_message(chat_id, "🛠 Шаг 6/9: Выберите состояние автомобиля:", reply_markup=nav_keyboard(rows))
    bot.register_next_step_handler(msg, get_condition)

def get_condition(message):
    if not message.text:
        ask_condition(message.chat.id)
        return
    if message.text == '❌ Отмена':
        temp_data.pop(message.chat.id, None)
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    if message.text == '⬅️ Назад':
        ask_price(message.chat.id)
        return
    temp_data[message.chat.id]['condition'] = message.text.strip()
    ask_docs(message.chat.id)

def ask_docs(chat_id):
    rows = [
        ['✅ Чистые (без проблем)'],
        ['⚠️ Есть проблемы (запрет, утиль, без ПТС)']
    ]
    msg = bot.send_message(chat_id, "📄 Шаг 7/9: Что с документами?", reply_markup=nav_keyboard(rows))
    bot.register_next_step_handler(msg, get_docs)

def get_docs(message):
    if not message.text:
        ask_docs(message.chat.id)
        return
    if message.text == '❌ Отмена':
        temp_data.pop(message.chat.id, None)
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    if message.text == '⬅️ Назад':
        ask_condition(message.chat.id)
        return
    temp_data[message.chat.id]['docs'] = message.text.strip()
    ask_desc(message.chat.id)

def ask_desc(chat_id):
    msg = bot.send_message(chat_id, "✍️ Шаг 8/9: Напишите описание (двигатель, коробка, косяки, торг):", reply_markup=nav_keyboard())
    bot.register_next_step_handler(msg, get_desc)

def get_desc(message):
    if not message.text:
        ask_desc(message.chat.id)
        return
    if message.text == '❌ Отмена':
        temp_data.pop(message.chat.id, None)
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    if message.text == '⬅️ Назад':
        ask_docs(message.chat.id)
        return
    temp_data[message.chat.id]['description'] = message.text.strip()
    ask_location_sell(message.chat.id)

def ask_location_sell(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("📍 Отправить мою геопозицию", request_location=True))
    markup.row('⬅️ Назад', '❌ Отмена')
    msg = bot.send_message(chat_id, "🌍 Шаг 9/9: Отправьте геопозицию кнопкой или напишите город текстом (например: Абинск):", reply_markup=markup)
    bot.register_next_step_handler(msg, get_location_sell)

def get_location_sell(message):
    if message.text == '❌ Отмена':
        temp_data.pop(message.chat.id, None)
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    if message.text == '⬅️ Назад':
        ask_desc(message.chat.id)
        return

    lat, lon, city_name = None, None, "Не указан"
    if message.location:
        lat = message.location.latitude
        lon = message.location.longitude
        try:
            loc = geolocator.reverse(f"{lat}, {lon}", language='ru')
            city_name = loc.raw.get('address', {}).get('city') or loc.raw.get('address', {}).get('town') or "Точка на карте"
        except Exception:
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
        except Exception:
            msg = bot.send_message(message.chat.id, "❌ Ошибка поиска города. Попробуйте отправить геопозицию кнопкой:")
            bot.register_next_step_handler(msg, get_location_sell)
            return
    else:
        ask_location_sell(message.chat.id)
        return

    d = temp_data[message.chat.id]
    status = 'approved' if is_admin(message.chat.id) else 'pending'

    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('''INSERT INTO cars (user_id, username, photo, brand, model, year, price, condition, docs, description, city, lat, lon, status)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (message.chat.id, d['username'], d['photo'], d['brand'], d['model'], d['year'],
               d['price'], d['condition'], d['docs'], d['description'], city_name, lat, lon, status))
    car_id = c.lastrowid
    conn.commit()
    conn.close()
    temp_data.pop(message.chat.id, None)

    if status == 'approved':
        bot.send_message(message.chat.id, "✅ Объявление опубликовано!", reply_markup=main_menu(message.chat.id))
    else:
        bot.send_message(message.chat.id, "✅ Объявление отправлено на проверку модератору! Вы получите уведомление после публикации.", reply_markup=main_menu(message.chat.id))
        notify_admins_new_car(car_id)

def notify_admins_new_car(car_id):
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('SELECT * FROM cars WHERE id = ?', (car_id,))
    car = c.fetchone()
    conn.close()
    if not car:
        return

    caption = format_car_caption(car, is_admin_view=True, header="🆕 Новое объявление на модерацию!")
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Одобрить", callback_data=f"mod_ok_{car_id}"),
        types.InlineKeyboardButton("⚠️ Предупреждение", callback_data=f"mod_warn_{car_id}")
    )
    markup.add(types.InlineKeyboardButton("🗑 Удалить (причина)", callback_data=f"mod_del_{car_id}"))

    for adm_id in get_all_admins():
        try:
            bot.send_photo(adm_id, car[3], caption=caption, reply_markup=markup)
        except Exception:
            pass

def format_car_caption(car, dist_text=None, is_admin_view=False, header=None):
    # car: 0:id, 1:uid, 2:uname, 3:photo, 4:brand, 5:model, 6:year, 7:price, 8:cond, 9:docs, 10:desc, 11:city, 12:lat, 13:lon, 14:status
    price_str = f"{car[7]:,}".replace(',', ' ')
    loc_line = dist_text if dist_text else f"📍 Город: {car[11]}"
    lines = []
    if header:
        lines.append(header)
        lines.append("")
    lines.append(f"🚘 {car[4]} {car[5]}, {car[6]} г. (ID: #{car[0]})")
    lines.append(f"💰 Цена: {price_str} ₽")
    lines.append(loc_line)
    lines.append(f"🛠 Состояние: {car[8]}")
    lines.append(f"📄 Документы: {car[9]}")
    lines.append(f"\n📝 Описание:\n{car[10]}")
    if is_admin_view:
        uname = f"@{car[2]}" if car[2] else f"ID {car[1]}"
        lines.append(f"\n👤 Продавец: {uname}")
    return "\n".join(lines)

# ================= ЛИЧНЫЙ КАБИНЕТ ПРОДАВЦА =================
@bot.message_handler(func=lambda m: m.text == '📋 Мои объявления')
def my_cars(message):
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('SELECT * FROM cars WHERE user_id = ? ORDER BY id DESC', (message.chat.id,))
    cars = c.fetchall()
    conn.close()

    if not cars:
        bot.send_message(message.chat.id, "У вас пока нет размещенных объявлений.")
        return

    status_map = {'pending': '⏳ На проверке', 'approved': '✅ Опубликовано', 'rejected': '❌ Отклонено'}
    for car in cars:
        st = status_map.get(car[14], car[14])
        caption = format_car_caption(car, header=f"Статус: {st}")
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✏️ Изменить цену", callback_data=f"my_price_{car[0]}"),
            types.InlineKeyboardButton("📝 Описание", callback_data=f"my_desc_{car[0]}")
        )
        markup.add(types.InlineKeyboardButton("🗑 Снять с продажи", callback_data=f"my_del_{car[0]}"))
        bot.send_photo(message.chat.id, car[3], caption=caption, reply_markup=markup)

def edit_my_price(message, car_id):
    if not message.text or message.text in ['❌ Отмена', '⬅️ Назад']:
        bot.send_message(message.chat.id, "Изменение отменено.", reply_markup=main_menu(message.chat.id))
        return
    clean_p = message.text.replace(' ', '')
    if not clean_p.isdigit():
        msg = bot.send_message(message.chat.id, "❌ Введите новую цену цифрами:")
        bot.register_next_step_handler(msg, edit_my_price, car_id)
        return
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('UPDATE cars SET price = ? WHERE id = ? AND user_id = ?', (int(clean_p), car_id, message.chat.id))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ Цена успешно обновлена!", reply_markup=main_menu(message.chat.id))

def edit_my_desc(message, car_id):
    if not message.text or message.text in ['❌ Отмена', '⬅️ Назад']:
        bot.send_message(message.chat.id, "Изменение отменено.", reply_markup=main_menu(message.chat.id))
        return
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('UPDATE cars SET description = ? WHERE id = ? AND user_id = ?', (message.text.strip(), car_id, message.chat.id))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ Описание успешно обновлено!", reply_markup=main_menu(message.chat.id))

# ================= МЕНЮ ФИЛЬТРОВ ПОКУПАТЕЛЯ =================
def send_filter_menu(chat_id, message_id=None):
    f = get_user_filter(chat_id)
    docs_text = "Только чистые" if f[11] == 1 else "Все (включая проблемные)"
    loc_text = f"{f[7]} (+{f[10]} км)" if f[7] != 'Не задан' else "Вся Россия"
    price_to_str = "без потолка" if f[6] >= 99999999 else f"{f[6]:,} ₽".replace(',', ' ')
    price_from_str = f"{f[5]:,} ₽".replace(',', ' ')

    text = (
        "⚙️ Ваши текущие фильтры поиска:\n\n"
        f"🚘 Марка: {f[1]}\n"
        f"📝 Модель: {f[2]}\n"
        f"📅 Год выпуска: от {f[3]} до {f[4]}\n"
        f"💰 Цена: от {price_from_str} до {price_to_str}\n"
        f"📍 Локация: {loc_text}\n"
        f"📄 Документы: {docs_text}\n\n"
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
    markup.add(types.InlineKeyboardButton("⬅️ В главное меню", callback_data="go_main"))

    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
        except Exception:
            bot.send_message(chat_id, text, reply_markup=markup)
    else:
        bot.send_message(chat_id, text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == '⚙️ Мой фильтр')
def open_filter_menu(message):
    send_filter_menu(message.chat.id)

def update_filter_field(user_id, field, value):
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute(f'UPDATE filters SET {field} = ? WHERE user_id = ?', (value, user_id))
    c.execute('DELETE FROM viewed WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def set_f_brand(message):
    if not message.text or message.text in ['⬅️ Назад', '❌ Отмена']:
        bot.send_message(message.chat.id, "Возврат в фильтры.", reply_markup=main_menu(message.chat.id))
        send_filter_menu(message.chat.id)
        return
    if message.text == '✍️ Другая марка':
        msg = bot.send_message(message.chat.id, "✍️ Введите марку текстом:", reply_markup=nav_keyboard(back_text='⬅️ Назад'))
        bot.register_next_step_handler(msg, set_f_brand)
        return
    val = 'Любая' if message.text.lower() in ['любая', 'все марки'] else message.text.strip()
    update_filter_field(message.chat.id, 'brand', val)
    update_filter_field(message.chat.id, 'model', 'Любая')
    bot.send_message(message.chat.id, f"✅ Выбрана марка: {val}", reply_markup=main_menu(message.chat.id))
    send_filter_menu(message.chat.id)

def set_f_model(message):
    if not message.text or message.text in ['⬅️ Назад', '❌ Отмена']:
        bot.send_message(message.chat.id, "Возврат в фильтры.", reply_markup=main_menu(message.chat.id))
        send_filter_menu(message.chat.id)
        return
    if message.text == '✍️ Другая модель':
        msg = bot.send_message(message.chat.id, "✍️ Введите модель текстом:", reply_markup=nav_keyboard(back_text='⬅️ Назад'))
        bot.register_next_step_handler(msg, set_f_model)
        return
    val = 'Любая' if message.text.lower() in ['любая', 'все модели'] else message.text.strip()
    update_filter_field(message.chat.id, 'model', val)
    bot.send_message(message.chat.id, f"✅ Выбрана модель: {val}", reply_markup=main_menu(message.chat.id))
    send_filter_menu(message.chat.id)

def set_f_year(message):
    if not message.text or message.text in ['⬅️ Назад', '❌ Отмена']:
        bot.send_message(message.chat.id, "Возврат в фильтры.", reply_markup=main_menu(message.chat.id))
        send_filter_menu(message.chat.id)
        return
    parts = message.text.strip().split()
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute('UPDATE filters SET year_from = ?, year_to = ? WHERE user_id = ?', (int(parts[0]), int(parts[1]), message.chat.id))
        c.execute('DELETE FROM viewed WHERE user_id = ?', (message.chat.id,))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ Год обновлен.", reply_markup=main_menu(message.chat.id))
        send_filter_menu(message.chat.id)
    else:
        msg = bot.send_message(message.chat.id, "❌ Напишите два года через пробел (например: 2008 2016):", reply_markup=nav_keyboard())
        bot.register_next_step_handler(msg, set_f_year)

def set_f_price(message):
    if not message.text or message.text in ['⬅️ Назад', '❌ Отмена']:
        bot.send_message(message.chat.id, "Возврат в фильтры.", reply_markup=main_menu(message.chat.id))
        send_filter_menu(message.chat.id)
        return
    parts = message.text.strip().split()
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute('UPDATE filters SET price_from = ?, price_to = ? WHERE user_id = ?', (int(parts[0]), int(parts[1]), message.chat.id))
        c.execute('DELETE FROM viewed WHERE user_id = ?', (message.chat.id,))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, "✅ Бюджет обновлен.", reply_markup=main_menu(message.chat.id))
        send_filter_menu(message.chat.id)
    else:
        msg = bot.send_message(message.chat.id, "❌ Напишите две суммы через пробел (например: 150000 600000):", reply_markup=nav_keyboard())
        bot.register_next_step_handler(msg, set_f_price)

def set_f_loc_step1(message):
    if message.text in ['⬅️ Назад', '❌ Отмена']:
        bot.send_message(message.chat.id, "Возврат в фильтры.", reply_markup=main_menu(message.chat.id))
        send_filter_menu(message.chat.id)
        return

    lat, lon, city_name = None, None, "Точка на карте"
    if message.location:
        lat, lon = message.location.latitude, message.location.longitude
        try:
            loc = geolocator.reverse(f"{lat}, {lon}", language='ru')
            city_name = loc.raw.get('address', {}).get('city') or loc.raw.get('address', {}).get('town') or "Точка на карте"
        except Exception:
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
    else:
        return

    temp_data[message.chat.id] = {'lat': lat, 'lon': lon, 'city_name': city_name}
    rows = [['50', '100', '200', '500']]
    msg = bot.send_message(message.chat.id, f"📍 Выбран город: {city_name}.\nВыберите или введите радиус поиска в км:", reply_markup=nav_keyboard(rows))
    bot.register_next_step_handler(msg, set_f_loc_step2)

def set_f_loc_step2(message):
    if not message.text or message.text == '❌ Отмена':
        temp_data.pop(message.chat.id, None)
        bot.send_message(message.chat.id, "Возврат в фильтры.", reply_markup=main_menu(message.chat.id))
        send_filter_menu(message.chat.id)
        return
    if message.text == '⬅️ Назад':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("📍 Моя текущая геопозиция", request_location=True))
        markup.row('⬅️ Назад', '❌ Отмена')
        msg = bot.send_message(message.chat.id, "🌍 Отправьте геопозицию или напишите город:", reply_markup=markup)
        bot.register_next_step_handler(msg, set_f_loc_step1)
        return
    if not message.text.isdigit():
        msg = bot.send_message(message.chat.id, "❌ Введите радиус цифрами (например: 100):")
        bot.register_next_step_handler(msg, set_f_loc_step2)
        return

    d = temp_data.pop(message.chat.id)
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('UPDATE filters SET city_name = ?, lat = ?, lon = ?, radius = ? WHERE user_id = ?',
              (d['city_name'], d['lat'], d['lon'], int(message.text), message.chat.id))
    c.execute('DELETE FROM viewed WHERE user_id = ?', (message.chat.id,))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ Локация обновлена!", reply_markup=main_menu(message.chat.id))
    send_filter_menu(message.chat.id)

# ================= ЛЕНТА АНКЕТ ПОКУПАТЕЛЯ =================
@bot.message_handler(func=lambda m: m.text == '🚗 Купить авто')
def buy_cars(message):
    show_next_car(message.chat.id)

def show_next_car(user_id):
    f = get_user_filter(user_id)
    _, f_brand, f_model, y_from, y_to, p_from, p_to, city_name, u_lat, u_lon, radius, only_clean = f

    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    query = '''SELECT * FROM cars 
               WHERE status = 'approved'
               AND year >= ? AND year <= ? 
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
    dist_text = None
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
        markup.row(
            types.InlineKeyboardButton("⚙️ Изменить фильтры", callback_data="open_filters"),
            types.InlineKeyboardButton("🔄 Смотреть заново", callback_data="reset_viewed")
        )
        markup.add(types.InlineKeyboardButton("⬅️ В главное меню", callback_data="go_main"))
        bot.send_message(user_id, "🏁 Подходящих машин по вашим фильтрам больше нет!", reply_markup=markup)
        return

    c.execute('INSERT INTO viewed (user_id, car_id) VALUES (?, ?)', (user_id, found_car[0]))
    conn.commit()
    conn.close()

    caption = format_car_caption(found_car, dist_text=dist_text)
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("❤️ Контакт продавца", callback_data=f"like_{found_car[0]}"),
        types.InlineKeyboardButton("👎 Дальше", callback_data="next_car")
    )
    markup.row(
        types.InlineKeyboardButton("⚙️ Фильтр", callback_data="open_filters"),
        types.InlineKeyboardButton("🚩 Пожаловаться", callback_data=f"rep_{found_car[0]}")
    )
    markup.add(types.InlineKeyboardButton("⬅️ В меню", callback_data="go_main"))

    bot.send_photo(user_id, found_car[3], caption=caption, reply_markup=markup)

# ================= ЖАЛОБЫ ПОКУПАТЕЛЕЙ =================
def process_report_reason(message, car_id):
    if not message.text or message.text in ['❌ Отмена', '⬅️ Назад']:
        bot.send_message(message.chat.id, "Жалоба отменена.", reply_markup=main_menu(message.chat.id))
        return

    reason = message.text.strip()
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('SELECT * FROM cars WHERE id = ?', (car_id,))
    car = c.fetchone()
    conn.close()

    bot.send_message(message.chat.id, "✅ Спасибо! Ваша жалоба отправлена администраторам на проверку.", reply_markup=main_menu(message.chat.id))
    if not car:
        return

    reporter = f"@{message.from_user.username}" if message.from_user.username else f"ID {message.chat.id}"
    header = f"🚩 ЖАЛОБА от {reporter}\nПричина: {reason}"
    caption = format_car_caption(car, is_admin_view=True, header=header)

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("⚠️ Предупреждение автору", callback_data=f"mod_warn_{car_id}"),
        types.InlineKeyboardButton("🗑 Удалить (причина)", callback_data=f"mod_del_{car_id}")
    )
    for adm_id in get_all_admins():
        try:
            bot.send_photo(adm_id, car[3], caption=caption, reply_markup=markup)
        except Exception:
            pass

# ================= АДМИН-ДЕЙСТВИЯ: ПРЕДУПРЕЖДЕНИЕ И УДАЛЕНИЕ =================
def send_admin_warning(message, car_id):
    if not message.text or message.text in ['❌ Отмена', '⬅️ Назад']:
        bot.send_message(message.chat.id, "Отправка предупреждения отменена.", reply_markup=main_menu(message.chat.id))
        return

    warn_text = message.text.strip()
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('SELECT user_id, brand, model, year FROM cars WHERE id = ?', (car_id,))
    car = c.fetchone()
    conn.close()

    if not car:
        bot.send_message(message.chat.id, "❌ Объявление не найдено.", reply_markup=main_menu(message.chat.id))
        return

    try:
        bot.send_message(
            car[0],
            f"⚠️ ПРЕДУПРЕЖДЕНИЕ ОТ АДМИНИСТРАЦИИ\n\n"
            f"По вашему объявлению: {car[1]} {car[2]}, {car[3]} г. (ID #{car_id})\n"
            f"Замечание: {warn_text}\n\n"
            f"Пожалуйста, исправьте нарушение в разделе «📋 Мои объявления», иначе карточка будет удалена."
        )
        bot.send_message(message.chat.id, "✅ Предупреждение отправлено автору!", reply_markup=main_menu(message.chat.id))
    except Exception:
        bot.send_message(message.chat.id, "⚠️ Не удалось доставить сообщение (пользователь заблокировал бота).", reply_markup=main_menu(message.chat.id))

def delete_car_with_reason(message, car_id):
    if not message.text or message.text in ['❌ Отмена', '⬅️ Назад']:
        bot.send_message(message.chat.id, "Удаление отменено.", reply_markup=main_menu(message.chat.id))
        return

    reason = message.text.strip()
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('SELECT user_id, brand, model, year FROM cars WHERE id = ?', (car_id,))
    car = c.fetchone()
    if car:
        c.execute('DELETE FROM cars WHERE id = ?', (car_id,))
        c.execute('DELETE FROM viewed WHERE car_id = ?', (car_id,))
        conn.commit()
    conn.close()

    if not car:
        bot.send_message(message.chat.id, "❌ Объявление уже было удалено.", reply_markup=main_menu(message.chat.id))
        return

    try:
        bot.send_message(
            car[0],
            f"🗑 ВАШЕ ОБЪЯВЛЕНИЕ УДАЛЕНО АДМИНИСТРАТОРОМ\n\n"
            f"Автомобиль: {car[1]} {car[2]}, {car[3]} г. (ID #{car_id})\n"
            f"Причина: {reason}"
        )
    except Exception:
        pass

    bot.send_message(message.chat.id, f"✅ Объявление #{car_id} удалено, автор уведомлен.", reply_markup=main_menu(message.chat.id))

def add_new_admin_step(message):
    if message.text in ['❌ Отмена', '⬅️ Назад']:
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return

    new_id = None
    if message.forward_from:
        new_id = message.forward_from.id
    elif message.text and message.text.strip().isdigit():
        new_id = int(message.text.strip())

    if not new_id:
        msg = bot.send_message(message.chat.id, "❌ Пришлите цифровой Telegram ID пользователя или перешлите его сообщение:", reply_markup=nav_keyboard())
        bot.register_next_step_handler(msg, add_new_admin_step)
        return

    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (new_id,))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, f"✅ Пользователь {new_id} назначен администратором!", reply_markup=main_menu(message.chat.id))

# ================= ОБРАБОТКА ВСЕХ ИНЛАЙН-КНОПОК =================
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    cid = call.message.chat.id
    bot.answer_callback_query(call.id)

    if call.data == "go_main":
        bot.send_message(cid, "Главное меню:", reply_markup=main_menu(cid))
    elif call.data == "open_filters":
        send_filter_menu(cid)
    elif call.data == "reset_viewed":
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute('DELETE FROM viewed WHERE user_id = ?', (cid,))
        conn.commit()
        conn.close()
        show_next_car(cid)
    elif call.data == "f_brand":
        brands = list(BRANDS.keys())
        rows = [['Любая']] + [brands[i:i+2] for i in range(0, len(brands), 2)] + [['✍️ Другая марка']]
        msg = bot.send_message(cid, "🚘 Выберите желаемую марку:", reply_markup=nav_keyboard(rows))
        bot.register_next_step_handler(msg, set_f_brand)
    elif call.data == "f_model":
        f = get_user_filter(cid)
        models = BRANDS.get(f[1], [])
        rows = [['Любая']] + [models[i:i+2] for i in range(0, len(models), 2)] + [['✍️ Другая модель']]
        msg = bot.send_message(cid, f"📝 Выберите модель ({f[1]}):", reply_markup=nav_keyboard(rows))
        bot.register_next_step_handler(msg, set_f_model)
    elif call.data == "f_year":
        msg = bot.send_message(cid, "📅 Введите год от и до через пробел (например: 2008 2018):", reply_markup=nav_keyboard())
        bot.register_next_step_handler(msg, set_f_year)
    elif call.data == "f_price":
        msg = bot.send_message(cid, "💰 Введите цену от и до в рублях через пробел (например: 200000 700000):", reply_markup=nav_keyboard())
        bot.register_next_step_handler(msg, set_f_price)
    elif call.data == "f_loc":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("📍 Моя текущая геопозиция", request_location=True))
        markup.row('⬅️ Назад', '❌ Отмена')
        msg = bot.send_message(cid, "🌍 Отправьте геопозицию или напишите город (например: Абинск):", reply_markup=markup)
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
    elif call.data in ["f_search", "next_car"]:
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
            bot.send_message(cid, f"📞 ID продавца в Telegram: {res[1]}")
        show_next_car(cid)
    elif call.data.startswith("rep_"):
        car_id = int(call.data.split("_")[1])
        rows = [['Фейк / Мошенник', 'Неверная цена'], ['Авто уже продано', 'Запрещенный контент']]
        msg = bot.send_message(cid, "🚩 Выберите или напишите причину жалобы:", reply_markup=nav_keyboard(rows))
        bot.register_next_step_handler(msg, process_report_reason, car_id)

    # Личный кабинет продавца
    elif call.data.startswith("my_price_"):
        car_id = int(call.data.split("_")[2])
        msg = bot.send_message(cid, "💰 Введите новую цену в рублях (только цифры):", reply_markup=nav_keyboard())
        bot.register_next_step_handler(msg, edit_my_price, car_id)
    elif call.data.startswith("my_desc_"):
        car_id = int(call.data.split("_")[2])
        msg = bot.send_message(cid, "📝 Введите новое описание автомобиля:", reply_markup=nav_keyboard())
        bot.register_next_step_handler(msg, edit_my_desc, car_id)
    elif call.data.startswith("my_del_"):
        car_id = int(call.data.split("_")[2])
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute('DELETE FROM cars WHERE id = ? AND user_id = ?', (car_id, cid))
        conn.commit()
        conn.close()
        bot.delete_message(cid, call.message.message_id)
        bot.send_message(cid, "🗑 Объявление снято с продажи.")

    # Админ-панель
    elif call.data == "adm_pending":
        if not is_admin(cid):
            return
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute("SELECT * FROM cars WHERE status = 'pending' ORDER BY id ASC LIMIT 1")
        car = c.fetchone()
        conn.close()
        if not car:
            bot.send_message(cid, "✅ Новых объявлений на модерации нет!")
            return
        caption = format_car_caption(car, is_admin_view=True, header="⏳ Заявка на модерацию:")
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✅ Одобрить", callback_data=f"mod_ok_{car[0]}"),
            types.InlineKeyboardButton("⚠️ Предупреждение", callback_data=f"mod_warn_{car[0]}")
        )
        markup.add(types.InlineKeyboardButton("🗑 Удалить (причина)", callback_data=f"mod_del_{car[0]}"))
        bot.send_photo(cid, car[3], caption=caption, reply_markup=markup)

    elif call.data.startswith("adm_all_"):
        if not is_admin(cid):
            return
        offset = int(call.data.split("_")[2])
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM cars WHERE status = 'approved'")
        total = c.fetchone()[0]
        if total == 0:
            conn.close()
            bot.send_message(cid, "📭 В базе пока нет активных объявлений.")
            return
        if offset >= total:
            offset = 0
        if offset < 0:
            offset = total - 1
        c.execute("SELECT * FROM cars WHERE status = 'approved' ORDER BY id DESC LIMIT 1 OFFSET ?", (offset,))
        car = c.fetchone()
        conn.close()

        caption = format_car_caption(car, is_admin_view=True, header=f"📋 Объявление {offset + 1} из {total}")
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("⬅️ Пред.", callback_data=f"adm_all_{offset - 1}"),
            types.InlineKeyboardButton("След. ➡️", callback_data=f"adm_all_{offset + 1}")
        )
        markup.row(
            types.InlineKeyboardButton("📞 Контакт", callback_data=f"adm_contact_{car[0]}"),
            types.InlineKeyboardButton("⚠️ Предупреждение", callback_data=f"mod_warn_{car[0]}")
        )
        markup.add(types.InlineKeyboardButton("🗑 Удалить (причина)", callback_data=f"mod_del_{car[0]}"))
        bot.send_photo(cid, car[3], caption=caption, reply_markup=markup)

    elif call.data.startswith("adm_contact_"):
        if not is_admin(cid):
            return
        car_id = int(call.data.split("_")[2])
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute('SELECT username, user_id FROM cars WHERE id = ?', (car_id,))
        res = c.fetchone()
        conn.close()
        if res:
            contact = f"@{res[0]}" if res[0] else f"ID: {res[1]}"
            bot.send_message(cid, f"👤 Автор объявления #{car_id}: {contact}")

    elif call.data.startswith("mod_ok_"):
        if not is_admin(cid):
            return
        car_id = int(call.data.split("_")[2])
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute("UPDATE cars SET status = 'approved' WHERE id = ?", (car_id,))
        c.execute("SELECT user_id, brand, model FROM cars WHERE id = ?", (car_id,))
        car = c.fetchone()
        conn.commit()
        conn.close()
        bot.delete_message(cid, call.message.message_id)
        bot.send_message(cid, f"✅ Объявление #{car_id} одобрено и опубликовано!")
        if car:
            try:
                bot.send_message(car[0], f"🎉 Ваше объявление ({car[1]} {car[2]}) прошло модерацию и опубликовано!")
            except Exception:
                pass

    elif call.data.startswith("mod_warn_"):
        if not is_admin(cid):
            return
        car_id = int(call.data.split("_")[2])
        rows = [['Загрузите реальные фото авто', 'Укажите корректную цену'], ['Неполное описание / спам']]
        msg = bot.send_message(cid, f"⚠️ Выберите или напишите текст предупреждения для объявления #{car_id}:", reply_markup=nav_keyboard(rows))
        bot.register_next_step_handler(msg, send_admin_warning, car_id)

    elif call.data.startswith("mod_del_"):
        if not is_admin(cid):
            return
        car_id = int(call.data.split("_")[2])
        rows = [['Фейк / Мошенничество', 'Нарушение правил площадки'], ['Некорректные данные / фото', 'Без указания причины']]
        msg = bot.send_message(cid, f"🗑 Выберите или напишите причину удаления объявления #{car_id}:", reply_markup=nav_keyboard(rows))
        bot.register_next_step_handler(msg, delete_car_with_reason, car_id)

    elif call.data == "adm_list":
        if not is_admin(cid):
            return
        admins = get_all_admins()
        text = "👥 Действующие администраторы:\n" + "\n".join([f"• {a}" for a in admins])
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("➕ Добавить админа", callback_data="adm_add"))
        for a in admins:
            if a != cid:
                markup.add(types.InlineKeyboardButton(f"➖ Удалить {a}", callback_data=f"adm_rem_{a}"))
        bot.send_message(cid, text, reply_markup=markup)

    elif call.data == "adm_add":
        if not is_admin(cid):
            return
        msg = bot.send_message(cid, "👤 Отправьте цифровой Telegram ID нового админа или перешлите любое его сообщение:", reply_markup=nav_keyboard())
        bot.register_next_step_handler(msg, add_new_admin_step)

    elif call.data.startswith("adm_rem_"):
        if not is_admin(cid):
            return
        rem_id = int(call.data.split("_")[2])
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute('DELETE FROM admins WHERE user_id = ?', (rem_id,))
        conn.commit()
        conn.close()
        bot.send_message(cid, f"✅ Администратор {rem_id} удален.")

print("Бот успешно запущен!")
bot.polling(none_stop=True)
