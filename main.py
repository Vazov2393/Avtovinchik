import os
import math
import sqlite3
import telebot
from telebot import types
from geopy.geocoders import Nominatim

TOKEN = os.environ.get('BOT_TOKEN') or os.environ.get('TOKEN') or 'ВАШ_ТОКЕН_ОТ_BOTFATHER'
ADMIN_ID = None

bot = telebot.TeleBot(TOKEN)
geolocator = Nominatim(user_agent="avtovinchik_bot_v5")

BRANDS = {
    "Лада (ВАЗ)": ["Приора", "Гранта", "Веста", "Нива", "2114", "2110", "2107"],
    "Toyota": ["Camry", "Corolla", "RAV4", "Land Cruiser", "Mark II"],
    "Hyundai": ["Solaris", "Accent", "Creta", "Sonata", "Tucson"],
    "Kia": ["Rio", "Ceed", "Optima", "Sportage", "Cerato"],
    "Volkswagen": ["Polo", "Passat", "Tiguan", "Golf", "Jetta"],
    "Skoda": ["Octavia", "Rapid", "Superb", "Kodiaq"],
    "Nissan": ["Almera", "Qashqai", "X-Trail", "Teana"],
    "Ford": ["Focus", "Mondeo", "Fusion", "Kuga"],
    "Renault": ["Logan", "Duster", "Sandero", "Megane"],
    "Chevrolet": ["Cruze", "Lacetti", "Aveo", "Niva"],
    "BMW": ["3 серия", "5 серия", "X5", "X3"],
    "Mercedes-Benz": ["E-класс", "C-класс", "S-класс", "GLE"]
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
    c.execute('CREATE TABLE IF NOT EXISTS viewed (user_id INTEGER, car_id INTEGER)')
    c.execute('CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)')
    if ADMIN_ID:
        c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (int(ADMIN_ID),))
    conn.commit()
    conn.close()

init_db()
temp_data = {}

def get_admins():
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('SELECT user_id FROM admins')
    rows = [r[0] for r in c.fetchall()]
    conn.close()
    return rows

def is_admin(user_id):
    return user_id in get_admins()

def calc_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

def main_menu(user_id=None):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('🚗 Купить авто', '💰 Продать авто')
    markup.row('⚙️ Мой фильтр', '📋 Мои объявления')
    if user_id and is_admin(user_id):
        markup.row('👑 Админ-панель')
    return markup

def back_kb(*extra):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for row in extra:
        markup.row(*row)
    markup.row('⬅️ Назад', '❌ Отмена')
    return markup

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

def format_car_caption(car, dist_line=""):
    price_str = f"{car[7]:,}".replace(',', ' ')
    loc_str = dist_line if dist_line else f"📍 Город: {car[11]}"
    return (
        f"🚘 **{car[4]} {car[5]}, {car[6]} г.** (ID: #{car[0]})
"
        f"💰 Цена: **{price_str} ₽**
"
        f"{loc_str}
"
        f"🛠 Состояние: {car[8]}
"
        f"📄 Документы: {car[9]}

"
        f"📝 {car[10]}"
    )

