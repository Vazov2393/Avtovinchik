import os
import sqlite3
import math
import telebot
from telebot import types
from geopy.geocoders import Nominatim

import database as db
import keyboards as kb
import admin

TOKEN = os.getenv('BOT_TOKEN') or os.getenv('TOKEN') or 'ВАШ_ТОКЕН_ОТ_BOTFATHER'
bot = telebot.TeleBot(TOKEN)
geolocator = Nominatim(user_agent="avtovinchik_bot_v3")

db.init_db()
admin.register_admin_handlers(bot)

temp_data = {}

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
    db.get_user_filter(message.chat.id)
    if db.get_admins_count() == 0:
        db.add_admin(message.chat.id, message.from_user.username or "Главный админ")
    is_adm = db.is_admin(message.chat.id)
    bot.send_message(
        message.chat.id,
        "👋 Добро пожаловать в Автовинчик!\nВыберите действие в меню ниже:",
        reply_markup=kb.main_menu(is_adm)
    )

@bot.message_handler(func=lambda m: m.text == '❌ Отмена' or m.text == '⬅️ В меню')
def cancel_action(message):
    temp_data.pop(message.chat.id, None)
    bot.send_message(
        message.chat.id,
        "Вы вернулись в главное меню.",
        reply_markup=kb.main_menu(db.is_admin(message.chat.id))
    )

# ================= ВЕТКА ПРОДАЖИ И ПРЕДПРОСМОТРА =================
@bot.message_handler(func=lambda m: m.text == '💰 Продать авто')
def sell_start(message):
    temp_data[message.chat.id] = {
        'username': message.from_user.username or "",
        'edit_mode': False
    }
    msg = bot.send_message(
        message.chat.id,
        "📸 Шаг 1/9: Отправьте фотографию автомобиля:",
        reply_markup=kb.back_cancel_kb(include_back=False)
    )
    bot.register_next_step_handler(msg, sell_photo)

def sell_photo(message):
    if message.text in ['❌ Отмена', '⬅️ В меню']:
        return cancel_action(message)
    if not message.photo:
        msg = bot.send_message(message.chat.id, "❌ Пожалуйста, отправьте именно фотографию:")
        bot.register_next_step_handler(msg, sell_photo)
        return
    temp_data[message.chat.id]['photo'] = message.photo[-1].file_id
    if temp_data[message.chat.id].get('edit_mode'):
        return show_preview(message.chat.id)
    ask_brand(message.chat.id)

def ask_brand(chat_id):
    msg = bot.send_message(
        chat_id,
        "🚘 Шаг 2/9: Выберите марку авто из списка или введите свою:",
        reply_markup=kb.brands_kb()
    )
    bot.register_next_step_handler(msg, sell_brand)

def sell_brand(message):
    if message.text == '❌ Отмена':
        return cancel_action(message)
    if message.text == '⬅️ Назад':
        return sell_start(message)
    if not message.text:
        return ask_brand(message.chat.id)
    if message.text == '✍️ Другая марка':
        msg = bot.send_message(message.chat.id, "Введите название марки текстом:", reply_markup=kb.back_cancel_kb())
        bot.register_next_step_handler(msg, sell_brand_manual)
        return
    temp_data[message.chat.id]['brand'] = message.text.strip()
    ask_model(message.chat.id)

def sell_brand_manual(message):
    if message.text == '❌ Отмена':
        return cancel_action(message)
    if message.text == '⬅️ Назад':
        return ask_brand(message.chat.id)
    if not message.text:
        return ask_brand(message.chat.id)
    temp_data[message.chat.id]['brand'] = message.text.strip()
    ask_model(message.chat.id)

def ask_model(chat_id):
    brand = temp_data[chat_id].get('brand', '')
    msg = bot.send_message(
        chat_id,
        f"📝 Шаг 3/9: Выберите модель ({brand}) или введите свою:",
        reply_markup=kb.models_kb(brand)
    )
    bot.register_next_step_handler(msg, sell_model)

