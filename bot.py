#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════╗
║                   PREMIUM TELEGRAM BOT - ULTIMATE EDITION            ║
║                       Yaratuvchi: ×ULUGʻBEK×                         ║
║                    Barcha huquqlar himoyalangan © 2025               ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import telebot
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import sqlite3
import os
import json
import logging
from datetime import datetime, timedelta
import threading
import time
from functools import wraps
import hashlib
import random
import string
import re
import csv
import io
import requests
from dotenv import load_dotenv
import traceback
from collections import defaultdict
import schedule
import sys
from flask import Flask # Render uchun qo'shildi

# ===== WEB SERVER FOR RENDER (KEEP ALIVE) =====
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is active!"

def run_web():
    # Render avtomatik beradigan PORT o'zgaruvchisini oladi
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# ===== LOAD ENVIRONMENT =====
load_dotenv()

# ===== LOGGING SETUP =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ===== CONFIGURATION =====
DEFAULT_CONFIG = {
    'API_TOKEN': os.getenv('API_TOKEN', '8531883502:AAEs6T9W1gZUxUMW2CUKGRxFb_USRFLMpQ4'),
    'ADMIN_ID': int(os.getenv('ADMIN_ID', '7666979987')),
    'CARD_NUMBER': os.getenv('CARD_NUMBER', '9860080195351079'),
    'CARD_HOLDER': os.getenv('CARD_HOLDER', 'Nargiza Q.'),
    'SUPPORT_CHAT_ID': int(os.getenv('SUPPORT_CHAT_ID', '7666979987')),
    'REFERRAL_BONUS_PERCENT': 10,
    'MIN_REFILL_AMOUNT': 1000,
    'MAX_REFILL_AMOUNT': 10000000,
    'PAYMENT_TIMEOUT': 300,
    'DEFAULT_LANGUAGE': 'uz',
    'ENABLE_AUTO_PAYMENT_CHECK': False,
    'AUTO_PAYMENT_API_URL': '',
    'AUTO_PAYMENT_API_KEY': ''
}

config = DEFAULT_CONFIG.copy()