@bot.message_handler(commands=['start'])
def start(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    get_user_filter(message.chat.id)
    if not get_admins():
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute('INSERT INTO admins (user_id) VALUES (?)', (message.chat.id,))
        conn.commit()
        conn.close()
    bot.send_message(message.chat.id, "👋 Добро пожаловать на Авторынок! Выберите действие:", reply_markup=main_menu(message.chat.id))

# ================= АДМИН-ПАНЕЛЬ =================
@bot.message_handler(commands=['admin'])
@bot.message_handler(func=lambda m: m.text == '👑 Админ-панель')
def admin_panel(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    if not get_admins():
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute('INSERT INTO admins (user_id) VALUES (?)', (message.chat.id,))
        conn.commit()
        conn.close()
    if not is_admin(message.chat.id):
        bot.send_message(message.chat.id, "⛔ У вас нет прав администратора.")
        return

    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM cars WHERE status='approved'")
    active_cnt = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM cars WHERE status='pending'")
    pend_cnt = c.fetchone()[0]
    conn.close()

    text = f"👑 **Панель администратора**

✅ В продаже: **{active_cnt}**
⏳ На проверке: **{pend_cnt}**"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(f"⏳ Очередь проверки ({pend_cnt})", callback_data="adm_pending"))
    markup.add(types.InlineKeyboardButton(f"📋 Все объявления ({active_cnt})", callback_data="adm_all_0"))
    markup.add(types.InlineKeyboardButton("👥 Управление админами", callback_data="adm_list"))
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=markup)

def admin_car_markup(car_id, nav_buttons=None):
    markup = types.InlineKeyboardMarkup()
    if nav_buttons:
        markup.row(*nav_buttons)
    markup.row(
        types.InlineKeyboardButton("⚠️ Предупреждение", callback_data=f"adm_warn_{car_id}"),
        types.InlineKeyboardButton("🗑 Удалить", callback_data=f"adm_del_{car_id}")
    )
    markup.add(types.InlineKeyboardButton("📞 Написать автору", callback_data=f"adm_contact_{car_id}"))
    return markup

def send_admin_all_car(chat_id, offset, message_id=None):
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM cars WHERE status='approved'")
    total = c.fetchone()[0]
    if total == 0:
        conn.close()
        bot.send_message(chat_id, "📭 Активных объявлений нет.")
        return
    offset = max(0, min(offset, total - 1))
    c.execute("SELECT * FROM cars WHERE status='approved' ORDER BY id DESC LIMIT 1 OFFSET ?", (offset,))
    car = c.fetchone()
    conn.close()

    nav = []
    if offset > 0:
        nav.append(types.InlineKeyboardButton("⬅️ Пред.", callback_data=f"adm_all_{offset-1}"))
    nav.append(types.InlineKeyboardButton(f"{offset+1}/{total}", callback_data="noop"))
    if offset < total - 1:
        nav.append(types.InlineKeyboardButton("След. ➡️", callback_data=f"adm_all_{offset+1}"))

    markup = admin_car_markup(car[0], nav)
    caption = f"👮 **Патруль базы**

" + format_car_caption(car)
    if message_id:
        try:
            bot.delete_message(chat_id, message_id)
        except:
            pass
    bot.send_photo(chat_id, car[3], caption=caption, parse_mode='Markdown', reply_markup=markup)

def process_admin_warn(message, car_id):
    if message.text == '❌ Отмена':
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute("SELECT user_id, brand, model, year FROM cars WHERE id=?", (car_id,))
    car = c.fetchone()
    conn.close()
    if car:
        try:
            bot.send_message(
                car[0],
                f"⚠️ **Предупреждение от администратора!**
"
                f"По объявлению: **{car[1]} {car[2]} ({car[3]} г.)** [ID #{car_id}]

"
                f"📝 **Замечание:** {message.text}

"
                f"Пожалуйста, исправьте недочеты в разделе «📋 Мои объявления», иначе карточка будет удалена.",
                parse_mode='Markdown'
            )
            bot.send_message(message.chat.id, f"✅ Предупреждение отправлено автору объявления #{car_id}.", reply_markup=main_menu(message.chat.id))
        except:
            bot.send_message(message.chat.id, "❌ Не удалось отправить сообщение пользователю (возможно, он заблокировал бота).", reply_markup=main_menu(message.chat.id))

def process_admin_delete_reason(message, car_id):
    if message.text == '❌ Отмена':
        bot.send_message(message.chat.id, "Удаление отменено.", reply_markup=main_menu(message.chat.id))
        return
    reason = "Нарушение правил площадки" if message.text == 'Без указания причины' else message.text
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute("SELECT user_id, brand, model, year FROM cars WHERE id=?", (car_id,))
    car = c.fetchone()
    if car:
        c.execute("DELETE FROM cars WHERE id=?", (car_id,))
        c.execute("DELETE FROM viewed WHERE car_id=?", (car_id,))
        conn.commit()
        try:
            bot.send_message(
                car[0],
                f"🗑 **Ваше объявление удалено администратором!**
"
                f"Автомобиль: **{car[1]} {car[2]} ({car[3]} г.)** [ID #{car_id}]
"
                f"📝 **Причина:** {reason}",
                parse_mode='Markdown'
            )
        except:
            pass
    conn.close()
    bot.send_message(message.chat.id, f"✅ Объявление #{car_id} удалено. Причина отправлена автору.", reply_markup=main_menu(message.chat.id))

def process_add_admin(message):
    if message.text == '❌ Отмена':
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    new_id = message.forward_from.id if message.forward_from else (int(message.text.strip()) if message.text and message.text.strip().isdigit() else None)
    if not new_id:
        msg = bot.send_message(message.chat.id, "❌ Пришлите цифровой ID или перешлите сообщение от пользователя:")
        bot.register_next_step_handler(msg, process_add_admin)
        return
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (new_id,))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, f"✅ Пользователь `{new_id}` назначен администратором!", parse_mode='Markdown', reply_markup=main_menu(message.chat.id))

# ================= ПОДАЧА ОБЪЯВЛЕНИЯ (ПРОДАТЬ) =================
@bot.message_handler(func=lambda m: m.text == '💰 Продать авто')
def sell_start(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)
    temp_data[message.chat.id] = {'username': message.from_user.username}
    step_sell_photo(message.chat.id)

def step_sell_photo(cid):
    msg = bot.send_message(cid, "📸 **Шаг 1/9.** Отправьте **фотографию** автомобиля:", parse_mode='Markdown', reply_markup=back_kb())
    bot.register_next_step_handler(msg, get_photo)

def get_photo(message):
    cid = message.chat.id
    if message.text in ['⬅️ Назад', '❌ Отмена']:
        bot.send_message(cid, "Возврат в главное меню.", reply_markup=main_menu(cid))
        return
    if not message.photo:
        msg = bot.send_message(cid, "❌ Нужно отправить именно фото! Попробуйте еще раз:")
        bot.register_next_step_handler(msg, get_photo)
        return
    temp_data[cid]['photo'] = message.photo[-1].file_id
    step_sell_brand(cid)

