import os
import json
import math
import sqlite3
import telebot
from telebot import types
from geopy.geocoders import Nominatim
from catalog import CATALOG

TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("TOKEN") or "ВАШ_ТОКЕН"
MY_ADMIN_ID = 0

bot = telebot.TeleBot(TOKEN)
geolocator = Nominatim(user_agent="avtovinchik_v7", timeout=5)
DB_DIR = os.environ.get("DATA_DIR", ".")
os.makedirs(DB_DIR, exist_ok=True)
DB = os.path.join(DB_DIR, "cars.db")
temp = {}


def db_exec(query, params=(), fetch=None):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(query, params)
    res = c.fetchone() if fetch == "one" else (c.fetchall() if fetch == "all" else None)
    last_id = c.lastrowid
    conn.commit()
    conn.close()
    return last_id if fetch == "id" else res


def init_db():
    db_exec("""CREATE TABLE IF NOT EXISTS cars (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT,
        photos TEXT, brand TEXT, model TEXT, year INTEGER, mileage INTEGER,
        gearbox TEXT, engine TEXT, price INTEGER, condition TEXT, docs TEXT,
        description TEXT, city TEXT, lat REAL, lon REAL,
        status TEXT DEFAULT 'pending')""")
    db_exec("""CREATE TABLE IF NOT EXISTS filters (
        user_id INTEGER PRIMARY KEY, brand TEXT DEFAULT 'Любая', model TEXT DEFAULT 'Любая',
        year_from INTEGER DEFAULT 1970, year_to INTEGER DEFAULT 2030,
        price_from INTEGER DEFAULT 0, price_to INTEGER DEFAULT 99999999,
        city_name TEXT DEFAULT 'Не задан', lat REAL, lon REAL,
        radius INTEGER DEFAULT 5000, docs_only_clean INTEGER DEFAULT 0,
        notify INTEGER DEFAULT 1)""")
    db_exec("CREATE TABLE IF NOT EXISTS viewed (user_id INTEGER, car_id INTEGER)")
    db_exec("CREATE TABLE IF NOT EXISTS favorites (user_id INTEGER, car_id INTEGER, PRIMARY KEY (user_id, car_id))")
    db_exec("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)")


init_db()


def is_admin(uid):
    if MY_ADMIN_ID and uid == MY_ADMIN_ID:
        return True
    return bool(db_exec("SELECT 1 FROM admins WHERE user_id=?", (uid,), "one"))


def get_filter(uid):
    f = db_exec("SELECT * FROM filters WHERE user_id=?", (uid,), "one")
    if not f:
        db_exec("INSERT INTO filters (user_id) VALUES (?)", (uid,))
        f = db_exec("SELECT * FROM filters WHERE user_id=?", (uid,), "one")
    return f


