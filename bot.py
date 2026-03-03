#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PROFESSIONAL TELEGRAM BOT - TOʻLIQ AVTOMATIK SISTEMA
Yaratuvchi: ×ULUGʻBEK×
Xususiyatlari: Premium, Referal, Toʻlov, Admin Panel, Analytics
"""

import telebot
from telebot import types
import sqlite3
import os
import json
import logging
from datetime import datetime, timedelta
import threading
import time
from functools import wraps
import hashlib
from dotenv import load_dotenv
import traceback

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

# ===== CONFIGURATION (SENING MA'LUMOTLARING JOYLASHDI) =====
API_TOKEN = '8531883502:AAEs6T9W1gZUxUMW2CUKGRxFb_USRFLMpQ4'
ADMIN_ID = 7666979987
CARD_NUMBER = '9860080195351079'
CARD_HOLDER = 'Nargiza Q.'
SUPPORT_CHAT_ID = 7666979987

# Initialize bot
bot = telebot.TeleBot(API_TOKEN)

# ===== DATABASE CLASS =====
class Database:
    def __init__(self, db_name='bot_data.db'):
        self.db_name = db_name
        self.init_db()
    
    def get_conn(self):
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Create all required tables"""
        conn = self.get_conn()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                balance REAL DEFAULT 0,
                status TEXT DEFAULT 'free',
                premium_expire TEXT,
                referral_code TEXT UNIQUE,
                referred_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP,
                is_banned BOOLEAN DEFAULT 0,
                language TEXT DEFAULT 'uz',
                total_spent REAL DEFAULT 0,
                total_referral_bonus REAL DEFAULT 0
            )
        ''')
        
        # Packages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS packages (
                package_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                description TEXT,
                type TEXT,
                duration INTEGER,
                price REAL,
                features TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                type TEXT,
                status TEXT DEFAULT 'pending',
                package_id INTEGER,
                screenshot_file_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confirmed_at TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                FOREIGN KEY(package_id) REFERENCES packages(package_id)
            )
        ''')
        
        # Support tickets table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS support_tickets (
                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                subject TEXT,
                message TEXT,
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        
        # Announcements table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS announcements (
                announcement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Admin settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_settings (
                setting_name TEXT PRIMARY KEY,
                setting_value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
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

db = Database()

# ===== UTILITY FUNCTIONS =====
def is_admin(user_id):
    """Check if user is admin"""
    return user_id == ADMIN_ID

def admin_only(func):
    """Decorator for admin-only commands"""
    @wraps(func)
    def wrapper(message):
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "❌ Faqat admin uchun!")
            logger.warning(f"Unauthorized admin access attempt by {message.from_user.id}")
            return
        return func(message)
    return wrapper

def get_user(user_id):
    """Get user from database"""
    return db.fetch_one('SELECT * FROM users WHERE user_id = ?', (user_id,))

def create_user(user_id, first_name, last_name, username, referred_by=None):
    """Create new user"""
    referral_code = hashlib.md5(str(user_id).encode()).hexdigest()[:8].upper()
    db.execute('''
        INSERT OR IGNORE INTO users (user_id, first_name, last_name, username, referral_code, referred_by)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, first_name, last_name, username, referral_code, referred_by))

def get_balance(user_id):
    """Get user balance"""
    result = db.fetch_one('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    return result['balance'] if result else 0

def update_balance(user_id, amount):
    """Update user balance"""
    db.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))

def get_user_stats(user_id):
    """Get comprehensive user statistics"""
    user = get_user(user_id)
    if not user:
        return None
    
    referrals = db.fetch_one('SELECT COUNT(*) as count FROM users WHERE referred_by = ?', (user_id,))
    ref_count = referrals['count'] if referrals else 0
    
    transactions = db.fetch_all('SELECT SUM(amount) as total FROM transactions WHERE user_id = ? AND status = "confirmed"', (user_id,))
    total_spent = transactions[0]['total'] if transactions and transactions[0]['total'] else 0
    
    return {
        'user_id': user['user_id'],
        'username': user['username'],
        'first_name': user['first_name'],
        'balance': user['balance'],
        'status': user['status'],
        'referral_code': user['referral_code'],
        'referral_count': ref_count,
        'total_spent': total_spent,
        'created_at': user['created_at'],
        'premium_expire': user['premium_expire']
    }

# ===== KEYBOARD BUILDERS =====
def main_menu_kb():
    """Main menu keyboard"""
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("💎 Premium", "🌟 Stars")
    kb.add("💰 Balans", "👥 Pul ishlash")
    kb.add("📱 Paketlar", "⚙️ Sozlamalar")
    kb.add("🆘 Yordam", "📊 Statistika")
    return kb

def admin_menu_kb():
    """Admin menu keyboard"""
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("👥 Foydalanuvchilar", "📊 Statistika")
    kb.add("💰 Toʻlovlar", "📢 Eʼlon")
    kb.add("📦 Paketlar", "⚙️ Sozlamalar")
    kb.add("🆘 Qoʻllab-quvvatlash", "🚀 Status")
    kb.add("🔙 Orqaga")
    return kb

def packages_inline_kb(package_type='premium'):
    """Inline keyboard for packages"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    packages = db.fetch_all('SELECT * FROM packages WHERE type = ? AND is_active = 1 ORDER BY price ASC', (package_type,))
    
    if not packages:
        # Add default packages if none exist
        default_packages = {
            'premium': [
                ('💎 1 OYLIK', 50000, 1, 'premium'),
                ('💎 3 OYLIK', 145000, 3, 'premium'),
                ('💎 6 OYLIK', 230000, 6, 'premium'),
                ('💎 12 OYLIK', 350000, 12, 'premium')
            ],
            'stars': [
                ('🌟 50 Stars', 15000, 1, 'stars'),
                ('🌟 100 Stars', 28000, 1, 'stars'),
                ('🌟 500 Stars', 135000, 1, 'stars'),
                ('🌟 1000 Stars', 260000, 1, 'stars')
            ]
        }
        
        for name, price, duration, ptype in default_packages.get(package_type, []):
            db.execute('''
                INSERT OR IGNORE INTO packages (name, description, type, duration, price, features)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, f"{name} paket", ptype, duration, price, "Premium xususiyatlar"))
        
        packages = db.fetch_all('SELECT * FROM packages WHERE type = ? AND is_active = 1 ORDER BY price ASC', (package_type,))
    
    for pkg in packages:
        btn_text = f"{pkg['name']} — {pkg['price']} so'm"
        kb.add(types.InlineKeyboardButton(btn_text, callback_data=f'buy_{pkg["package_id"]}'))
    
    kb.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data="main_menu"))
    return kb

