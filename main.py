import os
import sqlite3
import math
import telebot
from telebot import types
from geopy.geocoders import Nominatim

TOKEN = os.getenv('BOT_TOKEN') or os.getenv('TOKEN') or 'ВАШ_ТОКЕН_ОТ_BOTFATHER'
ADMIN_ID = 0

bot = telebot.TeleBot(TOKEN)
geolocator = Nominatim(user_agent="avtovinchik_bot_v5")

CAR_CATALOG = {
    "Лада (ВАЗ)": ["Приора", "Гранта", "Веста", "Нива", "2114", "2107", "Другая"],
    "Toyota": ["Camry", "Corolla", "RAV4", "Land Cruiser", "Mark II", "Другая"],
    "Hyundai": ["Solaris", "Elantra", "Creta", "Sonata", "Tucson", "Другая"],
    "Kia": ["Rio", "Ceed", "Optima", "Sportage", "K5", "Другая"],
    "Volkswagen": ["Polo", "Passat", "Tiguan", "Jetta", "Golf", "Другая"],
    "Nissan": ["Qashqai", "X-Trail", "Almera", "Teana", "Juke", "Другая"],
    "Ford": ["Focus", "Mondeo", "Fiesta", "Kuga", "Fusion", "Другая"],
    "Renault": ["Logan", "Duster", "Sandero", "Megane", "Kaptur", "Другая"],
    "Chevrolet": ["Cruze", "Lacetti", "Niva", "Aveo", "Cobalt", "Другая"],
    "BMW": ["3 серия", "5 серия", "X5", "X3", "7 серия", "Другая"],
    "Mercedes-Benz": ["C-класс", "E-класс", "S-класс", "GLC", "GLE", "Другая"],
    "Skoda": ["Octavia", "Rapid", "Superb", "Kodiaq", "Yeti", "Другая"]
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
        user_id INTEGER PRIMARY KEY,
        name TEXT
    )''')
    if ADMIN_ID:
        c.execute('INSERT OR IGNORE INTO admins (user_id, name) VALUES (?, ?)', (ADMIN_ID, 'Главный админ'))
    conn.commit()
    conn.close()

init_db()
temp_data = {}

def is_admin(user_id):
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM admins')
    count = c.fetchone()[0]
    if count == 0:
        c.execute('INSERT INTO admins (user_id, name) VALUES (?, ?)', (user_id, 'Главный админ'))
        conn.commit()
        conn.close()
        return True
    c.execute('SELECT 1 FROM admins WHERE user_id = ?', (user_id,))
    res = c.fetchone()
    conn.close()
    return bool(res)

def get_all_admins():
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('SELECT user_id, name FROM admins')
    res = c.fetchall()
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

def main_menu(user_id=None):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('🚗 Купить авто', '💰 Продать авто')
    markup.row('⚙️ Мой фильтр', '📋 Мои объявления')
    if user_id and is_admin(user_id):
        markup.row('👑 Админ-панель')
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    get_user_filter(message.chat.id)
    bot.send_message(
        message.chat.id,
        "👋 Добро пожаловать на Авторынок!\nВыберите действие в меню ниже:",
        reply_markup=main_menu(message.chat.id)
    )

# ================= АДМИН-ПАНЕЛЬ =================
@bot.message_handler(commands=['admin'])
@bot.message_handler(func=lambda m: m.text == '👑 Админ-панель')
def open_admin_panel(message):
    if not is_admin(message.chat.id):
        bot.send_message(message.chat.id, "⛔ У вас нет прав администратора.")
        return

    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM cars WHERE status = 'pending'")
    pending_cnt = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM cars WHERE status = 'approved'")
    approved_cnt = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM admins")
    admins_cnt = c.fetchone()[0]
    conn.close()

    text = (
        "👑 **Панель администратора**\n\n"
        f"⏳ Ждут проверки: **{pending_cnt}**\n"
        f"✅ В продаже: **{approved_cnt}**\n"
        f"👥 Администраторов: **{admins_cnt}**"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(f"⏳ На модерации ({pending_cnt})", callback_data="adm_pending"))
    markup.add(types.InlineKeyboardButton(f"📋 Все объявления ({approved_cnt})", callback_data="adm_all_0"))
    markup.add(types.InlineKeyboardButton("👥 Управление админами", callback_data="adm_list"))
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

def send_admin_car_card(chat_id, car, mode="pending", offset=0):
    # car: 0:id, 1:uid, 2:uname, 3:photo, 4:brand, 5:model, 6:year, 7:price, 8:cond, 9:docs, 10:desc, 11:city, 12:lat, 13:lon, 14:status
    price_str = f"{car[7]:,}".replace(',', ' ')
    author = f"@{car[2]}" if car[2] else f"ID {car[1]}"
    caption = (
        f"🆔 **Объявление #{car[0]}** ({car[14]})\n"
        f"👤 Автор: {author}\n"
        f"🚘 **{car[4]} {car[5]}, {car[6]} г.**\n"
        f"💰 Цена: **{price_str} ₽**\n"
        f"📍 Город: {car[11]}\n"
        f"🛠 Состояние: {car[8]}\n"
        f"📄 Документы: {car[9]}\n\n"
        f"📝 {car[10]}"
    )
    markup = types.InlineKeyboardMarkup()
    if mode == "pending":
        markup.row(
            types.InlineKeyboardButton("✅ Одобрить", callback_data=f"adm_ok_{car[0]}"),
            types.InlineKeyboardButton("⚠️ Предупреждение", callback_data=f"adm_warn_{car[0]}")
        )
        markup.row(
            types.InlineKeyboardButton("📞 Автор", callback_data=f"adm_contact_{car[0]}"),
            types.InlineKeyboardButton("🗑 Удалить", callback_data=f"adm_del_{car[0]}")
        )
    else:
        markup.row(
            types.InlineKeyboardButton("⚠️ Предупреждение", callback_data=f"adm_warn_{car[0]}"),
            types.InlineKeyboardButton("🗑 Удалить", callback_data=f"adm_del_{car[0]}")
        )
        markup.row(
            types.InlineKeyboardButton("📞 Написать автору", callback_data=f"adm_contact_{car[0]}")
        )
        nav = []
        if offset > 0:
            nav.append(types.InlineKeyboardButton("⬅️ Пред.", callback_data=f"adm_all_{offset-1}"))
        nav.append(types.InlineKeyboardButton("След. ➡️", callback_data=f"adm_all_{offset+1}"))
        markup.row(*nav)

    bot.send_photo(chat_id, car[3], caption=caption, parse_mode='Markdown', reply_markup=markup)

def process_adm_warn(message, car_id):
    if message.text == '❌ Отмена':
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('SELECT user_id, brand, model, year FROM cars WHERE id = ?', (car_id,))
    car = c.fetchone()
    conn.close()
    if car:
        try:
            bot.send_message(
                car[0],
                f"⚠️ **Предупреждение от администратора!**\n\n"
                f"По вашему объявлению: **{car[1]} {car[2]}, {car[3]} г.** (#{car_id})\n"
                f"📝 Замечание: {message.text}\n\n"
                f"Отредактируйте объявление в разделе «📋 Мои объявления».",
                parse_mode='Markdown'
            )
            bot.send_message(message.chat.id, "✅ Предупреждение отправлено автору!", reply_markup=main_menu(message.chat.id))
        except:
            bot.send_message(message.chat.id, "❌ Не удалось отправить сообщение автору (возможно, он заблокировал бота).", reply_markup=main_menu(message.chat.id))

def process_adm_del_reason(message, car_id):
    if message.text == '❌ Отмена':
        bot.send_message(message.chat.id, "Удаление отменено.", reply_markup=main_menu(message.chat.id))
        return
    reason = "Без указания причины" if message.text == 'Без причины' else message.text
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('SELECT user_id, brand, model, year FROM cars WHERE id = ?', (car_id,))
    car = c.fetchone()
    if car:
        c.execute('DELETE FROM cars WHERE id = ?', (car_id,))
        c.execute('DELETE FROM viewed WHERE car_id = ?', (car_id,))
        conn.commit()
        try:
            bot.send_message(
                car[0],
                f"🗑 **Ваше объявление удалено администратором**\n\n"
                f"🚘 Авто: **{car[1]} {car[2]}, {car[3]} г.** (#{car_id})\n"
                f"📌 Причина: {reason}",
                parse_mode='Markdown'
            )
        except:
            pass
    conn.close()
    bot.send_message(message.chat.id, f"✅ Объявление #{car_id} удалено.", reply_markup=main_menu(message.chat.id))

def process_add_admin(message):
    if message.text == '❌ Отмена':
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    new_id = None
    name = "Админ"
    if message.forward_from:
        new_id = message.forward_from.id
        name = message.forward_from.first_name or "Админ"
    elif message.text and message.text.strip().isdigit():
        new_id = int(message.text.strip())
    else:
        msg = bot.send_message(message.chat.id, "❌ Пришлите цифровой ID пользователя или перешлите его сообщение:")
        bot.register_next_step_handler(msg, process_add_admin)
        return

    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO admins (user_id, name) VALUES (?, ?)', (new_id, name))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, f"✅ Пользователь `{new_id}` ({name}) назначен администратором!", parse_mode='Markdown', reply_markup=main_menu(message.chat.id))

# ================= МОИ ОБЪЯВЛЕНИЯ =================
@bot.message_handler(func=lambda m: m.text == '📋 Мои объявления')
def my_cars(message):
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('SELECT id, brand, model, year, price, status FROM cars WHERE user_id = ?', (message.chat.id,))
    cars = c.fetchall()
    conn.close()

    if not cars:
        bot.send_message(message.chat.id, "📭 У вас пока нет размещенных объявлений.")
        return

    for car in cars:
        st = "⏳ На проверке" if car[5] == 'pending' else "✅ Опубликовано"
        price_str = f"{car[4]:,}".replace(',', ' ')
        text = f"🚘 **{car[1]} {car[2]}, {car[3]} г.** (#{car[0]})\n💰 Цена: **{price_str} ₽**\n📊 Статус: {st}"
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✏️ Цена", callback_data=f"my_price_{car[0]}"),
            types.InlineKeyboardButton("📝 Описание", callback_data=f"my_desc_{car[0]}")
        )
        markup.add(types.InlineKeyboardButton("🗑 Снять с продажи", callback_data=f"my_del_{car[0]}"))
        bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

def edit_my_price(message, car_id):
    if message.text == '❌ Отмена':
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    if not message.text or not message.text.isdigit():
        msg = bot.send_message(message.chat.id, "❌ Введите новую цену цифрами:")
        bot.register_next_step_handler(msg, edit_my_price, car_id)
        return
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('UPDATE cars SET price = ? WHERE id = ? AND user_id = ?', (int(message.text), car_id, message.chat.id))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ Цена успешно обновлена!", reply_markup=main_menu(message.chat.id))

def edit_my_desc(message, car_id):
    if message.text == '❌ Отмена':
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('UPDATE cars SET description = ? WHERE id = ? AND user_id = ?', (message.text.strip(), car_id, message.chat.id))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ Описание успешно обновлено!", reply_markup=main_menu(message.chat.id))

# ================= ВЕТКА ПРОДАЖИ =================
def back_cancel_markup(extra_rows=None):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if extra_rows:
        for r in extra_rows:
            markup.row(*r)
    markup.row('⬅️ Назад', '❌ Отмена')
    return markup

@bot.message_handler(func=lambda m: m.text == '💰 Продать авто')
def sell_start(message):
    temp_data[message.chat.id] = {'username': message.from_user.username}
    ask_photo(message.chat.id)

def ask_photo(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('⬅️ В главное меню')
    msg = bot.send_message(chat_id, "📸 Шаг 1/9: Отправьте **фотографию** автомобиля:", parse_mode='Markdown', reply_markup=markup)
    bot.register_next_step_handler(msg, get_photo)

def get_photo(message):
    if message.text == '⬅️ В главное меню':
        bot.send_message(message.chat.id, "Главное меню:", reply_markup=main_menu(message.chat.id))
        return
    if not message.photo:
        msg = bot.send_message(message.chat.id, "❌ Отправьте именно фотографию (картинкой):")
        bot.register_next_step_handler(msg, get_photo)
        return
    temp_data[message.chat.id]['photo'] = message.photo[-1].file_id
    ask_brand(message.chat.id)

def ask_brand(chat_id):
    brands = list(CAR_CATALOG.keys())
    rows = [brands[i:i+3] for i in range(0, len(brands), 3)]
    rows.append(['✍️ Другая марка'])
    msg = bot.send_message(chat_id, "🚘 Шаг 2/9: Выберите **марку** авто из списка или нажмите «Другая марка»:", parse_mode='Markdown', reply_markup=back_cancel_markup(rows))
    bot.register_next_step_handler(msg, get_brand)

def get_brand(message):
    if message.text == '❌ Отмена':
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    if message.text == '⬅️ Назад':
        ask_photo(message.chat.id)
        return
    if not message.text:
        ask_brand(message.chat.id)
        return
    if message.text == '✍️ Другая марка':
        msg = bot.send_message(message.chat.id, "✍️ Напишите **марку** автомобиля текстом:", parse_mode='Markdown', reply_markup=back_cancel_markup())
        bot.register_next_step_handler(msg, get_custom_brand)
        return
    temp_data[message.chat.id]['brand'] = message.text.strip()
    ask_model(message.chat.id)

def get_custom_brand(message):
    if message.text == '❌ Отмена':
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    if message.text == '⬅️ Назад':
        ask_brand(message.chat.id)
        return
    temp_data[message.chat.id]['brand'] = message.text.strip()
    ask_model(message.chat.id)

def ask_model(chat_id):
    brand = temp_data[chat_id].get('brand', '')
    models = CAR_CATALOG.get(brand, [])
    if models:
        rows = [models[i:i+3] for i in range(0, len(models), 3)]
        msg = bot.send_message(chat_id, f"📝 Шаг 3/9: Выберите **модель** для {brand}:", parse_mode='Markdown', reply_markup=back_cancel_markup(rows))
    else:
        msg = bot.send_message(chat_id, f"📝 Шаг 3/9: Напишите **модель** для {brand} текстом:", parse_mode='Markdown', reply_markup=back_cancel_markup())
    bot.register_next_step_handler(msg, get_model)

def get_model(message):
    if message.text == '❌ Отмена':
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    if message.text == '⬅️ Назад':
        ask_brand(message.chat.id)
        return
    if message.text == 'Другая':
        msg = bot.send_message(message.chat.id, "✍️ Напишите название **модели** текстом:", parse_mode='Markdown', reply_markup=back_cancel_markup())
        bot.register_next_step_handler(msg, get_custom_model)
        return
    temp_data[message.chat.id]['model'] = message.text.strip()
    ask_year(message.chat.id)

def get_custom_model(message):
    if message.text == '❌ Отмена':
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    if message.text == '⬅️ Назад':
        ask_model(message.chat.id)
        return
    temp_data[message.chat.id]['model'] = message.text.strip()
    ask_year(message.chat.id)

def ask_year(chat_id):
    msg = bot.send_message(chat_id, "📅 Шаг 4/9: Укажите **год выпуска** (только цифры, например: 2015):", parse_mode='Markdown', reply_markup=back_cancel_markup())
    bot.register_next_step_handler(msg, get_year)

def get_year(message):
    if message.text == '❌ Отмена':
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    if message.text == '⬅️ Назад':
        ask_model(message.chat.id)
        return
    if not message.text or not message.text.isdigit():
        msg = bot.send_message(message.chat.id, "❌ Введите год цифрами (например: 2012):")
        bot.register_next_step_handler(msg, get_year)
        return
    temp_data[message.chat.id]['year'] = int(message.text)
    ask_price(message.chat.id)

def ask_price(chat_id):
    msg = bot.send_message(chat_id, "💵 Шаг 5/9: Укажите **цену в рублях** (только цифры, например: 450000):", parse_mode='Markdown', reply_markup=back_cancel_markup())
    bot.register_next_step_handler(msg, get_price)

def get_price(message):
    if message.text == '❌ Отмена':
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    if message.text == '⬅️ Назад':
        ask_year(message.chat.id)
        return
    if not message.text or not message.text.isdigit():
        msg = bot.send_message(message.chat.id, "❌ Введите цену только цифрами без пробелов:")
        bot.register_next_step_handler(msg, get_price)
        return
    temp_data[message.chat.id]['price'] = int(message.text)
    ask_condition(message.chat.id)

def ask_condition(chat_id):
    rows = [['Отличное / Не требует вложений'], ['На ходу / Есть нюансы'], ['Требует ремонта / Битая']]
    msg = bot.send_message(chat_id, "🛠 Шаг 6/9: Выберите **состояние** автомобиля:", parse_mode='Markdown', reply_markup=back_cancel_markup(rows))
    bot.register_next_step_handler(msg, get_condition)

def get_condition(message):
    if message.text == '❌ Отмена':
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    if message.text == '⬅️ Назад':
        ask_price(message.chat.id)
        return
    temp_data[message.chat.id]['condition'] = message.text.strip()
    ask_docs(message.chat.id)

def ask_docs(chat_id):
    rows = [['✅ Чистые (без проблем)'], ['⚠️ Есть проблемы (запрет, утиль, без ПТС)']]
    msg = bot.send_message(chat_id, "📄 Шаг 7/9: Что с **документами**?", parse_mode='Markdown', reply_markup=back_cancel_markup(rows))
    bot.register_next_step_handler(msg, get_docs)

def get_docs(message):
    if message.text == '❌ Отмена':
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    if message.text == '⬅️ Назад':
        ask_condition(message.chat.id)
        return
    temp_data[message.chat.id]['docs'] = message.text.strip()
    ask_desc(message.chat.id)

def ask_desc(chat_id):
    msg = bot.send_message(chat_id, "✍️ Шаг 8/9: Напишите **описание** (двигатель, коробка, косяки, торг):", parse_mode='Markdown', reply_markup=back_cancel_markup())
    bot.register_next_step_handler(msg, get_desc)

def get_desc(message):
    if message.text == '❌ Отмена':
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    if message.text == '⬅️ Назад':
        ask_docs(message.chat.id)
        return
    temp_data[message.chat.id]['description'] = message.text.strip()
    ask_loc_sell(message.chat.id)

def ask_loc_sell(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("📍 Отправить мою геопозицию", request_location=True))
    markup.row('⬅️ Назад', '❌ Отмена')
    msg = bot.send_message(chat_id, "🌍 Шаг 9/9: Отправьте **геопозицию** кнопкой или напишите **город** текстом (например: Абинск):", parse_mode='Markdown', reply_markup=markup)
    bot.register_next_step_handler(msg, get_location_sell)

def get_location_sell(message):
    if message.text == '❌ Отмена':
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    if message.text == '⬅️ Назад':
        ask_desc(message.chat.id)
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
    c.execute('''INSERT INTO cars (user_id, username, photo, brand, model, year, price, condition, docs, description, city, lat, lon, status)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')''',
              (message.chat.id, d['username'], d['photo'], d['brand'], d['model'], d['year'],
               d['price'], d['condition'], d['docs'], d['description'], city_name, lat, lon))
    car_id = c.lastrowid
    c.execute('SELECT * FROM cars WHERE id = ?', (car_id,))
    new_car = c.fetchone()
    conn.commit()
    conn.close()
    del temp_data[message.chat.id]

    bot.send_message(message.chat.id, "✅ **Объявление отправлено на модерацию!** Как только админ проверит его, оно появится в поиске.", parse_mode='Markdown', reply_markup=main_menu(message.chat.id))

    for adm_id, _ in get_all_admins():
        try:
            bot.send_message(adm_id, "🔔 **Новое объявление на проверку!**", parse_mode='Markdown')
            send_admin_car_card(adm_id, new_car, mode="pending")
        except:
            pass