def step_sell_brand(cid):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    b_list = list(BRANDS.keys())
    for i in range(0, len(b_list), 3):
        markup.row(*b_list[i:i+3])
    markup.row('✍️ Другая марка')
    markup.row('⬅️ Назад', '❌ Отмена')
    msg = bot.send_message(cid, "🚘 **Шаг 2/9.** Выберите **марку** авто из списка или нажмите «Другая марка»:", parse_mode='Markdown', reply_markup=markup)
    bot.register_next_step_handler(msg, get_brand)

def get_brand(message):
    cid = message.chat.id
    if message.text == '❌ Отмена':
        bot.send_message(cid, "Отменено.", reply_markup=main_menu(cid))
        return
    if message.text == '⬅️ Назад':
        step_sell_photo(cid)
        return
    if not message.text:
        step_sell_brand(cid)
        return
    if message.text == '✍️ Другая марка':
        msg = bot.send_message(cid, "✍️ Напишите название **марки** вручную:", parse_mode='Markdown', reply_markup=back_kb())
        bot.register_next_step_handler(msg, get_brand_manual)
        return
    temp_data[cid]['brand'] = message.text.strip()
    step_sell_model(cid)

def get_brand_manual(message):
    cid = message.chat.id
    if message.text == '❌ Отмена':
        bot.send_message(cid, "Отменено.", reply_markup=main_menu(cid))
        return
    if message.text == '⬅️ Назад':
        step_sell_brand(cid)
        return
    temp_data[cid]['brand'] = message.text.strip()
    step_sell_model(cid)

def step_sell_model(cid):
    brand = temp_data[cid].get('brand', '')
    models = BRANDS.get(brand, [])
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for i in range(0, len(models), 3):
        markup.row(*models[i:i+3])
    markup.row('✍️ Другая модель')
    markup.row('⬅️ Назад', '❌ Отмена')
    msg = bot.send_message(cid, f"📝 **Шаг 3/9.** Выберите или напишите **модель** ({brand}):", parse_mode='Markdown', reply_markup=markup)
    bot.register_next_step_handler(msg, get_model)

def get_model(message):
    cid = message.chat.id
    if message.text == '❌ Отмена':
        bot.send_message(cid, "Отменено.", reply_markup=main_menu(cid))
        return
    if message.text == '⬅️ Назад':
        step_sell_brand(cid)
        return
    if not message.text:
        step_sell_model(cid)
        return
    if message.text == '✍️ Другая модель':
        msg = bot.send_message(cid, "✍️ Напишите **модель** вручную:", parse_mode='Markdown', reply_markup=back_kb())
        bot.register_next_step_handler(msg, get_model_manual)
        return
    temp_data[cid]['model'] = message.text.strip()
    step_sell_year(cid)

def get_model_manual(message):
    cid = message.chat.id
    if message.text == '❌ Отмена':
        bot.send_message(cid, "Отменено.", reply_markup=main_menu(cid))
        return
    if message.text == '⬅️ Назад':
        step_sell_model(cid)
        return
    temp_data[cid]['model'] = message.text.strip()
    step_sell_year(cid)

def step_sell_year(cid):
    msg = bot.send_message(cid, "📅 **Шаг 4/9.** Укажите **год выпуска** (только цифры, например: `2015`):", parse_mode='Markdown', reply_markup=back_kb())
    bot.register_next_step_handler(msg, get_year)

def get_year(message):
    cid = message.chat.id
    if message.text == '❌ Отмена':
        bot.send_message(cid, "Отменено.", reply_markup=main_menu(cid))
        return
    if message.text == '⬅️ Назад':
        step_sell_model(cid)
        return
    if not message.text or not message.text.strip().isdigit():
        msg = bot.send_message(cid, "❌ Введите год цифрами (например: 2012):")
        bot.register_next_step_handler(msg, get_year)
        return
    temp_data[cid]['year'] = int(message.text.strip())
    step_sell_price(cid)

def step_sell_price(cid):
    msg = bot.send_message(cid, "💵 **Шаг 5/9.** Укажите **цену в рублях** (только цифры, например: `450000`):", parse_mode='Markdown', reply_markup=back_kb())
    bot.register_next_step_handler(msg, get_price)

def get_price(message):
    cid = message.chat.id
    if message.text == '❌ Отмена':
        bot.send_message(cid, "Отменено.", reply_markup=main_menu(cid))
        return
    if message.text == '⬅️ Назад':
        step_sell_year(cid)
        return
    if not message.text or not message.text.strip().isdigit():
        msg = bot.send_message(cid, "❌ Введите цену цифрами без пробелов:")
        bot.register_next_step_handler(msg, get_price)
        return
    temp_data[cid]['price'] = int(message.text.strip())
    step_sell_cond(cid)

def step_sell_cond(cid):
    markup = back_kb(['Отличное / Без вложений', 'На ходу / Есть нюансы'], ['Требует ремонта / Битая'])
    msg = bot.send_message(cid, "🛠 **Шаг 6/9.** Выберите **состояние** автомобиля:", parse_mode='Markdown', reply_markup=markup)
    bot.register_next_step_handler(msg, get_condition)

def get_condition(message):
    cid = message.chat.id
    if message.text == '❌ Отмена':
        bot.send_message(cid, "Отменено.", reply_markup=main_menu(cid))
        return
    if message.text == '⬅️ Назад':
        step_sell_price(cid)
        return
    temp_data[cid]['condition'] = message.text.strip()
    step_sell_docs(cid)

