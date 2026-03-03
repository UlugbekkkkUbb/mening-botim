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

# ------------------- NARXLAR VA MAHSULOTLAR -------------------
PREMIUM_DATA = {
    '1_month': {'m': 1, 'p': 50000, 'n': '💎 1 Oylik Telegram Premium'},
    '3_months': {'m': 3, 'p': 145000, 'n': '💎 3 Oylik Telegram Premium'},
    '6_months': {'m': 6, 'p': 230000, 'n': '💎 6 Oylik Telegram Premium'},
    '12_months': {'m': 12, 'p': 350000, 'n': '💎 12 Oylik Telegram Premium'}
}

STARS_DATA = {
    '50': {'c': 50, 'p': 15000}, '100': {'c': 100, 'p': 29000},
    '250': {'c': 250, 'p': 65000}, '500': {'c': 500, 'p': 125000},
    '1000': {'c': 1000, 'p': 240000}, '5000': {'c': 5000, 'p': 1100000}
}

# ------------------- MA'LUMOTLAR BAZASI -------------------
def get_db():
    return sqlite3.connect('bot_database.db', check_same_thread=False)

def init_db():
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            uid INTEGER PRIMARY KEY, uname TEXT, fname TEXT, 
            balance REAL DEFAULT 0, refs INTEGER DEFAULT 0,
            ref_by INTEGER, is_prem INTEGER DEFAULT 0, 
            prem_exp TEXT, stars INTEGER DEFAULT 0, joined TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS orders (
            oid TEXT PRIMARY KEY, uid INTEGER, type TEXT, 
            pid TEXT, sum REAL, status TEXT, date TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS promos (
            code TEXT PRIMARY KEY, amount REAL, limit_use INTEGER, used_count INTEGER DEFAULT 0)''')
        conn.commit()

init_db()

# ------------------- ASOSIY MENYU VA START -------------------
def get_main_kb(uid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("💎 PREMIUM SOTIB OLISH", "🌟 STARS SOTIB OLISH")
    kb.add("👤 PROFILIM", "💸 PUL ISHLASH")
    kb.add("🎁 PROMO-KOD", "📞 ADMIN BILAN ALOQA")
    if uid == ADMIN_ID: kb.add("⚙️ ADMIN BOSHQARUV PANELI")
    return kb

@bot.message_handler(commands=['start'])
def welcome(message):
    uid, uname, fname = message.from_user.id, message.from_user.username, message.from_user.first_name
    with get_db() as conn:
        user = conn.execute("SELECT uid FROM users WHERE uid=?", (uid,)).fetchone()
        if not user:
            ref_id = int(message.text.split()[1]) if len(message.text.split()) > 1 and message.text.split()[1].isdigit() else None
            conn.execute("INSERT INTO users (uid, uname, fname, ref_by, joined) VALUES (?,?,?,?,?)",
                         (uid, uname, fname, ref_id, datetime.now().strftime("%Y-%m-%d")))
            if ref_id and ref_id != uid:
                conn.execute("UPDATE users SET balance=balance+500, refs=refs+1 WHERE uid=?", (ref_id,))
                bot.send_message(ref_id, "➕ *Sizda yangi referal!* +500 so'm qo'shildi.", parse_mode="Markdown")
        conn.commit()
    bot.send_message(uid, f"🌟 *Xush kelibsiz, {fname}!*\nKerakli bo'limni tanlang:", reply_markup=get_main_kb(uid), parse_mode="Markdown")

# ------------------- PROFIL VA SOTIB OLISH -------------------
@bot.message_handler(func=lambda m: m.text == "👤 PROFILIM")
def profile(message):
    with get_db() as conn:
        u = conn.execute("SELECT * FROM users WHERE uid=?", (message.from_user.id,)).fetchone()
    text = (f"👤 *PROFILINGIZ:*\n━━━━━━━━━━━━━━━\n🆔 ID: `{u[0]}`\n💰 Balans: *{u[3]:,.0f} so'm*\n"
            f"🌟 Stars: *{u[8]} ⭐*\n👥 Referallar: *{u[4]} ta*\n💎 Premium: {'✅' if u[6] else '❌'}\n━━━━━━━━━━━━━━━")
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "💎 PREMIUM SOTIB OLISH")
def buy_p(message):
    mk = types.InlineKeyboardMarkup(row_width=1)
    for k, v in PREMIUM_DATA.items():
        mk.add(types.InlineKeyboardButton(f"{v['n']} — {v['p']:,} so'm", callback_data=f"prm_{k}"))
    bot.send_message(message.chat.id, "👇 *Paketni tanlang:*", reply_markup=mk, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🌟 STARS SOTIB OLISH")
def buy_s(message):
    mk = types.InlineKeyboardMarkup(row_width=2)
    for k, v in STARS_DATA.items():
        mk.add(types.InlineKeyboardButton(f"{v['c']} ⭐ — {v['p']:,} so'm", callback_data=f"str_{k}"))
    bot.send_message(message.chat.id, "👇 *Miqdorni tanlang:*", reply_markup=mk, parse_mode="Markdown")

# ------------------- TO'LOV JARAYONI -------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith(('prm_', 'str_')))
def order_create(call):
    uid = call.from_user.id
    pre, pid = call.data.split('_')
    item = PREMIUM_DATA[pid] if pre == 'prm' else {'n': f"{STARS_DATA[pid]['c']} Stars", 'p': STARS_DATA[pid]['p']}
    oid = str(uuid.uuid4())[:8].upper()
    
    with get_db() as conn:
        conn.execute("INSERT INTO orders VALUES (?,?,?,?,?,?,?)", (oid, uid, pre, pid, item['p'], 'Kutilmoqda', datetime.now().strftime("%Y-%m-%d")))
        conn.commit()
    
    text = (f"🛒 *Buyurtma ID:* `{oid}`\n📦 Mahsulot: *{item['n']}*\n💰 Narxi: *{item['p']:,} so'm*\n\n"
            f"💳 Karta: `{CARD_NUMBER}`\n👤 Ega: *{CARD_HOLDER}*\n\n✅ To'lovdan so'ng tugmani bosing:")
    mk = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("✅ TO'LOV QILDIM", callback_data=f"confirm_{oid}"))
    bot.edit_message_text(text, uid, call.message.message_id, reply_markup=mk, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_'))
def admin_notify(call):
    oid = call.data.split('_')[1]
    bot.answer_callback_query(call.id, "✅ So'rov adminga yuborildi.")
    mk = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("✅ TASDIQLASH", callback_data=f"adm_ok_{oid}"),
        types.InlineKeyboardButton("❌ RAD ETISH", callback_data=f"adm_no_{oid}")
    )
    bot.send_message(ADMIN_ID, f"🔔 *Yangi to'lov!* ID: `{oid}`\nUser: {call.from_user.id}", reply_markup=mk, parse_mode="Markdown")
    bot.edit_message_text("⏳ *Admin tekshiruvi kutilmoqda...*", call.from_user.id, call.message.message_id, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_'))
def admin_res(call):
    if call.from_user.id != ADMIN_ID: return
    _, res, oid = call.data.split('_')
    with get_db() as conn:
        o = conn.execute("SELECT * FROM orders WHERE oid=?", (oid,)).fetchone()
        if not o: return
        uid, o_type, pid = o[1], o[2], o[3]
        if res == 'ok':
            if o_type == 'prm': conn.execute("UPDATE users SET is_prem=1 WHERE uid=?", (uid,))
            else: conn.execute("UPDATE users SET stars=stars+? WHERE uid=?", (STARS_DATA[pid]['c'], uid))
            bot.send_message(uid, f"🎉 *Buyurtmangiz (#{oid}) tasdiqlandi!*")
            bot.edit_message_text(f"✅ #{oid} tasdiqlandi", ADMIN_ID, call.message.message_id)
        else:
            bot.send_message(uid, f"❌ *Buyurtmangiz (#{oid}) rad etildi.*")
            bot.edit_message_text(f"❌ #{oid} rad etildi", ADMIN_ID, call.message.message_id)
        conn.execute("UPDATE orders SET status=? WHERE oid=?", ('Bajarildi' if res=='ok' else 'Rad etildi', oid))
        conn.commit()

# ------------------- SERVER VA ISHGA TUSHIRISH -------------------
@app.route('/')
def home(): return "Bot Running..."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port)).start()
    while True:
        try:
            bot.infinity_polling(timeout=20)
        except:
            time.sleep(5)
