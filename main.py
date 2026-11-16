import os
import math
import telebot
from telebot import types
from geopy.geocoders import Nominatim

from database import init_db, get_conn, is_admin, has_any_admin, add_admin, get_all_admins, get_user_filter
from keyboards import (
    CARS_CATALOG, main_menu, back_kb, brands_kb, models_kb,
    condition_kb, docs_kb, geo_kb, preview_inline_kb
)
from admin import send_admin_panel, register_admin_handlers

TOKEN = os.getenv('BOT_TOKEN') or os.getenv('TOKEN') or 'ВАШ_ТОКЕН_ОТ_BOTFATHER'
bot = telebot.TeleBot(TOKEN)
geolocator = Nominatim(user_agent="avtovinchik_modular_bot")

init_db()
temp_data = {}
admin_states = {}

register_admin_handlers(bot, admin_states)

def calc_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c)

@bot.message_handler(commands=['start'])
def cmd_start(message):
    cid = message.chat.id
    if not has_any_admin():
        add_admin(cid, 1)
    get_user_filter(cid)
    bot.send_message(
        cid,
        "👋 Добро пожаловать в Автовинчик!
Выберите действие в меню ниже:",
        reply_markup=main_menu(is_admin(cid))
    )

@bot.message_handler(commands=['admin'])
@bot.message_handler(func=lambda m: m.text == '👑 Админ-панель')
def cmd_admin(message):
    cid = message.chat.id
    if not has_any_admin():
        add_admin(cid, 1)
    if is_admin(cid):
        send_admin_panel(bot, cid)
    else:
        bot.send_message(cid, "У вас нет прав администратора.")

# ================= ПОДАЧА ОБЪЯВЛЕНИЯ + ПРЕДПРОСМОТР =================
@bot.message_handler(func=lambda m: m.text == '💰 Продать авто')
def sell_start(message):
    cid = message.chat.id
    temp_data[cid] = {'username': message.from_user.username, 'edit_mode': False}
    ask_photo(cid)

def ask_photo(cid):
    msg = bot.send_message(cid, "📸 Отправьте фотографию автомобиля:", reply_markup=back_kb())
    bot.register_next_step_handler(msg, step_photo)

def step_photo(message):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        if temp_data.get(cid, {}).get('edit_mode'):
            show_preview(cid)
        else:
            bot.send_message(cid, "Главное меню:", reply_markup=main_menu(is_admin(cid)))
        return
    if not message.photo:
        msg = bot.send_message(cid, "❌ Нужно отправить именно фотографию! Попробуйте еще раз:", reply_markup=back_kb())
        bot.register_next_step_handler(msg, step_photo)
        return
    temp_data[cid]['photo'] = message.photo[-1].file_id
    if temp_data[cid].get('edit_mode'):
        temp_data[cid]['edit_mode'] = False
        show_preview(cid)
    else:
        ask_brand(cid)

def ask_brand(cid):
    msg = bot.send_message(cid, "🚘 Выберите марку автомобиля:", reply_markup=brands_kb(False))
    bot.register_next_step_handler(msg, step_brand)

def step_brand(message):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        ask_photo(cid)
        return
    if not message.text:
        ask_brand(cid)
        return
    if message.text == '✍️ Другая марка':
        msg = bot.send_message(cid, "✍️ Напишите название марки текстом:", reply_markup=back_kb())
        bot.register_next_step_handler(msg, step_custom_brand)
        return
    temp_data[cid]['brand'] = message.text.strip()
    ask_model(cid)

def step_custom_brand(message):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        ask_brand(cid)
        return
    if not message.text:
        ask_brand(cid)
        return
    temp_data[cid]['brand'] = message.text.strip()
    ask_model(cid)

def ask_model(cid):
    brand = temp_data[cid]['brand']
    msg = bot.send_message(cid, f"📝 Выберите модель ({brand}):", reply_markup=models_kb(brand, False))
    bot.register_next_step_handler(msg, step_model)

