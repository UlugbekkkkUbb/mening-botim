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

# ------------------- KONFIGURATSIYA VA LOGGING -------------------
# Bu qismda botning barcha asosiy parametrlari va tizim xabarlari sozlanadi.
API_TOKEN = '8305687409:AAF4-xPc-lwMyJQHcvEFNKxn_nrpWVHBC80'
ADMIN_ID = 7666979987
ADMIN_USERNAME = '@IDD_ADMINN'
CARD_NUMBER = '9860080195351079'
CARD_HOLDER = 'Nargiza Karshiyeva'
BOT_USERNAME = '@PREMIUM_STARSS_1BOT'

# Xatoliklarni kuzatish uchun logging tizimi
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    handlers=[logging.FileHandler("bot_log.txt"), logging.StreamHandler()]
)

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

# ------------------- MAHSULOTLAR VA NARXNAVOSI -------------------
# Har bir mahsulot uchun batafsil tavsiflar qo'shildi.
PREMIUM_DATA = {
    '1_month': {'m': 1, 'p': 50000, 'n': '💎 1 Oylik Telegram Premium', 'desc': '30 kun davomida cheksiz imkoniyatlar.'},
    '3_months': {'m': 3, 'p': 145000, 'n': '💎 3 Oylik Telegram Premium', 'desc': '90 kunlik tejamkor paket.'},
    '6_months': {'m': 6, 'p': 230000, 'n': '💎 6 Oylik Telegram Premium', 'desc': '180 kunlik professional paket.'},
    '12_months': {'m': 12, 'p': 350000, 'n': '💎 12 Oylik Telegram Premium', 'desc': '365 kunlik maksimal darajadagi foyda.'}
}

STARS_DATA = {
    '50': {'c': 50, 'p': 15000}, '100': {'c': 100, 'p': 29000},
    '250': {'c': 250, 'p': 65000}, '500': {'c': 500, 'p': 125000},
    '1000': {'c': 1000, 'p': 240000}, '5000': {'c': 5000, 'p': 1100000}
}

# ------------------- MA'LUMOTLAR BAZASI (Kengaytirilgan) -------------------
def get_db():
    return sqlite3.connect('bot_database.db', check_same_thread=False)