def calc_dist(lat1, lon1, lat2, lon2):
    r = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return round(r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def get_photos_list(photos_str):
    try:
        res = json.loads(photos_str)
        return res if isinstance(res, list) else [photos_str]
    except Exception:
        return [photos_str] if photos_str else []


def send_car_media(chat_id, photos_list, caption, reply_markup=None):
    if len(photos_list) > 1:
        media = [types.InputMediaPhoto(p) for p in photos_list[:10]]
        bot.send_media_group(chat_id, media)
        return bot.send_message(chat_id, caption, reply_markup=reply_markup)
    elif len(photos_list) == 1:
        return bot.send_photo(chat_id, photos_list[0], caption=caption, reply_markup=reply_markup)
    else:
        return bot.send_message(chat_id, caption, reply_markup=reply_markup)


def format_car(car, dist_str=""):
    p = f"{car[10]:,}".replace(",", " ")
    mil = f"{car[7]:,}".replace(",", " ")
    loc = dist_str if dist_str else f"📍 Город: {car[14]}"
    return (
        f"🚘 {car[4]} {car[5]}, {car[6]} г.\n"
        f"💰 Цена: {p} руб.\n"
        f"🛣 Пробег: {mil} км | ⚙️ {car[8]} | 🐎 {car[9]}\n"
        f"{loc}\n"
        f"🛠 Состояние: {car[11]}\n📄 Документы: {car[12]}\n\n📝 {car[13]}"
    )


def format_adm_car(car):
    u = f"@{car[2]}" if car[2] else f"ID {car[1]}"
    return f"ID: {car[0]} | Продавец: {u}\n" + format_car(car)


def main_kb(uid):
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("🚗 Купить авто", "💰 Продать авто")
    m.row("⚙️ Мой фильтр", "⭐ Избранное")
    m.row("📋 Мои объявления")
    if is_admin(uid):
        m.row("👑 Админ-панель")
    return m


def back_kb():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("⬅️ Назад")
    return m


def brands_kb(flt=False):
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if flt:
        m.row("Любая")
    m.row("✍️ Ввести марку вручную", "⬅️ Назад")
    keys = list(CATALOG.keys())
    for i in range(0, len(keys), 2):
        m.row(*keys[i:i + 2])
    return m


def models_kb(brand, flt=False):
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if flt:
        m.row("Любая")
    m.row("✍️ Ввести модель вручную", "⬅️ Назад")
    mods = CATALOG.get(brand, [])
    for i in range(0, len(mods), 2):
        m.row(*mods[i:i + 2])
    return m


def geo_kb():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.add(types.KeyboardButton("📍 Отправить геопозицию", request_location=True))
    m.row("⬅️ Назад")
    return m


def reset_state(uid):
    bot.clear_step_handler_by_chat_id(uid)


@bot.message_handler(commands=["start"])
def cmd_start(m):
    uid = m.from_user.id
    reset_state(uid)
    get_filter(uid)
    cnt = db_exec("SELECT COUNT(*) FROM admins", fetch="one")
    if cnt and cnt[0] == 0:
        db_exec("INSERT OR IGNORE INTO admins VALUES (?)", (uid,))
    bot.send_message(uid, "👋 Добро пожаловать в Автовинчик!\nВыберите действие:", reply_markup=main_kb(uid))


# --- ПРОДАЖА + ПРЕДПРОСМОТР ---
@bot.message_handler(func=lambda m: m.text == "💰 Продать авто")
def sell_1(m):
    uid = m.from_user.id
    reset_state(uid)
    temp[uid] = {"username": m.from_user.username, "photos": []}
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("✅ Готово (далее)", "⬅️ Назад")
    msg = bot.send_message(uid, "📸 Шаг 1/12. Отправьте до 10 фото авто (можно по одному или альбомом) и нажмите «✅ Готово (далее)»:", reply_markup=kb)
    bot.register_next_step_handler(msg, sell_2)


def sell_2(m):
    uid = m.from_user.id
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("✅ Готово (далее)", "⬅️ Назад")
    if m.text == "⬅️ Назад":
        return bot.send_message(uid, "Главное меню:", reply_markup=main_kb(uid))
    if m.text == "✅ Готово (далее)":
        if not temp.get(uid, {}).get("photos"):
            msg = bot.send_message(uid, "❌ Сначала загрузите хотя бы одно фото:", reply_markup=kb)
            return bot.register_next_step_handler(msg, sell_2)
        msg = bot.send_message(uid, "🚘 Шаг 2/12. Выберите марку из списка или введите вручную:", reply_markup=brands_kb())
        return bot.register_next_step_handler(msg, sell_3)
    if m.photo:
        if len(temp[uid]["photos"]) < 10:
            temp[uid]["photos"].append(m.photo[-1].file_id)
            cnt = len(temp[uid]["photos"])
            msg = bot.send_message(uid, f"📥 Фото добавлено ({cnt}/10). Отправьте еще или нажмите «✅ Готово (далее)»:", reply_markup=kb)
        else:
            msg = bot.send_message(uid, "⚠️ Достигнут лимит 10 фото. Нажмите «✅ Готово (далее)»:", reply_markup=kb)
        return bot.register_next_step_handler(msg, sell_2)
    msg = bot.send_message(uid, "❌ Отправьте фото или нажмите «✅ Готово (далее)»:", reply_markup=kb)
    bot.register_next_step_handler(msg, sell_2)


def sell_3(m):
    uid = m.from_user.id
    if m.text == "⬅️ Назад":
        temp[uid]["photos"] = []
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row("✅ Готово (далее)", "⬅️ Назад")
        msg = bot.send_message(uid, "📸 Шаг 1/12. Загрузите фото заново:", reply_markup=kb)
        return bot.register_next_step_handler(msg, sell_2)
    if not m.text:
        msg = bot.send_message(uid, "❌ Выберите марку кнопкой или напишите текстом:", reply_markup=brands_kb())
        return bot.register_next_step_handler(msg, sell_3)
    if m.text == "✍️ Ввести марку вручную":
        msg = bot.send_message(uid, "✍️ Напишите название марки:", reply_markup=back_kb())
        return bot.register_next_step_handler(msg, sell_3)
    temp[uid]["brand"] = m.text.strip()
    msg = bot.send_message(uid, "📝 Шаг 3/12. Выберите модель из списка или введите вручную:", reply_markup=models_kb(temp[uid]["brand"]))
    bot.register_next_step_handler(msg, sell_4)


def sell_4(m):
    uid = m.from_user.id
    if m.text == "⬅️ Назад":
        msg = bot.send_message(uid, "🚘 Шаг 2/12. Выберите марку:", reply_markup=brands_kb())
        return bot.register_next_step_handler(msg, sell_3)
    if not m.text:
        msg = bot.send_message(uid, "❌ Выберите модель:", reply_markup=back_kb())
        return bot.register_next_step_handler(msg, sell_4)
    if m.text == "✍️ Ввести модель вручную":
        msg = bot.send_message(uid, "✍️ Напишите название модели:", reply_markup=back_kb())
        return bot.register_next_step_handler(msg, sell_4)
    temp[uid]["model"] = m.text.strip()
    msg = bot.send_message(uid, "📅 Шаг 4/12. Введите год выпуска (например: 2018):", reply_markup=back_kb())
    bot.register_next_step_handler(msg, sell_5)


def sell_5(m):
    uid = m.from_user.id
    if m.text == "⬅️ Назад":
        msg = bot.send_message(uid, "📝 Шаг 3/12. Выберите модель:", reply_markup=models_kb(temp[uid]["brand"]))
        return bot.register_next_step_handler(msg, sell_4)
    if not m.text or not m.text.strip().isdigit() or not (1950 <= int(m.text.strip()) <= 2027):
        msg = bot.send_message(uid, "❌ Введите корректный год (от 1950 до 2027):", reply_markup=back_kb())
        return bot.register_next_step_handler(msg, sell_5)
    temp[uid]["year"] = int(m.text.strip())
    msg = bot.send_message(uid, "🛣 Шаг 5/12. Введите пробег в км (цифрами):", reply_markup=back_kb())
    bot.register_next_step_handler(msg, sell_5_mil)


def sell_5_mil(m):
    uid = m.from_user.id
    if m.text == "⬅️ Назад":
        msg = bot.send_message(uid, "📅 Шаг 4/12. Введите год выпуска:", reply_markup=back_kb())
        return bot.register_next_step_handler(msg, sell_5)
    if not m.text or not m.text.strip().isdigit() or int(m.text.strip()) < 0:
        msg = bot.send_message(uid, "❌ Введите пробег цифрами:", reply_markup=back_kb())
        return bot.register_next_step_handler(msg, sell_5_mil)
    temp[uid]["mileage"] = int(m.text.strip())
    kb_g = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb_g.row("Механика", "Автомат")
    kb_g.row("Робот", "Вариатор")
    kb_g.row("⬅️ Назад")
    msg = bot.send_message(uid, "⚙️ Шаг 6/12. Выберите тип КПП:", reply_markup=kb_g)
    bot.register_next_step_handler(msg, sell_5_gb)


def sell_5_gb(m):
    uid = m.from_user.id
    if m.text == "⬅️ Назад":
        msg = bot.send_message(uid, "🛣 Шаг 5/12. Введите пробег:", reply_markup=back_kb())
        return bot.register_next_step_handler(msg, sell_5_mil)
    if not m.text:
        return
    temp[uid]["gearbox"] = m.text.strip()
    msg = bot.send_message(uid, "🐎 Шаг 7/12. Укажите объем и тип двигателя (например: 1.6 бензин, 106 л.с.):", reply_markup=back_kb())
    bot.register_next_step_handler(msg, sell_5_eng)


def sell_5_eng(m):
    uid = m.from_user.id
    if m.text == "⬅️ Назад":
        kb_g = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb_g.row("Механика", "Автомат")
        kb_g.row("Робот", "Вариатор")
        kb_g.row("⬅️ Назад")
        msg = bot.send_message(uid, "⚙️ Шаг 6/12. Выберите тип КПП:", reply_markup=kb_g)
        return bot.register_next_step_handler(msg, sell_5_gb)
    if not m.text:
        return
    temp[uid]["engine"] = m.text.strip()
    msg = bot.send_message(uid, "💰 Шаг 8/12. Введите цену в рублях (цифрами):", reply_markup=back_kb())
    bot.register_next_step_handler(msg, sell_6)


def sell_6(m):
    uid = m.from_user.id
    if m.text == "⬅️ Назад":
        msg = bot.send_message(uid, "🐎 Шаг 7/12. Укажите двигатель:", reply_markup=back_kb())
        return bot.register_next_step_handler(msg, sell_5_eng)
    if not m.text or not m.text.strip().isdigit() or int(m.text.strip()) < 1000:
        msg = bot.send_message(uid, "❌ Введите реальную цену в рублях (от 1000):", reply_markup=back_kb())
        return bot.register_next_step_handler(msg, sell_6)
    temp[uid]["price"] = int(m.text.strip())
    kb_c = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb_c.row("Отличное", "На ходу / Есть нюансы")
    kb_c.row("Требует ремонта / Битая", "⬅️ Назад")
    msg = bot.send_message(uid, "🛠 Шаг 9/12. Выберите состояние:", reply_markup=kb_c)
    bot.register_next_step_handler(msg, sell_7)


def sell_7(m):
    uid = m.from_user.id
    if m.text == "⬅️ Назад":
        msg = bot.send_message(uid, "💰 Шаг 8/12. Введите цену:", reply_markup=back_kb())
        return bot.register_next_step_handler(msg, sell_6)
    if not m.text:
        return
    temp[uid]["condition"] = m.text.strip()
    kb_d = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb_d.row("✅ Чистые (без проблем)", "⚠️ Есть проблемы")
    kb_d.row("⬅️ Назад")
    msg = bot.send_message(uid, "📄 Шаг 10/12. Что с документами?", reply_markup=kb_d)
    bot.register_next_step_handler(msg, sell_8)


def sell_8(m):
    uid = m.from_user.id
    if m.text == "⬅️ Назад":
        kb_c = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb_c.row("Отличное", "На ходу / Есть нюансы")
        kb_c.row("Требует ремонта / Битая", "⬅️ Назад")
        msg = bot.send_message(uid, "🛠 Шаг 9/12. Выберите состояние:", reply_markup=kb_c)
        return bot.register_next_step_handler(msg, sell_7)
    if not m.text:
        return
    temp[uid]["docs"] = m.text.strip()
    msg = bot.send_message(uid, "✍️ Шаг 11/12. Напишите описание авто:", reply_markup=back_kb())
    bot.register_next_step_handler(msg, sell_9)


def sell_9(m):
    uid = m.from_user.id
    if m.text == "⬅️ Назад":
        kb_d = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb_d.row("✅ Чистые (без проблем)", "⚠️ Есть проблемы")
        kb_d.row("⬅️ Назад")
        msg = bot.send_message(uid, "📄 Шаг 10/12. Что с документами?", reply_markup=kb_d)
        return bot.register_next_step_handler(msg, sell_8)
    if not m.text:
        msg = bot.send_message(uid, "❌ Напишите описание текстом:", reply_markup=back_kb())
        return bot.register_next_step_handler(msg, sell_9)
    temp[uid]["desc"] = m.text.strip()
    msg = bot.send_message(uid, "🌍 Шаг 12/12. Отправьте геопозицию или напишите город:", reply_markup=geo_kb())
    bot.register_next_step_handler(msg, sell_10)


def sell_10(m):
    uid = m.from_user.id
    if m.text == "⬅️ Назад":
        msg = bot.send_message(uid, "✍️ Шаг 11/12. Напишите описание:", reply_markup=back_kb())
        return bot.register_next_step_handler(msg, sell_9)
    lat, lon, city = None, None, "Не указан"
    if m.location:
        lat, lon = m.location.latitude, m.location.longitude
        try:
            loc = geolocator.reverse(f"{lat}, {lon}", language="ru")
            adr = loc.raw.get("address", {})
            city = adr.get("city") or adr.get("town") or adr.get("village") or "Точка на карте"
        except Exception:
            city = "Точка на карте"
    elif m.text:
        try:
            loc = geolocator.geocode(m.text.strip())
            if loc:
                lat, lon, city = loc.latitude, loc.longitude, m.text.strip().capitalize()
            else:
                msg = bot.send_message(uid, "❌ Город не найден. Введите точнее или отправьте геопозицию:", reply_markup=geo_kb())
                return bot.register_next_step_handler(msg, sell_10)
        except Exception:
            msg = bot.send_message(uid, "❌ Сервис карт временно недоступен. Отправьте геопозицию кнопкой:", reply_markup=geo_kb())
            return bot.register_next_step_handler(msg, sell_10)
    else:
        return
    temp[uid].update({"city": city, "lat": lat, "lon": lon})
    show_preview(uid)


def show_preview(uid):
    d = temp.get(uid)
    if not d:
        return
    p = f"{d['price']:,}".replace(",", " ")
    mil = f"{d['mileage']:,}".replace(",", " ")
    cap = (
        f"👀 ПРЕДПРОСМОТР ОБЪЯВЛЕНИЯ\n\n"
        f"🚘 {d['brand']} {d['model']}, {d['year']} г.\n"
        f"💰 Цена: {p} руб.\n"
        f"🛣 Пробег: {mil} км | ⚙️ {d['gearbox']} | 🐎 {d['engine']}\n"
        f"📍 Город: {d['city']}\n🛠 Состояние: {d['condition']}\n"
        f"📄 Документы: {d['docs']}\n\n📝 {d['desc']}"
    )
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton("✅ Отправить на модерацию", callback_data="prev_ok"))
    mk.row(
        types.InlineKeyboardButton("💰 Цена", callback_data="prev_pr"),
        types.InlineKeyboardButton("✍️ Описание", callback_data="prev_ds")
    )
    mk.row(types.InlineKeyboardButton("❌ Отменить", callback_data="prev_no"))
    bot.send_message(uid, "Проверьте карточку перед отправкой:", reply_markup=main_kb(uid))
    send_car_media(uid, d["photos"], cap, mk)