def sell_model(message):
    if message.text == '❌ Отмена':
        return cancel_action(message)
    if message.text == '⬅️ Назад':
        return ask_brand(message.chat.id)
    if not message.text:
        return ask_model(message.chat.id)
    if message.text == '✍️ Другая модель':
        msg = bot.send_message(message.chat.id, "Введите название модели текстом:", reply_markup=kb.back_cancel_kb())
        bot.register_next_step_handler(msg, sell_model_manual)
        return
    temp_data[message.chat.id]['model'] = message.text.strip()
    ask_year(message.chat.id)

def sell_model_manual(message):
    if message.text == '❌ Отмена':
        return cancel_action(message)
    if message.text == '⬅️ Назад':
        return ask_model(message.chat.id)
    if not message.text:
        return ask_model(message.chat.id)
    temp_data[message.chat.id]['model'] = message.text.strip()
    ask_year(message.chat.id)

def ask_year(chat_id):
    msg = bot.send_message(
        chat_id,
        "📅 Шаг 4/9: Введите год выпуска (цифрами, например 2015):",
        reply_markup=kb.back_cancel_kb()
    )
    bot.register_next_step_handler(msg, sell_year)

def sell_year(message):
    if message.text == '❌ Отмена':
        return cancel_action(message)
    if message.text == '⬅️ Назад':
        return ask_model(message.chat.id)
    if not message.text or not message.text.strip().isdigit():
        msg = bot.send_message(message.chat.id, "❌ Введите год только цифрами (например 2012):")
        bot.register_next_step_handler(msg, sell_year)
        return
    temp_data[message.chat.id]['year'] = int(message.text.strip())
    ask_price(message.chat.id)

def ask_price(chat_id):
    msg = bot.send_message(
        chat_id,
        "💰 Шаг 5/9: Введите цену в рублях (только цифры, например 450000):",
        reply_markup=kb.back_cancel_kb()
    )
    bot.register_next_step_handler(msg, sell_price)

def sell_price(message):
    if message.text == '❌ Отмена':
        return cancel_action(message)
    if message.text == '⬅️ Назад':
        if temp_data[message.chat.id].get('edit_mode'):
            return show_preview(message.chat.id)
        return ask_year(message.chat.id)
    if not message.text or not message.text.strip().isdigit():
        msg = bot.send_message(message.chat.id, "❌ Введите цену цифрами без пробелов:")
        bot.register_next_step_handler(msg, sell_price)
        return
    temp_data[message.chat.id]['price'] = int(message.text.strip())
    if temp_data[message.chat.id].get('edit_mode'):
        return show_preview(message.chat.id)
    ask_condition(message.chat.id)

def ask_condition(chat_id):
    msg = bot.send_message(
        chat_id,
        "🛠 Шаг 6/9: Выберите состояние автомобиля:",
        reply_markup=kb.condition_kb()
    )
    bot.register_next_step_handler(msg, sell_condition)

def sell_condition(message):
    if message.text == '❌ Отмена':
        return cancel_action(message)
    if message.text == '⬅️ Назад':
        return ask_price(message.chat.id)
    if not message.text:
        return ask_condition(message.chat.id)
    temp_data[message.chat.id]['condition'] = message.text.strip()
    ask_docs(message.chat.id)

def ask_docs(chat_id):
    msg = bot.send_message(
        chat_id,
        "📄 Шаг 7/9: Что с документами?",
        reply_markup=kb.docs_kb()
    )
    bot.register_next_step_handler(msg, sell_docs)

def sell_docs(message):
    if message.text == '❌ Отмена':
        return cancel_action(message)
    if message.text == '⬅️ Назад':
        return ask_condition(message.chat.id)
    if not message.text:
        return ask_docs(message.chat.id)
    temp_data[message.chat.id]['docs'] = message.text.strip()
    ask_desc(message.chat.id)

def ask_desc(chat_id):
    msg = bot.send_message(
        chat_id,
        "✍️ Шаг 8/9: Напишите описание (двигатель, КПП, нюансы, торг):",
        reply_markup=kb.back_cancel_kb()
    )
    bot.register_next_step_handler(msg, sell_desc)

