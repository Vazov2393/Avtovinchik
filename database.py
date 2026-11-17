import sqlite3
from config import DB, MY_ADMIN_ID


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
        status TEXT DEFAULT 'pending', published_at INTEGER DEFAULT 0,
        check_sent_at INTEGER DEFAULT 0)""")
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


def get_admins_list():
    adms = [r[0] for r in db_exec("SELECT user_id FROM admins", fetch="all")]
    if MY_ADMIN_ID and MY_ADMIN_ID not in adms:
        adms.append(MY_ADMIN_ID)
    return adms