def prev_edit(m, field):
    uid = m.from_user.id
    if m.text == "⬅️ Назад":
        return show_preview(uid)
    if field == "price":
        if not m.text or not m.text.strip().isdigit() or int(m.text.strip()) < 1000:
            msg = bot.send_message(uid, "❌ Введите цену цифрами (от 1000):", reply_markup=back_kb())
            return bot.register_next_step_handler(msg, prev_edit, "price")
        temp[uid]["price"] = int(m.text.strip())
    elif field == "desc":
        if not m.text:
            return
        temp[uid]["desc"] = m.text.strip()
    show_preview(uid)


# --- МОИ ОБЪЯВЛЕНИЯ ---
@bot.message_handler(func=lambda m: m.text == "📋 Мои объявления")
def my_cars(m):
    uid = m.from_user.id
    reset_state(uid)
    cars = db_exec("SELECT * FROM cars WHERE user_id=? ORDER BY id DESC", (uid,), "all")
    if not cars:
        return bot.send_message(uid, "У вас нет объявлений.", reply_markup=main_kb(uid))
    st_map = {"pending": "⏳ На проверке", "approved": "✅ Опубликовано"}
    for c in cars:
        mk = types.InlineKeyboardMarkup()
        mk.row(
            types.InlineKeyboardButton("💰 Цена", callback_data=f"my_pr_{c[0]}"),
            types.InlineKeyboardButton("📝 Описание", callback_data=f"my_ds_{c[0]}")
        )
        mk.row(types.InlineKeyboardButton("🗑 Снять с продажи", callback_data=f"my_dl_{c[0]}"))
        photos = get_photos_list(c[3])
        send_car_media(uid, photos, f"Статус: {st_map.get(c[17], c[17])}\n\n" + format_car(c), mk)


