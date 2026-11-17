import time
from telebot import types
from config import bot
from database import db_exec, is_admin, get_admins_list
from utils import main_kb, back_kb

db_exec("""CREATE TABLE IF NOT EXISTS banned (
    user_id INTEGER PRIMARY KEY,
    reason TEXT,
    banned_at INTEGER,
    appeal_sent_at INTEGER DEFAULT 0
)""")

try:
    db_exec("ALTER TABLE banned ADD COLUMN appeal_sent_at INTEGER DEFAULT 0")
except Exception:
    pass


def get_ban_info(uid):
    if is_admin(uid):
        return None
    row = db_exec("SELECT reason, appeal_sent_at FROM banned WHERE user_id=?", (uid,), "one")
    return row if row else None


def appeal_kb():
    mk = types.InlineKeyboardMarkup()
    mk.add(types.InlineKeyboardButton("🆘 Написать в техподдержку (обжаловать бан)", callback_data="ban_appeal"))
    return mk


def ban_user(target_uid, reason="Нарушение правил"):
    now = int(time.time())
    db_exec(
        "INSERT OR REPLACE INTO banned (user_id, reason, banned_at, appeal_sent_at) VALUES (?, ?, ?, 0)",
        (target_uid, reason, now)
    )
    cars = db_exec("SELECT id FROM cars WHERE user_id=?", (target_uid,), "all")
    for (cid,) in cars:
        db_exec("DELETE FROM cars WHERE id=?", (cid,))
        db_exec("DELETE FROM viewed WHERE car_id=?", (cid,))
        db_exec("DELETE FROM favorites WHERE car_id=?", (cid,))
    try:
        bot.send_message(
            target_uid,
            f"🚫 Вы заблокированы в боте.\nПричина: {reason}\n\nЕсли считаете блокировку ошибочной, вы можете связаться с администрацией:",
            reply_markup=appeal_kb()
        )
    except Exception:
        pass


def unban_user(target_uid):
    db_exec("DELETE FROM banned WHERE user_id=?", (target_uid,))
    try:
        bot.send_message(
            target_uid,
            "✅ Ваша блокировка в боте снята! Доступ восстановлен.",
            reply_markup=main_kb(target_uid)
        )
    except Exception:
        pass


@bot.message_handler(
    func=lambda m: get_ban_info(m.from_user.id) is not None,
    content_types=["text", "photo", "location", "document", "video", "voice", "audio", "sticker"]
)
def block_banned_messages(m):
    info = get_ban_info(m.from_user.id)
    reason = info[0]
    bot.send_message(
        m.from_user.id,
        f"🚫 Доступ к боту ограничен.\nПричина: {reason}",
        reply_markup=appeal_kb()
    )


@bot.callback_query_handler(func=lambda call: call.data == "ban_appeal")
def cb_ban_appeal(call):
    uid = call.from_user.id
    info = get_ban_info(uid)
    if not info:
        bot.answer_callback_query(call.id, "Вы не заблокированы.")
        return
    reason, last_appeal = info
    now = int(time.time())
    if last_appeal and (now - last_appeal) < 86400:
        bot.answer_callback_query(
            call.id,
            "⏳ Вы уже отправляли обращение. Повторно написать можно через 24 часа.",
            show_alert=True
        )
        return
    bot.answer_callback_query(call.id)
    msg = bot.send_message(
        uid,
        "✍️ Напишите ваше сообщение для администрации (текстом или с фото), чтобы обжаловать блокировку:",
        reply_markup=back_kb()
    )
    bot.register_next_step_handler(msg, send_ban_appeal, reason)


def send_ban_appeal(m, reason):
    uid = m.from_user.id
    if m.text == "⬅️ Назад":
        return bot.send_message(uid, "Отменено.", reply_markup=appeal_kb())
    now = int(time.time())
    db_exec("UPDATE banned SET appeal_sent_at=? WHERE user_id=?", (now, uid))

    uname = f"@{m.from_user.username}" if m.from_user.username else "без ника"
    header = (
        f"⚖️ ОБЖАЛОВАНИЕ БАНА\n"
        f"От: {m.from_user.first_name} ({uname} | ID: {uid})\n"
        f"Причина бана: {reason}\n\n"
    )
    mk = types.InlineKeyboardMarkup()
    mk.row(
        types.InlineKeyboardButton("✅ Разбанить", callback_data=f"ban_unban_{uid}"),
        types.InlineKeyboardButton("💬 Ответить анонимно", callback_data=f"ban_rep_{uid}")
    )
    for a in get_admins_list():
        try:
            if m.photo:
                bot.send_photo(a, m.photo[-1].file_id, caption=header + (m.caption or ""), reply_markup=mk)
            elif m.text:
                bot.send_message(a, header + m.text, reply_markup=mk)
        except Exception:
            pass
    bot.send_message(
        uid,
        "✅ Ваше обращение отправлено администрации. Ожидайте решения.",
        reply_markup=types.ReplyKeyboardRemove()
    )


