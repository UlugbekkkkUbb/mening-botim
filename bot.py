import os
import sqlite3
import uuid
import logging
import threading
import time
from datetime import datetime, timedelta
from functools import wraps
from contextlib import closing

from dotenv import load_dotenv
from flask import Flask
import telebot
from telebot import types

# ------------------- KONFIGURATSIYA (ENV orqali) -------------------
load_dotenv()

class Config:
    API_TOKEN = os.getenv('API_TOKEN', '8305687409:AAF4-xPc-lwMyJQHcvEFNKxn_nrpWVHBC80')
    ADMIN_ID = int(os.getenv('ADMIN_ID', '7666979987'))
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'IDD_ADMINN')
    CARD_NUMBER = os.getenv('CARD_NUMBER', '9860080195351079')
    CARD_HOLDER = os.getenv('CARD_HOLDER', 'Nargiza Karshiyeva')
    BOT_USERNAME = os.getenv('BOT_USERNAME', 'PREMIUM_STARSS_1BOT')
    DATABASE = os.getenv('DATABASE', 'bot_data.db')

    MIN_TOPUP = 5000
    MAX_TOPUP = 1000000
    REF_BONUS = 500
    PREMIUM_BONUS = 10
    STARS_BONUS = 5
    TOPUP_COMMISSION = 0

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

config = Config()