def my_edit_step(m, cid, field):
    uid = m.from_user.id
    if m.text == "⬅️ Назад":
        return bot.send_message(uid, "Отменено.", reply_markup=main_kb(uid))
    if field == "price":
        if not m.text or not m.text.strip().isdigit() or int(m.text.strip()) < 1000:
            msg = bot.send_message(uid, "❌ Введите цену цифрами (от 1000):", reply_markup=back_kb())
            return bot.register_next_step_handler(msg, my_edit_step, cid, "price")
        db_exec("UPDATE cars SET price=? WHERE id=?", (int(m.text.strip()), cid))
        bot.send_message(uid, "✅ Цена обновлена!", reply_markup=main_kb(uid))
    elif field == "description":
        if not m.text:
            return
        db_exec("UPDATE cars SET description=?, status='pending' WHERE id=?", (m.text.strip(), cid))
        bot.send_message(uid, "✅ Описание обновлено и отправлено на проверку!", reply_markup=main_kb(uid))
        notify_admins(cid)


def notify_admins(cid):
    car = db_exec("SELECT * FROM cars WHERE id=?", (cid,), "one")
    if not car:
        return
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton("✅ Одобрить", callback_data=f"adm_ok_{cid}"))
    mk.row(
        types.InlineKeyboardButton("⚠️ Предупреждение", callback_data=f"adm_wr_{cid}"),
        types.InlineKeyboardButton("🗑 Удалить", callback_data=f"adm_dl_{cid}_mod")
    )
    adms = [r[0] for r in db_exec("SELECT user_id FROM admins", fetch="all")]
    if MY_ADMIN_ID and MY_ADMIN_ID not in adms:
        adms.append(MY_ADMIN_ID)
    photos = get_photos_list(car[3])
    for a in adms:
        try:
            send_car_media(a, photos, "⏳ НОВОЕ НА МОДЕРАЦИЮ\n\n" + format_adm_car(car), mk)
        except Exception:
            pass


def notify_subscribers(car):
    filters = db_exec("SELECT * FROM filters WHERE notify=1 AND user_id!=?", (car[1],), "all")
    photos = get_photos_list(car[3])
    for f in filters:
        if not (f[3] <= car[6] <= f[4] and f[5] <= car[10] <= f[6]):
            continue
        if f[1] != "Любая" and f[1].lower() not in car[4].lower():
            continue
        if f[2] != "Любая" and f[2].lower() not in car[5].lower():
            continue
        if f[11] == 1 and "Чистые" not in car[12]:
            continue
        d_str = ""
        if f[7] != "Не задан" and f[8] and f[9]:
            if not (car[15] and car[16]):
                continue
            dist = calc_dist(f[8], f[9], car[15], car[16])
            if dist > f[10]:
                continue
            d_str = f"📍 Город: {car[14]} (~{dist} км от вас)"
        mk = types.InlineKeyboardMarkup()
        mk.row(
            types.InlineKeyboardButton("❤️ Контакт", callback_data=f"lk_{car[0]}"),
            types.InlineKeyboardButton("⭐ В избранное", callback_data=f"fav_{car[0]}")
        )
        try:
            send_car_media(f[0], photos, "🔔 НОВОЕ АВТО ПО ВАШЕМУ ФИЛЬТРУ!\n\n" + format_car(car, d_str), mk)
        except Exception:
            pass


