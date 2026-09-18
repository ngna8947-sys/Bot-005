# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║     Kairozen All-in-One Bot v4 — カイロゼン                  ║
║     ហាង + SMM Panel · ដាក់លុយ KHQR · Top Up Game Menu       ║
║     Global Discount · Panel Admin · Promo Code              ║
║     Compatible: Python 3.10+ · Termux / Pydroid 3         ║
╚══════════════════════════════════════════════════════════════╝
ដំឡើង:
  pip install pyTelegramBotAPI requests flask qrcode pillow --break-system-packages
"""

import json, logging, time, re, threading, hashlib, io, os, sys, subprocess, datetime
import requests as http_req
import telebot
from telebot.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from flask import Flask, request as flask_request, jsonify
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ─── COLOR CONSTANTS FOR TERMINAL ───
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[91m"
CLR_GREEN   = "\033[92m"
CLR_YELLOW  = "\033[93m"
CLR_BLUE    = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN    = "\033[96m"
CLR_WHITE   = "\033[97m"

BG_RED      = "\033[41m"
BG_GREEN    = "\033[42m"
BG_BLUE     = "\033[44m"

# Custom Colored Formatter for Logging
class ColoredFormatter(logging.Formatter):
    FORMATS = {
        logging.DEBUG:    f"{CLR_CYAN}%(asctime)s{CLR_RESET} [{CLR_BLUE}%(levelname)s{CLR_RESET}] %(message)s",
        logging.INFO:     f"{CLR_CYAN}%(asctime)s{CLR_RESET} [{CLR_GREEN}%(levelname)s{CLR_RESET}] %(message)s",
        logging.WARNING:  f"{CLR_CYAN}%(asctime)s{CLR_RESET} [{CLR_YELLOW}%(levelname)s{CLR_RESET}] %(message)s",
        logging.ERROR:    f"{CLR_CYAN}%(asctime)s{CLR_RESET} [{CLR_RED}%(levelname)s{CLR_RESET}] %(message)s",
        logging.CRITICAL: f"{CLR_CYAN}%(asctime)s{CLR_RESET} [{CLR_BOLD}{CLR_RED}%(levelname)s{CLR_RESET}] %(message)s"
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)

# Setup Logging with Colors
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setFormatter(ColoredFormatter())
logger.addHandler(console_handler)

# ─── Auto-install deps ───
def _ensure_deps():
    pkgs = {"PIL": "pillow", "qrcode": "qrcode"}
    for mod, pkg in pkgs.items():
        try: __import__(mod)
        except ImportError:
            logger.info(f"{CLR_YELLOW}Installing missing package: {pkg}...{CLR_RESET}")
            subprocess.run([sys.executable, "-m", "pip", "install", pkg,
                            "--break-system-packages", "-q"], check=False)
_ensure_deps()

import qrcode
from PIL import Image, ImageDraw, ImageFont

# ═══════════════════════════════════════════════════════════
#  CONFIG  — ដូរតម្លៃទាំងនេះ
# ═══════════════════════════════════════════════════════════
BOT_TOKEN          = "8914728102:AAEuRtEGUtF-kg5tjs_mrD-vYew89dyoxBI"
ADMIN_ID           = 8807182741

# Bakong KHQR (deposit ទាំង Store + SMM)
BAKONG_TOKEN       = "rbkMVUSQPooaey51jm1cD5ECnzmHyeNX7fBX4Afc16GU8k"
BANK_ACCOUNT       = "samnang_mon@bkrt"
MERCHANT_NAME      = "Khmer SMM"
MERCHANT_CITY      = "Phnom Penh"

DEPOSIT_EXPIRE_SEC = 180   # 20 minutes
POLL_INTERVAL      = 5
STOCK_ALERT_MIN    = 5

# ═══════════════════════════════════════════════════════════
#  FILES
# ═══════════════════════════════════════════════════════════
WALLETS_FILE    = "aio_wallets.json"
USERS_FILE      = "aio_users.json"
LANG_FILE       = "aio_lang.json"
PROMO_FILE      = "aio_promos.json"
SETTINGS_FILE   = "aio_settings.json"
DISCOUNT_FILE   = "aio_discount.json"   # Global Discount File[cite: 1]

PRODUCTS_FILE   = "aio_products.json"
ORDERS_FILE     = "aio_orders.json"
STOCK_FILE      = "aio_stock.json"
STORE_DEP_FILE  = "aio_store_deposits.json"
SEEN_TXN_FILE   = "aio_seen_txn.json"

SMM_API_FILE    = "aio_smm_api.json"
SMM_SVC_FILE    = "aio_smm_services.json"
SMM_ORD_FILE    = "aio_smm_orders.json"
SMM_PROFIT_FILE = "aio_smm_profit.json"
SMM_POLL_FILE   = "aio_smm_poll.json"

def _load(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    except: return default

def _save(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e: logger.error(f"{CLR_RED}Save {path}: {e}{CLR_RESET}")

# ─── Load all state ───
wallets         = _load(WALLETS_FILE,   {})
users_db        = _load(USERS_FILE,     {})
user_lang       = _load(LANG_FILE,      {})
promos          = _load(PROMO_FILE,     {})
settings        = _load(SETTINGS_FILE,  {})
discount_config = _load(DISCOUNT_FILE,  {"active": False, "pct": 0})

products        = _load(PRODUCTS_FILE,  [])
orders          = _load(ORDERS_FILE,    {})
stock           = _load(STOCK_FILE,     {})
store_deps      = _load(STORE_DEP_FILE, {})
seen_txn        = set(_load(SEEN_TXN_FILE, []))

smm_api         = _load(SMM_API_FILE,   {"url": "", "key": ""})
smm_services    = _load(SMM_SVC_FILE,   {})
smm_orders      = _load(SMM_ORD_FILE,   {})
smm_profit      = _load(SMM_PROFIT_FILE,{"pct": 20})
smm_poll        = _load(SMM_POLL_FILE,  {"interval": POLL_INTERVAL})

waiting         = {}   # uid -> step/dict
lang_cooldown   = {}

# Default products if empty
if not products:
    products = [
        {"id": "capcutpro", "name": "CapCut Pro", "icon": "✂️",
         "desc": "CapCut Pro · Auto Re-new · Auto-deliver",
         "plans": [{"label":"1 ខែ","price":1.50},{"label":"3 ខែ","price":4.50},{"label":"12 ខែ","price":14}]},
        {"id": "netflix", "name": "Netflix Premium", "icon": "🎬",
         "desc": "Netflix Premium 4K · Auto-deliver · 1 Screen",
         "plans": [{"label":"1 ខែ","price":2.50},{"label":"3 ខែ","price":4.99},{"label":"12 ខែ","price":25.99}]},
        {"id": "freefire", "name": "Free Fire Diamonds", "icon": "💎",
         "desc": "Free Fire Top Up · Manual/Auto Delivery via Player ID",
         "plans": [
             {"label": "100 Diamonds", "price": 1.00},
             {"label": "310 Diamonds", "price": 3.00},
             {"label": "520 Diamonds", "price": 5.00}
         ]},
    ]
    _save(PRODUCTS_FILE, products)

# ═══════════════════════════════════════════════════════════
#  BOT + HTTP
# ═══════════════════════════════════════════════════════════
bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

def _make_session():
    s = http_req.Session()
    r = Retry(total=3, backoff_factor=2, status_forcelist=[500,502,503,504])
    a = HTTPAdapter(max_retries=r)
    s.mount("http://", a); s.mount("https://", a)
    return s
http = _make_session()

# ═══════════════════════════════════════════════════════════
#  LANGUAGE
# ═══════════════════════════════════════════════════════════
STRINGS = {
    "kh": {
        "welcome": (
            "👋 សូស្ដីមក <b>Kairozen カイロゼン</b>!\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🌟 Bot នេះផ្ដល់សេវាកម្ម:\n"
            "🛍️ ទិញផលិតផលឌីជីថល & Top Up Game\n"
            "📊 សេវា SMM (Followers/Likes)\n"
            "💳 បញ្ចូលលុយ · ប្រវត្តិ · ជំនួយ\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "💰 សាច់ប្រាក់: <b>${:.2f}</b>"
        ),
        "select_lang":   "🌐 ជ្រើសរើសភាសា:",
        "lang_set":      "✅ ភាសាត្រូវបានផ្លាស់ប្ដូរ!",
        "menu":          "🏠 ត្រឡប់ Menu ដើម",
        "banned":        "🚫 គណនីរបស់អ្នកត្រូវបាន ban!",
        "cancel_ok":     "🏠 Menu",
        "no_service":    "❌ គ្មាន SMM Service ទេ",
        "choose_platform": "ជ្រើស Platform:",
        "choose_qty":    "ជ្រើស ចំនួន:",
        "send_link":     "ផ្ញើ Link របស់អ្នក:",
        "low_balance":   "❌ លុយមិនគ្រប់!",
        "order_done":    "✅ បញ្ជាទិញបានជោគជ័យ!",
        "deposit_ok":    "✅ ដាក់លុយបានជោគជ័យ!",
        "qr_expired":    "⏰ QR ផុតកំណត់! សូម top up ម្ដងទៀត",
        "qr_error":      "⚠️ QR Generate Error! ទំនាក់ Admin",
        "order_notfound":"❌ Order រកមិនឃើញ!",
        "no_orders":     "❌ គ្មាន Order ទេ!",
        "how_to_use": (
            "💡 <b>របៀបប្រើប្រាស់</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ ចុច <b>💳 ដាក់ប្រាក់</b> → ជ្រើស ចំនួន → Scan QR\n"
            "2️⃣ ចុច <b>🛍️ ហាងឌីជីថល</b> → ជ្រើស ផលិតផល → Plan → ទូទាត់\n"
            "3️⃣ ចុច <b>💎 ថុបអាប់ហ្គេម</b> → ជ្រើសកញ្ចប់ → បញ្ចូល Player ID\n"
            "4️⃣ ចុច <b>📊 សេវាកម្ម SMM</b> → Platform → សេវា → ចំនួន → ផ្ញើ Link"
        ),
        "support_msg": (
            "💬 <b>ជំនួយ</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📞 Admin: https://t.me/KhmerSMM007\n"
            "🌐 Channel: "
        ),
        "fallback": "❓ ប្រើ Menu ខាងក្រោម",
    },
    "en": {
        "welcome": (
            "👋 Welcome to <b>Kairozen カイロゼン</b>!\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🌟 Services available:\n"
            "🛍️ Buy Digital Products & Game Top Up\n"
            "📊 SMM Services (Followers/Likes)\n"
            "💳 Top Up · History · Support\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "💰 Balance: <b>${:.2f}</b>"
        ),
        "select_lang":   "🌐 Select Language:",
        "lang_set":      "✅ Language changed!",
        "menu":          "🏠 Back to Menu",
        "banned":        "🚫 Your account has been banned!",
        "cancel_ok":     "🏠 Menu",
        "no_service":    "❌ No SMM Services available",
        "choose_platform": "Choose Platform:",
        "choose_qty":    "Choose Quantity:",
        "send_link":     "Send your Link:",
        "low_balance":   "❌ Insufficient balance!",
        "order_done":    "✅ Order placed successfully!",
        "deposit_ok":    "✅ Deposit successful!",
        "qr_expired":    "⏰ QR expired! Please top up again",
        "qr_error":      "⚠️ QR Generate Error! Contact Admin",
        "order_notfound":"❌ Order not found!",
        "no_orders":     "❌ No orders yet!",
        "how_to_use": (
            "💡 <b>How to Use</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ Tap <b>💳 Top Up</b> → Choose Amount → Scan QR\n"
            "2️⃣ Tap <b>🛍️ Shop</b> → Choose Product → Plan → Pay\n"
            "3️⃣ Tap <b>💎 Game Top Up</b> → Choose Package → Enter Player ID\n"
            "4️⃣ Tap <b>📊 SMM Services</b> → Platform → Service → Qty → Send Link"
        ),
        "support_msg": (
            "💬 <b>Support</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📞 Admin: @KhmerSmm099\n"
            "🌐 Channel: @KhmerSmm099"
        ),
        "fallback": "❓ Use the menu below",
    },
}

def get_lang(uid): return user_lang.get(str(uid), "kh")

def t(uid, key, *args):
    lang = get_lang(uid)
    s = STRINGS.get(lang, STRINGS["kh"]).get(key) or STRINGS["kh"].get(key, key)
    if args:
        try: return s.format(*args)
        except: return s
    return s

def toggle_lang(uid):
    uid_str = str(uid)
    now = time.time()
    if now - lang_cooldown.get(uid_str, 0) < 3.0: return
    lang_cooldown[uid_str] = now
    cycle = {"kh": "en", "en": "kh"}
    user_lang[uid_str] = cycle.get(get_lang(uid), "kh")
    _save(LANG_FILE, user_lang)

def lang_flag(uid):
    return {"kh": "🇰🇭 ខ្មែរ", "en": "🇬🇧 English"}.get(get_lang(uid), "🇰🇭")

# ═══════════════════════════════════════════════════════════
#  WALLET & DISCOUNT HELPERS
# ═══════════════════════════════════════════════════════════
def bal(uid): return float(wallets.get(str(uid), 0))
def add_bal(uid, amt):
    wallets[str(uid)] = round(bal(uid) + amt, 2)
    _save(WALLETS_FILE, wallets)
def ded_bal(uid, amt):
    wallets[str(uid)] = max(0, round(bal(uid) - amt, 2))
    _save(WALLETS_FILE, wallets)
def set_bal(uid, amt):
    wallets[str(uid)] = round(float(amt), 2)
    _save(WALLETS_FILE, wallets)

def _calc_discounted_price(price):
    if discount_config.get("active", False):
        pct = float(discount_config.get("pct", 0))
        return round(price * (1 - pct / 100), 2)
    return price

# ═══════════════════════════════════════════════════════════
#  PROMO CODE
# ═══════════════════════════════════════════════════════════
def apply_promo(uid, code, amount):
    code = code.strip().upper()
    p = promos.get(code)
    if not p: return amount, 0, "❌ Promo Code ខុស!"
    if p.get("uses", 0) > 0 and p.get("used", 0) >= p["uses"]:
        return amount, 0, "❌ Promo Code ផុតសិទ្ធហើយ!"
    user_used = p.get("user_used", {})
    if str(uid) in user_used:
        return amount, 0, "❌ អ្នកបានប្រើ Promo Code នេះហើយ!"
    if p.get("pct", False):
        discount = round(amount * float(p["discount"]) / 100, 2)
    else:
        discount = min(float(p["discount"]), amount)
    final = max(0, round(amount - discount, 2))
    return final, discount, None

def confirm_promo(code, uid):
    code = code.strip().upper()
    p = promos.get(code)
    if not p: return
    p["used"] = p.get("used", 0) + 1
    uu = p.get("user_used", {})
    uu[str(uid)] = 1
    p["user_used"] = uu
    _save(PROMO_FILE, promos)

# ═══════════════════════════════════════════════════════════
#  KEYBOARDS (Added Game Top Up button on main menu)
# ═══════════════════════════════════════════════════════════
def main_kb(uid=None):
    lang = get_lang(uid) if uid else "kh"
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    if lang == "en":
        kb.row("🛍️ Shop",          "💎 Game Top Up")
        kb.row("📊 SMM Services",  "📦 Orders")
        kb.row("💳 Top Up",        "👜 Wallet",         "📜 History")
        kb.row("💬 Support",       "💡 How to Use",    "🌐 Language")
    else:
        kb.row("🛍️ ហាងឌីជីថល",    "💎 ថុបអាប់ហ្គេម")
        kb.row("📊 សេវាកម្ម SMM",  "📦 ការបញ្ជាទិញ")
        kb.row("💳 ដាក់ប្រាក់",    "👜 កាបូបលុយ",      "📜 ប្រវត្តិ")
        kb.row("💬 ជំនួយ Support", "💡 របៀបប្រើប្រាស់", "🌐 ភាសា / Language")
    return kb

def admin_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🛍️ ផលិតផល",       "📦 ការបញ្ជាទិញ")
    kb.row("📦 ស្តុក",         "➕ បន្ថែមស្តុក",    "➕ បន្ថែមផលិតផល")
    kb.row("➕ បន្ថែមគ្រប់សេវាកម្ម", "🔥 បញ្ចុះតម្លៃទាំងអស់")
    kb.row("✏️ កែតម្លៃ",       "💳 ប្រាក់បញ្ញើ")
    kb.row("━━━ 📊 SMM ━━━")
    kb.row("📊 ការបញ្ជា SMM",  "⚙️ កំណត់ SMM API")
    kb.row("➕ បន្ថែម SMM",    "🗑️ លុប SMM")
    kb.row("💹 ប្រាក់ចំណេញ SMM")
    kb.row("━━━ 💰 ហិរញ្ញវត្ថុ ━━━")
    kb.row("💰 កាបូបលុយ",      "💰 ឆែកលុយ API")
    kb.row("💸 បន្ថែមប្រាក់",   "💔 កាត់ប្រាក់")
    kb.row("━━━ 👥 អ្នកប្រើ ━━━")
    kb.row("👥 អ្នកប្រើប្រាស់",  "📊 ស្ថិតិ")
    kb.row("🎟️ លេខកូដPromo",   "📢 ផ្សព្វផ្សាយ")
    kb.row("⏱ ល្បឿន Poll",     "🔄 ធ្វើឱ្យទាន់សម័យ")
    return kb

def cancel_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("✕ Cancel")
    return kb

def lang_select_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇰🇭 ខ្មែរ", callback_data="setlang:kh"),
         InlineKeyboardButton("🇬🇧 English", callback_data="setlang:en")]
    ])

def deposit_amt_kb(uid=None, promo_code=None):
    lang = get_lang(uid) if uid else "kh"
    amts = [1, 2, 5, 10, 20, 50]
    btns = []
    row = []
    for a in amts:
        row.append(InlineKeyboardButton(f"${a}", callback_data=f"dep:{a}"))
        if len(row) == 3:
            btns.append(row); row = []
    if row: btns.append(row)
    btns.append([InlineKeyboardButton(
        "✏️ ផ្ទាល់ខ្លួន" if lang=="kh" else "✏️ Custom",
        callback_data="dep:custom")])
    if promo_code:
        btns.append([InlineKeyboardButton(
            f"🎟️ Promo: {promo_code} ✅", callback_data="dep:clrpromo")])
    else:
        btns.append([InlineKeyboardButton(
            "🎟️ ដាក់ Promo Code" if lang=="kh" else "🎟️ Enter Promo Code",
            callback_data="dep:promo")])
    return InlineKeyboardMarkup(btns)

def smm_cat_kb():
    PLATFORM_ICONS = {
        "tiktok": "🎵", "telegram": "📱", "facebook": "📘",
        "instagram": "📸", "youtube": "▶️", "twitter": "🐦",
        "x": "🐦", "threads": "🧵"
    }
    cats = _smm_get_categories()
    btns = []
    for cat in cats:
        icon = "📱"
        for key, ico in PLATFORM_ICONS.items():
            if key in cat.lower(): icon = ico; break
        btns.append([InlineKeyboardButton(f"{icon}  {cat}", callback_data=f"smmcat:{cat}")])
    btns.append([InlineKeyboardButton("🔙 Back", callback_data="back:main")])
    return InlineKeyboardMarkup(btns)

def smm_svc_kb(cat):
    SVC_ICONS = {
        "follower":"👤","like":"❤️","view":"👁","comment":"💬",
        "share":"🔗","save":"🔖","member":"👥","subscriber":"🔔",
        "watch":"👀","reaction":"😍",
    }
    svcs = _smm_get_svcs_in_cat(cat)
    btns = []
    for slug, s in svcs:
        label = s.get("label", slug)
        icon = "⚡"
        for key, ico in SVC_ICONS.items():
            if key in label.lower(): icon = ico; break
        btns.append([InlineKeyboardButton(f"{icon}  {label}", callback_data=f"smmsvc:{slug}")])
    btns.append([InlineKeyboardButton("🔙 Back", callback_data="back:smmcats")])
    return InlineKeyboardMarkup(btns)

def smm_qty_kb(slug, s):
    sr   = _smm_sell_rate(s["cost_rate"], slug)
    mn   = s.get("min", 100)
    mx   = s.get("max", 100000)
    label= s.get("label", slug)
    first= label.split()[0] if label else slug
    preset = s.get("preset_qtys")
    if preset and isinstance(preset, list):
        qtys = [q for q in preset if mn <= q <= mx]
    else:
        suggestions = [100, 500, 1000, 5000, 10000, 50000]
        qtys = []
        for q in [mn] + suggestions:
            if mn <= q <= mx and q not in qtys: qtys.append(q)
            if len(qtys) >= 6: break
    btns = []
    for q in qtys:
        price = sr * q / 1000
        btns.append([InlineKeyboardButton(
            f"{q:,} {first} — ${price:.2f}", callback_data=f"smmqty:{slug}:{q}")])
    btns.append([InlineKeyboardButton("🔙 Back", callback_data="back:smmcats")])
    return InlineKeyboardMarkup(btns)

def products_kb():
    btns = []
    for p in products:
        if p["id"] == "freefire": continue  # Exclude from normal shop if shown separately
        total = sum(
            len(stock.get(_stock_key(p["id"], i), []))
            for i in range(len(p.get("plans", [])))
        ) or len(stock.get(p["id"], []))
        label = f"{p.get('icon','📦')} {p['name']}"
        if total == 0:
            label += "  ❌ អស់"
        btns.append([InlineKeyboardButton(label, callback_data=f"prod:{p['id']}")])
    btns.append([InlineKeyboardButton("🔙 Back", callback_data="back:main")])
    return InlineKeyboardMarkup(btns)

def plans_kb(prod_id):
    p = _get_product(prod_id)
    if not p: return InlineKeyboardMarkup([])
    btns = []
    for i, plan in enumerate(p.get("plans", [])):
        cnt = _get_plan_stock_count(prod_id, i)
        orig_price = float(plan['price'])
        final_price = _calc_discounted_price(orig_price)
        
        if discount_config.get("active", False):
            price_str = f"<s>${orig_price:.2f}</s> <b>${final_price:.2f}</b> 🔥"
        else:
            price_str = f"<b>${orig_price:.2f}</b>"

        if prod_id == "freefire":
            label = f"✅ {plan['label']} — {price_str}"
            btns.append([InlineKeyboardButton(label, callback_data=f"plan:{prod_id}:{i}")])
        else:
            if cnt == 0:
                label = f"❌ {plan['label']} — {price_str}  [អស់]"
                btns.append([InlineKeyboardButton(label, callback_data=f"plan_oos:{prod_id}:{i}")])
            else:
                label = f"✅ {plan['label']} — {price_str}"
                btns.append([InlineKeyboardButton(label, callback_data=f"plan:{prod_id}:{i}")])
    btns.append([InlineKeyboardButton("🔙 Back", callback_data="back:shop")])
    return InlineKeyboardMarkup(btns)

# ═══════════════════════════════════════════════════════════
#  PRODUCT HELPERS
# ═══════════════════════════════════════════════════════════
def _get_product(pid):
    for p in products:
        if p["id"] == pid: return p
    return None

def _stock_key(pid, plan_idx=None):
    if plan_idx is not None:
        return f"{pid}__{plan_idx}"
    return pid

def _get_stock(pid, plan_idx=None):
    key = _stock_key(pid, plan_idx)
    if plan_idx is not None and key in stock:
        return stock.get(key, [])
    if plan_idx is not None:
        return stock.get(pid, [])
    return stock.get(pid, [])

def _get_plan_stock_count(pid, plan_idx):
    key = _stock_key(pid, plan_idx)
    return len(stock.get(key, []))

def _pop_stock(pid, plan_idx=None):
    key = _stock_key(pid, plan_idx)
    s = stock.get(key)
    if s is None and plan_idx is not None:
        s = stock.get(pid, [])
        key = pid
    if not s:
        return None
    item = s.pop(0)
    stock[key] = s
    _save(STOCK_FILE, stock)
    return item

# ═══════════════════════════════════════════════════════════
#  SMM HELPERS
# ═══════════════════════════════════════════════════════════
def _smm_get_categories():
    cats = []
    for s in smm_services.values():
        c = s.get("category", "Other")
        if c not in cats: cats.append(c)
    return cats

def _smm_get_svcs_in_cat(cat):
    return [(slug, s) for slug, s in smm_services.items() if s.get("category") == cat]

def _smm_profit_pct(): return float(smm_profit.get("pct", 20))

def _smm_sell_rate(cost, slug=None):
    s = smm_services.get(slug, {})
    if s.get("custom_price"): 
        base_price = float(s["custom_price"])
    else:
        base_price = round(float(cost) * (1 + _smm_profit_pct() / 100), 4)
    return _calc_discounted_price(base_price)

def _smm_api_post(params, timeout=25):
    url = smm_api.get("url", "")
    if not url: return None
    try:
        r = http.post(url, data=params, timeout=timeout)
        return r.json()
    except Exception as e:
        logger.error(f"{CLR_RED}SMM API: {e}{CLR_RESET}"); return None

def _smm_fetch_service(api_id):
    key = smm_api.get("key", "")
    url = smm_api.get("url", "")
    if not key or not url: return None
    try:
        r = http.post(url, data={"key": key, "action": "services"}, timeout=20)
        for s in r.json():
            if str(s.get("service")) == str(api_id):
                return {
                    "cost_rate": s.get("rate", s.get("min", "0")),
                    "min": int(s.get("min", 100)),
                    "max": int(s.get("max", 100000)),
                    "raw_name": s.get("name", ""),
                }
    except Exception as e: logger.error(f"{CLR_RED}Fetch service: {e}{CLR_RESET}")
    return None

def _smm_clean_name(raw):
    raw = re.sub(r'\s*\[.*?\]\s*', ' ', raw)
    raw = re.sub(r'\s*\(.*?\)\s*', ' ', raw)
    return re.sub(r'\s+', ' ', raw).strip()[:60]

def _smm_service_list_text():
    if not smm_services: return "❌ គ្មាន Service ទេ"
    lines = ["<b>📋 SMM Services</b>\n━━━━━━━━━━━━━━━━━━"]
    for cat in _smm_get_categories():
        lines.append(f"\n📂 <b>{cat}</b>")
        for slug, s in _smm_get_svcs_in_cat(cat):
            sr = _smm_sell_rate(s["cost_rate"], slug)
            lines.append(f"  • {s.get('label',slug)} — ${sr:.2f}/1K")
    return "\n".join(lines)

# ═══════════════════════════════════════════════════════════
#  BAKONG KHQR
# ═══════════════════════════════════════════════════════════
def _generate_khqr(uid, amount, note=""):
    try:
        from bakong_khqr import KHQR
        k = KHQR(BAKONG_TOKEN)
        qr_str = k.create_qr(
            bank_account  = BANK_ACCOUNT,
            merchant_name = MERCHANT_NAME,
            merchant_city = MERCHANT_CITY,
            amount        = round(float(amount), 2),
            currency      = "USD",
            bill_number   = (note or f"uid{uid}")[:25],
            static        = False,
        )
        return qr_str or ""
    except Exception as e:
        logger.error(f"{CLR_RED}[_generate_khqr] ❌ {e}{CLR_RESET}")
    return ""

def _check_bakong(md5, amount, start_ts):
    try:
        from bakong_khqr import KHQR as _BK
        k = _BK(BAKONG_TOKEN)
        status = k.check_payment(str(md5))
        return status == "PAID"
    except Exception as e:
        logger.error(f"{CLR_RED}[_check_bakong] {e}{CLR_RESET}")
    return False

def _watch_deposit(uid, uid_str, dep_id, amount, start_ts):
    deadline = time.time() + DEPOSIT_EXPIRE_SEC + 60
    while time.time() < deadline:
        dep = store_deps.get(dep_id)
        if not dep or dep.get("status") != "pending": return
        md5 = dep.get("md5", "")
        if _check_bakong(md5, amount, start_ts):
            bonus = float(dep.get("bonus", 0))
            total_credit = round(amount + bonus, 2)
            add_bal(uid, total_credit)
            store_deps[dep_id]["status"] = "confirmed"
            _save(STORE_DEP_FILE, store_deps)
            new_b = bal(uid)
            msg = (f"✅ <b>ដាក់លុយបានជោគជ័យ!</b>\n"
                   f"━━━━━━━━━━━━━━━━━━\n"
                   f"💰 បញ្ញើ: <b>${amount:.2f}</b>")
            if bonus > 0:
                msg += f"\n🎟️ Promo Bonus: <b>+${bonus:.2f}</b>"
            msg += (f"\n💳 Balance: <b>${new_b:.2f}</b>")
            try:
                bot.send_message(uid, msg, parse_mode="HTML", reply_markup=main_kb(uid))
            except: pass
            try:
                bot.send_message(ADMIN_ID,
                    f"💰 <b>ដាក់លុយ ✅ (Auto)</b>\n👤 <code>{uid_str}</code>\n"
                    f"💰 ${amount:.2f}" + (f" + Bonus ${bonus:.2f}" if bonus>0 else ""),
                    parse_mode="HTML")
            except: pass
            return
        time.sleep(POLL_INTERVAL)
    dep = store_deps.get(dep_id)
    if dep and dep.get("status") == "pending":
        dep["status"] = "expired"; _save(STORE_DEP_FILE, store_deps)
        try: bot.send_message(uid, "⏰ <b>QR ផុតកំណត់!</b> សូម top up ម្ដងទៀត", parse_mode="HTML")
        except: pass

def _send_deposit_qr(uid, amount, promo_code=None, label="💳 ដាក់ប្រាក់", bonus=0.0, promo_code_name=None):
    uid_str = str(uid)
    final_amount = amount
    discount = 0
    promo_applied = promo_code_name
    if promo_code and not promo_applied:
        fa, dc, err = apply_promo(uid, code=promo_code, amount=amount)
        if not err:
            final_amount = fa; discount = dc; promo_applied = promo_code

    qr_str = _generate_khqr(uid, final_amount, f"uid={uid} ${final_amount}")
    if not qr_str:
        bot.send_message(uid, "⚠️ មានបញ្ហា Generate QR! ទំនាក់ Admin", parse_mode="HTML")
        return

    try:
        from bakong_khqr import KHQR as _BK
        k = _BK(BAKONG_TOKEN)
        md5_hash = k.generate_md5(qr_str)
    except Exception as e:
        import hashlib
        md5_hash = hashlib.md5(qr_str.encode()).hexdigest()

    dep_id   = f"dep_{uid}_{int(time.time())}"
    start_ts = int(time.time())
    total_credit = round(final_amount + bonus, 2)

    store_deps[dep_id] = {
        "uid": uid_str, "amount": final_amount, "status": "pending",
        "bonus": bonus, "promo": promo_applied or "",
        "md5": md5_hash, "qr_str": qr_str,
    }
    _save(STORE_DEP_FILE, store_deps)

    cap = (f"{label}\n"
           f"━━━━━━━━━━━━━━━━━━\n"
           f"💰 ចំនួន: <b>${final_amount:.2f}</b>")
    if bonus > 0:
        cap += f"\n🎟️ ប្រាក់ Bonus Promo: <b>+${bonus:.2f}</b>"
    cap += (f"\n⏱ ផុតកំណត់: <b>{DEPOSIT_EXPIRE_SEC//60} នាទី</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📱 Scan ជាមួយ Bakong / ABA / Wing")
    
    if promo_applied and (bonus > 0 or discount > 0):
        confirm_promo(promo_applied, uid)

    try:
        admin_txt = (
            f"📥 <b>ការស្នើដាក់លុយថ្មី!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 User ID: <code>{uid_str}</code>\n"
            f"💰 ទឹកប្រាក់ស្នើ: <b>${final_amount:.2f}</b>"
        )
        if bonus > 0:
            admin_txt += f"\n🎟️ Bonus Promo: <b>+${bonus:.2f}</b>"
        admin_txt += f"\n💵 សរុបត្រូវបញ្ចូល: <b>${total_credit:.2f}</b>"

        admin_deposit_kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ ដាក់ប្រាក់ឱ្យគេ", callback_data=f"manual_dep:approve:{dep_id}"),
                InlineKeyboardButton("❌ កុំដាក់ប្រាក់ឱ្យគេ", callback_data=f"manual_dep:reject:{dep_id}")
            ]
        ])
        bot.send_message(ADMIN_ID, admin_txt, parse_mode="HTML", reply_markup=admin_deposit_kb)
    except Exception as e:
        logger.error(f"{CLR_RED}[deposit] Admin notification error: {e}{CLR_RESET}")

    img_buf = None
    try:
        import base64
        r = http.post(
            "https://api.bakongrelay.com/v1/generate_khqr_image",
            json    = {"qr": qr_str},
            headers = {"Authorization": f"Bearer {BAKONG_TOKEN}", "Content-Type": "application/json"},
            timeout = 10,
        )
        if r.ok and r.json().get("responseCode") == 0:
            img_b64 = r.json().get("data", {}).get("image", "")
            if img_b64:
                if "," in img_b64: img_b64 = img_b64.split(",", 1)[1]
                img_buf = io.BytesIO(base64.b64decode(img_b64))
                img_buf.seek(0); img_buf.name = "khqr.png"
    except Exception:
        pass

    if img_buf is None:
        try:
            import qrcode as _qrc
            qr = _qrc.QRCode(box_size=6, border=2)
            qr.add_data(qr_str); qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            img_buf = io.BytesIO(); img.save(img_buf, format="PNG"); img_buf.seek(0)
        except Exception:
            pass

    # បន្ថែម URL ABA ត្រង់នេះ
    aba_payment_url = "https://link.payway.com.kh/ABAPAYuN526009h"
    deposit_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 ចុចទីនេះដើម្បីបង់ប្រាក់តាម ABA", url=aba_payment_url)]
    ])

    if img_buf:
        try: bot.send_photo(uid, img_buf, caption=cap, parse_mode="HTML", reply_markup=deposit_markup)
        except: bot.send_message(uid, cap + f"\n\n<code>{qr_str}</code>", parse_mode="HTML", reply_markup=deposit_markup)
    else:
        bot.send_message(uid, cap + f"\n\n<code>{qr_str}</code>", parse_mode="HTML", reply_markup=deposit_markup)
        
    threading.Thread(target=_watch_deposit,
                     args=(uid, uid_str, dep_id, final_amount, start_ts), daemon=True).start()

# ═══════════════════════════════════════════════════════════
#  ORDER HELPERS
# ═══════════════════════════════════════════════════════════
def _make_order_id():
    return f"KZ{int(time.time())%100000:05d}"

def _place_store_order(uid, prod_id, plan_idx):
    p = _get_product(prod_id)
    if not p: return None, "❌ Product រកមិនឃើញ"
    plans = p.get("plans", [])
    if plan_idx >= len(plans): return None, "❌ Plan ខុស"
    plan  = plans[plan_idx]
    price = _calc_discounted_price(float(plan["price"]))
    qty   = int(plan.get("qty", 1))
    
    if bal(uid) < price: return None, f"❌ Balance មិនគ្រប់! (Balance: ${bal(uid):.2f})"
    
    if prod_id != "freefire":
        stock_cnt = _get_plan_stock_count(prod_id, plan_idx)
        if stock_cnt < qty: return None, f"❌ Stock អស់ហើយ! (Available: {stock_cnt})"
        items = [_pop_stock(prod_id, plan_idx) for _ in range(qty)]
    else:
        items = plan.get("items", [])

    ded_bal(uid, price)
    oid = _make_order_id()
    orders[oid] = {
        "uid": str(uid), "prod_id": prod_id, "prod_name": p["name"],
        "plan": plan["label"], "price": price, "qty": qty,
        "items": items, "status": "delivered" if prod_id != "freefire" else "pending_topup", "ts": int(time.time()),
    }
    _save(ORDERS_FILE, orders)
    
    if prod_id != "freefire":
        remaining = _get_plan_stock_count(prod_id, plan_idx)
        if remaining <= STOCK_ALERT_MIN:
            try:
                alert_txt = (
                    f"⚠️ <b>ជូនដំណឹង Stock!</b>\n"
                    f"📦 {p.get('icon','')} {p['name']} — {plan['label']}\n"
                    f"🔢 នៅសល់: <b>{remaining}</b>"
                )
                if remaining == 0:
                    alert_txt = (
                        f"🚨 <b>Stock អស់ហើយ!</b>\n"
                        f"📦 {p.get('icon','')} {p['name']} — {plan['label']}\n"
                        f"⚠️ ចូល ➕ បន្ថែមស្តុក ភ្លាម!"
                    )
                bot.send_message(ADMIN_ID, alert_txt, parse_mode="HTML")
            except: pass
    return oid, None

def _place_smm_order(uid, slug, qty):
    uid_str = str(uid)
    s = smm_services.get(slug)
    if not s: return None, "❌ Service រកមិនឃើញ"
    sr    = _smm_sell_rate(s["cost_rate"], slug)
    price = sr * qty / 1000
    if bal(uid) < price: return None, f"❌ Balance មិនគ្រប់! (Balance: ${bal(uid):.2f})"
    ded_bal(uid, price)
    key = smm_api.get("key",""); url = smm_api.get("url","")
    res = _smm_api_post({"key": key, "action": "add",
                         "service": s["api_id"], "link": "pending", "quantity": qty})
    api_order_id = str(res.get("order","")) if res else ""
    oid = _make_order_id()
    smm_orders[oid] = {
        "uid": uid_str, "slug": slug, "label": s.get("label",slug),
        "qty": qty, "price": price, "api_order_id": api_order_id,
        "status": "pending", "ts": int(time.time()),
    }
    _save(SMM_ORD_FILE, smm_orders)
    return oid, None

# ═══════════════════════════════════════════════════════════
#  TRACK USER
# ═══════════════════════════════════════════════════════════
def _track_user(message):
    uid = message.chat.id
    uid_str = str(uid)
    u = message.from_user
    users_db[uid_str] = {
        "name":     u.first_name or "",
        "username": u.username or "",
        "last":     int(time.time()),
        "banned":   users_db.get(uid_str, {}).get("banned", False),
    }
    _save(USERS_FILE, users_db)
    wallets.setdefault(uid_str, 0.0)

def is_banned(uid):
    return bool(users_db.get(str(uid), {}).get("banned", False))

# ═══════════════════════════════════════════════════════════
#  START
# ═══════════════════════════════════════════════════════════
@bot.message_handler(commands=["start"])
def cmd_start(message):
    uid = message.chat.id
    waiting.pop(uid, None)
    _track_user(message)
    if is_banned(uid):
        bot.send_message(uid, t(uid, "banned")); return
    if uid == ADMIN_ID:
        bot.send_message(uid,
            f"🤖 <b>Panel Admin — Kairozen All-in-One</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <code>{ADMIN_ID}</code>\n"
            f"💹 ចំណេញ SMM: <b>{_smm_profit_pct():.0f}%</b>\n"
            f"🔥 Global Discount: <b>{'ON (' + str(discount_config.get('pct')) + '%)' if discount_config.get('active') else 'OFF'}</b>\n"
            f"⏱ Poll: <b>{smm_poll.get('interval',5)}s</b>\n"
            f"━━━━━━━━━━━━━━━━━━",
            parse_mode="HTML", reply_markup=admin_kb())
        return
    if str(uid) not in user_lang:
        bot.send_message(uid,
            "🌐 <b>ជ្រើសរើសភាសា / Select Language</b>",
            parse_mode="HTML", reply_markup=lang_select_kb())
        return
    _show_welcome(uid)

def _show_welcome(uid):
    b = bal(uid)
    bot.send_message(uid,
        t(uid, "welcome", b),
        parse_mode="HTML",
        reply_markup=main_kb(uid))

# ═══════════════════════════════════════════════════════════
#  CALLBACKS
# ═══════════════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: c.data.startswith("setlang:"))
def cb_setlang(call):
    uid  = call.message.chat.id
    lang = call.data.split(":")[1]
    user_lang[str(uid)] = lang
    _save(LANG_FILE, user_lang)
    bot.answer_callback_query(call.id, t(uid, "lang_set"))
    try: bot.delete_message(uid, call.message.message_id)
    except: pass
    _show_welcome(uid)

@bot.callback_query_handler(func=lambda c: c.data.startswith("poll:"))
def cb_poll(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: bot.answer_callback_query(call.id); return
    sec = int(call.data.split(":")[1])
    smm_poll["interval"] = sec; _save(SMM_POLL_FILE, smm_poll)
    bot.answer_callback_query(call.id, f"✅ Poll = {sec}s")
    try: bot.edit_message_text(f"✅ Poll Speed = <b>{sec} វិ</b>",
                               chat_id=uid, message_id=call.message.message_id, parse_mode="HTML")
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("dep:"))
def cb_dep(call):
    uid     = call.message.chat.id
    uid_str = str(uid)
    lang    = get_lang(uid)
    val     = call.data[4:]
    bot.answer_callback_query(call.id)

    if val == "promo":
        waiting[uid] = {"step": "dep_enter_promo", "msg_id": call.message.message_id}
        bot.send_message(uid,
            "🎟️ <b>ដាក់ Promo Code:</b>\n"
            "<i>ឧ: SAVE50 · GIFT1 · FREE</i>" if lang=="kh" else
            "🎟️ <b>Enter Promo Code:</b>\n<i>e.g. SAVE50 · GIFT1</i>",
            parse_mode="HTML", reply_markup=cancel_kb())
        return

    if val == "clrpromo":
        step = waiting.get(uid)
        if isinstance(step, dict): step.pop("promo", None)
        try:
            bot.edit_message_reply_markup(
                chat_id=uid, message_id=call.message.message_id,
                reply_markup=deposit_amt_kb(uid, None))
        except: pass
        return

    if val == "custom":
        waiting[uid] = {"step": "dep_custom", "promo": _get_dep_promo(uid)}
        bot.send_message(uid,
            "✏️ <b>ផ្ញើចំនួន $ ដែលចង់ deposit:</b>" if lang=="kh" else
            "✏️ <b>Send amount $ to deposit:</b>",
            parse_mode="HTML", reply_markup=cancel_kb())
        return

    amount     = float(val)
    promo_code = _get_dep_promo(uid)
    waiting.pop(uid, None)
    _process_deposit(uid, uid_str, amount, promo_code)

def _get_dep_promo(uid):
    step = waiting.get(uid)
    if isinstance(step, dict):
        return step.get("promo")
    return None

def _process_deposit(uid, uid_str, amount, promo_code):
    lang  = get_lang(uid)
    bonus = 0.0
    promo_applied = None

    if promo_code:
        p = promos.get(promo_code.upper())
        if p and (p.get("uses", 0) == 0 or p.get("used", 0) < p.get("uses", 0)):
            if str(uid) not in p.get("user_used", {}):
                if p.get("pct", False):
                    bonus = round(amount * float(p["discount"]) / 100, 2)
                else:
                    bonus = round(float(p["discount"]), 2)
                promo_applied = promo_code.upper()

    _send_deposit_qr(uid, amount,
                     label=f"💳 <b>{'ដាក់ប្រាក់' if lang=='kh' else 'Top Up'}</b>",
                     bonus=bonus, promo_code_name=promo_applied)

@bot.callback_query_handler(func=lambda c: c.data.startswith("manual_dep:"))
def cb_manual_dep(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID:
        bot.answer_callback_query(call.id)
        return

    parts = call.data.split(":")
    action = parts[1]
    dep_id = parts[2]

    dep = store_deps.get(dep_id)
    if not dep:
        bot.answer_callback_query(call.id, "❌ សំណើនេះរកមិនឃើញ ឬផុតកំណត់ហើយ!", show_alert=True)
        return

    target_uid = int(dep["uid"])
    amount = float(dep["amount"])
    bonus = float(dep.get("bonus", 0))
    total_credit = round(amount + bonus, 2)

    if action == "approve":
        if dep.get("status") == "confirmed":
            bot.answer_callback_query(call.id, "⚠️ សំណើនេះបានបញ្ជាក់រួចរាល់ហើយ!", show_alert=True)
            return

        add_bal(target_uid, total_credit)
        dep["status"] = "confirmed"
        _save(STORE_DEP_FILE, store_deps)

        bot.answer_callback_query(call.id, "✅ បានដាក់ប្រាក់ឱ្យគេរួចរាល់!")
        
        try:
            bot.edit_message_text(
                f"✅ <b>បានដាក់ប្រាក់ឱ្យគេរួចរាល់!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"👤 User: <code>{target_uid}</code>\n"
                f"💰 ចំនួន: <b>${total_credit:.2f}</b>",
                chat_id=uid, message_id=call.message.message_id, parse_mode="HTML"
            )
        except Exception:
            pass

        try:
            msg = (f"✅ <b>ដាក់លុយបានជោគជ័យ! (ដោយ Admin)</b>\n"
                   f"━━━━━━━━━━━━━━━━━━\n"
                   f"💰 បញ្ញើ: <b>${amount:.2f}</b>")
            if bonus > 0:
                msg += f"\n🎟️ Bonus: <b>+${bonus:.2f}</b>"
            msg += f"\n💳 សាច់ប្រាក់បច្ចុប្បន្ន: <b>${bal(target_uid):.2f}</b>"
            bot.send_message(target_uid, msg, parse_mode="HTML", reply_markup=main_kb(target_uid))
        except Exception:
            pass

    elif action == "reject":
        dep["status"] = "rejected"
        _save(STORE_DEP_FILE, store_deps)

        bot.answer_callback_query(call.id, "❌ បានបដិសេធសំណើ!")
        
        try:
            bot.edit_message_text(
                f"❌ <b>បានបដិសេធ (កុំដាក់ប្រាក់ឱ្យគេ)!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"👤 User: <code>{target_uid}</code>\n"
                f"💰 ចំនួន: <b>${amount:.2f}</b>",
                chat_id=uid, message_id=call.message.message_id, parse_mode="HTML"
            )
        except Exception:
            pass

        try:
            bot.send_message(target_uid, "❌ សំណើដាក់ប្រាក់របស់អ្នកត្រូវបានបដិសេធដោយ Admin។", parse_mode="HTML")
        except Exception:
            pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("admaddall:"))
def cb_admaddall(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    bot.answer_callback_query(call.id)
    action = call.data.split(":")[1]

    if action == "digital":
        waiting[uid] = "add_product_name"
        bot.send_message(uid, "➕ <b>បញ្ចូលឈ្មោះផលិតផល ឬហ្គេមថ្មី៖</b>", parse_mode="HTML", reply_markup=cancel_kb())
    elif action == "smm":
        cats_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎵 TikTok",    callback_data="smmaddcat:TikTok"),
             InlineKeyboardButton("📘 Facebook",  callback_data="smmaddcat:Facebook")],
            [InlineKeyboardButton("📸 Instagram", callback_data="smmaddcat:Instagram"),
             InlineKeyboardButton("▶️ YouTube",   callback_data="smmaddcat:YouTube")],
            [InlineKeyboardButton("📱 Telegram",  callback_data="smmaddcat:Telegram")],
            [InlineKeyboardButton("✏️ Custom Category", callback_data="smmaddcat:custom")],
        ])
        bot.send_message(uid, "➕ <b>ជ្រើសរើស Category សម្រាប់ SMM Service៖</b>", parse_mode="HTML", reply_markup=cats_kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("prod:"))
def cb_prod(call):
    uid  = call.message.chat.id
    pid  = call.data[5:]
    bot.answer_callback_query(call.id)
    p = _get_product(pid)
    if not p: return
    lang = get_lang(uid)
    plans = p.get("plans", [])
    plan_lines = []
    for i, pl in enumerate(plans):
        cnt = _get_plan_stock_count(pid, i)
        orig_price = float(pl['price'])
        final_price = _calc_discounted_price(orig_price)
        
        if discount_config.get("active", False):
            price_str = f"<s>${orig_price:.2f}</s> <b>${final_price:.2f}</b> 🔥"
        else:
            price_str = f"<b>${orig_price:.2f}</b>"

        if pid == "freefire":
            status = "✅ Ready"
        else:
            status = "✅ Available" if cnt > 0 else "❌ អស់"
        plan_lines.append(f"  • {pl['label']} — {price_str}  {status}")
    plans_txt = "\n".join(plan_lines) if plan_lines else "  (គ្មាន plan)"
    txt = (f"{p.get('icon','📦')} <b>{p['name']}</b>\n"
           f"━━━━━━━━━━━━━━━━━━\n"
           f"📋 {p.get('desc','')}\n"
           f"━━━━━━━━━━━━━━━━━━\n"
           f"📦 Plans:\n{plans_txt}\n"
           f"━━━━━━━━━━━━━━━━━━\n"
           f"{'ជ្រើស Plan:' if lang=='kh' else 'Choose Plan:'}")
    try: bot.edit_message_text(txt, chat_id=uid, message_id=call.message.message_id,
                                parse_mode="HTML", reply_markup=plans_kb(pid))
    except: bot.send_message(uid, txt, parse_mode="HTML", reply_markup=plans_kb(pid))

@bot.callback_query_handler(func=lambda c: c.data.startswith("plan_oos:"))
def cb_plan_oos(call):
    bot.answer_callback_query(call.id, "❌ Plan នេះស្តុកអស់ហើយ! សូមរង់ចាំ Admin បន្ថែម.", show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data.startswith("plan:"))
def cb_plan(call):
    uid = call.message.chat.id
    bot.answer_callback_query(call.id)
    _, pid, idx = call.data.split(":")
    idx = int(idx)
    p   = _get_product(pid)
    if not p: return
    plan  = p["plans"][idx]
    price = _calc_discounted_price(float(plan["price"]))
    lang  = get_lang(uid)
    
    if pid == "freefire":
        waiting[uid] = {"step": "order_freefire_uid", "prod_id": pid, "plan_idx": idx, "price": price}
        bot.send_message(uid,
            f"💎 <b>{p['name']}</b> — {plan['label']} — <b>${price:.2f}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🎮 សូមបញ្ចូល **Player ID** របស់អ្នក៖\nEnter your Free Fire Player ID:",
            parse_mode="HTML", reply_markup=cancel_kb())
    else:
        waiting[uid] = {"step": "order_qty", "prod_id": pid, "plan_idx": idx, "price": price}
        bot.send_message(uid,
            f"🛍️ <b>{p['name']}</b> — {plan['label']} — <b>${price:.2f}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🔢 សូមបញ្ចូលចំនួន Account (លេខតែមួយ):\nSend a numeric count of accounts:",
            parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("admprod:"))
def cb_admprod(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    bot.answer_callback_query(call.id)
    parts  = call.data.split(":", 2)
    action = parts[1]
    pid    = parts[2] if len(parts) > 2 else ""
    p      = _get_product(pid)

    if action == "stock":
        p_obj = _get_product(pid)
        plans = p_obj.get("plans", []) if p_obj else []
        if pid == "freefire":
            bot.send_message(uid, f"📦 <b>{p_obj['name']}</b> — Game Top Up (No stock file needed, uses Player ID)", parse_mode="HTML")
            return
        if plans:
            lines = [f"📦 <b>{p_obj['name'] if p_obj else pid}</b> — Stock per Plan\n━━━━━━━━━━━━━━━━━━"]
            for i, pl in enumerate(plans):
                key   = _stock_key(pid, i)
                items = stock.get(key, [])
                lines.append(f"\n<b>{pl['label']}</b> ({len(items)} items)")
                preview = "\n".join(f"• <code>{it['data'] if isinstance(it,dict) else it}</code>" for it in items[:10])
                if preview: lines.append(preview)
                if len(items) > 10: lines.append(f"...+{len(items)-10} more")
            bot.send_message(uid, "\n".join(lines), parse_mode="HTML")
        else:
            items = _get_stock(pid)
            if not items:
                bot.send_message(uid, f"📦 Stock: <b>0</b> items", parse_mode="HTML"); return
            preview = "\n".join(f"• <code>{i}</code>" for i in items[:20])
            more    = f"\n...+{len(items)-20} more" if len(items) > 20 else ""
            bot.send_message(uid,
                f"📦 <b>{p['name'] if p else pid}</b> — Stock: <b>{len(items)}</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n{preview}{more}",
                parse_mode="HTML")

    elif action == "clrstock":
        p_obj  = _get_product(pid)
        plans  = p_obj.get("plans", []) if p_obj else []
        all_keys = [_stock_key(pid, i) for i in range(len(plans))] + [pid]
        total_cnt = sum(len(stock.get(k, [])) for k in all_keys)
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ យល់ព្រម Clear", callback_data=f"admprod:confirmclr:{pid}"),
            InlineKeyboardButton("❌ Cancel",         callback_data=f"admprod:cancel:{pid}"),
        ]])
        bot.send_message(uid,
            f"⚠️ Clear stock <b>{p['name'] if p else pid}</b>?\n"
            f"📦 Items: <b>{total_cnt}</b> នឹងត្រូវលុប!",
            parse_mode="HTML", reply_markup=kb)

    elif action == "confirmclr":
        p_obj = _get_product(pid)
        plans = p_obj.get("plans", []) if p_obj else []
        for i in range(len(plans)):
            stock.pop(_stock_key(pid, i), None)
        stock.pop(pid, None)
        _save(STOCK_FILE, stock)
        bot.send_message(uid,
            f"✅ Stock <b>{p['name'] if p else pid}</b> cleared (all plans)!",
            parse_mode="HTML", reply_markup=admin_kb())

    elif action == "del":
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ យល់ព្រម Delete", callback_data=f"admprod:confirmdel:{pid}"),
            InlineKeyboardButton("❌ Cancel",          callback_data=f"admprod:cancel:{pid}"),
        ]])
        cnt = len(_get_stock(pid))
        bot.send_message(uid,
            f"⚠️ Delete product <b>{p['name'] if p else pid}</b>?\n"
            f"📦 Stock: <b>{cnt}</b> items នឹងត្រូវលុបផងដែរ!",
            parse_mode="HTML", reply_markup=kb)

    elif action == "confirmdel":
        name = p["name"] if p else pid
        plans = p.get("plans", []) if p else []
        global products
        products = [x for x in products if x["id"] != pid]
        _save(PRODUCTS_FILE, products)
        for i in range(len(plans)):
            stock.pop(_stock_key(pid, i), None)
        stock.pop(pid, None)
        _save(STOCK_FILE, stock)
        bot.send_message(uid,
            f"✅ Product <b>{name}</b> deleted! (Stock cleared)",
            parse_mode="HTML", reply_markup=admin_kb())

    elif action == "cancel":
        bot.send_message(uid, "❌ Cancelled", reply_markup=admin_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("delsvc:"))
def cb_delsvc(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    bot.answer_callback_query(call.id)
    parts = call.data.split(":", 2)

    if len(parts) == 3 and parts[1] == "cat":
        cat = parts[2]
        to_del = [slug for slug, s in smm_services.items() if s.get("category") == cat]
        for slug in to_del:
            smm_services.pop(slug, None)
        _save(SMM_SVC_FILE, smm_services)
        try:
            bot.edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
        except: pass
        bot.send_message(uid,
            f"✅ Deleted <b>{len(to_del)}</b> services in <b>{cat}</b>",
            parse_mode="HTML", reply_markup=admin_kb())
        return

    slug = parts[1]
    s    = smm_services.get(slug)
    if not s:
        bot.send_message(uid, "❌ Service រកមិនឃើញ", reply_markup=admin_kb()); return
    label  = s.get("label", slug)
    api_id = s.get("api_id", "?")
    smm_services.pop(slug, None)
    _save(SMM_SVC_FILE, smm_services)
    try:
        bot.edit_message_reply_markup(uid, call.message.message_id, reply_markup=None)
    except: pass
    bot.send_message(uid,
        f"✅ Deleted: <b>[{api_id}] {label}</b>\n"
        f"📊 Remaining services: <b>{len(smm_services)}</b>",
        parse_mode="HTML", reply_markup=admin_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("smmapi:"))
def cb_smmapi(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    action = call.data[7:]
    bot.answer_callback_query(call.id)

    if action == "setup":
        waiting[uid] = "smm_api_url"
        bot.send_message(uid,
            "🌐 <b>ផ្ញើ SMM API URL</b>\nឧ: <code>https://smmking.net/api/v2</code>",
            parse_mode="HTML", reply_markup=cancel_kb())

    elif action == "test":
        url = smm_api.get("url",""); key = smm_api.get("key","")
        if not url or not key:
            bot.send_message(uid, "❌ API មិនទាន់ set!", reply_markup=admin_kb()); return
        try:
            r = http.post(url, data={"key": key, "action": "balance"}, timeout=10)
            d = r.json()
            balance  = d.get("balance", d.get("Balance", "?"))
            currency = d.get("currency", d.get("Currency", "USD"))
            bot.send_message(uid,
                f"✅ <b>Connection OK!</b>\n━━━━━━━━━━━━━━━━━━\n"
                f"💰 Balance: <b>{balance} {currency}</b>",
                parse_mode="HTML", reply_markup=admin_kb())
        except Exception as e:
            bot.send_message(uid, f"❌ Connection failed: <code>{e}</code>",
                             parse_mode="HTML", reply_markup=admin_kb())

    elif action == "clear":
        smm_api.clear(); smm_api.update({"url":"","key":""})
        _save(SMM_API_FILE, smm_api)
        bot.send_message(uid, "🗑️ SMM API cleared!", reply_markup=admin_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("smmaddcat:"))
def cb_smmaddcat(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    cat = call.data[len("smmaddcat:"):]
    bot.answer_callback_query(call.id)
    if cat == "custom":
        waiting[uid] = "smm_add_cat"
        bot.send_message(uid, "✏️ វាយ Category name (ឧ: TikTok Live, Spotify):",
                         reply_markup=cancel_kb())
    else:
        waiting[uid] = {"step": "smm_add_ids", "cat": cat}
        bot.send_message(uid,
            f"📂 Category: <b>{cat}</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"ផ្ញើ Service IDs (comma separated):\n"
            f"ឧ: <code>5441,5448,5502</code>\n\n"
            f"💡 IDs រក នៅ SMM Panel → Services",
            parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("smmcat:"))
def cb_smmcat(call):
    uid = call.message.chat.id
    cat = call.data[7:]
    bot.answer_callback_query(call.id)
    svcs = _smm_get_svcs_in_cat(cat)
    if not svcs:
        try: bot.answer_callback_query(call.id, "❌ គ្មាន Service", show_alert=True)
        except: pass
        return
    try:
        bot.edit_message_text(f"📂 <b>{cat}</b>\n━━━━━━━━━━━━━━━━━━\n{'ជ្រើស Service:'}",
                              chat_id=uid, message_id=call.message.message_id,
                              parse_mode="HTML", reply_markup=smm_svc_kb(cat))
    except:
        bot.send_message(uid, f"📂 <b>{cat}</b>", parse_mode="HTML", reply_markup=smm_svc_kb(cat))

@bot.callback_query_handler(func=lambda c: c.data.startswith("smmsvc:"))
def cb_smmsvc(call):
    uid  = call.message.chat.id
    slug = call.data[7:]
    bot.answer_callback_query(call.id)
    s = smm_services.get(slug)
    if not s: return
    sr   = _smm_sell_rate(s["cost_rate"], slug)
    lang = get_lang(uid)
    txt  = (f"⚡ <b>{s.get('label',slug)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 {'តម្លៃ' if lang=='kh' else 'Price'}: <b>${sr:.2f}/1K</b>\n"
            f"📏 Min: {s.get('min',10):,}  ·  Max: {s.get('max',100000):,}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{'ជ្រើស Quantity:' if lang=='kh' else 'Choose Quantity:'}")
    try:
        bot.edit_message_text(txt, chat_id=uid, message_id=call.message.message_id,
                              parse_mode="HTML", reply_markup=smm_qty_kb(slug, s))
    except:
        bot.send_message(uid, txt, parse_mode="HTML", reply_markup=smm_qty_kb(slug, s))

@bot.callback_query_handler(func=lambda c: c.data.startswith("smmqty:"))
def cb_smmqty(call):
    uid = call.message.chat.id
    bot.answer_callback_query(call.id)
    parts = call.data.split(":")
    slug  = parts[1]; qty = int(parts[2])
    s     = smm_services.get(slug)
    if not s: return
    sr    = _smm_sell_rate(s["cost_rate"], slug)
    price = sr * qty / 1000
    lang  = get_lang(uid)
    waiting[uid] = {"step": "smm_link", "slug": slug, "qty": qty, "price": price}
    try:
        bot.edit_message_text(
            f"🔗 <b>{'ផ្ញើ Link:' if lang=='kh' else 'Send Link:'}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 {s.get('label',slug)}\n"
            f"💰 {qty:,} — <b>${price:.4f}</b>",
            chat_id=uid, message_id=call.message.message_id,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="back:main")]]))
    except:
        bot.send_message(uid, f"🔗 ផ្ញើ Link:", parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("addstock_prod:"))
def cb_addstock_prod(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    pid = call.data[len("addstock_prod:"):]
    bot.answer_callback_query(call.id)
    p = _get_product(pid)
    if not p:
        bot.send_message(uid, "❌ Product រកមិនឃើញ", reply_markup=admin_kb()); return
    if pid == "freefire":
        bot.send_message(uid, "💎 Free Fire មិនបាច់ដាក់ Stock ទេ។ វាប្រើប្រព័ន្ធបំពេញតាម Player ID ។", reply_markup=admin_kb())
        return
    plans = p.get("plans", [])
    if not plans:
        bot.send_message(uid,
            f"❌ <b>{p['name']}</b> គ្មាន Plan!\nប្រើ ✏️ Edit Price ដើម្បីបន្ថែម plans ជាមុន.",
            parse_mode="HTML", reply_markup=admin_kb()); return
    btns = []
    for i, pl in enumerate(plans):
        cnt = _get_plan_stock_count(pid, i)
        status = f"({cnt} នៅ)" if cnt > 0 else "(❌ អស់)"
        btns.append([InlineKeyboardButton(
            f"{pl['label']} — ${pl['price']:.2f}  {status}",
            callback_data=f"addstock_plan:{pid}:{i}")])
    btns.append([InlineKeyboardButton("🔙 Back", callback_data="addstock_back")])
    bot.send_message(uid,
        f"➕ <b>Add Stock — {p.get('icon','')} {p['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\nជ្រើស Plan ដើម្បីដាក់ stock:",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))

@bot.callback_query_handler(func=lambda c: c.data.startswith("addstock_plan:"))
def cb_addstock_plan(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    bot.answer_callback_query(call.id)
    _, pid, idx_str = call.data.split(":", 2)
    idx = int(idx_str)
    p   = _get_product(pid)
    if not p: return
    plan = p["plans"][idx]
    waiting[uid] = {"step": "add_stock_items", "pid": pid, "plan_idx": idx}
    cnt = _get_plan_stock_count(pid, idx)
    bot.send_message(uid,
        f"➕ <b>Add Stock</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 {p.get('icon','')} <b>{p['name']}</b>\n"
        f"🏷️ Plan: <b>{plan['label']}</b> — ${plan['price']:.2f}\n"
        f"📊 Stock បច្ចុប្បន្ន: <b>{cnt}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📋 <b>របៀបដាក់ Stock:</b>\n"
        f"ផ្ញើ accounts <b>1 per line</b>\n\n"
        f"<b>Format:</b>\n"
        f"<code>email:password</code>\n",
        parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data == "addstock_back")
def cb_addstock_back(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    bot.answer_callback_query(call.id)
    if not products:
        bot.send_message(uid, "❌ គ្មាន Product", reply_markup=admin_kb()); return
    btns = []
    for p in products:
        if p["id"] == "freefire": continue
        btns.append([InlineKeyboardButton(
            f"{p.get('icon','📦')} {p['name']}", callback_data=f"addstock_prod:{p['id']}")])
    bot.send_message(uid,
        "➕ <b>Add Stock</b>\n━━━━━━━━━━━━━━━━━━\nជ្រើស Product:",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))

@bot.callback_query_handler(func=lambda c: c.data.startswith("editprice_prod:"))
def cb_editprice_prod(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    pid = call.data[len("editprice_prod:"):]
    bot.answer_callback_query(call.id)
    p = _get_product(pid)
    if not p:
        bot.send_message(uid, "❌ Product រកមិនឃើញ", reply_markup=admin_kb()); return
    plans = p.get("plans", [])
    btns  = []
    for i, pl in enumerate(plans):
        btns.append([
            InlineKeyboardButton(
                f"✏️ {pl['label']} — ${pl['price']:.2f}",
                callback_data=f"editprice_plan:{pid}:{i}"),
            InlineKeyboardButton(
                f"✏️ Label", callback_data=f"editlabel_plan:{pid}:{i}"),
            InlineKeyboardButton(
                f"🗑️", callback_data=f"delplan:{pid}:{i}"),
        ])
    btns.append([InlineKeyboardButton(
        "➕ បន្ថែម Plan ថ្មី", callback_data=f"editprice_addplan:{pid}")])
    btns.append([InlineKeyboardButton("🔙 Back", callback_data="editprice_back")])
    bot.send_message(uid,
        f"✏️ <b>Edit Plans — {p.get('icon','')} {p['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"ចុច ✏️ Label ដើម្បីកែឈ្មោះ  |  🗑️ ដើម្បីលុប Plan:",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))

@bot.callback_query_handler(func=lambda c: c.data.startswith("editprice_plan:"))
def cb_editprice_plan(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    bot.answer_callback_query(call.id)
    _, pid, idx_str = call.data.split(":", 2)
    idx  = int(idx_str)
    p    = _get_product(pid)
    if not p: return
    plan = p["plans"][idx]
    waiting[uid] = {"step": "edit_price_val", "pid": pid, "plan_idx": idx}
    bot.send_message(uid,
        f"✏️ <b>កែតម្លៃ Plan</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 {p.get('icon','')} <b>{p['name']}</b>\n"
        f"🏷️ Plan: <b>{plan['label']}</b>\n"
        f"💰 តម្លៃបច្ចុប្បន្ន: <b>${plan['price']:.2f}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"ផ្ញើ <b>តម្លៃថ្មី</b> (USD):\n"
        f"<i>ឧ: <code>2.50</code></i>",
        parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("editprice_addplan:"))
def cb_editprice_addplan(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    pid = call.data[len("editprice_addplan:"):]
    bot.answer_callback_query(call.id)
    p = _get_product(pid)
    if not p: return
    waiting[uid] = {"step": "edit_price_newplan_label", "pid": pid}
    bot.send_message(uid,
        f"➕ <b>បន្ថែម Plan ថ្មី</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 {p.get('icon','')} <b>{p['name']}</b>\n\n"
        f"ផ្ញើ <b>ឈ្មោះ Plan</b>:\n"
        f"<i>ឧ: <code>1 ខែ</code> ឬ <code>100 Diamonds</code></i>",
        parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data == "editprice_back")
def cb_editprice_back(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    bot.answer_callback_query(call.id)
    if not products:
        bot.send_message(uid, "❌ គ្មាន Product", reply_markup=admin_kb()); return
    btns = []
    for p in products:
        btns.append([InlineKeyboardButton(
            f"{p.get('icon','📦')} {p['name']}", callback_data=f"editprice_prod:{p['id']}")])
    bot.send_message(uid,
        "✏️ <b>Edit Price / Plans</b>\n━━━━━━━━━━━━━━━━━━\nជ្រើស Product:",
        parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))

@bot.callback_query_handler(func=lambda c: c.data.startswith("editlabel_plan:"))
def cb_editlabel_plan(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    bot.answer_callback_query(call.id)
    _, pid, idx_str = call.data.split(":", 2)
    idx  = int(idx_str)
    p    = _get_product(pid)
    if not p: return
    plan = p["plans"][idx]
    waiting[uid] = {"step": "edit_label_val", "pid": pid, "plan_idx": idx}
    bot.send_message(uid,
        f"✏️ <b>កែឈ្មោះ Plan</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 {p.get('icon','')} <b>{p['name']}</b>\n"
        f"🏷️ ឈ្មោះបច្ចុប្បន្ន: <b>{plan['label']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"ផ្ញើ <b>ឈ្មោះថ្មី</b>:\n<i>ឧ: <code>1 ខែ</code></i>",
        parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("delplan:"))
def cb_delplan(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    bot.answer_callback_query(call.id)
    _, pid, idx_str = call.data.split(":", 2)
    idx = int(idx_str)
    p   = _get_product(pid)
    if not p: return
    plan = p["plans"][idx]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ យល់ព្រម លុប", callback_data=f"delplan_ok:{pid}:{idx}"),
        InlineKeyboardButton("❌ Cancel",       callback_data=f"editprice_prod:{pid}"),
    ]])
    bot.send_message(uid,
        f"⚠️ លុប Plan <b>{plan['label']}</b> (${plan['price']:.2f})?",
        parse_mode="HTML", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("delplan_ok:"))
def cb_delplan_ok(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: return
    bot.answer_callback_query(call.id)
    _, pid, idx_str = call.data.split(":", 2)
    idx = int(idx_str)
    p   = _get_product(pid)
    if not p: return
    if idx >= len(p["plans"]): return
    label = p["plans"][idx]["label"]
    p["plans"].pop(idx)
    stock.pop(_stock_key(pid, idx), None)
    _save(PRODUCTS_FILE, products)
    _save(STOCK_FILE, stock)
    try: bot.edit_message_text(
        f"✅ Plan <b>{label}</b> លុបរួចហើយ!",
        chat_id=uid, message_id=call.message.message_id, parse_mode="HTML")
    except: pass
    bot.send_message(uid, f"✅ Plan <b>{label}</b> deleted.",
                     parse_mode="HTML", reply_markup=admin_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("back:"))
def cb_back(call):
    uid = call.message.chat.id
    bot.answer_callback_query(call.id)
    dest = call.data[5:]
    waiting.pop(uid, None)
    if dest == "main":
        _show_welcome(uid)
    elif dest == "shop":
        bot.send_message(uid, "🛍️ <b>Shop</b>", parse_mode="HTML", reply_markup=products_kb())
    elif dest == "smmcats":
        bot.send_message(uid, "📊 <b>SMM Services</b>", parse_mode="HTML", reply_markup=smm_cat_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("useraction:"))
def cb_useraction(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: bot.answer_callback_query(call.id); return
    bot.answer_callback_query(call.id)
    parts  = call.data.split(":", 2)
    action = parts[1]
    target = parts[2]

    if action == "ban":
        users_db.setdefault(target, {})["banned"] = True
        _save(USERS_FILE, users_db)
        name = users_db[target].get("name","?")
        try: bot.edit_message_text(
            f"🚫 <b>Banned:</b> {name} <code>{target}</code>",
            chat_id=uid, message_id=call.message.message_id, parse_mode="HTML")
        except: pass
        try: bot.send_message(int(target), "🚫 គណនីរបស់អ្នកត្រូវបាន ban!")
        except: pass

    elif action == "unban":
        users_db.setdefault(target, {})["banned"] = False
        _save(USERS_FILE, users_db)
        name = users_db[target].get("name","?")
        try: bot.edit_message_text(
            f"🔓 <b>Unbanned:</b> {name} <code>{target}</code>",
            chat_id=uid, message_id=call.message.message_id, parse_mode="HTML")
        except: pass
        try: bot.send_message(int(target), "✅ គណនីរបស់អ្នកត្រូវបាន unban!")
        except: pass

    elif action == "addbal":
        waiting[uid] = {"step": "add_balance_amt", "target": target}
        name = users_db.get(target,{}).get("name","?")
        b    = float(wallets.get(target, 0))
        bot.send_message(uid,
            f"💸 <b>បន្ថែម Balance</b>\n👤 <b>{name}</b> <code>{target}</code>\n"
            f"💳 សាច់ប្រាក់: <b>${b:.2f}</b>\n━━━━━━━━━━━━━━━━━━\nផ្ញើ Amount $:",
            parse_mode="HTML", reply_markup=cancel_kb())

    elif action == "dedbal":
        waiting[uid] = {"step": "deduct_balance_amt", "target": target}
        name = users_db.get(target,{}).get("name","?")
        b    = float(wallets.get(target, 0))
        bot.send_message(uid,
            f"💔 <b>កាត់ Balance</b>\n👤 <b>{name}</b> <code>{target}</code>\n"
            f"💳 សាច់ប្រាក់: <b>${b:.2f}</b>\n━━━━━━━━━━━━━━━━━━\nផ្ញើ Amount $ ដក:",
            parse_mode="HTML", reply_markup=cancel_kb())

@bot.callback_query_handler(func=lambda c: c.data.startswith("adminpromo:"))
def cb_adminpromo(call):
    uid = call.message.chat.id
    if uid != ADMIN_ID: bot.answer_callback_query(call.id); return
    bot.answer_callback_query(call.id)
    action = call.data.split(":")[1]
    if action == "add":
        waiting[uid] = "promo_add_code"
        bot.send_message(uid,
            "🎟️ <b>បន្ថែម Promo Code</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "ផ្ញើ: <code>CODE DISCOUNT TYPE USES</code>\n"
            "Type: <b>pct</b> (%) ឬ <b>fix</b> ($)\n"
            "ឧ: <code>SAVE50 50 pct 100</code>",
            parse_mode="HTML", reply_markup=cancel_kb())
    elif action == "list":
        _show_promos(uid)
    elif action.startswith("del_"):
        code = action[4:]
        promos.pop(code.upper(), None)
        _save(PROMO_FILE, promos)
        try:
            bot.edit_message_text(f"🗑️ Promo <b>{code}</b> លុបហើយ!",
                                  chat_id=uid, message_id=call.message.message_id, parse_mode="HTML")
        except: pass

def _show_promos(uid):
    if not promos:
        bot.send_message(uid, "❌ គ្មាន Promo Code ទេ", reply_markup=admin_kb()); return
    lines = ["🎟️ <b>Promo Codes</b>\n━━━━━━━━━━━━━━━━━━"]
    btns  = []
    for code, p in promos.items():
        dtype = f"{p['discount']}%" if p.get("pct") else f"${p['discount']}"
        uses  = f"{p.get('used',0)}/{p.get('uses',0)}"
        lines.append(f"• <code>{code}</code> — <b>{dtype}</b> | {uses} ប្រើ")
        btns.append([InlineKeyboardButton(f"🗑 {code}", callback_data=f"adminpromo:del_{code}")])
    btns.append([InlineKeyboardButton("➕ Add Promo", callback_data="adminpromo:add")])
    bot.send_message(uid, "\n".join(lines), parse_mode="HTML",
                     reply_markup=InlineKeyboardMarkup(btns))

# ═══════════════════════════════════════════════════════════
#  MAIN MESSAGE HANDLER
# ═══════════════════════════════════════════════════════════
@bot.message_handler(func=lambda m: True)
def handle(message):
    uid     = message.chat.id
    uid_str = str(uid)
    text    = message.text.strip() if message.text else ""
    step    = waiting.get(uid)
    lang    = get_lang(uid)

    _track_user(message)
    if is_banned(uid) and uid != ADMIN_ID:
        bot.send_message(uid, t(uid, "banned")); return

    if text in ("✕ Cancel", "❌ Cancel", "❌ បោះបង់"):
        waiting.pop(uid, None)
        kb = admin_kb() if uid == ADMIN_ID else main_kb(uid)
        bot.send_message(uid, t(uid, "cancel_ok"), reply_markup=kb); return

    # ══════════════════════════════════════════════════════
    #  ADMIN SECTION
    # ══════════════════════════════════════════════════════
    if uid == ADMIN_ID:

        if text == "➕ បន្ថែមគ្រប់សេវាកម្ម":
            kb_add_all = InlineKeyboardMarkup([
                [InlineKeyboardButton("🛍️ បន្ថែមផលិតផលឌីជីថល/ហ្គេម", callback_data="admaddall:digital")],
                [InlineKeyboardButton("📊 បន្ថែមសេវាកម្ម SMM", callback_data="admaddall:smm")],
            ])
            bot.send_message(uid,
                "➕ <b>ជ្រើសរើសប្រភេទសេវាកម្មដែលចង់បន្ថែម៖</b>\n━━━━━━━━━━━━━━━━━━",
                parse_mode="HTML", reply_markup=kb_add_all)
            return

        if text == "🔥 បញ្ចុះតម្លៃទាំងអស់":
            waiting[uid] = "admin_set_discount"
            status_txt = "🟢 កំពុងបើក" if discount_config.get("active") else "🔴 កំពុងបិទ"
            cur_pct = discount_config.get("pct", 0)
            bot.send_message(uid,
                f"🔥 <b>គ្រប់គ្រងការបញ្ចុះតម្លៃសេវាកម្មទាំងអស់</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"ស្ថានភាព: <b>{status_txt}</b>\n"
                f"អភាគរយបញ្ចុះ: <b>{cur_pct}%</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"ផ្ញើទម្រង់ជា: <code>ON 20</code> (ដើម្បីបើកនិងកំណត់ 20%) ឬ <code>OFF</code> (ដើម្បីបិទ)",
                parse_mode="HTML", reply_markup=cancel_kb())
            return

        if step == "admin_set_discount":
            parts = text.strip().split()
            cmd = parts[0].upper()
            if cmd == "OFF":
                discount_config["active"] = False
                discount_config["pct"] = 0
                _save(DISCOUNT_FILE, discount_config)
                waiting.pop(uid, None)
                bot.send_message(uid, "✅ បាន **បិទ** ការបញ្ចុះតម្លៃទាំងអស់រួចរាល់!", parse_mode="HTML", reply_markup=admin_kb())
                return
            elif cmd == "ON" and len(parts) >= 2:
                try:
                    pct = float(parts[1])
                    discount_config["active"] = True
                    discount_config["pct"] = pct
                    _save(DISCOUNT_FILE, discount_config)
                    waiting.pop(uid, None)
                    bot.send_message(uid, f"✅ បាន **បើក** ការបញ្ចុះតម្លៃ **{pct}%** លើរាល់សេវាកម្មទាំងអស់!", parse_mode="HTML", reply_markup=admin_kb())
                    return
                except ValueError:
                    pass
            bot.send_message(uid, "❌ ទម្រង់មិនត្រឹមត្រូវ! ប្រើឧទាហរណ៍: <code>ON 15</code> ឬ <code>OFF</code>", parse_mode="HTML")
            return

        if text.startswith("/addbal"):
            parts = text.split()
            if len(parts) < 3:
                bot.send_message(uid, "ប្រើ: /addbal UID AMOUNT"); return
            try:
                target = parts[1]; amt = float(parts[2])
                add_bal(int(target), amt)
                bot.send_message(uid,
                    f"✅ +${amt:.2f} → <code>{target}</code>\n💳 Balance: <b>${bal(int(target)):.2f}</b>",
                    parse_mode="HTML", reply_markup=admin_kb())
                try: bot.send_message(int(target),
                    f"✅ <b>Admin បន្ថែមលុយ!</b>\n💰 +${amt:.2f} | សាច់ប្រាក់: <b>${bal(int(target)):.2f}</b>",
                    parse_mode="HTML")
                except: pass
            except: bot.send_message(uid, "❌ Format ខុស")
            return

        if text.startswith("/deductbal"):
            parts = text.split()
            if len(parts) < 3:
                bot.send_message(uid, "ប្រើ: /deductbal UID AMOUNT"); return
            try:
                target = parts[1]; amt = float(parts[2])
                cur = bal(int(target))
                ded = min(amt, cur)
                ded_bal(int(target), ded)
                bot.send_message(uid,
                    f"✅ -${ded:.2f} → <code>{target}</code>\n💳 សាច់ប្រាក់: <b>${bal(int(target)):.2f}</b>",
                    parse_mode="HTML", reply_markup=admin_kb())
            except: bot.send_message(uid, "❌ Format ខុស")
            return

        if isinstance(step, dict) and step.get("step") == "add_balance_amt":
            target = step["target"]
            try:
                amt = float(text.replace("$",""))
                add_bal(int(target), amt)
                _save(WALLETS_FILE, wallets)
                waiting.pop(uid, None)
                bot.send_message(uid,
                    f"✅ <b>បន្ថែម Balance</b>\n👤 <code>{target}</code>\n"
                    f"💰 +${amt:.2f} | សាច់ប្រាក់: <b>${bal(int(target)):.2f}</b>",
                    parse_mode="HTML", reply_markup=admin_kb())
                try: bot.send_message(int(target),
                    f"✅ <b>Admin បន្ថែមលុយ!</b>\n💰 +${amt:.2f} | សាច់ប្រាក់: <b>${bal(int(target)):.2f}</b>",
                    parse_mode="HTML")
                except: pass
            except: bot.send_message(uid, "❌ Amount ខុស! ឧ: <code>5.00</code>", parse_mode="HTML")
            return

        if isinstance(step, dict) and step.get("step") == "deduct_balance_amt":
            target = step["target"]
            try:
                amt  = float(text.replace("$",""))
                cur  = bal(int(target))
                ded  = min(amt, cur)
                ded_bal(int(target), ded)
                waiting.pop(uid, None)
                bot.send_message(uid,
                    f"✅ <b>កាត់ Balance</b>\n👤 <code>{target}</code>\n"
                    f"💔 -${ded:.2f} | សាច់ប្រាក់: <b>${bal(int(target)):.2f}</b>",
                    parse_mode="HTML", reply_markup=admin_kb())
                try: bot.send_message(int(target),
                    f"⚠️ <b>Admin កាត់លុយ!</b>\n💔 -${ded:.2f} | សាច់ប្រាក់: <b>${bal(int(target)):.2f}</b>",
                    parse_mode="HTML")
                except: pass
            except: bot.send_message(uid, "❌ Amount ខុស!")
            return

        if step == "promo_add_code":
            parts = text.strip().split()
            if len(parts) < 4:
                bot.send_message(uid,
                    "❌ Format ខុស!\nឧ: <code>SAVE50 50 pct 100</code>", parse_mode="HTML"); return
            code = parts[0].upper()
            try:
                discount = float(parts[1])
                pct  = (parts[2].lower() == "pct")
                uses = int(parts[3])
            except:
                bot.send_message(uid, "❌ Format ខុស!", parse_mode="HTML"); return
            promos[code] = {"discount": discount, "pct": pct, "uses": uses, "used": 0}
            _save(PROMO_FILE, promos)
            waiting.pop(uid, None)
            dtype = f"{discount:.0f}%" if pct else f"${discount:.2f}"
            bot.send_message(uid,
                f"✅ <b>Promo Code Created!</b>\n"
                f"🎟️ <code>{code}</code> — <b>{dtype}</b> | {uses} uses",
                parse_mode="HTML", reply_markup=admin_kb()); return

        if step == "broadcast_msg":
            _do_broadcast(uid, message); return

        if isinstance(step, dict) and step.get("step") == "add_stock_items":
            pid      = step["pid"]
            plan_idx = step.get("plan_idx")
            lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
            if not lines:
                bot.send_message(uid, "❌ គ្មានទិន្នន័យ"); return
            key = _stock_key(pid, plan_idx)
            if key not in stock: stock[key] = []
            for line in lines:
                stock[key].append({"data": line, "ts": int(time.time())})
            _save(STOCK_FILE, stock)
            waiting.pop(uid, None)
            p = _get_product(pid)
            plan_label = ""
            if plan_idx is not None and p:
                plans = p.get("plans", [])
                if plan_idx < len(plans):
                    plan_label = f" — {plans[plan_idx]['label']}"
            bot.send_message(uid,
                f"✅ បន្ថែម <b>{len(lines)}</b> accounts ទៅ <code>{pid}</code>{plan_label}\n"
                f"📦 Total: <b>{len(stock[key])}</b>",
                parse_mode="HTML", reply_markup=admin_kb()); return

        if step == "smm_add_cat":
            waiting[uid] = {"step": "smm_add_ids", "cat": text}
            bot.send_message(uid,
                f"📂 Category: <b>{text}</b>\n"
                f"ផ្ញើ API Service IDs (comma):\n"
                f"ឧ: <code>5441,5448,5502</code>",
                parse_mode="HTML", reply_markup=cancel_kb()); return

        if isinstance(step, dict) and step.get("step") == "smm_add_ids":
            cat = step["cat"]
            ids = [i.strip() for i in text.replace(" ","").split(",") if i.strip().isdigit()]
            if not ids:
                bot.send_message(uid, "❌ ផ្ញើ IDs ជាលេខ ឧ: <code>5441,5448</code>", parse_mode="HTML"); return
            bot.send_message(uid, f"⏳ Fetching {len(ids)} services from API...")
            ok, fail = [], []
            for api_id in ids:
                info = _smm_fetch_service(api_id)
                if info:
                    slug = f"{cat.lower().replace(' ','_')}_{api_id}"
                    smm_services[slug] = {
                        "api_id": api_id, "cost_rate": info["cost_rate"],
                        "min": info["min"], "max": info["max"],
                        "label": _smm_clean_name(info["raw_name"]), "category": cat,
                    }
                    ok.append(f"✅ <code>{api_id}</code> — {smm_services[slug]['label']}")
                else:
                    fail.append(f"❌ <code>{api_id}</code> — not found")
            _save(SMM_SVC_FILE, smm_services)
            waiting.pop(uid, None)
            msg = f"<b>📊 SMM Import — {cat}</b>\n━━━━━━━━━━━━━━━━━━\n" + "\n".join(ok)
            if fail: msg += "\n\n<b>Failed:</b>\n" + "\n".join(fail)
            msg += f"\n\n✅ Total services: <b>{len(smm_services)}</b>"
            bot.send_message(uid, msg, parse_mode="HTML", reply_markup=admin_kb()); return

        if isinstance(step, dict) and step.get("step") == "edit_price_val":
            pid      = step["pid"]
            plan_idx = step["plan_idx"]
            p        = _get_product(pid)
            if not p:
                waiting.pop(uid, None); bot.send_message(uid, "❌ Product រកមិនឃើញ", reply_markup=admin_kb()); return
            try:
                new_price = round(float(text.replace("$","")), 2)
                if new_price < 0: raise ValueError
            except:
                bot.send_message(uid, "❌ តម្លៃខុស! ឧ: <code>2.50</code>", parse_mode="HTML"); return
            old_price = p["plans"][plan_idx]["price"]
            p["plans"][plan_idx]["price"] = new_price
            _save(PRODUCTS_FILE, products)
            waiting.pop(uid, None)
            bot.send_message(uid,
                f"✅ <b>តម្លៃបានកែ!</b>\n"
                f"📦 {p.get('icon','')} <b>{p['name']}</b> — {p['plans'][plan_idx]['label']}\n"
                f"💰 ${old_price:.2f} → <b>${new_price:.2f}</b>",
                parse_mode="HTML", reply_markup=admin_kb()); return

        if isinstance(step, dict) and step.get("step") == "edit_label_val":
            pid      = step["pid"]
            plan_idx = step["plan_idx"]
            p        = _get_product(pid)
            if not p:
                waiting.pop(uid, None); bot.send_message(uid, "❌ Product រកមិនឃើញ", reply_markup=admin_kb()); return
            new_label = text.strip()
            if not new_label:
                bot.send_message(uid, "❌ ឈ្មោះ Plan មិនអាចទទេ!"); return
            old_label = p["plans"][plan_idx]["label"]
            p["plans"][plan_idx]["label"] = new_label
            _save(PRODUCTS_FILE, products)
            waiting.pop(uid, None)
            bot.send_message(uid,
                f"✅ <b>ឈ្មោះ Plan បានកែ!</b>\n"
                f"📦 {p.get('icon','')} <b>{p['name']}</b>\n"
                f"🏷️ <b>{old_label}</b> → <b>{new_label}</b>",
                parse_mode="HTML", reply_markup=admin_kb()); return

        if isinstance(step, dict) and step.get("step") == "edit_price_newplan_label":
            pid   = step["pid"]
            label = text.strip()
            if not label:
                bot.send_message(uid, "❌ ឈ្មោះ Plan មិនអាចទទេ!"); return
            waiting[uid] = {"step": "edit_price_newplan_price", "pid": pid, "label": label}
            bot.send_message(uid,
                f"💰 Plan: <b>{label}</b>\nផ្ញើ <b>តម្លៃ</b> (USD):\n<i>ឧ: <code>2.50</code></i>",
                parse_mode="HTML", reply_markup=cancel_kb()); return

        if isinstance(step, dict) and step.get("step") == "edit_price_newplan_price":
            pid   = step["pid"]
            label = step["label"]
            p     = _get_product(pid)
            if not p:
                waiting.pop(uid, None); bot.send_message(uid, "❌ Product រកមិនឃើញ", reply_markup=admin_kb()); return
            try:
                price = round(float(text.replace("$","")), 2)
                if price < 0: raise ValueError
            except:
                bot.send_message(uid, "❌ តម្លៃខុស! ឧ: <code>2.50</code>", parse_mode="HTML"); return
            p["plans"].append({"label": label, "price": price})
            _save(PRODUCTS_FILE, products)
            waiting.pop(uid, None)
            bot.send_message(uid,
                f"✅ <b>Plan ថ្មីបានបន្ថែម!</b>\n"
                f"📦 {p.get('icon','')} <b>{p['name']}</b>\n"
                f"🏷️ <b>{label}</b> — ${price:.2f}",
                parse_mode="HTML", reply_markup=admin_kb()); return

        if step == "smm_set_profit":
            try:
                pct = float(text)
                smm_profit["pct"] = pct; _save(SMM_PROFIT_FILE, smm_profit)
                waiting.pop(uid, None)
                bot.send_message(uid, f"✅ SMM Profit <b>{pct:.0f}%</b>",
                                 parse_mode="HTML", reply_markup=admin_kb())
            except: bot.send_message(uid, "❌ ត្រូវជាលេខ")
            return

        if step == "smm_api_url":
            smm_api["url"] = text.strip().rstrip("/")
            waiting[uid] = "smm_api_key"
            bot.send_message(uid,
                f"✅ URL: <code>{smm_api['url']}</code>\n\n🔑 ឥឡូវ ផ្ញើ API Key:",
                parse_mode="HTML", reply_markup=cancel_kb()); return

        if step == "smm_api_key":
            smm_api["key"] = text.strip()
            _save(SMM_API_FILE, smm_api)
            waiting.pop(uid, None)
            bot.send_message(uid, "⏳ Testing connection...", reply_markup=admin_kb())
            try:
                r = http.post(smm_api["url"],
                              data={"key": smm_api["key"], "action": "balance"},
                              timeout=10)
                d = r.json()
                balance  = d.get("balance", d.get("Balance", "?"))
                currency = d.get("currency", d.get("Currency", "USD"))
                bot.send_message(uid,
                    f"✅ <b>SMM API ភ្ជាប់ហើយ!</b>\n━━━━━━━━━━━━━━━━━━\n"
                    f"🌐 URL: <code>{smm_api['url']}</code>\n"
                    f"💰 សាច់ប្រាក់: <b>{balance} {currency}</b>",
                    parse_mode="HTML", reply_markup=admin_kb())
            except Exception as e:
                bot.send_message(uid,
                    f"⚠️ API Saved ប៉ុន្តែ test failed: <code>{e}</code>",
                    parse_mode="HTML", reply_markup=admin_kb())
            return

        if step == "add_product_name":
            waiting[uid] = {"step": "add_product_icon", "name": text}
            bot.send_message(uid, f"<b>{text}</b>\nផ្ញើ Icon emoji (ឧ: ✂️ ឬ 💎):", parse_mode="HTML"); return

        if isinstance(step, dict) and step.get("step") == "add_product_icon":
            waiting[uid] = {"step": "add_product_desc", "name": step["name"], "icon": text}
            bot.send_message(uid, "ផ្ញើ Description:"); return

        if isinstance(step, dict) and step.get("step") == "add_product_desc":
            pid = step["name"].lower().replace(" ","_")
            products.append({"id": pid, "name": step["name"], "icon": step["icon"],
                             "desc": text, "plans": []})
            _save(PRODUCTS_FILE, products)
            waiting.pop(uid, None)
            bot.send_message(uid,
                f"✅ Product <b>{step['name']}</b> បង្កើតបានរួច!\n"
                "ប្រើ ✏️ កែតម្លៃ ដើម្បីបន្ថែម plans.",
                parse_mode="HTML", reply_markup=admin_kb()); return

        if text == "🛍️ ផលិតផល":
            if not products:
                bot.send_message(uid, "❌ គ្មានផលិតផល", reply_markup=admin_kb()); return
            for p in products:
                plans = p.get("plans", [])
                plans_txt = ""
                for i, pl in enumerate(plans):
                    cnt = _get_plan_stock_count(p["id"], i) if p["id"] != "freefire" else 999
                    oos = "" if p["id"] == "freefire" else (" ❌ អស់" if cnt == 0 else "")
                    stock_label = "Game (UID)" if p["id"] == "freefire" else f"ស្តុក: <b>{cnt}</b>"
                    plans_txt += f"  • {pl['label']} — <b>${pl['price']:.2f}</b> │ {stock_label}{oos}\n"
                if not plans_txt: plans_txt = "  (គ្មាន plan)\n"
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📦 មើលស្តុក",      callback_data=f"admprod:stock:{p['id']}"),
                     InlineKeyboardButton("🗑️ លុបស្តុក",      callback_data=f"admprod:clrstock:{p['id']}")],
                    [InlineKeyboardButton("❌ លុបផលិតផល",     callback_data=f"admprod:del:{p['id']}")],
                ])
                bot.send_message(uid,
                    f"{p.get('icon','📦')} <b>{p['name']}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🆔 ID: <code>{p['id']}</code>\n"
                    f"💰 Plans & ស្តុក:\n{plans_txt}",
                    parse_mode="HTML", reply_markup=kb)
            return

        if text == "📦 ការបញ្ជាទិញ":
            if not orders:
                bot.send_message(uid, "❌ គ្មានការបញ្ជាទិញ", reply_markup=admin_kb()); return
            lines = ["<b>📦 ការបញ្ជាទិញ (20 ចុងក្រោយ)</b>\n━━━━━━━━━━━━━━━━━━"]
            for oid, o in list(orders.items())[-20:]:
                lines.append(f"🆔 <code>{oid}</code> | 👤 <code>{o['uid']}</code> | {o.get('prod_name','?')} — {o.get('plan','?')} | ${o.get('price',0):.2f}")
            bot.send_message(uid, "\n".join(lines)[:4000], parse_mode="HTML", reply_markup=admin_kb()); return

        if text == "📊 ការបញ្ជា SMM":
            if not smm_orders:
                bot.send_message(uid, "❌ គ្មានការបញ្ជា SMM", reply_markup=admin_kb()); return
            lines = ["<b>📊 ការបញ្ជា SMM (20 ចុងក្រោយ)</b>\n━━━━━━━━━━━━━━━━━━"]
            for oid, o in list(smm_orders.items())[-20:]:
                lines.append(f"🆔 <code>{oid}</code> | 👤 <code>{o['uid']}</code>\n  {o.get('label','?')} | Qty:{o.get('qty','?')} | ${o.get('price',0):.4f} | {o.get('status','?')}")
            bot.send_message(uid, "\n".join(lines)[:4000], parse_mode="HTML", reply_markup=admin_kb()); return

        if text == "⚙️ កំណត់ SMM API":
            cur_url = smm_api.get("url","❌ មិនទាន់ set")
            cur_key = smm_api.get("key","❌ មិនទាន់ set")
            masked = cur_key[:6] + "****" + cur_key[-4:] if len(cur_key) > 10 else cur_key
            kb_api = InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ កំណត់ URL + Key", callback_data="smmapi:setup")],
                [InlineKeyboardButton("🔌 សាកល្បងភ្ជាប់", callback_data="smmapi:test")],
                [InlineKeyboardButton("🗑️ លុប API", callback_data="smmapi:clear")],
            ])
            bot.send_message(uid,
                f"⚙️ <b>SMM API Config</b>\n━━━━━━━━━━━━━━━━━━\n"
                f"🌐 URL: <code>{cur_url}</code>\n"
                f"🔑 Key: <code>{masked}</code>\n"
                f"━━━━━━━━━━━━━━━━━━",
                parse_mode="HTML", reply_markup=kb_api); return

        if text == "💰 កាបូបលុយ":
            lines = ["<b>💰 កាបូបលុយអ្នកប្រើ</b>\n━━━━━━━━━━━━━━━━━━"]
            for u_id, u_info in sorted(users_db.items(), key=lambda x: x[1].get("last",0), reverse=True)[:30]:
                b = wallets.get(u_id, 0)
                name = u_info.get("name","?")
                lines.append(f"👤 <b>{name}</b> <code>{u_id}</code> — <b>${float(b):.2f}</b>")
            bot.send_message(uid, "\n".join(lines)[:4000], parse_mode="HTML", reply_markup=admin_kb()); return

        if text == "📊 ស្ថិតិ":
            total_orders = len(orders) + len(smm_orders)
            total_users  = len(users_db)
            total_rev    = sum(float(o.get("price",0)) for o in orders.values())
            total_rev   += sum(float(o.get("price",0)) for o in smm_orders.values())
            bot.send_message(uid,
                f"📊 <b>ស្ថិតិ</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"👥 អ្នកប្រើ: <b>{total_users}</b>\n"
                f"📦 ការបញ្ជាសរុប: <b>{total_orders}</b>\n"
                f"💰 ចំណូលសរុប: <b>${total_rev:.2f}</b>\n"
                f"🎟️ Promo សកម្ម: <b>{len(promos)}</b>",
                parse_mode="HTML", reply_markup=admin_kb()); return

        if text == "👥 អ្នកប្រើប្រាស់":
            users_sorted = sorted(users_db.items(), key=lambda x: x[1].get("last",0), reverse=True)[:20]
            if not users_sorted:
                bot.send_message(uid, "❌ គ្មានអ្នកប្រើ", reply_markup=admin_kb()); return
            for u_id, u_info in users_sorted:
                b    = float(wallets.get(u_id, 0))
                name = u_info.get("name","?") or "?"
                uname= f"@{u_info['username']}" if u_info.get("username") else ""
                banned = u_info.get("banned", False)
                ban_label = "🔓 លែង Ban" if banned else "🚫 Ban"
                ban_cb    = f"useraction:unban:{u_id}" if banned else f"useraction:ban:{u_id}"
                status = " 🚫 BANNED" if banned else ""
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💸 បន្ថែមប្រាក់",  callback_data=f"useraction:addbal:{u_id}"),
                     InlineKeyboardButton("💔 កាត់ប្រាក់",    callback_data=f"useraction:dedbal:{u_id}")],
                    [InlineKeyboardButton(ban_label,           callback_data=ban_cb)],
                ])
                bot.send_message(uid,
                    f"👤 <b>{name}</b>{status}\n"
                    f"🆔 <code>{u_id}</code>  {uname}\n"
                    f"💳 Balance: <b>${b:.2f}</b>",
                    parse_mode="HTML", reply_markup=kb)
            return

        if text == "💳 ប្រាក់បញ្ញើ":
            pend = [(k, v) for k, v in store_deps.items() if v.get("status")=="pending"]
            if not pend:
                bot.send_message(uid, "✅ គ្មានការដាក់លុយ pending", reply_markup=admin_kb()); return
            lines = ["<b>💳 ប្រាក់បញ្ញើ រង់ចាំ</b>\n━━━━━━━━━━━━━━━━━━"]
            for k, v in pend:
                lines.append(f"👤 <code>{v.get('uid','?')}</code> | ${v.get('amount',0):.2f}\n  /addbal {v.get('uid','?')} {v.get('amount',0):.2f}")
            bot.send_message(uid, "\n".join(lines)[:4000], parse_mode="HTML", reply_markup=admin_kb()); return

        if text == "📦 ស្តុក":
            lines = ["<b>📦 ទិដ្ឋភាពស្តុក</b>\n━━━━━━━━━━━━━━━━━━"]
            for p in products:
                plans = p.get("plans", [])
                lines.append(f"\n{p.get('icon','')} <b>{p['name']}</b>")
                if p["id"] == "freefire":
                    lines.append(f"  • Game Top Up (Player ID)")
                elif plans:
                    for i, pl in enumerate(plans):
                        cnt   = _get_plan_stock_count(p["id"], i)
                        alert = " ⚠️" if 0 < cnt <= STOCK_ALERT_MIN else ""
                        oos   = " ❌ អស់" if cnt == 0 else ""
                        lines.append(f"  • {pl['label']} — <b>{cnt}</b>{alert}{oos}")
                else:
                    cnt = len(_get_stock(p["id"]))
                    alert = " ⚠️" if 0 < cnt <= STOCK_ALERT_MIN else ""
                    oos   = " ❌ អស់" if cnt == 0 else ""
                    lines.append(f"  (no plan) — <b>{cnt}</b>{alert}{oos}")
            bot.send_message(uid, "\n".join(lines), parse_mode="HTML", reply_markup=admin_kb()); return

        if text == "➕ បន្ថែមស្តុក":
            if not products:
                bot.send_message(uid, "❌ បង្កើតផលិតផលជាមុនសិន", reply_markup=admin_kb()); return
            btns = []
            for p in products:
                if p["id"] == "freefire": continue
                btns.append([InlineKeyboardButton(
                    f"{p.get('icon','📦')} {p['name']}", callback_data=f"addstock_prod:{p['id']}")])
            if not btns:
                bot.send_message(uid, "❌ គ្មានផលិតផលដែលត្រូវការស្តុកទេ។", reply_markup=admin_kb()); return
            bot.send_message(uid,
                "➕ <b>បន្ថែមស្តុក</b>\n━━━━━━━━━━━━━━━━━━\nជ្រើសផលិតផល:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(btns)); return

        if text == "➕ បន្ថែមផលិតផល":
            waiting[uid] = "add_product_name"
            bot.send_message(uid, "➕ <b>ឈ្មោះផលិតផល:</b>", parse_mode="HTML", reply_markup=cancel_kb()); return

        if text == "✏️ កែតម្លៃ":
            if not products:
                bot.send_message(uid, "❌ គ្មានផលិតផល", reply_markup=admin_kb()); return
            btns = []
            for p in products:
                btns.append([InlineKeyboardButton(
                    f"{p.get('icon','📦')} {p['name']}", callback_data=f"editprice_prod:{p['id']}")])
            bot.send_message(uid,
                "✏️ <b>កែតម្លៃ / Plan</b>\n━━━━━━━━━━━━━━━━━━\nជ្រើសផលិតផល:",
                parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns)); return

        if text == "💸 បន្ថែមប្រាក់":
            users_sorted = sorted(users_db.items(), key=lambda x: x[1].get("last",0), reverse=True)[:15]
            btns = []
            for u_id, u_info in users_sorted:
                b    = float(wallets.get(u_id, 0))
                name = (u_info.get("name") or "?")[:18]
                btns.append([InlineKeyboardButton(
                    f"👤 {name}  ${b:.2f}", callback_data=f"useraction:addbal:{u_id}")])
            bot.send_message(uid,
                "💸 <b>បន្ថែមប្រាក់</b>\n━━━━━━━━━━━━━━━━━━\nជ្រើសអ្នកប្រើ:",
                parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns)); return

        if text == "💔 កាត់ប្រាក់":
            users_sorted = sorted(users_db.items(), key=lambda x: x[1].get("last",0), reverse=True)[:15]
            btns = []
            for u_id, u_info in users_sorted:
                b    = float(wallets.get(u_id, 0))
                name = (u_info.get("name") or "?")[:18]
                btns.append([InlineKeyboardButton(
                    f"👤 {name}  ${b:.2f}", callback_data=f"useraction:dedbal:{u_id}")])
            bot.send_message(uid,
                "💔 <b>កាត់ប្រាក់</b>\n━━━━━━━━━━━━━━━━━━\nជ្រើសអ្នកប្រើ:",
                parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns)); return

        if text == "🎟️ លេខកូដPromo":
            _show_promos(uid)
            bot.send_message(uid,
                "🎟️ <b>គ្រប់គ្រង Promo Code</b>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ បន្ថែម Code", callback_data="adminpromo:add"),
                     InlineKeyboardButton("📋 មើលទាំងអស់", callback_data="adminpromo:list")]
                ])); return

        if text == "📢 ផ្សព្វផ្សាយ":
            waiting[uid] = "broadcast_msg"
            bot.send_message(uid,
                "📢 <b>ផ្សព្វផ្សាយ</b>\nផ្ញើ Message (text/photo/video):",
                parse_mode="HTML", reply_markup=cancel_kb()); return

        if text == "💹 ប្រាក់ចំណេញ SMM":
            waiting[uid] = "smm_set_profit"
            bot.send_message(uid,
                f"💹 <b>ប្រាក់ចំណេញ SMM: {_smm_profit_pct():.0f}%</b>\nផ្ញើ % ថ្មី:",
                parse_mode="HTML", reply_markup=cancel_kb()); return

        if text == "⏱ ល្បឿន Poll":
            cur = smm_poll.get("interval", 5)
            bot.send_message(uid, f"⏱ ល្បឿន Poll (បច្ចុប្បន្ន: {cur}s)",
                             reply_markup=InlineKeyboardMarkup([
                                 [InlineKeyboardButton("⚡ 3s", callback_data="poll:3"),
                                  InlineKeyboardButton("🟢 5s", callback_data="poll:5"),
                                  InlineKeyboardButton("🔵 10s", callback_data="poll:10")],
                                 [InlineKeyboardButton("🟡 15s", callback_data="poll:15"),
                                  InlineKeyboardButton("🔴 30s", callback_data="poll:30")],
                             ])); return

        if text == "🔄 ធ្វើឱ្យទាន់សម័យ":
            bot.send_message(uid, "✅ បានធ្វើឱ្យទាន់សម័យ!", reply_markup=admin_kb()); return

        if text == "➕ បន្ថែម SMM":
            cats_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎵 TikTok",    callback_data="smmaddcat:TikTok"),
                 InlineKeyboardButton("📘 Facebook",  callback_data="smmaddcat:Facebook")],
                [InlineKeyboardButton("📸 Instagram", callback_data="smmaddcat:Instagram"),
                 InlineKeyboardButton("▶️ YouTube",   callback_data="smmaddcat:YouTube")],
                [InlineKeyboardButton("📱 Telegram",  callback_data="smmaddcat:Telegram"),
                 InlineKeyboardButton("🐦 Twitter",   callback_data="smmaddcat:Twitter")],
                [InlineKeyboardButton("✏️ Custom Category", callback_data="smmaddcat:custom")],
            ])
            bot.send_message(uid,
                "➕ <b>បន្ថែម SMM Service</b>\n━━━━━━━━━━━━━━━━━━\nជ្រើស Category:",
                parse_mode="HTML", reply_markup=cats_kb); return

        if text == "🗑️ លុប SMM":
            if not smm_services:
                bot.send_message(uid, "❌ គ្មាន SMM Service ទេ", reply_markup=admin_kb()); return
            cats = {}
            for slug, s in smm_services.items():
                cat = s.get("category", "Other")
                cats.setdefault(cat, []).append((slug, s))
            for cat, svcs in cats.items():
                btns = []
                for slug, s in svcs:
                    label = s.get("label", slug)[:30]
                    api_id = s.get("api_id", "?")
                    btns.append([InlineKeyboardButton(
                        f"🗑️ [{api_id}] {label}",
                        callback_data=f"delsvc:{slug}"
                    )])
                btns.append([InlineKeyboardButton(
                    f"🗑️ លុបទាំងអស់ {cat}",
                    callback_data=f"delsvc:cat:{cat}"
                )])
                bot.send_message(uid,
                    f"📂 <b>{cat}</b> — {len(svcs)} services\n━━━━━━━━━━━━━━━━━━",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(btns))
            return

        if text == "💰 ឆែកលុយ API":
            url = smm_api.get("url",""); key = smm_api.get("key","")
            if not url or not key:
                bot.send_message(uid, "❌ SMM API មិនទាន់ set! ចូល ⚙️ Set SMM API", reply_markup=admin_kb()); return
            try:
                r = http.post(url, data={"key": key, "action": "balance"}, timeout=10)
                d = r.json()
                balance  = d.get("balance", d.get("Balance", "?"))
                currency = d.get("currency", d.get("Currency", "USD"))
                bot.send_message(uid,
                    f"💰 <b>SMM API សាច់ប្រាក់</b>\n━━━━━━━━━━━━━━━━━━\n"
                    f"💵 សាច់ប្រាក់: <b>{balance} {currency}</b>\n"
                    f"🌐 API: <code>{url}</code>",
                    parse_mode="HTML", reply_markup=admin_kb())
            except Exception as e:
                bot.send_message(uid, f"❌ API Error: {e}", reply_markup=admin_kb())
            return

        if text.startswith("━━━"):
            bot.send_message(uid, "👇 ជ្រើស menu ខាងក្រោម:", reply_markup=admin_kb()); return

        bot.send_message(uid, f"❓ ពាក្យបញ្ជាមិនស្គាល់។ ប្រើប៊ូតុង Menu ខាងក្រោម។", reply_markup=admin_kb()); return

    # ══════════════════════════════════════════════════════
    #  USER SECTION
    # ══════════════════════════════════════════════════════

    if isinstance(step, dict) and step.get("step") == "dep_enter_promo":
        msg_id = step.get("msg_id")
        code   = text.strip().upper()
        _, _, err = apply_promo(uid, code, 1.0)
        if err:
            bot.send_message(uid, err + "\nព្យាយាមម្ដងទៀត:", reply_markup=cancel_kb()); return
        waiting[uid] = {"step": "dep_choose_amt", "promo": code}
        p = promos.get(code, {})
        dtype = f"{p['discount']:.0f}%" if p.get("pct") else f"${float(p.get('discount',0)):.2f}"
        bot.send_message(uid,
            f"✅ Promo <b>{code}</b> ({dtype} bonus) applied!\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"ចុច ចំនួន ដើម្បី deposit:",
            parse_mode="HTML",
            reply_markup=deposit_amt_kb(uid, code)); return

    if isinstance(step, dict) and step.get("step") == "dep_choose_amt":
        try:
            amount = float(text.replace("$",""))
            if amount < 0.5: raise ValueError
            promo_code = step.get("promo")
            waiting.pop(uid, None)
            _process_deposit(uid, uid_str, amount, promo_code)
        except:
            bot.send_message(uid, "❌ ចំនួនខុស! ឧ: <code>5.00</code>", parse_mode="HTML")
        return

    if isinstance(step, dict) and step.get("step") == "dep_custom":
        try:
            amount = float(text.replace("$",""))
            if amount < 0.5: raise ValueError
            promo_code = step.get("promo")
            waiting.pop(uid, None)
            _process_deposit(uid, uid_str, amount, promo_code)
        except:
            bot.send_message(uid, "❌ ចំនួនខុស! ឧ: <code>5.00</code>", parse_mode="HTML")
        return

    if step == "dep_custom":
        try:
            amount = float(text.replace("$",""))
            if amount < 0.5: raise ValueError
            waiting.pop(uid, None)
            _process_deposit(uid, uid_str, amount, None)
        except:
            bot.send_message(uid, "❌ ចំនួនខុស! ឧ: <code>5.00</code>", parse_mode="HTML")
        return

    if isinstance(step, dict) and step.get("step") == "order_freefire_uid":
        prod_id  = step["prod_id"]
        plan_idx = step["plan_idx"]
        unit_price = step["price"]
        player_id = text.strip()
        
        waiting.pop(uid, None)
        p = _get_product(prod_id)
        if not p:
            bot.send_message(uid, "❌ Product រកមិនឃើញ", reply_markup=main_kb(uid)); return
        plan = p.get('plans', [])[plan_idx]
        
        if bal(uid) < unit_price:
            bot.send_message(uid,
                f"❌ Balance មិនគ្រប់!\n💳 Balance: <b>${bal(uid):.2f}</b>\n"
                f"🛒 Need: <b>${unit_price:.2f}</b>",
                parse_mode="HTML", reply_markup=main_kb(uid)); return

        plan["items"] = [f"Player ID: {player_id}"]
        oid, err = _place_store_order(uid, prod_id, plan_idx)
        if err:
            bot.send_message(uid, err, reply_markup=main_kb(uid)); return
            
        deliver_txt = (
            f"✅ <b>បញ្ជាទិញ Top Up Game បានជោគជ័យ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <code>{oid}</code>\n"
            f"💎 {p['name']} — {plan['label']}\n"
            f"🎮 Player ID: <code>{player_id}</code>\n"
            f"💰 បានបង់: <b>${unit_price:.2f}</b>\n"
            f"💳 សាច់ប្រាក់នៅសល់: <b>${bal(uid):.2f}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⏳ Admin កំពុងចាក់ពេជ្រជូនយ៉ាងលឿន!"
        )
        bot.send_message(uid, deliver_txt, parse_mode="HTML", reply_markup=main_kb(uid))
        try: bot.send_message(ADMIN_ID,
            f"💎 <b>New Game Top Up Order!</b>\n👤 User: <code>{uid_str}</code>\n"
            f"📦 {p['name']} | {plan['label']} | ID: <code>{player_id}</code> | ${unit_price:.2f}", parse_mode="HTML")
        except: pass
        return

    if isinstance(step, dict) and step.get("step") == "order_qty":
        prod_id  = step["prod_id"]
        plan_idx = step["plan_idx"]
        unit_price = step["price"]
        try:
            qty = int(text.strip())
            if qty <= 0: raise ValueError
        except:
            bot.send_message(uid, "❌ ចំនួនខុស! សូមបញ្ចូលលេខតែមួយ:", reply_markup=cancel_kb()); return
        waiting.pop(uid, None)
        p = _get_product(prod_id)
        if not p:
            bot.send_message(uid, "❌ Product រកមិនឃើញ", reply_markup=main_kb(uid)); return
        plan = p.get('plans', [])[plan_idx]
        stock_cnt = _get_plan_stock_count(prod_id, plan_idx)
        if stock_cnt < qty:
            bot.send_message(uid, f"❌ Stock មិនគ្រប់! មាន: <b>{stock_cnt}</b>", parse_mode="HTML", reply_markup=main_kb(uid)); return
        final_price = round(float(unit_price) * qty, 2)
        if bal(uid) < final_price:
            bot.send_message(uid,
                f"❌ Balance មិនគ្រប់!\n💳 Balance: <b>${bal(uid):.2f}</b>\n"
                f"🛒 Need: <b>${final_price:.2f}</b>",
                parse_mode="HTML", reply_markup=main_kb(uid)); return
        orig_price = plan.get("price")
        orig_qty = plan.get("qty", None)
        plan["price"] = final_price
        plan["qty"] = qty
        oid, err = _place_store_order(uid, prod_id, plan_idx)
        plan["price"] = orig_price
        if orig_qty is None:
            plan.pop("qty", None)
        else:
            plan["qty"] = orig_qty
        if err:
            bot.send_message(uid, err, reply_markup=main_kb(uid)); return
        o = orders[oid]
        items = o.get("items", [])
        deliver_txt = (
            f"✅ <b>បញ្ជាទិញបានជោគជ័យ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <code>{oid}</code>\n"
            f"📦 {p['name']} — {plan['label']}\n"
            f"🔢 ចំនួន: <b>{qty}</b> | 💰 បានបង់: <b>${final_price:.2f}</b>"
        )
        deliver_txt += f"\n💳 សាច់ប្រាក់: <b>${bal(uid):.2f}</b>\n━━━━━━━━━━━━━━━━━━\n"
        for item in items:
            if isinstance(item, dict):
                if "data" in item: deliver_txt += f"<code>{item['data']}</code>\n"
                else:
                    for k, v in item.items(): deliver_txt += f"<b>{k}</b>: <code>{v}</code>\n"
            else:
                deliver_txt += f"<code>{item}</code>\n"
        bot.send_message(uid, deliver_txt, parse_mode="HTML", reply_markup=main_kb(uid))
        try: bot.send_message(ADMIN_ID,
            f"🛒 <b>New Order</b>\n👤 <code>{str(uid)}</code>\n"
            f"📦 {p['name']} | {qty} | ${final_price:.2f}", parse_mode="HTML")
        except: pass
        return

    if isinstance(step, dict) and step.get("step") == "smm_link":
        slug  = step["slug"]
        qty   = step["qty"]
        price = step["price"]
        waiting.pop(uid, None)
        link  = text
        if bal(uid) < price:
            bot.send_message(uid,
                f"❌ Balance មិនគ្រប់!\n💳 ${bal(uid):.2f} | Need: ${price:.4f}",
                parse_mode="HTML", reply_markup=main_kb(uid)); return
        s = smm_services.get(slug)
        sr = _smm_sell_rate(s["cost_rate"], slug)
        ded_bal(uid, price)
        key = smm_api.get("key",""); api_url = smm_api.get("url","")
        res = None
        if key and api_url:
            res = _smm_api_post({"key":key,"action":"add","service":s["api_id"],"link":link,"quantity":qty})
        api_oid = str(res.get("order","")) if res else ""
        oid = _make_order_id()
        smm_orders[oid] = {
            "uid":uid_str,"slug":slug,"label":s.get("label",slug),
            "qty":qty,"price":price,"link":link,"api_order_id":api_oid,
            "status":"pending","ts":int(time.time())
        }
        _save(SMM_ORD_FILE, smm_orders)
        bot.send_message(uid,
            f"✅ <b>បញ្ជា SMM បានជោគជ័យ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <code>{oid}</code>\n"
            f"📊 {s.get('label',slug)}\n"
            f"🔢 ចំនួន: <b>{qty:,}</b> | 💰 <b>${price:.4f}</b>\n"
            f"🔗 <code>{link}</code>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💳 សាច់ប្រាក់: <b>${bal(uid):.2f}</b>",
            parse_mode="HTML", reply_markup=main_kb(uid))
        try: bot.send_message(ADMIN_ID,
            f"📊 <b>SMM Order</b>\n👤 <code>{uid_str}</code> | {s.get('label',slug)} | {qty:,} | ${price:.4f}", parse_mode="HTML")
        except: pass
        return

    # ── Main menu buttons ──
    if text in ("🛍️ Shop", "🛍️ ហាងឌីជីថល", "🛍️ ហាង"):
        bot.send_message(uid,
            "🛍️ <b>ហាងឌីជីថល</b>\n━━━━━━━━━━━━━━━━━━",
            parse_mode="HTML", reply_markup=products_kb()); return

    if text in ("💎 ថុបអាប់ហ្គេម", "💎 Game Top Up"):
        p = _get_product("freefire")
        if not p:
            bot.send_message(uid, "❌ មិនទាន់មានសេវាកម្ម Top Up Game ទេ។", reply_markup=main_kb(uid))
            return
        bot.send_message(uid,
            f"💎 <b>{p['name']}</b>\n━━━━━━━━━━━━━━━━━━\nជ្រើសរើសកញ្ចប់ Top Up:",
            parse_mode="HTML", reply_markup=plans_kb("freefire"))
        return

    if text in ("📊 SMM Services", "📊 សេវាកម្ម SMM", "📊 សេវា SMM"):
        if not smm_services:
            bot.send_message(uid,
                "❌ គ្មាន SMM Service ទេ\n(Admin ចូល ⚙️ កំណត់ SMM API ដើម្បី import)",
                reply_markup=main_kb(uid)); return
        bot.send_message(uid,
            "📊 <b>SMM Services</b>\n━━━━━━━━━━━━━━━━━━\n"
            "ជ្រើស Platform:",
            parse_mode="HTML", reply_markup=smm_cat_kb()); return

    if text in ("💳 ដាក់ប្រាក់", "💰 ដាក់ប្រាក់", "💰 Top Up", "💳 Top Up", "💸 បញ្ចូលលុយ"):
        b = bal(uid)
        waiting.pop(uid, None)
        bot.send_message(uid,
            f"💸 <b>{'ដាក់លុយ' if lang=='kh' else 'Top Up Wallet'}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💳 សាច់ប្រាក់: <b>${b:.2f}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{'ជ្រើស ចំនួន ឬ ដាក់ Promo Code មុន:' if lang=='kh' else 'Choose Amount or add Promo Code first:'}",
            parse_mode="HTML",
            reply_markup=deposit_amt_kb(uid)); return

    if text in ("📦 បញ្ជាទិញ", "📦 ការបញ្ជាទិញ", "📦 Orders"):
        my_orders = {oid: o for oid, o in {**orders, **smm_orders}.items() if o.get("uid") == uid_str}
        if not my_orders:
            bot.send_message(uid,
                "📦 <b>បញ្ជាទិញ</b>\n\n❌ គ្មាន Order ទេ!",
                parse_mode="HTML", reply_markup=main_kb(uid)); return
        lines = [f"📦 <b>បញ្ជាទិញ</b>\n━━━━━━━━━━━━━━━━━━"]
        for oid, o in sorted(my_orders.items(), key=lambda x: x[1].get("ts",0), reverse=True)[:10]:
            if "prod_name" in o:
                lines.append(f"🛍️ <code>{oid}</code> — {o['prod_name']} | ${o.get('price',0):.2f}")
            else:
                lines.append(f"📊 <code>{oid}</code> — {o.get('label','?')} x{o.get('qty','?')} | ${o.get('price',0):.4f} | {o.get('status','?')}")
        bot.send_message(uid, "\n".join(lines), parse_mode="HTML", reply_markup=main_kb(uid)); return

    if text in ("💬 ជំនួយ Support", "💬 Support"):
        bot.send_message(uid, t(uid, "support_msg"), parse_mode="HTML", reply_markup=main_kb(uid)); return

    if text in ("👜 កាបូបលុយ", "👜 Wallet"):
        b = bal(uid)
        my_deps = [(k, v) for k, v in store_deps.items()
                   if v.get("uid"] == uid_str]
        confirmed = sum(float(v.get("amount",0)) for _, v in my_deps if v.get("status")=="confirmed")
        pending   = sum(float(v.get("amount",0)) for _, v in my_deps if v.get("status")=="pending")
        bot.send_message(uid,
            f"👜 <b>{'កាបូបលុយ' if lang=='kh' else 'My Wallet'}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💳 សាច់ប្រាក់: <b>${b:.2f}</b>\n"
            f"✅ សរុបដាក់: <b>${confirmed:.2f}</b>\n"
            f"⏳ កំពុងរង់ចាំ: <b>${pending:.2f}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"ចុច 💳 {'ដាក់ប្រាក់' if lang=='kh' else 'Top Up'} ដើម្បីដាក់លុយ",
            parse_mode="HTML", reply_markup=main_kb(uid)); return

    if text in ("📜 ប្រវត្តិ", "📋 ប្រវត្តិ", "📜 History", "📋 History"):
        my_orders = {oid: o for oid, o in {**orders, **smm_orders}.items()
                     if o.get("uid") == uid_str}
        if not my_orders:
            bot.send_message(uid,
                f"📜 <b>{'ប្រវត្តិ' if lang=='kh' else 'History'}</b>\n\n❌ {'គ្មាន Order ទេ!' if lang=='kh' else 'No orders yet!'}",
                parse_mode="HTML", reply_markup=main_kb(uid)); return
        lines = [f"📜 <b>{'ប្រវត្តិ' if lang=='kh' else 'History'}</b>\n━━━━━━━━━━━━━━━━━━"]
        for oid, o in sorted(my_orders.items(), key=lambda x: x[1].get("ts",0), reverse=True)[:15]:
            dt = datetime.datetime.fromtimestamp(o.get("ts",0)).strftime("%d/%m %H:%M")
            if "prod_name" in o:
                lines.append(f"🛍️ <code>{oid}</code> | {o['prod_name']} — {o.get('plan','?')} | <b>${o.get('price',0):.2f}</b> | {dt}")
            else:
                lines.append(f"📊 <code>{oid}</code> | {o.get('label','?')} x{o.get('qty','?')} | <b>${o.get('price',0):.4f}</b> | {o.get('status','?')} | {dt}")
        bot.send_message(uid, "\n".join(lines)[:4000], parse_mode="HTML", reply_markup=main_kb(uid)); return

    if text in ("💡 របៀបប្រើប្រាស់", "💡 How to Use", "💡 របៀបប្រើ"):
        bot.send_message(uid, t(uid, "how_to_use"), parse_mode="HTML", reply_markup=main_kb(uid)); return

    if text in ("🌐 ភូមិភាសា / Language", "🌐 ភាសា / Language", "🌐 Language"):
        bot.send_message(uid, t(uid, "select_lang"),
                         parse_mode="HTML", reply_markup=lang_select_kb()); return

    bot.send_message(uid, t(uid, "fallback"), reply_markup=main_kb(uid))

# ═══════════════════════════════════════════════════════════
#  BROADCAST
# ═══════════════════════════════════════════════════════════
def _do_broadcast(admin_uid, message):
    waiting.pop(admin_uid, None)
    sent = failed = 0
    for u_id in list(users_db.keys()):
        try:
            if message.photo:
                bot.send_photo(int(u_id), message.photo[-1].file_id, caption=message.caption or "")
            elif message.video:
                bot.send_video(int(u_id), message.video.file_id, caption=message.caption or "")
            else:
                bot.send_message(int(u_id), message.text or "", parse_mode="HTML")
            sent += 1
        except: failed += 1
        time.sleep(0.05)
    bot.send_message(admin_uid,
        f"📢 <b>ផ្សព្វផ្សាយរួចរាល់!</b>\n✅ បានផ្ញើ: {sent} | ❌ បរាជ័យ: {failed}",
        parse_mode="HTML", reply_markup=admin_kb())

# ═══════════════════════════════════════════════════════════
#  PHOTO HANDLER
# ═══════════════════════════════════════════════════════════
@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    uid = message.chat.id
    if uid == ADMIN_ID and waiting.get(uid) == "broadcast_msg":
        _do_broadcast(uid, message); return

# ═══════════════════════════════════════════════════════════
#  FLASK CONTROL SERVER
# ═══════════════════════════════════════════════════════════
flask_app = Flask(__name__)
CONTROL_KEY = "kairozen_secret_2025"

def _check_key():
    key = flask_request.args.get("key") or (flask_request.get_json(silent=True) or {}).get("key")
    return key == CONTROL_KEY

@flask_app.route("/health")
def health():
    return jsonify({"status": "running", "bot": "Kairozen v4"})

@flask_app.route("/status")
def status():
    if not _check_key():
        return jsonify({"error": "Unauthorized"}), 403
    return jsonify({
        "status": "running",
        "users": len(users_db),
        "orders": len(orders) + len(smm_orders),
        "wallets": len(wallets),
    })

@flask_app.route("/shutdown", methods=["GET", "POST"])
def shutdown():
    if not _check_key():
        return jsonify({"error": "Unauthorized — wrong key"}), 403
    logger.warning(f"{CLR_RED}🛑 Shutdown requested via control server!{CLR_RESET}")
    try:
        bot.send_message(ADMIN_ID, "🛑 <b>Bot កំពុងបិទ...</b>\nបានទទួល shutdown command តាម Control Server។", parse_mode="HTML")
        time.sleep(1)
    except: pass
    def _stop():
        time.sleep(0.5)
        bot.stop_polling()
        time.sleep(1)
        os._exit(0)
    threading.Thread(target=_stop, daemon=True).start()
    return jsonify({"status": "shutting_down", "message": "Bot is stopping..."})

@flask_app.route("/restart", methods=["GET", "POST"])
def restart():
    if not _check_key():
        return jsonify({"error": "Unauthorized — wrong key"}), 403
    logger.warning(f"{CLR_YELLOW}🔄 Restart requested via control server!{CLR_RESET}")
    try:
        bot.send_message(ADMIN_ID, "🔄 <b>Bot កំពុង Restart...</b>\nបានទទួល restart command តាម Control Server។", parse_mode="HTML")
        time.sleep(1)
    except: pass
    def _restart():
        time.sleep(0.5)
        bot.stop_polling()
        time.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)
    threading.Thread(target=_restart, daemon=True).start()
    return jsonify({"status": "restarting", "message": "Bot is restarting..."})

@flask_app.route("/broadcast_web", methods=["POST"])
def broadcast_web():
    if not _check_key():
        return jsonify({"error": "Unauthorized"}), 403
    data = flask_request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "No text provided"}), 400
    sent = failed = 0
    for u_id in list(users_db.keys()):
        try:
            bot.send_message(int(u_id), text, parse_mode="HTML")
            sent += 1
        except: failed += 1
        time.sleep(0.05)
    return jsonify({"sent": sent, "failed": failed})

def run_flask():
    logger.info(f"{CLR_CYAN}🌐 Control Server running on port 5055{CLR_RESET}")
    flask_app.run(host="0.0.0.0", port=5055, debug=False, use_reloader=False)

def print_banner():
    banner = f"""
{CLR_CYAN}{CLR_BOLD}╔══════════════════════════════════════════════════════════════╗
║     {CLR_GREEN}Kairozen All-in-One Bot v4 — カイロゼン                  {CLR_CYAN}║
║     {CLR_YELLOW}ហាង + SMM Panel · ដាក់លុយ KHQR · Top Up Game Menu       {CLR_CYAN}║
║     {CLR_MAGENTA}Global Discount · Panel Admin · Promo Code              {CLR_CYAN}║
║     {CLR_WHITE}Compatible: Python 3.10+ · Termux / Pydroid 3         {CLR_CYAN}║
╚══════════════════════════════════════════════════════════════╝{CLR_RESET}
"""
    print(banner)

# ═══════════════════════════════════════════════════════════
#  MAIN
# ════════════════អ្នកប្រើប្រាស់
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    print_banner()
    logger.info(f"{CLR_BOLD}{CLR_GREEN}🚀 Kairozen All-in-One Bot v4 កំពុងចាប់ផ្ដើម...{CLR_RESET}")
    threading.Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling(timeout=20, long_polling_timeout=15)
