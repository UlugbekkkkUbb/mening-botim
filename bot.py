import telebot
from telebot import types
import sqlite3
import os
import json
import logging
import threading
from datetime import datetime, timedelta
from flask import Flask
import uuid
import time
import re
import random

# ------------------- KONFIGURATSIYA (Batafsil) -------------------
API_TOKEN = '8305687409:AAF4-xPc-lwMyJQHcvEFNKxn_nrpWVHBC80'
ADMIN_ID = 7666979987
ADMIN_USERNAME = '@IDD_ADMINN'
CARD_NUMBER = '9860080195351079'
CARD_HOLDER = 'Nargiza Karshiyeva'
BOT_USERNAME = '@PREMIUM_STARSS_1BOT'
CHANNEL_LINK = "https://t.me/your_channel" # Majburiy obuna bo'lsa

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s'
)

# ------------------- NARXNAVOSI (Kengaytirilgan) -------------------
PREMIUM_DATA = {
    '1_month': {'m': 1, 'p': 50000, 'n': '💎 1 Oylik Telegram Premium', 'd': '30 kunlik cheksiz imkoniyatlar.'},
    '3_months': {'m': 3, 'p': 145000, 'n': '💎 3 Oylik Telegram Premium', 'd': '90 kunlik chegirmali paket.'},
    '6_months': {'m': 6, 'p': 230000, 'n': '💎 6 Oylik Telegram Premium', 'd': '180 kunlik professional paket.'},
    '12_months': {'m': 12, 'p': 350000, 'n': '💎 12 Oylik Telegram Premium', 'd': '365 kunlik maksimal tejamkorlik.'}
}

STARS_DATA = {
    '50': {'c': 50, 'p': 15000}, '75': {'c': 75, 'p': 22000},
    '100': {'c': 100, 'p': 29000}, '250': {'c': 250, 'p': 65000},
    '500': {'c': 500, 'p': 125000}, '1000': {'c': 1000, 'p': 240000},
    '2500': {'c': 2500, 'p': 580000}, '5000': {'c': 5000, 'p': 1100000}
}

# ------------------- MA'LUMOTLAR BAZASI (Professional) -------------------
def get_db():
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    return conn