# --- ИЗБРАННОЕ ---
@bot.message_handler(func=lambda m: m.text == "⭐ Избранное")
def fav_list(m):
    uid = m.from_user.id
    reset_state(uid)
    rows = db_exec("SELECT c.* FROM cars c JOIN favorites f ON c.id=f.car_id WHERE f.user_id=? AND c.status='approved'", (uid,), "all")
    if not rows:
        return bot.send_message(uid, "В избранном пока пусто.", reply_markup=main_kb(uid))
    for c in rows:
        mk = types.InlineKeyboardMarkup()
        if c[2]:
            mk.row(types.InlineKeyboardButton("📞 Написать продавцу", url=f"https://t.me/{c[2]}"))
        else:
            mk.row(types.InlineKeyboardButton("📞 Профиль продавца", url=f"tg://user?id={c[1]}"))
        mk.row(types.InlineKeyboardButton("❌ Убрать из избранного", callback_data=f"unfav_{c[0]}"))
        send_car_media(uid, get_photos_list(c[3]), format_car(c), mk)


# --- ФИЛЬТР И ЛЕНТА ---
@bot.message_handler(func=lambda m: m.text == "⚙️ Мой фильтр")
def flt_menu(m):
    reset_state(m.from_user.id)
    send_flt(m.from_user.id)


def send_flt(uid, mid=None):
    f = get_filter(uid)
    docs = "Только чистые" if f[11] == 1 else "Все"
    ntf = "Вкл 🔔" if f[12] == 1 else "Выкл 🔕"
    loc = f"{f[7]} (+{f[10]} км)" if f[7] != "Не задан" else "Вся Россия"
    pto = "без потолка" if f[6] >= 99999999 else f"{f[6]:,}".replace(",", " ") + " руб."
    txt = (
        f"⚙️ Фильтры поиска:\n\n🚘 Марка: {f[1]}\n📝 Модель: {f[2]}\n"
        f"📅 Год: {f[3]} - {f[4]}\n💰 Цена: {f[5]} - {pto}\n📍 Локация: {loc}\n"
        f"📄 Документы: {docs}\n🔔 Уведомления о новинках: {ntf}"
    )
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(f"🚘 Марка: {f[1]}", callback_data="fb"), types.InlineKeyboardButton(f"📝 Модель: {f[2]}", callback_data="fm"))
    mk.row(types.InlineKeyboardButton(f"📅 Год: {f[3]}-{f[4]}", callback_data="fy"), types.InlineKeyboardButton("💰 Цена от/до", callback_data="fp"))
    mk.row(types.InlineKeyboardButton("📍 Локация", callback_data="fl"), types.InlineKeyboardButton("📄 Документы", callback_data="fd"))
    mk.row(types.InlineKeyboardButton(f"🔔 Уведомления: {ntf}", callback_data="fn"))
    mk.row(types.InlineKeyboardButton("🔄 Сбросить", callback_data="fr"), types.InlineKeyboardButton("🔍 Показать авто", callback_data="fs"))
    if mid:
        try:
            return bot.edit_message_text(txt, uid, mid, reply_markup=mk)
        except Exception:
            pass
    bot.send_message(uid, txt, reply_markup=mk)


def flt_step(m, mode):
    uid = m.from_user.id
    if m.text == "⬅️ Назад":
        bot.send_message(uid, "Главное меню:", reply_markup=main_kb(uid))
        return send_flt(uid)
    if mode == "brand":
        if m.text == "✍️ Ввести марку вручную":
            msg = bot.send_message(uid, "Введите марку или слово Любая:", reply_markup=back_kb())
            return bot.register_next_step_handler(msg, flt_step, "brand")
        v = "Любая" if m.text.lower() == "любая" else m.text.strip()
        db_exec("UPDATE filters SET brand=?, model='Любая' WHERE user_id=?", (v, uid))
    elif mode == "model":
        if m.text == "✍️ Ввести модель вручную":
            msg = bot.send_message(uid, "Введите модель или слово Любая:", reply_markup=back_kb())
            return bot.register_next_step_handler(msg, flt_step, "model")
        v = "Любая" if m.text.lower() == "любая" else m.text.strip()
        db_exec("UPDATE filters SET model=? WHERE user_id=?", (v, uid))
    elif mode == "year":
        p = m.text.strip().split() if m.text else []
        if len(p) != 2 or not p[0].isdigit() or not p[1].isdigit():
            msg = bot.send_message(uid, "❌ Введите два года через пробел (например: 2010 2020):", reply_markup=back_kb())
            return bot.register_next_step_handler(msg, flt_step, "year")
        db_exec("UPDATE filters SET year_from=?, year_to=? WHERE user_id=?", (int(p[0]), int(p[1]), uid))
    elif mode == "price":
        p = m.text.strip().split() if m.text else []
        if len(p) != 2 or not p[0].isdigit() or not p[1].isdigit():
            msg = bot.send_message(uid, "❌ Введите две суммы через пробел:", reply_markup=back_kb())
            return bot.register_next_step_handler(msg, flt_step, "price")
        db_exec("UPDATE filters SET price_from=?, price_to=? WHERE user_id=?", (int(p[0]), int(p[1]), uid))
    elif mode == "loc1":
        lat, lon, city = None, None, "Точка на карте"
        if m.location:
            lat, lon = m.location.latitude, m.location.longitude
        elif m.text:
            try:
                loc = geolocator.geocode(m.text.strip())
                if not loc:
                    msg = bot.send_message(uid, "❌ Город не найден. Введите точнее или отправьте геопозицию:", reply_markup=geo_kb())
                    return bot.register_next_step_handler(msg, flt_step, "loc1")
                lat, lon, city = loc.latitude, loc.longitude, m.text.strip().capitalize()
            except Exception:
                msg = bot.send_message(uid, "❌ Ошибка геокодера. Отправьте геопозицию кнопкой:", reply_markup=geo_kb())
                return bot.register_next_step_handler(msg, flt_step, "loc1")
        else:
            return
        temp[uid] = {"lat": lat, "lon": lon, "city": city}
        kb_r = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb_r.row("50", "100", "200", "500")
        kb_r.row("⬅️ Назад")
        msg = bot.send_message(uid, "Выберите радиус в км:", reply_markup=kb_r)
        return bot.register_next_step_handler(msg, flt_step, "loc2")
    elif mode == "loc2":
        if not m.text or not m.text.strip().isdigit():
            msg = bot.send_message(uid, "❌ Введите число:", reply_markup=back_kb())
            return bot.register_next_step_handler(msg, flt_step, "loc2")
        d = temp.pop(uid, {})
        db_exec("UPDATE filters SET city_name=?, lat=?, lon=?, radius=? WHERE user_id=?", (d.get("city"), d.get("lat"), d.get("lon"), int(m.text.strip()), uid))
    db_exec("DELETE FROM viewed WHERE user_id=?", (uid,))
    bot.send_message(uid, "✅ Фильтр обновлен!", reply_markup=main_kb(uid))
    send_flt(uid)