def step_sell_docs(cid):
    markup = back_kb(['✅ Чистые (без проблем)', '⚠️ Есть проблемы (запрет, утиль, без ПТС)'])
    msg = bot.send_message(cid, "📄 **Шаг 7/9.** Что с **документами**?", parse_mode='Markdown', reply_markup=markup)
    bot.register_next_step_handler(msg, get_docs)

def get_docs(message):
    cid = message.chat.id
    if message.text == '❌ Отмена':
        bot.send_message(cid, "Отменено.", reply_markup=main_menu(cid))
        return
    if message.text == '⬅️ Назад':
        step_sell_cond(cid)
        return
    temp_data[cid]['docs'] = message.text.strip()
    step_sell_desc(cid)

def step_sell_desc(cid):
    msg = bot.send_message(cid, "✍️ **Шаг 8/9.** Напишите **описание** (двигатель, коробка, косяки, торг):", parse_mode='Markdown', reply_markup=back_kb())
    bot.register_next_step_handler(msg, get_desc)

def get_desc(message):
    cid = message.chat.id
    if message.text == '❌ Отмена':
        bot.send_message(cid, "Отменено.", reply_markup=main_menu(cid))
        return
    if message.text == '⬅️ Назад':
        step_sell_docs(cid)
        return
    temp_data[cid]['description'] = message.text.strip()
    step_sell_loc(cid)

def step_sell_loc(cid):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("📍 Отправить мою геопозицию", request_location=True))
    markup.row('⬅️ Назад', '❌ Отмена')
    msg = bot.send_message(cid, "🌍 **Шаг 9/9.** Отправьте **геопозицию** кнопкой или напишите **город** текстом (например: Абинск):", parse_mode='Markdown', reply_markup=markup)
    bot.register_next_step_handler(msg, get_location_sell)

def get_location_sell(message):
    cid = message.chat.id
    if message.text == '❌ Отмена':
        bot.send_message(cid, "Отменено.", reply_markup=main_menu(cid))
        return
    if message.text == '⬅️ Назад':
        step_sell_desc(cid)
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
                msg = bot.send_message(cid, "❌ Город не найден. Напишите точнее (например: Краснодарский край, Абинск):")
                bot.register_next_step_handler(msg, get_location_sell)
                return
        except:
            msg = bot.send_message(cid, "❌ Ошибка поиска города. Отправьте геопозицию кнопкой:")
            bot.register_next_step_handler(msg, get_location_sell)
            return

    d = temp_data[cid]
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute('''INSERT INTO cars (user_id, username, photo, brand, model, year, price, condition, docs, description, city, lat, lon, status)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')''',
              (cid, d['username'], d['photo'], d['brand'], d['model'], d['year'],
               d['price'], d['condition'], d['docs'], d['description'], city_name, lat, lon))
    car_id = c.lastrowid
    c.execute("SELECT * FROM cars WHERE id=?", (car_id,))
    new_car = c.fetchone()
    conn.commit()
    conn.close()
    del temp_data[cid]

    bot.send_message(cid, "✅ **Объявление отправлено на модерацию!** Как только админ проверит его, оно появится в поиске.", parse_mode='Markdown', reply_markup=main_menu(cid))

    # Отправляем всем админам на модерацию
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Одобрить", callback_data=f"mod_ok_{car_id}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"mod_no_{car_id}")
    )
    markup.add(types.InlineKeyboardButton("⚠️ Предупреждение автору", callback_data=f"adm_warn_{car_id}"))
    for adm in get_admins():
        try:
            bot.send_photo(adm, new_car[3], caption="🆕 **Новая анкета на проверку!**

" + format_car_caption(new_car), parse_mode='Markdown', reply_markup=markup)
        except:
            pass

# ================= МОИ ОБЪЯВЛЕНИЯ =================
@bot.message_handler(func=lambda m: m.text == '📋 Мои объявления')
def my_cars(message):
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute("SELECT * FROM cars WHERE user_id=? ORDER BY id DESC", (message.chat.id,))
    cars = c.fetchall()
    conn.close()

    if not cars:
        bot.send_message(message.chat.id, "📭 У вас пока нет размещенных объявлений.")
        return

    st_map = {'pending': '⏳ На проверке', 'approved': '✅ Опубликовано', 'rejected': '❌ Отклонено'}
    for car in cars:
        st_text = st_map.get(car[14], car[14])
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✏️ Цена", callback_data=f"my_price_{car[0]}"),
            types.InlineKeyboardButton("📝 Описание", callback_data=f"my_desc_{car[0]}")
        )
        markup.add(types.InlineKeyboardButton("🗑 Снять с продажи", callback_data=f"my_del_{car[0]}"))
        bot.send_photo(message.chat.id, car[3], caption=f"Статус: **{st_text}**

" + format_car_caption(car), parse_mode='Markdown', reply_markup=markup)

def edit_my_price(message, car_id):
    if message.text in ['⬅️ Назад', '❌ Отмена']:
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    if not message.text or not message.text.strip().isdigit():
        msg = bot.send_message(message.chat.id, "❌ Введите новую цену цифрами:")
        bot.register_next_step_handler(msg, edit_my_price, car_id)
        return
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute("UPDATE cars SET price=? WHERE id=? AND user_id=?", (int(message.text.strip()), car_id, message.chat.id))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ Цена успешно обновлена!", reply_markup=main_menu(message.chat.id))

def edit_my_desc(message, car_id):
    if message.text in ['⬅️ Назад', '❌ Отмена']:
        bot.send_message(message.chat.id, "Отменено.", reply_markup=main_menu(message.chat.id))
        return
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute("UPDATE cars SET description=? WHERE id=? AND user_id=?", (message.text.strip(), car_id, message.chat.id))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "✅ Описание обновлено!", reply_markup=main_menu(message.chat.id))

