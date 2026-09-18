# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║     Kairozen All-in-One Bot v4 — カイロゼン                  ║
║     ហាង + SMM Panel · ដាក់លុយ KHQR · Top Up Game Menu       ║
║     Global Discount · Panel Admin · Promo Code              ║
║     Compatible: Python 3.10+ · Termux / Pydroid 3 / Render  ║
╚══════════════════════════════════════════════════════════════╝
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
#  CONFIG  — កែប្រែតម្លៃខាងក្រោមតាមតម្រូវការ
# ═══════════════════════════════════════════════════════════
BOT_TOKEN          = "8914728102:AAFCUOmvtYKp3LLoBlg4H4Fbz5PE8joN2zU"
ADMIN_ID           = 8807182741

BAKONG_TOKEN       = "rbkMVUSQPooaey51jm1cD5ECnzmHyeNX7fBX4Afc16GU8k"
BANK_ACCOUNT       = "samnang_mon@bkrt"
MERCHANT_NAME      = "Khmer SMM"
MERCHANT_CITY      = "Phnom Penh"

DEPOSIT_EXPIRE_SEC = 180   
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
DISCOUNT_FILE   = "aio_discount.json"

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

waiting         = {}
lang_cooldown   = {}

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

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

def _make_session():
    s = http_req.Session()
    r = Retry(total=3, backoff_factor=2, status_forcelist=[500,502,503,504])
    a = HTTPAdapter(max_retries=r)
    s.mount("http://", a); s.mount("https://", a)
    return s
http = _make_session()

# ─── FLASK SERVER FOR RENDER KEEP-ALIVE ───
app = Flask(__name__)

@app.route('/')
def index():
    return "Kairozen Bot is running live!"

def run_flask():
    port = int(os.environ.get("PORT", 5055))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

# ─── LANGUAGE ───
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
            "📞 Admin: @SmeyLov008\n"
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

def bal(uid): return float(wallets.get(str(uid), 0))
def add_bal(uid, amt):
    wallets[str(uid)] = round(bal(uid) + amt, 2)
    _save(WALLETS_FILE, wallets)
def ded_bal(uid, amt):
    wallets[str(uid)] = max(0, round(bal(uid) - amt, 2))
    _save(WALLETS_FILE, wallets)

def _calc_discounted_price(price):
    if discount_config.get("active", False):
        pct = float(discount_config.get("pct", 0))
        return round(price * (1 - pct / 100), 2)
    return price

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

# ─── KEYBOARDS ───
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
    btns.append([InlineKeyboardButton("✏️ ផ្ទាល់ខ្លួន" if lang=="kh" else "✏️ Custom", callback_data="dep:custom")])
    if promo_code:
        btns.append([InlineKeyboardButton(f"🎟️ Promo: {promo_code} ✅", callback_data="dep:clrpromo")])
    else:
        btns.append([InlineKeyboardButton("🎟️ ដាក់ Promo Code" if lang=="kh" else "🎟️ Enter Promo Code", callback_data="dep:promo")])
    return InlineKeyboardMarkup(btns)

def smm_cat_kb():
    cats = []
    for s in smm_services.values():
        c = s.get("category", "Other")
        if c not in cats: cats.append(c)
    btns = []
    for cat in cats:
        btns.append([InlineKeyboardButton(f"📱  {cat}", callback_data=f"smmcat:{cat}")])
    btns.append([InlineKeyboardButton("🔙 Back", callback_data="back:main")])
    return InlineKeyboardMarkup(btns)

def smm_svc_kb(cat):
    svcs = [(slug, s) for slug, s in smm_services.items() if s.get("category") == cat]
    btns = []
    for slug, s in svcs:
        label = s.get("label", slug)
        btns.append([InlineKeyboardButton(f"⚡  {label}", callback_data=f"smmsvc:{slug}")])
    btns.append([InlineKeyboardButton("🔙 Back", callback_data="back:smmcats")])
    return InlineKeyboardMarkup(btns)

def smm_qty_kb(slug, s):
    sr   = 1.0 # default rate factor
    mn   = s.get("min", 100)
    mx   = s.get("max", 100000)
    qtys = [100, 500, 1000, 5000, 10000]
    btns = []
    for q in qtys:
        if mn <= q <= mx:
            btns.append([InlineKeyboardButton(f"{q:,}", callback_data=f"smmqty:{slug}:{q}")])
    btns.append([InlineKeyboardButton("🔙 Back", callback_data="back:smmcats")])
    return InlineKeyboardMarkup(btns)