def sell_desc(message):
    if message.text == '❌ Отмена':
        return cancel_action(message)
    if message.text == '⬅️ Назад':
        if temp_data[message.chat.id].get('edit_mode'):
            return show_preview(message.chat.id)
        return ask_docs(message.chat.id)
    if not message.text:
        return ask_desc(message.chat.id)
    temp_data[message.chat.id]['description'] = message.text.strip()
    if temp_data[message.chat.id].get('edit_mode'):
        return show_preview(message.chat.id)
    ask_location(message.chat.id)

def ask_location(chat_id):
    msg = bot.send_message(
        chat_id,
        "🌍 Шаг 9/9: Нажмите кнопку геопозиции или напишите город (например: Абинск):",
        reply_markup=kb.location_kb()
    )
    bot.register_next_step_handler(msg, sell_location)

def sell_location(message):
    if message.text == '❌ Отмена':
        return cancel_action(message)
    if message.text == '⬅️ Назад':
        return ask_desc(message.chat.id)

    lat, lon, city_name = None, None, "Не указан"
    if message.location:
        lat = message.location.latitude
        lon = message.location.longitude
        try:
            loc = geolocator.reverse(f"{lat}, {lon}", language='ru')
            addr = loc.raw.get('address', {})
            city_name = addr.get('city') or addr.get('town') or addr.get('village') or "Точка на карте"
        except Exception:
            city_name = "Точка на карте"
    elif message.text:
        try:
            loc = geolocator.geocode(message.text.strip())
            if loc:
                lat, lon = loc.latitude, loc.longitude
                city_name = message.text.strip().capitalize()
            else:
                msg = bot.send_message(message.chat.id, "❌ Город не найден. Напишите точнее (например: Абинск):")
                bot.register_next_step_handler(msg, sell_location)
                return
        except Exception:
            msg = bot.send_message(message.chat.id, "❌ Ошибка поиска города. Отправьте геопозицию кнопкой:")
            bot.register_next_step_handler(msg, sell_location)
            return
    else:
        return ask_location(message.chat.id)

    temp_data[message.chat.id]['city'] = city_name
    temp_data[message.chat.id]['lat'] = lat
    temp_data[message.chat.id]['lon'] = lon
    show_preview(message.chat.id)

def show_preview(chat_id):
    d = temp_data.get(chat_id)
    if not d:
        return
    d['edit_mode'] = True
    price_str = f"{d['price']:,}".replace(',', ' ')
    caption = (
        f"👀 ПРЕДПРОСМОТР ОБЪЯВЛЕНИЯ\n\n"
        f"🚘 {d['brand']} {d['model']}, {d['year']} г.\n"
        f"💰 Цена: {price_str} ₽\n"
        f"📍 Город: {d['city']}\n"
        f"🛠 Состояние: {d['condition']}\n"
        f"📄 Документы: {d['docs']}\n\n"
        f"📝 {d['description']}"
    )
    bot.send_photo(
        chat_id,
        d['photo'],
        caption=caption,
        reply_markup=kb.preview_inline_kb()
    )

# ================= МОИ ОБЪЯВЛЕНИЯ =================
@bot.message_handler(func=lambda m: m.text == '📋 Мои объявления')
def my_cars(message):
    cars = db.get_user_cars(message.chat.id)
    if not cars:
        bot.send_message(
            message.chat.id,
            "У вас пока нет активных объявлений.",
            reply_markup=kb.main_menu(db.is_admin(message.chat.id))
        )
        return
    for car in cars:
        status_map = {
            'pending': '⏳ На проверке',
            'approved': '✅ Опубликовано',
            'rejected': '❌ Отклонено'
        }
        st = status_map.get(car, car)
        price_str = f"{car:,}".replace(',', ' ')
        caption = (
            f"🆔 Объявление #{car} ({st})\n"
            f"🚘 {car} {car}, {car} г.\n"
            f"💰 Цена: {price_str} ₽\n"
            f"📍 Город: {car}\n"
            f"📝 {car}"
        )
        bot.send_photo(
            message.chat.id,
            car,
            caption=caption,
            reply_markup=kb.my_car_inline_kb(car)
        )

