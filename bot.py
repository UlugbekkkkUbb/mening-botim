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
import re

# ------------------- KONFIGURATSIYA -------------------
API_TOKEN = '8305687409:AAF4-xPc-lwMyJQHcvEFNKxn_nrpWVHBC80'
ADMIN_ID = 7666979987
ADMIN_USERNAME = 'IDD_ADMINN'
CARD_NUMBER = '9860080195351079'
CARD_HOLDER = 'Nargiza Karshiyeva'
BOT_USERNAME = 'bot_username'

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

# ------------------- NARXLAR -------------------
PREMIUM_PRICES = {
    '1_month': {'months': 1, 'price': 50000, 'display': '1 Oylik Premium'},
    '3_months': {'months': 3, 'price': 180000, 'display': '3 Oylik Premium'},
    '6_months': {'months': 6, 'price': 230000, 'display': '6 Oylik Premium'},
    '12_months': {'months': 12, 'price': 290000, 'display': '12 Oylik Premium'}
}

STARS_PRICES = {
    '50_stars': {'count': 50, 'price': 15000, 'display': '50 ⭐ Stars'},
    '75_stars': {'count': 75, 'price': 21000, 'display': '75 ⭐ Stars'},
    '100_stars': {'count': 100, 'price': 28000, 'display': '100 ⭐ Stars'},
    '150_stars': {'count': 150, 'price': 40000, 'display': '150 ⭐ Stars'},
    '250_stars': {'count': 250, 'price': 65000, 'display': '250 ⭐ Stars'},
    '350_stars': {'count': 350, 'price': 95000, 'display': '350 ⭐ Stars'},
    '500_stars': {'count': 500, 'price': 135000, 'display': '500 ⭐ Stars'},
    '750_stars': {'count': 750, 'price': 190000, 'display': '750 ⭐ Stars'},
    '1000_stars': {'count': 1000, 'price': 265000, 'display': '1000 ⭐ Stars'},
    '1500_stars': {'count': 1500, 'price': 365000, 'display': '1500 ⭐ Stars'},
    '2500_stars': {'count': 2500, 'price': 590000, 'display': '2500 ⭐ Stars'}
}

# ------------------- MA'LUMOTLAR BAZASI -------------------
def get_db_connection():
    return sqlite3.connect('bot_data.db', check_same_thread=False, timeout=20)

def init_db():
    conn = get_db_connection()
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
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM admin_settings WHERE setting_id=1")
    settings = c.fetchone()
    conn.close()
    if not settings:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("""INSERT INTO admin_settings(setting_id, card_number, card_holder, min_topup, max_topup, ref_commission, premium_commission, stars_commission, topup_commission, required_subscription, subscription_channel, subscription_price)
                     VALUES(1, ?, ?, 5000, 1000000, 500, 10, 5, 0, 0, '', 0)""", (CARD_NUMBER, CARD_HOLDER))
        conn.commit()
        conn.close()
        return (1, CARD_NUMBER, CARD_HOLDER, 5000, 1000000, 500, 10, 5, 0, 0, '', 0)
    return settings

def update_admin_setting(setting_key, value):
    conn = get_db_connection()
    c = conn.cursor()
    update_query = f"UPDATE admin_settings SET {setting_key}=? WHERE setting_id=1"
    c.execute(update_query, (value,))
    conn.commit()
    conn.close()

def get_user_data(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def create_user(user_id, username, first_name, referred_by=None):
    conn = get_db_connection()
    c = conn.cursor()
    settings = get_admin_settings()
    required_premium = settings[9]
    c.execute("""INSERT INTO users(user_id, username, first_name, referred_by, join_date, last_active, is_required_premium)
                 VALUES(?, ?, ?, ?, ?, ?, ?)""",
              (user_id, username, first_name, referred_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), required_premium))
    conn.commit()
    conn.close()

def add_referral_bonus(referrer_id, referred_user_id, bonus_amount):
    conn = get_db_connection()
    c = conn.cursor()
    referral_id = str(uuid.uuid4())[:12]
    c.execute("""INSERT INTO referral_history(referral_id, referrer_id, referred_user_id, bonus_amount, created_at)
                 VALUES(?, ?, ?, ?, ?)""",
              (referral_id, referrer_id, referred_user_id, bonus_amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    c.execute("UPDATE users SET balance=balance+?, referral_income=referral_income+?, referrals=referrals+1 WHERE user_id=?",
              (bonus_amount, bonus_amount, referrer_id))
    conn.commit()
    conn.close()

# ------------------- OBUNANI TEKSHIRISH -------------------
def is_subscribed(user_id, channel_username):
    try:
        if channel_username.startswith('https://t.me/'):
            channel_username = channel_username.replace('https://t.me/', '')
        if not channel_username.startswith('@'):
            channel_username = '@' + channel_username
        member = bot.get_chat_member(chat_id=channel_username, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"Subscription check error: {e}")
        return False

# ------------------- KLAVIATURALAR -------------------
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
    settings = get_admin_settings()
    if settings[9] == 1:
        channel = settings[10]
        if channel:
            return is_subscribed(user_id, channel)
    return True

# ------------------- HANDLERLAR -------------------
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
                    f"👤 Jami referallar: {ref_user[5] + 1}\n", 
                    parse_mode="HTML")
        user = get_user_data(user_id)
    
    settings = get_admin_settings()
    if settings[9]:
        if not check_required_subscription(user_id):
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("💎 Obuna bo'lish", url=settings[10]))
            bot.send_message(user_id, "🔒 <b>MAJBURIY OBUNA</b>\n\nBotdan foydalanish uchun kanalga obuna bo'ling.", parse_mode="HTML", reply_markup=markup)
            return
    
    bot.send_message(user_id, "<b>👋 Assalomu alaykum!</b>\n\n🤖 Botga xush kelibsiz!", parse_mode="HTML", reply_markup=main_menu_keyboard(user_id))