# ================= ФИЛЬТРЫ ПОКУПАТЕЛЯ =================
def send_filter_menu(chat_id, message_id=None):
    f = get_user_filter(chat_id)
    docs_text = "Только чистые" if f[11] == 1 else "Все (включая проблемные)"
    loc_text = f"{f[7]} (+{f[10]} км)" if f[7] != 'Не задан' else "Вся Россия"
    p_to = "без потолка" if f[6] >= 99999999 else f"{f[6]:,} ₽".replace(',', ' ')
    p_from = f"{f[5]:,} ₽".replace(',', ' ')

    text = (
        "⚙️ **Ваши фильтры поиска:**

"
        f"🚘 **Марка:** {f[1]}
"
        f"📝 **Модель:** {f[2]}
"
        f"📅 **Год:** от {f[3]} до {f[4]}
"
        f"💰 **Цена:** от {p_from} до {p_to}
"
        f"📍 **Локация:** {loc_text}
"
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
        types.InlineKeyboardButton("📄 Документы", callback_data="f_docs")
    )
    markup.row(
        types.InlineKeyboardButton("🔄 Сбросить", callback_data="f_reset"),
        types.InlineKeyboardButton("🔍 Показать авто", callback_data="f_search")
    )
    markup.add(types.InlineKeyboardButton("⬅️ Назад в меню", callback_data="to_main"))

    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
            return
        except:
            pass
    bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == '⚙️ Мой фильтр')
def open_filter(message):
    send_filter_menu(message.chat.id)

def set_f_brand(message):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        bot.send_message(cid, "Возврат к фильтрам.", reply_markup=main_menu(cid))
        send_filter_menu(cid)
        return
    val = 'Любая' if message.text == 'Любая марка' else message.text.strip()
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute("UPDATE filters SET brand=?, model='Любая' WHERE user_id=?", (val, cid))
    c.execute("DELETE FROM viewed WHERE user_id=?", (cid,))
    conn.commit()
    conn.close()
    bot.send_message(cid, f"✅ Марка: {val}", reply_markup=main_menu(cid))
    send_filter_menu(cid)

def set_f_model(message):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        bot.send_message(cid, "Возврат к фильтрам.", reply_markup=main_menu(cid))
        send_filter_menu(cid)
        return
    val = 'Любая' if message.text == 'Любая модель' else message.text.strip()
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute("UPDATE filters SET model=? WHERE user_id=?", (val, cid))
    c.execute("DELETE FROM viewed WHERE user_id=?", (cid,))
    conn.commit()
    conn.close()
    bot.send_message(cid, f"✅ Модель: {val}", reply_markup=main_menu(cid))
    send_filter_menu(cid)

def set_f_year(message):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        bot.send_message(cid, "Возврат к фильтрам.", reply_markup=main_menu(cid))
        send_filter_menu(cid)
        return
    parts = message.text.strip().split() if message.text else []
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute("UPDATE filters SET year_from=?, year_to=? WHERE user_id=?", (int(parts[0]), int(parts[1]), cid))
        c.execute("DELETE FROM viewed WHERE user_id=?", (cid,))
        conn.commit()
        conn.close()
        bot.send_message(cid, "✅ Год обновлен!", reply_markup=main_menu(cid))
        send_filter_menu(cid)
    else:
        msg = bot.send_message(cid, "❌ Введите два года через пробел (например: `2010 2020`):", parse_mode='Markdown')
        bot.register_next_step_handler(msg, set_f_year)

def set_f_price(message):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        bot.send_message(cid, "Возврат к фильтрам.", reply_markup=main_menu(cid))
        send_filter_menu(cid)
        return
    parts = message.text.strip().split() if message.text else []
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute("UPDATE filters SET price_from=?, price_to=? WHERE user_id=?", (int(parts[0]), int(parts[1]), cid))
        c.execute("DELETE FROM viewed WHERE user_id=?", (cid,))
        conn.commit()
        conn.close()
        bot.send_message(cid, "✅ Бюджет обновлен!", reply_markup=main_menu(cid))
        send_filter_menu(cid)
    else:
        msg = bot.send_message(cid, "❌ Введите две суммы через пробел (например: `150000 600000`):", parse_mode='Markdown')
        bot.register_next_step_handler(msg, set_f_price)