# ------------------- LOGGING -------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ------------------- DATABASE -------------------
class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with self._get_conn() as conn:
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

    def _get_conn(self):
        return sqlite3.connect(self.db_path, timeout=10)

    def execute(self, query, params=(), fetchone=False, fetchall=False):
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute(query, params)
            conn.commit()
            if fetchone:
                return c.fetchone()
            if fetchall:
                return c.fetchall()
            return c.lastrowid

    def get_user(self, user_id):
        return self.execute("SELECT * FROM users WHERE user_id=?", (user_id,), fetchone=True)

    def create_user(self, user_id, username, first_name, referred_by=None):
        settings = self.get_admin_settings()
        required_premium = settings[9] if settings else 0
        self.execute(
            """INSERT INTO users
               (user_id, username, first_name, referred_by, join_date, last_active, is_required_premium)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, username, first_name, referred_by,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             required_premium)
        )

    def get_admin_settings(self):
        settings = self.execute(
            "SELECT * FROM admin_settings WHERE setting_id=1", fetchone=True
        )
        if not settings:
            self.execute(
                """INSERT INTO admin_settings
                   (setting_id, card_number, card_holder, min_topup, max_topup, ref_commission,
                    premium_commission, stars_commission, topup_commission,
                    required_subscription, subscription_channel, subscription_price)
                   VALUES (1, ?, ?, 5000, 1000000, 500, 10, 5, 0, 0, '', 0)""",
                (config.CARD_NUMBER, config.CARD_HOLDER)
            )
            settings = self.execute(
                "SELECT * FROM admin_settings WHERE setting_id=1", fetchone=True
            )
        return settings

    def update_admin_setting(self, key, value):
        self.execute(f"UPDATE admin_settings SET {key}=? WHERE setting_id=1", (value,))

    def add_referral_bonus(self, referrer_id, referred_user_id, bonus_amount):
        referral_id = str(uuid.uuid4())[:12]
        self.execute(
            """INSERT INTO referral_history
               (referral_id, referrer_id, referred_user_id, bonus_amount, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (referral_id, referrer_id, referred_user_id, bonus_amount,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        self.execute(
            "UPDATE users SET balance=balance+?, referral_income=referral_income+?, referrals=referrals+1 WHERE user_id=?",
            (bonus_amount, bonus_amount, referrer_id)
        )

db = Database(config.DATABASE)

# ------------------- BOT INIT -------------------
bot = telebot.TeleBot(config.API_TOKEN, parse_mode='HTML')
app = Flask(__name__)

# ------------------- DEKORATORLAR -------------------
def user_required(func):
    @wraps(func)
    def wrapper(message_or_call):
        user_id = message_or_call.from_user.id
        user = db.get_user(user_id)
        if not user:
            username = message_or_call.from_user.username or "username_yo'q"
            first_name = message_or_call.from_user.first_name or "Foydalanuvchi"
            db.create_user(user_id, username, first_name)
            user = db.get_user(user_id)
        if user[13]:  # is_banned
            bot.reply_to(message_or_call, "❌ Siz bloklangansiz.")
            return
        return func(message_or_call)
    return wrapper

def admin_only(func):
    @wraps(func)
    def wrapper(message_or_call):
        if message_or_call.from_user.id != config.ADMIN_ID:
            bot.reply_to(message_or_call, "❌ Siz admin emassiz!")
            return
        return func(message_or_call)
    return wrapper

def subscription_required(func):
    @wraps(func)
    def wrapper(message_or_call):
        user_id = message_or_call.from_user.id
        settings = db.get_admin_settings()
        if settings[9]:  # required_subscription
            channel = settings[10]
            if channel and not is_subscribed(user_id, channel):
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("💎 Obuna bo'lish", url=channel))
                bot.reply_to(
                    message_or_call,
                    f"🔒 <b>MAJBURIY OBUNA</b>\n\nBotdan foydalanish uchun quyidagi kanalga obuna bo'ling:\n{channel}",
                    reply_markup=markup
                )
                return
        return func(message_or_call)
    return wrapper

# ------------------- YORDAMCHI FUNKSIYALAR -------------------
def extract_channel_username(channel_url):
    if channel_url.startswith('https://t.me/'):
        return channel_url.replace('https://t.me/', '').split('/')[0]
    return channel_url.replace('@', '')

def is_subscribed(user_id, channel_url):
    try:
        username = extract_channel_username(channel_url)
        member = bot.get_chat_member(chat_id='@' + username, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Subscription check error: {e}")
        return False

def get_main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("💎 Premium", "🌟 Stars")
    markup.add("📦 Paketlar", "💰 Balans")
    markup.add("👥 Pul ishlash", "❓ Yordam")
    markup.add("♻️ Hisob to'ldirish")
    if user_id == config.ADMIN_ID:
        markup.add("⚙️ Admin Panel")
    return markup

def payment_method_markup(order_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Karta orqali", callback_data=f"pay_card_{order_id}"))
    markup.add(types.InlineKeyboardButton("💰 Balansdan", callback_data=f"pay_balance_{order_id}"))
    markup.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data=f"cancel_order_{order_id}"))
    return markup

# ------------------- HANDLERLAR -------------------
@bot.message_handler(commands=['start'])
@user_required
@subscription_required
def start(message):
    user_id = message.from_user.id
    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        referrer_id = int(args[1])
        if referrer_id != user_id:
            referrer = db.get_user(referrer_id)
            if referrer:
                settings = db.get_admin_settings()
                bonus = settings[5]  # ref_commission
                db.add_referral_bonus(referrer_id, user_id, bonus)
                bot.send_message(
                    referrer_id,
                    f"🎉 <b>Yangi referal qo'shildi!</b>\n\n✅ Bonus: +{bonus:,.0f} so'm"
                )
    welcome = f"""
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
    bot.send_message(user_id, welcome, reply_markup=get_main_keyboard(user_id))

@bot.message_handler(func=lambda m: m.text == "💎 Premium")
@user_required
@subscription_required
def premium_menu(message):
    user_id = message.from_user.id
    user = db.get_user(user_id)
    if user[6]:
        bot.send_message(
            user_id,
            f"✅ Siz allaqachon Premium foydalanuvchisiz!\n"
            f"📅 Amal qilish muddati: {user[7] or 'Cheksiz'}"
        )
        return
    text = "<b>💎 PREMIUM PAKETLAR</b>\n\nPaketni tanlang:"
    markup = types.InlineKeyboardMarkup()
    for key, pkg in config.PREMIUM_PRICES.items():
        markup.add(types.InlineKeyboardButton(
            f"{pkg['display']} - {pkg['price']:,} so'm",
            callback_data=f"buy_premium_{key}"
        ))
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
    bot.send_message(user_id, text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🌟 Stars")
@user_required
@subscription_required
def stars_menu(message):
    user_id = message.from_user.id
    user = db.get_user(user_id)
    text = f"<b>⭐ STARS PAKETLARI</b>\n\nSizning stars: {user[8]:,.0f} ⭐\n\nPaketni tanlang:"
    markup = types.InlineKeyboardMarkup()
    for key, pkg in config.STARS_PRICES.items():
        markup.add(types.InlineKeyboardButton(
            f"{pkg['display']} - {pkg['price']:,} so'm",
            callback_data=f"buy_stars_{key}"
        ))
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
    bot.send_message(user_id, text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📦 Paketlar")
@user_required
@subscription_required
def packages(message):
    text = "<b>📦 BARCHA PAKETLAR</b>\n\n"
    text += "<b>💎 Premium:</b>\n"
    for pkg in config.PREMIUM_PRICES.values():
        text += f"  • {pkg['display']} - {pkg['price']:,} so'm\n"
    text += "\n<b>⭐ Stars:</b>\n"
    for pkg in config.STARS_PRICES.values():
        text += f"  • {pkg['display']} - {pkg['price']:,} so'm\n"
    bot.send_message(message.from_user.id, text)

@bot.message_handler(func=lambda m: m.text == "💰 Balans")
@user_required
@subscription_required
def balance(message):
    user_id = message.from_user.id
    user = db.get_user(user_id)
    premium_status = "💎 Premium (Faol)" if user[6] else "📝 Oddiy"
    text = f"""
<b>💰 SIZNING BALANSINGIZ</b>

💵 So'm: {user[3]:,.0f} so'm
⭐ Stars: {user[8]:,.0f}
👥 Referallar: {user[5]}
📊 Jami daromad: {user[9]:,.0f} so'm
👤 Referal income: {user[10]:,.0f} so'm

🆔 ID: <code>{user_id}</code>
📅 Qo'shilgan: {user[11]}
🌟 Status: {premium_status}
    """
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 Yangilash", callback_data="refresh_balance"))
    bot.send_message(user_id, text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "👥 Pul ishlash")
@user_required
@subscription_required
def earn(message):
    user_id = message.from_user.id
    user = db.get_user(user_id)
    settings = db.get_admin_settings()
    bot_username = bot.get_me().username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    text = f"""
<b>👥 PUL ISHLASH</b>

🔗 <b>Referal havolangiz:</b>
<code>{ref_link}</code>

💰 <b>Komissiyalar:</b>
• Har bir taklif: {settings[5]:,.0f} so'm
• Premium sotish: +{settings[6]:,.0f} so'm
• Stars sotish: +{settings[7]:,.0f} so'm

📈 <b>Sizning statistika:</b>
• Referallar: {user[5]}
• Referal income: {user[10]:,.0f} so'm
    """
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📋 Nusxalash", callback_data=f"copy_ref_{user_id}"))
    markup.add(types.InlineKeyboardButton("📊 Referal tarixi", callback_data=f"ref_history_{user_id}"))
    bot.send_message(user_id, text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "❓ Yordam")
@user_required
def help(message):
    settings = db.get_admin_settings()
    text = f"""
<b>❓ YORDAM</b>

<b>Xizmatlar:</b>
💎 Premium - Telegram Premium
⭐ Stars - Telegram Stars
💰 Balans - hisobingiz
👥 Pul ishlash - referal tizimi
♻️ Hisob to'ldirish - balans qo'shish

<b>To'lov usullari:</b>
💳 Karta (UzCard/Humo)
💰 Balansdan yechish
👥 Referal bonus

<b>Admin:</b> @{config.ADMIN_USERNAME}
    """
    bot.send_message(message.from_user.id, text)

@bot.message_handler(func=lambda m: m.text == "♻️ Hisob to'ldirish")
@user_required
@subscription_required
def topup(message):
    text = "<b>♻️ HISOB TO'LDIRISH</b>\n\nTo'lov usulini tanlang:"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Karta orqali", callback_data="topup_card"))
    bot.send_message(message.from_user.id, text, reply_markup=markup)

# ------------------- ADMIN PANEL -------------------
@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Panel")
@admin_only
def admin_panel(message):
    total_users = db.execute("SELECT COUNT(*) FROM users", fetchone=True)[0]
    completed_orders = db.execute("SELECT COUNT(*) FROM orders WHERE status='completed'", fetchone=True)[0]
    total_revenue = db.execute("SELECT SUM(amount) FROM orders WHERE status='completed'", fetchone=True)[0] or 0
    pending = db.execute("SELECT COUNT(*) FROM orders WHERE status IN ('pending', 'pending_check', 'pending_admin')", fetchone=True)[0]
    text = f"""
<b>⚙️ ADMIN PANEL</b>

📊 Statistika:
👥 Foydalanuvchilar: {total_users}
📦 Yakunlangan buyurtmalar: {completed_orders}
💰 Jami daromad: {total_revenue:,.0f} so'm
⏳ Kutilayotgan: {pending}
    """
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("📊 Statistika", "⚙️ Sozlamalar")
    markup.add("📧 Xabar yuborish", "👥 Foydalanuvchilar")
    markup.add("📈 Daromad", "📋 Buyurtmalar")
    markup.add("🔐 Majburiy Obuna", "🔙 Orqaga")
    bot.send_message(message.from_user.id, text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📊 Statistika" and m.from_user.id == config.ADMIN_ID)
@admin_only
def admin_stats(message):
    stats = db.execute(
        """SELECT
            (SELECT COUNT(*) FROM users) as total_users,
            (SELECT COUNT(DISTINCT referred_by) FROM users WHERE referred_by IS NOT NULL) as with_ref,
            (SELECT COUNT(*) FROM orders WHERE status='completed') as completed,
            (SELECT COUNT(*) FROM orders WHERE status='pending' OR status='pending_check' OR status='pending_admin') as pending,
            (SELECT SUM(amount) FROM orders WHERE status='completed') as total_rev,
            (SELECT SUM(amount) FROM orders WHERE product_type='premium' AND status='completed') as premium_rev,
            (SELECT SUM(amount) FROM orders WHERE product_type='stars' AND status='completed') as stars_rev,
            (SELECT SUM(amount) FROM orders WHERE product_type='topup' AND status='completed') as topup_rev,
            (SELECT SUM(bonus_amount) FROM referral_history) as referral_paid
        """, fetchone=True)
    (total_users, with_ref, completed, pending, total_rev, premium_rev, stars_rev, topup_rev, referral_paid) = stats
    text = f"""
<b>📊 BATAFSIL STATISTIKA</b>

👥 Foydalanuvchilar: {total_users}
   Referallar bilan: {with_ref}

📦 Buyurtmalar:
   Yakunlangan: {completed}
   Kutilayotgan: {pending}

💰 Daromad (jami): {total_rev:,.0f} so'm
   Premium: {premium_rev:,.0f}
   Stars: {stars_rev:,.0f}
   Top-up: {topup_rev:,.0f}
   Referal to'langan: {referral_paid:,.0f}
    """
    bot.send_message(message.from_user.id, text)

@bot.message_handler(func=lambda m: m.text == "⚙️ Sozlamalar" and m.from_user.id == config.ADMIN_ID)
@admin_only
def admin_settings(message):
    settings = db.get_admin_settings()
    text = f"""
<b>⚙️ SOZLAMALAR</b>

💳 Karta: <code>{settings[1]}</code>
👤 Egasi: {settings[2]}

🔢 Min to'lov: {settings[3]:,.0f} so'm
🔢 Max to'lov: {settings[4]:,.0f} so'm

💰 Referal bonus: {settings[5]:,.0f} so'm
💰 Premium bonus: {settings[6]:,.0f} so'm
💰 Stars bonus: {settings[7]:,.0f} so'm
💰 Top-up komissiya: {settings[8]:.1f}%

🔐 Majburiy obuna: {'✅' if settings[9] else '❌'} {settings[10] or ''}
    """
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Karta", callback_data="setting_card"))
    markup.add(types.InlineKeyboardButton("🔢 Min/Max", callback_data="setting_minmax"))
    markup.add(types.InlineKeyboardButton("💰 Komissiyalar", callback_data="setting_commission"))
    markup.add(types.InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back"))
    bot.send_message(message.from_user.id, text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📧 Xabar yuborish" and m.from_user.id == config.ADMIN_ID)
@admin_only
def broadcast(message):
    msg = bot.send_message(
        config.ADMIN_ID,
        "<b>📧 XABAR YUBORISH</b>\n\nXabar matnini kiriting (HTML):"
    )
    bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    text = message.text
    sent, failed = 0, 0
    users = db.execute("SELECT user_id FROM users", fetchall=True)
    status_msg = bot.send_message(config.ADMIN_ID, "⏳ Xabar yuborilmoqda...")
    for (user_id,) in users:
        try:
            bot.send_message(user_id, text)
            sent += 1
        except Exception as e:
            logger.error(f"Broadcast to {user_id} failed: {e}")
            failed += 1
        time.sleep(0.05)
    bot.edit_message_text(
        f"✅ Xabar yuborildi\n✔️ Muvaffaqiyatli: {sent}\n❌ Xato: {failed}",
        config.ADMIN_ID, status_msg.message_id
    )

@bot.message_handler(func=lambda m: m.text == "👥 Foydalanuvchilar" and m.from_user.id == config.ADMIN_ID)
@admin_only
def users_list(message):
    users = db.execute(
        "SELECT user_id, username, first_name, balance, is_premium, referrals FROM users ORDER BY join_date DESC LIMIT 30",
        fetchall=True
    )
    text = "<b>👥 SO'NGI 30 FOYDALANUVCHI</b>\n\n"
    for i, (uid, uname, fname, bal, prem, refs) in enumerate(users, 1):
        prem_icon = "💎" if prem else "📝"
        uname = f"@{uname}" if uname else "no username"
        text += f"{i}. {fname} ({uname}) {prem_icon}\n   💰 {bal:,.0f} so'm | 👥 {refs} | 🆔 {uid}\n"
    bot.send_message(config.ADMIN_ID, text)

@bot.message_handler(func=lambda m: m.text == "📈 Daromad" and m.from_user.id == config.ADMIN_ID)
@admin_only
def revenue(message):
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    today_rev = db.execute(
        "SELECT SUM(amount) FROM orders WHERE status='completed' AND created_at LIKE ?", (f"{today}%",), fetchone=True
    )[0] or 0
    week_rev = db.execute(
        "SELECT SUM(amount) FROM orders WHERE status='completed' AND created_at > ?", (week_ago,), fetchone=True
    )[0] or 0
    month_rev = db.execute(
        "SELECT SUM(amount) FROM orders WHERE status='completed' AND created_at > ?", (month_ago,), fetchone=True
    )[0] or 0
    total_rev = db.execute("SELECT SUM(amount) FROM orders WHERE status='completed'", fetchone=True)[0] or 0
    text = f"""
<b>📈 DAROMAD</b>

📅 Bugun: {today_rev:,.0f} so'm
📅 Bu hafta: {week_rev:,.0f} so'm
📅 Bu oy: {month_rev:,.0f} so'm
💰 Jami: {total_rev:,.0f} so'm
    """
    bot.send_message(config.ADMIN_ID, text)

@bot.message_handler(func=lambda m: m.text == "📋 Buyurtmalar" and m.from_user.id == config.ADMIN_ID)
@admin_only
def orders(message):
    orders = db.execute(
        "SELECT order_id, user_id, product_type, amount, status, created_at FROM orders ORDER BY created_at DESC LIMIT 20",
        fetchall=True
    )
    text = "<b>📋 OXIRGI 20 BUYURTMA</b>\n\n"
    for order in orders:
        status_emoji = "✅" if order[4] == "completed" else "⏳" if order[4] in ["pending", "pending_check", "pending_admin"] else "❌"
        text += f"{status_emoji} #{order[0]}\n   👤 {order[1]} | 📦 {order[2].upper()} | 💰 {order[3]:,.0f} so'm | 📅 {order[5][:16]}\n"
    bot.send_message(config.ADMIN_ID, text)

@bot.message_handler(func=lambda m: m.text == "🔐 Majburiy Obuna" and m.from_user.id == config.ADMIN_ID)
@admin_only
def required_subscription_menu(message):
    settings = db.get_admin_settings()
    status = "✅ YOQILGAN" if settings[9] else "❌ O'CHIQ"
    text = f"""
<b>🔐 MAJBURIY OBUNA</b>

Holat: {status}
Kanal: {settings[10] or 'Belgilanmagan'}
Narx: {settings[11]:,.0f} so'm

Buyruqlar:
/sub_on - yoqish
/sub_off - o'chirish
/sub_channel <link> - kanal o'rnatish
/sub_price <sum> - narx o'rnatish
/sub_status - holat
    """
    bot.send_message(config.ADMIN_ID, text)

@bot.message_handler(func=lambda m: m.text == "🔙 Orqaga" and m.from_user.id == config.ADMIN_ID)
@admin_only
def admin_back_to_main(message):
    bot.send_message(config.ADMIN_ID, "👋 Asosiy menyu", reply_markup=get_main_keyboard(config.ADMIN_ID))

# ------------------- BUYRUKLAR (MAJBURIY OBUNA UCHUN) -------------------
@bot.message_handler(commands=['sub_on'])
@admin_only
def sub_on(message):
    db.update_admin_setting('required_subscription', 1)
    settings = db.get_admin_settings()
    if not settings[10]:
        bot.reply_to(message, "⚠️ Kanal linki belgilanmagan! /sub_channel orqali o'rnating.")
        return
    bot.reply_to(message, "✅ Majburiy obuna yoqildi.")

@bot.message_handler(commands=['sub_off'])
@admin_only
def sub_off(message):
    db.update_admin_setting('required_subscription', 0)
    bot.reply_to(message, "✅ Majburiy obuna o'chirildi.")

@bot.message_handler(commands=['sub_channel'])
@admin_only
def sub_channel(message):
    try:
        link = message.text.split()[1]
        if not link.startswith('https://t.me/'):
            bot.reply_to(message, "❌ Link https://t.me/... formatida bo'lishi kerak.")
            return
        db.update_admin_setting('subscription_channel', link)
        bot.reply_to(message, f"✅ Kanal linki o'rnatildi: {link}")
    except IndexError:
        bot.reply_to(message, "❌ Linkni kiriting: /sub_channel https://t.me/kanal")

@bot.message_handler(commands=['sub_price'])
@admin_only
def sub_price(message):
    try:
        price = float(message.text.split()[1])
        db.update_admin_setting('subscription_price', price)
        bot.reply_to(message, f"✅ Narx o'rnatildi: {price:,.0f} so'm")
    except (IndexError, ValueError):
        bot.reply_to(message, "❌ Narxni kiriting: /sub_price 50000")

@bot.message_handler(commands=['sub_status'])
@admin_only
def sub_status(message):
    settings = db.get_admin_settings()
    status = "✅ YOQILGAN" if settings[9] else "❌ O'CHIQ"
    bot.reply_to(
        message,
        f"<b>🔐 Majburiy obuna</b>\n\nStatus: {status}\nKanal: {settings[10] or 'Belgilanmagan'}\nNarx: {settings[11]:,.0f} so'm"
    )

@bot.message_handler(commands=['ban'])
@admin_only
def ban_user(message):
    try:
        uid = int(message.text.split()[1])
        db.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (uid,))
        bot.reply_to(message, f"✅ Foydalanuvchi {uid} bloklandi.")
    except (IndexError, ValueError):
        bot.reply_to(message, "❌ ID kiriting: /ban 123456789")

@bot.message_handler(commands=['unban'])
@admin_only
def unban_user(message):
    try:
        uid = int(message.text.split()[1])
        db.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (uid,))
        bot.reply_to(message, f"✅ Foydalanuvchi {uid} blokdan chiqarildi.")
    except (IndexError, ValueError):
        bot.reply_to(message, "❌ ID kiriting: /unban 123456789")

# ------------------- CALLBACKLAR -------------------
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        data = call.data
        user_id = call.from_user.id

        # Premium sotib olish
        if data.startswith("buy_premium_"):
            product_id = data.replace("buy_premium_", "")
            if product_id not in config.PREMIUM_PRICES:
                bot.answer_callback_query(call.id, "❌ Noto'g'ri paket")
                return
            pkg = config.PREMIUM_PRICES[product_id]
            order_id = str(uuid.uuid4())[:12]
            db.execute(
                """INSERT INTO orders
                   (order_id, user_id, product_type, product_id, amount, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (order_id, user_id, 'premium', product_id, pkg['price'], 'pending',
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            text = f"""
<b>💎 PREMIUM SOTIB OLISH</b>

Paket: {pkg['display']}
Narx: {pkg['price']:,} so'm
Buyurtma ID: <code>{order_id}</code>

To'lov usulini tanlang:
            """
            markup = payment_method_markup(order_id)
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
            bot.answer_callback_query(call.id)

        # Stars sotib olish
        elif data.startswith("buy_stars_"):
            product_id = data.replace("buy_stars_", "")
            if product_id not in config.STARS_PRICES:
                bot.answer_callback_query(call.id, "❌ Noto'g'ri paket")
                return
            pkg = config.STARS_PRICES[product_id]
            order_id = str(uuid.uuid4())[:12]
            db.execute(
                """INSERT INTO orders
                   (order_id, user_id, product_type, product_id, amount, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (order_id, user_id, 'stars', product_id, pkg['price'], 'pending',
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            text = f"""
<b>⭐ STARS SOTIB OLISH</b>

Paket: {pkg['display']}
Narx: {pkg['price']:,} so'm
Stars: {pkg['count']} ⭐
Buyurtma ID: <code>{order_id}</code>

To'lov usulini tanlang:
            """
            markup = payment_method_markup(order_id)
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
            bot.answer_callback_query(call.id)

        # Karta orqali to'lov
        elif data.startswith("pay_card_"):
            order_id = data.replace("pay_card_", "")
            order = db.execute(
                "SELECT amount, product_type FROM orders WHERE order_id=? AND user_id=?",
                (order_id, user_id), fetchone=True
            )
            if not order:
                bot.answer_callback_query(call.id, "❌ Buyurtma topilmadi", show_alert=True)
                return
            amount, product_type = order
            settings = db.get_admin_settings()
            text = f"""
<b>💳 KARTA ORQALI TO'LOV</b>

Summa: {amount:,.0f} so'm
Buyurtma: <code>{order_id}</code>

💳 Karta: <code>{settings[1]}</code>
👤 Egasi: {settings[2]}

To'lovni amalga oshirgach, quyidagi tugmani bosing.
            """
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("✅ To'lov qildim", callback_data=f"confirm_payment_{order_id}"))
            markup.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data=f"cancel_order_{order_id}"))
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
            bot.answer_callback_query(call.id)

        # Balansdan to'lov
        elif data.startswith("pay_balance_"):
            order_id = data.replace("pay_balance_", "")
            order = db.execute(
                "SELECT amount, product_type, product_id FROM orders WHERE order_id=? AND user_id=?",
                (order_id, user_id), fetchone=True
            )
            if not order:
                bot.answer_callback_query(call.id, "❌ Buyurtma topilmadi", show_alert=True)
                return
            amount, product_type, product_id = order
            user = db.get_user(user_id)
            if user[3] < amount:
                bot.answer_callback_query(
                    call.id,
                    f"❌ Balans yetarli emas.\nKerak: {amount:,.0f} so'm\nSizda: {user[3]:,.0f} so'm",
                    show_alert=True
                )
                return
            # Balansdan yechish
            db.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amount, user_id))
            # Buyurtmani yakunlash
            if product_type == 'premium':
                pkg = config.PREMIUM_PRICES[product_id]
                until = (datetime.now() + timedelta(days=30*pkg['months'])).strftime("%Y-%m-%d")
                db.execute("UPDATE users SET is_premium=1, premium_until=? WHERE user_id=?", (until, user_id))
                success = f"✅ Premium ({pkg['display']}) faollashtirildi!"
            elif product_type == 'stars':
                pkg = config.STARS_PRICES[product_id]
                db.execute("UPDATE users SET stars=stars+? WHERE user_id=?", (pkg['count'], user_id))
                success = f"✅ {pkg['display']} qo'shildi!"
            else:
                success = "✅ To'lov amalga oshirildi!"
            db.execute(
                "UPDATE orders SET status='completed', payment_method='balance', completed_at=? WHERE order_id=?",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), order_id)
            )
            bot.edit_message_text(success, call.message.chat.id, call.message.message_id)
            bot.answer_callback_query(call.id, "✅ To'lov muvaffaqiyatli!", show_alert=True)

        # To'lov qildim (chek so'rash)
        elif data.startswith("confirm_payment_"):
            order_id = data.replace("confirm_payment_", "")
            order = db.execute(
                "SELECT status FROM orders WHERE order_id=? AND user_id=?",
                (order_id, user_id), fetchone=True
            )
            if not order or order[0] != 'pending':
                bot.answer_callback_query(call.id, "❌ Buyurtma holati noto'g'ri", show_alert=True)
                return
            db.execute("UPDATE orders SET status='pending_check', payment_method='card' WHERE order_id=?", (order_id,))
            bot.edit_message_text(
                f"✅ To'lov qabul qilindi.\n\nEndi to'lov chekini (skrinshot yoki chek raqamini) yuboring.",
                call.message.chat.id, call.message.message_id
            )
            bot.send_message(user_id, "📸 Iltimos, to'lov chekini yuboring (rasm yoki matn).")
            bot.register_next_step_handler_by_chat_id(user_id, process_check, order_id)
            bot.answer_callback_query(call.id)

        # Buyurtmani bekor qilish
        elif data.startswith("cancel_order_"):
            order_id = data.replace("cancel_order_", "")
            db.execute("UPDATE orders SET status='cancelled' WHERE order_id=? AND user_id=?", (order_id, user_id))
            bot.edit_message_text("❌ Buyurtma bekor qilindi.", call.message.chat.id, call.message.message_id)
            bot.answer_callback_query(call.id)

        # Hisob to'ldirish (karta)
        elif data == "topup_card":
            msg = bot.send_message(
                user_id,
                "<b>♻️ HISOB TO'LDIRISH</b>\n\nSummani kiriting (so'm):\nMin: 5,000 | Max: 1,000,000"
            )
            bot.register_next_step_handler(msg, process_topup_amount)
            bot.answer_callback_query(call.id)

        # Balans yangilash
        elif data == "refresh_balance":
            user = db.get_user(user_id)
            if not user:
                bot.answer_callback_query(call.id, "❌ Foydalanuvchi topilmadi", show_alert=True)
                return
            prem = "💎 Premium (Faol)" if user[6] else "📝 Oddiy"
            text = f"""
<b>💰 BALANS</b>

💵 So'm: {user[3]:,.0f} so'm
⭐ Stars: {user[8]:,.0f}
👥 Referallar: {user[5]}
📊 Jami daromad: {user[9]:,.0f} so'm
👤 Referal income: {user[10]:,.0f} so'm

🆔 ID: <code>{user_id}</code>
📅 Qo'shilgan: {user[11]}
🌟 Status: {prem}
            """
            try:
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id)
            except Exception:
                bot.send_message(user_id, text)
            bot.answer_callback_query(call.id)

        # Referal havolani nusxalash
        elif data.startswith("copy_ref_"):
            bot.answer_callback_query(call.id, "🔗 Havola nusxalandi!", show_alert=True)
            bot_name = bot.get_me().username
            ref_link = f"https://t.me/{bot_name}?start={user_id}"
            bot.send_message(user_id, f"<code>{ref_link}</code>")

        # Referal tarixi
        elif data.startswith("ref_history_"):
            history = db.execute(
                "SELECT referred_user_id, bonus_amount, created_at FROM referral_history WHERE referrer_id=? ORDER BY created_at DESC LIMIT 20",
                (user_id,), fetchall=True
            )
            if not history:
                bot.send_message(user_id, "📭 Hali referal tarixi yo'q.")
            else:
                text = "<b>📊 Referal tarixi:</b>\n\n"
                for ref_id, bonus, date in history:
                    text += f"👤 {ref_id} | 💰 {bonus:,.0f} so'm | 📅 {date[:10]}\n"
                bot.send_message(user_id, text)
            bot.answer_callback_query(call.id)

        # Admin sozlamalari: karta o'zgartirish
        elif data == "setting_card":
            if user_id != config.ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ Ruxsat yo'q", show_alert=True)
                return
            msg = bot.send_message(config.ADMIN_ID, "💳 Yangi karta raqamini kiriting (faqat raqamlar):")
            bot.register_next_step_handler(msg, process_new_card)

        # Admin sozlamalari: min/max
        elif data == "setting_minmax":
            if user_id != config.ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ Ruxsat yo'q", show_alert=True)
                return
            msg = bot.send_message(config.ADMIN_ID, "🔢 Yangi minimal summani kiriting (so'm):")
            bot.register_next_step_handler(msg, process_new_min)

        # Admin sozlamalari: komissiyalar
        elif data == "setting_commission":
            if user_id != config.ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ Ruxsat yo'q", show_alert=True)
                return
            settings = db.get_admin_settings()
            text = f"""
<b>💰 KOMISSIYALAR</b>

1. Referal bonus: {settings[5]:,.0f}
2. Premium bonus: {settings[6]:,.0f}
3. Stars bonus: {settings[7]:,.0f}
4. Top-up komissiya (%): {settings[8]:.1f}

Qaysi birini o'zgartirasiz? (1-4)
            """
            msg = bot.send_message(config.ADMIN_ID, text)
            bot.register_next_step_handler(msg, process_commission_choice)

        # Admin panelga qaytish
        elif data == "admin_back":
            if user_id != config.ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ Ruxsat yo'q", show_alert=True)
                return
            admin_panel(call.message)
            bot.answer_callback_query(call.id)

        # Admin tomonidan buyurtmani tasdiqlash
        elif data.startswith("admin_approve_"):
            if user_id != config.ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ Ruxsat yo'q", show_alert=True)
                return
            order_id = data.replace("admin_approve_", "")
            order = db.execute(
                "SELECT user_id, amount, product_type, product_id FROM orders WHERE order_id=?",
                (order_id,), fetchone=True
            )
            if not order:
                bot.answer_callback_query(call.id, "❌ Buyurtma topilmadi", show_alert=True)
                return
            uid, amount, product_type, product_id = order
            if product_type == 'topup':
                db.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, uid))
                success_text = f"✅ Hisobingiz {amount:,.0f} so'mga to'ldirildi!"
            elif product_type == 'premium':
                pkg = config.PREMIUM_PRICES[product_id]
                until = (datetime.now() + timedelta(days=30*pkg['months'])).strftime("%Y-%m-%d")
                db.execute("UPDATE users SET is_premium=1, premium_until=? WHERE user_id=?", (until, uid))
                success_text = f"✅ Premium ({pkg['display']}) faollashtirildi!"
            elif product_type == 'stars':
                pkg = config.STARS_PRICES[product_id]
                db.execute("UPDATE users SET stars=stars+? WHERE user_id=?", (pkg['count'], uid))
                success_text = f"✅ {pkg['display']} qo'shildi!"
            else:
                success_text = "✅ Buyurtma tasdiqlandi!"
            db.execute(
                "UPDATE orders SET status='completed', completed_at=? WHERE order_id=?",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), order_id)
            )
            bot.send_message(uid, f"<b>✅ Buyurtma tasdiqlandi!</b>\n\n{success_text}")
            bot.edit_message_text(
                f"✅ #{order_id} tasdiqlandi",
                call.message.chat.id, call.message.message_id
            )
            bot.answer_callback_query(call.id, "✅ Tasdiqlandi")

        # Admin tomonidan buyurtmani rad etish
        elif data.startswith("admin_reject_"):
            if user_id != config.ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ Ruxsat yo'q", show_alert=True)
                return
            order_id = data.replace("admin_reject_", "")
            order = db.execute(
                "SELECT user_id FROM orders WHERE order_id=?", (order_id,), fetchone=True
            )
            if not order:
                bot.answer_callback_query(call.id, "❌ Buyurtma topilmadi", show_alert=True)
                return
            uid = order[0]
            db.execute("UPDATE orders SET status='rejected' WHERE order_id=?", (order_id,))
            bot.send_message(uid, f"❌ <b>Buyurtma rad etildi</b>\n\nBuyurtma #{order_id}\nSabab: Chek noto'g'ri yoki to'lov amalga oshmagan.")
            bot.edit_message_text(
                f"❌ #{order_id} rad etildi",
                call.message.chat.id, call.message.message_id
            )
            bot.answer_callback_query(call.id, "❌ Rad etildi")

        # Asosiy menyuga qaytish
        elif data == "back_to_main":
            bot.edit_message_text(
                "<b>🔙 Asosiy menyu</b>",
                call.message.chat.id, call.message.message_id,
                reply_markup=get_main_keyboard(user_id)
            )
            bot.answer_callback_query(call.id)

        else:
            bot.answer_callback_query(call.id, "❌ Noma'lum buyruq")
    except Exception as e:
        logger.exception("Callback error")
        bot.answer_callback_query(call.id, "❌ Xatolik yuz berdi", show_alert=True)

# ------------------- STEP HANDLERLAR -------------------
def process_check(message, order_id):
    user_id = message.from_user.id
    order = db.execute(
        "SELECT status FROM orders WHERE order_id=? AND user_id=?",
        (order_id, user_id), fetchone=True
    )
    if not order or order[0] != 'pending_check':
        bot.send_message(user_id, "❌ Buyurtma topilmadi yoki allaqachon ko'rib chiqilgan.")
        return
    db.execute("UPDATE orders SET status='pending_admin' WHERE order_id=?", (order_id,))
    caption = f"🔔 <b>Yangi to'lov cheki</b>\n\n👤 User: {user_id}\n🆔 Buyurtma: {order_id}"
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"admin_approve_{order_id}"),
        types.InlineKeyboardButton("❌ Rad etish", callback_data=f"admin_reject_{order_id}")
    )
    if message.photo:
        file_id = message.photo[-1].file_id
        bot.send_photo(config.ADMIN_ID, file_id, caption=caption, reply_markup=markup)
    elif message.text:
        caption += f"\n\n{message.text}"
        bot.send_message(config.ADMIN_ID, caption, reply_markup=markup)
    else:
        bot.send_message(user_id, "❌ Noto'g'ri format. Iltimos, rasm yoki matn yuboring.")
        return
    bot.send_message(user_id, "✅ Chek adminga yuborildi. Tez orada tasdiqlanadi.")

def process_topup_amount(message):
    user_id = message.from_user.id
    try:
        amount = float(message.text.strip())
    except:
        bot.send_message(user_id, "❌ Noto'g'ri format. Faqat son kiriting.")
        return
    settings = db.get_admin_settings()
    if amount < settings[3] or amount > settings[4]:
        bot.send_message(
            user_id,
            f"❌ Summa {settings[3]:,.0f} - {settings[4]:,.0f} so'm oralig'ida bo'lishi kerak."
        )
        return
    order_id = str(uuid.uuid4())[:12]
    db.execute(
        """INSERT INTO orders
           (order_id, user_id, product_type, product_id, amount, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (order_id, user_id, 'topup', 'topup', amount, 'pending',
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    text = f"""
<b>💳 KARTA ORQALI TO'LOV</b>

Summa: {amount:,.0f} so'm
Buyurtma: <code>{order_id}</code>

💳 Karta: <code>{settings[1]}</code>
👤 Egasi: {settings[2]}

To'lovni amalga oshirgach, quyidagi tugmani bosing.
    """
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ To'lov qildim", callback_data=f"confirm_payment_{order_id}"))
    markup.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data=f"cancel_order_{order_id}"))
    bot.send_message(user_id, text, reply_markup=markup)

# ------------------- ADMIN SOZLAMALARINI O'ZGARTIRISH STEPLARI -------------------
def process_new_card(message):
    if message.from_user.id != config.ADMIN_ID:
        return
    card = message.text.strip()
    if not card.isdigit():
        bot.send_message(config.ADMIN_ID, "❌ Karta raqami faqat raqamlardan iborat bo'lishi kerak.")
        return
    db.update_admin_setting('card_number', card)
    bot.send_message(config.ADMIN_ID, f"✅ Karta raqami yangilandi: <code>{card}</code>")

def process_new_min(message):
    if message.from_user.id != config.ADMIN_ID:
        return
    try:
        new_min = float(message.text.strip())
    except:
        bot.send_message(config.ADMIN_ID, "❌ Noto'g'ri format.")
        return
    bot.send_message(config.ADMIN_ID, f"Minimal {new_min:,.0f} so'm qilib belgilandi. Endi maksimalni kiriting:")
    bot.register_next_step_handler(message, lambda m: process_new_max(m, new_min))

def process_new_max(message, new_min):
    if message.from_user.id != config.ADMIN_ID:
        return
    try:
        new_max = float(message.text.strip())
    except:
        bot.send_message(config.ADMIN_ID, "❌ Noto'g'ri format.")
        return
    if new_max <= new_min:
        bot.send_message(config.ADMIN_ID, "❌ Maksimal minimaldan katta bo'lishi kerak.")
        return
    db.update_admin_setting('min_topup', new_min)
    db.update_admin_setting('max_topup', new_max)
    bot.send_message(config.ADMIN_ID, f"✅ Yangi chegaralar: {new_min:,.0f} - {new_max:,.0f} so'm")

def process_commission_choice(message):
    if message.from_user.id != config.ADMIN_ID:
        return
    choice = message.text.strip()
    if choice not in ['1','2','3','4']:
        bot.send_message(config.ADMIN_ID, "❌ 1-4 oralig'ida tanlang.")
        return
    prompts = {
        '1': "Yangi referal bonus miqdorini kiriting (so'm):",
        '2': "Yangi premium bonus miqdorini kiriting (so'm):",
        '3': "Yangi stars bonus miqdorini kiriting (so'm):",
        '4': "Yangi top-up komissiya foizini kiriting (masalan 5):"
    }
    msg = bot.send_message(config.ADMIN_ID, prompts[choice])
    bot.register_next_step_handler(msg, lambda m: process_new_commission(m, choice))

def process_new_commission(message, choice):
    if message.from_user.id != config.ADMIN_ID:
        return
    try:
        value = float(message.text.strip())
    except:
        bot.send_message(config.ADMIN_ID, "❌ Noto'g'ri format.")
        return
    field_map = {'1': 'ref_commission', '2': 'premium_commission', '3': 'stars_commission', '4': 'topup_commission'}
    db.update_admin_setting(field_map[choice], value)
    bot.send_message(config.ADMIN_ID, f"✅ Yangilandi: {value}")

# ------------------- FLASK SERVER -------------------
@app.route('/')
def home():
    return "Bot ishlayapti ✅", 200

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# ------------------- BOTNI ISHGA TUSHIRISH -------------------
if __name__ == '__main__':
    logger.info("Bot ishga tushdi...")
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(5)