@bot.message_handler(func=lambda m: m.text == "🚗 Купить авто")
def buy_start(m):
    reset_state(m.from_user.id)
    next_car(m.from_user.id)


def next_car(uid):
    f = get_filter(uid)
    q = "SELECT * FROM cars WHERE status='approved' AND year>=? AND year<=? AND price>=? AND price<=? AND id NOT IN (SELECT car_id FROM viewed WHERE user_id=?)"
    pr = [f[3], f[4], f[5], f[6], uid]
    if f[1] != "Любая":
        q += " AND LOWER(brand) LIKE ?"
        pr.append(f"%{f[1].lower()}%")
    if f[2] != "Любая":
        q += " AND LOWER(model) LIKE ?"
        pr.append(f"%{f[2].lower()}%")
    if f[11] == 1:
        q += " AND docs LIKE '%Чистые%'"
    cars = db_exec(q + " ORDER BY id DESC", tuple(pr), "all")
    found, d_str = None, ""
    for c in cars:
        if f[7] == "Не задан" or not f[8] or not f[9]:
            found = c
            break
        elif c[15] and c[16]:
            dist = calc_dist(f[8], f[9], c[15], c[16])
            if dist <= f[10]:
                found, d_str = c, f"📍 Город: {c[14]} (~{dist} км от вас)"
                break
    if not found:
        mk = types.InlineKeyboardMarkup()
        mk.row(types.InlineKeyboardButton("🔄 Смотреть заново", callback_data="reset_v"))
        mk.row(types.InlineKeyboardButton("⚙️ Изменить фильтр", callback_data="open_f"))
        return bot.send_message(uid, "🏁 Подходящих авто больше нет!", reply_markup=mk)
    db_exec("INSERT INTO viewed VALUES (?, ?)", (uid, found[0]))
    mk = types.InlineKeyboardMarkup()
    mk.row(
        types.InlineKeyboardButton("❤️ Контакт", callback_data=f"lk_{found[0]}"),
        types.InlineKeyboardButton("👎 Дальше", callback_data="nx")
    )
    mk.row(
        types.InlineKeyboardButton("⭐ В избранное", callback_data=f"fav_{found[0]}"),
        types.InlineKeyboardButton("⚙️ Фильтр", callback_data="open_f")
    )
    mk.row(types.InlineKeyboardButton("🚩 Пожаловаться", callback_data=f"rp_{found[0]}"))
    send_car_media(uid, get_photos_list(found[3]), format_car(found, d_str), mk)


def rep_step(m, cid):
    uid = m.from_user.id
    if m.text == "⬅️ Назад":
        bot.send_message(uid, "Отменено.", reply_markup=main_kb(uid))
        return next_car(uid)
    car = db_exec("SELECT * FROM cars WHERE id=?", (cid,), "one")
    if car:
        mk = types.InlineKeyboardMarkup()
        mk.row(types.InlineKeyboardButton("⚠️ Предупреждение", callback_data=f"adm_wr_{cid}"), types.InlineKeyboardButton("🗑 Удалить", callback_data=f"adm_dl_{cid}_rep"))
        adms = [r[0] for r in db_exec("SELECT user_id FROM admins", fetch="all")]
        if MY_ADMIN_ID and MY_ADMIN_ID not in adms:
            adms.append(MY_ADMIN_ID)
        for a in adms:
            try:
                send_car_media(a, get_photos_list(car[3]), f"🚩 ЖАЛОБА ОТ ID {uid}\nПричина: {m.text}\n\n" + format_adm_car(car), mk)
            except Exception:
                pass
    bot.send_message(uid, "✅ Жалоба отправлена админам!", reply_markup=main_kb(uid))
    next_car(uid)


# --- АДМИНКА ---
@bot.message_handler(commands=["admin"])
@bot.message_handler(func=lambda m: m.text == "👑 Админ-панель")
def adm_panel(m):
    uid = m.from_user.id
    reset_state(uid)
    cnt = db_exec("SELECT COUNT(*) FROM admins", fetch="one")
    if cnt and cnt[0] == 0:
        db_exec("INSERT OR IGNORE INTO admins VALUES (?)", (uid,))
    if not is_admin(uid):
        return bot.send_message(uid, "Нет доступа.", reply_markup=main_kb(uid))
    ap = db_exec("SELECT COUNT(*) FROM cars WHERE status='approved'", fetch="one")[0]
    pn = db_exec("SELECT COUNT(*) FROM cars WHERE status='pending'", fetch="one")[0]
    us = db_exec("SELECT COUNT(*) FROM filters", fetch="one")[0]
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton(f"⏳ На модерации ({pn})", callback_data="adm_mod"))
    mk.row(types.InlineKeyboardButton("📋 Все объявления", callback_data="adm_all"))
    mk.row(types.InlineKeyboardButton("👥 Админы", callback_data="adm_us"))
    bot.send_message(uid, f"👑 Админ-панель\n\nПользователей: {us}\nВ продаже: {ap}\nНа проверке: {pn}", reply_markup=mk)


