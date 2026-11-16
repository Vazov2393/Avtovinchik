import sqlite3

DB_NAME = 'cars.db'

def get_conn():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS cars (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        photo TEXT,
        brand TEXT,
        model TEXT,
        year INTEGER,
        price INTEGER,
        condition TEXT,
        docs TEXT,
        description TEXT,
        city TEXT,
        lat REAL,
        lon REAL,
        status TEXT DEFAULT 'pending'
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS filters (
        user_id INTEGER PRIMARY KEY,
        brand TEXT DEFAULT 'Любая',
        model TEXT DEFAULT 'Любая',
        year_from INTEGER DEFAULT 1970,
        year_to INTEGER DEFAULT 2030,
        price_from INTEGER DEFAULT 0,
        price_to INTEGER DEFAULT 99999999,
        city_name TEXT DEFAULT 'Не задан',
        lat REAL,
        lon REAL,
        radius INTEGER DEFAULT 5000,
        docs_only_clean INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS viewed (
        user_id INTEGER,
        car_id INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY,
        is_super INTEGER DEFAULT 0
    )''')
    conn.commit()
    conn.close()

def is_admin(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT user_id FROM admins WHERE user_id = ?', (user_id,))
    res = c.fetchone()
    conn.close()
    return res is not None

def has_any_admin():
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM admins')
    cnt = c.fetchone()[0]
    conn.close()
    return cnt > 0

def add_admin(user_id, is_super=0):
    conn = get_conn()
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO admins (user_id, is_super) VALUES (?, ?)', (user_id, is_super))
    conn.commit()
    conn.close()

def remove_admin(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('DELETE FROM admins WHERE user_id = ? AND is_super = 0', (user_id,))
    conn.commit()
    conn.close()

def get_all_admins():
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT user_id, is_super FROM admins')
    res = c.fetchall()
    conn.close()
    return res

def get_user_filter(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM filters WHERE user_id = ?', (user_id,))
    f = c.fetchone()
    if not f:
        c.execute('INSERT INTO filters (user_id) VALUES (?)', (user_id,))
        conn.commit()
        c.execute('SELECT * FROM filters WHERE user_id = ?', (user_id,))
        f = c.fetchone()
    conn.close()
    return f
