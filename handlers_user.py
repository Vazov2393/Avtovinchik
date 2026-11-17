from telebot import types
from config import bot, geolocator, temp
from database import db_exec, get_filter, get_admins_list
from utils import (
    reset_state, main_kb, back_kb, brands_kb, models_kb, geo_kb,
    send_car_media, get_photos_list, format_car, notify_admins
)


@bot.message_handler(commands=["start"])
def cmd_start(m):
    uid = m.from_user.id
    reset_state(uid)
    get_filter(uid)
    cnt = db_exec("SELECT COUNT(*) FROM admins", fetch="one")
    if cnt and cnt[0] == 0:
        db_exec("INSERT OR IGNORE INTO admins VALUES (?)", (uid,))
    bot.send_message(uid, "👋 Добро пожаловать в Автовинчик!\nВыберите действие:", reply_markup=main_kb(uid))


# --- ТЕХПОДДЕРЖКА ---
@bot.message_handler(func=lambda m: m.text == "🆘 Техподдержка")
def support_start(m):
    uid = m.from_user.id
    reset_state(uid)
    msg = bot.send_message(
        uid,
        "🆘 Напишите ваш вопрос или опишите проблему (можно прикрепить фото).\nАдминистратор ответит вам здесь:",
        reply_markup=back_kb()
    )
    bot.register_next_step_handler(msg, support_send)


def support_send(m):
    uid = m.from_user.id
    if m.text == "⬅️ Назад":
        return bot.send_message(uid, "Главное меню:", reply_markup=main_kb(uid))
    uname = f"@{m.from_user.username}" if m.from_user.username else "без ника"
    header = f"📩 ОБРАЩЕНИЕ В ТЕХПОДДЕРЖКУ\nОт: {m.from_user.first_name} ({uname} | ID: {uid})\n\n"
    mk = types.InlineKeyboardMarkup()
    mk.add(types.InlineKeyboardButton("💬 Ответить пользователю", callback_data=f"sup_rep_{uid}"))
    adms = get_admins_list()
    if not adms:
        return bot.send_message(uid, "❌ Сейчас нет свободных операторов.", reply_markup=main_kb(uid))
    for a in adms:
        try:
            if m.photo:
                cap = header + (m.caption or "")
                bot.send_photo(a, m.photo[-1].file_id, caption=cap, reply_markup=mk)
            elif m.text:
                bot.send_message(a, header + m.text, reply_markup=mk)
        except Exception:
            pass
    bot.send_message(uid, "✅ Ваше сообщение передано в техподдержку! Ожидайте ответа.", reply_markup=main_kb(uid))


# --- ПРОДАЖА + ПРЕДПРОСМОТР ---
@bot.message_handler(func=lambda m: m.text == "💰 Продать авто")
def sell_1(m):
    uid = m.from_user.id
    reset_state(uid)
    temp[uid] = {"username": m.from_user.username, "photos": []}
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("✅ Готово (далее)", "⬅️ Назад")
    msg = bot.send_message(uid, "📸 Шаг 1/12. Отправьте до 10 фото авто и нажмите «✅ Готово (далее)»:", reply_markup=kb)
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