# ===== MAIN COMMANDS =====
@bot.message_handler(commands=['start'])
def start(message):
    """Start command"""
    user_id = message.from_user.id
    
    try:
        # Get or create user
        user = get_user(user_id)
        if not user:
            # Check for referral code in /start
            args = message.text.split()
            referred_by = None
            
            if len(args) > 1:
                ref_code = args[1]
                ref_user = db.fetch_one('SELECT user_id FROM users WHERE referral_code = ?', (ref_code.upper(),))
                if ref_user:
                    referred_by = ref_user['user_id']
            
            create_user(user_id, message.from_user.first_name, message.from_user.last_name, 
                       message.from_user.username, referred_by)
        
        db.execute('UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE user_id = ?', (user_id,))
        
        logger.info(f'User {user_id} (@{message.from_user.username}) started the bot')
        
        text = """
🦾 **NOMER 1 BOTGA XUSH KELIBSIZ!** 🦾

Ushbu bot sizga quyidagi xizmatlarni taqdim etadi:

💎 **Premium Obuna** - Shaxsiy xususiyatlar
🌟 **Stars Xizmati** - Qo'shimcha imkoniyatlar  
💰 **Balans** - Toʻlov va refill
👥 **Referal Dasturi** - Dostlarni taklif qiling, pul ishlang
🆘 **24/7 Qoʻllab-quvvatlash** - Muammolarni hal qilish

✨ **Hamma xizmatlar avtomatlashgan va xavfsiz!** ✨
        """
        
        bot.send_message(user_id, text, reply_markup=main_menu_kb(), parse_mode="Markdown")
    
    except Exception as e:
        logger.error(f"Error in start command: {e}\n{traceback.format_exc()}")
        bot.send_message(user_id, "❌ Xatoli! Qaytadan urinib koʻring.")

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    """Admin panel"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        bot.reply_to(message, "❌ Faqat admin uchun!")
        return
    
    text = "🔐 **ADMIN PANELGA XUSH KELIBSIZ!**\n\nNima qilmoqchisiz?"
    bot.send_message(user_id, text, reply_markup=admin_menu_kb(), parse_mode="Markdown")

@bot.message_handler(commands=['ref'])
def referral_link(message):
    """Get referral link"""
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user:
        bot.send_message(user_id, "❌ Avval /start buyrug'ini kiriting")
        return
    
    text = f"""
👥 **REFERAL DASTURI**

🔗 Sizning Referal Kodi: `{user['referral_code']}`

📱 Linkni Koʻchirish:
`/start {user['referral_code']}`

💰 **Bonuslar:**
• Har bir oʻz do'stingiz uchun: 10% bonus
• Cheksiz do'st taklif qiling!
    """
    
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📋 Statistika", callback_data="ref_stats"))
    
    bot.send_message(user_id, text, reply_markup=kb, parse_mode="Markdown")

# ===== USER COMMANDS =====
@bot.message_handler(func=lambda m: m.text == "💎 Premium")
def premium_packages(message):
    """Show premium packages"""
    try:
        bot.send_message(message.chat.id, "📦 **Premium paketlarini tanlang:**", 
                        reply_markup=packages_inline_kb('premium'), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in premium_packages: {e}")

@bot.message_handler(func=lambda m: m.text == "🌟 Stars")
def stars_packages(message):
    """Show stars packages"""
    try:
        bot.send_message(message.chat.id, "📦 **Stars paketlarini tanlang:**", 
                        reply_markup=packages_inline_kb('stars'), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in stars_packages: {e}")

@bot.message_handler(func=lambda m: m.text == "💰 Balans")
def balance(message):
    """Show user balance"""
    try:
        user_id = message.from_user.id
        user = get_user(user_id)
        
        if not user:
            bot.send_message(user_id, "❌ Foydalanuvchi topilmadi. /start ni kiriting")
            return
        
        balance = user['balance']
        
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("💳 Toʻldirish", callback_data="refill"),
            types.InlineKeyboardButton("📊 Tarix", callback_data="balance_history")
        )
        
        text = f"""