# ================= ФИЛЬТРЫ ПОКУПАТЕЛЯ =================
def send_filter_menu(chat_id, message_id=None):
    f = get_user_filter(chat_id)
    docs_text = "Только чистые" if f[11] == 1 else "Все"
    loc_text = f"{f[7]} (+{f[10]} км)" if f[7] != 'Не задан' else "Вся Россия"
    price_to_str = "без потолка" if f[6] >= 99999999 else f"{f[6]:,} ₽".replace(',', ' ')
    price_from_str = f"{f[5]:,} ₽".replace(',', ' ')

    text = (
        "⚙️ **Ваши фильтры поиска:**\n\n"
        f"🚘 **Марка:** {f[1]}\n"
        f"📝 **Модель:** {f[2]}\n"
        f"📅 **Год:** от {f[3]} до {f[4]}\n"
        f"💰 **Цена:** от {price_from_str} до {price_to_str}\n"
        f"📍 **Локация:** {loc_text}\n"
        f"📄 **Документы:** {docs_text}"
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
        types.InlineKeyboardButton(f"📍 Локация", callback_data="f_loc"),
        types.InlineKeyboardButton(f"📄 Документы", callback_data="f_docs")
    )
    markup.row(
        types.InlineKeyboardButton("🔄 Сбросить всё", callback_data="f_reset"),
        types.InlineKeyboardButton("🔍 Показать авто", callback_data="f_search")
    )
    markup.add(types.InlineKeyboardButton("⬅️ Назад в главное меню", callback_data="to_main"))

    if message_id:
        bot.edit_message_text(text, chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
    else:
        bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == '⚙️ Мой фильтр')
