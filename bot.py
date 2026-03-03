import telebot
from telebot import types
import sqlite3
import os
import json
import logging
from datetime import datetime, timedelta
import threading
from flask import Flask

# ===== CONFIGURATION =====
API_TOKEN = '8531883502:AAEsqT9W1gZUXuMMw2CUKGRxFb_USRFLmpQ'
ADMIN_ID = 7666979987
CARD_NUMBER = '9860080195351079'
CARD_HOLDER = 'Nargiza Q.'

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

# ===== DATABASE SETUP =====
def init_db():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, username TEXT, 
                  balance REAL DEFAULT 0, referrals INTEGER DEFAULT 0,
                  referred_by INTEGER, is_premium INTEGER DEFAULT 0,
                  join_date TEXT)''')
    
    # Agar ustunlar bo'lmasa qo'shish (Xatolikni oldini olish)
    try:
        c.execute("ALTER TABLE users ADD COLUMN total_referral_bonus REAL DEFAULT 0")
    except:
        pass
    
    conn.commit()
    conn.close()

init_db()

# ===== KEYBOARDS =====
def main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👤 Kabinet", "💰 Pul ishlash", "💎 Premium", "📊 Statistika", "ℹ️ Yordam")
    if user_id == ADMIN_ID:
        markup.add("⚙️ Admin Panel")
    return markup

# ===== HANDLERS =====
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    ref_id = None
    
    # Referal linkni tekshirish
    if len(message.text.split()) > 1:
        ref_id = message.text.split()[1]
        if ref_id.isdigit():
            ref_id = int(ref_id)

    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()

    if not user:
        # Yangi foydalanuvchi
        date_str = datetime.now().strftime("%Y-%m-%d")
        c.execute("INSERT INTO users (user_id, username, referred_by, join_date) VALUES (?, ?, ?, ?)",
                  (user_id, message.from_user.username, ref_id, date_str))
        
        if ref_id and ref_id != user_id:
            c.execute("UPDATE users SET balance = balance + 500, referrals = referrals + 1 WHERE user_id=?", (ref_id,))
            bot.send_message(ref_id, f"🎉 Tabriklaymiz! Sizning havolangiz orqali yangi a'zo qo'shildi. Balansingizga 500 so'm qo'shildi.")
            
        conn.commit()
    
    conn.close()
    bot.send_message(user_id, "👋 Salom! Botga xush kelibsiz. Bu yerda siz pul ishlashingiz va premium funksiyalardan foydalanishingiz mumkin.", 
                     reply_markup=main_menu(user_id))

@bot.message_handler(func=lambda m: m.text == "👤 Kabinet")
def cabinet(message):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute("SELECT balance, referrals, is_premium FROM users WHERE user_id=?", (message.from_user.id,))
    user = c.fetchone()
    conn.close()
    
    status = "💎 Premium" if user[2] else "📝 Oddiy"
    text = f"🆔 ID: {message.from_user.id}\n" \
           f"💰 Balans: {user[0]} so'm\n" \
           f"👥 Takliflar: {user[1]} ta\n" \
           f"🌟 Holat: {status}"
    bot.send_message(message.from_user.id, text)

@bot.message_handler(func=lambda m: m.text == "💰 Pul ishlash")
def earn(message):
    bot_username = bot.get_me().username
    ref_link = f"https://t.me/{bot_username}?start={message.from_user.id}"
    text = f"🔗 Sizning referal havolangiz:\n`{ref_link}`\n\nHar bir taklif qilingan do'stingiz uchun 500 so'm beriladi!"
    bot.send_message(message.from_user.id, text, parse_mode="Markdown")

# ===== FLASK FOR RENDER =====
@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

if __name__ == "__main__":
    # Botni alohida oqimda yurgizish
    threading.Thread(target=run_flask).start()
    print("🤖 BOT ISHGA TUSHDI...")
    bot.infinity_polling()