def edit_car_photo_step(message, car_id):
    if message.text in ['❌ Отмена', '⬅️ В меню']:
        return cancel_action(message)
    if not message.photo:
        msg = bot.send_message(message.chat.id, "❌ Отправьте именно фотографию:")
        bot.register_next_step_handler(msg, edit_car_photo_step, car_id)
        return
    db.update_car_field(car_id, 'photo', message.photo[-1].file_id)
    bot.send_message(
        message.chat.id,
        "✅ Фотография успешно обновлена!",
        reply_markup=kb.main_menu(db.is_admin(message.chat.id))
    )

def edit_car_price_step(message, car_id):
    if message.text in ['❌ Отмена', '⬅️ В меню']:
        return cancel_action(message)
    if not message.text or not message.text.strip().isdigit():
        msg = bot.send_message(message.chat.id, "❌ Введите новую цену цифрами:")
        bot.register_next_step_handler(msg, edit_car_price_step, car_id)
        return
    db.update_car_field(car_id, 'price', int(message.text.strip()))
    bot.send_message(
        message.chat.id,
        "✅ Цена успешно обновлена!",
        reply_markup=kb.main_menu(db.is_admin(message.chat.id))
    )

def edit_car_desc_step(message, car_id):
    if message.text in ['❌ Отмена', '⬅️ В меню']:
        return cancel_action(message)
    if not message.text:
        msg = bot.send_message(message.chat.id, "❌ Введите новое описание текстом:")
        bot.register_next_step_handler(msg, edit_car_desc_step, car_id)
        return
    db.update_car_field(car_id, 'description', message.text.strip())
    bot.send_message(
        message.chat.id,
        "✅ Описание успешно обновлено!",
        reply_markup=kb.main_menu(db.is_admin(message.chat.id))
    )

# ================= ФИЛЬТРЫ ПОКУПАТЕЛЯ =================
@bot.message_handler(func=lambda m: m.text == '⚙️ Мой фильтр')
def open_filters(message):
    send_filter_card(message.chat.id)

def send_filter_card(chat_id, message_id=None):
    f = db.get_user_filter(chat_id)
    docs_text = "Только чистые" if f == 1 else "Все"
    loc_text = f"{f} (+{f} км)" if f != 'Не задан' else "Вся Россия"
    p_from = f"{f:,} ₽".replace(',', ' ')
    p_to = "без потолка" if f >= 99999999 else f"{f:,} ₽".replace(',', ' ')

    text = (
        f"⚙️ Ваши фильтры поиска:\n\n"
        f"🚘 Марка: {f}\n"
        f"📝 Модель: {f}\n"
        f"📅 Год: от {f} до {f}\n"
        f"💰 Цена: от {p_from} до {p_to}\n"
        f"📍 Локация: {loc_text}\n"
        f"📄 Документы: {docs_text}"
    )
    markup = kb.filter_inline_kb(f)
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=markup)

def f_set_brand(message):
    if message.text in ['❌ Отмена', '⬅️ Назад']:
        bot.send_message(message.chat.id, "Возврат к фильтрам.", reply_markup=kb.main_menu(db.is_admin(message.chat.id)))
        return send_filter_card(message.chat.id)
    val = 'Любая' if message.text.lower() == 'любая' else message.text.strip()
    db.update_filter(message.chat.id, brand=val, model='Любая')
    bot.send_message(message.chat.id, f"✅ Марка: {val}", reply_markup=kb.main_menu(db.is_admin(message.chat.id)))
    send_filter_card(message.chat.id)

def f_set_model(message):
    if message.text in ['❌ Отмена', '⬅️ Назад']:
        bot.send_message(message.chat.id, "Возврат к фильтрам.", reply_markup=kb.main_menu(db.is_admin(message.chat.id)))
        return send_filter_card(message.chat.id)
    val = 'Любая' if message.text.lower() == 'любая' else message.text.strip()
    db.update_filter(message.chat.id, model=val)
    bot.send_message(message.chat.id, f"✅ Модель: {val}", reply_markup=kb.main_menu(db.is_admin(message.chat.id)))
    send_filter_card(message.chat.id)

