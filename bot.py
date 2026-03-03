import telebot
from telebot import types
import sqlite3
import os
import json
import logging
from datetime import datetime, timedelta
import threading
from flask import Flask
import uuid
import time

API_TOKEN = '8305687409:AAF4-xPc-lwMyJQHcvEFNKxn_nrpWVHBC80'
ADMIN_ID = 7666979987
ADMIN_USERNAME = 'IDD_ADMINN'
CARD_NUMBER = '9860080195351079'
CARD_HOLDER = 'Nargiza Karshiyeva'
BOT_USERNAME = 'bot_username'

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

PREMIUM_PRICES = {
    '1_month': {'months': 1, 'price': 25000, 'display': '1 Oy Premium'},
    '3_months': {'months': 3, 'price': 60000, 'display': '3 Oy Premium'},
    '12_months': {'months': 12, 'price': 180000, 'display': '1 Yil Premium'}
}

STARS_PRICES = {
    '100_stars': {'count': 100, 'price': 10000, 'display': '100 ⭐ Stars'},
    '500_stars': {'count': 500, 'price': 45000, 'display': '500 ⭐ Stars'},
    '1000_stars': {'count': 1000, 'price': 80000, 'display': '1000 ⭐ Stars'},
    '5000_stars': {'count': 5000, 'price': 350000, 'display': '5000 ⭐ Stars'}
}