def adm_mod_next(uid):
    car = db_exec("SELECT * FROM cars WHERE status='pending' ORDER BY id ASC LIMIT 1", fetch="one")
    if not car:
        return bot.send_message(uid, "✅ На проверке пусто.", reply_markup=main_kb(uid))
    mk = types.InlineKeyboardMarkup()
    mk.row(types.InlineKeyboardButton("✅ Одобрить", callback_data=f"adm_ok_{car[0]}"))
    mk.row(types.InlineKeyboardButton("⚠️ Предупреждение", callback_data=f"adm_wr_{car[0]}"), types.InlineKeyboardButton("🗑 Удалить", callback_data=f"adm_dl_{car[0]}_mod"))
    send_car_media(uid, get_photos_list(car[3]), "⏳ ПРОВЕРКА\n\n" + format_adm_car(car), mk)


def adm_browse(uid, idx=0):
    cars = db_exec("SELECT * FROM cars WHERE status='approved' ORDER BY id DESC", fetch="all")
    if not cars:
        return bot.send_message(uid, "Объявлений нет.", reply_markup=main_kb(uid))
    idx = idx % len(cars)
    c = cars[idx]
    mk = types.InlineKeyboardMarkup()
    if len(cars) > 1:
        mk.row(types.InlineKeyboardButton("⬅️ Пред.", callback_data=f"adm_br_{idx - 1}"), types.InlineKeyboardButton("След. ➡️", callback_data=f"adm_br_{idx + 1}"))
    mk.row(types.InlineKeyboardButton("⚠️ Предупреждение", callback_data=f"adm_wr_{c[0]}"), types.InlineKeyboardButton("🗑 Удалить", callback_data=f"adm_dl_{c[0]}_all"))
    send_car_media(uid, get_photos_list(c[3]), f"📋 ({idx + 1}/{len(cars)})\n\n" + format_adm_car(c), mk)


def adm_action_step(m, mode, cid=None):
    uid = m.from_user.id
    if m.text == "⬅️ Назад":
        return bot.send_message(uid, "Отменено.", reply_markup=main_kb(uid))
    if mode == "warn":
        car = db_exec("SELECT * FROM cars WHERE id=?", (cid,), "one")
        if car:
            try:
                bot.send_message(car[1], f"⚠️ ПРЕДУПРЕЖДЕНИЕ ОТ АДМИНА\nАвто: {car[4]} {car[5]} ({car[6]} г.)\nТекст: {m.text}")
            except Exception:
                pass
        bot.send_message(uid, "✅ Предупреждение отправлено!", reply_markup=main_kb(uid))
    elif mode.startswith("del_"):
        car = db_exec("SELECT * FROM cars WHERE id=?", (cid,), "one")
        if car:
            db_exec("DELETE FROM cars WHERE id=?", (cid,))
            db_exec("DELETE FROM viewed WHERE car_id=?", (cid,))
            db_exec("DELETE FROM favorites WHERE car_id=?", (cid,))
            try:
                bot.send_message(car[1], f"🗑 ВАШЕ ОБЪЯВЛЕНИЕ УДАЛЕНО\nАвто: {car[4]} {car[5]}\nПричина: {m.text}")
            except Exception:
                pass
        bot.send_message(uid, "✅ Удалено!", reply_markup=main_kb(uid))
        if mode == "del_mod":
            adm_mod_next(uid)
    elif mode == "add_adm":
        nid = m.forward_from.id if m.forward_from else (int(m.text.strip()) if m.text and m.text.strip().isdigit() else None)
        if nid:
            db_exec("INSERT OR IGNORE INTO admins VALUES (?)", (nid,))
            bot.send_message(uid, f"✅ Админ {nid} добавлен!", reply_markup=main_kb(uid))
        else:
            bot.send_message(uid, "❌ Неверный ID.", reply_markup=main_kb(uid))