def set_f_loc1(message):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        bot.send_message(cid, "Возврат к фильтрам.", reply_markup=main_menu(cid))
        send_filter_menu(cid)
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
            msg = bot.send_message(cid, "❌ Город не найден. Напишите точнее (например: Абинск):")
            bot.register_next_step_handler(msg, set_f_loc1)
            return

    temp_data[cid] = {'lat': lat, 'lon': lon, 'city_name': city_name}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('50', '100', '200', '500')
    markup.row('⬅️ Назад')
    msg = bot.send_message(cid, f"📍 Выбран город: **{city_name}**. Укажите **радиус поиска в км**:", parse_mode='Markdown', reply_markup=markup)
    bot.register_next_step_handler(msg, set_f_loc2)

def set_f_loc2(message):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("📍 Моя текущая геопозиция", request_location=True))
        markup.row('⬅️ Назад')
        msg = bot.send_message(cid, "🌍 Отправьте вашу **геопозицию** или напишите **город**:", parse_mode='Markdown', reply_markup=markup)
        bot.register_next_step_handler(msg, set_f_loc1)
        return
    if not message.text or not message.text.strip().isdigit():
        msg = bot.send_message(cid, "❌ Введите радиус цифрами (например: 100):")
        bot.register_next_step_handler(msg, set_f_loc2)
        return
    d = temp_data[cid]
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute("UPDATE filters SET city_name=?, lat=?, lon=?, radius=? WHERE user_id=?",
              (d['city_name'], d['lat'], d['lon'], int(message.text.strip()), cid))
    c.execute("DELETE FROM viewed WHERE user_id=?", (cid,))
    conn.commit()
    conn.close()
    del temp_data[cid]
    bot.send_message(cid, "✅ Локация сохранена!", reply_markup=main_menu(cid))
    send_filter_menu(cid)

# ================= ЛЕНТА ПОКУПАТЕЛЯ (ДАЙВИНЧИК + ЖАЛОБЫ) =================
@bot.message_handler(func=lambda m: m.text == '🚗 Купить авто')
def buy_cars(message):
    show_next_car(message.chat.id)