def open_filter_menu(message):
    send_filter_menu(message.chat.id)

def set_f_brand(message):
    if message.text == '⬅️ Назад':
        bot.send_message(message.chat.id, "Возврат в фильтры:", reply_markup=main_menu(message.chat.id))
        send_filter_menu(message.chat.id)
        return
    val = 'Любая' if message.text in ['Любая', '✍️ Другая марка'] else message.text.strip()
    update_filter_field(message.chat.id, 'brand', val)
    update_filter_field(message.chat.id, 'model', 'Любая')
    bot.send_message(message.chat.id, f"✅ Выбрана марка: {val}", reply_markup=main_menu(message.chat.id))
    send_filter_menu(message.chat.id)

def set_f_model(message):
    if message.text == '⬅️ Назад':
        bot.send_message(message.chat.id, "Возврат в фильтры:", reply_markup=main_menu(message.chat.id))
        send_filter_menu(message.chat.id)
        return
    val = 'Любая' if message.text in ['Любая', 'Другая'] else message.text.strip()
    update_filter_field(message.chat.id, 'model', val)
    bot.send_message(message.chat.id, f"✅ Выбрана модель: {val}", reply_markup=main_menu(message.chat.id))
    send_filter_menu(message.chat.id)

def set_f_year(message):
    if message.text == '⬅️ Назад':
        bot.send_message(message.chat.id, "Возврат в фильтры:", reply_markup=main_menu(message.chat.id))
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
        bot.send_message(message.chat.id, "✅ Год обновлен!", reply_markup=main_menu(message.chat.id))
        send_filter_menu(message.chat.id)
    else:
        msg = bot.send_message(message.chat.id, "❌ Напишите два года через пробел (например: `2008 2016`):", parse_mode='Markdown')
        bot.register_next_step_handler(msg, set_f_year)

