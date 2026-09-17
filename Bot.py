import json, logging, time, os, sys, subprocess, threading, io
import telebot
from telebot.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from flask import Flask, jsonify

# ─── Auto-install deps ───
def _ensure_deps():
    pkgs = {"PIL": "pillow", "qrcode": "qrcode"}
    for mod, pkg in pkgs.items():
        try: __import__(mod)
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", pkg,
                            "--break-system-packages", "-q"], check=False)
_ensure_deps()

import qrcode
from PIL import Image, ImageDraw, ImageFont

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════
BOT_TOKEN          = "8914728102:AAFCUOmvtYKp3LLoBlg4H4Fbz5PE8joN2zU"
ADMIN_ID           = 5915683588

# Bakong KHQR
BAKONG_TOKEN       = "rbkMVUSQPooaey51jm1cD5ECnzmHyeNX7fBX4Afc16GU8k"
BANK_ACCOUNT       = "samnang_mon@bkrt"
MERCHANT_NAME      = "Smey Lov"
MERCHANT_CITY      = "Phnom Penh"
DEPOSIT_EXPIRE_SEC = 300  # ៥ នាទី (300 វិនាទី)
POLL_INTERVAL      = 5

# ═══════════════════════════════════════════════════════════
#  FILES & STATE
# ═══════════════════════════════════════════════════════════
WALLETS_FILE     = "aio_wallets.json"
USERS_FILE       = "aio_users.json"
STORE_DEP_FILE   = "aio_store_deposits.json"
STORE_ITEMS_FILE = "aio_store_items.json"

