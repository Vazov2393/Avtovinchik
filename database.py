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
        photos TEXT, brand TEXT, model TEXT, year INTEGER, mileage INTEGER DEFAULT 0,
        gearbox TEXT DEFAULT '', engine TEXT DEFAULT '', price INTEGER,
        condition TEXT, docs TEXT, description TEXT, city TEXT, lat REAL, lon REAL,
        status TEXT DEFAULT 'pending', published_at INTEGER DEFAULT 0,
        check_sent_at INTEGER DEFAULT 0)""")

    car_cols = [r[1] for r in db_exec("PRAGMA table_info(cars)", fetch="all")]
    migrations_cars = {
        "photos": "TEXT DEFAULT '[]'",
        "mileage": "INTEGER DEFAULT 0",
        "gearbox": "TEXT DEFAULT ''",
        "engine": "TEXT DEFAULT ''",
        "published_at": "INTEGER DEFAULT 0",
        "check_sent_at": "INTEGER DEFAULT 0"
    }
    for col, col_type in migrations_cars.items():
        if col not in car_cols:
            db_exec(f"ALTER TABLE cars ADD COLUMN {col} {col_type}")
    if "photo" in car_cols and "photos" in car_cols:
        db_exec("UPDATE cars SET photos=photo WHERE (photos IS NULL OR photos='' OR photos='[]') AND photo IS NOT NULL")

    db_exec("""CREATE TABLE IF NOT EXISTS filters (
        user_id INTEGER PRIMARY KEY, brand TEXT DEFAULT 'Любая', model TEXT DEFAULT 'Любая',
        year_from INTEGER DEFAULT 1970, year_to INTEGER DEFAULT 2030,
        price_from INTEGER DEFAULT 0, price_to INTEGER DEFAULT 99999999,
        city_name TEXT DEFAULT 'Не задан', lat REAL, lon REAL,
        radius INTEGER DEFAULT 5000, docs_only_clean INTEGER DEFAULT 0,
        notify INTEGER DEFAULT 1)""")

    flt_cols = [r[1] for r in db_exec("PRAGMA table_info(filters)", fetch="all")]
    if "notify" not in flt_cols:
        db_exec("ALTER TABLE filters ADD COLUMN notify INTEGER DEFAULT 1")

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
