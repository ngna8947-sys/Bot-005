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
    pkgs = {
        "PIL": "pillow",
        "qrcode": "qrcode",
        "requests": "requests",
        "bakong_khqr": "bakong-khqr",
    }
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
    "fb_like_kh": {"cat": "Facebook", "name": "👍 FB Likes ខ្មែរ Real", "rate": 1.50, "min": 50, "max": 20000, "api_service_id": 101},
    "fb_like_mix": {"cat": "Facebook", "name": "👍 FB Likes Mix Global", "rate": 0.80, "min": 100, "max": 100000, "api_service_id": 102},
    "fb_react_love": {"cat": "Facebook", "name": "❤️ FB React Love", "rate": 1.20, "min": 50, "max": 20000, "api_service_id": 103},
    "fb_react_haha": {"cat": "Facebook", "name": "😆 FB React Haha", "rate": 1.20, "min": 50, "max": 20000, "api_service_id": 104},
    "fb_page_fol": {"cat": "Facebook", "name": "👥 FB Page Followers", "rate": 2.20, "min": 100, "max": 50000, "api_service_id": 106},
    "fb_prof_fol": {"cat": "Facebook", "name": "👤 FB Profile Followers", "rate": 1.90, "min": 100, "max": 50000, "api_service_id": 107},
    "fb_views_video": {"cat": "Facebook", "name": "👁 FB Video Views", "rate": 0.25, "min": 500, "max": 100000, "api_service_id": 108},
    "fb_reel_view": {"cat": "Facebook", "name": "🎬 FB Reels Views", "rate": 0.30, "min": 500, "max": 200000, "api_service_id": 110},
    "fb_share": {"cat": "Facebook", "name": "🔄 FB Post Shares", "rate": 2.50, "min": 50, "max": 5000, "api_service_id": 111},
    "tt_view": {"cat": "TikTok", "name": "👁 TikTok Views (លឿន)", "rate": 0.15, "min": 1000, "max": 1000000, "api_service_id": 201},
    "tt_like": {"cat": "TikTok", "name": "❤️ TikTok Likes (HQ)", "rate": 1.20, "min": 100, "max": 50000, "api_service_id": 202},
    "tt_follow": {"cat": "TikTok", "name": "👥 TikTok Followers (មិនស្រក)", "rate": 2.80, "min": 100, "max": 20000, "api_service_id": 203},
    "tg_member": {"cat": "Telegram", "name": "✈️ Telegram Members", "rate": 1.80, "min": 100, "max": 50000, "api_service_id": 301},
    "tg_post_view": {"cat": "Telegram", "name": "👁 TG Post Views", "rate": 0.10, "min": 100, "max": 100000, "api_service_id": 302},
    "yt_view": {"cat": "YouTube", "name": "👁 YouTube Views", "rate": 1.80, "min": 500, "max": 50000, "api_service_id": 401},
    "ig_follow": {"cat": "Instagram", "name": "📸 IG Followers (HQ)", "rate": 1.60, "min": 100, "max": 30000, "api_service_id": 501}
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
#  STATIC KHQR GENERATOR (ស្ដង់ដារដែលធនាគារទទួលស្គាល់ ១០០%)
# ═══════════════════════════════════════════════════════════
def _crc16_khqr(data: str) -> str:
    crc = 0xFFFF
    for ch in data:
        crc ^= (ord(ch) << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return f"{crc:04X}"

def _build_static_khqr(account_id: str) -> str:
    def tag(tid: int, val: str) -> str:
        val_str = str(val)
        return f"{tid:02d}{len(val_str.encode('utf-8')):02d}{val_str}"

    sub29 = tag(0, "kh.gov.nbc.bakong") + tag(1, account_id)
    tag29 = tag(29, sub29)

    payload = (
        tag(0, "01") +
        tag(1, "11") +                   # 11 = Static QR ស្តង់ដារ (ដំណើរការគ្រប់ធនាគារ)
        tag29 +
        tag(52, "5999") +
        tag(53, "840") +
        tag(58, "KH") +
        tag(59, MERCHANT_NAME) +
        tag(60, MERCHANT_CITY) +
        "6304"
    )
    return payload + _crc16_khqr(payload)

def _generate_khqr(uid, amount, note=""):
    try:
        from bakong_khqr import KHQR
        qr = KHQR(BAKONG_TOKEN).create_qr(
            bank_account=BANK_ACCOUNT,
            merchant_name=MERCHANT_NAME,
            merchant_city=MERCHANT_CITY,
            amount=round(float(amount), 2),
            currency="USD",
            bill_number=(note or f"uid{uid}")[:25],
            static=True,                  # ប្រើ Static QR ដើម្បីកុំឱ្យធនាគារបដិសេធ
        )
        if qr and qr.startswith("000201"):
            return qr
    except Exception:
        pass
    
    return _build_static_khqr(BANK_ACCOUNT)

def _check_bakong(md5, amount, start_ts):
    # 1. ឆែកតាម Library
    try:
        from bakong_khqr import KHQR as _BK
        if _BK(BAKONG_TOKEN).check_payment(str(md5)) == "PAID":
            return True
    except Exception:
        pass

    # 2. ឆែកផ្ទាល់តាម Bakong API Endpoint
    try:
        url = "https://api-bakong.nbc.gov.kh/v1/check_transaction_by_md5"
        headers = {
            "Authorization": f"Bearer {BAKONG_TOKEN}",
            "Content-Type": "application/json"
        }
        res = requests.post(url, json={"md5": str(md5)}, headers=headers, timeout=8).json()
        if res.get("responseCode") == 0 and res.get("data", {}).get("status") == "SUCCESS":
            return True
    except Exception:
        pass

    return False

# ═══════════════════════════════════════════════════════════
#  DRAW STYLED ABA PAY TEMPLATE
# ═══════════════════════════════════════════════════════════
def _generate_styled_khqr_image(qr_str, amount, merchant_name="KhmerSMM"):
    card_w, card_h = 750, 1150
    card = Image.new("RGBA", (card_w, card_h), "#FFFFFF")
    draw = ImageDraw.Draw(card)

    draw.rectangle([(0, 0), (card_w, 35)], fill="#00465c")
    draw.polygon([(0, 35), (45, 35), (0, 75)], fill="#00465c")

    font_aba, font_pay, font_slogan, font_name, font_khqr_small, font_amt, font_dollar = (
        None, None, None, None, None, None, None
    )
    for f_bold in ["arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf"]:
        try:
            font_aba = ImageFont.truetype(f_bold, 54)
            font_pay = ImageFont.truetype(f_bold, 54)
            font_name = ImageFont.truetype(f_bold, 40)
            font_khqr_small = ImageFont.truetype(f_bold, 28)
            font_amt = ImageFont.truetype(f_bold, 32)
            font_dollar = ImageFont.truetype(f_bold, 30)
            break
        except: pass

    for f_reg in ["arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans.ttf"]:
        try:
            font_slogan = ImageFont.truetype(f_reg, 24)
            break
        except: pass

    if not font_aba:
        font_aba = font_pay = font_name = font_slogan = font_khqr_small = font_amt = font_dollar = ImageFont.load_default()

    aba_txt, pay_txt = "ABA'", " PAY"
    b_aba = font_aba.getbbox(aba_txt)
    b_pay = font_pay.getbbox(pay_txt)
    w_aba = b_aba[2] - b_aba[0]
    w_pay = b_pay[2] - b_pay[0]
    start_x = (card_w - (w_aba + w_pay)) // 2

    draw.text((start_x, 115), aba_txt, fill="#00465c", font=font_aba)
    draw.text((start_x + w_aba, 115), pay_txt, fill="#00a3b8", font=font_pay)
    draw.text((card_w // 2, 190), "Scan. Pay. Done.", fill="#111111", font=font_slogan, anchor="mm")

    qr_inner_size = 380
    qr_cx, qr_cy = card_w // 2, 450
    box_x1 = qr_cx - (qr_inner_size // 2) - 25
    box_y1 = qr_cy - (qr_inner_size // 2) - 25
    box_x2 = qr_cx + (qr_inner_size // 2) + 25
    box_y2 = qr_cy + (qr_inner_size // 2) + 25

    arm = 50
    bracket_color = "#c2c7cc"
    bw = 6
    draw.line([(box_x1, box_y1 + arm), (box_x1, box_y1 + 18)], fill=bracket_color, width=bw)
    draw.arc([(box_x1, box_y1), (box_x1 + 36, box_y1 + 36)], 180, 270, fill=bracket_color, width=bw)
    draw.line([(box_x1 + 18, box_y1), (box_x1 + arm, box_y1)], fill=bracket_color, width=bw)

    draw.line([(box_x2 - arm, box_y1), (box_x2 - 18, box_y1)], fill=bracket_color, width=bw)
    draw.arc([(box_x2 - 36, box_y1), (box_x2, box_y1 + 36)], 270, 360, fill=bracket_color, width=bw)
    draw.line([(box_x2, box_y1 + 18), (box_x2, box_y1 + arm)], fill=bracket_color, width=bw)

    draw.line([(box_x1, box_y2 - arm), (box_x1, box_y2 - 18)], fill=bracket_color, width=bw)
    draw.arc([(box_x1, box_y2 - 36), (box_x1 + 36, box_y2)], 90, 180, fill=bracket_color, width=bw)
    draw.line([(box_x1 + 18, box_y2), (box_x1 + arm, box_y2)], fill=bracket_color, width=bw)

    draw.line([(box_x2 - arm, box_y2), (box_x2 - 18, box_y2)], fill=bracket_color, width=bw)
    draw.arc([(box_x2 - 36, box_y2 - 36), (box_x2, box_y2)], 0, 90, fill=bracket_color, width=bw)
    draw.line([(box_x2, box_y2 - arm), (box_x2, box_y2 - 18)], fill=bracket_color, width=bw)

    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=0)
    qr.add_data(qr_str)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#000000", back_color="#FFFFFF").convert("RGBA")
    qr_img = qr_img.resize((qr_inner_size, qr_inner_size), Image.Resampling.LANCZOS)
    card.paste(qr_img, (qr_cx - (qr_inner_size // 2), qr_cy - (qr_inner_size // 2)))

    draw.ellipse([(qr_cx - 32, qr_cy - 32), (qr_cx + 32, qr_cy + 32)], fill="#FFFFFF")
    draw.ellipse([(qr_cx - 27, qr_cy - 27), (qr_cx + 27, qr_cy + 27)], fill="#000000")
    draw.text((qr_cx, qr_cy), "$", fill="#FFFFFF", font=font_dollar, anchor="mm")

    draw.text((card_w // 2, box_y2 + 65), merchant_name, fill="#1a2530", font=font_name, anchor="mm")
    draw.text((card_w // 2, box_y2 + 125), f"AMOUNT: ${amount:.2f} USD", fill="#00465c", font=font_amt, anchor="mm")

    overlay = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    ov_draw.rounded_rectangle([(card_w - 250, card_h - 200), (card_w + 120, card_h + 120)], radius=95, fill="#d61b36")
    ov_draw.rounded_rectangle([(card_w - 170, card_h - 120), (card_w + 120, card_h + 120)], radius=60, fill="#FFFFFF")
    ov_draw.rectangle([(0, card_h - 30), (card_w, card_h)], fill="#00465c")
    card = Image.alpha_composite(card, overlay)
    draw = ImageDraw.Draw(card)

    draw.text((55, card_h - 130), "Member of", fill="#5a6872", font=ImageFont.load_default())
    draw.text((55, card_h - 105), "KHQR", fill="#c8102e", font=font_khqr_small)

    buf = io.BytesIO()
    card.convert("RGB").save(buf, format="PNG", quality=95)
    buf.seek(0)
    return buf

def _build_caption(amount, remaining_sec):
    mins, secs = max(0, remaining_sec // 60), max(0, remaining_sec % 60)
    return (
        f"💳 <b>ដាក់ប្រាក់ចូលគណនី (Top Up)</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 ឈ្មោះគណនី: <b>{MERCHANT_NAME}</b>\n"
        f"💰 ចំនួនទឹកប្រាក់ត្រូវផ្ញើ: <b>${amount:.2f} USD</b>\n"
        f"⏱ ផុតកំណត់ក្នុងរយ: <b>{mins:02d}:{secs:02d} នាទី</b> ⏳\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📱 Scan ជាមួយ ABA, Bakong ឬ Wing (សូមវាយចំនួន <b>${amount:.2f}</b> ពេលបាញ់)"
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
        buf = _generate_styled_khqr_image(qr_str, amount, MERCHANT_NAME)
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
        [InlineKeyboardButton("✏️ បញ្ចូលចំនួនទឹកប្រាក់ផ្សេងទៀត", callback_data="dep:custom")]
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
    game = games_db.get(game_key)
    btns = []
    if game and game.get("items"):
        for idx, it in enumerate(game["items"]):
            orig = it["price"]
            cur = get_disc_price(orig, disc)
            tag = f"🔥${cur:.2f}" if disc > 0 else f"${orig:.2f}"
            btns.append([InlineKeyboardButton(f"{it['name']} ➔ 💎 {tag}", callback_data=f"buy_game:{game_key}:{idx}")])
    btns.append([InlineKeyboardButton("🔙 ត្រឡប់ទៅបញ្ជីហ្គេម", callback_data="back_to_games")])
    return InlineKeyboardMarkup(btns)

def accounts_menu_kb():
    disc = discounts.get("account", 0)
    btns = []
    for aid, a in accounts_db.items():
        stock = len(a.get("stock", []))
        if stock > 0:
            orig = a["price"]
            cur = get_disc_price(orig, disc)
            tag = f"🔥${cur:.2f}" if disc > 0 else f"${orig:.2f}"
            btns.append([InlineKeyboardButton(f"📦 {a['title']} | {tag} [សល់: {stock}]", callback_data=f"view_acc:{aid}")])
    return InlineKeyboardMarkup(btns) if btns else None

# ═══════════════════════════════════════════════════════════
#  START
# ═══════════════════════════════════════════════════════════
@bot.message_handler(commands=["start"])
def cmd_start(message):
    uid = message.chat.id
    waiting.pop(uid, None)
    users_db.setdefault(str(uid), {})
    users_db[str(uid)]["name"] = message.from_user.first_name or ""
    users_db[str(uid)]["username"] = message.from_user.username or ""
    users_db[str(uid)]["last"] = int(time.time())
    _save(USERS_FILE, users_db)
    wallets.setdefault(str(uid), 0.0)

    disc_info = ""
    if any(discounts.values()):
        disc_info = "\n🎉 <b>ប្រូម៉ូសិនបញ្ចុះតម្លៃពិសេស (Hot Promotions)៖</b>\n"
        if discounts.get("smm", 0) > 0:
            disc_info += f"• សេវាកម្ម SMM បញ្ចុះ: <b>{discounts['smm']}%</b> 🔥\n"
        if discounts.get("game", 0) > 0:
            disc_info += f"• Top Up Game បញ្ចុះ: <b>{discounts['game']}%</b> 🔥\n"
        if discounts.get("account", 0) > 0:
            disc_info += f"• ទិញអាខោន បញ្ចុះ: <b>{discounts['account']}%</b> 🔥\n"

    welcome_text = (
        f"╭━━━━━━━━━━━━━━━━━━━╮\n"
        f"  👋 សួស្ដី <b>{message.from_user.first_name}</b>!\n"
        f"  🇰🇭 ស្វាគមន៍មកកាន់ <b>KhmerSMM Bot</b>\n"
        f"╰━━━━━━━━━━━━━━━━━━━╯\n"
        f"🚀 <b>សេវាកម្ម SMM:</b> Likes, Followers, Views, Shares\n"
        f"🎮 <b>Top Up Game:</b> MLBB, Free Fire, PUBG\n"
        f"🛒 <b>Account Store:</b> កាត់លុយស្វ័យប្រវត្តិតាម Bot\n"
        f"{disc_info}"
        f"─────────────────────\n"
        f"💰 សមតុល្យគណនី: <b>${bal(uid):.2f} USD</b> 💳\n"
        f"👉 <i>សូមចុច Menu ខាងក្រោមដើម្បីដំណើរការ៖</i>"
    )
    bot.send_message(
        uid, welcome_text, reply_markup=admin_kb() if uid == ADMIN_ID else user_kb(uid)
    )

@bot.message_handler(content_types=["contact"])
def handle_contact(message):
    uid = message.chat.id
    if message.contact:
        phone = message.contact.phone_number
        if not phone.startswith("+"):
            phone = "+" + phone
        users_db.setdefault(str(uid), {})
        users_db[str(uid)]["phone"] = phone
        _save(USERS_FILE, users_db)
        bot.send_message(
            uid,
            f"✅ <b>បានភ្ជាប់លេខទូរស័ព្ទជោគជ័យ!</b>\n📞 លេខរបស់អ្នក: <code>{phone}</code>",
            reply_markup=admin_kb() if uid == ADMIN_ID else user_kb(uid),
        )

# ═══════════════════════════════════════════════════════════
#  CALLBACK QUERIES
# ═══════════════════════════════════════════════════════════
@bot.callback_query_handler(func=lambda c: True)
def handle_callbacks(call):
    uid = call.message.chat.id
    data = call.data

    if data.startswith("dep:"):
        val = data[4:]
        bot.answer_callback_query(call.id)
        if val == "custom":
            waiting[uid] = "dep_custom"
            bot.send_message(uid, "✏️ <b>សូមផ្ញើចំនួនទឹកប្រាក់ ($) ដែលចង់ដាក់:</b>\n<i>ឧទាហរណ៍៖ 3.50 ឬ 15</i>", reply_markup=cancel_kb())
            return
        _send_deposit_qr(uid, float(val))

    elif data.startswith("smm_cat:"):
        parts = data.split(":")
        cat = parts[1]
        page = int(parts[2]) if len(parts) > 2 else 0
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            f"📌 <b>កាតាឡុកសេវាកម្ម: {cat} (ទំព័រ {page+1})</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👇 សូមជ្រើសរើសសេវាកម្មដែលអ្នកត្រូវការ៖",
            chat_id=uid,
            message_id=call.message.message_id,
            reply_markup=smm_by_cat_kb(cat, page=page),
        )

    elif data == "back_to_smm_cats":
        bot.answer_callback_query(call.id)
        kb = category_smm_kb()
        if not kb:
            bot.edit_message_text("❌ មិនទាន់មានសេវាកម្ម SMM ដាក់លក់នៅឡើយទេ!", chat_id=uid, message_id=call.message.message_id)
        else:
            bot.edit_message_text(
                "⚡️ <b>សូមជ្រើសរើសប្រភេទបណ្តាញសង្គម៖</b>",
                chat_id=uid,
                message_id=call.message.message_id,
                reply_markup=kb,
            )

    elif data.startswith("order_smm:"):
        sid = data.split(":")[1]
        srv = services_db.get(sid)
        if not srv:
            bot.answer_callback_query(call.id, "❌ មិនមានសេវានេះទេ!")
            return
        bot.answer_callback_query(call.id)
        waiting[uid] = {"step": "smm_link", "sid": sid}
        bot.send_message(
            uid,
            f"╭─────────────────────╮\n"
            f"  📌 <b>សេវាកម្ម:</b> {srv['name']}\n"
            f"╰─────────────────────╯\n\n"
            f"🔗 <b>សូមផ្ញើតំណភ្ជាប់ (Link) ផុស/គណនី/ឆានែល:</b>\n"
            f"<i>ឧទាហរណ៍: https://www.facebook.com/...</i>",
            reply_markup=cancel_kb(),
        )

    elif data.startswith("game_cat:"):
        gkey = data.split(":")[1]
        game = games_db.get(gkey)
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            f"🎮 <b>ជ្រើសរើសកញ្ចប់ {game['title']}៖</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👇 សូមជ្រើសរើសចំនួនពេជ្រ ឬកញ្ចប់ដែលអ្នកចង់បញ្ចូល៖",
            chat_id=uid,
            message_id=call.message.message_id,
            reply_markup=game_items_kb(gkey),
        )

    elif data == "back_to_games":
        bot.answer_callback_query(call.id)
        kb = games_menu_kb()
        if not kb:
            bot.edit_message_text("❌ មិនទាន់មានហ្គេមដាក់លក់នៅឡើយទេ!", chat_id=uid, message_id=call.message.message_id)
        else:
            bot.edit_message_text("🎮 <b>សូមជ្រើសរើសហ្គេមដែលអ្នកចង់ Top Up៖</b>", chat_id=uid, message_id=call.message.message_id, reply_markup=kb)

    elif data.startswith("buy_game:"):
        _, gkey, idx = data.split(":")
        game = games_db.get(gkey)
        item = game["items"][int(idx)]
        orig_price = item["price"]
        disc = discounts.get("game", 0)
        final_price = get_disc_price(orig_price, disc)

        if bal(uid) < final_price:
            bot.answer_callback_query(call.id, "❌ សមតុល្យមិនគ្រប់គ្រាន់!", show_alert=True)
            bot.send_message(
                uid,
                f"❌ <b>សមតុល្យមិនគ្រប់គ្រាន់!</b>\n💰 តម្លៃ: <b>${final_price:.2f}</b>\n💳 អ្នកមាន: <b>${bal(uid):.2f}</b>",
                reply_markup=deposit_amt_kb(),
            )
            return

        bot.answer_callback_query(call.id)
        waiting[uid] = {"step": "game_id", "gkey": gkey, "item": item, "final_price": final_price}
        format_guide = (
            "<code>Player_ID (Zone_ID)</code> ឧទាហរណ៍៖ <code>12345678 (1234)</code>"
            if game.get("req_zone")
            else "<code>Player_ID</code> ឧទាហរណ៍៖ <code>12345678</code>"
        )
        disc_lbl = f" (🔥 បញ្ចុះតម្លៃ -{disc}%)" if disc > 0 else ""
        bot.send_message(
            uid,
            f"╭─────────────────────╮\n"
            f"  🎮 <b>កញ្ចប់:</b> {item['name']}\n"
            f"  💰 <b>តម្លៃ:</b> ${final_price:.2f}{disc_lbl}\n"
            f"╰─────────────────────╯\n"
            f"📝 <b>សូមបញ្ចូល Player ID ហ្គេមរបស់អ្នក:</b>\n"
            f"👉 ទម្រង់: {format_guide}",
            reply_markup=cancel_kb(),
        )

    elif data.startswith("view_acc:"):
        aid = data.split(":")[1]
        acc = accounts_db.get(aid)
        if not acc:
            bot.answer_callback_query(call.id, "❌ អាខោននេះលែងមានក្នុងស្តុក!")
            return
        stock = len(acc.get("stock", []))
        if stock == 0:
            bot.answer_callback_query(call.id, "❌ ដាច់ស្តុកហើយ!", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        orig_price = acc["price"]
        disc = discounts.get("account", 0)
        final_price = get_disc_price(orig_price, disc)
        price_display = f"${final_price:.2f} (ដើម: <s>${orig_price:.2f}</s> -{disc}%)" if disc > 0 else f"${orig_price:.2f}"

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"💳 បង់ ${final_price:.2f} ទិញភ្លាមៗ", callback_data=f"confirm_buy_acc:{aid}")],
            [InlineKeyboardButton("⬅️ ថយក្រោយ", callback_data="back_to_accs")]
        ])
        bot.edit_message_text(
            f"╭─────────────────────╮\n"
            f"  🛒 <b>{acc['title']}</b>\n"
            f"╰─────────────────────╯\n"
            f"📝 <b>ការពណ៌នា:</b> {acc.get('desc', 'គ្មានព័ត៌មាន')}\n"
            f"💰 <b>តម្លៃ:</b> {price_display}\n"
            f"📦 <b>ចំនួនក្នុងស្តុក:</b> {stock}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💡 ចុចប៊ូតុងខាងក្រោមដើម្បីទិញ (ប្រព័ន្ធកាត់លុយ និងផ្ញើទិន្នន័យជូនភ្លាមៗ)៖",
            chat_id=uid,
            message_id=call.message.message_id,
            reply_markup=kb,
        )

    elif data == "back_to_accs":
        bot.answer_callback_query(call.id)
        kb = accounts_menu_kb()
        if not kb:
            bot.edit_message_text("❌ មិនទាន់មានអាខោនដាក់លក់នៅឡើយទេ!", chat_id=uid, message_id=call.message.message_id)
        else:
            bot.edit_message_text("🛒 <b>សូមជ្រើសរើសប្រភេទអាខោនដែលអ្នកចង់ទិញ៖</b>", chat_id=uid, message_id=call.message.message_id, reply_markup=kb)

    elif data.startswith("confirm_buy_acc:"):
        aid = data.split(":")[1]
        acc = accounts_db.get(aid)
        if not acc or len(acc.get("stock", [])) == 0:
            bot.answer_callback_query(call.id, "❌ អាខោននេះអស់ពីស្តុកហើយ!", show_alert=True)
            return
        orig_price = acc["price"]
        disc = discounts.get("account", 0)
        price = get_disc_price(orig_price, disc)

        if bal(uid) < price:
            bot.answer_callback_query(call.id, "❌ សមតុល្យមិនគ្រប់គ្រាន់!", show_alert=True)
            bot.send_message(
                uid,
                f"❌ <b>សមតុល្យមិនគ្រប់គ្រាន់!</b>\n💰 តម្លៃអាខោន: <b>${price:.2f}</b>\n💳 អ្នកមាន: <b>${bal(uid):.2f}</b>",
                reply_markup=deposit_amt_kb(),
            )
            return

        ded_bal(uid, price)
        item_data = acc["stock"].pop(0)
        _save(ACCOUNTS_FILE, accounts_db)
        bot.answer_callback_query(call.id, "✅ ទិញបានជោគជ័យ!")

        oid = f"ACC_{int(time.time())}"
        orders_db[oid] = {
            "uid": str(uid),
            "service_name": f"Account - {acc['title']}",
            "target": item_data,
            "qty": 1,
            "charge": price,
            "status": "completed",
            "type": "ACCOUNT",
            "time": int(time.time()),
        }
        _save(ORDERS_FILE, orders_db)

        bot.send_message(
            uid,
            f"🎉 <b>ការទិញអាខោនទទួលបានជោគជ័យ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 លេខកូដ: <code>{oid}</code>\n"
            f"🛒 ប្រភេទ: <b>{acc['title']}</b>\n"
            f"💰 ចំណាយ: <b>${price:.2f}</b>\n"
            f"💳 សមតុល្យនៅសល់: <b>${bal(uid):.2f}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🔐 <b>ព័ត៌មានគណនីរបស់អ្នក (Account Data):</b>\n"
            f"<code>{item_data}</code>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ <i>សូមផ្លាស់ប្តូរពាក្យសម្ងាត់ និងចងភ្ជាប់ព័ត៌មានផ្ទាល់ខ្លួនរបស់អ្នកភ្លាមៗ!</i>",
            reply_markup=user_kb(uid),
        )
        try:
            bot.send_message(
                ADMIN_ID,
                f"🛒 <b>ភ្ញៀវបានទិញអាខោន!</b>\n"
                f"👤 <code>{uid}</code> | 📦 {acc['title']}\n"
                f"💰 ចំណូល: +${price:.2f}\n"
                f"📦 ស្តុកនៅសល់: {len(acc['stock'])}",
            )
        except: pass

    # --- ADMIN ACTIONS ---
    elif data.startswith("edit_smm_price:"):
        if uid != ADMIN_ID: return
        sid = data.split(":")[1]
        srv = services_db.get(sid)
        if not srv:
            bot.answer_callback_query(call.id, "❌ រកមិនឃើញសេវា")
            return
        bot.answer_callback_query(call.id)
        waiting[uid] = {"step": "admin_edit_smm_rate", "sid": sid}
        bot.send_message(
            uid,
            f"✏️ <b>កែតម្លៃសេវាកម្ម SMM</b>\n"
            f"📌 សេវា: <b>{srv['name']}</b>\n"
            f"💰 តម្លៃបច្ចុប្បន្ន: <b>${srv['rate']:.2f}/1k</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"សូមបញ្ចូល <b>តម្លៃថ្មី (USD) ក្នុង 1,000 ចំនួន</b> (ឧ: <code>1.10</code>):",
            reply_markup=cancel_kb(),
        )

    elif data.startswith("adm_game_items_edit:"):
        if uid != ADMIN_ID: return
        gkey = data.split(":")[1]
        game = games_db.get(gkey)
        if not game:
            bot.answer_callback_query(call.id, "❌ រកមិនឃើញហ្គេម")
            return
        bot.answer_callback_query(call.id)
        btns = []
        for idx, it in enumerate(game.get("items", [])):
            btns.append([InlineKeyboardButton(f"✏️ {it['name']} (${it['price']:.2f})", callback_data=f"edit_game_price:{gkey}:{idx}")])
        btns.append([InlineKeyboardButton("🗑️ លុបហ្គេមនេះចោល", callback_data=f"del_game:{gkey}")])
        bot.send_message(uid, f"🎮 <b>ជ្រើសរើសកញ្ចប់ដែលចង់កែតម្លៃក្នុង {game['title']}៖</b>", reply_markup=InlineKeyboardMarkup(btns))

    elif data.startswith("edit_game_price:"):
        if uid != ADMIN_ID: return
        _, gkey, idx_str = data.split(":")
        idx = int(idx_str)
        game = games_db.get(gkey)
        item = game["items"][idx]
        bot.answer_callback_query(call.id)
        waiting[uid] = {"step": "admin_edit_game_price", "gkey": gkey, "idx": idx}
        bot.send_message(
            uid,
            f"✏️ <b>កែតម្លៃកញ្ចប់ហ្គេម</b>\n"
            f"🎮 ហ្គេម: <b>{game['title']}</b>\n"
            f"💎 កញ្ចប់: <b>{item['name']}</b>\n"
            f"💰 តម្លៃបច្ចុប្បន្ន: <b>${item['price']:.2f}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"សូមបញ្ចូល <b>តម្លៃថ្មី (USD)</b> (ឧ: <code>2.30</code>):",
            reply_markup=cancel_kb(),
        )

    elif data.startswith("edit_acc_price:"):
        if uid != ADMIN_ID: return
        aid = data.split(":")[1]
        acc = accounts_db.get(aid)
        if not acc:
            bot.answer_callback_query(call.id, "❌ រកមិនឃើញអាខោន")
            return
        bot.answer_callback_query(call.id)
        waiting[uid] = {"step": "admin_edit_acc_price", "aid": aid}
        bot.send_message(
            uid,
            f"✏️ <b>កែតម្លៃអាខោន</b>\n"
            f"🛒 ប្រភេទ: <b>{acc['title']}</b>\n"
            f"💰 តម្លៃបច្ចុប្បន្ន: <b>${acc['price']:.2f}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"សូមបញ្ចូល <b>តម្លៃថ្មី (USD)</b> (ឧ: <code>4.50</code>):",
            reply_markup=cancel_kb(),
        )

    elif data.startswith("set_disc:"):
        if uid != ADMIN_ID: return
        target = data.split(":")[1]
        target_name = "សេវាកម្ម SMM" if target == "smm" else ("Top Up Game" if target == "game" else "ទិញអាខោន")
        bot.answer_callback_query(call.id)
        waiting[uid] = {"step": "admin_input_disc", "target": target}
        bot.send_message(
            uid,
            f"🏷️ <b>កំណត់ភាគរយបញ្ចុះតម្លៃសម្រាប់ {target_name}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"សូមបញ្ចូលភាគរយ % (ឧ: <code>10</code> ឬ <code>20</code> ឬវាយ <code>0</code> ដើម្បីលុបប្រូម៉ូសិនវិញ):",
            reply_markup=cancel_kb(),
        )

    elif data.startswith("del_smm:"):
        if uid != ADMIN_ID: return
        sid = data.split(":")[1]
        if sid in services_db:
            del services_db[sid]
            _save(SERVICES_FILE, services_db)
            bot.answer_callback_query(call.id, "✅ បានលុបសេវារួចរាល់")
            bot.edit_message_text("🗑️ បានលុបសេវាកម្ម SMM នេះចេញ!", chat_id=uid, message_id=call.message.message_id)

    elif data.startswith("adm_set_zone:"):
        if uid != ADMIN_ID: return
        val = data.split(":")[1] == "yes"
        step = waiting.get(uid)
        if isinstance(step, dict) and step.get("step") == "admin_game_zone":
            step["req_zone"] = val
            step["step"] = "admin_item_name"
            bot.answer_callback_query(call.id)
            bot.send_message(
                uid,
                "💎 <b>សូមបញ្ចូលឈ្មោះកញ្ចប់អីវ៉ាន់</b>\n(ឧទាហរណ៍៖ <code>💎 86 Diamonds</code> ឬ <code>🪙 60 UC</code>):",
                reply_markup=cancel_kb(),
            )

    elif data.startswith("del_game:"):
        if uid != ADMIN_ID: return
        gkey = data.split(":")[1]
        if gkey in games_db:
            del games_db[gkey]
            _save(GAMES_FILE, games_db)
            bot.answer_callback_query(call.id, "✅ បានលុបហ្គេមរួចរាល់")
            bot.edit_message_text(
                "🗑️ បានលុបហ្គេមនេះចេញពីបញ្ជីលក់!",
                chat_id=uid,
                message_id=call.message.message_id,
            )

    elif data.startswith("del_acc:"):
        if uid != ADMIN_ID: return
        aid = data.split(":")[1]
        if aid in accounts_db:
            del accounts_db[aid]
            _save(ACCOUNTS_FILE, accounts_db)
            bot.answer_callback_query(call.id, "✅ បានលុបអាខោនរួចរាល់")
            bot.edit_message_text(
                "🗑️ បានលុបមុខទំនិញអាខោននេះចោល!",
                chat_id=uid,
                message_id=call.message.message_id,
            )

    elif data.startswith("adm_add_stock:"):
        if uid != ADMIN_ID: return
        aid = data.split(":")[1]
        acc = accounts_db.get(aid)
        if not acc:
            bot.answer_callback_query(call.id, "❌ រកមិនឃើញទំនិញ")
            return
        bot.answer_callback_query(call.id)
        waiting[uid] = {"step": "admin_push_stock", "aid": aid}
        bot.send_message(
            uid,
            f"📥 <b>បញ្ចូលស្តុកបន្ថែមសម្រាប់: {acc['title']}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"សូមផ្ញើព័ត៌មានគណនី (មួយជួរមួយអាខោន):",
            reply_markup=cancel_kb(),
        )

    elif data.startswith("manual_dep:"):
        if uid != ADMIN_ID: return
        _, act, dep_id = data.split(":")
        dep = store_deps.get(dep_id)
        if not dep:
            bot.answer_callback_query(call.id, "❌ គ្មានទិន្នន័យ")
            return
        target_uid, amt = int(dep["uid"]), float(dep["amount"])
        if act == "approve":
            if dep.get("status") == "confirmed":
                bot.answer_callback_query(call.id, "⚠️ ដាក់រួចហើយ!")
                return
            add_bal(target_uid, amt)
            dep["status"] = "confirmed"
            _save(STORE_DEP_FILE, store_deps)
            bot.answer_callback_query(call.id, "✅ បានបញ្ចូលលុយ")
            try:
                bot.send_message(
                    target_uid,
                    f"✅ <b>Admin បានបញ្ចូលលុយជូន:</b> +${amt:.2f}\n💳 សមតុល្យសរុប: <b>${bal(target_uid):.2f}</b>",
                )
            except: pass
        elif act == "reject":
            dep["status"] = "rejected"
            _save(STORE_DEP_FILE, store_deps)
            bot.answer_callback_query(call.id, "❌ បដិសេធ")
            try:
                bot.send_message(target_uid, "❌ សំណើដាក់ប្រាក់ត្រូវបានបដិសេធ។")
            except: pass

    elif data.startswith("admin_order:"):
        if uid != ADMIN_ID: return
        _, act, oid = data.split(":")
        order = orders_db.get(oid)
        if not order:
            bot.answer_callback_query(call.id, "❌ រកមិនឃើញ Order")
            return
        target_uid = int(order["uid"])
        if act == "done":
            order["status"] = "completed"
            _save(ORDERS_FILE, orders_db)
            bot.answer_callback_query(call.id, "✅ បញ្ចប់ Order")
            bot.edit_message_text(f"✅ Order <code>{oid}</code> ត្រូវបានបញ្ចប់!", chat_id=uid, message_id=call.message.message_id)
            try:
                bot.send_message(
                    target_uid,
                    f"🎉 <b>Order របស់អ្នកត្រូវបានបញ្ចប់ជោគជ័យ!</b>\n🆔 កូដ: <code>{oid}</code>\n📦 សេវាកម្ម: {order['service_name']}",
                )
            except: pass
        elif act == "cancel":
            add_bal(target_uid, order["charge"])
            order["status"] = "canceled"
            _save(ORDERS_FILE, orders_db)
            bot.answer_callback_query(call.id, "❌ Cancel & Refund")
            bot.edit_message_text(f"❌ Order <code>{oid}</code> ត្រូវបាន Refund!", chat_id=uid, message_id=call.message.message_id)
            try:
                bot.send_message(
                    target_uid,
                    f"⚠️ <b>Order <code>{oid}</code> ត្រូវបានបដិសេធ!</b>\n💰 ប្រាក់បានបង្វិលជូនវិញ: +${order['charge']:.2f}",
                )
            except: pass

    elif data == "admin_change_api":
        if uid != ADMIN_ID: return
        bot.answer_callback_query(call.id)
        waiting[uid] = "admin_set_api_url"
        bot.send_message(uid, "🌐 <b>សូមផ្ញើ SMM API URL (API v2):</b>", reply_markup=cancel_kb())

    elif data == "admin_refresh_apibal":
        if uid != ADMIN_ID: return
        bot.answer_callback_query(call.id, "🔄 ឆែកសមតុល្យ...")
        bot.send_message(uid, f"💰 <b>សមតុល្យ Provider:</b> <b>{smm_api_balance()}</b>")

# ═══════════════════════════════════════════════════════════
#  TEXT MESSAGES HANDLER
# ═══════════════════════════════════════════════════════════
@bot.message_handler(func=lambda m: True)
def handle_messages(message):
    uid = message.chat.id
    text = message.text.strip() if message.text else ""
    step = waiting.get(uid)

    if text in ("✕ Cancel", "❌ Cancel"):
        waiting.pop(uid, None)
        bot.send_message(
            uid,
            "🏠 ត្រឡប់មកកាន់ផ្ទាំងដើមវិញ",
            reply_markup=admin_kb() if uid == ADMIN_ID else user_kb(uid),
        )
        return

    if text in ("📱 ចុចភ្ជាប់លេខទូរស័ព្ទ (Share Contact)", "📱 ភ្ជាប់លេខទូរស័ព្ទ"):
        bot.send_message(
            uid,
            "📱 សូមចុចប៊ូតុង <b>«Share Contact»</b> ខាងក្រោមដើម្បីបញ្ជាក់លេខទូរស័ព្ទរបស់អ្នក៖",
            reply_markup=request_contact_kb(),
        )
        return

    if uid == ADMIN_ID and step == "admin_input_dep_target":
        target = text.replace("@", "")
        waiting[uid] = {"step": "admin_input_dep_amt", "target": target}
        bot.send_message(
            uid,
            f"👤 អ្នកទទួល: <code>{target}</code>\n"
            f"💰 <b>សូមបញ្ចូលចំនួនទឹកប្រាក់ ($) ដែលចង់ដាក់ឱ្យ:</b> (ឧ: <code>5.00</code>):",
            reply_markup=cancel_kb(),
        )
        return

    if uid == ADMIN_ID and isinstance(step, dict) and step.get("step") == "admin_input_dep_amt":
        try:
            amt = round(float(text.replace("$", "")), 2)
            if amt <= 0: raise ValueError
        except:
            bot.send_message(uid, "❌ សូមបញ្ចូលចំនួនទឹកប្រាក់ជាលេខវិជ្ជមាន (ឧ: 5.00):")
            return

        target_input = str(step["target"])
        final_uid = None
        if target_input in users_db:
            final_uid = target_input
        else:
            for u_k, u_v in users_db.items():
                if u_v.get("username", "").lower() == target_input.lower():
                    final_uid = u_k
                    break

        if not final_uid:
            final_uid = target_input

        add_bal(final_uid, amt)
        waiting.pop(uid, None)
        new_balance = bal(final_uid)

        bot.send_message(
            uid,
            f"✅ <b>បានបញ្ចូលទឹកប្រាក់ជូនភ្ញៀវជោគជ័យ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 ភ្ញៀវ ID: <code>{final_uid}</code>\n"
            f"💰 ចំនួនបន្ថែម: <b>+${amt:.2f}</b>\n"
            f"💳 សមតុល្យបច្ចុប្បន្ន: <b>${new_balance:.2f}</b>",
            reply_markup=admin_kb(),
        )
        try:
            bot.send_message(
                int(final_uid),
                f"🎉 <b>Admin បានបញ្ចូលទឹកប្រាក់ជូនអ្នក!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💰 ចំនួនបន្ថែម: <b>+${amt:.2f}</b>\n"
                f"💳 សមតុល្យសរុប: <b>${new_balance:.2f}</b>\n"
                f"💡 សូមរីករាយជាមួយសេវាកម្មរបស់យើង!",
            )
        except: pass
        return

    if uid == ADMIN_ID and isinstance(step, dict) and step.get("step") == "admin_edit_smm_rate":
        try:
            rate = round(float(text.replace("$", "")), 2)
            if rate <= 0: raise ValueError
        except:
            bot.send_message(uid, "❌ សូមបញ្ចូលតម្លៃជាលេខ (ឧ: 1.50):")
            return
        sid = step["sid"]
        if sid in services_db:
            services_db[sid]["rate"] = rate
            _save(SERVICES_FILE, services_db)
            waiting.pop(uid, None)
            bot.send_message(uid, f"✅ <b>បានកែតម្លៃសេវា SMM ជោគជ័យ!</b>\n📌 {services_db[sid]['name']}\n💰 តម្លៃថ្មី: <b>${rate:.2f}/1k</b>", reply_markup=admin_kb())
        return

    if uid == ADMIN_ID and isinstance(step, dict) and step.get("step") == "admin_edit_game_price":
        try:
            price = round(float(text.replace("$", "")), 2)
            if price <= 0: raise ValueError
        except:
            bot.send_message(uid, "❌ សូមបញ្ចូលតម្លៃជាលេខ (ឧ: 2.00):")
            return
        gkey, idx = step["gkey"], step["idx"]
        if gkey in games_db and idx < len(games_db[gkey]["items"]):
            games_db[gkey]["items"][idx]["price"] = price
            _save(GAMES_FILE, games_db)
            waiting.pop(uid, None)
            bot.send_message(uid, f"✅ <b>បានកែតម្លៃកញ្ចប់ហ្គេមជោគជ័យ!</b>\n🎮 {games_db[gkey]['title']} - {games_db[gkey]['items'][idx]['name']}\n💰 តម្លៃថ្មី: <b>${price:.2f}</b>", reply_markup=admin_kb())
        return

    if uid == ADMIN_ID and isinstance(step, dict) and step.get("step") == "admin_edit_acc_price":
        try:
            price = round(float(text.replace("$", "")), 2)
            if price <= 0: raise ValueError
        except:
            bot.send_message(uid, "❌ សូមបញ្ចូលតម្លៃជាលេខ (ឧ: 5.00):")
            return
        aid = step["aid"]
        if aid in accounts_db:
            accounts_db[aid]["price"] = price
            _save(ACCOUNTS_FILE, accounts_db)
            waiting.pop(uid, None)
            bot.send_message(uid, f"✅ <b>បានកែតម្លៃអាខោនជោគជ័យ!</b>\n🛒 {accounts_db[aid]['title']}\n💰 តម្លៃថ្មី: <b>${price:.2f}</b>", reply_markup=admin_kb())
        return

    if uid == ADMIN_ID and isinstance(step, dict) and step.get("step") == "admin_input_disc":
        try:
            percent = int(text.replace("%", ""))
            if percent < 0 or percent > 100: raise ValueError
        except:
            bot.send_message(uid, "❌ សូមបញ្ចូលភាគរយជាលេខពី 0 ដល់ 100:")
            return
        target = step["target"]
        discounts[target] = percent
        _save(DISCOUNTS_FILE, discounts)
        waiting.pop(uid, None)
        target_name = "សេវាកម្ម SMM" if target == "smm" else ("Top Up Game" if target == "game" else "ទិញអាខោន")
        bot.send_message(
            uid,
            f"✅ <b>បានកំណត់បញ្ចុះតម្លៃជោគជ័យ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📦 ផ្នែក: <b>{target_name}</b>\n"
            f"🏷️ បញ្ចុះតម្លៃ: <b>{percent}%</b>\n"
            f"💡 ភ្ញៀវនឹងឃើញស្លាកបញ្ចុះតម្លៃ និងគិតតម្លៃពិសេសភ្លាមៗ!",
            reply_markup=admin_kb(),
        )
        return

    if uid == ADMIN_ID and step == "admin_smm_cat":
        waiting[uid] = {"step": "admin_smm_name", "cat": text}
        bot.send_message(uid, f"📁 ប្រភេទ: <b>{text}</b>\n\n📝 សូមបញ្ចូល <b>ឈ្មោះសេវាកម្ម SMM</b> (ឧទាហរណ៍៖ 👍 FB Likes Real):", reply_markup=cancel_kb())
        return

    if uid == ADMIN_ID and isinstance(step, dict) and step.get("step") == "admin_smm_name":
        step["name"] = text
        step["step"] = "admin_smm_rate"
        waiting[uid] = step
        bot.send_message(uid, f"💰 សូមបញ្ចូល <b>តម្លៃដើមគិតជា USD ($) ក្នុង 1,000 ចំនួន</b> (ឧ: <code>1.20</code>):", reply_markup=cancel_kb())
        return

    if uid == ADMIN_ID and isinstance(step, dict) and step.get("step") == "admin_smm_rate":
        try:
            rate = round(float(text.replace("$", "")), 2)
            if rate <= 0: raise ValueError
        except:
            bot.send_message(uid, "❌ សូមបញ្ចូលតម្លៃជាលេខ (ឧ: 1.50):")
            return
        step["rate"] = rate
        step["step"] = "admin_smm_minmax"
        waiting[uid] = step
        bot.send_message(uid, "🔢 សូមបញ្ចូលចំនួន <b>Min និង Max</b> ចន្លោះដកឃ្លា (ឧ: <code>100 10000</code>):", reply_markup=cancel_kb())
        return

    if uid == ADMIN_ID and isinstance(step, dict) and step.get("step") == "admin_smm_minmax":
        try:
            parts = text.split()
            s_min, s_max = int(parts[0]), int(parts[1])
        except:
            bot.send_message(uid, "❌ សូមបញ្ចូលលេខចំនួនពីរ (ឧ: 100 10000):")
            return
        step["min"] = s_min
        step["max"] = s_max
        step["step"] = "admin_smm_api_id"
        waiting[uid] = step
        bot.send_message(uid, "🌐 សូមបញ្ចូល <b>Service ID នៅលើវេបសាយ Provider API</b> (បើអត់មានទេ វាយលេខ <code>0</code>):", reply_markup=cancel_kb())
        return

    if uid == ADMIN_ID and isinstance(step, dict) and step.get("step") == "admin_smm_api_id":
        try: api_id = int(text)
        except: api_id = 0
        sid = f"smm_{int(time.time())}"
        services_db[sid] = {
            "cat": step["cat"],
            "name": step["name"],
            "rate": step["rate"],
            "min": step["min"],
            "max": step["max"],
            "api_service_id": api_id
        }
        _save(SERVICES_FILE, services_db)
        waiting.pop(uid, None)
        bot.send_message(
            uid,
            f"✅ <b>បានបន្ថែមសេវាកម្ម SMM ជោគជ័យ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📁 ប្រភេទ: <b>{step['cat']}</b>\n"
            f"📌 ឈ្មោះ: <b>{step['name']}</b>\n"
            f"💵 តម្លៃ: <b>${step['rate']:.2f}/1k</b>\n"
            f"🔢 Min: {step['min']:,} - Max: {step['max']:,}\n"
            f"💡 ភ្ញៀវអាចមើលឃើញ និងកុម្ម៉ង់បានភ្លាមៗ!",
            reply_markup=admin_kb()
        )
        return

    if uid == ADMIN_ID and step == "admin_acc_title":
        waiting[uid] = {"step": "admin_acc_desc", "title": text}
        bot.send_message(uid, "📝 <b>សូមបញ្ចូលការពិពណ៌នាខ្លីៗពីអាខោន</b> (ឧ: Full Info ឬ Lv 70...):", reply_markup=cancel_kb())
        return

    if uid == ADMIN_ID and isinstance(step, dict) and step.get("step") == "admin_acc_desc":
        step["desc"] = text
        step["step"] = "admin_acc_price"
        waiting[uid] = step
        bot.send_message(uid, "💰 <b>សូមបញ្ចូលតម្លៃដើមលក់គិតជា USD ($)</b> (ឧ: <code>2.50</code>):", reply_markup=cancel_kb())
        return

    if uid == ADMIN_ID and isinstance(step, dict) and step.get("step") == "admin_acc_price":
        try:
            price = round(float(text.replace("$", "")), 2)
            if price <= 0: raise ValueError
        except:
            bot.send_message(uid, "❌ សូមបញ្ចូលតម្លៃជាលេខ (ឧ: 5.00):")
            return
        aid = f"acc_{int(time.time())}"
        accounts_db[aid] = {
            "title": step["title"],
            "desc": step["desc"],
            "price": price,
            "stock": [],
        }
        _save(ACCOUNTS_FILE, accounts_db)
        waiting.pop(uid, None)
        bot.send_message(
            uid,
            f"✅ <b>បានបង្កើតប្រភេទអាខោនជោគជ័យ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🛒 ប្រភេទ: <b>{step['title']}</b>\n"
            f"💰 តម្លៃដើម: <b>${price:.2f}</b>\n"
            f"📦 ស្តុកបច្ចុប្បន្ន: <b>0</b> (សូមចុច <b>📥 បញ្ចូលស្តុកអាខោន</b> ដើម្បីដាក់អីវ៉ាន់លក់)!",
            reply_markup=admin_kb(),
        )
        return

    if uid == ADMIN_ID and isinstance(step, dict) and step.get("step") == "admin_push_stock":
        items = [line.strip() for line in text.split("\n") if line.strip()]
        if not items:
            bot.send_message(uid, "❌ សូមបញ្ចូលទិន្នន័យអាខោនយ៉ាងហោចណាស់មួយ:")
            return
        aid = step["aid"]
        if aid in accounts_db:
            accounts_db[aid].setdefault("stock", []).extend(items)
            _save(ACCOUNTS_FILE, accounts_db)
            total_stock = len(accounts_db[aid]["stock"])
            waiting.pop(uid, None)
            bot.send_message(
                uid,
                f"✅ <b>បានបញ្ចូលទំនិញចូលស្តុកជោគជ័យ!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🛒 ប្រភេទ: <b>{accounts_db[aid]['title']}</b>\n"
                f"➕ បន្ថែមថ្មី: <b>{len(items)}</b> អាខោន\n"
                f"📦 ស្តុកសរុបបច្ចុប្បន្ន: <b>{total_stock}</b> អាខោន\n"
                f"💡 ភ្ញៀវអាចចូលទិញយកទិន្នន័យបានភ្លាមៗ!",
                reply_markup=admin_kb(),
            )
        return

    if uid == ADMIN_ID and step == "admin_game_title":
        title_in = text.strip()
        matched_gkey = None
        for k, v in games_db.items():
            if v.get("title", "").strip().lower() == title_in.lower():
                matched_gkey = k
                break

        if matched_gkey:
            waiting[uid] = {
                "step": "admin_item_name",
                "gkey": matched_gkey,
                "title": games_db[matched_gkey]["title"],
                "req_zone": games_db[matched_gkey].get("req_zone", False),
            }
            bot.send_message(
                uid,
                f"🎮 ហ្គេម <b>{games_db[matched_gkey]['title']}</b> មានរួចហើយ!\n\n"
                f"💎 <b>សូមបញ្ចូលឈ្មោះកញ្ចប់អីវ៉ាន់ថ្មីបន្ថែម:</b>\n"
                f"(ឧទាហរណ៍៖ <code>💎 100 Diamonds</code>):",
                reply_markup=cancel_kb(),
            )
        else:
            gkey = f"game_{int(time.time())}"
            waiting[uid] = {"step": "admin_game_zone", "gkey": gkey, "title": title_in}
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ ត្រូវការ Zone ID (ដូច MLBB)", callback_data="adm_set_zone:yes")],
                [InlineKeyboardButton("❌ មិនត្រូវការ (ដូច Free Fire/PUBG)", callback_data="adm_set_zone:no")],
            ])
            bot.send_message(uid, f"🎮 ឈ្មោះហ្គេម: <b>{title_in}</b>\n\nតើហ្គេមនេះត្រូវការ Zone ID ដែរឬទេ?", reply_markup=kb)
        return

    if uid == ADMIN_ID and isinstance(step, dict) and step.get("step") == "admin_item_name":
        step["item_name"] = text
        step["step"] = "admin_item_price"
        waiting[uid] = step
        bot.send_message(
            uid,
            f"💰 <b>សូមបញ្ចូលតម្លៃដើមលក់គិតជា USD ($)</b> សម្រាប់ {text}\n(ឧ: <code>1.25</code>):",
            reply_markup=cancel_kb(),
        )
        return

    if uid == ADMIN_ID and isinstance(step, dict) and step.get("step") == "admin_item_price":
        try:
            price = round(float(text.replace("$", "")), 2)
            if price <= 0: raise ValueError
        except:
            bot.send_message(uid, "❌ សូមបញ្ចូលតម្លៃជាលេខ (ឧ: 1.50):")
            return

        gkey = step["gkey"]
        if gkey not in games_db:
            games_db[gkey] = {
                "title": step["title"],
                "req_zone": step.get("req_zone", False),
                "items": [],
            }

        games_db[gkey].setdefault("items", []).append({
            "id": f"it_{int(time.time())}",
            "name": step["item_name"],
            "price": price,
        })
        _save(GAMES_FILE, games_db)
        waiting.pop(uid, None)
        bot.send_message(
            uid,
            f"✅ <b>បានដាក់លក់ហ្គេមជោគជ័យ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🎮 ហ្គេម: <b>{games_db[gkey]['title']}</b>\n"
            f"💎 កញ្ចប់: <b>{step['item_name']}</b>\n"
            f"💰 តម្លៃដើម: <b>${price:.2f}</b>\n"
            f"💡 ភ្ញៀវអាចមើលឃើញ និងកុម្ម៉ង់ Top Up បានភ្លាមៗ!",
            reply_markup=admin_kb(),
        )
        return

    if uid == ADMIN_ID and step == "admin_set_api_url":
        api_cfg["api_url"] = text
        _save(API_CONFIG_FILE, api_cfg)
        waiting[uid] = "admin_set_api_key"
        bot.send_message(uid, "🔑 <b>សូមបញ្ចូល API Key:</b>", reply_markup=cancel_kb())
        return

    if uid == ADMIN_ID and step == "admin_set_api_key":
        api_cfg["api_key"] = text
        _save(API_CONFIG_FILE, api_cfg)
        waiting.pop(uid, None)
        bot.send_message(uid, "✅ <b>បានរក្សាទុក API ជោគជ័យ!</b>", reply_markup=admin_kb())
        return

    # --- SMM FLOW ---
    if isinstance(step, dict) and step.get("step") == "smm_link":
        step["link"] = text
        srv = services_db[step["sid"]]
        step["step"] = "smm_qty"
        waiting[uid] = step
        disc = discounts.get("smm", 0)
        cur_rate = get_disc_price(srv["rate"], disc)
        rate_lbl = f"${cur_rate:.2f}/1k 🔥(-{disc}%)" if disc > 0 else f"${srv['rate']:.2f}/1k"
        bot.send_message(
            uid,
            f"🔢 <b>សូមបញ្ចូលចំនួនដែលចង់បាន:</b>\n"
            f"• អប្បបរមា (Min): <code>{srv['min']:,}</code>\n"
            f"• អតិបរមា (Max): <code>{srv['max']:,}</code>\n"
            f"💵 តម្លៃគិតជា: <b>{rate_lbl}</b>",
            reply_markup=cancel_kb(),
        )
        return

    if isinstance(step, dict) and step.get("step") == "smm_qty":
        try:
            qty = int(text.replace(",", ""))
        except:
            bot.send_message(uid, "❌ សូមបញ្ចូលជាលេខគត់:")
            return
        srv = services_db[step["sid"]]
        if qty < srv["min"] or qty > srv["max"]:
            bot.send_message(uid, f"❌ ចំនួនត្រូវនៅចន្លោះ {srv['min']:,} ដល់ {srv['max']:,}:")
            return
        disc = discounts.get("smm", 0)
        eff_rate = get_disc_price(srv["rate"], disc)
        cost = max(0.01, round((qty / 1000.0) * eff_rate, 2))

        if bal(uid) < cost:
            waiting.pop(uid, None)
            bot.send_message(
                uid,
                f"❌ សមតុល្យមិនគ្រប់គ្រាន់! (តម្លៃ: ${cost:.2f} | អ្នកមាន: ${bal(uid):.2f})",
                reply_markup=deposit_amt_kb(),
            )
            return
        ded_bal(uid, cost)
        oid = f"SMM_{int(time.time())}"
        waiting.pop(uid, None)
        api_res = smm_api_order(srv.get("api_service_id", 0), step["link"], qty)
        api_id = api_res.get("order", "Pending/Manual")
        orders_db[oid] = {
            "uid": str(uid),
            "service_name": srv["name"],
            "target": step["link"],
            "qty": qty,
            "charge": cost,
            "status": "processing" if "order" in api_res else "pending_admin",
            "type": "SMM",
            "api_order_id": api_id,
            "time": int(time.time()),
        }
        _save(ORDERS_FILE, orders_db)
        disc_msg = f" <i>(បញ្ចុះតម្លៃ -{disc}%)</i>" if disc > 0 else ""
        bot.send_message(
            uid,
            f"🎉 <b>កុម្ម៉ង់បានជោគជ័យ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 លេខកូដ: <code>{oid}</code>\n"
            f"📌 សេវាកម្ម: <b>{srv['name']}</b>\n"
            f"🔗 Link: <code>{step['link']}</code>\n"
            f"🔢 ចំនួន: <b>{qty:,}</b>\n"
            f"💰 ចំណាយ: <b>${cost:.2f}</b>{disc_msg}\n"
            f"💳 សមតុល្យនៅសល់: <b>${bal(uid):.2f}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⚡️ ប្រព័ន្ធកំពុងដំណើរការបញ្ជូនជូនភ្លាមៗ!",
            reply_markup=user_kb(uid),
        )
        admin_kb_order = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Done", callback_data=f"admin_order:done:{oid}"),
                InlineKeyboardButton("❌ Cancel & Refund", callback_data=f"admin_order:cancel:{oid}"),
            ]
        ])
        try:
            bot.send_message(
                ADMIN_ID,
                f"🚨 <b>Order SMM ថ្មី!</b>\n🆔 <code>{oid}</code> | 👤 <code>{uid}</code>\n📌 {srv['name']}\n🔗 Link: {step['link']}\n🔢 Qty: {qty:,} | 💰 ${cost:.2f}",
                reply_markup=admin_kb_order,
            )
        except: pass
        return

    # --- GAME TOP UP FLOW ---
    if isinstance(step, dict) and step.get("step") == "game_id":
        player_info = text
        item = step["item"]
        cost = step["final_price"]
        game_title = games_db[step["gkey"]]["title"]

        if bal(uid) < cost:
            waiting.pop(uid, None)
            bot.send_message(uid, "❌ សមតុល្យមិនគ្រប់គ្រាន់!", reply_markup=deposit_amt_kb())
            return

        ded_bal(uid, cost)
        oid = f"GAME_{int(time.time())}"
        waiting.pop(uid, None)

        orders_db[oid] = {
            "uid": str(uid),
            "service_name": f"{game_title} - {item['name']}",
            "target": player_info,
            "qty": 1,
            "charge": cost,
            "status": "processing",
            "type": "GAME",
            "time": int(time.time()),
        }
        _save(ORDERS_FILE, orders_db)

        bot.send_message(
            uid,
            f"🎉 <b>កុម្ម៉ង់បញ្ចូលហ្គេមជោគជ័យ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 លេខកូដ: <code>{oid}</code>\n"
            f"🎮 ហ្គេម: <b>{game_title}</b>\n"
            f"💎 កញ្ចប់: <b>{item['name']}</b>\n"
            f"👤 Player ID: <code>{player_info}</code>\n"
            f"💰 ចំណាយ: <b>${cost:.2f}</b>\n"
            f"💳 សមតុល្យនៅសល់: <b>${bal(uid):.2f}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⏳ Admin កំពុងរៀបចំបញ្ចូលជូន!",
            reply_markup=user_kb(uid),
        )

        admin_kb_game = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ បញ្ចូលរួចរាល់ (Done)", callback_data=f"admin_order:done:{oid}"),
                InlineKeyboardButton("❌ បដិសេធ (Cancel & Refund)", callback_data=f"admin_order:cancel:{oid}"),
            ]
        ])
        try:
            bot.send_message(
                ADMIN_ID,
                f"🎮 <b>Order Top Up Game ថ្មី!</b>\n"
                f"🆔 <code>{oid}</code> | 👤 <code>{uid}</code>\n"
                f"🎮 <b>{game_title}</b>\n"
                f"💎 <b>{item['name']}</b>\n"
                f"📝 <b>Player ID:</b> <code>{player_info}</code>\n"
                f"💰 ចំណូល: <b>${cost:.2f}</b>",
                reply_markup=admin_kb_game,
            )
        except: pass
        return

    if step == "dep_custom":
        try:
            amt = float(text.replace("$", ""))
            if amt < 0.1: raise ValueError
            waiting.pop(uid, None)
            _send_deposit_qr(uid, amt)
        except:
            bot.send_message(uid, "❌ សូមបញ្ចូលចំនួនទឹកប្រាក់ជាលេខ (ឧ: 2.50):")
        return

    # --- USER MENU BUTTONS ---
    if text.startswith("🚀 សេវាកម្ម SMM"):
        kb = category_smm_kb()
        if not kb:
            bot.send_message(
                uid,
                "❌ <b>បច្ចុប្បន្នមិនទាន់មានសេវាកម្ម SMM ដាក់លក់នៅឡើយទេ!</b>\nសូមរង់ចាំ Admin បន្ថែមសេវាកម្មចូលប្រព័ន្ធ។",
                reply_markup=user_kb(uid),
            )
            return
        bot.send_message(uid, "⚡️ <b>សូមជ្រើសរើសប្រភេទបណ្តាញសង្គម៖</b>", reply_markup=kb)
        return

    if text.startswith("🎮 បញ្ចូលហ្គេម"):
        kb = games_menu_kb()
        if not kb:
            bot.send_message(
                uid,
                "❌ <b>មិនទាន់មានហ្គេមដាក់លក់នៅឡើយទេ!</b>\nសូមរង់ចាំ Admin បន្ថែមទំនិញចូលប្រព័ន្ធ។",
                reply_markup=user_kb(uid),
            )
            return
        bot.send_message(uid, "🎮 <b>សូមជ្រើសរើសហ្គេមដែលអ្នកចង់ Top Up៖</b>", reply_markup=kb)
        return

    if text.startswith("🛒 ទិញអាខោន"):
        kb = accounts_menu_kb()
        if not kb:
            bot.send_message(
                uid,
                "❌ <b>បច្ចុប្បន្នមិនទាន់មានអាខោនក្នុងស្តុកនៅឡើយទេ!</b>\nសូមរង់ចាំ Admin បន្ថែមអីវ៉ាន់ចូលក្នុងប្រព័ន្ធ។",
                reply_markup=user_kb(uid),
            )
            return
        bot.send_message(uid, "🛒 <b>សូមជ្រើសរើសប្រភេទអាខោនដែលអ្នកចង់ទិញ៖</b>", reply_markup=kb)
        return

    if text in ("👜 កាបូបលុយ", "👜 Wallet"):
        phone_txt = users_db.get(str(uid), {}).get("phone", "មិនទាន់ភ្ជាប់")
        bot.send_message(
            uid,
            f"╭─────────────────────╮\n"
            f"  👜 <b>ព័ត៌មានកាបូបលុយផ្ទាល់ខ្លួន</b>\n"
            f"╰─────────────────────╯\n"
            f"👤 ID: <code>{uid}</code>\n"
            f"📱 លេខទូរស័ព្ទ: <code>{phone_txt}</code>\n"
            f"💰 សមតុល្យសាច់ប្រាក់: <b>${bal(uid):.2f} USD</b>\n"
            f"─────────────────────\n"
            f"💡 ចុចប៊ូតុង <b>💳 ដាក់ប្រាក់ (Top Up)</b> ដើម្បីបញ្ចូលប្រាក់តាម KHQR។",
            reply_markup=user_kb(uid),
        )
        return

    if text in ("💳 ដាក់ប្រាក់", "💳 ដាក់ប្រាក់ (Top Up)", "💳 Top Up"):
        waiting.pop(uid, None)
        bot.send_message(
            uid,
            f"💸 <b>បញ្ចូលទឹកប្រាក់ស្វ័យប្រវត្តិតាម Bakong KHQR</b>\n"
            f"💳 សមតុល្យបច្ចុប្បន្ន: <b>${bal(uid):.2f}</b>\n\n"
            f"👉 សូមជ្រើសរើសចំនួនប្រាក់ដែលចង់ដាក់៖",
            reply_markup=deposit_amt_kb(),
        )
        return

    if text == "📦 ប្រវត្តិបញ្ជាទិញ":
        u_orders = [o for o in orders_db.values() if o.get("uid") == str(uid)]
        if not u_orders:
            bot.send_message(uid, "❌ គ្មានប្រវត្តិបញ្ជាទិញទេ!")
            return
        msg = "📦 <b>ប្រវត្តិបញ្ជាទិញ ៥ ចុងក្រោយ៖</b>\n━━━━━━━━━━━━━━━━━━\n"
        for o in list(reversed(u_orders))[:5]:
            status_ico = (
                "⏳"
                if o["status"] == "processing"
                else ("✅" if o["status"] == "completed" else "❌")
            )
            msg += f"{status_ico} <b>{o['service_name']}</b>\n  └ ព័ត៌មាន: <code>{o['target']}</code>\n  └ ចំណាយ: ${o['charge']:.2f} | ស្ថានភាព: <b>{o['status'].capitalize()}</b>\n\n"
        bot.send_message(uid, msg)
        return

    if text == "💬 ជំនួយ Support":
        bot.send_message(
            uid,
            "💬 <b>ផ្នែកបម្រើអតិថិជន Khmer SMM & Game</b>\n━━━━━━━━━━━━━━━━━━\n📞 Telegram: @SmeyLov008",
        )
        return

    # --- ADMIN COMMANDS ---
    if uid == ADMIN_ID:
        if text == "💸 ដាក់ទឹកប្រាក់ឱ្យភ្ញៀវ":
            waiting[uid] = "admin_input_dep_target"
            bot.send_message(
                uid,
                "💸 <b>បញ្ចូលទឹកប្រាក់ដោយផ្ទាល់ជូនភ្ញៀវ</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "សូមបញ្ចូល <b>Telegram ID ឬ Username ភ្ញៀវ</b> (ឧទាហរណ៍៖ <code>123456789</code> ឬ <code>@username</code>):",
                reply_markup=cancel_kb(),
            )
            return

        if text == "👥 អ្នកប្រើប្រាស់":
            if not users_db:
                bot.send_message(uid, "❌ មិនទាន់មានអ្នកប្រើប្រាស់នៅឡើយទេ!", reply_markup=admin_kb())
                return
            lines = [f"👥 <b>បញ្ជីអ្នកប្រើប្រាស់សរុប ({len(users_db)} នាក់)៖</b>\n━━━━━━━━━━━━━━━━━━"]
            for u_id, u_info in sorted(users_db.items(), key=lambda x: x[1].get("last", 0), reverse=True)[:35]:
                name = u_info.get("name") or "គ្មានឈ្មោះ"
                uname = f"@{u_info['username']}" if u_info.get("username") else "គ្មាន Username"
                phone = u_info.get("phone") or "គ្មានលេខ"
                u_bal = bal(u_id)
                lines.append(
                    f"👤 <b>{name}</b> ({uname})\n"
                    f"   ├ ID: <code>{u_id}</code>\n"
                    f"   ├ 📱 លេខ: <code>{phone}</code>\n"
                    f"   └ 💰 សមតុល្យ: <b>${u_bal:.2f}</b>\n"
                )
            bot.send_message(uid, "\n".join(lines)[:4000], reply_markup=admin_kb())
            return

        if text.startswith("🏷️ បញ្ចុះតម្លៃ"):
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"🚀 សេវាកម្ម SMM (បច្ចុប្បន្ន: {discounts.get('smm',0)}%)", callback_data="set_disc:smm")],
                [InlineKeyboardButton(f"🎮 Top Up Game (បច្ចុប្បន្ន: {discounts.get('game',0)}%)", callback_data="set_disc:game")],
                [InlineKeyboardButton(f"🛒 ទិញអាខោន (បច្ចុប្បន្ន: {discounts.get('account',0)}%)", callback_data="set_disc:account")]
            ])
            bot.send_message(
                uid,
                f"🏷️ <b>ការកំណត់បញ្ចុះតម្លៃទូទាំងប្រព័ន្ធ (Discounts)</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"• SMM: <b>{discounts.get('smm', 0)}%</b>\n"
                f"• Game: <b>{discounts.get('game', 0)}%</b>\n"
                f"• Account: <b>{discounts.get('account', 0)}%</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"សូមជ្រើសរើសផ្នែកដែលចង់កំណត់ ឬកែប្រែភាគរយ % បញ្ចុះតម្លៃ៖",
                reply_markup=kb
            )
            return

        if text == "➕ បន្ថែមសេវា SMM":
            waiting[uid] = "admin_smm_cat"
            bot.send_message(uid, "📁 <b>សូមបញ្ចូលឈ្មោះប្រភេទបណ្តាញសង្គម</b>\n(ឧទាហរណ៍៖ <code>Facebook</code> ឬ <code>TikTok</code> ឬ <code>Telegram</code>):", reply_markup=cancel_kb())
            return

        if text == "🛠 គ្រប់គ្រងសេវា SMM":
            if not services_db:
                bot.send_message(uid, "❌ មិនទាន់មានសេវាកម្ម SMM ណាមួយនៅឡើយទេ!", reply_markup=admin_kb())
                return
            for sid, s in list(services_db.items())[-10:]:
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✏️ កែប្រែតម្លៃ", callback_data=f"edit_smm_price:{sid}"),
                     InlineKeyboardButton("🗑️ លុបសេវា", callback_data=f"del_smm:{sid}")]
                ])
                bot.send_message(uid, f"📌 <b>{s['name']}</b>\n📁 Category: {s.get('cat','ទូទៅ')}\n💰 តម្លៃដើម: <b>${s['rate']:.2f}/1k</b>", reply_markup=kb)
            return

        if text == "➕ បង្កើតប្រភេទអាខោន":
            waiting[uid] = "admin_acc_title"
            bot.send_message(uid, "📝 <b>សូមបញ្ចូលឈ្មោះ/ប្រភេទអាខោន</b>\n(ឧទាហរណ៍៖ <code>TikTok 10k Follow</code> ឬ <code>Netflix 1 Month</code> ឬ <code>Free Fire VIP</code>):", reply_markup=cancel_kb())
            return

        if text == "📥 បញ្ចូលស្តុកអាខោន":
            if not accounts_db:
                bot.send_message(uid, "❌ មិនទាន់មានប្រភេទអាខោននៅឡើយទេ! សូមចុច <b>➕ បង្កើតប្រភេទអាខោន</b> ជាមុនសិន។", reply_markup=admin_kb())
                return
            btns = []
            for aid, a in accounts_db.items():
                btns.append([InlineKeyboardButton(f"📥 ដាក់ចូល: {a['title']}", callback_data=f"adm_add_stock:{aid}")])
            bot.send_message(uid, "📦 <b>ជ្រើសរើសប្រភេទអាខោនដែលត្រូវដាក់អីវ៉ាន់ចូលស្តុក៖</b>", reply_markup=InlineKeyboardMarkup(btns))
            return

        if text == "🛒 គ្រប់គ្រងអាខោន":
            if not accounts_db:
                bot.send_message(uid, "❌ មិនទាន់មានមុខទំនិញអាខោនណាមួយនៅឡើយទេ!", reply_markup=admin_kb())
                return
            for aid, a in accounts_db.items():
                stock = len(a.get("stock", []))
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✏️ កែតម្លៃ", callback_data=f"edit_acc_price:{aid}"),
                     InlineKeyboardButton("📥 បញ្ចូលស្តុក", callback_data=f"adm_add_stock:{aid}")],
                    [InlineKeyboardButton("🗑️ លុបចោល", callback_data=f"del_acc:{aid}")]
                ])
                bot.send_message(uid, f"📦 <b>{a['title']}</b>\n💰 តម្លៃដើម: <b>${a['price']:.2f}</b>\n📦 ស្តុកនៅសល់: <b>{stock}</b> អាខោន", reply_markup=kb)
            return

        if text == "➕ បន្ថែមហ្គេម/កញ្ចប់":
            waiting[uid] = "admin_game_title"
            bot.send_message(
                uid,
                "📝 <b>សូមបញ្ចូលឈ្មោះហ្គេម</b>\n(ឧទាហរណ៍៖ <code>Mobile Legends</code> ឬ <code>Free Fire</code> ឬ <code>PUBG Mobile</code>):",
                reply_markup=cancel_kb(),
            )
            return

        if text == "🎮 គ្រប់គ្រងហ្គេម":
            if not games_db:
                bot.send_message(uid, "❌ មិនទាន់មានហ្គេមណាមួយក្នុងប្រព័ន្ធនៅឡើយទេ!", reply_markup=admin_kb())
                return
            for gkey, g in games_db.items():
                item_count = len(g.get("items", []))
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✏️ កែតម្លៃកញ្ចប់នីមួយៗ", callback_data=f"adm_game_items_edit:{gkey}")],
                    [InlineKeyboardButton("🗑️ លុបហ្គេមនេះចោល", callback_data=f"del_game:{gkey}")]
                ])
                bot.send_message(
                    uid,
                    f"🎮 <b>{g['title']}</b>\n📦 កញ្ចប់អីវ៉ាន់: <b>{item_count}</b> កញ្ចប់",
                    reply_markup=kb,
                )
            return

        if text == "⚙️ កំណត់ SMM API":
            api_u = api_cfg.get("api_url", "មិនទាន់កំណត់")
            api_k = (
                ("*" * 8 + api_cfg.get("api_key")[-4:])
                if api_cfg.get("api_key")
                else "មិនទាន់កំណត់"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ ប្ដូរ API URL & Key", callback_data="admin_change_api")],
                [InlineKeyboardButton("🔄 ឆែកលុយ Provider", callback_data="admin_refresh_apibal")],
            ])
            bot.send_message(
                uid,
                f"⚙️ <b>SMM API Config</b>\n🌐 URL: <code>{api_u}</code>\n🔑 Key: <code>{api_k}</code>\n💰 សមតុល្យ: <b>{smm_api_balance()}</b>",
                reply_markup=kb,
            )
            return

        if text == "📦 បញ្ជី Order ទាំងអស់":
            pending = [
                (oid, o)
                for oid, o in orders_db.items()
                if o.get("status") in ("processing", "pending_admin")
            ]
            if not pending:
                bot.send_message(uid, "✅ គ្មាន Order កំពុងរង់ចាំទេ!", reply_markup=admin_kb())
                return
            for oid, o in pending[:5]:
                kb = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Done", callback_data=f"admin_order:done:{oid}"),
                        InlineKeyboardButton("❌ Cancel", callback_data=f"admin_order:cancel:{oid}"),
                    ]
                ])
                bot.send_message(
                    uid,
                    f"🆔 <code>{oid}</code> [<b>{o.get('type','SMM')}</b>]\n👤 <code>{o['uid']}</code>\n📌 {o['service_name']}\n🎯 Target: <code>{o['target']}</code>\n💰 ${o['charge']:.2f}",
                    reply_markup=kb,
                )
            return

        if text.startswith("/addbal"):
            parts = text.split()
            if len(parts) == 3:
                try:
                    target, amt = parts[1], float(parts[2])
                    add_bal(target, amt)
                    bot.send_message(
                        uid,
                        f"✅ +${amt:.2f} ទៅកាន់ <code>{target}</code> (Balance: ${bal(target):.2f})",
                    )
                    try:
                        bot.send_message(
                            int(target),
                            f"✅ Admin បានបញ្ចូលប្រាក់: +${amt:.2f}\nសមតុល្យ: <b>${bal(target):.2f}</b>",
                        )
                    except: pass
                except:
                    bot.send_message(uid, "❌ /addbal UID AMOUNT")
            return

        if text.startswith("/deductbal"):
            parts = text.split()
            if len(parts) == 3:
                try:
                    target, amt = parts[1], float(parts[2])
                    ded_bal(target, amt)
                    bot.send_message(uid, f"✅ -${amt:.2f} ពី <code>{target}</code>")
                except:
                    bot.send_message(uid, "❌ /deductbal UID AMOUNT")
            return

        if text == "💰 កាបូបលុយសរុប":
            lines = ["<b>💰 កាបូបលុយអ្នកប្រើ</b>\n━━━━━━━━━━━━━━━━━━"]
            for u_id, u_info in sorted(
                users_db.items(), key=lambda x: x[1].get("last", 0), reverse=True
            )[:25]:
                lines.append(
                    f"👤 {u_info.get('name','?')} (<code>{u_id}</code>): <b>${bal(u_id):.2f}</b>"
                )
            bot.send_message(uid, "\n".join(lines)[:4000], reply_markup=admin_kb())
            return

        if text == "🏠 Menu ភ្ញៀវ":
            bot.send_message(uid, "👁 ទម្រង់ជាភ្ញៀវ", reply_markup=user_kb(uid))
            return

        if text == "📢 ផ្សព្វផ្សាយ":
            waiting[uid] = "broadcast"
            bot.send_message(uid, "📢 ផ្ញើសារដែលចង់ Broadcast:", reply_markup=cancel_kb())
            return

        if step == "broadcast":
            waiting.pop(uid, None)
            sent = 0
            for u in users_db.keys():
                try:
                    bot.send_message(int(u), text)
                    sent += 1
                except: pass
            bot.send_message(uid, f"✅ ផ្ញើបាន {sent} នាក់", reply_markup=admin_kb())
            return

    bot.send_message(uid, "❓ សូមជ្រើសរើស Menu ខាងក្រោម៖", reply_markup=user_kb(uid))

# ═══════════════════════════════════════════════════════════
#  FLASK RUN
# ═══════════════════════════════════════════════════════════
flask_app = Flask(__name__)

@flask_app.route("/health")
@flask_app.route("/")
def health():
    return jsonify({"status": "running", "service": "KhmerSMM Bot", "type": "Static KHQR Verified"})

def run_flask():
    port = int(os.environ.get("PORT", 5055))
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    logger.info("🚀 KhmerSMM Full Bot is running...")
    threading.Thread(target=run_flask, daemon=True).start()
    
    while True:
        try:
            bot.remove_webhook()
            time.sleep(1)
            bot.infinity_polling(timeout=20, long_polling_timeout=15, skip_pending=True)
        except Exception as e:
            logger.error(f"Polling error: {e}. Retrying in 5 seconds...")
            time.sleep(5)
