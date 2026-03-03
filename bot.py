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
ADMIN_USERNAME = '@IDD_ADMINN'
CARD_NUMBER = '9860080195351079'
CARD_HOLDER = 'Nargiza Karshiyeva'
BOT_USERNAME = '@PREMIUM_STARSS_1BOT'

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

# ------------------- DB FUNKSIYALARI -------------------
def init_db():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users(
                 user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
                 balance REAL DEFAULT 0, referrals INTEGER DEFAULT 0,
                 referred_by INTEGER, is_premium INTEGER DEFAULT 0,
                 premium_until TEXT, stars REAL DEFAULT 0,
                 total_earned REAL DEFAULT 0, referral_income REAL DEFAULT 0,
                 join_date TEXT, last_active TEXT, is_banned INTEGER DEFAULT 0,
                 is_required_premium INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS orders(
                 order_id TEXT PRIMARY KEY, user_id INTEGER,
                 product_type TEXT, product_id TEXT, amount REAL,
                 status TEXT, payment_method TEXT, created_at TEXT, completed_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS admin_settings(
                 setting_id INTEGER PRIMARY KEY, card_number TEXT, card_holder TEXT,
                 min_topup REAL DEFAULT 5000, max_topup REAL DEFAULT 1000000,
                 ref_commission REAL DEFAULT 500, premium_commission REAL DEFAULT 10,
                 stars_commission REAL DEFAULT 5, topup_commission REAL DEFAULT 0,
                 required_subscription INTEGER DEFAULT 0, subscription_channel TEXT,
                 subscription_price REAL DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS referral_history(
                 referral_id TEXT PRIMARY KEY, referrer_id INTEGER, 
                 referred_user_id INTEGER, bonus_amount REAL, created_at TEXT)''')
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
        c.execute("INSERT INTO admin_settings(setting_id, card_number, card_holder) VALUES(1, ?, ?)", (CARD_NUMBER, CARD_HOLDER))
        conn.commit()
        conn.close()
        return get_admin_settings()
    return settings

def update_admin_setting(key, val):
    conn = sqlite3.connect('bot_data.db')
    conn.execute(f"UPDATE admin_settings SET {key}=? WHERE setting_id=1", (val,))
    conn.commit()
    conn.close()

def get_user_data(user_id):
    conn = sqlite3.connect('bot_data.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

# ------------------- YORDAMCHI FUNKSIYALAR -------------------
def is_subscribed(user_id, channel_url):
    if not channel_url: return True
    try:
        channel_user = channel_url.replace('https://t.me/', '@')
        member = bot.get_chat_member(chat_id=channel_user, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except: return False

def check_premium_expiry(user_id):
    user = get_user_data(user_id)
    if user and user[6] == 1 and user[7]:
        expiry_date = datetime.strptime(user[7], "%Y-%m-%d %H:%M:%S")
        if datetime.now() > expiry_date:
            conn = sqlite3.connect('bot_data.db')
            conn.execute("UPDATE users SET is_premium=0, premium_until=NULL WHERE user_id=?", (user_id,))
            conn.commit()
            conn.close()
            return False
        return True
    return False

# ------------------- KLAVIATURALAR -------------------
def main_menu_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("💎 Premium", "🌟 Stars", "📦 Paketlar", "💰 Balans", "👥 Pul ishlash", "❓ Yordam", "♻️ Hisob to'ldirish")
    if user_id == ADMIN_ID: markup.add("⚙️ Admin Panel")
    return markup

def payment_method_markup(order_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Karta orqali", callback_data=f"pay_card_{order_id}"))
    markup.add(types.InlineKeyboardButton("💰 Balansdan", callback_data=f"pay_balance_{order_id}"))
    markup.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data=f"cancel_order_{order_id}"))
    return markup

# ------------------- MIDDLEWARE -------------------
@bot.message_handler(func=lambda m: True)
def middleware(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    
    if user and user[13] == 1:
        bot.send_message(user_id, "🚫 Siz bloklangansiz.")
        return

    # Premium muddatini tekshirish
    check_premium_expiry(user_id)

    if message.text and message.text.startswith('/start'):
        return start(message)

    settings = get_admin_settings()
    if settings[9] == 1 and not is_subscribed(user_id, settings[10]):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💎 Obuna bo'lish", url=settings[10]))
        bot.send_message(user_id, "🔒 Botdan foydalanish uchun kanalga obuna bo'ling.", reply_markup=markup)
        return

    # Router
    text = message.text
    if text == "💎 Premium": premium_handler(message)
    elif text == "🌟 Stars": stars_handler(message)
    elif text == "📦 Paketlar": packages_handler(message)
    elif text == "💰 Balans": balance_handler(message)
    elif text == "👥 Pul ishlash": earn_handler(message)
    elif text == "❓ Yordam": help_handler(message)
    elif text == "♻️ Hisob to'ldirish": topup_handler(message)
    elif text == "⚙️ Admin Panel": admin_panel(message)
    elif text == "📊 Statistika": admin_stats(message)
    elif text == "⚙️ Sozlamalar": admin_settings(message)
    elif text == "📧 Xabar yuborish": broadcast_message(message)
    elif text == "📈 Daromad": revenue_report(message)
    elif text == "🔐 Majburiy Obuna": required_subscription_handler(message)
    elif text == "🔙 Orqaga": admin_back(message)

# ------------------- ASOSIY HANDLERLAR -------------------
def start(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    if not user:
        ref_id = None
        args = message.text.split()
        if len(args) > 1 and args[1].isdigit(): ref_id = int(args[1])
        
        conn = sqlite3.connect('bot_data.db')
        conn.execute("INSERT INTO users(user_id, username, first_name, referred_by, join_date, last_active) VALUES(?,?,?,?,?,?)",
                     (user_id, message.from_user.username, message.from_user.first_name, ref_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        if ref_id and ref_id != user_id:
            settings = get_admin_settings()
            bonus = settings[5]
            conn.execute("UPDATE users SET balance=balance+?, referral_income=referral_income+?, referrals=referrals+1 WHERE user_id=?", (bonus, bonus, ref_id))
            conn.execute("INSERT INTO referral_history VALUES(?,?,?,?,?)", (str(uuid.uuid4())[:8], ref_id, user_id, bonus, datetime.now().strftime("%Y-%m-%d")))
            bot.send_message(ref_id, f"🎉 Yangi referal! +{bonus:,.0f} so'm.")
        conn.commit()
        conn.close()

    bot.send_message(user_id, "👋 Xush kelibsiz!", reply_markup=main_menu_keyboard(user_id))

def balance_handler(message):
    user = get_user_data(message.from_user.id)
    premium_text = "❌ Faol emas"
    if user[6] == 1:
        premium_text = f"✅ Faol (Tugash: {user[7]})"
    
    text = (f"👤 <b>Foydalanuvchi:</b> {message.from_user.first_name}\n"
            f"💰 <b>Balans:</b> {user[3]:,.0f} so'm\n"
            f"⭐ <b>Stars:</b> {user[8]:,.0f}\n"
            f"💎 <b>Premium:</b> {premium_text}\n"
            f"👥 <b>Referallar:</b> {user[5]} ta")
    bot.send_message(message.chat.id, text, parse_mode="HTML")

def premium_handler(message):
    markup = types.InlineKeyboardMarkup()
    for k, v in PREMIUM_PRICES.items():
        markup.add(types.InlineKeyboardButton(f"{v['display']} - {v['price']:,} so'm", callback_data=f"buy_premium_{k}"))
    bot.send_message(message.chat.id, "💎 Premium paket tanlang:", reply_markup=markup)

def stars_handler(message):
    markup = types.InlineKeyboardMarkup()
    for k, v in STARS_PRICES.items():
        markup.add(types.InlineKeyboardButton(f"{v['display']} - {v['price']:,} so'm", callback_data=f"buy_stars_{k}"))
    bot.send_message(message.chat.id, "🌟 Stars paket tanlang:", reply_markup=markup)

# ------------------- CALLBACK & BUYURTMA -------------------
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    uid = call.from_user.id
    data = call.data

    if data.startswith("buy_premium_"):
        pid = data.replace("buy_premium_", "")
        pkg = PREMIUM_PRICES[pid]
        oid = str(uuid.uuid4())[:8]
        save_order(oid, uid, 'premium', pid, pkg['price'])
        bot.edit_message_text(f"💎 {pkg['display']}\nTo'lov usulini tanlang:", call.message.chat.id, call.message.message_id, reply_markup=payment_method_markup(oid))

    elif data.startswith("buy_stars_"):
        pid = data.replace("buy_stars_", "")
        pkg = STARS_PRICES[pid]
        oid = str(uuid.uuid4())[:8]
        save_order(oid, uid, 'stars', pid, pkg['price'])
        bot.edit_message_text(f"🌟 {pkg['display']}\nTo'lov usulini tanlang:", call.message.chat.id, call.message.message_id, reply_markup=payment_method_markup(oid))

    elif data.startswith("pay_balance_"):
        oid = data.replace("pay_balance_", "")
        process_balance_payment(call, oid)

    elif data.startswith("pay_card_"):
        oid = data.replace("pay_card_", "")
        settings = get_admin_settings()
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ To'lov qildim", callback_data=f"req_admin_{oid}"))
        bot.edit_message_text(f"💳 Karta: <code>{settings[1]}</code>\n👤 {settings[2]}\n\nTo'lovdan so'ng tugmani bosing.", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="HTML")

    elif data.startswith("req_admin_"):
        oid = data.replace("req_admin_", "")
        bot.answer_callback_query(call.id, "Adminga yuborildi.")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"adm_ok_{oid}"),
                   types.InlineKeyboardButton("❌ Rad etish", callback_data=f"adm_no_{oid}"))
        bot.send_message(ADMIN_ID, f"🔔 Yangi to'lov (Karta)\nID: {oid}\nUser: {uid}", reply_markup=markup)

    elif data.startswith("adm_ok_"):
        complete_order(data.replace("adm_ok_", ""))
        bot.delete_message(call.message.chat.id, call.message.message_id)

    elif data.startswith("adm_no_"):
        oid = data.replace("adm_no_", "")
        bot.send_message(ADMIN_ID, f"❌ Buyurtma #{oid} rad etildi.")
        bot.delete_message(call.message.chat.id, call.message.message_id)

def save_order(oid, uid, ptype, pid, am):
    conn = sqlite3.connect('bot_data.db')
    conn.execute("INSERT INTO orders (order_id, user_id, product_type, product_id, amount, status, created_at) VALUES (?,?,?,?,?,?,?)",
                 (oid, uid, ptype, pid, am, 'pending', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def process_balance_payment(call, oid):
    uid = call.from_user.id
    conn = sqlite3.connect('bot_data.db')
    order = conn.execute("SELECT amount FROM orders WHERE order_id=?", (oid,)).fetchone()
    user = conn.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
    
    if user[0] >= order[0]:
        conn.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (order[0], uid))
        conn.commit()
        conn.close()
        complete_order(oid)
        bot.answer_callback_query(call.id, "✅ Muvaffaqiyatli to'landi!")
    else:
        bot.answer_callback_query(call.id, "❌ Mablag' yetarli emas!", show_alert=True)
        conn.close()

def complete_order(oid):
    conn = sqlite3.connect('bot_data.db')
    order = conn.execute("SELECT user_id, product_type, product_id, amount FROM orders WHERE order_id=?", (oid,)).fetchone()
    if not order: return
    
    uid, ptype, pid, am = order
    user = conn.execute("SELECT is_premium, premium_until FROM users WHERE user_id=?", (uid,)).fetchone()
    
    if ptype == 'premium':
        months = PREMIUM_PRICES[pid]['months']
        # Agar allaqachon premium bo'lsa, muddatni ustiga qo'shish
        current_expiry = datetime.now()
        if user[0] == 1 and user[1]:
            try:
                db_expiry = datetime.strptime(user[1], "%Y-%m-%d %H:%M:%S")
                if db_expiry > current_expiry: current_expiry = db_expiry
            except: pass
        
        new_expiry = current_expiry + timedelta(days=30 * months)
        conn.execute("UPDATE users SET is_premium=1, premium_until=? WHERE user_id=?", (new_expiry.strftime("%Y-%m-%d %H:%M:%S"), uid))
        
    elif ptype == 'stars':
        count = STARS_PRICES[pid]['count']
        conn.execute("UPDATE users SET stars=stars+? WHERE user_id=?", (count, uid))
    
    elif ptype == 'topup':
        conn.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (am, uid))

    conn.execute("UPDATE orders SET status='completed', completed_at=? WHERE order_id=?", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), oid))
    conn.commit()
    conn.close()
    bot.send_message(uid, f"✅ Buyurtmangiz #{oid} muvaffaqiyatli bajarildi!")

# ------------------- ADMIN FUNKSIYALAR -------------------
def admin_panel(message):
    if message.from_user.id != ADMIN_ID: return
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📊 Statistika", "⚙️ Sozlamalar", "📧 Xabar yuborish", "📈 Daromad", "🔐 Majburiy Obuna", "🔙 Orqaga")
    bot.send_message(ADMIN_ID, "Admin Panel", reply_markup=markup)

def admin_stats(message):
    conn = sqlite3.connect('bot_data.db')
    u = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    p = conn.execute("SELECT COUNT(*) FROM users WHERE is_premium=1").fetchone()[0]
    bot.send_message(ADMIN_ID, f"👥 Foydalanuvchilar: {u}\n💎 Premiumlar: {p}")
    conn.close()

def revenue_report(message):
    conn = sqlite3.connect('bot_data.db')
    rev = conn.execute("SELECT SUM(amount) FROM orders WHERE status='completed'").fetchone()[0] or 0
    bot.send_message(ADMIN_ID, f"💰 Jami daromad: {rev:,.0f} so'm")
    conn.close()

def admin_back(message):
    bot.send_message(ADMIN_ID, "Menyu", reply_markup=main_menu_keyboard(ADMIN_ID))

def broadcast_message(message):
    bot.send_message(ADMIN_ID, "Xabar matnini kiriting:")
    bot.register_next_step_handler(message, send_all)

def send_all(message):
    conn = sqlite3.connect('bot_data.db')
    users = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()
    for u in users:
        try: bot.send_message(u[0], message.text)
        except: continue
    bot.send_message(ADMIN_ID, "Yuborildi.")

# ------------------- RUN -------------------
def run_flask(): app.run(host='0.0.0.0', port=8080)

if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    while True:
        try: import os

if __name__ == "__main__":
    # Render portni avtomatik taqdim etadi, biz shuni ishlatamiz
    port = int(os.environ.get("PORT", 5000))
    # Flask (veb-server)ni alohida oqimda ishga tushiramiz
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port)).start()
    # Botni cheksiz kutish (infinity_polling) rejimida ishga tushiramiz
    bot.infinity_polling()

        except Exception as e:
            logging.error(e)
            time.sleep(5)