@bot.message_handler(func=lambda m: m.text == "💎 Premium")
def premium_handler(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    if not check_required_subscription(user_id):
        return
    bot.send_message(user_id, "<b>💎 PREMIUM PAKETLARINI TANLANG</b>", parse_mode="HTML", reply_markup=premium_inline_markup())

@bot.message_handler(func=lambda m: m.text == "🌟 Stars")
def stars_handler(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    if not check_required_subscription(user_id):
        return
    bot.send_message(user_id, f"<b>⭐ TELEGRAM STARS SOTIB OLING</b>\n\nStars: {user[8]:,.0f} ⭐", parse_mode="HTML", reply_markup=stars_inline_markup())

@bot.message_handler(func=lambda m: m.text == "💰 Balans")
def balance_handler(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    text = f"<b>💰 BALANS:</b> {user[3]:,.0f} so'm\n<b>⭐ STARS:</b> {user[8]:,.0f} ta"
    bot.send_message(user_id, text, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "👥 Pul ishlash")
def earn_handler(message):
    user_id = message.from_user.id
    bot_name = bot.get_me().username
    ref_link = f"https://t.me/{bot_name}?start={user_id}"
    bot.send_message(user_id, f"<b>🔗 Referal havolangiz:</b>\n<code>{ref_link}</code>", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "♻️ Hisob to'ldirish")
def topup_handler(message):
    user_id = message.from_user.id
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Karta orqali to'lov", callback_data="topup_card"))
    bot.send_message(user_id, "<b>🏦 To'lov usulini tanlang:</b>", parse_mode="HTML", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Panel" and m.from_user.id == ADMIN_ID)
def admin_panel(message):
    bot.send_message(message.from_user.id, "<b>⚙️ ADMIN PANEL</b>", parse_mode="HTML", reply_markup=admin_panel_markup())

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_premium_"))
def buy_premium(call):
    product_id = call.data.replace("buy_premium_", "")
    pkg = PREMIUM_PRICES[product_id]
    order_id = str(uuid.uuid4())[:12]
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO orders(order_id, user_id, product_type, product_id, amount, status, created_at) VALUES(?,?,?,?,?,?,?)",
              (order_id, call.from_user.id, 'premium', product_id, pkg['price'], 'pending', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    bot.edit_message_text(f"📦 {pkg['display']}\n💰 Narxi: {pkg['price']:,} so'm", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=payment_method_markup(order_id))

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_card_"))
def pay_card(call):
    order_id = call.data.replace("pay_card_", "")
    settings = get_admin_settings()
    text = f"💳 Karta: <code>{settings[1]}</code>\n👤 Egasi: {settings[2]}\n🆔 Buyurtma: {order_id}"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ To'lov qildim", callback_data=f"confirm_payment_{order_id}"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_payment_"))
def confirm_payment(call):
    order_id = call.data.replace("confirm_payment_", "")
    bot.send_message(ADMIN_ID, f"🔔 Yangi to'lov: {order_id}\nTasdiqlash: /admin_confirm {order_id}")
    bot.answer_callback_query(call.id, "✅ Adminga xabar yuborildi.")

@bot.message_handler(commands=['admin_confirm'])
def admin_confirm(message):
    if message.from_user.id != ADMIN_ID: return
    order_id = message.text.split()[1]
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT user_id, amount FROM orders WHERE order_id=?", (order_id,))
    order = c.fetchone()
    if order:
        c.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (order[1], order[0]))
        c.execute("UPDATE orders SET status='completed' WHERE order_id=?", (order_id,))
        conn.commit()
        bot.send_message(order[0], "✅ Hisobingiz to'ldirildi!")
    conn.close()

# ------------------- FLASK VA ISHGA TUSHIRISH -------------------
@app.route('/')
def home(): return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    while True:
        try:
            bot.infinity_polling()
        except Exception as e:
            time.sleep(5)