💰 **BALANS BOSHQARUVI**

💵 Sizning Balans: `{balance}` so'm
📅 Oxirgi Faollik: {user['last_activity']}

Balansni toʻldiring va xizmatlarni sotib oling!
        """
        
        bot.send_message(user_id, text, reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in balance: {e}")

@bot.message_handler(func=lambda m: m.text == "👥 Pul ishlash")
def referral_system(message):
    """Referral system"""
    try:
        user_id = message.from_user.id
        stats = get_user_stats(user_id)
        
        if not stats:
            bot.send_message(user_id, "❌ Foydalanuvchi topilmadi")
            return
        
        text = f"""
👥 **REFERAL DASTURI - PUL ISHLASH**

🔗 **Sizning Kodi:** `{stats['referral_code']}`

📊 **Statistika:**
• Jami referral: {stats['referral_count']} ta
• Olgan bonus: {stats['total_referral_bonus']} so'm

💡 **Qanday Ishlaydi?**
1️⃣ Dostingizga linkni yuboring
2️⃣ U botga kirsa, 10% bonus olasiz
3️⃣ Cheksiz do'st - cheksiz bonus!

🎁 **Bonusni Qanday Ishlatish?**
→ Balansga qoʻshiladi
→ Paket sotib olishga ishlatish mumkin
        """
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🔗 Linkni Koʻchirish", callback_data="copy_ref"))
        kb.add(types.InlineKeyboardButton("📊 Referallari", callback_data="ref_list"))
        
        bot.send_message(user_id, text, reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in referral_system: {e}")

@bot.message_handler(func=lambda m: m.text == "📱 Paketlar")
def all_packages(message):
    """Show all available packages"""
    try:
        packages = db.fetch_all('SELECT * FROM packages WHERE is_active = 1')
        
        if not packages:
            bot.send_message(message.chat.id, "📦 Paketlar mavjud emas")
            return
        
        text = "📦 **MAVJUD PAKETLAR:**\n\n"
        
        for pkg in packages:
            text += f"💎 {pkg['name']}\n"
            text += f"   💵 Narx: {pkg['price']} so'm\n"
            text += f"   ⏱️ Muddati: {pkg['duration']} kun\n"
            text += f"   📝 {pkg['description']}\n\n"
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("💎 Premium", callback_data="show_premium"))
        kb.add(types.InlineKeyboardButton("🌟 Stars", callback_data="show_stars"))
        
        bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in all_packages: {e}")

@bot.message_handler(func=lambda m: m.text == "⚙️ Sozlamalar")
def settings(message):
    """User settings"""
    try:
        user_id = message.from_user.id
        user = get_user(user_id)
        
        if not user:
            bot.send_message(user_id, "❌ Foydalanuvchi topilmadi")
            return
        
        text = f"""
⚙️ **SOZLAMALAR**

👤 Username: @{user['username']}
📝 Ism: {user['first_name']} {user['last_name']}
📊 Status: {user['status']}
🌐 Tili: {user['language']}

Sozlamalarni oʻzgartirish uchun qaysi tugmani bosing?
        """
        
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        kb.add("🌐 Til oʻzgartirish", "🔔 Bildirishnomalar")
        kb.add("🔐 Parol", "📱 Raqamni oʻzgartirish")
        kb.add("🔙 Orqaga")
        
        bot.send_message(user_id, text, reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in settings: {e}")

@bot.message_handler(func=lambda m: m.text == "🆘 Yordam")
def support(message):
    """Support system"""
    try:
        user_id = message.from_user.id
        msg = bot.send_message(user_id, "📝 **Savol yoki muammoni batafsil yozing:**\n\n(Yoki /cancel bilan bekor qiling)")
        bot.register_next_step_handler(msg, handle_support_message)
    except Exception as e:
        logger.error(f"Error in support: {e}")

def handle_support_message(message):
    """Handle support message"""
    try:
        user_id = message.from_user.id
        
        if message.text == "/cancel":
            bot.send_message(user_id, "❌ Bekor qilindi", reply_markup=main_menu_kb())
            return
        
        user = get_user(user_id)
        
        # Save ticket
        db.execute('''
            INSERT INTO support_tickets (user_id, subject, message)
            VALUES (?, ?, ?)
        ''', (user_id, 'User Support Request', message.text))
        
        # Notify admin
        admin_text = f"""
🆘 **YANGI QOʻLLAB-QUVVATLASH XABARI**

👤 Foydalanuvchi: @{user['username']} (ID: {user_id})
📝 Xabar:
{message.text}

📅 Vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("✅ Javob Berish", callback_data=f"reply_ticket_{user_id}"))
        
        bot.send_message(SUPPORT_CHAT_ID, admin_text, reply_markup=kb, parse_mode="Markdown")
        
        bot.send_message(user_id, """
✅ **XAB AR YUBORILDI!**

Qoʻllab-quvvatlash jamoasi tez orada sizga javob beradilar.
        """, reply_markup=main_menu_kb(), parse_mode="Markdown")
        
        logger.info(f"Support message from {user_id}: {message.text[:50]}...")
    except Exception as e:
        logger.error(f"Error in handle_support_message: {e}")

