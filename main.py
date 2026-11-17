import time
import threading
from telebot import types
from config import bot
from database import init_db, db_exec
import handlers_user
import handlers_buyer
import handlers_admin

THREE_DAYS = 3 * 24 * 3600
ONE_DAY = 24 * 3600


def check_actuality_worker():
    while True:
        try:
            now = int(time.time())
            # 1. Удаляем объявления, по которым не ответили за 24 часа
            expired = db_exec(
                "SELECT id, user_id, brand, model FROM cars WHERE status='approved' AND check_sent_at > 0 AND ? - check_sent_at >= ?",
                (now, ONE_DAY), "all"
            )
            for cid, uid, brand, model in expired:
                db_exec("DELETE FROM cars WHERE id=?", (cid,))
                db_exec("DELETE FROM viewed WHERE car_id=?", (cid,))
                db_exec("DELETE FROM favorites WHERE car_id=?", (cid,))
                try:
                    bot.send_message(
                        uid,
                        f"🗑 Ваше объявление ({brand} {model}) автоматически удалено, так как вы не подтвердили его актуальность в течение 24 часов."
                    )
                except Exception:
                    pass

            # 2. Отправляем запрос актуальности каждые 3 дня
            to_check = db_exec(
                "SELECT id, user_id, brand, model FROM cars WHERE status='approved' AND check_sent_at = 0 AND published_at > 0 AND ? - published_at >= ?",
                (now, THREE_DAYS), "all"
            )
            for cid, uid, brand, model in to_check:
                db_exec("UPDATE cars SET check_sent_at=? WHERE id=?", (now, cid))
                mk = types.InlineKeyboardMarkup()
                mk.row(
                    types.InlineKeyboardButton("✅ Да, актуально", callback_data=f"act_ok_{cid}"),
                    types.InlineKeyboardButton("🗑 Снять с продажи", callback_data=f"my_dl_{cid}")
                )
                try:
                    bot.send_message(
                        uid,
                        f"⏳ Проверка актуальности!\n\nВаше авто ({brand} {model}) размещено уже 3 дня. Объявление еще актуально?\n\n⚠️ Если не ответить в течение 24 часов, объявление удалится автоматически.",
                        reply_markup=mk
                    )
                except Exception:
                    pass
        except Exception as e:
            print(f"Ошибка фоновой проверки: {e}")
        time.sleep(600)


if __name__ == "__main__":
    init_db()
    t = threading.Thread(target=check_actuality_worker, daemon=True)
    t.start()
    print("Автовинчик (модульная версия) запущен!")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
