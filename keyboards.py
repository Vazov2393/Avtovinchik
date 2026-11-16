from telebot import types

CARS_CATALOG = {
    'Лада (ВАЗ)': ['Приора', 'Гранта', 'Веста', 'Нива', '2114', '2110', '2107', 'Калина'],
    'Toyota': ['Camry', 'Corolla', 'RAV4', 'Land Cruiser', 'Mark II', 'Chaser', 'Avensis'],
    'Hyundai': ['Solaris', 'Accent', 'Creta', 'Sonata', 'Elantra', 'Tucson', 'Santa Fe'],
    'Kia': ['Rio', 'Ceed', 'Sportage', 'Optima', 'K5', 'Cerato', 'Spectra'],
    'Volkswagen': ['Polo', 'Passat', 'Golf', 'Tiguan', 'Jetta', 'Touareg'],
    'Nissan': ['Almera', 'Qashqai', 'X-Trail', 'Teana', 'Juke', 'Note'],
    'Ford': ['Focus', 'Mondeo', 'Fusion', 'Kuga', 'Fiesta'],
    'Renault': ['Logan', 'Sandero', 'Duster', 'Megane', 'Arkana'],
    'Chevrolet': ['Cruze', 'Lacetti', 'Niva', 'Aveo', 'Lanos'],
    'BMW': ['3 серия', '5 серия', '7 серия', 'X5', 'X3', 'X6'],
    'Mercedes-Benz': ['C-класс', 'E-класс', 'S-класс', 'GLC', 'GLE'],
    'Skoda': ['Octavia', 'Rapid', 'Superb', 'Kodiaq', 'Yeti'],
    'Mazda': ['3', '6', 'CX-5', 'CX-7'],
    'Mitsubishi': ['Lancer', 'Outlander', 'Pajero', 'ASX']
}

def main_menu(is_adm=False):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('🚗 Купить авто', '💰 Продать авто')
    markup.row('⚙️ Мой фильтр', '📋 Мои объявления')
    if is_adm:
        markup.row('👑 Админ-панель')
    return markup

def back_kb():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('⬅️ Назад')
    return markup

def brands_kb(include_any=False):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if include_any:
        markup.row('Любая')
    brands = list(CARS_CATALOG.keys())
    for i in range(0, len(brands), 2):
        markup.row(*brands[i:i+2])
    markup.row('✍️ Другая марка')
    markup.row('⬅️ Назад')
    return markup

def models_kb(brand, include_any=False):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if include_any:
        markup.row('Любая')
    models = CARS_CATALOG.get(brand, [])
    for i in range(0, len(models), 2):
        markup.row(*models[i:i+2])
    markup.row('✍️ Другая модель')
    markup.row('⬅️ Назад')
    return markup

def condition_kb():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('Отличное / Не требует вложений')
    markup.row('На ходу / Есть нюансы')
    markup.row('Требует ремонта / Битая')
    markup.row('⬅️ Назад')
    return markup

def docs_kb():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('Чистые (без проблем)')
    markup.row('Есть проблемы (запрет, утиль, без ПТС)')
    markup.row('⬅️ Назад')
    return markup

def geo_kb():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("📍 Отправить мою геопозицию", request_location=True))
    markup.row('⬅️ Назад')
    return markup

def preview_inline_kb():
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("✅ Отправить на модерацию", callback_data="prev_submit"))
    markup.row(
        types.InlineKeyboardButton("📸 Изменить фото", callback_data="prev_edit_photo"),
        types.InlineKeyboardButton("💰 Изменить цену", callback_data="prev_edit_price")
    )
    markup.row(
        types.InlineKeyboardButton("✍️ Изменить описание", callback_data="prev_edit_desc"),
        types.InlineKeyboardButton("❌ Отменить", callback_data="prev_cancel")
    )
    return markup

def admin_menu_kb(pending_count, active_count):
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton(f"⏳ На модерации ({pending_count})", callback_data="adm_pending"))
    markup.row(types.InlineKeyboardButton(f"📋 Все объявления ({active_count})", callback_data="adm_all_0"))
    markup.row(types.InlineKeyboardButton("👥 Управление админами", callback_data="adm_staff"))
    return markup