def init_db():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users(
                 user_id INTEGER PRIMARY KEY,
                 username TEXT,
                 first_name TEXT,
                 balance REAL DEFAULT 0,
                 referrals INTEGER DEFAULT 0,
                 referred_by INTEGER,
                 is_premium INTEGER DEFAULT 0,
                 premium_until TEXT,
                 stars REAL DEFAULT 0,
                 total_earned REAL DEFAULT 0,
                 referral_income REAL DEFAULT 0,
                 join_date TEXT,
                 last_active TEXT,
                 is_banned INTEGER DEFAULT 0,
                 is_required_premium INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS orders(
                 order_id TEXT PRIMARY KEY,
                 user_id INTEGER,
                 product_type TEXT,
                 product_id TEXT,
                 amount REAL,
                 status TEXT,
                 payment_method TEXT,
                 created_at TEXT,
                 completed_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions(
                 transaction_id TEXT PRIMARY KEY,
                 user_id INTEGER,
                 amount REAL,
                 type TEXT,
                 description TEXT,
                 created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS referral_history(
                 referral_id TEXT PRIMARY KEY,
                 referrer_id INTEGER,
                 referred_user_id INTEGER,
                 bonus_amount REAL,
                 created_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS admin_settings(
                 setting_id INTEGER PRIMARY KEY,
                 card_number TEXT,
                 card_holder TEXT,
                 min_topup REAL DEFAULT 5000,
                 max_topup REAL DEFAULT 1000000,
                 ref_commission REAL DEFAULT 500,
                 premium_commission REAL DEFAULT 10,
                 stars_commission REAL DEFAULT 5,
                 topup_commission REAL DEFAULT 0,
                 required_subscription INTEGER DEFAULT 0,
                 subscription_channel TEXT,
                 subscription_price REAL DEFAULT 0)''')
    conn.commit()
    conn.close()

init_db()

def get_admin_settings():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT * FROM admin_settings WHERE setting_id=1")
    settings = c.fetchone()
    conn.close()
    if not settings:
        conn = sqlite3.connect('bot_data.db')
        c = conn.cursor()
        c.execute("""INSERT INTO admin_settings(setting_id, card_number, card_holder, min_topup, max_topup, ref_commission, premium_commission, stars_commission, topup_commission, required_subscription, subscription_channel, subscription_price)
                     VALUES(1, ?, ?, 5000, 1000000, 500, 10, 5, 0, 0, '', 0)""", (CARD_NUMBER, CARD_HOLDER))
        conn.commit()
        conn.close()
        return (1, CARD_NUMBER, CARD_HOLDER, 5000, 1000000, 500, 10, 5, 0, 0, '', 0)
    return settings

def update_admin_setting(setting_key, value):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    update_query = f"UPDATE admin_settings SET {setting_key}=? WHERE setting_id=1"
    c.execute(update_query, (value,))
    conn.commit()
    conn.close()

def get_user_data(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def create_user(user_id, username, first_name, referred_by=None):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    settings = get_admin_settings()
    required_premium = settings[9]
    c.execute("""INSERT INTO users(user_id, username, first_name, referred_by, join_date, last_active, is_required_premium)
                 VALUES(?, ?, ?, ?, ?, ?, ?)""",
              (user_id, username, first_name, referred_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), required_premium))
    conn.commit()
    conn.close()

def add_referral_bonus(referrer_id, referred_user_id, bonus_amount):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    referral_id = str(uuid.uuid4())[:12]
    c.execute("""INSERT INTO referral_history(referral_id, referrer_id, referred_user_id, bonus_amount, created_at)
                 VALUES(?, ?, ?, ?, ?)""",
              (referral_id, referrer_id, referred_user_id, bonus_amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    c.execute("UPDATE users SET balance=balance+?, referral_income=referral_income+?, referrals=referrals+1 WHERE user_id=?",
              (bonus_amount, bonus_amount, referrer_id))
    conn.commit()
    conn.close()

def main_menu_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("💎 Premium", "🌟 Stars")
    markup.add("📦 Paketlar", "💰 Balans")
    markup.add("👥 Pul ishlash", "❓ Yordam")
    markup.add("♻️ Hisob to'ldirish")
    if user_id == ADMIN_ID:
        markup.add("⚙️ Admin Panel")
    return markup

def premium_inline_markup():
    markup = types.InlineKeyboardMarkup()
    for key, pkg in PREMIUM_PRICES.items():
        btn_text = f"💎 {pkg['display']} - {pkg['price']:,} so'm"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"buy_premium_{key}"))
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_menu"))
    return markup

def stars_inline_markup():
    markup = types.InlineKeyboardMarkup()
    for key, pkg in STARS_PRICES.items():
        btn_text = f"⭐ {pkg['display']} - {pkg['price']:,} so'm"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"buy_stars_{key}"))
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_menu"))
    return markup

def payment_method_markup(order_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Karta orqali", callback_data=f"pay_card_{order_id}"))
    markup.add(types.InlineKeyboardButton("💰 Balansdan", callback_data=f"pay_balance_{order_id}"))
    markup.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data=f"cancel_order_{order_id}"))
    return markup

def admin_panel_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📊 Statistika", "⚙️ Sozlamalar")
    markup.add("📧 Xabar yuborish", "👥 Foydalanuvchilar")
    markup.add("📈 Daromad", "📋 Buyurtmalar")
    markup.add("🔐 Majburiy Obuna", "🔙 Orqaga")
    return markup

def admin_settings_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Karta", callback_data="setting_card"))
    markup.add(types.InlineKeyboardButton("🔢 Min/Max to'lov", callback_data="setting_minmax"))
    markup.add(types.InlineKeyboardButton("💰 Komissiyalar", callback_data="setting_commission"))
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back"))
    return markup

def check_required_subscription(user_id):
    user = get_user_data(user_id)
    if user[14]:
        return user[6]
    return True

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or "username_yo'q"
    first_name = message.from_user.first_name or "Foydalanuvchi"
    referred_by = None
    
    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        referred_by = int(args[1])
    
    user = get_user_data(user_id)
    if not user:
        create_user(user_id, username, first_name, referred_by)
        if referred_by and referred_by != user_id:
            ref_user = get_user_data(referred_by)
            if ref_user:
                settings = get_admin_settings()
                ref_bonus = settings[5]
                add_referral_bonus(referred_by, user_id, ref_bonus)
                bot.send_message(referred_by, 
                    f"🎉 <b>Yangi Referal Qo'shildi!</b>\n\n"
                    f"✅ Bonus: +{ref_bonus:,.0f} so'm\n"
                    f"👤 Jami referallar: {ref_user[5] + 1}\n"
                    f"💰 Jami earninglar: {ref_user[10] + ref_bonus:,.0f} so'm", 
                    parse_mode="HTML")
        user = get_user_data(user_id)
    
    settings = get_admin_settings()
    if settings[9]:
        if not check_required_subscription(user_id):
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("💎 Obuna bo'lish", url=settings[10]))
            bot.send_message(user_id, 
                f"🔒 <b>MAJBURIY OBUNA</b>\n\n"
                f"Botdan foydalanish uchun quyidagi kanalga obuna bo'lishingiz kerak:\n\n"
                f"{settings[10]}\n\n"
                f"Obuna bo'lganingizdan keyin /start buyrug'ini qayta bosing.",
                parse_mode="HTML",
                reply_markup=markup)
            return
    
    welcome_text = f"""
<b>👋 Assalomu alaykum!</b>

🤖 <b>Mening Botimga Xush Kelibsiz!</b>

<b>Siz quyidagi xizmatlardan foydalanishingiz mumkin:</b>

💎 <b>Premium</b> - Telegram Premium sotib oling
⭐ <b>Stars</b> - Telegram Stars olish
💰 <b>Balans</b> - Balansingizni ko'rish
👥 <b>Pul ishlash</b> - Referal orqali daromad
♻️ <b>Hisob to'ldirish</b> - Balans qo'shish
❓ <b>Yordam</b> - Savol-javoblar

<i>Tugmalardan birini tanlang va boshlang!</i>
    """
    bot.send_message(user_id, welcome_text, parse_mode="HTML", reply_markup=main_menu_keyboard(user_id))

@bot.message_handler(func=lambda m: m.text == "💎 Premium")
def premium_handler(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    
    if user[14] and not check_required_subscription(user_id):
        markup = types.InlineKeyboardMarkup()
        settings = get_admin_settings()
        markup.add(types.InlineKeyboardButton("💎 Obuna bo'lish", url=settings[10]))
        bot.send_message(user_id, 
            f"🔒 <b>MAJBURIY OBUNA</b>\n\n"
            f"Ushbu xizmatdan foydalanish uchun quyidagi kanalga obuna bo'lishingiz kerak.",
            parse_mode="HTML",
            reply_markup=markup)
        return
    
    if user[6]:
        expiry = user[7] if user[7] else "Cheksiz"
        bot.send_message(user_id, 
            f"✅ <b>Siz allaqachon Premium foydalanuvchisiz!</b>\n\n"
            f"💎 <b>Premium Status:</b> Faol\n"
            f"📅 <b>Amal qilish muddati:</b> {expiry}\n\n"
            f"<i>Yangi paket sotib olishingiz mumkin va muddat uzaytiriladi.</i>", 
            parse_mode="HTML")
        return
    
    text = """
<b>💎 PREMIUM PAKETLARINI TANLANG</b>

<i>Premium obunasi bilan Telegram-ning barcha premium xususiyatlaridan foydalaning!</i>

<b>Nima beradi:</b>
✨ Custom emoji
🎨 Profil rangini o'zgartirish
🎭 Emoji o'lami
📁 Papka tashkillash
+ Yana ko'plab features

<b>Paketlarni tanlang:</b>
    """
    
    bot.send_message(user_id, text, parse_mode="HTML", reply_markup=premium_inline_markup())

@bot.message_handler(func=lambda m: m.text == "🌟 Stars")
def stars_handler(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    
    if user[14] and not check_required_subscription(user_id):
        markup = types.InlineKeyboardMarkup()
        settings = get_admin_settings()
        markup.add(types.InlineKeyboardButton("💎 Obuna bo'lish", url=settings[10]))
        bot.send_message(user_id, 
            f"🔒 <b>MAJBURIY OBUNA</b>\n\n"
            f"Ushbu xizmatdan foydalanish uchun quyidagi kanalga obuna bo'lishingiz kerak.",
            parse_mode="HTML",
            reply_markup=markup)
        return
    
    text = f"""
<b>⭐ TELEGRAM STARS SOTIB OLING</b>

<i>Telegram Stars bilan o'z sevimli kontentni qo'llab-quvvatlang!</i>

<b>Stars nima?</b>
Telegram's yangi to'lov valuutasi
Kontentni qo'llab-quvvatlash
In-app xaridlar

<b>Sizning hozirgi Stars:</b> {user[8]:,.0f} ⭐

<b>Paketlarni tanlang:</b>
    """
    
    bot.send_message(user_id, text, parse_mode="HTML", reply_markup=stars_inline_markup())

@bot.message_handler(func=lambda m: m.text == "📦 Paketlar")
def packages_handler(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    
    if user[14] and not check_required_subscription(user_id):
        markup = types.InlineKeyboardMarkup()
        settings = get_admin_settings()
        markup.add(types.InlineKeyboardButton("💎 Obuna bo'lish", url=settings[10]))
        bot.send_message(user_id, 
            f"🔒 <b>MAJBURIY OBUNA</b>\n\n"
            f"Ushbu xizmatdan foydalanish uchun quyidagi kanalga obuna bo'lishingiz kerak.",
            parse_mode="HTML",
            reply_markup=markup)
        return
    
    text = "<b>📦 BARCHA MAVJUD PAKETLAR</b>\n\n"
    text += "<b>💎 PREMIUM PAKETLARI:</b>\n"
    for key, pkg in PREMIUM_PRICES.items():
        text += f"  💎 <b>{pkg['display']}</b> - {pkg['price']:,} so'm\n"
    
    text += "\n<b>⭐ STARS PAKETLARI:</b>\n"
    for key, pkg in STARS_PRICES.items():
        text += f"  ⭐ <b>{pkg['display']}</b> - {pkg['price']:,} so'm\n"
    
    text += "\n<b>💰 TO'LOV USULLARI:</b>\n"
    text += "  💳 <b>Karta orqali</b> (UzCard, Humo)\n"
    text += "  💵 <b>Balansdan</b>\n"
    text += "  👥 <b>Referal bonus</b>\n"
    
    text += "\n<b>⚡ XUSUSIYATLAR:</b>\n"
    text += "  ✅ Instant tasdiqlanish\n"
    text += "  🔒 Xavfli to'lov\n"
    text += "  📊 To'liq statistika\n"
    
    bot.send_message(user_id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "💰 Balans")
def balance_handler(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    
    if user[14] and not check_required_subscription(user_id):
        markup = types.InlineKeyboardMarkup()
        settings = get_admin_settings()
        markup.add(types.InlineKeyboardButton("💎 Obuna bo'lish", url=settings[10]))
        bot.send_message(user_id, 
            f"🔒 <b>MAJBURIY OBUNA</b>\n\n"
            f"Ushbu xizmatdan foydalanish uchun quyidagi kanalga obuna bo'lishingiz kerak.",
            parse_mode="HTML",
            reply_markup=markup)
        return
    
    premium_status = "💎 Premium (Faol)" if user[6] else "📝 Odiy"
    
    text = f"""
<b>💰 SIZNING BALANSINGIZ</b>

<b>💵 So'm Balans:</b> {user[3]:,.0f} so'm
<b>⭐ Stars:</b> {user[8]:,.0f} ta
<b>👥 Referallar:</b> {user[5]} ta
<b>📊 Jami Earned:</b> {user[9]:,.0f} so'm
<b>👤 Referal Income:</b> {user[10]:,.0f} so'm

<b>🔑 Hisobat Ma'lumotlari:</b>
<b>🆔 User ID:</b> <code>{user_id}</code>
<b>📅 Qo'shilgan sana:</b> {user[11]}
<b>🌟 Status:</b> {premium_status}
    """
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 Yangilash", callback_data="refresh_balance"))
    
    bot.send_message(user_id, text, parse_mode="HTML", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "👥 Pul ishlash")
def earn_handler(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    settings = get_admin_settings()
    
    if user[14] and not check_required_subscription(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💎 Obuna bo'lish", url=settings[10]))
        bot.send_message(user_id, 
            f"🔒 <b>MAJBURIY OBUNA</b>\n\n"
            f"Ushbu xizmatdan foydalanish uchun quyidagi kanalga obuna bo'lishingiz kerak.",
            parse_mode="HTML",
            reply_markup=markup)
        return
    
    bot_name = bot.get_me().username
    ref_link = f"https://t.me/{bot_name}?start={user_id}"
    
    text = f"""
<b>👥 PUL ISHLASHNI BOSHLANG</b>

<b>Referal sistemasi orqali daromad qilish juda oson!</b>

<b>🔗 Sizning Referal Havolangiz:</b>
<code>{ref_link}</code>

<b>📊 KOMISSIYA JADAVALI:</b>

  💵 <b>Har bir taklif:</b> {settings[5]:,.0f} so'm
  💎 <b>Premium sotish:</b> +{settings[6]:,.0f} so'm bonus
  ⭐ <b>Stars sotish:</b> +{settings[7]:,.0f} so'm bonus

<b>📈 SIZNING STATISTIKA:</b>

  👤 <b>Jami referallar:</b> {user[5]} ta
  💸 <b>Referal income:</b> {user[10]:,.0f} so'm
  📊 <b>Jami daromad:</b> {user[9]:,.0f} so'm

<b>💡 MASLAHAT:</b>
Do'stlaringiz bilan havolangizni ulashing va har bir yangi do'st uchun {settings[5]:,.0f} so'm bonus oling!
Ular Premium yoki Stars sotib olsa, qo'shimcha bonus olasiz!
    """
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📋 Nusxalash", callback_data=f"copy_ref_{user_id}"))
    markup.add(types.InlineKeyboardButton("📊 Referal Tarixi", callback_data=f"ref_history_{user_id}"))
    
    bot.send_message(user_id, text, parse_mode="HTML", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "❓ Yordam")
def help_handler(message):
    settings = get_admin_settings()
    text = f"""
<b>❓ BOTDAN FOYDALANISH VA YORDAM</b>

<b>🔹 ASOSIY XIZMATLAR:</b>

<b>💎 Premium</b>
Telegram Premium obunasini sotib oling va barcha premium xususiyatlardan foydalaning. Bir necha oy davomida avtomatik qayta yangilash.

<b>⭐ Stars</b>
Telegram Stars sotib olib, kontent yaratuvchilarni qo'llab-quvvatlang va ularning nomli kontentiga pul o'tkazing.

<b>💰 Balans</b>
Barcha balans, Stars va daromadingizni real vaqtda ko'ring. To'liq statistika va tahlil.

<b>👥 Pul ishlash</b>
Do'stlaringizni taklif qiling va har bitta yoqtirilgan do'st uchun {settings[5]:,.0f} so'm bonus oling.

<b>♻️ Hisob to'ldirish</b>
Kartangiz orqali balansingizga pul qo'shing. Min: 5,000 so'm | Max: 1,000,000 so'm

<b>🔹 ALOQA VA QO'LLAB-QUVVATLASH:</b>

Admin: <a href="https://t.me/{ADMIN_USERNAME}">@{ADMIN_USERNAME}</a>
ID: {ADMIN_ID}

<b>🔹 TO'LOV USULLARI:</b>

✅ Karta orqali (UzCard, Humo)
✅ Balansdan
✅ Referal bonuslar

<b>🔹 XAVFSIZLIK:</b>

🔒 Barcha to'lovlar xavfli
✅ SSL sertifikati
📋 To'liq tasdiqlanish

<b>⚠️ MUHIM BILGILER:</b>

• Minimum hisob to'ldirish: 5,000 so'm
• Maksimum hisob to'ldirish: 1,000,000 so'm
• To'lovlar 5-15 daqiqa ichida tasdiqlanadi
• Premium avtomatik qayta yangilanadi
• Referal bonuslar darhol qo'shiladi

Boshqa savollar bo'lsa, admin bilan bog'lanishdan tortinmang!
    """
    bot.send_message(message.from_user.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "♻️ Hisob to'ldirish")
def topup_handler(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    settings = get_admin_settings()
    
    if user[14] and not check_required_subscription(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💎 Obuna bo'lish", url=settings[10]))
        bot.send_message(user_id, 
            f"🔒 <b>MAJBURIY OBUNA</b>\n\n"
            f"Ushbu xizmatdan foydalanish uchun quyidagi kanalga obuna bo'lishingiz kerak.",
            parse_mode="HTML",
            reply_markup=markup)
        return
    
    text = """
<b>♻️ BALANSINGIZNI TO'LDIRING</b>

Balansingizga pul qo'shib:
💎 Premium sotib oling
⭐ Stars olish
+ Boshqa xizmatlardan foydalaning

<b>🏦 To'lov usulini tanlang:</b>
    """
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Karta orqali to'lov", callback_data="topup_card"))
    
    bot.send_message(user_id, text, parse_mode="HTML", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Panel")
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.from_user.id, "❌ <b>Siz admin emassiz!</b>", parse_mode="HTML")
        return
    
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders WHERE status='completed'")
    orders = c.fetchone()[0]
    c.execute("SELECT SUM(amount) FROM orders WHERE status='completed'")
    revenue = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM orders WHERE status='pending'")
    pending = c.fetchone()[0]
    conn.close()
    
    text = f"""
<b>⚙️ ADMIN PANEL</b>

<b>📊 ASOSIY STATISTIKA:</b>
👥 Jami foydalanuvchilar: <b>{total_users}</b>
📦 Yakunlangan buyurtmalar: <b>{orders}</b>
💰 Jami daromad: <b>{revenue:,.0f} so'm</b>
⏳ Kutilayotgan: <b>{pending}</b>

<b>👇 Quyida soslamalar va boshqa imkoniyatlardan foydalaning:</b>
    """
    
    bot.send_message(message.from_user.id, text, parse_mode="HTML", reply_markup=admin_panel_markup())

@bot.message_handler(func=lambda m: m.text == "📊 Statistika" and m.from_user.id == ADMIN_ID)
def admin_stats(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(DISTINCT referred_by) FROM users WHERE referred_by IS NOT NULL")
    with_referrals = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM orders WHERE status='completed'")
    completed = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM orders WHERE status='pending'")
    pending = c.fetchone()[0]
    
    c.execute("SELECT SUM(amount) FROM orders WHERE status='completed'")
    total_revenue = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(amount) FROM orders WHERE product_type='premium' AND status='completed'")
    premium_revenue = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(amount) FROM orders WHERE product_type='stars' AND status='completed'")
    stars_revenue = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(amount) FROM orders WHERE product_type='topup' AND status='completed'")
    topup_revenue = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(bonus_amount) FROM referral_history")
    referral_paid = c.fetchone()[0] or 0
    
    conn.close()
    
    text = f"""
<b>📊 BATAFSIL STATISTIKA</b>

<b>👥 FOYDALANUVCHILAR:</b>
  Jami: <b>{total_users}</b> ta
  Referallar bilan: <b>{with_referrals}</b> ta
  O'rtacha: <b>{(total_users/30 if total_users > 0 else 0):.1f}</b> kuniga

<b>📦 BUYURTMALAR:</b>
  Yakunlangan: <b>{completed}</b> ta
  Kutilayotgan: <b>{pending}</b> ta
  To'liq turi: <b>{completed + pending}</b> ta

<b>💰 DAROMAD (Jami):</b>
  Umumiy: <b>{total_revenue:,.0f} so'm</b>
  
  <b>Mahsulot bo'yicha:</b>
    💎 Premium: <b>{premium_revenue:,.0f} so'm</b> ({completed if completed > 0 else 0})
    ⭐ Stars: <b>{stars_revenue:,.0f} so'm</b>
    ♻️ Top-up: <b>{topup_revenue:,.0f} so'm</b>
  
  <b>Bonuslar:</b>
    👥 Referallar: <b>{referral_paid:,.0f} so'm</b>

<b>📈 O'RTACHA:</b>
  Foydalanuvchi uchun: <b>{(total_revenue/total_users if total_users > 0 else 0):,.0f} so'm</b>
  Buyurtma uchun: <b>{(total_revenue/completed if completed > 0 else 0):,.0f} so'm</b>

<b>🎯 KONVERSIYA:</b>
  Foydalanuvchidan daromad: <b>{(completed/total_users*100 if total_users > 0 else 0):.1f}%</b>
    """
    
    bot.send_message(message.from_user.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "⚙️ Sozlamalar" and m.from_user.id == ADMIN_ID)
def admin_settings(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    settings = get_admin_settings()
    text = f"""
<b>⚙️ BOTNING SOZLAMALARI</b>

<b>💳 KARTA MA'LUMOTLARI:</b>
  Raqami: <code>{settings[1]}</code>
  Egasi: <b>{settings[2]}</b>

<b>🔢 TO'LOV CHEGARALARI:</b>
  Minimal: <b>{settings[3]:,.0f} so'm</b>
  Maksimal: <b>{settings[4]:,.0f} so'm</b>

<b>💰 KOMISSIYALAR:</b>
  Referal bonus: <b>{settings[5]:,.0f} so'm</b>
  Premium bonus: <b>{settings[6]:,.0f} so'm</b>
  Stars bonus: <b>{settings[7]:,.0f} so'm</b>
  Top-up komissiya: <b>{settings[8]:,.0f}%</b>

<b>👇 O'zgartirishni tanlang:</b>
    """
    
    bot.send_message(message.from_user.id, text, parse_mode="HTML", reply_markup=admin_settings_markup())

@bot.message_handler(func=lambda m: m.text == "🔐 Majburiy Obuna" and m.from_user.id == ADMIN_ID)
def required_subscription_handler(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    settings = get_admin_settings()
    status = "✅ YOQILGAN" if settings[9] else "❌ O'CHIQLGAN"
    
    text = f"""
<b>🔐 MAJBURIY OBUNA SOZLAMALARI</b>

<b>Hozirgi Status:</b> {status}

<b>Joriy Konfiguratsiya:</b>
  Kanal: {settings[10] if settings[10] else 'Belgilanmagan'}
  Narxi: {settings[11]:,.0f} so'm

<b>Quyidagi buyruqlardan foydalaning:</b>

1️⃣ <b>/sub_on</b> - Majburiy obunani yoqish
2️⃣ <b>/sub_off</b> - Majburiy obunani o'chirish
3️⃣ <b>/sub_channel URL</b> - Kanal linkini o'rnatish
   Misol: /sub_channel https://t.me/mychannel

4️⃣ <b>/sub_price 0</b> - Narx o'rnatish (0 = bepul)
   Misol: /sub_price 50000

<b>📋 Amallar:</b>
/sub_status - Joriy holatni ko'rish
/sub_test 123456789 - User ID ni test qilish
    """
    
    bot.send_message(message.from_user.id, text, parse_mode="HTML")

@bot.message_handler(commands=['sub_on'])
def sub_on(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    update_admin_setting('required_subscription', 1)
    settings = get_admin_settings()
    
    if not settings[10]:
        bot.send_message(message.from_user.id, 
            "⚠️ <b>Kanal linki belgilanmagan!</b>\n\n"
            "Avval /sub_channel URL buyrug'i bilan kanal linkini o'rnating.",
            parse_mode="HTML")
        return
    
    bot.send_message(message.from_user.id, "✅ <b>Majburiy obuna yoqildi!</b>\n\nBarcha yangi foydalanuvchilar obuna bo'lishi kerak bo'ladi.", parse_mode="HTML")

@bot.message_handler(commands=['sub_off'])
def sub_off(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    update_admin_setting('required_subscription', 0)
    bot.send_message(message.from_user.id, "✅ <b>Majburiy obuna o'chirildi!</b>", parse_mode="HTML")

@bot.message_handler(commands=['sub_channel'])
def sub_channel(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        channel_link = message.text.split(' ', 1)[1].strip()
        if not channel_link.startswith('https://t.me/'):
            bot.send_message(message.from_user.id, "❌ <b>Noto'g'ri format!</b>\n\nMisol: /sub_channel https://t.me/mychannel", parse_mode="HTML")
            return
        
        update_admin_setting('subscription_channel', channel_link)
        bot.send_message(message.from_user.id, f"✅ <b>Kanal linki o'rnatildi!</b>\n\n{channel_link}", parse_mode="HTML")
    except:
        bot.send_message(message.from_user.id, "❌ <b>Xato!</b>\n\nMisol: /sub_channel https://t.me/mychannel", parse_mode="HTML")

@bot.message_handler(commands=['sub_price'])
def sub_price(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        price = float(message.text.split()[1])
        update_admin_setting('subscription_price', price)
        bot.send_message(message.from_user.id, f"✅ <b>Narx o'rnatildi!</b>\n\n{price:,.0f} so'm", parse_mode="HTML")
    except:
        bot.send_message(message.from_user.id, "❌ <b>Xato!</b>\n\nMisol: /sub_price 50000", parse_mode="HTML")

@bot.message_handler(commands=['sub_status'])
def sub_status(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    settings = get_admin_settings()
    status = "✅ YOQILGAN" if settings[9] else "❌ O'CHIQLGAN"
    
    text = f"""
<b>🔐 MAJBURIY OBUNA HOLATI</b>

<b>Status:</b> {status}
<b>Kanal:</b> {settings[10] if settings[10] else 'Belgilanmagan'}
<b>Narxi:</b> {settings[11]:,.0f} so'm

<b>Tafsif:</b>
Majburiy obuna yoqilgan bo'lsa, foydalanuvchilar xizmatlardan foydalanish uchun belgilangan kanalga obuna bo'lishi kerak.
    """
    
    bot.send_message(message.from_user.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "📧 Xabar yuborish" and m.from_user.id == ADMIN_ID)
def broadcast_message(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    bot.send_message(message.from_user.id, 
        "<b>📧 JAMI FOYDALANUVCHILARGA XABAR</b>\n\n"
        "Xabar matninini kiriting (HTML formatida yozishingiz mumkin):\n\n"
        "<i>Misol: &lt;b&gt;Yangi xususiyatlar!&lt;/b&gt;</i>", 
        parse_mode="HTML")
    bot.register_next_step_handler(message, process_broadcast)

def process_broadcast(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    broadcast_text = message.text
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = c.fetchall()
    conn.close()
    
    sent = 0
    failed = 0
    
    status_msg = bot.send_message(message.from_user.id, "⏳ <b>Xabar yuborilmoqda...</b>", parse_mode="HTML")
    
    for user in users:
        try:
            bot.send_message(user[0], broadcast_text, parse_mode="HTML")
            sent += 1
        except:
            failed += 1
        time.sleep(0.05)
    
    bot.edit_message_text(
        f"✅ <b>Xabar yuborildi!</b>\n\n"
        f"✔️ Muvaffaqiyatli: <b>{sent}</b>\n"
        f"❌ Xato: <b>{failed}</b>",
        message.from_user.id, status_msg.message_id, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "👥 Foydalanuvchilar" and m.from_user.id == ADMIN_ID)
def users_list(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT user_id, username, first_name, balance, is_premium, referrals FROM users ORDER BY join_date DESC LIMIT 30")
    users = c.fetchall()
    conn.close()
    
    text = "<b>👥 SO'NGGI 30 FOYDALANUVCHI</b>\n\n"
    for i, user in enumerate(users, 1):
        premium_status = "💎" if user[4] else "📝"
        username_display = f"@{user[1]}" if user[1] else "username_yo'q"
        text += f"{i}. {user[2]} ({username_display}) {premium_status}\n"
        text += f"   💰 {user[3]:,.0f} so'm | 👥 {user[5]} referral | 🆔 {user[0]}\n"
    
    bot.send_message(message.from_user.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "📈 Daromad" and m.from_user.id == ADMIN_ID)
def revenue_report(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    c.execute("SELECT SUM(amount) FROM orders WHERE status='completed' AND created_at LIKE ?", (f"{today}%",))
    today_rev = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(amount) FROM orders WHERE status='completed' AND created_at LIKE ?", (f"{yesterday}%",))
    yesterday_rev = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(amount) FROM orders WHERE status='completed' AND created_at > ?", (week_ago,))
    week_rev = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(amount) FROM orders WHERE status='completed' AND created_at > ?", (month_ago,))
    month_rev = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(amount) FROM orders WHERE status='completed'")
    total_rev = c.fetchone()[0] or 0
    
    conn.close()
    
    text = f"""
<b>📈 DAROMAD HISOBOTI</b>

<b>📅 VAQT BO'YICHA:</b>
  Bugun: <b>{today_rev:,.0f} so'm</b>
  Kecha: <b>{yesterday_rev:,.0f} so'm</b>
  Bu hafta: <b>{week_rev:,.0f} so'm</b>
  Bu oy: <b>{month_rev:,.0f} so'm</b>

<b>💰 JAMI DAROMAD:</b> <b>{total_rev:,.0f} so'm</b>

<b>📊 O'RTACHA:</b>
  Kuniga: <b>{(today_rev if today_rev > 0 else total_rev/30):,.0f} so'm</b>
  Oyiga: <b>{(month_rev if month_rev > 0 else 0):,.0f} so'm</b>
    """
    
    bot.send_message(message.from_user.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "📋 Buyurtmalar" and m.from_user.id == ADMIN_ID)
def orders_list(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT order_id, user_id, product_type, amount, status, created_at FROM orders ORDER BY created_at DESC LIMIT 20")
    orders = c.fetchall()
    conn.close()
    
    text = "<b>📋 SO'NGGI 20 BUYURTMA</b>\n\n"
    for i, order in enumerate(orders, 1):
        status_emoji = "✅" if order[4] == "completed" else "⏳" if order[4] == "pending" else "❌"
        text += f"{i}. {status_emoji} #{order[0]}\n"
        text += f"   👤 User: {order[1]} | 📦 {order[2].upper()} | 💰 {order[3]:,.0f} so'm\n"
        text += f"   📅 {order[5]}\n"
    
    bot.send_message(message.from_user.id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "🔙 Orqaga" and m.from_user.id == ADMIN_ID)
def admin_back(message):
    if message.from_user.id != ADMIN_ID:
        return
    bot.send_message(message.from_user.id, "👋 <b>Asosiy menyu</b>", parse_mode="HTML", reply_markup=main_menu_keyboard(message.from_user.id))

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_premium_"))
def buy_premium(call):
    user_id = call.from_user.id
    product_id = call.data.replace("buy_premium_", "")
    
    if product_id not in PREMIUM_PRICES:
        bot.answer_callback_query(call.id, "❌ Xato paket!")
        return
    
    order_id = str(uuid.uuid4())[:12]
    pkg = PREMIUM_PRICES[product_id]
    
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("""INSERT INTO orders(order_id, user_id, product_type, product_id, amount, status, created_at)
                 VALUES(?, ?, ?, ?, ?, ?, ?)""",
              (order_id, user_id, 'premium', product_id, pkg['price'], 'pending', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    
    text = f"""
<b>💎 PREMIUM SOTIB OLISH</b>

<b>Siz tanlagan paket:</b>
📦 {pkg['display']}
💰 Narxi: <b>{pkg['price']:,} so'm</b>
🆔 Buyurtma ID: <code>{order_id}</code>

<b>⏱️ Muddat:</b> {pkg['months']} oy

<b>Kuting... To'lov usulini tanlang:</b>
    """
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=payment_method_markup(order_id))
    bot.answer_callback_query(call.id, "✅ Paket tanlandi!", show_alert=False)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_stars_"))
def buy_stars(call):
    user_id = call.from_user.id
    product_id = call.data.replace("buy_stars_", "")
    
    if product_id not in STARS_PRICES:
        bot.answer_callback_query(call.id, "❌ Xato paket!")
        return
    
    order_id = str(uuid.uuid4())[:12]
    pkg = STARS_PRICES[product_id]
    
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("""INSERT INTO orders(order_id, user_id, product_type, product_id, amount, status, created_at)
                 VALUES(?, ?, ?, ?, ?, ?, ?)""",
              (order_id, user_id, 'stars', product_id, pkg['price'], 'pending', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    
    text = f"""
<b>⭐ STARS SOTIB OLISH</b>

<b>Siz tanlagan paket:</b>
📦 {pkg['display']}
💰 Narxi: <b>{pkg['price']:,} so'm</b>
🆔 Buyurtma ID: <code>{order_id}</code>

<b>⭐ Stars miqdori:</b> {pkg['count']} ta

<b>Kuting... To'lov usulini tanlang:</b>
    """
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=payment_method_markup(order_id))
    bot.answer_callback_query(call.id, "✅ Paket tanlandi!", show_alert=False)

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_card_"))
def pay_card(call):
    user_id = call.from_user.id
    order_id = call.data.replace("pay_card_", "")
    
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT amount, product_type FROM orders WHERE order_id=? AND user_id=?", (order_id, user_id))
    order = c.fetchone()
    conn.close()
    
    if not order:
        bot.answer_callback_query(call.id, "❌ Buyurtma topilmadi!", show_alert=True)
        return
    
    amount, product_type = order
    settings = get_admin_settings()
    
    text = f"""
<b>💳 KARTA ORQALI TO'LOV</b>

<b>To'lov ma'lumotlari:</b>
💰 Summa: <b>{amount:,} so'm</b>
📦 Mahsulot: <b>{product_type.upper()}</b>
🆔 Buyurtma: <code>{order_id}</code>

<b>📍 KARTA DETALYLARI:</b>
💳 Karta raqami: <code>{settings[1]}</code>
👤 Egasi: <b>{settings[2]}</b>

<b>📝 QADAMLAR:</b>
1️⃣ Yuqoridagi karta raqamiga pul o'tkazing
2️⃣ Buyurtma raqamini eslatib qo'ying
3️⃣ Quyidagi ✅ tugmasini bosing

<b>⏰ VAQTI:</b> 
To'lov 5-15 daqiqa ichida tasdiqlanadi

<b>⚠️ MUHIM:</b>
To'lovdan keyin <b>iltimos ✅ tugmasini bosing</b>
Agar 15 daqiqada xabar bo'lmasa, yana bosing
    """
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ To'lov amalga oshdi", callback_data=f"confirm_payment_{order_id}"))
    markup.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data=f"cancel_order_{order_id}"))
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
    bot.answer_callback_query(call.id, "💳 Karta ma'lumotlari ko'rsatildi!", show_alert=False)

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_balance_"))
def pay_balance(call):
    user_id = call.from_user.id
    order_id = call.data.replace("pay_balance_", "")
    
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT amount, product_type, product_id FROM orders WHERE order_id=? AND user_id=?", (order_id, user_id))
    order = c.fetchone()
    
    if not order:
        bot.answer_callback_query(call.id, "❌ Buyurtma topilmadi!", show_alert=True)
        conn.close()
        return
    
    amount, product_type, product_id = order
    c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    
    if not user or user[0] < amount:
        bot.answer_callback_query(call.id, 
            f"❌ Balansingizda yetarli mablag' yo'q!\n\nKerakli: {amount:,.0f} so'm\nHozirgi: {user[0]:,.0f} so'm", 
            show_alert=True)
        conn.close()
        return
    
    c.execute("UPDATE users SET balance=balance-?, last_active=? WHERE user_id=?", 
              (amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
    c.execute("UPDATE orders SET status=?, payment_method=?, completed_at=? WHERE order_id=?",
              ('completed', 'balance', datetime.now().strftime("%Y-%m-%d %H:%M:%S"), order_id))
    
    if product_type == 'premium':
        pkg = PREMIUM_PRICES[product_id]
        premium_until = (datetime.now() + timedelta(days=30*pkg['months'])).strftime("%Y-%m-%d")
        c.execute("UPDATE users SET is_premium=1, premium_until=? WHERE user_id=?", (premium_until, user_id))
        success_text = f"""
✅ <b>PREMIUM SOTIB OLINDI!</b>

🎉 <b>Tabriklaymiz!</b>

💎 <b>Paket:</b> {pkg['display']}
📅 <b>Muddat:</b> {pkg['months']} oy
⏰ <b>Tugatish:</b> {premium_until}
💰 <b>Hisob:</b> {amount:,.0f} so'm

<b>Endi siz barcha premium xususiyatlardan foydalanishingiz mumkin!</b>
        """
    else:
        pkg = STARS_PRICES[product_id]
        c.execute("UPDATE users SET stars=stars+? WHERE user_id=?", (pkg['count'], user_id))
        success_text = f"""
✅ <b>STARS SOTIB OLINDI!</b>

🎉 <b>Tabriklaymiz!</b>

⭐ <b>Paket:</b> {pkg['display']}
📦 <b>Miqdori:</b> {pkg['count']} ta
💰 <b>Hisob:</b> {amount:,.0f} so'm

<b>Stars balansingizga qo'shildi va endi foydalanishingiz mumkin!</b>
        """
    
    conn.commit()
    conn.close()
    
    bot.answer_callback_query(call.id, "✅ To'lov muvaffaqiyatli! Mahsulot balansingizga qo'shildi!", show_alert=True)
    bot.edit_message_text(success_text, call.message.chat.id, call.message.message_id, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("topup_card"))
def topup_card(call):