def f_set_year(message):
    if message.text in ['❌ Отмена', '⬅️ Назад']:
        bot.send_message(message.chat.id, "Возврат к фильтрам.", reply_markup=kb.main_menu(db.is_admin(message.chat.id)))
        return send_filter_card(message.chat.id)
    parts = message.text.strip().split()
    if len(parts) == 2 and parts.isdigit() and parts.isdigit():
        db.update_filter(message.chat.id, year_from=int(parts), year_to=int(parts))
        bot.send_message(message.chat.id, "✅ Годы обновлены!", reply_markup=kb.main_menu(db.is_admin(message.chat.id)))
        send_filter_card(message.chat.id)
    else:
        msg = bot.send_message(message.chat.id, "❌ Введите два года через пробел (например: 2010 2020):")
        bot.register_next_step_handler(msg, f_set_year)

def f_set_price(message):
    if message.text in ['❌ Отмена', '⬅️ Назад']:
        bot.send_message(message.chat.id, "Возврат к фильтрам.", reply_markup=kb.main_menu(db.is_admin(message.chat.id)))
        return send_filter_card(message.chat.id)
    parts = message.text.strip().split()
    if len(parts) == 2 and parts.isdigit() and parts.isdigit():
        db.update_filter(message.chat.id, price_from=int(parts), price_to=int(parts))
        bot.send_message(message.chat.id, "✅ Бюджет обновлен!", reply_markup=kb.main_menu(db.is_admin(message.chat.id)))
        send_filter_card(message.chat.id)
    else:
        msg = bot.send_message(message.chat.id, "❌ Введите две цены через пробел (например: 150000 600000):")
        bot.register_next_step_handler(msg, f_set_price)

def f_set_loc_city(message):
    if message.text in ['❌ Отмена', '⬅️ Назад']:
        bot.send_message(message.chat.id, "Возврат к фильтрам.", reply_markup=kb.main_menu(db.is_admin(message.chat.id)))
        return send_filter_card(message.chat.id)
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
            msg = bot.send_message(message.chat.id, "❌ Город не найден. Введите точнее (например: Абинск):")
            bot.register_next_step_handler(msg, f_set_loc_city)
            return
    temp_data[message.chat.id] = {'lat': lat, 'lon': lon, 'city_name': city_name}
    msg = bot.send_message(
        message.chat.id,
        f"📍 Город: {city_name}. Выберите или введите радиус поиска в км:",
        reply_markup=kb.radius_kb()
    )
    bot.register_next_step_handler(msg, f_set_loc_radius)

def f_set_loc_radius(message):
    if message.text == '⬅️ Назад':
        msg = bot.send_message(message.chat.id, "🌍 Отправьте геопозицию или напишите город:", reply_markup=kb.location_kb())
        bot.register_next_step_handler(msg, f_set_loc_city)
        return
    if message.text == '❌ Отмена':
        bot.send_message(message.chat.id, "Отменено.", reply_markup=kb.main_menu(db.is_admin(message.chat.id)))
        return send_filter_card(message.chat.id)
    if not message.text or not message.text.strip().isdigit():
        msg = bot.send_message(message.chat.id, "❌ Введите радиус цифрами (например: 100):")
        bot.register_next_step_handler(msg, f_set_loc_radius)
        return
    d = temp_data.pop(message.chat.id, {})
    db.update_filter(
        message.chat.id,
        city_name=d.get('city_name', 'Не задан'),
        lat=d.get('lat'),
        lon=d.get('lon'),
        radius=int(message.text.strip())
    )
    bot.send_message(message.chat.id, "✅ Локация сохранена!", reply_markup=kb.main_menu(db.is_admin(message.chat.id)))
    send_filter_card(message.chat.id)

# ================= ЛЕНТА ПОИСКА (ДАЙВИНЧИК) =================
@bot.message_handler(func=lambda m: m.text == '🚗 Купить авто')
def buy_cars(message):
    show_next_car(message.chat.id)