def products_kb():
    btns = []
    for p in products:
        if p["id"] == "freefire": continue
        btns.append([InlineKeyboardButton(f"{p.get('icon','📦')} {p['name']}", callback_data=f"prod:{p['id']}")])
    btns.append([InlineKeyboardButton("🔙 Back", callback_data="back:main")])
    return InlineKeyboardMarkup(btns)

def plans_kb(prod_id):
    p = next((x for x in products if x["id"] == prod_id), None)
    if not p: return InlineKeyboardMarkup([])
    btns = []
    for i, plan in enumerate(p.get("plans", [])):
        price = _calc_discounted_price(float(plan['price']))
        btns.append([InlineKeyboardButton(f"✅ {plan['label']} — ${price:.2f}", callback_data=f"plan:{prod_id}:{i}")])
    btns.append([InlineKeyboardButton("🔙 Back", callback_data="back:shop")])
    return InlineKeyboardMarkup(btns)

# ─── BAKONG KHQR (Fixed parameter: account_id) ───
def _generate_khqr(uid, amount, note=""):
    try:
        from bakong_khqr import KHQR
        k = KHQR(BAKONG_TOKEN)
        qr_str = k.create_qr(
            account_id    = BANK_ACCOUNT,  # ធ្វើការកែសម្រួលត្រឹមត្រូវពី bank_account មកเป็น account_id ស្របតាមបណ្ណាល័យជំនាន់ថ្មី
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
            try:
                bot.send_message(uid, f"✅ <b>ដាក់លុយបានជោគជ័យ! +${total_credit:.2f}</b>", parse_mode="HTML", reply_markup=main_kb(uid))
            except: pass
            return
        time.sleep(POLL_INTERVAL)

def _send_deposit_qr(uid, amount, promo_code=None, label="💳 ដាក់ប្រាក់", bonus=0.0, promo_code_name=None):
    uid_str = str(uid)
    final_amount = amount
    if promo_code and not promo_code_name:
        fa, _, err = apply_promo(uid, code=promo_code, amount=amount)
        if not err:
            final_amount = fa; promo_code_name = promo_code

    qr_str = _generate_khqr(uid, final_amount, f"uid={uid} ${final_amount}")
    if not qr_str:
        bot.send_message(uid, "⚠️ មានបញ្ហា Generate QR! ទំនាក់ Admin", parse_mode="HTML")
        return

    try:
        from bakong_khqr import KHQR as _BK
        k = _BK(BAKONG_TOKEN)
        md5_hash = k.generate_md5(qr_str)
    except Exception:
        md5_hash = hashlib.md5(qr_str.encode()).hexdigest()

    dep_id   = f"dep_{uid}_{int(time.time())}"
    start_ts = int(time.time())

    store_deps[dep_id] = {
        "uid": uid_str, "amount": final_amount, "status": "pending",
        "bonus": bonus, "promo": promo_code_name or "",
        "md5": md5_hash, "qr_str": qr_str,
    }
    _save(STORE_DEP_FILE, store_deps)

    cap = (f"{label}\n"
           f"━━━━━━━━━━━━━━━━━━\n"
           f"💰 ចំនួន: <b>${final_amount:.2f}</b>\n"
           f"⏱ ផុតកំណត់: <b>{DEPOSIT_EXPIRE_SEC//60} នាទី</b>\n"
           f"━━━━━━━━━━━━━━━━━━\n"
           f"📱 Scan ជាមួយ Bakong / ABA / Wing")

    if promo_code_name:
        confirm_promo(promo_code_name, uid)

    img_buf = None
    try:
        import qrcode as _qrc
        qr = _qrc.QRCode(box_size=6, border=2)
        qr.add_data(qr_str); qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        img_buf = io.BytesIO(); img.save(img_buf, format="PNG"); img_buf.seek(0)
    except Exception:
        pass

    if img_buf:
        try: bot.send_photo(uid, img_buf, caption=cap, parse_mode="HTML")
        except: bot.send_message(uid, cap + f"\n\n<code>{qr_str}</code>", parse_mode="HTML")
    else:
        bot.send_message(uid, cap + f"\n\n<code>{qr_str}</code>", parse_mode="HTML")
        
    threading.Thread(target=_watch_deposit, args=(uid, uid_str, dep_id, final_amount, start_ts), daemon=True).start()

# ─── BOT HANDLERS ───
@bot.message_handler(commands=["start"])
def cmd_start(message):
    uid = message.chat.id
    waiting.pop(uid, None)
    if uid == ADMIN_ID:
        bot.send_message(uid, "🤖 <b>Panel Admin — Kairozen All-in-One</b>", parse_mode="HTML", reply_markup=admin_kb())
        return
    if str(uid) not in user_lang:
        bot.send_message(uid, "🌐 <b>ជ្រើសរើសភាសា / Select Language</b>", parse_mode="HTML", reply_markup=lang_select_kb())
        return
    bot.send_message(uid, t(uid, "welcome", bal(uid)), parse_mode="HTML", reply_markup=main_kb(uid))

@bot.callback_query_handler(func=lambda c: c.data.startswith("setlang:"))
def cb_setlang(call):
    uid  = call.message.chat.id
    lang = call.data.split(":")[1]
    user_lang[str(uid)] = lang
    _save(LANG_FILE, user_lang)
    bot.answer_callback_query(call.id, t(uid, "lang_set"))
    try: bot.delete_message(uid, call.message.message_id)
    except: pass
    bot.send_message(uid, t(uid, "welcome", bal(uid)), parse_mode="HTML", reply_markup=main_kb(uid))

@bot.callback_query_handler(func=lambda c: c.data.startswith("dep:"))
def cb_dep(call):
    uid = call.message.chat.id
    val = call.data[4:]
    bot.answer_callback_query(call.id)
    if val == "custom":
        waiting[uid] = "dep_custom"
        bot.send_message(uid, "✏️ <b>ផ្ញើចំនួន $ ដែលចង់ deposit:</b>", parse_mode="HTML", reply_markup=cancel_kb())
        return
    _send_deposit_qr(uid, float(val))

@bot.message_handler(func=lambda m: True)
def handle(message):
    uid     = message.chat.id
    text    = message.text.strip() if message.text else ""
    step    = waiting.get(uid)

    if text in ("✕ Cancel", "❌ Cancel"):
        waiting.pop(uid, None)
        bot.send_message(uid, "🏠 Menu", reply_markup=main_kb(uid) if uid != ADMIN_ID else admin_kb())
        return

    if step == "dep_custom":
        try:
            amt = float(text.replace("$",""))
            if amt < 0.5: raise ValueError
            waiting.pop(uid, None)
            _send_deposit_qr(uid, amt)
        except:
            bot.send_message(uid, "❌ ចំនួនខុស! ឧ: <code>5.00</code>", parse_mode="HTML")
        return

    if text in ("🛍️ Shop", "🛍️ ហាងឌីជីថល"):
        bot.send_message(uid, "🛍️ <b>ហាងឌីជីថល</b>", parse_mode="HTML", reply_markup=products_kb())
        return

    if text in ("💳 ដាក់ប្រាក់", "💰 ដាក់ប្រាក់", "💳 Top Up"):
        bot.send_message(uid, f"💸 <b>ដាក់លុយ</b>\n💳 Balance: <b>${bal(uid):.2f}</b>", parse_mode="HTML", reply_markup=deposit_amt_kb(uid))
        return

    if text in ("👜 កាបូបលុយ", "👜 Wallet"):
        bot.send_message(uid, f"👜 <b>កាបូបលុយ</b>\n💳 Balance: <b>${bal(uid):.2f}</b>", parse_mode="HTML", reply_markup=main_kb(uid))
        return

    if uid == ADMIN_ID:
        bot.send_message(uid, "👇 ជ្រើស Menu ខាងក្រោម:", reply_markup=admin_kb())
        return

    bot.send_message(uid, t(uid, "fallback"), reply_markup=main_kb(uid))

if __name__ == "__main__":
    logger.info(f"{CLR_GREEN}🚀 Kairozen All-in-One Bot v4 กำลังเริ่ม...{CLR_RESET}")
    # បើក Flask Server ក្នុង Background Thread ដើម្បីដំណើរការរត់នៅលើ Render Web Service មិនឱ្យរអាក់រអួល
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # ចាប់ផ្ដើម Telegram Bot Polling
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            logger.error(f"{CLR_RED}Polling error: {e}{CLR_RESET}")
            time.sleep(5)