def set_f_price(message):
    if message.text == '⬅️ Назад':
        bot.send_message(message.chat.id, "Возврат в фильтры:", reply_markup=main_menu(message.chat.id))
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
        bot.send_message(message.chat.id, "✅ Цена обновлена!", reply_markup=main_menu(message.chat.id))
        send_filter_menu(message.chat.id)
    else:
        msg = bot.send_message(message.chat.id, "❌ Напишите две суммы через пробел (например: `150000 600000`):", parse_mode='Markdown')
        bot.register_next_step_handler(msg, set_f_price)

def set_f_loc_step1(message):
    if message.text == '⬅️ Назад':
        bot.send_message(message.chat.id, "Возврат в фильтры:", reply_markup=main_menu(message.chat.id))
        send_filter_menu(message.chat.id)
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
    markup.row('⬅️ Назад')
    msg = bot.send_message(message.chat.id, f"📍 Выбран город: **{city_name}**.\nВыберите или введите **радиус поиска в км**:", parse_mode='Markdown', reply_markup=markup)
    bot.register_next_step_handler(msg, set_f_loc_step2)

def set_f_loc_step2(message):
    if message.text == '⬅️ Назад':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("📍 Моя текущая геопозиция", request_location=True))
        markup.row('⬅️ Назад')
        msg = bot.send_message(message.chat.id, "🌍 Отправьте вашу **геопозицию** или напишите **город**:", parse_mode='Markdown', reply_markup=markup)
        bot.register_next_step_handler(msg, set_f_loc_step1)
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
    bot.send_message(message.chat.id, "✅ Локация обновлена!", reply_markup=main_menu(message.chat.id))
    send_filter_menu(message.chat.id)

