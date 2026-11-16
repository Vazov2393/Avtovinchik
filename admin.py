from telebot import types
from database import get_conn, is_admin, get_all_admins, add_admin, remove_admin
from keyboards import admin_menu_kb, back_kb, main_menu

def format_car_text(car):
    price_str = f"{car[7]:,}".replace(',', ' ')
    uname = f"@{car[2]}" if car[2] else f"ID {car[1]}"
    return (
        f"ID объявления: {car[0]}
"
        f"Продавец: {uname}
"
        f"Авто: {car[4]} {car[5]}, {car[6]} г.
"
        f"Цена: {price_str} руб.
"
        f"Город: {car[11]}
"
        f"Состояние: {car[8]}
"
        f"Документы: {car[9]}
"
        f"Описание: {car[10]}"
    )

def send_admin_panel(bot, chat_id):
    if not is_admin(chat_id):
        return
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM cars WHERE status = 'pending'")
    p_cnt = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM cars WHERE status = 'approved'")
    a_cnt = c.fetchone()[0]
    conn.close()
    bot.send_message(
        chat_id,
        f"👑 Панель администратора

На проверке: {p_cnt}
В продаже: {a_cnt}",
        reply_markup=admin_menu_kb(p_cnt, a_cnt)
    )

def register_admin_handlers(bot, admin_states):
    @bot.callback_query_handler(func=lambda call: call.data.startswith("adm_"))
    def handle_admin_calls(call):
        cid = call.message.chat.id
        if not is_admin(cid):
            bot.answer_callback_query(call.id, "Нет доступа")
            return
        bot.answer_callback_query(call.id)
        data = call.data

        if data == "adm_pending":
            show_pending_car(bot, cid)

        elif data.startswith("adm_ok_"):
            car_id = int(data.split("_")[2])
            conn = get_conn()
            c = conn.cursor()
            c.execute("SELECT user_id, brand, model FROM cars WHERE id = ?", (car_id,))
            row = c.fetchone()
            c.execute("UPDATE cars SET status = 'approved' WHERE id = ?", (car_id,))
            conn.commit()
            conn.close()
            bot.delete_message(cid, call.message.message_id)
            bot.send_message(cid, f"✅ Объявление #{car_id} одобрено!")
            if row:
                try:
                    bot.send_message(row[0], f"✅ Ваше объявление ({row[1]} {row[2]}) прошло модерацию и опубликовано!")
                except:
                    pass
            show_pending_car(bot, cid)

        elif data.startswith("adm_warn_"):
            car_id = int(data.split("_")[2])
            admin_states[cid] = {'action': 'warn', 'car_id': car_id}
            msg = bot.send_message(cid, f"⚠️ Напишите текст предупреждения для автора объявления #{car_id}:", reply_markup=back_kb())
            bot.register_next_step_handler(msg, process_admin_text)

        elif data.startswith("adm_del_"):
            car_id = int(data.split("_")[2])
            admin_states[cid] = {'action': 'del', 'car_id': car_id}
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.row("Без указания причины")
            markup.row("Фейк / Неверная цена", "Нарушение правил фото")
            markup.row("⬅️ Назад")
            msg = bot.send_message(cid, f"🗑 Укажите причину удаления объявления #{car_id}:", reply_markup=markup)
            bot.register_next_step_handler(msg, process_admin_text)

        elif data.startswith("adm_all_"):
            offset = int(data.split("_")[2])
            show_all_cars(bot, cid, offset)

        elif data.startswith("adm_contact_"):
            car_id = int(data.split("_")[2])
            conn = get_conn()
            c = conn.cursor()
            c.execute("SELECT username, user_id FROM cars WHERE id = ?", (car_id,))
            row = c.fetchone()
            conn.close()
            if row:
                contact = f"@{row[0]}" if row[0] else f"tg://user?id={row[1]}"
                bot.send_message(cid, f"📞 Контакт продавца (объявление #{car_id}): {contact}")

        elif data == "adm_staff":
            admins = get_all_admins()
            lines = ["👥 Список администраторов:
"]
            for uid, is_sup in admins:
                role = " (Главный)" if is_sup else ""
                lines.append(f"- ID: {uid}{role}")
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton("➕ Добавить админа", callback_data="adm_add_staff"),
                types.InlineKeyboardButton("➖ Удалить админа", callback_data="adm_rem_staff")
            )
            bot.send_message(cid, "
".join(lines), reply_markup=markup)

        elif data == "adm_add_staff":
            admin_states[cid] = {'action': 'add_admin'}
            msg = bot.send_message(cid, "Введите цифровой Telegram ID нового админа (или перешлите его сообщение сюда):", reply_markup=back_kb())
            bot.register_next_step_handler(msg, process_admin_text)

        elif data == "adm_rem_staff":
            admin_states[cid] = {'action': 'rem_admin'}
            msg = bot.send_message(cid, "Введите цифровой Telegram ID админа для удаления:", reply_markup=back_kb())
            bot.register_next_step_handler(msg, process_admin_text)

    def process_admin_text(message):
        cid = message.chat.id
        if cid not in admin_states:
            return
        state = admin_states[cid]
        if message.text == '⬅️ Назад':
            del admin_states[cid]
            bot.send_message(cid, "Действие отменено.", reply_markup=main_menu(True))
            send_admin_panel(bot, cid)
            return

        action = state['action']
        if action == 'warn':
            car_id = state['car_id']
            conn = get_conn()
            c = conn.cursor()
            c.execute("SELECT user_id, brand, model, year FROM cars WHERE id = ?", (car_id,))
            row = c.fetchone()
            conn.close()
            del admin_states[cid]
            if row:
                try:
                    bot.send_message(
                        row[0],
                        f"⚠️ Предупреждение от администратора!
По объявлению: {row[1]} {row[2]}, {row[3]} г. (ID #{car_id})

Замечание: {message.text}"
                    )
                    bot.send_message(cid, "✅ Предупреждение отправлено автору!", reply_markup=main_menu(True))
                except:
                    bot.send_message(cid, "❌ Не удалось отправить сообщение пользователю.", reply_markup=main_menu(True))

        elif action == 'del':
            car_id = state['car_id']
            reason = message.text
            conn = get_conn()
            c = conn.cursor()
            c.execute("SELECT user_id, brand, model, year FROM cars WHERE id = ?", (car_id,))
            row = c.fetchone()
            c.execute("DELETE FROM cars WHERE id = ?", (car_id,))
            conn.commit()
            conn.close()
            del admin_states[cid]
            bot.send_message(cid, f"🗑 Объявление #{car_id} удалено.", reply_markup=main_menu(True))
            if row:
                try:
                    bot.send_message(
                        row[0],
                        f"🗑 Ваше объявление ({row[1]} {row[2]}, {row[3]} г.) удалено администратором.
Причина: {reason}"
                    )
                except:
                    pass

        elif action == 'add_admin':
            new_id = None
            if message.forward_from:
                new_id = message.forward_from.id
            elif message.text and message.text.strip().isdigit():
                new_id = int(message.text.strip())
            del admin_states[cid]
            if new_id:
                add_admin(new_id, 0)
                bot.send_message(cid, f"✅ Пользователь {new_id} назначен администратором!", reply_markup=main_menu(True))
                try:
                    bot.send_message(new_id, "👑 Вам выданы права администратора! Нажмите /start для обновления меню.")
                except:
                    pass
            else:
                bot.send_message(cid, "❌ Не удалось распознать ID. Убедитесь, что прислали цифры или переслали сообщение с открытым профилем.", reply_markup=main_menu(True))

        elif action == 'rem_admin':
            del admin_states[cid]
            if message.text and message.text.strip().isdigit():
                rem_id = int(message.text.strip())
                remove_admin(rem_id)
                bot.send_message(cid, f"✅ Права администратора сняты с ID {rem_id}.", reply_markup=main_menu(True))
            else:
                bot.send_message(cid, "❌ Введите корректный цифровой ID.", reply_markup=main_menu(True))

def show_pending_car(bot, chat_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM cars WHERE status = 'pending' ORDER BY id ASC LIMIT 1")
    car = c.fetchone()
    conn.close()
    if not car:
        bot.send_message(chat_id, "✅ Новых объявлений на проверке нет.")
        return

    caption = "⏳ ПРОВЕРКА ОБЪЯВЛЕНИЯ

" + format_car_text(car)
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Одобрить", callback_data=f"adm_ok_{car[0]}"),
        types.InlineKeyboardButton("⚠️ Предупреждение", callback_data=f"adm_warn_{car[0]}")
    )
    markup.row(types.InlineKeyboardButton("🗑 Удалить с причиной", callback_data=f"adm_del_{car[0]}"))
    bot.send_photo(chat_id, car[3], caption=caption, reply_markup=markup)

def show_all_cars(bot, chat_id, offset):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM cars WHERE status = 'approved'")
    total = c.fetchone()[0]
    if total == 0:
        conn.close()
        bot.send_message(chat_id, "В базе пока нет опубликованных объявлений.")
        return
    if offset < 0:
        offset = 0
    if offset >= total:
        offset = total - 1
    c.execute("SELECT * FROM cars WHERE status = 'approved' ORDER BY id DESC LIMIT 1 OFFSET ?", (offset,))
    car = c.fetchone()
    conn.close()

    caption = f"📋 ОБЪЯВЛЕНИЕ {offset + 1} из {total}

" + format_car_text(car)
    markup = types.InlineKeyboardMarkup()
    nav = []
    if offset > 0:
        nav.append(types.InlineKeyboardButton("⬅️ Пред.", callback_data=f"adm_all_{offset - 1}"))
    if offset + 1 < total:
        nav.append(types.InlineKeyboardButton("След. ➡️", callback_data=f"adm_all_{offset + 1}"))
    if nav:
        markup.row(*nav)
    markup.row(
        types.InlineKeyboardButton("📞 Написать автору", callback_data=f"adm_contact_{car[0]}"),
        types.InlineKeyboardButton("⚠️ Предупреждение", callback_data=f"adm_warn_{car[0]}")
    )
    markup.row(types.InlineKeyboardButton("🗑 Удалить с причиной", callback_data=f"adm_del_{car[0]}"))
    bot.send_photo(chat_id, car[3], caption=caption, reply_markup=markup)
