from telebot import types
from config import bot, geolocator, temp
from database import db_exec, get_filter, get_admins_list
from utils import (
    reset_state, main_kb, back_kb, brands_kb, models_kb, geo_kb,
    calc_dist, send_car_media, get_photos_list, format_car, format_adm_car
)


@bot.message_handler(func=lambda m: m.text == "⭐ Избранное")
def fav_list(m):
    uid = m.from_user.id
    reset_state(uid)
    rows = db_exec(
        "SELECT c.* FROM cars c JOIN favorites f ON c.id=f.car_id WHERE f.user_id=? AND c.status='approved'",
        (uid,), "all"
    )
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
        for a in get_admins_list():
            try:
                send_car_media(a, get_photos_list(car[3]), f"🚩 ЖАЛОБА ОТ ID {uid}\nПричина: {m.text}\n\n" + format_adm_car(car), mk)
            except Exception:
                pass
    bot.send_message(uid, "✅ Жалоба отправлена админам!", reply_markup=main_kb(uid))
    next_car(uid)
