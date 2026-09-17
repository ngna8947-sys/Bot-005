import io
import json
import logging
import os
import subprocess
import sys
import threading
import time
from flask import Flask, jsonify
import telebot
from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

def _ensure_deps():
    pkgs = {"PIL": "pillow", "qrcode": "qrcode", "requests": "requests"}
    for mod, pkg in pkgs.items():
        try:
            __import__(mod)
        except ImportError:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    pkg,
                    "--break-system-packages",
                    "-q",
                ],
                check=False,
            )

_ensure_deps()

from PIL import Image, ImageDraw, ImageFont
import qrcode
import requests

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════
BOT_TOKEN = "8914728102:AAFCUOmvtYKp3LLoBlg4H4Fbz5PE8joN2zU"
ADMIN_ID = 5915683588

BAKONG_TOKEN = "rbkMVUSQPooaey51jm1cD5ECnzmHyeNX7fBX4Afc16GU8k"
BANK_ACCOUNT = "samnang_mon@bkrt"
MERCHANT_NAME = "KhmerSMM"
MERCHANT_CITY = "Phnom Penh"
DEPOSIT_EXPIRE_SEC = 300
POLL_INTERVAL = 5

WALLETS_FILE = "smm_wallets.json"
USERS_FILE = "smm_users.json"
ORDERS_FILE = "smm_orders.json"
SERVICES_FILE = "smm_services.json"
GAMES_FILE = "smm_games.json"
ACCOUNTS_FILE = "smm_accounts.json"
STORE_DEP_FILE = "smm_store_deposits.json"
API_CONFIG_FILE = "smm_api_config.json"
DISCOUNTS_FILE = "smm_discounts.json"

DEFAULT_KHMER_SMM = {
    # ─── FACEBOOK ───
    "fb_like_kh": {"cat": "Facebook", "name": "👍 FB Likes ខ្មែរ Real", "rate": 1.50, "min": 50, "max": 20000, "api_service_id": 101},
    "fb_like_mix": {"cat": "Facebook", "name": "👍 FB Likes Mix Global", "rate": 0.80, "min": 100, "max": 100000, "api_service_id": 102},
    "fb_react_love": {"cat": "Facebook", "name": "❤️ FB React Love", "rate": 1.20, "min": 50, "max": 20000, "api_service_id": 103},
    "fb_react_haha": {"cat": "Facebook", "name": "😆 FB React Haha", "rate": 1.20, "min": 50, "max": 20000, "api_service_id": 104},
    "fb_react_care": {"cat": "Facebook", "name": "🥰 FB React Care", "rate": 1.20, "min": 50, "max": 20000, "api_service_id": 105},
    "fb_page_fol": {"cat": "Facebook", "name": "👥 FB Page Followers", "rate": 2.20, "min": 100, "max": 50000, "api_service_id": 106},
    "fb_prof_fol": {"cat": "Facebook", "name": "👤 FB Profile Followers", "rate": 1.90, "min": 100, "max": 50000, "api_service_id": 107},
    "fb_views_video": {"cat": "Facebook", "name": "👁 FB Video Views", "rate": 0.25, "min": 500, "max": 100000, "api_service_id": 108},
    "fb_reel_view": {"cat": "Facebook", "name": "🎬 FB Reels Views", "rate": 0.30, "min": 500, "max": 200000, "api_service_id": 110},
    "fb_share": {"cat": "Facebook", "name": "🔄 FB Post Shares", "rate": 2.50, "min": 50, "max": 5000, "api_service_id": 111},

    # ─── TIKTOK ───
    "tt_view": {"cat": "TikTok", "name": "👁 TikTok Views (លឿន)", "rate": 0.15, "min": 1000, "max": 1000000, "api_service_id": 201},
    "tt_like": {"cat": "TikTok", "name": "❤️ TikTok Likes (HQ)", "rate": 1.20, "min": 100, "max": 50000, "api_service_id": 202},
    "tt_follow": {"cat": "TikTok", "name": "👥 TikTok Followers (មិនស្រក)", "rate": 2.80, "min": 100, "max": 20000, "api_service_id": 203},
    "tt_share": {"cat": "TikTok", "name": "🔁 TikTok Shares/Repost", "rate": 0.50, "min": 100, "max": 50000, "api_service_id": 204},

    # ─── TELEGRAM ───
    "tg_member": {"cat": "Telegram", "name": "✈️ Telegram Members", "rate": 1.80, "min": 100, "max": 50000, "api_service_id": 301},
    "tg_post_view": {"cat": "Telegram", "name": "👁 TG Post Views", "rate": 0.10, "min": 100, "max": 100000, "api_service_id": 302},
    "tg_react": {"cat": "Telegram", "name": "🔥 TG Reactions (Fire)", "rate": 0.60, "min": 50, "max": 20000, "api_service_id": 303},

    # ─── YOUTUBE ───
    "yt_view": {"cat": "YouTube", "name": "👁 YouTube Views", "rate": 1.80, "min": 500, "max": 50000, "api_service_id": 401},
    "yt_sub": {"cat": "YouTube", "name": "🔴 YouTube Subscribers", "rate": 18.00, "min": 50, "max": 2000, "api_service_id": 402},

    # ─── INSTAGRAM ───
    "ig_follow": {"cat": "Instagram", "name": "📸 IG Followers (HQ)", "rate": 1.60, "min": 100, "max": 30000, "api_service_id": 501},
    "ig_like": {"cat": "Instagram", "name": "❤️ IG Post Likes", "rate": 0.70, "min": 100, "max": 30000, "api_service_id": 502}
}

