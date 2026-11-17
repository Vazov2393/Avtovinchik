import json
import math
from telebot import types
from config import bot
from catalog import CATALOG
from database import db_exec, is_admin, get_admins_list


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


def reset_state(uid):
    bot.clear_step_handler_by_chat_id(uid)


def main_kb(uid):
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("🚗 Купить авто", "💰 Продать авто")
    m.row("⚙️ Мой фильтр", "⭐ Избранное")
    m.row("📋 Мои объявления", "🆘 Техподдержка")
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
    photos = get_photos_list(car[3])
    for a in get_admins_list():
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