def step_model(message):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        ask_brand(cid)
        return
    if not message.text:
        ask_model(cid)
        return
    if message.text == '✍️ Другая модель':
        msg = bot.send_message(cid, "✍️ Напишите модель текстом:", reply_markup=back_kb())
        bot.register_next_step_handler(msg, step_custom_model)
        return
    temp_data[cid]['model'] = message.text.strip()
    ask_year(cid)

def step_custom_model(message):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        ask_model(cid)
        return
    if not message.text:
        ask_model(cid)
        return
    temp_data[cid]['model'] = message.text.strip()
    ask_year(cid)

def ask_year(cid):
    msg = bot.send_message(cid, "📅 Укажите год выпуска (цифрами, например: 2015):", reply_markup=back_kb())
    bot.register_next_step_handler(msg, step_year)

def step_year(message):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        ask_model(cid)
        return
    if not message.text or not message.text.strip().isdigit():
        msg = bot.send_message(cid, "❌ Введите год цифрами (например: 2012):", reply_markup=back_kb())
        bot.register_next_step_handler(msg, step_year)
        return
    temp_data[cid]['year'] = int(message.text.strip())
    ask_price(cid)

def ask_price(cid):
    msg = bot.send_message(cid, "💵 Укажите цену в рублях (только цифры, например: 450000):", reply_markup=back_kb())
    bot.register_next_step_handler(msg, step_price)

def step_price(message):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        if temp_data.get(cid, {}).get('edit_mode'):
            show_preview(cid)
        else:
            ask_year(cid)
        return
    if not message.text or not message.text.strip().isdigit():
        msg = bot.send_message(cid, "❌ Введите цену цифрами без пробелов:", reply_markup=back_kb())
        bot.register_next_step_handler(msg, step_price)
        return
    temp_data[cid]['price'] = int(message.text.strip())
    if temp_data[cid].get('edit_mode'):
        temp_data[cid]['edit_mode'] = False
        show_preview(cid)
    else:
        ask_condition(cid)

def ask_condition(cid):
    msg = bot.send_message(cid, "🛠 Выберите состояние автомобиля:", reply_markup=condition_kb())
    bot.register_next_step_handler(msg, step_condition)

def step_condition(message):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        ask_price(cid)
        return
    if not message.text:
        ask_condition(cid)
        return
    temp_data[cid]['condition'] = message.text.strip()
    ask_docs(cid)

def ask_docs(cid):
    msg = bot.send_message(cid, "📄 Что с документами?", reply_markup=docs_kb())
    bot.register_next_step_handler(msg, step_docs)

def step_docs(message):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        ask_condition(cid)
        return
    if not message.text:
        ask_docs(cid)
        return
    temp_data[cid]['docs'] = message.text.strip()
    ask_desc(cid)

def ask_desc(cid):
    msg = bot.send_message(cid, "✍️ Напишите описание (двигатель, коробка, нюансы, торг):", reply_markup=back_kb())
    bot.register_next_step_handler(msg, step_desc)

def step_desc(message):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        if temp_data.get(cid, {}).get('edit_mode'):
            show_preview(cid)
        else:
            ask_docs(cid)
        return
    if not message.text:
        ask_desc(cid)
        return
    temp_data[cid]['description'] = message.text.strip()
    if temp_data[cid].get('edit_mode'):
        temp_data[cid]['edit_mode'] = False
        show_preview(cid)
    else:
        ask_geo(cid)

def ask_geo(cid):
    msg = bot.send_message(cid, "🌍 Отправьте геопозицию кнопкой или напишите название города (например: Абинск):", reply_markup=geo_kb())
    bot.register_next_step_handler(msg, step_geo)

def step_geo(message):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        ask_desc(cid)
        return
    lat, lon, city_name = None, None, "Не указан"
    if message.location:
        lat = message.location.latitude
        lon = message.location.longitude
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
                msg = bot.send_message(cid, "❌ Город не найден. Напишите точнее (например: Краснодарский край, Абинск):", reply_markup=geo_kb())
                bot.register_next_step_handler(msg, step_geo)
                return
        except:
            msg = bot.send_message(cid, "❌ Ошибка поиска города. Отправьте геопозицию кнопкой:", reply_markup=geo_kb())
            bot.register_next_step_handler(msg, step_geo)
            return
    else:
        ask_geo(cid)
        return

    temp_data[cid]['lat'] = lat
    temp_data[cid]['lon'] = lon
    temp_data[cid]['city'] = city_name
    show_preview(cid)