def show_next_car(user_id):
    f = db.get_user_filter(user_id)
    _, f_brand, f_model, y_from, y_to, p_from, p_to, city_name, u_lat, u_lon, radius, only_clean = f

    cars = db.get_approved_unviewed_cars(user_id, f_brand, f_model, y_from, y_to, p_from, p_to, only_clean)
    found_car = None
    dist_text = ""

    for car in cars:
        if city_name == 'Не задан' or not u_lat or not u_lon:
            found_car = car
            dist_text = f"📍 Город: {car}"
            break
        elif car and car:
            dist = calc_distance(u_lat, u_lon, car, car)
            if dist <= radius:
                found_car = car
                dist_text = f"📍 Город: {car} (~{dist} км от вас)"
                break

    if not found_car:
        bot.send_message(
            user_id,
            "🏁 Подходящих машин по вашим фильтрам больше нет!",
            reply_markup=kb.empty_feed_kb()
        )
        return

    db.mark_viewed(user_id, found_car)
    price_str = f"{found_car:,}".replace(',', ' ')
    caption = (
        f"🚘 {found_car} {found_car}, {found_car} г.\n"
        f"💰 Цена: {price_str} ₽\n"
        f"{dist_text}\n"
        f"🛠 Состояние: {found_car}\n"
        f"📄 Документы: {found_car}\n\n"
        f"📝 {found_car}"
    )
    bot.send_photo(
        user_id,
        found_car,
        caption=caption,
        reply_markup=kb.feed_inline_kb(found_car)
    )

def report_reason_step(message, car_id):
    if message.text in ['❌ Отмена', '⬅️ В меню']:
        return cancel_action(message)
    reason = message.text.strip() if message.text else "Без описания"
    car = db.get_car_by_id(car_id)
    if car:
        admins = db.get_all_admins()
        report_text = (
            f"🚩 НОВАЯ ЖАЛОБА НА ОБЪЯВЛЕНИЕ #{car_id}\n"
            f"Причина: {reason}\n"
            f"От пользователя: @{message.from_user.username or message.chat.id}\n\n"
            f"🚘 {car} {car}, {car} г. — {car} ₽"
        )
        for adm_id in admins:
            try:
                bot.send_photo(
                    adm_id,
                    car,
                    caption=report_text,
                    reply_markup=kb.admin_car_inline_kb(car_id, back_to='list')
                )
            except Exception:
                pass
    bot.send_message(
        message.chat.id,
        "✅ Жалоба отправлена администраторам!",
        reply_markup=kb.main_menu(db.is_admin(message.chat.id))
    )