def _load(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if data else default
    except:
        return default

def _save(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Save {path}: {e}")

wallets = _load(WALLETS_FILE, {})
users_db = _load(USERS_FILE, {})
orders_db = _load(ORDERS_FILE, {})
services_db = _load(SERVICES_FILE, DEFAULT_KHMER_SMM)
games_db = _load(GAMES_FILE, {})
accounts_db = _load(ACCOUNTS_FILE, {})
store_deps = _load(STORE_DEP_FILE, {})
api_cfg = _load(API_CONFIG_FILE, {"api_url": "", "api_key": ""})
discounts = _load(DISCOUNTS_FILE, {"smm": 0, "game": 0, "account": 0})
waiting = {}

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

def bal(uid):
    return float(wallets.get(str(uid), 0.0))

def add_bal(uid, amt):
    wallets[str(uid)] = round(bal(uid) + amt, 2)
    _save(WALLETS_FILE, wallets)

def ded_bal(uid, amt):
    wallets[str(uid)] = max(0.0, round(bal(uid) - amt, 2))
    _save(WALLETS_FILE, wallets)

def get_disc_price(orig_price, disc_percent):
    if disc_percent <= 0:
        return orig_price
    return max(0.01, round(orig_price * (1 - disc_percent / 100.0), 2))

def smm_api_order(service_id, link, quantity):
    url, key = api_cfg.get("api_url"), api_cfg.get("api_key")
    if not url or not key:
        return {"error": "Admin មិនទាន់កំណត់ API"}
    payload = {"key": key, "action": "add", "service": service_id, "link": link, "quantity": quantity}
    try:
        return requests.post(url, data=payload, timeout=25).json()
    except Exception as e:
        return {"error": str(e)}

def smm_api_balance():
    url, key = api_cfg.get("api_url"), api_cfg.get("api_key")
    if not url or not key:
        return "❌ មិនទាន់កំណត់ API"
    try:
        resp = requests.post(url, data={"key": key, "action": "balance"}, timeout=15).json()
        if "balance" in resp:
            return f"${float(resp['balance']):.2f} {resp.get('currency', 'USD')}"
        return f"Error: {resp.get('error', 'Unknown')}"
    except Exception as e:
        return f"Error: {e}"

# ═══════════════════════════════════════════════════════════
#  DRAW STYLED BAKONG KHQR TEMPLATE (រចនាបថ Bakong ពណ៌ក្រហម)
# ═══════════════════════════════════════════════════════════
def _generate_styled_khqr_image(qr_str, amount, merchant_name="KhmerSMM"):
    card_w, card_h = 750, 1050
    card = Image.new("RGBA", (card_w, card_h), "#FFFFFF")
    draw = ImageDraw.Draw(card)

    # ឆ្នូតខាងលើពណ៌ក្រហម Bakong
    draw.rectangle([(0, 0), (card_w, 28)], fill="#c8102e")

    font_header, font_slogan, font_name, font_khqr_small, font_amt, font_dollar = None, None, None, None, None, None
    for f_bold in ["arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf"]:
        try:
            font_header = ImageFont.truetype(f_bold, 54)
            font_name = ImageFont.truetype(f_bold, 42)
            font_khqr_small = ImageFont.truetype(f_bold, 28)
            font_amt = ImageFont.truetype(f_bold, 30)
            font_dollar = ImageFont.truetype(f_bold, 32)
            break
        except:
            pass

    for f_reg in ["arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans.ttf"]:
        try:
            font_slogan = ImageFont.truetype(f_reg, 24)
            break
        except:
            pass

    if not font_header:
        font_header = font_name = font_slogan = font_khqr_small = font_amt = font_dollar = ImageFont.load_default()

    # បង្ហាញពាក្យ BAKONG PAY (ពណ៌ក្រហមស្អាត)
    draw.text((card_w // 2, 100), "BAKONG PAY", fill="#c8102e", font=font_header, anchor="mm")
    draw.text((card_w // 2, 170), "Scan. Pay. Done.", fill="#111111", font=font_slogan, anchor="mm")

    # ប្រអប់ដាក់ QR Code
    qr_box_size = 440
    box_x1 = (card_w - qr_box_size) // 2
    box_y1 = 225
    box_x2, box_y2 = box_x1 + qr_box_size, box_y1 + qr_box_size
    draw.rounded_rectangle([(box_x1, box_y1), (box_x2, box_y2)], radius=36, outline="#d6d9dc", width=5)

    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=0)
    qr.add_data(qr_str)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#000000", back_color="#FFFFFF").convert("RGBA")

    inner_qr_size = 360
    qr_img = qr_img.resize((inner_qr_size, inner_qr_size), Image.Resampling.LANCZOS)
    qr_px = (card_w - inner_qr_size) // 2
    qr_py = box_y1 + (qr_box_size - inner_qr_size) // 2
    card.paste(qr_img, (qr_px, qr_py))

    center_x = card_w // 2
    center_y = qr_py + (inner_qr_size // 2)
    draw.ellipse([(center_x - 32, center_y - 32), (center_x + 32, center_y + 32)], fill="#FFFFFF")
    draw.ellipse([(center_x - 27, center_y - 27), (center_x + 27, center_y + 27)], fill="#c8102e")
    draw.text((center_x, center_y), "$", fill="#FFFFFF", font=font_dollar, anchor="mm")

    # ឈ្មោះគណនី KhmerSMM
    draw.text((card_w // 2, box_y2 + 50), "KhmerSMM", fill="#1a2530", font=font_name, anchor="mm")
    draw.text((card_w // 2, box_y2 + 105), f"AMOUNT: ${amount:.2f} USD", fill="#c8102e", font=font_amt, anchor="mm")

    # ក្បាច់ curve ផ្នែកខាងក្រោម
    bg_curve = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(bg_curve)
    bg_draw.rounded_rectangle([(card_w - 240, card_h - 180), (card_w + 120, card_h + 120)], radius=90, fill="#c8102e")
    card = Image.alpha_composite(card, bg_curve)
    draw = ImageDraw.Draw(card)

    draw.text((55, card_h - 100), "Member of", fill="#5a6872", font=ImageFont.load_default())
    draw.text((55, card_h - 78), "KHQR", fill="#c8102e", font=font_khqr_small)

    buf = io.BytesIO()
    card.convert("RGB").save(buf, format="PNG", quality=95)
    buf.seek(0)
    return buf

def _generate_khqr(uid, amount, note=""):
    try:
        from bakong_khqr import KHQR
        return KHQR(BAKONG_TOKEN).create_qr(
            bank_account=BANK_ACCOUNT,
            merchant_name="KhmerSMM",
            merchant_city=MERCHANT_CITY,
            amount=round(float(amount), 2),
            currency="USD",
            bill_number=(note or f"uid{uid}")[:25],
            static=False,
        ) or ""
    except Exception as e:
        logger.error(f"[_generate_khqr] Error: {e}")
        return ""

def _check_bakong(md5, amount, start_ts):
    try:
        from bakong_khqr import KHQR as _BK
        return _BK(BAKONG_TOKEN).check_payment(str(md5)) == "PAID"
    except Exception:
        return False

def _build_caption(amount, remaining_sec):
    mins, secs = max(0, remaining_sec // 60), max(0, remaining_sec % 60)
    return (
        f"💳 <b>ដាក់ប្រាក់ចូលគណនី (Top Up)</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 ឈ្មោះគណនី: <b>KhmerSMM</b>\n"
        f"💰 ចំនួនទឹកប្រាក់: <b>${amount:.2f}</b> (បានកំណត់ស្វ័យប្រវត្តិក្នុង QR)\n"
        f"⏱ ផុតកំណត់ក្នុងរយ: <b>{mins:02d}:{secs:02d} នាទី</b> ⏳\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📱 Scan ជាមួយ Bakong, ABA, Wing ឬធនាគារនានា"
    )

def _watch_deposit_and_countdown(uid, uid_str, dep_id, amount, msg_id, start_ts):
    deadline = start_ts + DEPOSIT_EXPIRE_SEC
    last_edit = 0

    while time.time() < deadline:
        now = time.time()
        remaining = int(deadline - now)
        dep = store_deps.get(dep_id)
        if not dep or dep.get("status") != "pending":
            return

        if _check_bakong(dep.get("md5", ""), amount, start_ts):
            add_bal(uid, round(amount, 2))
            dep["status"] = "confirmed"
            _save(STORE_DEP_FILE, store_deps)
            try:
                bot.edit_message_caption(
                    chat_id=uid,
                    message_id=msg_id,
                    caption=f"✅ <b>ការទូទាត់ទទួលបានជោគជ័យ!</b>\n💰 បញ្ចូល: +${amount:.2f}",
                )
                bot.send_message(
                    uid,
                    f"✅ <b>ដាក់ប្រាក់ជោគជ័យ!</b>\n💰 +${amount:.2f}\n💳 សមតុល្យសរុប: <b>${bal(uid):.2f}</b>",
                    reply_markup=user_kb(uid),
                )
                bot.send_message(
                    ADMIN_ID, f"💰 <b>Auto KHQR</b>\n👤 <code>{uid_str}</code> | +${amount:.2f}"
                )
            except:
                pass
            return

        if now - last_edit >= 10 and msg_id:
            try:
                bot.edit_message_caption(
                    chat_id=uid,
                    message_id=msg_id,
                    caption=_build_caption(amount, remaining),
                )
                last_edit = now
            except:
                pass
        time.sleep(POLL_INTERVAL)

    dep = store_deps.get(dep_id)
    if dep and dep.get("status") == "pending":
        dep["status"] = "expired"
        _save(STORE_DEP_FILE, store_deps)
        try:
            bot.edit_message_caption(
                chat_id=uid,
                message_id=msg_id,
                caption="❌ <b>QR ផុតកំណត់ហើយ!</b> សូមស្នើសុំម្ដងទៀត។",
            )
        except:
            pass

def _send_deposit_qr(uid, amount):
    uid_str = str(uid)
    qr_str = _generate_khqr(uid, amount, f"uid={uid} ${amount}")
    if not qr_str:
        bot.send_message(uid, "⚠️ បរាជ័យក្នុងការបង្កើត QR! សូមទាក់ទង Admin")
        return

    try:
        from bakong_khqr import KHQR as _BK
        md5_hash = _BK(BAKONG_TOKEN).generate_md5(qr_str)
    except Exception:
        import hashlib
        md5_hash = hashlib.md5(qr_str.encode()).hexdigest()

    dep_id = f"dep_{uid}_{int(time.time())}"
    store_deps[dep_id] = {
        "uid": uid_str,
        "amount": amount,
        "status": "pending",
        "md5": md5_hash,
        "qr_str": qr_str,
    }
    _save(STORE_DEP_FILE, store_deps)

    admin_kb_dep = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ បញ្ចូលលុយឱ្យ", callback_data=f"manual_dep:approve:{dep_id}"),
            InlineKeyboardButton("❌ បដិសេធ", callback_data=f"manual_dep:reject:{dep_id}"),
        ]
    ])
    try:
        bot.send_message(
            ADMIN_ID,
            f"📥 <b>ការស្នើដាក់លុយ!</b>\n👤 <code>{uid_str}</code> | 💰 <b>${amount:.2f}</b>",
            reply_markup=admin_kb_dep,
        )
    except:
        pass

    try:
        buf = _generate_styled_khqr_image(qr_str, amount, "KhmerSMM")
        sent = bot.send_photo(uid, buf, caption=_build_caption(amount, DEPOSIT_EXPIRE_SEC))
    except Exception:
        sent = bot.send_message(
            uid, _build_caption(amount, DEPOSIT_EXPIRE_SEC) + f"\n\n<code>{qr_str}</code>"
        )

    msg_id = sent.message_id if sent else None
    threading.Thread(
        target=_watch_deposit_and_countdown,
        args=(uid, uid_str, dep_id, amount, msg_id, int(time.time())),
        daemon=True,
    ).start()

# ═══════════════════════════════════════════════════════════
#  KEYBOARDS
# ═══════════════════════════════════════════════════════════
def user_kb(uid=None):
    s_d = f" 🏷️-{discounts['smm']}%" if discounts.get("smm", 0) > 0 else ""
    g_d = f" 🏷️-{discounts['game']}%" if discounts.get("game", 0) > 0 else ""
    a_d = f" 🏷️-{discounts['account']}%" if discounts.get("account", 0) > 0 else ""

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(f"🚀 សេវាកម្ម SMM{s_d}", f"🎮 បញ្ចូលហ្គេម{g_d}")
    kb.row(f"🛒 ទិញអាខោន{a_d}", "💳 ដាក់ប្រាក់ (Top Up)")
    
    uid_str = str(uid) if uid else ""
    if uid_str and not users_db.get(uid_str, {}).get("phone"):
        kb.row("📱 ចុចភ្ជាប់លេខទូរស័ព្ទ", "👜 កាបូបលុយ")
        kb.row("📦 ប្រវត្តិបញ្ជាទិញ", "💬 ជំនួយ Support")
    else:
        kb.row("👜 កាបូបលុយ", "📦 ប្រវត្តិបញ្ជាទិញ", "💬 ជំនួយ Support")
    return kb

def request_contact_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.row(KeyboardButton("📱 ចុចចែករំលែកលេខទូរស័ព្ទ (Share Contact)", request_contact=True))
    kb.row("✕ Cancel")
    return kb

def admin_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("💸 ដាក់ទឹកប្រាក់ឱ្យភ្ញៀវ", "🏷️ បញ្ចុះតម្លៃ (Discount)")
    kb.row("➕ បន្ថែមសេវា SMM", "🛠 គ្រប់គ្រងសេវា SMM")
    kb.row("➕ បន្ថែមហ្គេម/កញ្ចប់", "🎮 គ្រប់គ្រងហ្គេម")
    kb.row("➕ បង្កើតប្រភេទអាខោន", "📥 បញ្ចូលស្តុកអាខោន")
    kb.row("🛒 គ្រប់គ្រងអាខោន", "📦 បញ្ជី Order ទាំងអស់")
    kb.row("💰 កាបូបលុយសរុប", "👥 អ្នកប្រើប្រាស់")
    kb.row("⚙️ កំណត់ SMM API", "📢 ផ្សព្វផ្សាយ", "🏠 Menu ភ្ញៀវ")
    return kb

def cancel_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("✕ Cancel")
    return kb

def deposit_amt_kb():
    btns = [
        [InlineKeyboardButton("💵 $1.00", callback_data="dep:1"), InlineKeyboardButton("💵 $2.00", callback_data="dep:2"), InlineKeyboardButton("💵 $5.00", callback_data="dep:5")],
        [InlineKeyboardButton("💵 $10.00", callback_data="dep:10"), InlineKeyboardButton("💵 $20.00", callback_data="dep:20"), InlineKeyboardButton("💵 $50.00", callback_data="dep:50")],
        [InlineKeyboardButton("✏️ បញ្ចូលចំនួនទឹកប្រាក់ផ្ទាល់ខ្លួន", callback_data="dep:custom")]
    ]
    return InlineKeyboardMarkup(btns)

def category_smm_kb():
    cats = sorted(list(set([s.get("cat", "ទូទៅ") for s in services_db.values()])))
    if not cats:
        return None
    d_tag = f" 🔥-{discounts['smm']}%" if discounts.get("smm", 0) > 0 else ""
    icons = {"Facebook": "🔵", "TikTok": "🎵", "Telegram": "✈️", "YouTube": "🔴", "Instagram": "📸"}
    btns = []
    row = []
    for c in cats:
        ico = icons.get(c, "📁")
        count = len([s for s in services_db.values() if s.get("cat") == c])
        row.append(InlineKeyboardButton(f"{ico} {c} ({count}){d_tag}", callback_data=f"smm_cat:{c}:0"))
        if len(row) == 2:
            btns.append(row)
            row = []
    if row:
        btns.append(row)
    return InlineKeyboardMarkup(btns)

def smm_by_cat_kb(category, page=0, per_page=5):
    disc = discounts.get("smm", 0)
    items = [(sid, s) for sid, s in services_db.items() if s.get("cat") == category]
    total_pages = max(1, (len(items) + per_page - 1) // per_page)
    start = page * per_page
    end = start + per_page

    btns = []
    for sid, s in items[start:end]:
        orig = s["rate"]
        cur = get_disc_price(orig, disc)
        tag = f"🔥${cur:.2f}" if disc > 0 else f"${orig:.2f}"
        btns.append([InlineKeyboardButton(f"{s['name']} | 🟢 {tag}/1k", callback_data=f"order_smm:{sid}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ ថយក្រោយ", callback_data=f"smm_cat:{category}:{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("បន្ទាប់ ➡️", callback_data=f"smm_cat:{category}:{page+1}"))
    if nav:
        btns.append(nav)

    btns.append([InlineKeyboardButton("🔙 ត្រឡប់ទៅ Category", callback_data="back_to_smm_cats")])
    return InlineKeyboardMarkup(btns)

def games_menu_kb():
    btns = []
    d_tag = f" 🔥-{discounts['game']}%" if discounts.get("game", 0) > 0 else ""
    for gkey, g in games_db.items():
        if g.get("items") and len(g["items"]) > 0:
            btns.append([InlineKeyboardButton(f"🎮 {g['title']}{d_tag}", callback_data=f"game_cat:{gkey}")])
    return InlineKeyboardMarkup(btns) if btns else None

def game_items_kb(game_key):
    disc = discounts.get("game", 0)
    game = ga