# --- CALLBACKS ---
@bot.callback_query_handler(func=lambda call: True)
def cb_all(call):
    uid = call.from_user.id
    d = call.data
    bot.answer_callback_query(call.id)

    if d == "prev_ok":
        info = temp.pop(uid, None)
        if not info:
            return
        photos_json = json.dumps(info["photos"])
        cid = db_exec(
            "INSERT INTO cars (user_id, username, photos, brand, model, year, mileage, gearbox, engine, price, condition, docs, description, city, lat, lon) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (uid, info["username"], photos_json, info["brand"], info["model"], info["year"], info["mileage"], info["gearbox"], info["engine"], info["price"], info["condition"], info["docs"], info["desc"], info["city"], info["lat"], info["lon"]),
            "id"
        )
        bot.delete_message(uid, call.message.message_id)
        bot.send_message(uid, "✅ Отправлено на модерацию!", reply_markup=main_kb(uid))
        notify_admins(cid)
    elif d == "prev_pr":
        msg = bot.send_message(uid, "💰 Новая цена:", reply_markup=back_kb())
        bot.register_next_step_handler(msg, prev_edit, "price")
    elif d == "prev_ds":
        msg = bot.send_message(uid, "✍️ Новое описание:", reply_markup=back_kb())
        bot.register_next_step_handler(msg, prev_edit, "desc")
    elif d == "prev_no":
        temp.pop(uid, None)
        bot.delete_message(uid, call.message.message_id)
        bot.send_message(uid, "❌ Отменено.", reply_markup=main_kb(uid))
    elif d.startswith("my_pr_"):
        msg = bot.send_message(uid, "💰 Новая цена:", reply_markup=back_kb())
        bot.register_next_step_handler(msg, my_edit_step, int(d.split("_")[2]), "price")
    elif d.startswith("my_ds_"):
        msg = bot.send_message(uid, "📝 Новое описание:", reply_markup=back_kb())
        bot.register_next_step_handler(msg, my_edit_step, int(d.split("_")[2]), "description")
    elif d.startswith("my_dl_"):
        cid = int(d.split("_")[2])
        db_exec("DELETE FROM cars WHERE id=?", (cid,))
        db_exec("DELETE FROM favorites WHERE car_id=?", (cid,))
        bot.delete_message(uid, call.message.message_id)
        bot.send_message(uid, "🗑 Снято с продажи.", reply_markup=main_kb(uid))
    elif d == "open_f":
        send_flt(uid)
    elif d == "fb":
        msg = bot.send_message(uid, "Выберите марку:", reply_markup=brands_kb(True))
        bot.register_next_step_handler(msg, flt_step, "brand")
    elif d == "fm":
        f = get_filter(uid)
        msg = bot.send_message(uid, "Выберите модель:", reply_markup=models_kb(f[1], True))
        bot.register_next_step_handler(msg, flt_step, "model")
    elif d == "fy":
        msg = bot.send_message(uid, "Год от и до (например: 2010 2020):", reply_markup=back_kb())
        bot.register_next_step_handler(msg, flt_step, "year")
    elif d == "fp":
        msg = bot.send_message(uid, "Цена от и до (например: 100000 600000):", reply_markup=back_kb())
        bot.register_next_step_handler(msg, flt_step, "price")
    elif d == "fl":
        msg = bot.send_message(uid, "Отправьте геопозицию или город:", reply_markup=geo_kb())
        bot.register_next_step_handler(msg, flt_step, "loc1")
    elif d == "fd":
        f = get_filter(uid)
        db_exec("UPDATE filters SET docs_only_clean=? WHERE user_id=?", (0 if f[11] == 1 else 1, uid))
        db_exec("DELETE FROM viewed WHERE user_id=?", (uid,))
        send_flt(uid, call.message.message_id)
    elif d == "fn":
        f = get_filter(uid)
        db_exec("UPDATE filters SET notify=? WHERE user_id=?", (0 if f[12] == 1 else 1, uid))
        send_flt(uid, call.message.message_id)
    elif d == "fr":
        db_exec("DELETE FROM filters WHERE user_id=?", (uid,))
        db_exec("DELETE FROM viewed WHERE user_id=?", (uid,))
        send_flt(uid, call.message.message_id)
    elif d == "reset_v":
        db_exec("DELETE FROM viewed WHERE user_id=?", (uid,))
        next_car(uid)
    elif d in ["fs", "nx"]:
        next_car(uid)
    elif d.startswith("fav_"):
        cid = int(d.split("_")[1])
        db_exec("INSERT OR IGNORE INTO favorites VALUES (?, ?)", (uid, cid))
        bot.send_message(uid, "⭐ Добавлено в избранное!")
    elif d.startswith("unfav_"):
        cid = int(d.split("_")[1])
        db_exec("DELETE FROM favorites WHERE user_id=? AND car_id=?", (uid, cid))
        bot.delete_message(uid, call.message.message_id)
    elif d.startswith("lk_"):
        c = db_exec("SELECT username, user_id, brand, model FROM cars WHERE id=?", (int(d.split("_")[1]),), "one")
        if c:
            mk = types.InlineKeyboardMarkup()
            if c[0]:
                mk.add(types.InlineKeyboardButton(f"💬 Написать @{c[0]}", url=f"https://t.me/{c[0]}"))
            else:
                mk.add(types.InlineKeyboardButton("💬 Открыть профиль продавца", url=f"tg://user?id={c[1]}"))
            bot.send_message(uid, f"📞 Контакт продавца ({c[2]} {c[3]}):", reply_markup=mk)
        next_car(uid)
    elif d.startswith("rp_"):
        mk = types.ReplyKeyboardMarkup(resize_keyboard=True)
        mk.row("Фейк / Мошенники", "Неверная цена")
        mk.row("Продано", "⬅️ Назад")
        msg = bot.send_message(uid, "🚩 Причина жалобы:", reply_markup=mk)
        bot.register_next_step_handler(msg, rep_step, int(d.split("_")[1]))
    elif d == "adm_mod" and is_admin(uid):
        adm_mod_next(uid)
    elif d == "adm_all" and is_admin(uid):
        adm_browse(uid, 0)
    elif d.startswith("adm_br_") and is_admin(uid):
        bot.delete_message(uid, call.message.message_id)
        adm_browse(uid, int(d.split("_")[2]))
    elif d.startswith("adm_ok_") and is_admin(uid):
        cid = int(d.split("_")[2])
        c = db_exec("SELECT * FROM cars WHERE id=?", (cid,), "one")
        if c:
            db_exec("UPDATE cars SET status='approved' WHERE id=?", (cid,))
            try:
                bot.send_message(c[1], f"✅ Ваше авто ({c[4]} {c[5]}) опубликовано!")
            except Exception:
                pass
            updated_c = db_exec("SELECT * FROM cars WHERE id=?", (cid,), "one")
            notify_subscribers(updated_c)
        bot.delete_message(uid, call.message.message_id)
        adm_mod_next(uid)
    elif d.startswith("adm_wr_") and is_admin(uid):
        msg = bot.send_message(uid, "⚠️ Введите текст предупреждения:", reply_markup=back_kb())
        bot.register_next_step_handler(msg, adm_action_step, "warn", int(d.split("_")[2]))
    elif d.startswith("adm_dl_") and is_admin(uid):
        p = d.split("_")
        mk = types.ReplyKeyboardMarkup(resize_keyboard=True)
        mk.row("Без причины", "Нарушение правил")
        mk.row("⬅️ Назад")
        msg = bot.send_message(uid, "🗑 Укажите причину удаления:", reply_markup=mk)
        bot.register_next_step_handler(msg, adm_action_step, f"del_{p[3]}", int(p[2]))
    elif d == "adm_us" and is_admin(uid):
        adms = [str(r[0]) for r in db_exec("SELECT user_id FROM admins", fetch="all")]
        mk = types.InlineKeyboardMarkup()
        mk.add(types.InlineKeyboardButton("➕ Добавить админа", callback_data="adm_add"))
        bot.send_message(uid, "👥 Админы:\n" + "\n".join(adms), reply_markup=mk)
    elif d == "adm_add" and is_admin(uid):
        msg = bot.send_message(uid, "Введите ID нового админа или перешлите его сообщение:", reply_markup=back_kb())
        bot.register_next_step_handler(msg, adm_action_step, "add_adm")


print("Автовинчик v7 запущен!")
bot.infinity_polling(timeout=10, long_polling_timeout=5)