def _load(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    except: return default

def _save(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e: logger.error(f"Save {path}: {e}")

wallets    = _load(WALLETS_FILE, {})
users_db   = _load(USERS_FILE, {})
store_deps = _load(STORE_DEP_FILE, {})

def _load_store():
    try:
        with open(STORE_ITEMS_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return {"smm": {}, "game": {}, "acc": {}}

def _save_store(data):
    try:
        with open(STORE_ITEMS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e: logger.error(f"Save store error: {e}")

store_db = _load_store()
waiting    = {}

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

def bal(uid): return float(wallets.get(str(uid), 0.0))
def add_bal(uid, amt):
    wallets[str(uid)] = round(bal(uid) + amt, 2)
    _save(WALLETS_FILE, wallets)
def ded_bal(uid, amt):
    wallets[str(uid)] = max(0.0, round(bal(uid) - amt, 2))
    _save(WALLETS_FILE, wallets)

# ═══════════════════════════════════════════════════════════
#  DRAW STYLED KHQR TEMPLATE (HD & ROUNDED CORNERS)
# ═══════════════════════════════════════════════════════════
def _generate_styled_khqr_image(qr_str, amount, merchant_name):
    card_w, card_h = 600, 920
    radius = 36

    mask = Image.new("L", (card_w, card_h), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([(0, 0), (card_w, card_h)], radius=radius, fill=255)

    card = Image.new("RGBA", (card_w, card_h), "#FFFFFF")
    draw = ImageDraw.Draw(card)

    header_h = 135
    header_color = "#E11A22"
    draw.rectangle([(0, 0), (card_w, header_h)], fill=header_color)

    font_header, font_name, font_amt, font_curr, font_logo = None, None, None, None, None
    for f_path in ["arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf"]:
        try:
            font_header = ImageFont.truetype(f_path, 42)
            font_name   = ImageFont.truetype(f_path, 28)
            font_amt    = ImageFont.truetype(f_path, 34)
            font_logo   = ImageFont.truetype(f_path, 26)
            break
        except: pass

    for f_path in ["arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans.ttf"]:
        try:
            font_curr = ImageFont.truetype(f_path, 20)
            break
        except: pass

    if not font_header:
        font_header = font_name = font_amt = font_curr = font_logo = ImageFont.load_default()

    draw.text((card_w // 2, header_h // 2), "KHQR", fill="#FFFFFF", font=font_header, anchor="mm")

    margin_x = 45
    draw.text((margin_x, 175), merchant_name, fill="#111111", font=font_name)
    
    amt_str = f"{amount:,.2f}".replace(".", ",")
    draw.text((margin_x, 225), amt_str, fill="#000000", font=font_amt)
    
    try:
        amt_w = font_amt.getbbox(amt_str)[2] - font_amt.getbbox(amt_str)[0]
    except:
        amt_w = len(amt_str) * 20
    draw.text((margin_x + amt_w + 14, 238), "USD", fill="#555555", font=font_curr)

    line_y = 295
    for x in range(margin_x, card_w - margin_x, 18):
        draw.line([(x, line_y), (x + 10, line_y)], fill="#CCCCCC", width=3)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=12,
        border=0
    )
    qr.add_data(qr_str)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#000000", back_color="#FFFFFF").convert("RGBA")

    qr_size = 510
    qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
    qr_top = 345
    card.paste(qr_img, ((card_w - qr_size) // 2, qr_top))

    c_x = card_w // 2
    c_y = qr_top + (qr_size // 2)
    r_outer = 35
    r_inner = 30
    draw.ellipse([(c_x - r_outer, c_y - r_outer), (c_x + r_outer, c_y + r_outer)], fill="#FFFFFF")
    draw.ellipse([(c_x - r_inner, c_y - r_inner), (c_x + r_inner, c_y + r_inner)], fill="#000000")
    draw.text((c_x, c_y), "$", fill="#FFFFFF", font=font_logo, anchor="mm")

    final_card = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    final_card.paste(card, (0, 0), mask=mask)

    buf = io.BytesIO()
    final_card.save(buf, format="PNG")
    buf.seek(0)
    return buf

# ═══════════════════════════════════════════════════════════
#  BAKONG KHQR & COUNTDOWN
# ═══════════════════════════════════════════════════════════
def _generate_khqr(uid, amount, note=""):
    try:
        from bakong_khqr import KHQR
        k = KHQR(BAKONG_TOKEN)
        return k.create_qr(
            bank_account=BANK_ACCOUNT, merchant_name=MERCHANT_NAME,
            merchant_city=MERCHANT_CITY, amount=round(float(amount), 2),
            currency="USD", bill_number=(note or f"uid{uid}")[:25], static=False
        ) or ""
    except Exception as e:
        logger.error(f"[_generate_khqr] Error: {e}")
        return ""

def _check_bakong(md5, amount, start_ts):
    try:
        from bakong_khqr import KHQR as _BK
        return _BK(BAKONG_TOKEN).check_payment(str(md5)) == "PAID"
    except Exception: return False

def _build_caption(amount, remaining_sec):
    mins = max(0, remaining_sec // 60)
    secs = max(0, remaining_sec % 60)
    timer_text = f"{mins:02d}:{secs:02d}"
    return (
        f"💳 <b>ដាក់ប្រាក់ (Top Up)</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 ចំនួន: <b>${amount:.2f}</b>\n"
        f"⏱ ផុតកំណត់ក្នុងរយ: <b>{timer_text} នាទី</b> ⏳\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📱 Scan ជាមួយ Bakong / ABA / Wing"
    )

def _watch_deposit_and_countdown(uid, uid_str, dep_id, amount, msg_id, start_ts):
    deadline = start_ts + DEPOSIT_EXPIRE_SEC
    last_edit_time = 0

    while time.time() < deadline:
        now = time.time()
        remaining = int(deadline - now)

        dep = store_deps.get(dep_id)
        if not dep or dep.get("status") != "pending":
            return
        
        md5 = dep.get("md5", "")
        if _check_bakong(md5, amount, start_ts):
            add_bal(uid, round(amount, 2))
            store_deps[dep_id]["status"] = "confirmed"
            _save(STORE_DEP_FILE, store_deps)
            try:
                bot.edit_message_caption(
                    chat_id=uid, message_id=msg_id,
                    caption=f"✅ <b>ការទូទាត់ទទួលបានជោគជ័យ!</b>\n💰 ចំនួន: +${amount:.2f}"
                )
                bot.send_message(uid, f"✅ <b>ដាក់លុយបានជោគជ័យ!</b>\n💰 +${amount:.2f}\n💳 សរុប: <b>${bal(uid):.2f}</b>", reply_markup=user_kb())
                bot.send_message(ADMIN_ID, f"💰 <b>Auto KHQR</b>\n👤 <code>{uid_str}</code> | +${amount:.2f}")
            except: pass
            return

        if now - last_edit_time >= 10 and msg_id:
            try:
                bot.edit_message_caption(
                    chat_id=uid, message_id=msg_id,
                    caption=_build_caption(amount, remaining)
                )
                last_edit_time = now
            except: pass

        time.sleep(POLL_INTERVAL)

    dep = store_deps.get(dep_id)
    if dep and dep.get("status") == "pending":
        dep["status"] = "expired"
        _save(STORE_DEP_FILE, store_deps)
        try:
            bot.edit_message_caption(
                chat_id=uid, message_id=msg_id,
                caption=f"❌ <b>QR ផុតកំណត់ហើយ (Expired)!</b>\nសូមធ្វើការស្នើសុំដាក់ប្រាក់ម្ដងទៀត។"
            )
            bot.send_message(uid, "⏰ <b>QR ផុតកំណត់!</b> សូមព្យាយាមម្ដងទៀត។")
        except: pass

def _send_deposit_qr(uid, amount):
    uid_str = str(uid)
    qr_str = _generate_khqr(uid, amount, f"uid={uid} ${amount}")
    if not qr_str:
        bot.send_message(uid, "⚠️ មានបញ្ហាបង្កើត QR! សូមទាក់ទង Admin"); return

    try:
        from bakong_khqr import KHQR as _BK
        md5_hash = _BK(BAKONG_TOKEN).generate_md5(qr_str)
    except Exception:
        import hashlib
        md5_hash = hashlib.md5(qr_str.encode()).hexdigest()

    dep_id = f"dep_{uid}_{int(time.time())}"
    store_deps[dep_id] = {"uid": uid_str, "amount": amount, "status": "pending", "md5": md5_hash, "qr_str": qr_str}
    _save(STORE_DEP_FILE, store_deps)

    initial_cap = _build_caption(amount, DEPOSIT_EXPIRE_SEC)

    admin_kb_dep = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ បញ្ចូលលុយឱ្យ", callback_data=f"manual_dep:approve:{dep_id}"),
         InlineKeyboardButton("❌ បដិសេធ", callback_data=f"manual_dep:reject:{dep_id}")]
    ])
    try: bot.send_message(ADMIN_ID, f"📥 <b>ការស្នើដាក់លុយ!</b>\n👤 <code>{uid_str}</code> | 💰 <b>${amount:.2f}</b>", reply_markup=admin_kb_dep)
    except: pass

    sent_msg = None
    try:
        buf = _generate_styled_khqr_image(qr_str, amount, MERCHANT_NAME)
        sent_msg = bot.send_photo(uid, buf, caption=initial_cap)
    except Exception as e:
        logger.error(f"Styled QR generation failed: {e}")
        try:
            qr = qrcode.QRCode(box_size=6, border=2)
            qr.add_data(qr_str); qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
            sent_msg = bot.send_photo(uid, buf, caption=initial_cap)
        except Exception:
            sent_msg = bot.send_message(uid, initial_cap + f"\n\n<code>{qr_str}</code>")

    msg_id = sent_msg.message_id if sent_msg else None
    threading.Thread(target=_watch_deposit_and_countdown, args=(uid, uid_str, dep_id, amount, msg_id, int(time.time())), daemon=True).start()

# ═══════════════════════════════════════════════════════════
#  KEYBOARDS
# ═══════════════════════════════════════════════════════════
def user_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🌐 សេវាកម្ម SMM", "🎮 Top Up ហ្គេម")
    kb.row("🛒 ទិញ Account", "🔥 ទំនិញបញ្ចុះតម្លៃ (%)")
    kb.row("💳 ដាក់ប្រាក់", "👜 កាបូបលុយ", "💬 ជំនួយ Support")
    return kb

def admin_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("➕ បន្ថែមទំនិញ/សេវាកម្ម", "📦 គ្រប់គ្រងទំនិញ")
    kb.row("💰 កាបូបលុយសរុប", "💸 បន្ថែម/កាត់លុយភ្ញៀវ")
    kb.row("👥 អ្នកប្រើប្រាស់ទាំងអស់", "📢 ផ្សព្វផ្សាយសារ")
    return kb

def cancel_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("✕ Cancel")
    return kb

def deposit_amt_kb():
    amts = [1, 2, 5, 10, 20, 50]
    btns, row = [], []
    for a in amts:
        row.append(InlineKeyboardButton(f"${a}", callback_data=f"dep:{a}"))
        if len(row) == 3:
            btns.append(row); row = []
    if row: btns.append(row)
    btns.append([InlineKeyboardButton("✏️ បញ្ចូលចំនួនផ្ទាល់ខ្លួន", callback_data="dep:custom")])
    return InlineKeyboardMarkup(btns)

# ═══════════════════════════════════════════════════════════
#  START
# ═══════════════════════════════════════════════════════════
@bot.message_handler(commands=["start"])
def cmd_start(message):
    uid = message.chat.id
    waiting.pop(uid, None)
    users_db[str(uid)] = {
        "name": message.from_user.first_name or "",
        "username": message.from_user.username or "",
        "last": int(time.time())
    }
    _save(USERS_FILE, users_db)
    wallets.setdefault(str(uid), 0.0)

    welcome_text = (
        f"👋 សួស្ដី <b>{message.from_user.first_name}</b>!\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🌟 ស្វាគមន៍មកកាន់ប្រព័ន្ធ AIO Store (SMM, Top Up & Account)\n"
        f"💰 សាច់ប្រាក់ក្នុងកាបូប: <b>${bal(uid):.2f}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💡 <i>សូមជ្រើសរើសសេវាកម្មខាងក្រោមតាមតម្រូវការរបស់អ្នក!</i>"
    )
    bot.send_message(uid, welcome_text, reply_markup=admin_kb() if uid == ADMIN_ID else user_kb())

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
            bot.send_message(uid, "✏️ <b>សូមផ្ញើចំនួន $ ដែលចង់ដាក់:</b>", reply_markup=cancel_kb())
            return
        _send_deposit_qr(uid, float(val))

    elif data.startswith("manual_dep:"):
        if uid != ADMIN_ID: return
        _, act, dep_id = data.split(":")
        dep = store_deps.get(dep_id)
        if not dep:
            bot.answer_callback_query(call.id, "❌ សំណើមិនមាន!", show_alert=True); return
        target_uid = int(dep["uid"])
        amt = float(dep["amount"])
        if act == "approve":
            if dep.get("status") == "confirmed":
                bot.answer_callback_query(call.id, "⚠️ បានដាក់រួចហើយ!", show_alert=True); return
            add_bal(target_uid, amt)
            dep["status"] = "confirmed"
            _save(STORE_DEP_FILE, store_deps)
            bot.answer_callback_query(call.id, "✅ បានបញ្ចូលលុយជូនរួចរាល់")
            try: bot.send_message(target_uid, f"✅ <b>Admin បានបញ្ចូលលុយជូន:</b> +${amt:.2f}\n💳 សរុប: <b>${bal(target_uid):.2f}</b>")
            except: pass
        elif act == "reject":
            dep["status"] = "rejected"
            _save(STORE_DEP_FILE, store_deps)
            bot.answer_callback_query(call.id, "❌ បានបដិសេធ")
            try: bot.send_message(target_uid, "❌ សំណើដាក់ប្រាក់របស់អ្នកត្រូវបានបដិសេធ។")
            except: pass

    elif data.startswith("add_type:"):
        if uid != ADMIN_ID: return
        t_type = data.split(":")[1]
        bot.answer_callback_query(call.id)
        waiting[uid] = {"step": "item_title", "category": t_type}
        bot.edit_message_text(
            f"📝 <b>ប្រភេទ: {t_type.upper()}</b>\n\nសូមវាយបញ្ចូល <b>ឈ្មោះទំនិញ ឬសេវាកម្ម</b>:",
            chat_id=uid, message_id=call.message.message_id
        )

    elif data.startswith("buy_item:"):
        item_id = data.split(":")[1]
        found_item = None
        for cat, items in store_db.items():
            if item_id in items:
                found_item = items[item_id]
                break
        
        if not found_item:
            bot.answer_callback_query(call.id, "❌ រកមិនឃើញទំនិញនេះទេ!", show_alert=True); return
        
        price = float(found_item.get("final_price", found_item.get("price", 0)))
        if bal(uid) < price:
            bot.answer_callback_query(call.id, "❌ សាច់ប្រាក់មិនគ្រប់គ្រាន់ទេ!", show_alert=True)
            bot.send_message(uid, f"❌ <b>សាច់ប្រាក់មិនគ្រប់គ្រាន់!</b>\n💰 តម្លៃ: <b>${price:.2f}</b>\n💳 កាបូបរបស់អ្នក: <b>${bal(uid):.2f}</b>", reply_markup=deposit_amt_kb())
            return
        
        ded_bal(uid, price)
        bot.answer_callback_query(call.id, f"✅ ទិញជោគជ័យ -${price:.2f}")
        bot.send_message(
            uid,
            f"✅ <b>ទិញទំនិញ/សេវាកម្មជោគជ័យ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📦 ឈ្មោះ: <b>{found_item['title']}</b>\n"
            f"💰 ចំនួនប្រាក់កាត់: <b>${price:.2f}</b>\n"
            f"💳 សល់ប្រាក់ក្នុងកាបូប: <b>${bal(uid):.2f}</b>\n\n"
            f"💬 <i>សំណើរបស់អ្នកត្រូវបានបញ្ជូនទៅកាន់ Admin ដើម្បីដំណើរការជូនជាបន្ទាន់!</i>",
            reply_markup=user_kb()
        )
        try:
            bot.send_message(ADMIN_ID, f"🛒 <b>មានការបញ្ជាទិញថ្មី!</b>\n👤 User ID: <code>{uid}</code>\n📦 មុខទំនិញ: {found_item['title']}\n💰 តម្លៃ: ${price:.2f}")
        except: pass

    elif data.startswith("del_item:"):
        if uid != ADMIN_ID: return
        item_id = data.split(":")[1]
        deleted = False
        for cat in store_db:
            if item_id in store_db[cat]:
                del store_db[cat][item_id]
                deleted = True
        if deleted:
            _save_store(store_db)
            bot.answer_callback_query(call.id, "✅ បានលុបទំនិញរួចរាល់")
            try: bot.edit_message_text("🗑️ បានលុបទំនិញដោយជោគជ័យ!", chat_id=uid, message_id=call.message.message_id)
            except: pass

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
        bot.send_message(uid, "🏠 បោះបង់សកម្មភាព ត្រឡប់មក Menu ដើមវិញ", reply_markup=admin_kb() if uid == ADMIN_ID else user_kb())
        return

    # ─── ដំណើរការ Admin បន្ថែមទំនិញ ───
    if isinstance(step, dict) and step.get("step") == "item_title":
        step["title"] = text
        step["step"] = "item_price"
        bot.send_message(uid, f"💰 ទំនិញ: <b>{text}</b>\n\nសូមបញ្ចូល <b>តម្លៃដើម (USD)</b> (ឧទាហរណ៍: <code>5.00</code>):", reply_markup=cancel_kb())
        return

    elif isinstance(step, dict) and step.get("step") == "item_price":
        try:
            price = float(text.replace("$", ""))
            step["price"] = price
            step["step"] = "item_discount"
            bot.send_message(uid, "🏷️ សូមបញ្ចូល <b>ភាគរយបញ្ចុះតម្លៃ (%)</b> (ឧទាហរណ៍: បើអត់មានដាក់ <code>0</code>, បើបញ្ចុះ១០ភាគរយដាក់ <code>10</code>):", reply_markup=cancel_kb())
        except:
            bot.send_message(uid, "❌ សូមបញ្ចូលតម្លៃជាលេខឱ្យបានត្រឹមត្រូវ (ឧ: <code>2.50</code>):")
        return

    elif isinstance(step, dict) and step.get("step") == "item_discount":
        try:
            discount = float(text.replace("%", ""))
            cat = step["category"]
            item_id = f"item_{int(time.time())}"
            
            final_price = round(step["price"] * (1 - discount / 100), 2)
            
            store_db.setdefault(cat, {})[item_id] = {
                "title": step["title"],
                "price": step["price"],
                "discount": discount,
                "final_price": final_price,
                "date": int(time.time())
            }
            _save_store(store_db)
            waiting.pop(uid, None)
            
            bot.send_message(
                uid,
                f"✅ <b>បានបន្ថែមទំនិញជោគជ័យ!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"📂 ប្រភេទ: <b>{cat.upper()}</b>\n"
                f"🏷️ ឈ្មោះ: <b>{step['title']}</b>\n"
                f"💵 តម្លៃដើម: <b>${step['price']:.2f}</b>\n"
                f"🏷 បញ្ចុះតម្លៃ: <b>{discount}%</b>\n"
                f"💰 តម្លៃលក់ជាក់ស្តែង: <b>${final_price:.2f}</b>",
                reply_markup=admin_kb()
            )
        except:
            bot.send_message(uid, "❌ សូមបញ្ចូលភាគរយជាលេខត្រឹមត្រូវ (ឧ: <code>15</code>):")
        return

    # ─── ដំណើរការ Admin បន្ថែម/កាត់លុយភ្ញៀវ (+ / - UID Amount) ───
    if step == "admin_bal_action" and uid == ADMIN_ID:
        parts = text.split()
        if len(parts) >= 3:
            action, target_uid, amount_str = parts[0], parts[1], parts[2]
            try:
                amt = float(amount_str)
                if action == "+":
                    add_bal(target_uid, amt)
                    bot.send_message(uid, f"✅ បានបន្ថែមប្រាក់ <b>+${amt:.2f}</b> ទៅកាន់ ID: <code>{target_uid}</code> រួចរាល់។", reply_markup=admin_kb())
                    try: bot.send_message(int(target_uid), f"🎁 <b>Admin បានបញ្ចូលលុយជូនអ្នក:</b> +${amt:.2f}\n💳 សាច់ប្រាក់សរុប: <b>${bal(target_uid):.2f}</b>")
                    except: pass
                elif action == "-":
                    ded_bal(target_uid, amt)
                    bot.send_message(uid, f"✅ បានកាត់ប្រាក់ <b>-${amt:.2f}</b> ពី ID: <code>{target_uid}</code> រួចរាល់។", reply_markup=admin_kb())
                    try: bot.send_message(int(target_uid), f"⚠️ Admin បានកាត់ប្រាក់របស់អ្នក: -${amt:.2f}\n💳 សាច់ប្រាក់នៅសល់: <b>${bal(target_uid):.2f}</b>")
                    except: pass
                waiting.pop(uid, None)
                return
            except Exception as e:
                bot.send_message(uid, f"❌ កំហុសទម្រង់! សូមពិនិត្យមើលឡើងវិញ (Error: {e})")
                return
        else:
            bot.send_message(uid, "❌ ទម្រង់មិនត្រឹមត្រូវ! ឧទាហរណ៍: <code>+ 5915683588 10</code>")
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

    # --- USER STORE MENU (3 ប្រភេទសេវាកម្ម) ---
    if text == "🌐 សេវាកម្ម SMM":
        items = store_db.get("smm", {})
        if not items: bot.send_message(uid, "❌ មិនទាន់មានសេវាកម្ម SMM នៅឡើយទេ។"); return
        _send_store_catalog_msg(uid, "🌐 សេវាកម្ម SMM ទាំងអស់", items)
        return

    if text == "🎮 Top Up ហ្គេម":
        items = store_db.get("game", {})
        if not items: bot.send_message(uid, "❌ មិនទាន់មានសេវាកម្ម Top Up ហ្គេមនៅឡើយទេ។"); return
        _send_store_catalog_msg(uid, "🎮 សេវាកម្ម Top Up ហ្គេម", items)
        return

    if text == "🛒 ទិញ Account":
        items = store_db.get("acc", {})
        if not items: bot.send_message(uid, "❌ មិនទាន់មាន Account ដាក់លក់នៅឡើយទេ។"); return
        _send_store_catalog_msg(uid, "🛒 បញ្ជី Account សម្រាប់លក់", items)
        return

    if text == "🔥 ទំនិញបញ្ចុះតម្លៃ (%)":
        all_discounted = []
        for cat, items in store_db.items():
            for i_id, info in items.items():
                if info.get("discount", 0) > 0:
                    all_discounted.append((i_id, info))
        if not all_discounted:
            bot.send_message(uid, "❌ បច្ចុប្បន្នមិនមានទំនិញបញ្ចុះតម្លៃពិសេសទេ។"); return
        
        btns = []
        for i_id, info in all_discounted:
            label = f"🔥 {info['title']} (-{info['discount']}%) ➔ ${info['final_price']:.2f}"
            btns.append([InlineKeyboardButton(label, callback_data=f"buy_item:{i_id}")])
        bot.send_message(uid, "🔥 <b>បញ្ជីទំនិញនិងសេវាកម្មកំពុងបញ្ចុះតម្លៃពិសេស៖</b>", reply_markup=InlineKeyboardMarkup(btns))
        return

    if text in ("👜 កាបូបលុយ", "👜 Wallet"):
        bot.send_message(uid,
            f"👜 <b>កាបូបលុយរបស់អ្នក</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"👤 ID: <code>{uid}</code>\n💰 សាច់ប្រាក់: <b>${bal(uid):.2f}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n💡 ចុចប៊ូតុង <b>💳 ដាក់ប្រាក់</b> ដើម្បីបញ្ចូលលុយទិញទំនិញ។", reply_markup=user_kb())
        return

    if text in ("💳 ដាក់ប្រាក់", "💳 Top Up"):
        waiting.pop(uid, None)
        bot.send_message(uid, f"💸 <b>បញ្ចូលទឹកប្រាក់</b>\n💳 សាច់ប្រាក់បច្ចុប្បន្ន: <b>${bal(uid):.2f}</b>\n\nសូមជ្រើសរើសចំនួនប្រាក់៖", reply_markup=deposit_amt_kb())
        return

    if text == "💬 ជំនួយ Support":
        bot.send_message(uid, "💬 <b>ទំនាក់ទំនងជំនួយ</b>\n━━━━━━━━━━━━━━━━━━\n📞 Admin: @SmeyLov008")
        return

    # --- ADMIN MENU ---
    if uid == ADMIN_ID:
        if text == "➕ បន្ថែមទំនិញ/សេវាកម្ម":
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🌐 SMM Services", callback_data="add_type:smm")],
                [InlineKeyboardButton("🎮 Top Up Game", callback_data="add_type:game")],
                [InlineKeyboardButton("🛒 Account Store", callback_data="add_type:acc")]
            ])
            bot.send_message(uid, "📦 <b>សូមជ្រើសរើសប្រភេទសេវាកម្ម/ទំនិញដែលចង់បន្ថែម៖</b>", reply_markup=kb)
            return

        if text == "📦 គ្រប់គ្រងទំនិញ":
            has_items = False
            for cat, items in store_db.items():
                if items:
                    has_items = True
                    for i_id, info in items.items():
                        price_str = f"${info.get('final_price', info.get('price', 0)):.2f}"
                        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🗑️ លុបទំនិញនេះ", callback_data=f"del_item:{i_id}")]])
                        bot.send_message(uid, f"📂 [{cat.upper()}] <b>{info['title']}</b>\n💰 តម្លៃ: <b>{price_str}</b> (ลด {info.get('discount', 0)}%)", reply_markup=kb)
            if not has_items:
                bot.send_message(uid, "❌ មិនទាន់មានទំនិញ/សេវាកម្មណាមួយក្នុងប្រព័ន្ធទេ។", reply_markup=admin_kb())
            return

        if text == "💸 បន្ថែម/កាត់លុយភ្ញៀវ":
            waiting[uid] = "admin_bal_action"
            bot.send_message(
                uid,
                "💸 <b>គ្រប់គ្រងទឹកប្រាក់ភ្ញៀវ</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "សូមផ្ញើបញ្ជាមកតាមទម្រង់ខាងក្រោម:\n\n"
                "• បន្ថែមលុយ: <code>+ [UID] [ចំនួនទឹកប្រាក់]</code> (ឧ: <code>+ 5915683588 10</code>)\n"
                "• កាត់លុយ: <code>- [UID] [ចំនួនទឹកប្រាក់]</code> (ឧ: <code>- 5915683588 5</code>)\n\n"
                "<i>ឬចុចប៊ូតុង Cancel ដើម្បីបោះបង់។</i>",
                reply_markup=cancel_kb()
            )
            return

        if text == "👥 អ្នកប្រើប្រាស់ទាំងអស់":
            if not users_db:
                bot.send_message(uid, "❌ មិនទាន់មានអ្នកប្រើប្រាស់ក្នុងប្រព័ន្ធទេ។")
                return
            
            lines = [f"👥 <b>បញ្ជីឈ្មោះអ្នកប្រើប្រាស់សរុប ({len(users_db)} នាក់):</b>\n━━━━━━━━━━━━━━━━━━"]
            count = 1
            for u_id, u_info in users_db.items():
                name = u_info.get("name", "Unknown")
                user_balance = bal(u_id)
                lines.append(f"{count}. 👤 <b>{name}</b>\n    🆔 ID: <code>{u_id}</code>\n    💰 កាបូប: <b>${user_balance:.2f}</b>")
                count += 1
                if len("\n".join(lines)) > 3500:
                    bot.send_message(uid, "\n".join(lines))
                    lines = ["━━━━━━━━━━━━━━━━━━"]
                    
            if len(lines) > 1:
                bot.send_message(uid, "\n".join(lines), reply_markup=admin_kb())
            return

        if text == "💰 កាបូបលុយសរុប":
            lines = ["<b>💰 កាបូបលុយអ្នកប្រើសរុប</b>\n━━━━━━━━━━━━━━━━━━"]
            for u_id, u_info in sorted(users_db.items(), key=lambda x: x[1].get("last",0), reverse=True)[:25]:
                lines.append(f"👤 {u_info.get('name','?')} (<code>{u_id}</code>): <b>${bal(u_id):.2f}</b>")
            bot.send_message(uid, "\n".join(lines)[:4000], reply_markup=admin_kb()); return

        if text == "📢 ផ្សព្វផ្សាយសារ":
            waiting[uid] = "broadcast"
            bot.send_message(uid, "📢 ផ្ញើសារដែលចង់ផ្សាយ:", reply_markup=cancel_kb()); return

        if step == "broadcast":
            waiting.pop(uid, None)
            sent = 0
            for u in users_db.keys():
                try: bot.send_message(int(u), text); sent += 1
                except: pass
            bot.send_message(uid, f"✅ ផ្ញើបាន {sent} នាក់", reply_markup=admin_kb()); return

    bot.send_message(uid, "❓ សូមជ្រើសរើសតាម Menu ខាងក្រោម៖", reply_markup=user_kb())

def _send_store_catalog_msg(uid, title_header, items_dict):
    btns = []
    for i_id, info in items_dict.items():
        disc = info.get("discount", 0)
        if disc > 0:
            label = f"{info['title']} (-{disc}%) ➔ ${info['final_price']:.2f}"
        else:
            label = f"{info['title']} ➔ ${info['price']:.2f}"
        btns.append([InlineKeyboardButton(label, callback_data=f"buy_item:{i_id}")])
    bot.send_message(uid, f"<b>{title_header}</b>\n━━━━━━━━━━━━━━━━━━", reply_markup=InlineKeyboardMarkup(btns))

# ═══════════════════════════════════════════════════════════
#  FLASK RUN
# ═══════════════════════════════════════════════════════════
flask_app = Flask(__name__)
@flask_app.route("/health")
def health(): return jsonify({"status": "running", "type": "AIO Store Bot"})

def run_flask():
    flask_app.run(host="0.0.0.0", port=5055, debug=False, use_reloader=False)

if __name__ == "__main__":
    logger.info("🚀 Bot is running...")
    threading.Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling(timeout=20, long_polling_timeout=15)