def update_filter_field(user_id, field, value):
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute(f'UPDATE filters SET {field} = ? WHERE user_id = ?', (value, user_id))
    c.execute('DELETE FROM viewed WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

# ================= ЛЕНТА АНКЕТ И ЖАЛОБЫ =================
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
        markup.add(types.InlineKeyboardButton("⬅️ В главное меню", callback_data="to_main"))
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
    markup.row(
        types.InlineKeyboardButton("❤️ Контакт продавца", callback_data=f"like_{found_car[0]}"),
        types.InlineKeyboardButton("👎 Дальше", callback_data="next_car")
    )
    markup.row(
        types.InlineKeyboardButton("⚙️ Фильтр", callback_data="open_filters"),
        types.InlineKeyboardButton("🚩 Пожаловаться", callback_data=f"report_{found_car[0]}")
    )
    markup.add(types.InlineKeyboardButton("⬅️ В меню", callback_data="to_main"))

    bot.send_photo(user_id, found_car[3], caption=caption, parse_mode='Markdown', reply_markup=markup)

def process_user_report(message, car_id):
    if message.text == '❌ Отмена':
        bot.send_message(message.chat.id, "Жалоба отменена.", reply_markup=main_menu(message.chat.id))
        return
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('SELECT * FROM cars WHERE id = ?', (car_id,))
    car = c.fetchone()
    conn.close()
    if car:
        reporter = f"@{message.from_user.username}" if message.from_user.username else f"ID {message.chat.id}"
        for adm_id, _ in get_all_admins():
            try:
                bot.send_message(adm_id, f"🚨 **Жалоба от покупателя ({reporter})!**\n📌 Причина: {message.text}", parse_mode='Markdown')
                send_admin_car_card(adm_id, car, mode="all", offset=0)
            except:
                pass
    bot.send_message(message.chat.id, "✅ Спасибо! Жалоба передана администраторам на проверку.", reply_markup=main_menu(message.chat.id))

# ================= ОБРАБОТЧИК ВСЕХ ИНЛАЙН-КНОПОК =================
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    cid = call.message.chat.id
    bot.answer_callback_query(call.id)

    if call.data == "to_main":
        bot.send_message(cid, "Главное меню:", reply_markup=main_menu(cid))
    elif call.data == "open_filters":
        send_filter_menu(cid)
    elif call.data == "f_brand":
        brands = list(CAR_CATALOG.keys())
        rows = [brands[i:i+3] for i in range(0, len(brands), 3)]
        rows.append(['Любая', '⬅️ Назад'])
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for r in rows:
            markup.row(*r)
        msg = bot.send_message(cid, "🚘 Выберите **марку** из списка или напишите свою:", parse_mode='Markdown', reply_markup=markup)
        bot.register_next_step_handler(msg, set_f_brand)
    elif call.data == "f_model":
        f = get_user_filter(cid)
        models = CAR_CATALOG.get(f[1], [])
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        if models:
            for i in range(0, len(models), 3):
                markup.row(*models[i:i+3])
        markup.row('Любая', '⬅️ Назад')
        msg = bot.send_message(cid, "📝 Выберите **модель** или напишите текстом:", parse_mode='Markdown', reply_markup=markup)
        bot.register_next_step_handler(msg, set_f_model)
    elif call.data == "f_year":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row('⬅️ Назад')
        msg = bot.send_message(cid, "📅 Введите **год от и до** через пробел (например: `2008 2018`):", parse_mode='Markdown', reply_markup=markup)
        bot.register_next_step_handler(msg, set_f_year)
    elif call.data == "f_price":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row('⬅️ Назад')
        msg = bot.send_message(cid, "💰 Введите **цену от и до** в рублях через пробел (например: `200000 700000`):", parse_mode='Markdown', reply_markup=markup)
        bot.register_next_step_handler(msg, set_f_price)
    elif call.data == "f_loc":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("📍 Моя текущая геопозиция", request_location=True))
        markup.row('⬅️ Назад')
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
            bot.send_message(cid, f"📞 Ссылка на профиль продавца: [Написать](tg://user?id={res[1]})", parse_mode='Markdown')
        show_next_car(cid)
    elif call.data.startswith("report_"):
        car_id = int(call.data.split("_")[1])
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row('Фейк / Мошенники', 'Неверная цена / Описание')
        markup.row('Битая / Проблемы с доками скрыты', '❌ Отмена')
        msg = bot.send_message(cid, "🚩 Выберите или напишите **причину жалобы** на это объявление:", parse_mode='Markdown', reply_markup=markup)
        bot.register_next_step_handler(msg, process_user_report, car_id)

    # --- Мои объявления ---
    elif call.data.startswith("my_price_"):
        car_id = int(call.data.split("_")[2])
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row('❌ Отмена')
        msg = bot.send_message(cid, "💰 Введите **новую цену** в рублях (только цифры):", parse_mode='Markdown', reply_markup=markup)
        bot.register_next_step_handler(msg, edit_my_price, car_id)
    elif call.data.startswith("my_desc_"):
        car_id = int(call.data.split("_")[2])
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row('❌ Отмена')
        msg = bot.send_message(cid, "📝 Напишите **новое описание** автомобиля:", parse_mode='Markdown', reply_markup=markup)
        bot.register_next_step_handler(msg, edit_my_desc, car_id)
    elif call.data.startswith("my_del_"):
        car_id = int(call.data.split("_")[2])
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute('DELETE FROM cars WHERE id = ? AND user_id = ?', (car_id, cid))
        c.execute('DELETE FROM viewed WHERE car_id = ?', (car_id,))
        conn.commit()
        conn.close()
        bot.edit_message_text("✅ Объявление снято с продажи и удалено.", cid, call.message.message_id)

    # --- Админ-панель ---
    elif call.data == "adm_pending":
        if not is_admin(cid): return
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute("SELECT * FROM cars WHERE status = 'pending' LIMIT 1")
        car = c.fetchone()
        conn.close()
        if not car:
            bot.send_message(cid, "✅ Новых объявлений на модерации нет!")
        else:
            send_admin_car_card(cid, car, mode="pending")
    elif call.data.startswith("adm_all_"):
        if not is_admin(cid): return
        offset = int(call.data.split("_")[2])
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute("SELECT * FROM cars WHERE status = 'approved' ORDER BY id DESC LIMIT 1 OFFSET ?", (offset,))
        car = c.fetchone()
        conn.close()
        if not car:
            bot.send_message(cid, "🏁 Больше опубликованных объявлений нет.")
        else:
            send_admin_car_card(cid, car, mode="all", offset=offset)
    elif call.data.startswith("adm_ok_"):
        if not is_admin(cid): return
        car_id = int(call.data.split("_")[2])
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute("UPDATE cars SET status = 'approved' WHERE id = ?", (car_id,))
        c.execute("SELECT user_id, brand, model FROM cars WHERE id = ?", (car_id,))
        car = c.fetchone()
        conn.commit()
        conn.close()
        bot.send_message(cid, f"✅ Объявление #{car_id} одобрено и опубликовано!")
        if car:
            try:
                bot.send_message(car[0], f"🎉 Ваше объявление **{car[1]} {car[2]}** (#{car_id}) прошло проверку и опубликовано!", parse_mode='Markdown')
            except:
                pass
    elif call.data.startswith("adm_warn_"):
        if not is_admin(cid): return
        car_id = int(call.data.split("_")[2])
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row('Загрузите реальные фото авто', 'Уточните состояние документов')
        markup.row('Укажите реальную цену', '❌ Отмена')
        msg = bot.send_message(cid, f"⚠️ Выберите или напишите текст **предупреждения** для объявления #{car_id}:", parse_mode='Markdown', reply_markup=markup)
        bot.register_next_step_handler(msg, process_adm_warn, car_id)
    elif call.data.startswith("adm_del_"):
        if not is_admin(cid): return
        car_id = int(call.data.split("_")[2])
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row('Фейк / Мошенничество', 'Не соответствует правилам')
        markup.row('Без причины', '❌ Отмена')
        msg = bot.send_message(cid, f"🗑 Выберите или напишите **причину удаления** объявления #{car_id}:", parse_mode='Markdown', reply_markup=markup)
        bot.register_next_step_handler(msg, process_adm_del_reason, car_id)
    elif call.data.startswith("adm_contact_"):
        if not is_admin(cid): return
        car_id = int(call.data.split("_")[2])
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute('SELECT username, user_id FROM cars WHERE id = ?', (car_id,))
        res = c.fetchone()
        conn.close()
        if res and res[0]:
            bot.send_message(cid, f"📞 Автор объявления #{car_id}: @{res[0]}")
        elif res:
            bot.send_message(cid, f"📞 Ссылка на автора #{car_id}: [Написать](tg://user?id={res[1]})", parse_mode='Markdown')
    elif call.data == "adm_list":
        if not is_admin(cid): return
        admins = get_all_admins()
        text = "👥 **Список администраторов:**\n\n" + "\n".join([f"• `{uid}` — {name}" for uid, name in admins])
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("➕ Добавить админа", callback_data="adm_add"))
        for uid, name in admins:
            if uid != cid:
                markup.add(types.InlineKeyboardButton(f"❌ Удалить {name} ({uid})", callback_data=f"adm_rem_{uid}"))
        bot.send_message(cid, text, parse_mode='Markdown', reply_markup=markup)
    elif call.data == "adm_add":
        if not is_admin(cid): return
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row('❌ Отмена')
        msg = bot.send_message(cid, "👤 Пришлите **цифровой Telegram ID** нового админа или просто **перешлите сюда любое его сообщение**:", parse_mode='Markdown', reply_markup=markup)
        bot.register_next_step_handler(msg, process_add_admin)
    elif call.data.startswith("adm_rem_"):
        if not is_admin(cid): return
        rem_id = int(call.data.split("_")[2])
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute('DELETE FROM admins WHERE user_id = ?', (rem_id,))
        conn.commit()
        conn.close()
        bot.send_message(cid, f"✅ Администратор `{rem_id}` удален.", parse_mode='Markdown')

print("Бот Авторынок с админкой и жалобами запущен!")
bot.polling(none_stop=True)