def init_db():
    with get_db() as conn:
        c = conn.cursor()
        # Foydalanuvchilar haqida barcha ma'lumotlar
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            uid INTEGER PRIMARY KEY, uname TEXT, fname TEXT, 
            balance REAL DEFAULT 0, refs INTEGER DEFAULT 0,
            ref_by INTEGER, is_prem INTEGER DEFAULT 0, 
            prem_exp TEXT, stars INTEGER DEFAULT 0, joined TEXT)''')
        # Buyurtmalar tarixi va holati
        c.execute('''CREATE TABLE IF NOT EXISTS orders (
            oid TEXT PRIMARY KEY, uid INTEGER, type TEXT, 
            pid TEXT, sum REAL, status TEXT, date TEXT)''')
        # Tizim statistikasi uchun qo'shimcha jadval
        c.execute('''CREATE TABLE IF NOT EXISTS stats (key TEXT PRIMARY KEY, value INTEGER)''')
        conn.commit()

init_db()

# ------------------- YORDAMCHI FUNKSIYALAR -------------------
def format_money(amount):
    return "{:,.0f}".format(amount).replace(",", " ")

# ------------------- KLAVIATURALAR -------------------
def get_main_kb(uid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        types.KeyboardButton("💎 PREMIUM SOTIB OLISH"),
        types.KeyboardButton("🌟 STARS SOTIB OLISH")
    )
    kb.add(
        types.KeyboardButton("👤 PROFILIM"),
        types.KeyboardButton("💸 PUL ISHLASH")
    )
    kb.add(
        types.KeyboardButton("🎁 PROMO-KOD"),
        types.KeyboardButton("📞 ADMIN BILAN ALOQA")
    )
    if uid == ADMIN_ID:
        kb.add(types.KeyboardButton("⚙️ ADMIN PANELI"))
    return kb

# ------------------- ASOSIY KOMANDALAR -------------------
@bot.message_handler(commands=['start'])
def welcome_handler(message):
    uid, uname, fname = message.from_user.id, message.from_user.username, message.from_user.first_name
    logging.info(f"Yangi foydalanuvchi: {uid} - {fname}")
    
    with get_db() as conn:
        user = conn.execute("SELECT uid FROM users WHERE uid=?", (uid,)).fetchone()
        if not user:
            # Referal tizimi integratsiyasi
            ref_id = None
            if len(message.text.split()) > 1:
                potential_ref = message.text.split()[1]
                if potential_ref.isdigit() and int(potential_ref) != uid:
                    ref_id = int(potential_ref)
            
            conn.execute("INSERT INTO users (uid, uname, fname, ref_by, joined) VALUES (?,?,?,?,?)",
                         (uid, uname, fname, ref_id, datetime.now().strftime("%Y-%m-%d %H:%M")))
            
            if ref_id:
                conn.execute("UPDATE users SET balance=balance+500, refs=refs+1 WHERE uid=?", (ref_id,))
                try:
                    bot.send_message(ref_id, f"🎊 *Yangi referal!* Sizga 500 so'm bonus berildi.", parse_mode="Markdown")
                except: pass
        conn.commit()

    text = (f"👋 *Assalomu alaykum, {fname}!*\n\n"
            f"🚀 *{BOT_USERNAME}* botiga xush kelibsiz!\n"
            f"Bu yerda siz Telegram xizmatlarini eng arzon narxlarda xarid qilishingiz mumkin.\n\n"
            f"✅ *Ishonchli va Tezkor*\n"
            f"💎 *Premium va Stars kafolatlangan*")
    bot.send_message(uid, text, reply_markup=get_main_kb(uid), parse_mode="Markdown")

# ------------------- PROFIL VA STATISTIKA -------------------
@bot.message_handler(func=lambda m: m.text == "👤 PROFILIM")
def show_profile(message):
    uid = message.from_user.id
    with get_db() as conn:
        u = conn.execute("SELECT * FROM users WHERE uid=?", (uid,)).fetchone()
    
    if not u: return
    
    profile_text = (
        f"👤 *Sizning Profilingiz*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🆔 ID: `{u[0]}`\n"
        f"👤 Ism: *{u[2]}*\n"
        f"💰 Balans: *{format_money(u[3])} so'm*\n"
        f"🌟 Stars: *{u[8]} ⭐*\n"
        f"💎 Premium: {'✅ Faol' if u[6] else '❌ Faol emas'}\n"
        f"👥 Taklif qilinganlar: *{u[4]} ta*\n"
        f"📅 Ro'yxatdan o'tgan sana: *{u[9]}*\n"
        f"━━━━━━━━━━━━━━━"
    )
    bot.send_message(uid, profile_text, parse_mode="Markdown")

# ------------------- SOTIB OLISH JARAYONI (Batafsil) -------------------
@bot.message_handler(func=lambda m: m.text == "💎 PREMIUM SOTIB OLISH")
def list_premium(message):
    mk = types.InlineKeyboardMarkup(row_width=1)
    for k, v in PREMIUM_DATA.items():
        btn_text = f"{v['n']} — {format_money(v['p'])} so'm"
        mk.add(types.InlineKeyboardButton(btn_text, callback_data=f"buy_prm_{k}"))
    bot.send_message(message.chat.id, "✨ *Telegram Premium paketlarini tanlang:*", reply_markup=mk, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def handle_purchase_step(call):
    uid = call.from_user.id
    data = call.data.split('_')
    p_type, p_id = data[1], data[2]
    
    order_id = str(uuid.uuid4())[:10].upper()
    item_name = ""
    price = 0
    
    if p_type == 'prm':
        item = PREMIUM_DATA[p_id]
        item_name, price = item['n'], item['p']
    else:
        item = STARS_DATA[p_id]
        item_name, price = f"{item['c']} Telegram Stars", item['p']
        
    with get_db() as conn:
        conn.execute("INSERT INTO orders VALUES (?,?,?,?,?,?,?)", 
                     (order_id, uid, p_type, p_id, price, 'Kutilmoqda', datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
        
    pay_msg = (
        f"💳 *To'lov Ma'lumotlari*\n\n"
        f"🆔 Buyurtma ID: `{order_id}`\n"
        f"📦 Mahsulot: *{item_name}*\n"
        f"💰 To'lov miqdori: *{format_money(price)} so'm*\n\n"
        f"🏧 Karta: `{CARD_NUMBER}`\n"
        f"👤 Karta egasi: *{CARD_HOLDER}*\n\n"
        f"⚠️ *Muhim:* To'lovni amalga oshirgach, chekni rasmga olib saqlang va quyidagi tugmani bosing."
    )
    
    mk = types.InlineKeyboardMarkup()
    mk.add(types.InlineKeyboardButton("✅ TO'LOVNI QILDIM", callback_data=f"confirm_{order_id}"))
    bot.edit_message_text(pay_msg, uid, call.message.message_id, reply_markup=mk, parse_mode="Markdown")

# ------------------- ADMIN BOSHQARUVI -------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_'))
def notify_admin_payment(call):
    order_id = call.data.split('_')[1]
    bot.answer_callback_query(call.id, "🚀 So'rovingiz adminga yuborildi. Kuting...", show_alert=True)
    
    with get_db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE oid=?", (order_id,)).fetchone()
    
    admin_txt = (
        f"🔔 *YANGI TO'LOV SO'ROVI*\n"
        f"🆔 Order ID: `{order_id}`\n"
        f"👤 User: {call.from_user.first_name} (@{call.from_user.username})\n"
        f"💰 Summa: {format_money(order[4])} so'm\n"
        f"📦 Turi: {order[2].upper()}"
    )
    
    mk = types.InlineKeyboardMarkup()
    mk.add(
        types.InlineKeyboardButton("✅ TASDIQLASH", callback_data=f"adm_ok_{order_id}"),
        types.InlineKeyboardButton("❌ RAD ETISH", callback_data=f"adm_no_{order_id}")
    )
    bot.send_message(ADMIN_ID, admin_txt, reply_markup=mk, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_'))
def final_decision(call):
    if call.from_user.id != ADMIN_ID: return
    
    _, res, oid = call.data.split('_')
    with get_db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE oid=?", (oid,)).fetchone()
        if not order: return
        
        uid, o_type, pid = order[1], order[2], order[3]
        if res == 'ok':
            if o_type == 'prm':
                conn.execute("UPDATE users SET is_prem=1 WHERE uid=?", (uid,))
            else:
                conn.execute("UPDATE users SET stars=stars+? WHERE uid=?", (STARS_DATA[pid]['c'], uid))
            
            bot.send_message(uid, f"🎉 *Xushxabar!* Sizning #{oid} buyurtmangiz tasdiqlandi va hisobingizga qo'shildi!", parse_mode="Markdown")
            bot.edit_message_text(f"✅ #{oid} TASDIQLANDI", ADMIN_ID, call.message.message_id)
        else:
            bot.send_message(uid, f"❌ *Afsuski,* sizning #{oid} buyurtmangiz rad etildi. Ma'lumotlarni qayta tekshiring.", parse_mode="Markdown")
            bot.edit_message_text(f"❌ #{oid} RAD ETILDI", ADMIN_ID, call.message.message_id)
            
        conn.execute("UPDATE orders SET status=? WHERE oid=?", ('YAKUNLANDI' if res=='ok' else 'RAD ETILDI', oid))
        conn.commit()

# ------------------- SERVER VA RUN -------------------
@app.route('/')
def health_check():
    return "Bot is healthy and running!", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    # Flaskni alohida oqimda ishga tushirish
    threading.Thread(target=run_flask, daemon=True).start()
    
    logging.info("Bot polling rejimi boshlandi...")
    while True:
        try:
            bot.infinity_polling(timeout=25, long_polling_timeout=10)
        except Exception as e:
            logging.error(f"Polling xatosi: {e}")
            time.sleep(5)