def show_preview(cid):
    d = temp_data.get(cid)
    if not d:
        return
    price_str = f"{d['price']:,}".replace(',', ' ')
    caption = (
        "👀 ПРЕДПРОСМОТР ОБЪЯВЛЕНИЯ

"
        f"🚘 {d['brand']} {d['model']}, {d['year']} г.
"
        f"💰 Цена: {price_str} руб.
"
        f"📍 Город: {d['city']}
"
        f"🛠 Состояние: {d['condition']}
"
        f"📄 Документы: {d['docs']}

"
        f"📝 {d['description']}

"
        "Проверьте данные перед отправкой на модерацию:"
    )
    bot.send_message(cid, "Карточка сформирована:", reply_markup=main_menu(is_admin(cid)))
    bot.send_photo(cid, d['photo'], caption=caption, reply_markup=preview_inline_kb())

# ================= МОИ ОБЪЯВЛЕНИЯ (РЕДАКТИРОВАНИЕ ФОТО, ЦЕНЫ, ОПИСАНИЯ) =================
@bot.message_handler(func=lambda m: m.text == '📋 Мои объявления')
def my_cars(message):
    cid = message.chat.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, brand, model, year, price, status, photo FROM cars WHERE user_id = ? ORDER BY id DESC", (cid,))
    rows = c.fetchall()
    conn.close()

    if not rows:
        bot.send_message(cid, "У вас пока нет размещенных объявлений.")
        return

    for r in rows:
        st = "⏳ На проверке" if r[5] == 'pending' else "✅ Опубликовано"
        price_str = f"{r[4]:,}".replace(',', ' ')
        caption = f"🚘 {r[1]} {r[2]}, {r[3]} г.
💰 Цена: {price_str} руб.
Статус: {st}"
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("📸 Заменить фото", callback_data=f"my_photo_{r[0]}"),
            types.InlineKeyboardButton("💰 Изменить цену", callback_data=f"my_price_{r[0]}")
        )
        markup.row(
            types.InlineKeyboardButton("✍️ Изменить описание", callback_data=f"my_desc_{r[0]}"),
            types.InlineKeyboardButton("🗑 Снять с продажи", callback_data=f"my_del_{r[0]}")
        )
        bot.send_photo(cid, r[6], caption=caption, reply_markup=markup)

def edit_existing_photo(message, car_id):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        bot.send_message(cid, "Отменено.", reply_markup=main_menu(is_admin(cid)))
        return
    if not message.photo:
        msg = bot.send_message(cid, "❌ Отправьте именно фотографию:", reply_markup=back_kb())
        bot.register_next_step_handler(msg, edit_existing_photo, car_id)
        return
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE cars SET photo = ?, status = 'pending' WHERE id = ? AND user_id = ?", (message.photo[-1].file_id, car_id, cid))
    conn.commit()
    conn.close()
    bot.send_message(cid, "✅ Фотография обновлена! Объявление отправлено на повторную проверку.", reply_markup=main_menu(is_admin(cid)))
    notify_admins_new_car(car_id)

def edit_existing_price(message, car_id):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        bot.send_message(cid, "Отменено.", reply_markup=main_menu(is_admin(cid)))
        return
    if not message.text or not message.text.strip().isdigit():
        msg = bot.send_message(cid, "❌ Введите новую цену цифрами:", reply_markup=back_kb())
        bot.register_next_step_handler(msg, edit_existing_price, car_id)
        return
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE cars SET price = ? WHERE id = ? AND user_id = ?", (int(message.text.strip()), car_id, cid))
    conn.commit()
    conn.close()
    bot.send_message(cid, "✅ Цена успешно обновлена!", reply_markup=main_menu(is_admin(cid)))