def init_db():
    with get_db() as conn:
        c = conn.cursor()
        # Foydalanuvchilar jadvali
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            uid INTEGER PRIMARY KEY, 
            uname TEXT, 
            fname TEXT, 
            balance REAL DEFAULT 0, 
            refs INTEGER DEFAULT 0,
            ref_by INTEGER, 
            is_prem INTEGER DEFAULT 0, 
            prem_exp TEXT, 
            stars INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0, 
            joined TEXT)''')
        # Buyurtmalar jadvali
        c.execute('''CREATE TABLE IF NOT EXISTS orders (
            oid TEXT PRIMARY KEY, 
            uid INTEGER, 
            type TEXT, 
            pid TEXT, 
            sum REAL, 
            status TEXT, 
            date TEXT)''')
        # Promo-kodlar jadvali
        c.execute('''CREATE TABLE IF NOT EXISTS promos (
            code TEXT PRIMARY KEY, 
            amount REAL, 
            limit_use INTEGER, 
            used_count INTEGER DEFAULT 0)''')
        conn.commit()

init_db()

# ------------------- DEKORATORLAR VA YORDAMCHI FUNKSIYALAR -------------------
def is_admin(uid):
    return uid == ADMIN_ID

def format_num(num):
    return "{:,}".format(num).replace(",", " ")

# ------------------- KLAVIATURALAR (Vizual) -------------------
def get_main_kb(uid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        types.KeyboardButton("💎 PREMIUM SOTIB OLISH"),
        types.KeyboardButton("🌟 STARS SOTIB OLISH"),
        types.KeyboardButton("👤 PROFILIM"),
        types.KeyboardButton("💸 PUL ISHLASH"),
        types.KeyboardButton("🎁 PROMO-KOD"),
        types.KeyboardButton("📞 ADMIN BILAN ALOQA")
    )
    if is_admin(uid):
        kb.add(types.KeyboardButton("⚙️ ADMIN BOSHQARUV PANELI"))
    return kb

# ------------------- ASOSIY LOGIKA -------------------
@bot.message_handler(commands=['start'])
def welcome(message):
    uid = message.from_user.id
    uname = message.from_user.username
    fname = message.from_user.first_name
    
    with get_db() as conn:
        user = conn.execute("SELECT uid FROM users WHERE uid=?", (uid,)).fetchone()
        if not user:
            ref_id = None
            args = message.text.split()
            if len(args) > 1 and args[1].isdigit():
                ref_id = int(args[1])
                if ref_id != uid:
                    conn.execute("UPDATE users SET balance=balance+500, refs=refs+1 WHERE uid=?", (ref_id,))
                    try: bot.send_message(ref_id, f"➕ *Sizda yangi referal!* Balansingizga 500 so'm qo'shildi.", parse_mode="Markdown")
                    except: pass
            
            conn.execute("INSERT INTO users (uid, uname, fname, ref_by, joined) VALUES (?,?,?,?,?)",
                         (uid, uname, fname, ref_id, datetime.now().strftime("%Y-%m-%d %H:%M")))
            conn.commit()

    welcome_msg = (
        f"👋 *Assalomu alaykum, {fname}!*\n\n"
        f"🤖 *PREMIUM & STARS* rasmiy savdo botiga xush kelibsiz.\n"
        f"Bu yerda siz o'z hisobingizni xavfsiz va tezkor to'ldirishingiz mumkin.\n\n"
        f"💎 *Premium* — Telegramning barcha yopiq funksiyalari.\n"
        f"🌟 *Stars* — Ilovalar va o'yinlar uchun ichki valyuta.\n\n"
        f"👇 *Davom etish uchun menyudan foydalaning:*"
    )
    bot.send_message(uid, welcome_msg, reply_markup=get_main_kb(uid), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "👤 PROFILIM")
def profile(message):
    uid = message.from_user.id
    with get_db() as conn:
        u = conn.execute("SELECT * FROM users WHERE uid=?", (uid,)).fetchone()
    
    status = "💎 Faol" if u[6] == 1 else "❌ Faol emas"
    text = (
        f"👤 *Sizning ma'lumotlaringiz:*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🆔 ID: `{u[0]}`\n"
        f"💰 Balansingiz: *{format_num(u[3])} so'm*\n"
        f"🌟 Stars miqdori: *{u[8]} ⭐*\n"
        f"👥 Takliflar: *{u[4]} ta*\n"
        f"💎 Premium: {status}\n"
        f"📅 Qo'shilgan sana: *{u[10]}*\n"
        f"━━━━━━━━━━━━━━━"
    )
    bot.send_message(uid, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "💎 PREMIUM SOTIB OLISH")
def buy_premium(message):
    mk = types.InlineKeyboardMarkup(row_width=1)
    for k, v in PREMIUM_DATA.items():
        mk.add(types.InlineKeyboardButton(f"{v['n']} — {format_num(v['p'])} so'm", callback_data=f"prm_{k}"))
    bot.send_message(message.chat.id, "🌟 *Telegram Premium paketlaridan birini tanlang:*", reply_markup=mk, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🌟 STARS SOTIB OLISH")
def buy_stars(message):
    mk = types.InlineKeyboardMarkup(row_width=2)
    btns = [types.InlineKeyboardButton(f"{v['c']} ⭐ — {format_num(v['p'])} so'm", callback_data=f"str_{k}") for k, v in STARS_DATA.items()]
    mk.add(*btns)
    bot.send_message(message.chat.id, "✨ *Telegram Stars miqdorini tanlang:*", reply_markup=mk, parse_mode="Markdown")

# ------------------- CALLBACK HANDLERS (Sotuv jarayoni) -------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith(('prm_', 'str_')))
def process_order(call):
    uid = call.from_user.id
    prefix, pid = call.data.split('_')
    
    if prefix == 'prm':
        item = PREMIUM_DATA[pid]
        p_name = item['n']
        price = item['p']
    else:
        item = STARS_DATA[pid]
        p_name = f"{item['c']} Telegram Stars"
        price = item['p']
        
    oid = str(uuid.uuid4())[:12].upper()
    
    with get_db() as conn:
        conn.execute("INSERT INTO orders VALUES (?,?,?,?,?,?,?)",
                     (oid, uid, prefix, pid, price, 'Kutilmoqda', datetime.now().strftime("%H:%M:%S")))
        conn.commit()
    
    pay_text = (
        f"🛒 *Yangi buyurtma shakllandi!*\n\n"
        f"📦 Mahsulot: *{p_name}*\n"
        f"💰 To'lov summasi: *{format_num(price)} so'm*\n"
        f"🆔 Buyurtma ID: `{oid}`\n\n"
        f"💳 To'lov uchun karta: `{CARD_NUMBER}`\n"
        f"👤 Karta egasi: *{CARD_HOLDER}*\n\n"
        f"⚠️ *Diqqat:* To'lovni amalga oshirib, chekni (skrinshot) adminga yuboring yoki quyidagi tugmani bosing."
    )
    
    mk = types.InlineKeyboardMarkup()
    mk.add(types.InlineKeyboardButton("✅ TO'LOV QILDIM", callback_data=f"confirm_{oid}"))
    bot.edit_message_text(pay_text, uid, call.message.message_id, reply_markup=mk, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_'))
def admin_notification(call):
    oid = call.data.split('_')[1]
    bot.answer_callback_query(call.id, "✅ So'rov yuborildi. Admin tekshirmoqda...", show_alert=True)
    
    with get_db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE oid=?", (oid,)).fetchone()
    
    admin_text = (
        f"🔔 *YANGI TO'LOV SO'ROVI!*\n\n"
        f"👤 Foydalanuvchi: {call.from_user.first_name} (@{call.from_user.username})\n"
        f"🆔 User ID: `{call.from_user.id}`\n"
        f"📦 Turi: {order[2].upper()}\n"
        f"💰 Summa: {format_num(order[4])} so'm\n"
        f"🆔 Order ID: `{oid}`"
    )
    
    mk = types.InlineKeyboardMarkup()
    mk.add(
        types.InlineKeyboardButton("✅ TASDIQLASH", callback_data=f"adm_ok_{oid}"),
        types.InlineKeyboardButton("❌ RAD ETISH", callback_data=f"adm_no_{oid}")
    )
    bot.send_message(ADMIN_ID, admin_text, reply_markup=mk, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_'))
def admin_decision(call):
    if not is_admin(call.from_user.id): return
    
    _, action, oid = call.data.split('_')
    with get_db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE oid=?", (oid,)).fetchone()
        if not order: return
        
        uid, o_type, pid, o_sum = order[1], order[2], order[3], order[4]
        
        if action == 'ok':
            if o_type == 'prm':
                days = PREMIUM_DATA[pid]['m'] * 30
                exp_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
                conn.execute("UPDATE users SET is_prem=1, prem_exp=? WHERE uid=?", (exp_date, uid))
                bot.send_message(uid, f"🎉 *Tabriklaymiz!* Telegram Premium muvaffaqiyatli faollashtirildi.\n📅 Muddat: {exp_date} gacha.", parse_mode="Markdown")
            else:
                count = STARS_DATA[pid]['c']
                conn.execute("UPDATE users SET stars=stars+? WHERE uid=?", (count, uid))
                bot.send_message(uid, f"🌟 *Tabriklaymiz!* Hisobingizga {count} Stars qo'shildi!", parse_mode="Markdown")
            
            conn.execute("UPDATE orders SET status='Tasdiqlandi' WHERE oid=?", (oid,))
            bot.edit_message_text(f"✅ Order {oid} bajarildi.", ADMIN_ID, call.message.message_id)
        else:
            bot.send_message(uid, f"❌ Kechirasiz, sizning `{oid}` raqamli buyurtmangiz rad etildi.", parse_mode="Markdown")
            bot.edit_message_text(f"❌ Order {oid} rad etildi.", ADMIN_ID, call.message.message_id)
        conn.commit()

# ------------------- ADMIN PANEL (Kengaytirilgan) -------------------
@bot.message_handler(func=lambda m: m.text == "⚙️ ADMIN BOSHQARUV PANELI")
def admin_panel(message):
    if not is_admin(message.from_user.id): return
    
    with get_db() as conn:
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE status='Tasdiqlandi'").fetchone()[0]
        total_sum = conn.execute("SELECT SUM(sum) FROM orders WHERE status='Tasdiqlandi'").fetchone()[0] or 0
        
    text = (
        f"📊 *BOT STATISTIKASI*\n\n"
        f"👥 Umumiy foydalanuvchilar: *{total_users} ta*\n"
        f"📦 Muvaffaqiyatli buyurtmalar: *{total_orders} ta*\n"
        f"💰 Umumiy tushum: *{format_num(total_sum)} so'm*\n\n"
        f"🔧 *Boshqaruv funksiyalari:* /sms - Xabar yuborish, /stat - To'liq tahlil"
    )
    bot.send_message(ADMIN_ID, text, parse_mode="Markdown")

# ------------------- SERVER VA ISHGA TUSHIRISH (Stabil) -------------------
@app.route('/')
def ping(): return "Bot ishlamoqda...", 200

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    # Flaskni alohida oqimda ishga tushiramiz (Render uchun)
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("Bot ishga tushdi...")
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=10)
        except Exception as e:
            logging.error(f"Xatolik: {e}")
            time.sleep(5)