def show_next_car(user_id):
    f = get_user_filter(user_id)
    _, f_brand, f_model, y_from, y_to, p_from, p_to, city_name, u_lat, u_lon, radius, only_clean = f

    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    query = '''SELECT * FROM cars WHERE status='approved' 
               AND year >= ? AND year <= ? AND price >= ? AND price <= ?
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

    found_car, dist_line = None, ""
    for car in cars:
        if city_name == 'Не задан' or not u_lat or not u_lon:
            found_car = car
            break
        elif car[12] and car[13]:
            dist = calc_distance(u_lat, u_lon, car[12], car[13])
            if dist <= radius:
                found_car = car
                dist_line = f"📍 Город: {car[11]} (~{dist} км от вас)"
                break

    if not found_car:
        conn.close()
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⚙️ Изменить фильтры", callback_data="open_filters"))
        markup.add(types.InlineKeyboardButton("⬅️ В главное меню", callback_data="to_main"))
        bot.send_message(user_id, "🏁 Подходящих машин больше нет! Попробуйте изменить фильтры.", reply_markup=markup)
        return

    c.execute("INSERT INTO viewed (user_id, car_id) VALUES (?, ?)", (user_id, found_car[0]))
    conn.commit()
    conn.close()

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("❤️ Контакт продавца", callback_data=f"like_{found_car[0]}"),
        types.InlineKeyboardButton("👎 Дальше", callback_data="next_car")
    )
    markup.row(
        types.InlineKeyboardButton("⚙️ Фильтр", callback_data="open_filters"),
        types.InlineKeyboardButton("🚩 Пожаловаться", callback_data=f"rep_{found_car[0]}")
    )
    markup.add(types.InlineKeyboardButton("⬅️ В меню", callback_data="to_main"))

    bot.send_photo(user_id, found_car[3], caption=format_car_caption(found_car, dist_line), parse_mode='Markdown', reply_markup=markup)

def process_user_report(message, car_id):
    cid = message.chat.id
    if message.text in ['⬅️ Назад', '❌ Отмена']:
        bot.send_message(cid, "Жалоба отменена.", reply_markup=main_menu(cid))
        show_next_car(cid)
        return

    reason = message.text.strip()
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    c.execute("SELECT * FROM cars WHERE id=?", (car_id,))
    car = c.fetchone()
    conn.close()

    bot.send_message(cid, "✅ **Жалоба отправлена администраторам!** Спасибо за помощь.", parse_mode='Markdown', reply_markup=main_menu(cid))

    if car:
        reporter = f"@{message.from_user.username}" if message.from_user.username else f"ID {cid}"
        markup = admin_car_markup(car[0])
        caption = (
            f"🚨 **ПОСТУПИЛА ЖАЛОБА ОТ ПОКУПАТЕЛЯ!**
"
            f"👤 Отправил: {reporter}
"
            f"📝 **Причина жалобы:** {reason}

" + format_car_caption(car)
        )
        for adm in get_admins():
            try:
                bot.send_photo(adm, car[3], caption=caption, parse_mode='Markdown', reply_markup=markup)
            except:
                pass
    show_next_car(cid)

# ================= ОБРАБОТЧИК ВСЕХ ИНЛАЙН-КНОПОК =================
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    cid = call.message.chat.id
    data = call.data
    bot.answer_callback_query(call.id)

    if data == "noop":
        return
    elif data == "to_main":
        bot.send_message(cid, "Главное меню:", reply_markup=main_menu(cid))
    elif data == "open_filters":
        send_filter_menu(cid)
    elif data == "next_car" or data == "f_search":
        show_next_car(cid)

    # Покупка: контакт и жалоба
    elif data.startswith("like_"):
        car_id = int(data.split("_")[1])
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute("SELECT username, user_id FROM cars WHERE id=?", (car_id,))
        res = c.fetchone()
        conn.close()
        if res and res[0]:
            bot.send_message(cid, f"📞 Напишите продавцу в Telegram: @{res[0]}")
        elif res:
            bot.send_message(cid, f"📞 Профиль продавца: [Написать](tg://user?id={res[1]})", parse_mode='Markdown')
        show_next_car(cid)

    elif data.startswith("rep_"):
        car_id = int(data.split("_")[1])
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row('Фейк / Мошенники', 'Неверная цена или фото')
        markup.row('Машина уже продана', 'Запрещенный товар / Спам')
        markup.row('⬅️ Назад')
        msg = bot.send_message(cid, f"🚩 Выберите или напишите **причину жалобы** на объявление #{car_id}:", parse_mode='Markdown', reply_markup=markup)
        bot.register_next_step_handler(msg, process_user_report, car_id)

    # Фильтры
    elif data == "f_brand":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        b_list = list(BRANDS.keys())
        for i in range(0, len(b_list), 3):
            markup.row(*b_list[i:i+3])
        markup.row('Любая марка', '⬅️ Назад')
        msg = bot.send_message(cid, "🚘 Выберите или напишите **марку** авто:", parse_mode='Markdown', reply_markup=markup)
        bot.register_next_step_handler(msg, set_f_brand)

    elif data == "f_model":
        f = get_user_filter(cid)
        models = BRANDS.get(f[1], [])
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for i in range(0, len(models), 3):
            markup.row(*models[i:i+3])
        markup.row('Любая модель', '⬅️ Назад')
        msg = bot.send_message(cid, "📝 Выберите или напишите **модель** авто:", parse_mode='Markdown', reply_markup=markup)
        bot.register_next_step_handler(msg, set_f_model)

    elif data == "f_year":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row('⬅️ Назад')
        msg = bot.send_message(cid, "📅 Введите **год от и до** через пробел (например: `2008 2018`):", parse_mode='Markdown', reply_markup=markup)
        bot.register_next_step_handler(msg, set_f_year)

    elif data == "f_price":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row('⬅️ Назад')
        msg = bot.send_message(cid, "💰 Введите **цену от и до** через пробел (например: `150000 500000`):", parse_mode='Markdown', reply_markup=markup)
        bot.register_next_step_handler(msg, set_f_price)

    elif data == "f_loc":
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("📍 Моя текущая геопозиция", request_location=True))
        markup.row('⬅️ Назад')
        msg = bot.send_message(cid, "🌍 Отправьте вашу **геопозицию** или напишите **город**:", parse_mode='Markdown', reply_markup=markup)
        bot.register_next_step_handler(msg, set_f_loc1)

    elif data == "f_docs":
        f = get_user_filter(cid)
        new_val = 0 if f[11] == 1 else 1
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute("UPDATE filters SET docs_only_clean=? WHERE user_id=?", (new_val, cid))
        c.execute("DELETE FROM viewed WHERE user_id=?", (cid,))
        conn.commit()
        conn.close()
        send_filter_menu(cid, call.message.message_id)

    elif data == "f_reset":
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute("DELETE FROM filters WHERE user_id=?", (cid,))
        c.execute("DELETE FROM viewed WHERE user_id=?", (cid,))
        conn.commit()
        conn.close()
        send_filter_menu(cid, call.message.message_id)

    # Мои объявления (редактирование / удаление продавцом)
    elif data.startswith("my_price_"):
        car_id = int(data.split("_")[2])
        msg = bot.send_message(cid, "✏️ Введите **новую цену** в рублях (только цифры):", parse_mode='Markdown', reply_markup=back_kb())
        bot.register_next_step_handler(msg, edit_my_price, car_id)

    elif data.startswith("my_desc_"):
        car_id = int(data.split("_")[2])
        msg = bot.send_message(cid, "📝 Введите **новое описание** автомобиля:", parse_mode='Markdown', reply_markup=back_kb())
        bot.register_next_step_handler(msg, edit_my_desc, car_id)

    elif data.startswith("my_del_"):
        car_id = int(data.split("_")[2])
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute("DELETE FROM cars WHERE id=? AND user_id=?", (car_id, cid))
        c.execute("DELETE FROM viewed WHERE car_id=?", (car_id,))
        conn.commit()
        conn.close()
        bot.send_message(cid, "🗑 Ваше объявление снято с продажи и удалено.")

    # Админка: модерация, патруль, предупреждения, удаление с причиной, управление админами
    elif data.startswith("mod_ok_") and is_admin(cid):
        car_id = int(data.split("_")[2])
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute("UPDATE cars SET status='approved' WHERE id=?", (car_id,))
        c.execute("SELECT user_id, brand, model FROM cars WHERE id=?", (car_id,))
        car = c.fetchone()
        conn.commit()
        conn.close()
        bot.send_message(cid, f"✅ Объявление #{car_id} одобрено и опубликовано!")
        if car:
            try:
                bot.send_message(car[0], f"🎉 Ваше объявление **{car[1]} {car[2]}** прошло модерацию и появилось в поиске!", parse_mode='Markdown')
            except:
                pass

    elif data.startswith("mod_no_") and is_admin(cid):
        car_id = int(data.split("_")[2])
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute("UPDATE cars SET status='rejected' WHERE id=?", (car_id,))
        c.execute("SELECT user_id, brand, model FROM cars WHERE id=?", (car_id,))
        car = c.fetchone()
        conn.commit()
        conn.close()
        bot.send_message(cid, f"❌ Объявление #{car_id} отклонено.")
        if car:
            try:
                bot.send_message(car[0], f"❌ Ваше объявление **{car[1]} {car[2]}** отклонено модератором.", parse_mode='Markdown')
            except:
                pass

    elif data == "adm_pending" and is_admin(cid):
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute("SELECT * FROM cars WHERE status='pending' ORDER BY id ASC LIMIT 1")
        car = c.fetchone()
        conn.close()
        if not car:
            bot.send_message(cid, "✅ Очередь модерации пуста!")
            return
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✅ Одобрить", callback_data=f"mod_ok_{car[0]}"),
            types.InlineKeyboardButton("❌ Отклонить", callback_data=f"mod_no_{car[0]}")
        )
        markup.row(
            types.InlineKeyboardButton("⚠️ Предупреждение", callback_data=f"adm_warn_{car[0]}"),
            types.InlineKeyboardButton("🗑 Удалить", callback_data=f"adm_del_{car[0]}")
        )
        bot.send_photo(cid, car[3], caption="⏳ **Анкета на проверке:**

" + format_car_caption(car), parse_mode='Markdown', reply_markup=markup)

    elif data.startswith("adm_all_") and is_admin(cid):
        offset = int(data.split("_")[2])
        send_admin_all_car(cid, offset, call.message.message_id)

    elif data.startswith("adm_warn_") and is_admin(cid):
        car_id = int(data.split("_")[2])
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row('Некачественные фото / скриншоты', 'Укажите корректную цену')
        markup.row('Дополните описание автомобиля', '❌ Отмена')
        msg = bot.send_message(cid, f"⚠️ Выберите или напишите **текст предупреждения** автору объявления #{car_id}:", parse_mode='Markdown', reply_markup=markup)
        bot.register_next_step_handler(msg, process_admin_warn, car_id)

    elif data.startswith("adm_del_") and is_admin(cid):
        car_id = int(data.split("_")[2])
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row('Фейк / Мошенничество', 'Запрещенный контент / Спам')
        markup.row('Неактуальное объявление', 'Без указания причины')
        markup.row('❌ Отмена')
        msg = bot.send_message(cid, f"🗑 Укажите **причину удаления** объявления #{car_id} (она придет продавцу):", parse_mode='Markdown', reply_markup=markup)
        bot.register_next_step_handler(msg, process_admin_delete_reason, car_id)

    elif data.startswith("adm_contact_") and is_admin(cid):
        car_id = int(data.split("_")[2])
        conn = sqlite3.connect('cars.db')
        c = conn.cursor()
        c.execute("SELECT username, user_id FROM cars WHERE id=?", (car_id,))
        res = c.fetchone()
        conn.close()
        if res and res[0]:
            bot.send_message(cid, f"📞 Автор объявления #{car_id}: @{res[0]} (ID: `{res[1]}`)", parse_mode='Markdown')
        elif res:
            bot.send_message(cid, f"📞 Профиль автора #{car_id}: [Написать](tg://user?id={res[1]}) (ID: `{res[1]}`)", parse_mode='Markdown')

    elif data == "adm_list" and is_admin(cid):
        adms = get_admins()
        adm_str = "
".join([f"• `{a}`" for a in adms])
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("➕ Добавить админа", callback_data="adm_add"))
        for a in adms:
            if a != cid:
                markup.add(types.InlineKeyboardButton(f"❌ Удалить админа {a}", callback_data=f"adm_rem_{a}"))
        bot.send_message(cid, f"👥 **Список администраторов:**
{adm_str}", parse_mode='Markdown', reply_markup=markup)

    elif data == "adm_add" and is_admin(cid):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row('❌ Отмена')
        msg = bot.send_message(cid, "➕ Пришлите **цифровой Telegram ID** нового админа или просто **перешлите сюда любое его сообщение**:", parse_mode='Markdown', reply_markup=markup)
        bot.register_next_step_handler(msg, process_add_admin)

    elif data.startswith("adm_rem_") and is_admin(cid):
        rem_id = int(data.split("_")[2])
        if rem_id != cid:
            conn = sqlite3.connect('cars.db')
            c = conn.cursor()
            c.execute("DELETE FROM admins WHERE user_id=?", (rem_id,))
            conn.commit()
            conn.close()
            bot.send_message(cid, f"✅ Администратор `{rem_id}` удален.", parse_mode='Markdown')

print("Бот Авторынок v5 успешно запущен!")
bot.polling(none_stop=True)
