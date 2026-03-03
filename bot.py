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

# ------------------- MAHSULOTLAR VA NARXLAR -------------------
PREMIUM_PRICES = {
    '1_month': {'months': 1, 'price': 50000, 'display': '💎 1 Oylik Premium'},
    '3_months': {'months': 3, 'price': 180000, 'display': '💎 3 Oylik Premium'},
    '6_months': {'months': 6, 'price': 230000, 'display': '💎 6 Oylik Premium'},
    '12_months': {'months': 12, 'price': 290000, 'display': '💎 12 Oylik Premium'}
}

STARS_PRICES = {
    '50_stars': {'count': 50, 'price': 15000, 'display': '🌟 50 Telegram Stars'},
    '75_stars': {'count': 75, 'price': 21000, 'display': '🌟 75 Telegram Stars'},
    '100_stars': {'count': 100, 'price': 28000, 'display': '🌟 100 Telegram Stars'},
    '250_stars': {'count': 250, 'price': 65000, 'display': '🌟 250 Telegram Stars'},
    '500_stars': {'count': 500, 'price': 135000, 'display': '🌟 500 Telegram Stars'},
    '1000_stars': {'count': 1000, 'price': 265000, 'display': '🌟 1000 Telegram Stars'}
}

# ------------------- MA'LUMOTLAR BAZASI -------------------
def init_db():
    conn = sqlite3.connect('bot_data.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users(
                 user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
                 balance REAL DEFAULT 0, referrals INTEGER DEFAULT 0,
                 referred_by INTEGER, is_premium INTEGER DEFAULT 0,
                 premium_until TEXT, stars REAL DEFAULT 0,
                 is_banned INTEGER DEFAULT 0, join_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS orders(
                 order_id TEXT PRIMARY KEY, user_id INTEGER,
                 product_type TEXT, product_id TEXT, amount REAL,
                 status TEXT, created_at TEXT)''')
    conn.commit()
    conn.close()

init_db()

def get_user_data(user_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

# ------------------- KLAVIATURALAR -------------------
def main_menu_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("💎 Premium"), types.KeyboardButton("🌟 Stars"),
        types.KeyboardButton("💰 Balans"), types.KeyboardButton("👥 Pul ishlash"),
        types.KeyboardButton("♻️ Hisob to'ldirish"), types.KeyboardButton("❓ Yordam")
    )
    if user_id == ADMIN_ID:
        markup.add(types.KeyboardButton("⚙️ Admin Panel"))
    return markup

# ------------------- ASOSIY FUNKSIYALAR -------------------
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    user = get_user_data(user_id)
    
    if not user:
        referred_by = None
        args = message.text.split()
        if len(args) > 1 and args[1].isdigit():
            referred_by = int(args[1])
        
        conn = sqlite3.connect('bot_data.db')
        conn.execute("INSERT INTO users(user_id, username, first_name, referred_by, join_date) VALUES(?,?,?,?,?)",
                     (user_id, message.from_user.username, message.from_user.first_name, referred_by, datetime.now().strftime("%Y-%m-%d")))
        
        if referred_by and referred_by != user_id:
            conn.execute("UPDATE users SET balance = balance + 500, referrals = referrals + 1 WHERE user_id = ?", (referred_by,))
            bot.send_message(referred_by, f"🎊 *Yangi do'st!* Siz taklif qilgan foydalanuvchi botga kirdi va balansingizga *500 so'm* qo'shildi!", parse_mode="Markdown")
        conn.commit()
        conn.close()

    welcome_text = (
        f"👋 *Assalomu alaykum, {message.from_user.first_name}!*\n\n"
        f"🌟 *PREMIUM STARS* botiga xush kelibsiz!\n\n"
        f"Bu yerda siz eng arzon narxlarda:\n"
        f"🔹 *Telegram Premium* (1, 3, 6, 12 oy)\n"
        f"🔹 *Telegram Stars* (Yulduzchalar)\n"
        f"sotib olishingiz yoki do'stlaringizni taklif qilib *pul ishlashingiz* mumkin! 💸\n\n"
        f"👇 Kerakli bo'limni tanlang:"
    )
    bot.send_message(user_id, welcome_text, reply_markup=main_menu_keyboard(user_id), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "💰 Balans")
def balance_info(message):
    user = get_user_data(message.from_user.id)
    status = "💎 Faol" if user[6] == 1 else "❌ Faol emas"
    expiry = f"\n📅 Tugash muddati: `{user[7]}`" if user[7] else ""
    
    text = (
        f"👤 *Sizning hisobingiz:*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 *Asosiy balans:* `{user[3]:,.0f} so'm`\n"
        f"🌟 *Yulduzchalar:* `{user[8]:,.0f} ⭐`\n"
        f"👥 *Referallar:* `{user[4]} ta`\n"
        f"💎 *Premium holati:* {status}{expiry}\n"
        f"━━━━━━━━━━━━━━━"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "💎 Premium")
def premium_menu(message):
    markup = types.InlineKeyboardMarkup()
    for key, val in PREMIUM_PRICES.items():
        markup.add(types.InlineKeyboardButton(f"{val['display']} — {val['price']:,} so'm", callback_data=f"buy_premium_{key}"))
    
    text = (
        f"💎 *Telegram Premium afzalliklari:*\n\n"
        f"✅ Ikki baravar ko'p limitlar\n"
        f"✅ Tez yuklab olish hujjati\n"
        f"✅ Ovozli xabarlarni matnga aylantirish\n"
        f"✅ Reklamasiz Telegram va boshqalar!\n\n"
        f"👇 *Paketni tanlang:*"
    )
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🌟 Stars")
def stars_menu(message):
    markup = types.InlineKeyboardMarkup()
    for key, val in STARS_PRICES.items():
        markup.add(types.InlineKeyboardButton(f"{val['display']} — {val['price']:,} so'm", callback_data=f"buy_stars_{key}"))
    
    text = (
        f"🌟 *Telegram Stars nima?*\n\n"
        f"Bu Telegram ichidagi raqamli to'lov birligi bo'lib, ular orqali botlar va mini-applarda xaridlar qilish mumkin.\n\n"
        f"👇 *Kerakli miqdorni tanlang:*"
    )
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "👥 Pul ishlash")
def referral_menu(message):
    user_id = message.from_user.id
    ref_link = f"https://t.me/{BOT_USERNAME[1:]}?start={user_id}"
    text = (
        f"👥 *Do'stlarni taklif qiling va pul ishlang!*\n\n"
        f"Har bir faol taklif qilgan do'stingiz uchun sizga *500 so'm* beriladi!\n\n"
        f"🔗 *Sizning havolaingiz:*\n`{ref_link}`\n\n"
        f"🎁 Havolani do'stlaringizga yuboring va daromad olishni boshlang!"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ------------------- TO'LOV VA ADMIN TASDIQLASH -------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def handle_purchase(call):
    user_id = call.from_user.id
    data = call.data.split('_')
    p_type = data[1] # premium yoki stars
    p_id = "_".join(data[2:])
    
    if p_type == 'premium':
        item = PREMIUM_PRICES[p_id]
    else:
        item = STARS_PRICES[p_id]
        
    order_id = str(uuid.uuid4())[:8].upper()
    
    # Buyurtmani bazaga yozish
    conn = sqlite3.connect('bot_data.db')
    conn.execute("INSERT INTO orders VALUES(?,?,?,?,?,?,?)", 
                 (order_id, user_id, p_type, p_id, item['price'], 'pending', datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    
    payment_text = (
        f"💳 *To'lov ma'lumotlari:*\n\n"
        f"📦 *Mahsulot:* {item['display']}\n"
        f"💰 *Narxi:* `{item['price']:,} so'm`\n"
        f"🆔 *Buyurtma ID:* `{order_id}`\n\n"
        f"💳 *Karta raqami:* `{CARD_NUMBER}`\n"
        f"👤 *Karta egasi:* {CARD_HOLDER}\n\n"
        f"⚠️ *Muhim:* To'lovni amalga oshirgach, chekni (skrinshot) saqlab qo'ying va quyidagi tugmani bosing!"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ To'lovni qildim", callback_data=f"confirm_{order_id}"))
    bot.edit_message_text(payment_text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_'))
def notify_admin(call):
    order_id = call.data.split('_')[1]
    bot.answer_callback_query(call.id, "✅ So'rovingiz adminga yuborildi. Kuting!", show_alert=True)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"adm_ok_{order_id}"),
        types.InlineKeyboardButton("❌ Rad etish", callback_data=f"adm_no_{order_id}")
    )
    
    bot.send_message(ADMIN_ID, f"🔔 *Yangi buyurtma!*\n\nID: `{order_id}`\nUser: {call.from_user.id}\nUsername: @{call.from_user.username}", reply_markup=markup, parse_mode="Markdown")
    bot.edit_message_text("⏳ *Sizning to'lovingiz admin tomonidan tekshirilmoqda...*", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_'))
def admin_action(call):
    data = call.data.split('_')
    action = data[1] # ok yoki no
    order_id = data[2]
    
    conn = sqlite3.connect('bot_data.db')
    order = conn.execute("SELECT user_id, product_type, product_id, amount FROM orders WHERE order_id=?", (order_id,)).fetchone()
    
    if order:
        uid, p_type, p_id, amount = order
        if action == 'ok':
            if p_type == 'premium':
                months = PREMIUM_PRICES[p_id]['months']
                expiry = (datetime.now() + timedelta(days=30*months)).strftime("%Y-%m-%d")
                conn.execute("UPDATE users SET is_premium=1, premium_until=? WHERE user_id=?", (expiry, uid))
                bot.send_message(uid, f"🎉 *Tabriklaymiz!* Sizning *{months} oylik Premium* obunangiz faollashtirildi!", parse_mode="Markdown")
            else:
                stars_count = STARS_PRICES[p_id]['count']
                conn.execute("UPDATE users SET stars = stars + ? WHERE user_id=?", (stars_count, uid))
                bot.send_message(uid, f"🎉 *Muvaffaqiyatli!* Hisobingizga *{stars_count} ⭐ Stars* qo'shildi!", parse_mode="Markdown")
            
            conn.execute("UPDATE orders SET status='completed' WHERE order_id=?", (order_id,))
            bot.edit_message_text(f"✅ Buyurtma #{order_id} tasdiqlandi!", call.message.chat.id, call.message.message_id)
        else:
            bot.send_message(uid, f"❌ *Kechirasiz!* Sizning #{order_id} buyurtmangiz rad etildi. Muammo bo'lsa adminga murojaat qiling.", parse_mode="Markdown")
            bot.edit_message_text(f"❌ Buyurtma #{order_id} rad etildi!", call.message.chat.id, call.message.message_id)
            
    conn.commit()
    conn.close()

# ------------------- SERVER VA ISHGA TUSHIRISH -------------------
@app.route('/')
def home():
    return "Bot status: Running"

if __name__ == "__main__":
    # Render portni taqdim etadi
    port = int(os.environ.get("PORT", 5000))
    # Flaskni alohida oqimda ishga tushirish (Render o'chib qolmasligi uchun)
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port)).start()
    
    while True:
        try:
            logging.info("Bot ishga tushmoqda...")
            bot.infinity_polling(timeout=15, long_polling_timeout=5)
        except Exception as e:
            logging.error(f"Kutilmagan xato: {e}")
            time.sleep(5)