@bot.callback_query_handler(func=lambda call: get_ban_info(call.from_user.id) is not None)
def block_banned_callbacks(call):
    info = get_ban_info(call.from_user.id)
    bot.answer_callback_query(call.id, f"🚫 Вы заблокированы: {info[0]}", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data.startswith("ban_unban_") and is_admin(call.from_user.id))
def cb_admin_unban(call):
    target_uid = int(call.data.split("_")[2])
    unban_user(target_uid)
    bot.answer_callback_query(call.id, "✅ Пользователь разбанен!")
    try:
        bot.edit_message_reply_markup(call.from_user.id, call.message.message_id, reply_markup=None)
    except Exception:
        pass
    bot.send_message(call.from_user.id, f"✅ Пользователь ID `{target_uid}` разблокирован.", parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data.startswith("ban_rep_") and is_admin(call.from_user.id))
def cb_admin_ban_reply(call):
    target_uid = int(call.data.split("_")[2])
    bot.answer_callback_query(call.id)
    msg = bot.send_message(
        call.from_user.id,
        f"✍️ Введите анонимный ответ для заблокированного пользователя ID {target_uid}:",
        reply_markup=back_kb()
    )
    bot.register_next_step_handler(msg, admin_ban_reply_step, target_uid)


def admin_ban_reply_step(m, target_uid):
    uid = m.from_user.id
    if m.text == "⬅️ Назад":
        return bot.send_message(uid, "Отменено.", reply_markup=main_kb(uid))
    try:
        if m.photo:
            bot.send_photo(target_uid, m.photo[-1].file_id, caption="👨‍💻 Ответ администрации:\n\n" + (m.caption or ""))
        elif m.text:
            bot.send_message(target_uid, f"👨‍💻 Ответ администрации:\n\n{m.text}")
        bot.send_message(uid, "✅ Ответ отправлен пользователю!", reply_markup=main_kb(uid))
    except Exception:
        bot.send_message(uid, "❌ Не удалось отправить сообщение (бот заблокирован).", reply_markup=main_kb(uid))


@bot.message_handler(commands=["ban"])
def cmd_ban(m):
    uid = m.from_user.id
    if not is_admin(uid):
        return
    parts = m.text.split(maxsplit=2)
    if len(parts) < 2 or not parts[1].isdigit():
        return bot.send_message(
            uid,
            "ℹ️ Использование: `/ban ID_пользователя Причина`\nПример: `/ban 123456789 Фейковые объявления`",
            parse_mode="Markdown"
        )
    target_uid = int(parts[1])
    if is_admin(target_uid):
        return bot.send_message(uid, "❌ Нельзя забанить администратора.")
    reason = parts[2] if len(parts) > 2 else "Нарушение правил"
    ban_user(target_uid, reason)
    bot.send_message(uid, f"🚫 Пользователь `{target_uid}` забанен.\nПричина: {reason}", parse_mode="Markdown")


@bot.message_handler(commands=["unban"])
def cmd_unban(m):
    uid = m.from_user.id
    if not is_admin(uid):
        return
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].isdigit():
        return bot.send_message(
            uid,
            "ℹ️ Использование: `/unban ID_пользователя`\nПример: `/unban 123456789`",
            parse_mode="Markdown"
        )
    target_uid = int(parts[1])
    unban_user(target_uid)
    bot.send_message(uid, f"✅ Пользователь `{target_uid}` разблокирован.", parse_mode="Markdown")


@bot.message_handler(commands=["banlist"])
def cmd_banlist(m):
    uid = m.from_user.id
    if not is_admin(uid):
        return
    rows = db_exec("SELECT user_id, reason FROM banned", fetch="all")
    if not rows:
        return bot.send_message(uid, "📋 Список заблокированных пуст.")
    mk = types.InlineKeyboardMarkup()
    lines = []
    for r in rows:
        lines.append(f"• `{r[0]}` — {r[1]}")
        mk.add(types.InlineKeyboardButton(f"✅ Разбанить {r[0]}", callback_data=f"ban_unban_{r[0]}"))
    bot.send_message(
        uid,
        "🚫 **Забаненные пользователи:**\n\n" + "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=mk
    )