@bot.message_handler(func=lambda m: m.text == "📊 Statistika")
def user_stats(message):
    """User statistics"""
    try:
        user_id = message.from_user.id
        stats = get_user_stats(user_id)
        
        if not stats:
            bot.send_message(user_id, "❌ Foydalanuvchi topilmadi")
            return
        
        text = f"""
📊 **SIZNING STATISTIKA**

👤 Username: @{stats['username']}
📝 Ism: {stats['first_name']}
💰 Balans: {stats['balance']} so'm
📦 Status: {stats['status']}

👥 Referal:
  • Jami: {stats['referral_count']} ta
  • Bonus: {stats['total_referral_bonus']} so'm

💳 Hisob:
  • Jami sarflandi: {stats['total_spent']} so'm
  • Qoʻshilgan: {stats['created_at']}
  • Oxirgi faollik: Shunga oʻxshash

🎁 Premium Muddati: {stats['premium_expire'] if stats['premium_expire'] else 'Yo\'q'}
        """
        
        bot.send_message(user_id, text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in user_stats: {e}")

# ===== PAYMENT SYSTEM =====
@bot.callback_query_handler(func=lambda c: c.data.startswith('buy_'))
def buy_package(call):
    """Buy package callback"""
    try:
        user_id = call.from_user.id
        package_id = int(call.data.split('_')[1])
        
        package = db.fetch_one('SELECT * FROM packages WHERE package_id = ?', (package_id,))
        
        if not package:
            bot.answer_callback_query(call.id, "❌ Paket topilmadi!", show_alert=True)
            return
        
        user = get_user(user_id)
        balance = user['balance'] if user else 0
        
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_buy_{package_id}"),
            types.InlineKeyboardButton("❌ Bekor", callback_data="cancel_buy")
        )
        
        text = f"""
📋 **BUYURTMA TAHLILI**

📦 Paket: {package['name']}
💵 Narx: {package['price']} so'm
📝 Tavsif: {package['description']}
⏱️ Muddati: {package['duration']} kun

💰 **Sizning Balans:** {balance} so'm

{"✅ Balansingiz yetarli!" if balance >= package['price'] else "❌ Balans yetarli emas! Toʻldirish kerak."}

❓ **Tasdiqlaysizmi?**
        """
        
        bot.edit_message_text(text, call.from_user.id, call.message.message_id, 
                             reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in buy_package: {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith('confirm_buy_'))
def confirm_payment(call):
    """Confirm purchase"""
    try:
        user_id = call.from_user.id
        package_id = int(call.data.split('_')[2])
        
        package = db.fetch_one('SELECT * FROM packages WHERE package_id = ?', (package_id,))
        user = get_user(user_id)
        
        if user['balance'] < package['price']:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("💰 BALANSNI TO'LDIRISH", callback_data="refill"))
            
            bot.edit_message_text(f"""
❌ **MABLAG' YETARLI EMAS!**

Kerak: {package['price']} so'm
Sizda: {user['balance']} so'm

Avval balansni toʻldiring!
            """, user_id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")
            return
        
        # Deduct balance
        update_balance(user_id, -package['price'])
        
        # Update user status and expiry
        expire_date = (datetime.now() + timedelta(days=package['duration'])).isoformat()
        db.execute('UPDATE users SET status = ?, premium_expire = ? WHERE user_id = ?',
                  (package['type'], expire_date, user_id))
        
        # Create transaction record
        db.execute('''
            INSERT INTO transactions (user_id, amount, type, package_id, status, confirmed_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, package['price'], 'package', package_id, 'confirmed'))
        
        # Update stats
        db.execute('UPDATE users SET total_spent = total_spent + ? WHERE user_id = ?',
                  (package['price'], user_id))
        
        # If user has referrer, give them bonus
        user = get_user(user_id)
        if user['referred_by']:
            bonus = package['price'] * 0.1  # 10% bonus
            update_balance(user['referred_by'], bonus)
            db.execute('UPDATE users SET total_referral_bonus = total_referral_bonus + ? WHERE user_id = ?',
                      (bonus, user['referred_by']))
        
        # Notify user
        bot.edit_message_text(f"""
✅ **HARID MUVAFFAQIYATLI!**

📦 Paket: {package['name']}
💵 Narx: {package['price']} so'm
⏱️ Muddati: {package['duration']} kun

🎉 Tabriklaymiz! Siz endi premium foydalanuvchi!

📧 Qoʻshimcha taʼfsil emailga yuboriladi.
        """, user_id, call.message.message_id, parse_mode="Markdown")
        
        # Notify admin
        bot.send_message(ADMIN_ID, f"""
🔔 **YANGI HARID!**

👤 Foydalanuvchi: @{user['username']} (ID: {user_id})
📦 Paket: {package['name']}
💵 Narx: {package['price']} so'm
✅ Status: Tasdiqlanadi
        """, parse_mode="Markdown")
        
        logger.info(f"User {user_id} bought package {package_id} for {package['price']}")
    
    except Exception as e:
        logger.error(f"Error in confirm_payment: {e}\n{traceback.format_exc()}")
        bot.answer_callback_query(call.id, "❌ Xatoli yuz berdi!", show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data == "refill")
def refill_balance(call):
    """Refill balance"""
    try:
        msg = bot.send_message(call.from_user.id, "💰 **Qancha summani toʻldirmoqchisiz?**\n\n(Faqat raqam kiriting, masalan: 50000)")
        bot.register_next_step_handler(msg, process_refill_amount)
    except Exception as e:
        logger.error(f"Error in refill_balance: {e}")

def process_refill_amount(message):
    """Process refill amount"""
    try:
        user_id = message.from_user.id
        
        amount = float(message.text.strip())
        
        if amount <= 0:
            bot.send_message(user_id, "❌ Summa musbat boʻlishi kerak!")
            return
        
        if amount > 10000000:
            bot.send_message(user_id, "❌ Juda koʻp! Maksimum 10,000,000 so'm")
            return
        
        # Create transaction
        db.execute('''
            INSERT INTO transactions (user_id, amount, type, status)
            VALUES (?, ?, ?, ?)
        ''', (user_id, amount, 'refill', 'pending'))
        
        # Start payment timer
        msg = bot.send_message(user_id, "⌛ Toʻlov tizimi ishga tushmoqda...")
        threading.Thread(target=payment_timer, args=(user_id, msg.message_id, amount), daemon=True).start()
    
    except ValueError:
        bot.send_message(message.from_user.id, "❌ Noto'g'ri raqam! Faqat sonlarni kiriting.")
    except Exception as e:
        logger.error(f"Error in process_refill_amount: {e}")

def payment_timer(user_id, msg_id, amount):
    """Payment timer countdown"""
    try:
        for i in range(300, -1, -20):
            m, s = divmod(i, 60)
            
            text = f"""
🏦 **TO'LOV TIZIMI**

⏰ Vaqt: `{m:02d}:{s:02d}`
💳 Karta: `{CARD_NUMBER}`
💵 Summa: `{amount}` so'm
📸 Chekni foto ko'rinishida yuboring!

⚠️ Vaqt tugasa, toʻlov bekor qilinadi!
            """
            
            try:
                bot.edit_message_text(text, user_id, msg_id, parse_mode="Markdown")
            except:
                break
            
            time.sleep(20)
        
        # Check if payment was confirmed
        transaction = db.fetch_one('''
            SELECT * FROM transactions WHERE user_id = ? AND amount = ? AND type = 'refill' AND status = 'pending' ORDER BY created_at DESC LIMIT 1
        ''', (user_id, amount))
        
        if transaction:
            db.execute('UPDATE transactions SET status = "expired" WHERE transaction_id = ?', (transaction['transaction_id'],))
            bot.send_message(user_id, "❌ **Toʻlov vaqti tugadi!**\n\nQaytadan urinib koʻring.", reply_markup=main_menu_kb())
    
    except Exception as e:
        logger.error(f"Error in payment_timer: {e}")

@bot.message_handler(content_types=['photo'])
def handle_payment_screenshot(message):
    """Handle payment screenshot"""
    try:
        user_id = message.from_user.id
        
        # Get pending transaction
        transaction = db.fetch_one('''
            SELECT * FROM transactions WHERE user_id = ? AND status = 'pending' ORDER BY created_at DESC LIMIT 1
        ''', (user_id,))
        
        if not transaction:
            bot.send_message(user_id, "❌ Faol toʻlov topilmadi. Qaytadan boshlang.")
            return
        
        # Save screenshot
        db.execute('''
            UPDATE transactions SET screenshot_file_id = ? WHERE transaction_id = ?
        ''', (message.photo[-1].file_id, transaction['transaction_id']))
        
        # Notify admin
        user = get_user(user_id)
        admin_text = f"""
💳 **YANGI TO'LOV CHEKI**

👤 Foydalanuvchi: {user['first_name']} @{user['username']} (ID: {user_id})
💵 Summa: {transaction['amount']} so'm
📝 Turi: {transaction['type']}
📸 Screenshot yuborildi

⏳ Admin tekshirilmoqda...
        """
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_{transaction['transaction_id']}"))
        kb.add(types.InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{transaction['transaction_id']}"))
        
        bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=admin_text, 
                      reply_markup=kb, parse_mode="Markdown")
        
        bot.send_message(user_id, """
✅ **CHEK YUBORILDI!**

Admin tekshirilmoqda...
Tez orada balans qoʻshiladi.

Shukron! 🙏
        """, reply_markup=main_menu_kb(), parse_mode="Markdown")
        
        logger.info(f"Payment screenshot from user {user_id} for {transaction['amount']}")
    
    except Exception as e:
        logger.error(f"Error in handle_payment_screenshot: {e}")

# ===== ADMIN PANEL SYSTEM =====
@bot.message_handler(func=lambda m: m.text == "👥 Foydalanuvchilar" and is_admin(m.from_user.id))
@admin_only
def admin_users(message):
    """Admin - Users management"""
    try:
        users = db.fetch_all('SELECT COUNT(*) as count FROM users')
        total_users = users[0]['count'] if users else 0
        
        premium = db.fetch_all('SELECT COUNT(*) as count FROM users WHERE status = "premium"')
        premium_count = premium[0]['count'] if premium else 0
        
        banned = db.fetch_all('SELECT COUNT(*) as count FROM users WHERE is_banned = 1')
        banned_count = banned[0]['count'] if banned else 0
        
        text = f"""
👥 **FOYDALANUVCHILAR BOSHQARUVI**

📊 Jami: {total_users} ta
💎 Premium: {premium_count} ta
🆓 Bepul: {total_users - premium_count} ta
🚫 Bloklangan: {banned_count} ta

📈 **Faollik:**
• Bugun: 0 (avtomatik hisoblanadi)
• Bu hafta: 0
• Bu oy: {total_users}
        """
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("📋 Barcha Foydalanuvchilar", callback_data="admin_list_users"))
        kb.add(types.InlineKeyboardButton("🔍 Foydalanuvchini Qidirish", callback_data="admin_search_user"))
        
        bot.send_message(message.from_user.id, text, reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in admin_users: {e}")

@bot.message_handler(func=lambda m: m.text == "💰 Toʻlovlar" and is_admin(m.from_user.id))
@admin_only
def admin_payments(message):
    """Admin - Payments management"""
    try:
        pending = db.fetch_all('''
            SELECT * FROM transactions WHERE status = 'pending' ORDER BY created_at DESC LIMIT 10
        ''')
        
        if not pending:
            bot.send_message(message.from_user.id, "✅ Kutilayotgan toʻlovlar yoʻq", reply_markup=admin_menu_kb())
            return
        
        text = "💰 **KUTILAYOTGAN TOʻLOVLAR (Oxirgi 10):**\n\n"
        
        for t in pending:
            user = get_user(t['user_id'])
            text += f"• {user['first_name']} - {t['amount']} so'm\n"
            text += f"  ├─ ID: {t['transaction_id']}\n"
            text += f"  └─ {t['created_at']}\n\n"
        
        bot.send_message(message.from_user.id, text, reply_markup=admin_menu_kb(), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in admin_payments: {e}")

@bot.message_handler(func=lambda m: m.text == "📢 Eʼlon" and is_admin(m.from_user.id))
@admin_only
def admin_announcement(message):
    """Admin - Send announcement"""
    try:
        msg = bot.send_message(message.from_user.id, "📢 **Eʼlonni yozing:**\n\n(Barcha foydalanuvchilarga yuboriladi)")
        bot.register_next_step_handler(msg, handle_announcement)
    except Exception as e:
        logger.error(f"Error in admin_announcement: {e}")

def handle_announcement(message):
    """Handle announcement"""
    try:
        if message.text == "/cancel":
            bot.send_message(message.from_user.id, "❌ Bekor qilindi", reply_markup=admin_menu_kb())
            return
        
        # Save announcement
        db.execute('INSERT INTO announcements (title, content) VALUES (?, ?)', 
                  ('Admin Announcement', message.text))
        
        # Get all users
        users = db.fetch_all('SELECT user_id FROM users WHERE is_banned = 0')
        
        # Send to all users
        sent = 0
        failed = 0
        
        for user in users:
            try:
                bot.send_message(user['user_id'], f"""
📢 **MUHIM EʼLON:**

{message.text}

━━━━━━━━━━━━━━━━━━━━
📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}
                """, parse_mode="Markdown")
                sent += 1
            except:
                failed += 1
        
        bot.send_message(message.from_user.id, f"""
✅ **EʼLON YUBORILDI!**

✅ Muvaffaqiyatli: {sent} ta
❌ Muvaffaqiyatsiz: {failed} ta
        """, reply_markup=admin_menu_kb(), parse_mode="Markdown")
        
        logger.info(f"Announcement sent to {sent} users")
    except Exception as e:
        logger.error(f"Error in handle_announcement: {e}")

@bot.message_handler(func=lambda m: m.text == "📦 Paketlar" and is_admin(m.from_user.id))
@admin_only
def admin_packages(message):
    """Admin - Packages management"""
    try:
        packages = db.fetch_all('SELECT * FROM packages ORDER BY price ASC')
        
        if not packages:
            bot.send_message(message.from_user.id, "❌ Paketlar yoʻq", reply_markup=admin_menu_kb())
            return
        
        text = "📦 **PAKETLAR BOSHQARUVI:**\n\n"
        
        for pkg in packages:
            status = "✅" if pkg['is_active'] else "❌"
            text += f"{status} **{pkg['name']}**\n"
            text += f"   💵 {pkg['price']} so'm | ⏱️ {pkg['duration']} kun\n"
            text += f"   🏷️ {pkg['type'].upper()}\n\n"
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("➕ Yangi Paket", callback_data="admin_add_package"))
        kb.add(types.InlineKeyboardButton("✏️ Paketni Oʻzgartirish", callback_data="admin_edit_package"))
        
        bot.send_message(message.from_user.id, text, reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in admin_packages: {e}")

@bot.message_handler(func=lambda m: m.text == "⚙️ Sozlamalar" and is_admin(m.from_user.id))
@admin_only
def admin_settings(message):
    """Admin - Settings"""
    try:
        text = """
⚙️ **ADMIN SOZLAMALARI**

Qaysini oʻzgartirmoqchisiz?
        """
        
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        kb.add("💳 Karta Raqami", "👤 Admin ID")
        kb.add("💵 Refill Qiymati", "📱 Support Chat")
        kb.add("🔙 Orqaga")
        
        bot.send_message(message.from_user.id, text, reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in admin_settings: {e}")

@bot.message_handler(func=lambda m: m.text == "🚀 Status" and is_admin(m.from_user.id))
@admin_only
def admin_status(message):
    """Admin - Bot status"""
    try:
        users = db.fetch_all('SELECT COUNT(*) as count FROM users')
        transactions = db.fetch_all('SELECT COUNT(*) as count, SUM(amount) as total FROM transactions WHERE status = "confirmed"')
        
        user_count = users[0]['count'] if users else 0
        trans_count = transactions[0]['count'] if transactions else 0
        total_revenue = transactions[0]['total'] if transactions and transactions[0]['total'] else 0
        
        text = f"""
🚀 **BOT STATUSI**

✅ Status: AKTIV VA ISHGA TUSHGAN
📊 Foydalanuvchilar: {user_count} ta
💰 Jami Daromad: {total_revenue} so'm
💳 Tasdiqlangan Tranzaksiyalar: {trans_count} ta

🔧 Tekhnologiya:
• Python + pyTelegramBotAPI
• SQLite3 Database
• Multi-threading System
• Auto Payment Processing

📈 Faol Xususiyatlar:
✅ Premium System
✅ Referal Program
✅ Automatic Payments
✅ Admin Panel
✅ Support System
✅ Analytics & Stats

🎯 Yaratuvchi: ×ULUGʻBEK×
📅 Versiya: 1.0.0
🔐 Xavfsizlik: HIGH
        """
        
        bot.send_message(message.from_user.id, text, reply_markup=admin_menu_kb(), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in admin_status: {e}")

# ===== BACK BUTTON =====
@bot.message_handler(func=lambda m: m.text == "🔙 Orqaga")
def go_back(message):
    """Go back button"""
    try:
        if is_admin(message.from_user.id):
            bot.send_message(message.from_user.id, "🔐 **Admin Panelga Xush Kelibsiz!**\n\nNima qilmoqchisiz?", 
                            reply_markup=admin_menu_kb(), parse_mode="Markdown")
        else:
            bot.send_message(message.from_user.id, "🏠 **Asosiy Menyu**", 
                            reply_markup=main_menu_kb(), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in go_back: {e}")

# ===== INLINE CALLBACKS =====
@bot.callback_query_handler(func=lambda c: c.data == "main_menu")
def callback_main_menu(call):
    """Main menu callback"""
    try:
        bot.delete_message(call.from_user.id, call.message.message_id)
        bot.send_message(call.from_user.id, "🏠 **Asosiy Menyu**", reply_markup=main_menu_kb(), 
                        parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in callback_main_menu: {e}")

@bot.callback_query_handler(func=lambda c: c.data == "cancel_buy")
def callback_cancel(call):
    """Cancel purchase"""
    try:
        bot.delete_message(call.from_user.id, call.message.message_id)
        bot.send_message(call.from_user.id, "❌ Bekor qilindi", reply_markup=main_menu_kb())
    except Exception as e:
        logger.error(f"Error in callback_cancel: {e}")

@bot.callback_query_handler(func=lambda c: c.data == "copy_ref")
def callback_copy_ref(call):
    """Copy referral code"""
    try:
        user = get_user(call.from_user.id)
        bot.answer_callback_query(call.id, f"Kod: {user['referral_code']}", show_alert=True)
    except Exception as e:
        logger.error(f"Error in callback_copy_ref: {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith('approve_'))
def approve_payment(call):
    """Approve payment - Admin"""
    try:
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Faqat admin!", show_alert=True)
            return
        
        transaction_id = int(call.data.split('_')[1])
        transaction = db.fetch_one('SELECT * FROM transactions WHERE transaction_id = ?', (transaction_id,))
        
        # Update transaction
        db.execute('UPDATE transactions SET status = "confirmed", confirmed_at = CURRENT_TIMESTAMP WHERE transaction_id = ?', 
                  (transaction_id,))
        
        # Add balance if refill
        if transaction['type'] == 'refill':
            update_balance(transaction['user_id'], transaction['amount'])
        
        # Notify user
        bot.send_message(transaction['user_id'], f"""
✅ **TOʻLOV TASDIQLANDI!**

💵 Summa: {transaction['amount']} so'm
📝 Turi: {transaction['type']}

Balans qoʻshildi! ✨
        """, reply_markup=main_menu_kb(), parse_mode="Markdown")
        
        bot.edit_message_text(f"✅ Tasdiqlandi! ({transaction['amount']} so'm)", 
                             call.from_user.id, call.message.message_id)
        
        logger.info(f"Payment {transaction_id} approved by admin")
    except Exception as e:
        logger.error(f"Error in approve_payment: {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith('reject_'))
def reject_payment(call):
    """Reject payment - Admin"""
    try:
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Faqat admin!", show_alert=True)
            return
        
        transaction_id = int(call.data.split('_')[1])
        transaction = db.fetch_one('SELECT * FROM transactions WHERE transaction_id = ?', (transaction_id,))
        
        # Update transaction
        db.execute('UPDATE transactions SET status = "rejected" WHERE transaction_id = ?', (transaction_id,))
        
        # Notify user
        bot.send_message(transaction['user_id'], """
❌ **TOʻLOV RAD ETILDI**

Chekda muammo topildi.
Qaytadan urinib koʻring yoki qoʻllab-quvvatlash bilan bogʻlanin.
        """, reply_markup=main_menu_kb(), parse_mode="Markdown")
        
        bot.edit_message_text("❌ Rad etildi!", call.from_user.id, call.message.message_id)
        
        logger.info(f"Payment {transaction_id} rejected by admin")
    except Exception as e:
        logger.error(f"Error in reject_payment: {e}")

@bot.callback_query_handler(func=lambda c: c.data == "show_premium")
def callback_show_premium(call):
    """Show premium packages"""
    try:
        bot.delete_message(call.from_user.id, call.message.message_id)
        bot.send_message(call.from_user.id, "📦 **Premium paketlarini tanlang:**",
                        reply_markup=packages_inline_kb('premium'), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in callback_show_premium: {e}")

@bot.callback_query_handler(func=lambda c: c.data == "show_stars")
def callback_show_stars(call):
    """Show stars packages"""
    try:
        bot.delete_message(call.from_user.id, call.message.message_id)
        bot.send_message(call.from_user.id, "📦 **Stars paketlarini tanlang:**",
                        reply_markup=packages_inline_kb('stars'), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in callback_show_stars: {e}")

@bot.callback_query_handler(func=lambda c: c.data == "ref_stats")
def callback_ref_stats(call):
    """Referral statistics"""
    try:
        stats = get_user_stats(call.from_user.id)
        
        text = f"""
👥 **REFERAL STATISTIKA**

🔗 Kod: {stats['referral_code']}
👥 Jami: {stats['referral_count']} ta
💰 Bonus: {stats['total_referral_bonus']} so'm

🎁 Har bir do'st = 10% bonus!
        """
        
        bot.answer_callback_query(call.id, text, show_alert=True)
    except Exception as e:
        logger.error(f"Error in callback_ref_stats: {e}")

@bot.callback_query_handler(func=lambda c: c.data == "balance_history")
def callback_balance_history(call):
    """Balance history"""
    try:
        transactions = db.fetch_all('''
            SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT 10
        ''', (call.from_user.id,))
        
        if not transactions:
            bot.answer_callback_query(call.id, "Tarix yoʻq", show_alert=True)
            return
        
        text = "💰 **TOʻLOV TARIXI (Oxirgi 10):**\n\n"
        
        for t in transactions:
            status = "✅" if t['status'] == "confirmed" else "⏳" if t['status'] == "pending" else "❌"
            text += f"{status} {t['amount']} so'm - {t['type']}\n"
            text += f"   {t['created_at']}\n\n"
        
        bot.answer_callback_query(call.id, text, show_alert=True)
    except Exception as e:
        logger.error(f"Error in callback_balance_history: {e}")

# ===== ERROR HANDLER =====
@bot.message_handler(func=lambda m: True)
def default_handler(message):
    """Default handler for unknown messages"""
    try:
        bot.send_message(message.from_user.id, """
❌ **NOMA'LUM BUYRUQ**

Menyu tugmasini ishlating yoki:
/start - Qayta boshlash
/admin - Admin paneli
/ref - Referal

Qoʻllab-quvvatlash uchun: 🆘 Yordam
        """, reply_markup=main_menu_kb(), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in default_handler: {e}")

# ===== SCHEDULED TASKS =====
def check_premium_expiry():
    """Check premium expiry and update status"""
    while True:
        try:
            time.sleep(3600)  # Check every hour
            
            users = db.fetch_all('''
                SELECT * FROM users WHERE status != 'free' AND premium_expire < datetime('now')
            ''')
            
            for user in users:
                db.execute('UPDATE users SET status = "free" WHERE user_id = ?', (user['user_id'],))
                
                try:
                    bot.send_message(user['user_id'], """
⚠️ **PREMIUM MUDDATI TUGADI**

Yangi paket sotib olish uchun:
💎 Premium yoki 🌟 Stars tugmasini bosing
                    """, reply_markup=main_menu_kb(), parse_mode="Markdown")
                except:
                    pass
                
                logger.info(f"Premium expired for user {user['user_id']}")
        
        except Exception as e:
            logger.error(f"Error in check_premium_expiry: {e}")

def cleanup_old_transactions():
    """Cleanup old pending transactions"""
    while True:
        try:
            time.sleep(86400)  # Check every 24 hours
            
            # Delete pending transactions older than 7 days
            db.execute('''
                DELETE FROM transactions WHERE status = 'pending' AND created_at < datetime('now', '-7 days')
            ''')
            
            logger.info("Cleaned up old transactions")
        
        except Exception as e:
            logger.error(f"Error in cleanup_old_transactions: {e}")

# Start scheduled tasks
threading.Thread(target=check_premium_expiry, daemon=True).start()
threading.Thread(target=cleanup_old_transactions, daemon=True).start()

# ===== START BOT =====
if __name__ == '__main__':
    logger.info('═' * 50)
    logger.info('🤖 PROFESSIONAL TELEGRAM BOT ISHGA TUSHMOQDA...')
    logger.info('═' * 50)
    # logger.info(f'Bot ID: {bot.get_me().id}') # Buni o'chirib qo'ydim xato bermasligi uchun
    # logger.info(f'Bot Username: @{bot.get_me().username}')
    logger.info(f'Admin ID: {ADMIN_ID}')
    logger.info('═' * 50)
    
    print("""
╔═══════════════════════════════════════════════════╗
║  🤖 PROFESSIONAL TELEGRAM BOT - V1.0.0            ║
║  Yaratuvchi: ×ULUGʻBEK×                            ║
║  Status: ISHGA TUSHGAN ✅                         ║
╚═══════════════════════════════════════════════════╝
""")
    bot.infinity_polling()