# ===== DATABASE CLASS =====
class Database:
    def __init__(self, db_name='premium_bot.db'):
        self.db_name = db_name
        self.init_db()
        self.load_config()
    
    def get_conn(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        conn = self.get_conn()
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_name TEXT, balance REAL DEFAULT 0, status TEXT DEFAULT 'active', role TEXT DEFAULT 'user', premium_expire TIMESTAMP, referral_code TEXT UNIQUE, referred_by INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_activity TIMESTAMP, language TEXT DEFAULT 'uz', total_spent REAL DEFAULT 0, total_referral_bonus REAL DEFAULT 0, total_referrals INTEGER DEFAULT 0, notifications BOOLEAN DEFAULT 1, notes TEXT, FOREIGN KEY(referred_by) REFERENCES users(user_id))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS packages (package_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, description TEXT, type TEXT, duration INTEGER, star_count INTEGER, price REAL, features TEXT, is_active BOOLEAN DEFAULT 1, sort_order INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS transactions (transaction_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL, type TEXT, status TEXT DEFAULT 'pending', package_id INTEGER, screenshot_file_id TEXT, gift_telegram_user_id INTEGER, admin_id INTEGER, admin_note TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, confirmed_at TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(user_id), FOREIGN KEY(package_id) REFERENCES packages(package_id), FOREIGN KEY(admin_id) REFERENCES users(user_id))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS support_tickets (ticket_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, subject TEXT, message TEXT, status TEXT DEFAULT 'open', priority TEXT DEFAULT 'normal', assigned_to INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP, closed_at TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(user_id), FOREIGN KEY(assigned_to) REFERENCES users(user_id))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS ticket_replies (reply_id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id INTEGER, user_id INTEGER, message TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(ticket_id) REFERENCES support_tickets(ticket_id), FOREIGN KEY(user_id) REFERENCES users(user_id))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS announcements (announcement_id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, content TEXT, image_file_id TEXT, is_active BOOLEAN DEFAULT 1, sent_count INTEGER DEFAULT 0, failed_count INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, scheduled_for TIMESTAMP, filters TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS settings (setting_name TEXT PRIMARY KEY, setting_value TEXT, setting_type TEXT DEFAULT 'string', description TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_by INTEGER)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS logs (log_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT, details TEXT, ip TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS referral_stats (stat_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, date DATE, referrals INTEGER DEFAULT 0, earnings REAL DEFAULT 0, UNIQUE(user_id, date))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS daily_stats (date DATE PRIMARY KEY, new_users INTEGER DEFAULT 0, transactions INTEGER DEFAULT 0, revenue REAL DEFAULT 0, refills REAL DEFAULT 0, purchases REAL DEFAULT 0)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS backup_log (backup_id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT, size INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
        conn.close()
        self.init_default_packages()
        self.init_default_settings()
    
    def init_default_packages(self):
        packages = [
            ('💎 1 OYLIK PREMIUM', 'Telegram Premium 1 oy', 'premium_gift', 1, None, 50000, 'Telegram Premium 1 oy sovgʻasi', 1),
            ('💎 3 OYLIK PREMIUM', 'Telegram Premium 3 oy', 'premium_gift', 3, None, 145000, 'Telegram Premium 3 oy sovgʻasi', 2),
            ('💎 6 OYLIK PREMIUM', 'Telegram Premium 6 oy', 'premium_gift', 6, None, 230000, 'Telegram Premium 6 oy sovgʻasi', 3),
            ('💎 12 OYLIK PREMIUM', 'Telegram Premium 12 oy', 'premium_gift', 12, None, 350000, 'Telegram Premium 12 oy sovgʻasi', 4),
            ('🌟 50 STARS', 'Telegram Stars 50', 'stars_gift', None, 50, 15000, 'Telegram Stars 50 sovgʻasi', 5),
            ('🌟 100 STARS', 'Telegram Stars 100', 'stars_gift', None, 100, 28000, 'Telegram Stars 100 sovgʻasi', 6),
            ('🌟 500 STARS', 'Telegram Stars 500', 'stars_gift', None, 500, 135000, 'Telegram Stars 500 sovgʻasi', 7),
            ('🌟 1000 STARS', 'Telegram Stars 1000', 'stars_gift', None, 1000, 260000, 'Telegram Stars 1000 sovgʻasi', 8),
        ]
        for pkg in packages:
            self.execute('INSERT OR IGNORE INTO packages (name, description, type, duration, star_count, price, features, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', pkg)
    
    def init_default_settings(self):
        settings = [
            ('card_number', config['CARD_NUMBER'], 'string', 'Karta raqami'),
            ('card_holder', config['CARD_HOLDER'], 'string', 'Karta egasi'),
            ('support_chat_id', str(config['SUPPORT_CHAT_ID']), 'int', 'Qoʻllab-quvvatlash chat ID'),
            ('admin_ids', str(config['ADMIN_ID']), 'json', 'Adminlar ID roʻyxati'),
            ('referral_bonus_percent', str(config['REFERRAL_BONUS_PERCENT']), 'int', 'Referal bonusi foizi'),
            ('min_refill_amount', str(config['MIN_REFILL_AMOUNT']), 'int', 'Minimal toʻlov miqdori'),
            ('max_refill_amount', str(config['MAX_REFILL_AMOUNT']), 'int', 'Maksimal toʻlov miqdori'),
            ('payment_timeout', str(config['PAYMENT_TIMEOUT']), 'int', 'Toʻlovni kutish vaqti'),
            ('default_language', config['DEFAULT_LANGUAGE'], 'string', 'Standart til'),
            ('enable_auto_payment_check', str(config['ENABLE_AUTO_PAYMENT_CHECK']), 'bool', 'Avtomatik toʻlov tekshiruvi'),
            ('bot_status', 'active', 'string', 'Bot holati'),
            ('maintenance_text', 'Bot texnik ishlar olib borilmoqda.', 'string', 'Texnik ish xabari'),
            ('welcome_message', '🦾 **XUSH KELIBSIZ!**\n\nUshbu bot orqali Telegram Premium va Stars xarid qilishingiz mumkin.', 'text', 'Salomlashish xabari'),
        ]
        for name, value, typ, desc in settings:
            self.execute('INSERT OR IGNORE INTO settings (setting_name, setting_value, setting_type, description) VALUES (?, ?, ?, ?)', (name, value, typ, desc))
    
    def execute(self, query, params=()):
        try:
            conn = self.get_conn()
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Database execute error: {e}")
            return False
    
    def fetch_one(self, query, params=()):
        try:
            conn = self.get_conn()
            cursor = conn.cursor()
            cursor.execute(query, params)
            result = cursor.fetchone()
            conn.close()
            return result
        except Exception as e:
            logger.error(f"Database fetch_one error: {e}")
            return None
    
    def fetch_all(self, query, params=()):
        try:
            conn = self.get_conn()
            cursor = conn.cursor()
            cursor.execute(query, params)
            result = cursor.fetchall()
            conn.close()
            return result
        except Exception as e:
            logger.error(f"Database fetch_all error: {e}")
            return []
    
    def load_config(self):
        global config
        rows = self.fetch_all('SELECT setting_name, setting_value, setting_type FROM settings')
        for row in rows:
            name, val, typ = row['setting_name'], row['setting_value'], row['setting_type']
            try:
                if typ == 'int': config[name] = int(val)
                elif typ == 'float': config[name] = float(val)
                elif typ == 'bool': config[name] = val.lower() in ('true', '1', 'yes')
                elif typ == 'json': config[name] = json.loads(val)
                else: config[name] = val
            except: config[name] = val

db = Database()
bot = telebot.TeleBot(config['API_TOKEN'])

# ===== HELPER FUNCTIONS =====
def is_admin(user_id):
    admin_ids = config.get('admin_ids', str(DEFAULT_CONFIG['ADMIN_ID']))
    if isinstance(admin_ids, str):
        admin_ids = [int(x.strip()) for x in admin_ids.split(',') if x.strip().isdigit()]
    elif isinstance(admin_ids, int): admin_ids = [admin_ids]
    return user_id in (admin_ids if isinstance(admin_ids, list) else [DEFAULT_CONFIG['ADMIN_ID']])

def admin_only(func):
    @wraps(func)
    def wrapper(message):
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "❌ Siz admin emassiz!")
            return
        return func(message)
    return wrapper

def maintenance_check(func):
    @wraps(func)
    def wrapper(message):
        if config.get('bot_status') == 'maintenance' and not is_admin(message.from_user.id):
            bot.reply_to(message, config.get('maintenance_text', 'Bot texnik ishlar olib borilmoqda.'))
            return
        return func(message)
    return wrapper

def get_user(user_id): return db.fetch_one('SELECT * FROM users WHERE user_id = ?', (user_id,))

def create_user(user_id, first_name, last_name, username, referred_by=None):
    referral_code = hashlib.md5(f"{user_id}{time.time()}".encode()).hexdigest()[:8].upper()
    db.execute('INSERT OR IGNORE INTO users (user_id, first_name, last_name, username, referral_code, referred_by, language) VALUES (?, ?, ?, ?, ?, ?, ?)', (user_id, first_name, last_name, username, referral_code, referred_by, config['default_language']))
    if referred_by:
        db.execute('UPDATE users SET total_referrals = total_referrals + 1 WHERE user_id = ?', (referred_by,))
        today = datetime.now().date().isoformat()
        db.execute('INSERT INTO referral_stats (user_id, date, referrals) VALUES (?, ?, 1) ON CONFLICT(user_id, date) DO UPDATE SET referrals = referrals + 1', (referred_by, today))
    today = datetime.now().date().isoformat()
    db.execute('INSERT INTO daily_stats (date, new_users) VALUES (?, 1) ON CONFLICT(date) DO UPDATE SET new_users = new_users + 1', (today,))

def update_balance(user_id, amount, log_details=''):
    db.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    db.execute('INSERT INTO logs (user_id, action, details) VALUES (?, "balance_change", ?)', (user_id, f"{amount} so'm. {log_details}"))

def get_user_stats(user_id):
    user = get_user(user_id)
    if not user: return None
    ref_count = db.fetch_one('SELECT COUNT(*) as count FROM users WHERE referred_by = ?', (user_id,))['count']
    total_spent = db.fetch_one('SELECT SUM(amount) as total FROM transactions WHERE user_id = ? AND status = "confirmed"', (user_id,))['total'] or 0
    total_bonus = db.fetch_one('SELECT SUM(amount) as total FROM transactions WHERE user_id = ? AND type = "referral_bonus" AND status = "confirmed"', (user_id,))['total'] or 0
    return {**dict(user), 'referral_count': ref_count, 'total_spent': total_spent, 'total_referral_bonus': total_bonus}

def format_number(num): return f"{int(num):,}".replace(',', ' ')

# ===== KEYBOARDS =====
def main_menu_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=4)
    kb.add(KeyboardButton("💎 Premium"), KeyboardButton("💰 Balans"), KeyboardButton("📦 Paketlar"), KeyboardButton("❓ Yordam"))
    kb.add(KeyboardButton("🌟 Stars"), KeyboardButton("👥 Pul ishlash"), KeyboardButton("⚙️ Sozlamalar"))
    kb.add(KeyboardButton("🆘 SOS"), KeyboardButton("📊 Statistika"))
    return kb

def admin_menu_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(KeyboardButton("👥 Foydalanuvchilar"), KeyboardButton("📊 Statistika"), KeyboardButton("💰 Toʻlovlar"), KeyboardButton("📢 Eʼlon"), KeyboardButton("📦 Paketlar"), KeyboardButton("⚙️ Sozlamalar"), KeyboardButton("🔙 Orqaga"))
    return kb

def packages_inline_kb(package_type, page=0):
    per_page = 5
    offset = page * per_page
    packages = db.fetch_all('SELECT * FROM packages WHERE type = ? AND is_active = 1 ORDER BY sort_order ASC LIMIT ? OFFSET ?', (package_type, per_page, offset))
    kb = InlineKeyboardMarkup(row_width=1)
    for pkg in packages:
        kb.add(InlineKeyboardButton(f"{pkg['name']} — {format_number(pkg['price'])} so'm", callback_data=f"buy_{pkg['package_id']}"))
    kb.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu"))
    return kb

# ===== HANDLERS =====
@bot.message_handler(commands=['start'])
@maintenance_check
def start(message):
    user_id = message.from_user.id
    referred_by = None
    args = message.text.split()
    if len(args) > 1:
        ref_user = db.fetch_one('SELECT user_id FROM users WHERE referral_code = ?', (args[1].upper(),))
        if ref_user: referred_by = ref_user['user_id']
    if not get_user(user_id):
        create_user(user_id, message.from_user.first_name, message.from_user.last_name, message.from_user.username, referred_by)
    bot.send_message(user_id, config.get('welcome_message', 'Xush kelibsiz!'), reply_markup=main_menu_kb(), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "💎 Premium")
def prem_btn(m): bot.send_message(m.chat.id, "💎 **Premium paketlar:**", reply_markup=packages_inline_kb('premium_gift'), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🌟 Stars")
def stars_btn(m): bot.send_message(m.chat.id, "🌟 **Stars paketlar:**", reply_markup=packages_inline_kb('stars_gift'), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "💰 Balans")
def balance_btn(m):
    user = get_user(m.from_user.id)
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("💳 To‘ldirish", callback_data="refill"), InlineKeyboardButton("📜 Tarix", callback_data="balance_history"))
    bot.send_message(m.from_user.id, f"💰 **BALANS:** {format_number(user['balance'])} so'm", reply_markup=kb, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📊 Statistika")
def stats_btn(m):
    s = get_user_stats(m.from_user.id)
    text = f"📊 **STATISTIKA**\n\nID: `{s['user_id']}`\nBalans: {format_number(s['balance'])} so'm\nReferallar: {s['referral_count']} ta"
    bot.send_message(m.from_user.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🆘 SOS")
def sos_btn(m):
    bot.send_message(m.from_user.id, "🚨 SOS yuborildi. Adminlar bilan bog'lanamiz.")
    for aid in [config['ADMIN_ID']]: bot.send_message(aid, f"🚨 SOS: {m.from_user.id} (@{m.from_user.username})")

@bot.callback_query_handler(func=lambda c: c.data == "refill")
def refill_call(call):
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("50 000", callback_data="rf_50000"), InlineKeyboardButton("100 000", callback_data="rf_100000"))
    bot.edit_message_text("Summani tanlang:", call.from_user.id, call.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith('rf_'))
def rf_amount(call):
    amt = int(call.data.split('_')[1])
    db.execute('INSERT INTO transactions (user_id, amount, type, status) VALUES (?, ?, "refill", "pending")', (call.from_user.id, amt))
    bot.edit_message_text(f"Karta: `{config['card_number']}`\nSumma: {format_number(amt)} so'm\nChekni yuboring.", call.from_user.id, call.message.message_id, parse_mode="Markdown")

@bot.message_handler(content_types=['photo'])
def handle_receipt(message):
    trans = db.fetch_one('SELECT * FROM transactions WHERE user_id = ? AND status = "pending" ORDER BY created_at DESC LIMIT 1', (message.from_user.id,))
    if trans:
        db.execute('UPDATE transactions SET screenshot_file_id = ? WHERE transaction_id = ?', (message.photo[-1].file_id, trans['transaction_id']))
        bot.reply_to(message, "✅ Chek qabul qilindi. Tasdiqlashni kuting.")
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"ap_{trans['transaction_id']}"), InlineKeyboardButton("❌ Rad etish", callback_data=f"rj_{trans['transaction_id']}"))
        bot.send_photo(config['ADMIN_ID'], message.photo[-1].file_id, caption=f"To'lov: {format_number(trans['amount'])} so'm\nUser: {message.from_user.id}", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith(('ap_', 'rj_')))
def admin_decision(call):
    tid = int(call.data.split('_')[1])
    trans = db.fetch_one('SELECT * FROM transactions WHERE transaction_id = ?', (tid,))
    if call.data.startswith('ap_'):
        db.execute('UPDATE transactions SET status = "confirmed" WHERE transaction_id = ?', (tid,))
        update_balance(trans['user_id'], trans['amount'], "To'lov tasdiqlandi")
        bot.send_message(trans['user_id'], "✅ Balans to'ldirildi!")
    else:
        db.execute('UPDATE transactions SET status = "rejected" WHERE transaction_id = ?', (tid,))
        bot.send_message(trans['user_id'], "❌ To'lov rad etildi.")
    bot.edit_message_caption("Bajarildi", call.from_user.id, call.message.message_id)

# ===== SCHEDULED TASKS =====
def run_scheduled():
    while True:
        schedule.run_pending()
        time.sleep(60)

threading.Thread(target=run_scheduled, daemon=True).start()

# ===== START BOT =====
if __name__ == '__main__':
    # Render uchun Flaskni alohida oqimda ishga tushirish
    threading.Thread(target=run_web, daemon=True).start()
    
    logger.info('🤖 BOT ISHGA TUSHDI...')
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        logger.critical(f"Xatolik: {e}")

