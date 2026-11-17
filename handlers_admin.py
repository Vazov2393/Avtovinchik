import json
import time
from telebot import types
from config import bot, temp
from database import db_exec, is_admin, get_filter
from utils import (
    reset_state, main_kb, back_kb, brands_kb, models_kb, geo_kb,
    send_car_media, get_photos_list, format_adm_car,
    notify_admins, notify_subscribers
)
from handlers_user import prev_edit, my_edit_step
from handlers_buyer import send_flt, flt_step, next_car, rep_step


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


def adm_action_step(m, mode, target_id=None):
    uid = m.from_user.id
    if m.text == "⬅️ Назад":
        return bot.send_message(uid, "Отменено.", reply_markup=main_kb(uid))
    if mode == "sup_reply":
        try:
            if m.photo:
                cap = "👨‍💻 Ответ техподдержки:\n\n" + (m.caption or "")
                bot.send_photo(target_id, m.photo[-1].file_id, caption=cap)
            elif m.text:
                bot.send_message(target_id, f"👨‍💻 Ответ техподдержки:\n\n{m.text}")
            bot.send_message(uid, "✅ Ответ отправлен пользователю!", reply_markup=main_kb(uid))
        except Exception:
            bot.send_message(uid, "❌ Не удалось отправить (пользователь заблокировал бота).", reply_markup=main_kb(uid))
    elif mode == "warn":
        car = db_exec("SELECT * FROM cars WHERE id=?", (target_id,), "one")
        if car:
            try:
                bot.send_message(car[1], f"⚠️ ПРЕДУПРЕЖДЕНИЕ ОТ АДМИНА\nАвто: {car[4]} {car[5]} ({car[6]} г.)\nТекст: {m.text}")
            except Exception:
                pass
        bot.send_message(uid, "✅ Предупреждение отправлено!", reply_markup=main_kb(uid))
    elif mode.startswith("del_"):
        car = db_exec("SELECT * FROM cars WHERE id=?", (target_id,), "one")
        if car:
            db_exec("DELETE FROM cars WHERE id=?", (target_id,))
            db_exec("DELETE FROM viewed WHERE car_id=?", (target_id,))
            db_exec("DELETE FROM favorites WHERE car_id=?", (target_id,))
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


# --- ОБРАБОТЧИК ВСЕХ INLINE-КНОПОК ---
@bot.callback_query_handler(func=lambda call: True)
def cb_all(call):
    uid = call.from_user.id
    d = call.data
    bot.answer_callback_query(call.id)

    # Подтверждение актуальности (каждые 3 дня)
    if d.startswith("act_ok_"):
        cid = int(d.split("_")[2])
        car = db_exec("SELECT id FROM cars WHERE id=? AND user_id=?", (cid, uid), "one")
        if car:
            now = int(time.time())
            db_exec("UPDATE cars SET published_at=?, check_sent_at=0 WHERE id=?", (now, cid))
            try:
                bot.delete_message(uid, call.message.message_id)
            except Exception:
                pass
            bot.send_message(uid, "✅ Отлично! Ваше объявление продлено еще на 3 дня.")
        else:
            bot.send_message(uid, "❌ Объявление уже удалено.")

    # Предпросмотр и личный кабинет
    elif d == "prev_ok":
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

    # Фильтры и поиск
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

    # Админка и техподдержка
    elif d.startswith("sup_rep_") and is_admin(uid):
        target_uid = int(d.split("_")[2])
        msg = bot.send_message(uid, f"✍️ Введите ответ для пользователя ID {target_uid} (текст или фото):", reply_markup=back_kb())
        bot.register_next_step_handler(msg, adm_action_step, "sup_reply", target_uid)
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
            now = int(time.time())
            db_exec("UPDATE cars SET status='approved', published_at=?, check_sent_at=0 WHERE id=?", (now, cid))
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