def edit_existing_desc(message, car_id):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        bot.send_message(cid, "Отменено.", reply_markup=main_menu(is_admin(cid)))
        return
    if not message.text:
        return
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE cars SET description = ?, status = 'pending' WHERE id = ? AND user_id = ?", (message.text.strip(), car_id, cid))
    conn.commit()
    conn.close()
    bot.send_message(cid, "✅ Описание обновлено! Объявление отправлено на повторную проверку.", reply_markup=main_menu(is_admin(cid)))
    notify_admins_new_car(car_id)

def notify_admins_new_car(car_id):
    for adm_id, _ in get_all_admins():
        try:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⏳ Открыть модерацию", callback_data="adm_pending"))
            bot.send_message(adm_id, f"🔔 Новое или измененное объявление (#{car_id}) ожидает проверки!", reply_markup=markup)
        except:
            pass

# ================= ФИЛЬТРЫ И ЛЕНТА ПОКУПАТЕЛЯ =================
def send_filter_menu(chat_id, message_id=None):
    f = get_user_filter(chat_id)
    docs_text = "Только чистые" if f[11] == 1 else "Все"
    loc_text = f"{f[7]} (+{f[10]} км)" if f[7] != 'Не задан' else "Вся Россия"
    p_to = "без потолка" if f[6] >= 99999999 else f"{f[6]:,} руб.".replace(',', ' ')
    p_from = f"{f[5]:,} руб.".replace(',', ' ')

    text = (
        "⚙️ Ваши фильтры поиска:

"
        f"🚘 Марка: {f[1]}
"
        f"📝 Модель: {f[2]}
"
        f"📅 Год: от {f[3]} до {f[4]}
"
        f"💰 Цена: от {p_from} до {p_to}
"
        f"📍 Локация: {loc_text}
"
        f"📄 Документы: {docs_text}"
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

    if message_id:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
    else:
        bot.send_message(chat_id, text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == '⚙️ Мой фильтр')
def open_filter(message):
    send_filter_menu(message.chat.id)

def set_f_brand(message):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        bot.send_message(cid, "Возврат в фильтр", reply_markup=main_menu(is_admin(cid)))
        send_filter_menu(cid)
        return
    if message.text == '✍️ Другая марка':
        msg = bot.send_message(cid, "✍️ Напишите марку текстом:", reply_markup=back_kb())
        bot.register_next_step_handler(msg, set_f_brand)
        return
    val = 'Любая' if message.text.lower() == 'любая' else message.text.strip()
    update_filter_field(cid, 'brand', val)
    update_filter_field(cid, 'model', 'Любая')
    bot.send_message(cid, f"Выбрана марка: {val}", reply_markup=main_menu(is_admin(cid)))
    send_filter_menu(cid)

def set_f_model(message):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        bot.send_message(cid, "Возврат в фильтр", reply_markup=main_menu(is_admin(cid)))
        send_filter_menu(cid)
        return
    if message.text == '✍️ Другая модель':
        msg = bot.send_message(cid, "✍️ Напишите модель текстом:", reply_markup=back_kb())
        bot.register_next_step_handler(msg, set_f_model)
        return
    val = 'Любая' if message.text.lower() == 'любая' else message.text.strip()
    update_filter_field(cid, 'model', val)
    bot.send_message(cid, f"Выбрана модель: {val}", reply_markup=main_menu(is_admin(cid)))
    send_filter_menu(cid)

def set_f_year(message):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        bot.send_message(cid, "Возврат в фильтр", reply_markup=main_menu(is_admin(cid)))
        send_filter_menu(cid)
        return
    parts = message.text.strip().split() if message.text else []
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        conn = get_conn()
        c = conn.cursor()
        c.execute('UPDATE filters SET year_from = ?, year_to = ? WHERE user_id = ?', (int(parts[0]), int(parts[1]), cid))
        c.execute('DELETE FROM viewed WHERE user_id = ?', (cid,))
        conn.commit()
        conn.close()
        bot.send_message(cid, "Годы обновлены!", reply_markup=main_menu(is_admin(cid)))
        send_filter_menu(cid)
    else:
        msg = bot.send_message(cid, "❌ Напишите два года через пробел (например: 2008 2018):", reply_markup=back_kb())
        bot.register_next_step_handler(msg, set_f_year)

def set_f_price(message):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        bot.send_message(cid, "Возврат в фильтр", reply_markup=main_menu(is_admin(cid)))
        send_filter_menu(cid)
        return
    parts = message.text.strip().split() if message.text else []
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        conn = get_conn()
        c = conn.cursor()
        c.execute('UPDATE filters SET price_from = ?, price_to = ? WHERE user_id = ?', (int(parts[0]), int(parts[1]), cid))
        c.execute('DELETE FROM viewed WHERE user_id = ?', (cid,))
        conn.commit()
        conn.close()
        bot.send_message(cid, "Бюджет обновлен!", reply_markup=main_menu(is_admin(cid)))
        send_filter_menu(cid)
    else:
        msg = bot.send_message(cid, "❌ Напишите две суммы через пробел (например: 150000 600000):", reply_markup=back_kb())
        bot.register_next_step_handler(msg, set_f_price)

def set_f_loc1(message):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        bot.send_message(cid, "Возврат в фильтр", reply_markup=main_menu(is_admin(cid)))
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
            msg = bot.send_message(cid, "❌ Город не найден. Напишите точнее (например: Абинск):", reply_markup=geo_kb())
            bot.register_next_step_handler(msg, set_f_loc1)
            return
    else:
        return

    temp_data[cid] = {'f_lat': lat, 'f_lon': lon, 'f_city': city_name}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('50', '100', '200', '500')
    markup.row('⬅️ Назад')
    msg = bot.send_message(cid, f"📍 Выбран город: {city_name}.
Выберите или введите радиус поиска в км:", reply_markup=markup)
    bot.register_next_step_handler(msg, set_f_loc2)

def set_f_loc2(message):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        msg = bot.send_message(cid, "🌍 Отправьте геопозицию или напишите город:", reply_markup=geo_kb())
        bot.register_next_step_handler(msg, set_f_loc1)
        return
    if not message.text or not message.text.strip().isdigit():
        msg = bot.send_message(cid, "❌ Введите радиус цифрами (например: 100):")
        bot.register_next_step_handler(msg, set_f_loc2)
        return
    d = temp_data[cid]
    conn = get_conn()
    c = conn.cursor()
    c.execute('UPDATE filters SET city_name = ?, lat = ?, lon = ?, radius = ? WHERE user_id = ?',
              (d['f_city'], d['f_lat'], d['f_lon'], int(message.text.strip()), cid))
    c.execute('DELETE FROM viewed WHERE user_id = ?', (cid,))
    conn.commit()
    conn.close()
    bot.send_message(cid, "✅ Локация обновлена!", reply_markup=main_menu(is_admin(cid)))
    send_filter_menu(cid)

def update_filter_field(user_id, field, value):
    conn = get_conn()
    c = conn.cursor()
    c.execute(f'UPDATE filters SET {field} = ? WHERE user_id = ?', (value, user_id))
    c.execute('DELETE FROM viewed WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

@bot.message_handler(func=lambda m: m.text == '🚗 Купить авто')
def buy_cars(message):
    show_next_car(message.chat.id)

def show_next_car(user_id):
    f = get_user_filter(user_id)
    _, f_brand, f_model, y_from, y_to, p_from, p_to, city_name, u_lat, u_lon, radius, only_clean = f

    conn = get_conn()
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
        bot.send_message(user_id, "🏁 Подходящих машин по вашим фильтрам больше нет!", reply_markup=markup)
        return

    c.execute('INSERT INTO viewed (user_id, car_id) VALUES (?, ?)', (user_id, found_car[0]))
    conn.commit()
    conn.close()

    price_formatted = f"{found_car[7]:,}".replace(',', ' ')
    caption = (
        f"🚘 {found_car[4]} {found_car[5]}, {found_car[6]} г.
"
        f"💰 Цена: {price_formatted} руб.
"
        f"{dist_text}
"
        f"🛠 Состояние: {found_car[8]}
"
        f"📄 Документы: {found_car[9]}

"
        f"📝 {found_car[10]}"
    )

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("❤️ Контакт продавца", callback_data=f"like_{found_car[0]}"),
        types.InlineKeyboardButton("👎 Дальше", callback_data="next_car")
    )
    markup.row(
        types.InlineKeyboardButton("⚙️ Фильтр", callback_data="open_filters"),
        types.InlineKeyboardButton("🚩 Пожаловаться", callback_data=f"rep_{found_car[0]}")
    )

    bot.send_photo(user_id, found_car[3], caption=caption, reply_markup=markup)

def send_report_reason(message, car_id):
    cid = message.chat.id
    if message.text == '⬅️ Назад':
        bot.send_message(cid, "Жалоба отменена.", reply_markup=main_menu(is_admin(cid)))
        return
    reason = message.text or "Без описания"
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM cars WHERE id = ?", (car_id,))
    car = c.fetchone()
    conn.close()
    bot.send_message(cid, "✅ Жалоба отправлена администраторам!", reply_markup=main_menu(is_admin(cid)))
    if car:
        for adm_id, _ in get_all_admins():
            try:
                markup = types.InlineKeyboardMarkup()
                markup.row(
                    types.InlineKeyboardButton("⚠️ Предупреждение", callback_data=f"adm_warn_{car[0]}"),
                    types.InlineKeyboardButton("🗑 Удалить с причиной", callback_data=f"adm_del_{car[0]}")
                )
                bot.send_photo(
                    adm_id, car[3],
                    caption=f"🚩 ЖАЛОБА НА ОБЪЯВЛЕНИЕ #{car[0]}
Причина: {reason}

Авто: {car[4]} {car[5]}, {car[6]} г.
Цена: {car[7]} руб.
Описание: {car[10]}",
                    reply_markup=markup
                )
            except:
                pass

# ================= ОБЩИЕ CALLBACK-КНОПКИ =================
@bot.callback_query_handler(func=lambda call: not call.data.startswith("adm_"))
def handle_user_callbacks(call):
    cid = call.message.chat.id
    bot.answer_callback_query(call.id)
    data = call.data

    # Предпросмотр перед отправкой
    if data == "prev_submit":
        d = temp_data.get(cid)
        if not d:
            bot.send_message(cid, "❌ Данные устарели. Попробуйте подать заново.")
            return
        conn = get_conn()
        c = conn.cursor()
        c.execute('''INSERT INTO cars (user_id, username, photo, brand, model, year, price, condition, docs, description, city, lat, lon, status)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')''',
                  (cid, d['username'], d['photo'], d['brand'], d['model'], d['year'],
                   d['price'], d['condition'], d['docs'], d['description'], d['city'], d['lat'], d['lon']))
        car_id = c.lastrowid
        conn.commit()
        conn.close()
        del temp_data[cid]
        bot.delete_message(cid, call.message.message_id)
        bot.send_message(cid, "✅ Объявление отправлено на модерацию! После проверки оно появится в общей ленте.", reply_markup=main_menu(is_admin(cid)))
        notify_admins_new_car(car_id)

    elif data == "prev_edit_photo":
        if cid in temp_data:
            temp_data[cid]['edit_mode'] = True
            ask_photo(cid)
    elif data == "prev_edit_price":
        if cid in temp_data:
            temp_data[cid]['edit_mode'] = True
            ask_price(cid)
    elif data == "prev_edit_desc":
        if cid in temp_data:
            temp_data[cid]['edit_mode'] = True
            ask_desc(cid)
    elif data == "prev_cancel":
        if cid in temp_data:
            del temp_data[cid]
        bot.delete_message(cid, call.message.message_id)
        bot.send_message(cid, "❌ Подача объявления отменена.", reply_markup=main_menu(is_admin(cid)))

    # Мои объявления
    elif data.startswith("my_photo_"):
        car_id = int(data.split("_")[2])
        msg = bot.send_message(cid, "📸 Отправьте новую фотографию:", reply_markup=back_kb())
        bot.register_next_step_handler(msg, edit_existing_photo, car_id)
    elif data.startswith("my_price_"):
        car_id = int(data.split("_")[2])
        msg = bot.send_message(cid, "💰 Введите новую цену в рублях:", reply_markup=back_kb())
        bot.register_next_step_handler(msg, edit_existing_price, car_id)
    elif data.startswith("my_desc_"):
        car_id = int(data.split("_")[2])
        msg = bot.send_message(cid, "✍️ Введите новое описание:", reply_markup=back_kb())
        bot.register_next_step_handler(msg, edit_existing_desc, car_id)
    elif data.startswith("my_del_"):
        car_id = int(data.split("_")[2])
        conn = get_conn()
        c = conn.cursor()
        c.execute("DELETE FROM cars WHERE id = ? AND user_id = ?", (car_id, cid))
        conn.commit()
        conn.close()
        bot.delete_message(cid, call.message.message_id)
        bot.send_message(cid, "✅ Объявление снято с продажи.")

    # Фильтры и лента
    elif data == "open_filters":
        send_filter_menu(cid)
    elif data == "f_brand":
        msg = bot.send_message(cid, "🚘 Выберите марку:", reply_markup=brands_kb(True))
        bot.register_next_step_handler(msg, set_f_brand)
    elif data == "f_model":
        f = get_user_filter(cid)
        msg = bot.send_message(cid, f"📝 Выберите модель ({f[1]}):", reply_markup=models_kb(f[1], True))
        bot.register_next_step_handler(msg, set_f_model)
    elif data == "f_year":
        msg = bot.send_message(cid, "📅 Введите год от и до через пробел (например: 2008 2018):", reply_markup=back_kb())
        bot.register_next_step_handler(msg, set_f_year)
    elif data == "f_price":
        msg = bot.send_message(cid, "💰 Введите цену от и до через пробел (например: 150000 700000):", reply_markup=back_kb())
        bot.register_next_step_handler(msg, set_f_price)
    elif data == "f_loc":
        msg = bot.send_message(cid, "🌍 Отправьте геопозицию или напишите город:", reply_markup=geo_kb())
        bot.register_next_step_handler(msg, set_f_loc1)
    elif data == "f_docs":
        f = get_user_filter(cid)
        new_val = 0 if f[11] == 1 else 1
        update_filter_field(cid, 'docs_only_clean', new_val)
        send_filter_menu(cid, call.message.message_id)
    elif data == "f_reset":
        conn = get_conn()
        c = conn.cursor()
        c.execute('DELETE FROM filters WHERE user_id = ?', (cid,))
        c.execute('DELETE FROM viewed WHERE user_id = ?', (cid,))
        conn.commit()
        conn.close()
        send_filter_menu(cid, call.message.message_id)
    elif data in ("f_search", "next_car"):
        show_next_car(cid)
    elif data.startswith("like_"):
        car_id = int(data.split("_")[1])
        conn = get_conn()
        c = conn.cursor()
        c.execute('SELECT username, user_id FROM cars WHERE id = ?', (car_id,))
        res = c.fetchone()
        conn.close()
        if res and res[0]:
            bot.send_message(cid, f"📞 Напишите продавцу в Telegram: @{res[0]}")
        elif res:
            bot.send_message(cid, f"📞 Профиль продавца (ID): {res[1]}")
        show_next_car(cid)
    elif data.startswith("rep_"):
        car_id = int(data.split("_")[1])
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("Фейк / Неверная цена", "Продано / Не отвечает")
        markup.row("Нарушение правил", "⬅️ Назад")
        msg = bot.send_message(cid, "🚩 Выберите или напишите причину жалобы:", reply_markup=markup)
        bot.register_next_step_handler(msg, send_report_reason, car_id)

if __name__ == '__main__':
    print("Автовинчик успешно запущен!")
    bot.polling(none_stop=True)