# ================= ОБРАБОТЧИК CALLBACK-КНОПОК ПОЛЬЗОВАТЕЛЕЙ =================
@bot.callback_query_handler(func=lambda call: not call.data.startswith('adm_'))
def user_callbacks(call):
    cid = call.message.chat.id
    data = call.data
    bot.answer_callback_query(call.id)

    # Предпросмотр
    if data == 'prev_publish':
        d = temp_data.pop(cid, None)
        if not d:
            bot.send_message(cid, "❌ Данные объявления устарели. Начните заново.")
            return
        car_id = db.insert_car(
            cid, d['username'], d['photo'], d['brand'], d['model'],
            d['year'], d['price'], d['condition'], d['docs'],
            d['description'], d['city'], d['lat'], d['lon']
        )
        bot.delete_message(cid, call.message.message_id)
        bot.send_message(
            cid,
            "✅ Объявление отправлено на модерацию! Вы получите уведомление после проверки.",
            reply_markup=kb.main_menu(db.is_admin(cid))
        )
        admin.notify_admins_new_car(bot, car_id)

    elif data == 'prev_edit_photo':
        msg = bot.send_message(cid, "📸 Отправьте новое фото для объявления:", reply_markup=kb.back_cancel_kb(include_back=False))
        bot.register_next_step_handler(msg, sell_photo)

    elif data == 'prev_edit_price':
        msg = bot.send_message(cid, "💰 Введите новую цену в рублях:", reply_markup=kb.back_cancel_kb())
        bot.register_next_step_handler(msg, sell_price)

    elif data == 'prev_edit_desc':
        msg = bot.send_message(cid, "✍️ Введите новое описание:", reply_markup=kb.back_cancel_kb())
        bot.register_next_step_handler(msg, sell_desc)

    elif data == 'prev_cancel':
        temp_data.pop(cid, None)
        bot.delete_message(cid, call.message.message_id)
        bot.send_message(cid, "❌ Создание объявления отменено.", reply_markup=kb.main_menu(db.is_admin(cid)))

    # Мои объявления
    elif data.startswith('my_photo_'):
        car_id = int(data.split('_'))
        msg = bot.send_message(cid, "📸 Отправьте новую фотографию:", reply_markup=kb.back_cancel_kb(include_back=False))
        bot.register_next_step_handler(msg, edit_car_photo_step, car_id)

    elif data.startswith('my_price_'):
        car_id = int(data.split('_'))
        msg = bot.send_message(cid, "💰 Введите новую цену цифрами:", reply_markup=kb.back_cancel_kb(include_back=False))
        bot.register_next_step_handler(msg, edit_car_price_step, car_id)

    elif data.startswith('my_desc_'):
        car_id = int(data.split('_'))
        msg = bot.send_message(cid, "✍️ Введите новое описание:", reply_markup=kb.back_cancel_kb(include_back=False))
        bot.register_next_step_handler(msg, edit_car_desc_step, car_id)

    elif data.startswith('my_del_'):
        car_id = int(data.split('_'))
        db.delete_car(car_id)
        bot.delete_message(cid, call.message.message_id)
        bot.send_message(cid, "🗑 Объявление снято с продажи.")

    # Фильтры
    elif data == 'open_filters':
        send_filter_card(cid)
    elif data == 'f_brand':
        msg = bot.send_message(cid, "🚘 Выберите марку или напишите 'Любая':", reply_markup=kb.brands_kb(for_filter=True))
        bot.register_next_step_handler(msg, f_set_brand)
    elif data == 'f_model':
        f = db.get_user_filter(cid)
        msg = bot.send_message(cid, "📝 Выберите модель или напишите 'Любая':", reply_markup=kb.models_kb(f, for_filter=True))
        bot.register_next_step_handler(msg, f_set_model)
    elif data == 'f_year':
        msg = bot.send_message(cid, "📅 Введите год от и до через пробел (например: 2008 2018):", reply_markup=kb.back_cancel_kb())
        bot.register_next_step_handler(msg, f_set_year)
    elif data == 'f_price':
        msg = bot.send_message(cid, "💰 Введите цену от и до через пробел (например: 200000 700000):", reply_markup=kb.back_cancel_kb())
        bot.register_next_step_handler(msg, f_set_price)
    elif data == 'f_loc':
        msg = bot.send_message(cid, "🌍 Отправьте геопозицию или напишите город:", reply_markup=kb.location_kb())
        bot.register_next_step_handler(msg, f_set_loc_city)
    elif data == 'f_docs':
        f = db.get_user_filter(cid)
        db.update_filter(cid, docs_only_clean=(0 if f == 1 else 1))
        send_filter_card(cid, call.message.message_id)
    elif data == 'f_reset':
        db.reset_filter(cid)
        send_filter_card(cid, call.message.message_id)
    elif data in ['f_search', 'next_car']:
        show_next_car(cid)
    elif data == 'to_main_menu':
        bot.send_message(cid, "Главное меню:", reply_markup=kb.main_menu(db.is_admin(cid)))

    # Лента
    elif data.startswith('like_'):
        car_id = int(data.split('_'))
        car = db.get_car_by_id(car_id)
        if car:
            if car:
                bot.send_message(cid, f"📞 Напишите продавцу в Telegram: @{car}")
            else:
                bot.send_message(cid, f"📞 Профиль продавца (ID: {car})")
        show_next_car(cid)

    elif data.startswith('report_'):
        car_id = int(data.split('_'))
        msg = bot.send_message(cid, "🚩 Напишите причину жалобы на это объявление:", reply_markup=kb.back_cancel_kb(include_back=False))
        bot.register_next_step_handler(msg, report_reason_step, car_id)

if __name__ == '__main__':
    print("Бот Автовинчик успешно запущен!")
    bot.polling(none_stop=True)
