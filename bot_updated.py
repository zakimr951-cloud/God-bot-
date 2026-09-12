import os
import sqlite3
import hashlib
import secrets
import logging
from html import escape
from math import ceil

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.constants import ChatMemberStatus
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

DB_FILE = "bot.db"

ITEMS_PER_PAGE = 6
PASSWORD_ITERATIONS = 200_000

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# ============================================================
# DATABASE
# ============================================================

def get_db():
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = get_db()

    con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            item_type TEXT NOT NULL DEFAULT 'text',
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            user_id INTEGER PRIMARY KEY,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    if OWNER_ID:
        con.execute(
            "INSERT OR IGNORE INTO admins (user_id) VALUES (?)",
            (OWNER_ID,),
        )

    # Migrate older databases that did not have item_type.
    columns = [row["name"] for row in con.execute("PRAGMA table_info(items)").fetchall()]
    if "item_type" not in columns:
        con.execute(
            "ALTER TABLE items ADD COLUMN item_type TEXT NOT NULL DEFAULT 'text'"
        )

    con.commit()
    con.close()


# ============================================================
# PASSWORD SYSTEM
# ============================================================

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)

    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )

    return (
        salt.hex()
        + ":"
        + hashed.hex()
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, hash_hex = stored_hash.split(":")

        salt = bytes.fromhex(salt_hex)

        new_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            PASSWORD_ITERATIONS,
        )

        return secrets.compare_digest(
            new_hash.hex(),
            hash_hex,
        )

    except Exception:
        return False


# ============================================================
# USERS
# ============================================================

def save_user(user):
    con = get_db()

    con.execute(
        """
        INSERT INTO users (user_id, username, first_name)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name
        """,
        (
            user.id,
            user.username or "",
            user.first_name or "",
        ),
    )

    con.commit()
    con.close()


# ============================================================
# ADMIN CHECK
# ============================================================

def is_admin(user_id: int) -> bool:
    con = get_db()

    row = con.execute(
        "SELECT 1 FROM admins WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    con.close()

    return row is not None


# ============================================================
# LICENSE CHECK
# ============================================================

def has_license(user_id: int) -> bool:
    con = get_db()

    row = con.execute(
        "SELECT 1 FROM licenses WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    con.close()

    return row is not None


def get_password_hash(user_id: int):
    con = get_db()

    row = con.execute(
        "SELECT password_hash FROM licenses WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    con.close()

    if not row:
        return None

    return row["password_hash"]


# ============================================================
# KEYBOARDS
# ============================================================

def user_keyboard():
    return ReplyKeyboardMarkup(
        [
            [
                KeyboardButton("🎁 ITEMS"),
                KeyboardButton("ℹ️ ABOUT"),
            ],
        ],
        resize_keyboard=True,
    )


def admin_keyboard():
    return ReplyKeyboardMarkup(
        [
            [
                KeyboardButton("➕ Add Item"),
                KeyboardButton("➖ Remove Item"),
            ],
            [
                KeyboardButton("📋 List Items"),
            ],
            [
                KeyboardButton("➕ Add Channel"),
                KeyboardButton("➖ Remove Channel"),
            ],
            [
                KeyboardButton("📋 List Channels"),
            ],
            [
                KeyboardButton("📢 Broadcast"),
                KeyboardButton("📊 Statistics"),
            ],
            [
                KeyboardButton("👤 Add Admin"),
                KeyboardButton("🗑 Remove Admin"),
            ],
            [
                KeyboardButton("📋 List Admins"),
            ],
            [
                KeyboardButton("🔑 Add License"),
                KeyboardButton("🗑 Remove License"),
            ],
            [
                KeyboardButton("📋 License List"),
            ],
            [
                KeyboardButton("🔄 Change Password"),
            ],
            [
                KeyboardButton("❌ Cancel"),
            ],
        ],
        resize_keyboard=True,
    )


def cancel_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("❌ Cancel")]
        ],
        resize_keyboard=True,
    )


# ============================================================
# WELCOME
# ============================================================

async def send_welcome(update: Update):
    user = update.effective_user
    message = update.effective_message

    text = (
        f"🐣🎀 <b>HELLO MERE KUCHU PUCHU ♡</b>\n\n"
        f"🥰 Swagat Hai Aapka Yaha Par 🧸💞\n\n"
        f"🆔 <b>Your Telegram ID:</b> <code>{user.id}</code>"
    )

    photos = await context_bot.get_user_profile_photos(
        user.id,
        limit=1,
    )

    if photos.total_count > 0:
        file_id = photos.photos[0][-1].file_id

        await message.reply_photo(
            photo=file_id,
            caption=text,
            parse_mode="HTML",
        )
    else:
        await message.reply_text(
            text,
            parse_mode="HTML",
        )


# Global bot reference for PFP helper
context_bot = None


# ============================================================
# CHANNELS
# ============================================================

def get_channels():
    con = get_db()

    rows = con.execute(
        "SELECT * FROM channels ORDER BY id ASC"
    ).fetchall()

    con.close()

    return rows


async def check_channels(user_id: int, bot):
    channels = get_channels()

    if not channels:
        return True

    for channel in channels:
        username = channel["username"]

        try:
            member = await bot.get_chat_member(
                username,
                user_id,
            )

            if member.status in [
                ChatMemberStatus.LEFT,
                ChatMemberStatus.BANNED,
            ]:
                return False

        except Exception:
            return False

    return True


async def send_channel_verification(update: Update):
    channels = get_channels()

    buttons = []

    for channel in channels:
        username = channel["username"]

        clean = username.replace("@", "")

        buttons.append(
            [
                InlineKeyboardButton(
                    f"📢 Join {username}",
                    url=f"https://t.me/{clean}",
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                "✅ VERIFY",
                callback_data="verify",
            )
        ]
    )

    await update.effective_message.reply_text(
        "🔐 <b>CHANNEL VERIFICATION</b>\n\n"
        "Pehle required channel join karo.\n"
        "Join karne ke baad VERIFY press karo.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ============================================================
# LOGIN
# ============================================================

async def ask_login(update: Update, context):
    context.user_data["state"] = "login_password"

    await update.effective_message.reply_text(
        "🔑 <b>PASSWORD LOGIN</b>\n\n"
        "Apna password enter karo.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


# ============================================================
# MAIN MENU
# ============================================================

async def show_main_menu(update: Update):
    await update.effective_message.reply_text(
        "🏠 <b>MAIN MENU</b>\n\n"
        "Neeche se option choose karo.",
        parse_mode="HTML",
        reply_markup=user_keyboard(),
    )


# ============================================================
# ITEMS
# ============================================================

async def show_items(
    update: Update,
    context,
    page=0,
):
    con = get_db()

    total = con.execute(
        "SELECT COUNT(*) AS c FROM items"
    ).fetchone()["c"]

    rows = con.execute(
        """
        SELECT *
        FROM items
        ORDER BY id DESC
        LIMIT ?
        OFFSET ?
        """,
        (
            ITEMS_PER_PAGE,
            page * ITEMS_PER_PAGE,
        ),
    ).fetchall()

    con.close()

    # Store visible keyboard labels -> item ID
    context.user_data["item_buttons"] = {}

    buttons = []

    # ========================================================
    # 6 ITEMS = 3 ROWS × 2 COLUMNS
    # ========================================================

    for i in range(0, len(rows), 2):
        row = []

        for item in rows[i:i + 2]:

            label = f"🎁 {item['name']}"

            # Avoid duplicate keyboard labels
            if label in context.user_data["item_buttons"]:
                label = f"🎁 {item['name']} #{item['id']}"

            context.user_data["item_buttons"][label] = item["id"]

            row.append(
                KeyboardButton(label)
            )

        buttons.append(row)

    # ========================================================
    # PAGE NAVIGATION
    # ========================================================

    navigation = []

    if page > 0:
        navigation.append(
            KeyboardButton("⬅️ PREVIOUS")
        )

    if (page + 1) * ITEMS_PER_PAGE < total:
        navigation.append(
            KeyboardButton("NEXT ➡️")
        )

    if navigation:
        buttons.append(navigation)

    # ========================================================
    # BACK
    # ========================================================

    buttons.append(
        [
            KeyboardButton("🔙 BACK")
        ]
    )

    # ========================================================
    # TEXT
    # ========================================================

    if total == 0:

        text = (
            "🎁 <b>ITEMS</b>\n\n"
            "❌ No items available right now."
        )

    else:

        total_pages = ceil(
            total / ITEMS_PER_PAGE
        )

        text = (
            "🎁 <b>ITEMS</b>\n\n"
            "Select an item below.\n\n"
            f"📄 Page {page + 1}/{total_pages}"
        )

    context.user_data["items_page"] = page

    await update.effective_message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            buttons,
            resize_keyboard=True,
        ),
    )


# ============================================================
# OPEN ITEM
# ============================================================

async def open_item(
    update: Update,
    context,
    item_id: int,
):
    con = get_db()

    item = con.execute(
        "SELECT * FROM items WHERE id = ?",
        (item_id,),
    ).fetchone()

    con.close()

    if not item:
        await update.effective_message.reply_text(
            "❌ Item nahi mila.",
            reply_markup=user_keyboard(),
        )
        return

    item_type = item["item_type"]
    content = item["content"]
    name = item["name"]

    try:
        if item_type == "link":
            await update.effective_message.reply_text(
                f"🎁 <b>{escape(name)}</b>\n\n"
                f"🔗 {escape(content)}",
                parse_mode="HTML",
                reply_markup=user_keyboard(),
            )

        elif item_type == "text":
            await update.effective_message.reply_text(
                f"🎁 <b>{escape(name)}</b>\n\n"
                f"{escape(content)}",
                parse_mode="HTML",
                reply_markup=user_keyboard(),
            )

        else:
            captions = {
                "zip": f"🎁 <b>{escape(name)}</b>\n\n📦 ZIP",
                "file": f"🎁 <b>{escape(name)}</b>\n\n📄 FILE",
                "apk": f"🎁 <b>{escape(name)}</b>\n\n📱 APK",
                "pdf": f"🎁 <b>{escape(name)}</b>\n\n📕 PDF",
            }

            await update.effective_message.reply_document(
                document=content,
                caption=captions.get(
                    item_type,
                    f"🎁 <b>{escape(name)}</b>"
                ),
                parse_mode="HTML",
                reply_markup=user_keyboard(),
            )

    except Exception as e:
        logger.exception("Failed to deliver item %s: %s", item_id, e)
        await update.effective_message.reply_text(
            "❌ Item deliver nahi ho paya.",
            reply_markup=user_keyboard(),
        )


# ============================================================
# ABOUT
# ============================================================

async def show_about(update: Update):
    await update.effective_message.reply_text(
        "ℹ️ <b>ABOUT</b>\n\n"
        "🎁 Items are managed by the admin.\n"
        "🔐 Access is protected by Telegram ID,\n"
        "license and individual password.\n\n"
        "🛡️ Secure • Simple • Fast",
        parse_mode="HTML",
        reply_markup=user_keyboard(),
    )


# ============================================================
# ADMIN PANEL
# ============================================================

async def show_admin_panel(update: Update):
    await update.effective_message.reply_text(
        "🛠️ <b>ADMIN PANEL</b>\n\n"
        "Neeche se option choose karo.",
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


# ============================================================
# START
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user
    save_user(user)

    context.user_data.clear()

    if is_admin(user.id):
        await send_welcome(update)
        await show_admin_panel(update)
        return

    await send_welcome(update)

    if not has_license(user.id):

        await update.effective_message.reply_text(
            "❌ <b>ACCESS DENIED</b>\n\n"
            "Aapke Telegram ID par active license nahi hai.",
            parse_mode="HTML",
        )

        return

    channels_ok = await check_channels(
        user.id,
        update.get_bot(),
    )

    if not channels_ok:

        await send_channel_verification(update)
        return

    await ask_login(
        update,
        context,
    )


# ============================================================
# VERIFY CALLBACK
# ============================================================

async def verify_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    await query.answer()

    user = update.effective_user

    if not has_license(user.id):
        await query.message.reply_text(
            "❌ Aapke account par license nahi hai."
        )
        return

    ok = await check_channels(
        user.id,
        context.bot,
    )

    if not ok:

        await query.message.reply_text(
            "❌ Pehle saare required channels join karo."
        )

        return

    await query.message.reply_text(
        "✅ <b>VERIFICATION SUCCESSFUL</b>",
        parse_mode="HTML",
    )

    await ask_login(
        update,
        context,
    )


# ============================================================
# CANCEL
# ============================================================

async def cancel_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data.clear()

    user = update.effective_user

    if is_admin(user.id):

        await update.effective_message.reply_text(
            "❌ Cancelled.",
            reply_markup=admin_keyboard(),
        )

    else:

        await update.effective_message.reply_text(
            "❌ Cancelled.",
            reply_markup=user_keyboard(),
        )


# ============================================================
# ADMIN: ADD ITEM
# ============================================================

async def admin_add_item_start(update, context):

    context.user_data["state"] = "add_item_name"

    await update.effective_message.reply_text(
        "➕ <b>ADD ITEM</b>\n\n"
        "Step 1/3\n\n"
        "Item Name bhejo.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


async def admin_add_item_name(update, context):

    name = (update.effective_message.text or "").strip()

    if not name:
        return

    context.user_data["new_item_name"] = name
    context.user_data["state"] = "add_item_type"

    await update.effective_message.reply_text(
        "➕ <b>ADD ITEM</b>\n\n"
        "Step 2/3\n\n"
        "Item type select karo:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            [
                [
                    KeyboardButton("📦 ZIP"),
                    KeyboardButton("📄 FILE"),
                ],
                [
                    KeyboardButton("📱 APK"),
                    KeyboardButton("📕 PDF"),
                ],
                [
                    KeyboardButton("🔗 LINK"),
                    KeyboardButton("📝 TEXT"),
                ],
                [
                    KeyboardButton("❌ Cancel"),
                ],
            ],
            resize_keyboard=True,
        ),
    )


async def admin_add_item_type(update, context):

    type_map = {
        "📦 ZIP": "zip",
        "📄 FILE": "file",
        "📱 APK": "apk",
        "📕 PDF": "pdf",
        "🔗 LINK": "link",
        "📝 TEXT": "text",
    }

    item_type = type_map.get((update.effective_message.text or "").strip())

    if not item_type:
        await update.effective_message.reply_text(
            "❌ Upar diye gaye 6 options me se ek select karo."
        )
        return

    context.user_data["new_item_type"] = item_type
    context.user_data["state"] = "add_item_content"

    labels = {
        "zip": "ZIP file",
        "file": "file/document",
        "apk": "APK file",
        "pdf": "PDF file",
        "link": "link",
        "text": "text",
    }

    await update.effective_message.reply_text(
        "➕ <b>ADD ITEM</b>\n\n"
        "Step 3/3\n\n"
        f"Type: <b>{labels[item_type].upper()}</b>\n\n"
        "Ab actual content bhejo.\n"
        "• ZIP / FILE / APK / PDF → file upload karo\n"
        "• LINK → link as text bhejo\n"
        "• TEXT → normal text bhejo",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


async def admin_add_item_content(update, context):

    item_type = context.user_data.get("new_item_type")
    message = update.effective_message

    if item_type in {"zip", "file", "apk", "pdf"}:
        if not message.document:
            await message.reply_text(
                "❌ Is type ke liye file/document upload karo."
            )
            return

        content = message.document.file_id

    elif item_type == "link":
        content = (message.text or "").strip()

        if not content:
            await message.reply_text(
                "❌ Valid link bhejo."
            )
            return

    else:  # text
        content = (message.text or "").strip()

        if not content:
            await message.reply_text(
                "❌ Text bhejo."
            )
            return

    context.user_data["new_item_content"] = content
    context.user_data["state"] = "add_item_save"

    await message.reply_text(
        "➕ <b>ADD ITEM</b>\n\n"
        "Details received.\n\n"
        "💾 SAVE press karein.",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            [
                [
                    KeyboardButton("💾 SAVE ✅")
                ],
                [
                    KeyboardButton("❌ Cancel")
                ],
            ],
            resize_keyboard=True,
        ),
    )


async def admin_add_item_save(update, context):

    name = context.user_data.get("new_item_name")
    item_type = context.user_data.get("new_item_type")
    content = context.user_data.get("new_item_content")

    if not name or not item_type or not content:
        await update.effective_message.reply_text(
            "❌ Item data missing.",
            reply_markup=admin_keyboard(),
        )
        context.user_data.clear()
        return

    con = get_db()

    cur = con.execute(
        "INSERT INTO items (name, item_type, content) VALUES (?, ?, ?)",
        (name, item_type, content),
    )

    item_id = cur.lastrowid

    con.commit()
    con.close()

    context.user_data.clear()

    await update.effective_message.reply_text(
        "✅ <b>ITEM SAVED</b>\n\n"
        f"🎁 {escape(name)}\n"
        f"📂 Type: <b>{escape(item_type.upper())}</b>\n"
        f"🆔 ID: {item_id}",
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN: REMOVE ITEM
# ============================================================

async def admin_remove_item_start(update, context):

    context.user_data["state"] = "remove_item"

    await update.effective_message.reply_text(
        "➖ <b>REMOVE ITEM</b>\n\n"
        "Item ID bhejo.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


async def admin_remove_item(update, context):

    try:
        item_id = int(update.effective_message.text.strip())
    except ValueError:

        await update.effective_message.reply_text(
            "❌ Valid Item ID bhejo."
        )
        return

    con = get_db()

    cur = con.execute(
        "DELETE FROM items WHERE id = ?",
        (item_id,),
    )

    con.commit()
    deleted = cur.rowcount

    con.close()

    context.user_data.clear()

    if deleted:
        msg = f"✅ Item ID {item_id} removed."
    else:
        msg = "❌ Item nahi mila."

    await update.effective_message.reply_text(
        msg,
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN: LIST ITEMS
# ============================================================

async def admin_list_items(update, context):

    con = get_db()

    rows = con.execute(
        "SELECT id, name FROM items ORDER BY id DESC"
    ).fetchall()

    con.close()

    if not rows:

        await update.effective_message.reply_text(
            "📋 <b>LIST ITEMS</b>\n\n"
            "No items found.",
            parse_mode="HTML",
            reply_markup=admin_keyboard(),
        )

        return

    lines = [
        "📋 <b>LIST ITEMS</b>\n"
    ]

    for item in rows:

        lines.append(
            f"🆔 <code>{item['id']}</code> — "
            f"🎁 {escape(item['name'])}"
        )

    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN: ADD CHANNEL
# ============================================================

async def admin_add_channel_start(update, context):

    context.user_data["state"] = "add_channel"

    await update.effective_message.reply_text(
        "➕ <b>ADD CHANNEL</b>\n\n"
        "Channel username bhejo.\n\n"
        "Example:\n"
        "<code>@mychannel</code>",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


async def admin_add_channel(update, context):

    username = update.effective_message.text.strip()

    if not username.startswith("@"):

        await update.effective_message.reply_text(
            "❌ Channel username @ ke saath bhejo.\n"
            "Example: @mychannel"
        )
        return

    con = get_db()

    try:

        con.execute(
            "INSERT INTO channels (username) VALUES (?)",
            (username,),
        )

        con.commit()

        msg = f"✅ Channel added: {username}"

    except sqlite3.IntegrityError:

        msg = "❌ Ye channel already added hai."

    con.close()

    context.user_data.clear()

    await update.effective_message.reply_text(
        msg,
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN: REMOVE CHANNEL
# ============================================================

async def admin_remove_channel_start(update, context):

    context.user_data["state"] = "remove_channel"

    await update.effective_message.reply_text(
        "➖ <b>REMOVE CHANNEL</b>\n\n"
        "Channel username bhejo.\n"
        "Example: @mychannel",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


async def admin_remove_channel(update, context):

    username = update.effective_message.text.strip()

    con = get_db()

    cur = con.execute(
        "DELETE FROM channels WHERE username = ?",
        (username,),
    )

    con.commit()

    deleted = cur.rowcount

    con.close()

    context.user_data.clear()

    if deleted:
        msg = f"✅ Removed: {username}"
    else:
        msg = "❌ Channel nahi mila."

    await update.effective_message.reply_text(
        msg,
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN: LIST CHANNELS
# ============================================================

async def admin_list_channels(update, context):

    rows = get_channels()

    if not rows:

        await update.effective_message.reply_text(
            "📋 <b>LIST CHANNELS</b>\n\n"
            "No channels added.",
            parse_mode="HTML",
            reply_markup=admin_keyboard(),
        )

        return

    lines = [
        "📋 <b>LIST CHANNELS</b>\n"
    ]

    for row in rows:

        lines.append(
            f"🆔 {row['id']} — {escape(row['username'])}"
        )

    await update.effective_message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN: STATISTICS
# ============================================================

async def admin_statistics(update, context):

    con = get_db()

    users = con.execute(
        "SELECT COUNT(*) AS c FROM users"
    ).fetchone()["c"]

    items = con.execute(
        "SELECT COUNT(*) AS c FROM items"
    ).fetchone()["c"]

    channels = con.execute(
        "SELECT COUNT(*) AS c FROM channels"
    ).fetchone()["c"]

    admins = con.execute(
        "SELECT COUNT(*) AS c FROM admins"
    ).fetchone()["c"]

    licenses = con.execute(
        "SELECT COUNT(*) AS c FROM licenses"
    ).fetchone()["c"]

    con.close()

    text = (
        "📊 <b>STATISTICS</b>\n\n"
        f"👥 Users: <b>{users}</b>\n"
        f"🎁 Items: <b>{items}</b>\n"
        f"📢 Channels: <b>{channels}</b>\n"
        f"🛠️ Admins: <b>{admins}</b>\n"
        f"🔑 Licenses: <b>{licenses}</b>"
    )

    await update.effective_message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN: ADD ADMIN
# ============================================================

async def admin_add_admin_start(update, context):

    context.user_data["state"] = "add_admin"

    await update.effective_message.reply_text(
        "👤 <b>ADD ADMIN</b>\n\n"
        "New admin ka Telegram ID bhejo.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


async def admin_add_admin(update, context):

    try:
        user_id = int(update.effective_message.text.strip())
    except ValueError:

        await update.effective_message.reply_text(
            "❌ Valid Telegram ID bhejo."
        )
        return

    con = get_db()

    con.execute(
        "INSERT OR IGNORE INTO admins (user_id) VALUES (?)",
        (user_id,),
    )

    con.commit()
    con.close()

    context.user_data.clear()

    await update.effective_message.reply_text(
        f"✅ Admin added.\n\n"
        f"🆔 <code>{user_id}</code>",
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN: REMOVE ADMIN
# ============================================================

async def admin_remove_admin_start(update, context):

    context.user_data["state"] = "remove_admin"

    await update.effective_message.reply_text(
        "🗑 <b>REMOVE ADMIN</b>\n\n"
        "Admin Telegram ID bhejo.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


async def admin_remove_admin(update, context):

    try:
        user_id = int(update.effective_message.text.strip())
    except ValueError:

        await update.effective_message.reply_text(
            "❌ Valid Telegram ID bhejo."
        )
        return

    if user_id == OWNER_ID:

        await update.effective_message.reply_text(
            "❌ Owner ko remove nahi kar sakte."
        )
        return

    con = get_db()

    cur = con.execute(
        "DELETE FROM admins WHERE user_id = ?",
        (user_id,),
    )

    con.commit()

    deleted = cur.rowcount

    con.close()

    context.user_data.clear()

    if deleted:
        msg = "✅ Admin removed."
    else:
        msg = "❌ Admin nahi mila."

    await update.effective_message.reply_text(
        msg,
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN: LIST ADMINS
# ============================================================

async def admin_list_admins(update, context):

    con = get_db()

    rows = con.execute(
        "SELECT user_id FROM admins ORDER BY user_id"
    ).fetchall()

    con.close()

    if not rows:

        text = "📋 <b>LIST ADMINS</b>\n\nNo admins."

    else:

        lines = [
            "📋 <b>LIST ADMINS</b>\n"
        ]

        for row in rows:
            lines.append(
                f"👤 <code>{row['user_id']}</code>"
            )

        text = "\n".join(lines)

    await update.effective_message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN: ADD LICENSE
# ============================================================

async def admin_add_license_start(update, context):

    context.user_data["state"] = "license_user_id"

    await update.effective_message.reply_text(
        "🔑 <b>ADD LICENSE</b>\n\n"
        "Step 1/2\n\n"
        "User Telegram ID bhejo.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


async def admin_license_user_id(update, context):

    try:
        user_id = int(update.effective_message.text.strip())
    except ValueError:

        await update.effective_message.reply_text(
            "❌ Valid Telegram ID bhejo."
        )
        return

    context.user_data["license_user_id"] = user_id
    context.user_data["state"] = "license_password"

    await update.effective_message.reply_text(
        "🔑 <b>ADD LICENSE</b>\n\n"
        "Step 2/2\n\n"
        "Is user ke liye password set karo.\n\n"
        "⚠️ Har user ka password alag hoga.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


async def admin_license_password(update, context):

    password = update.effective_message.text.strip()

    if len(password) < 4:

        await update.effective_message.reply_text(
            "❌ Password minimum 4 characters ka rakho."
        )
        return

    user_id = context.user_data.get(
        "license_user_id"
    )

    if not user_id:

        await update.effective_message.reply_text(
            "❌ User ID missing."
        )
        context.user_data.clear()
        return

    password_hash = hash_password(password)

    con = get_db()

    con.execute(
        """
        INSERT INTO licenses (user_id, password_hash)
        VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET password_hash = excluded.password_hash
        """,
        (
            user_id,
            password_hash,
        ),
    )

    con.commit()
    con.close()

    context.user_data.clear()

    await update.effective_message.reply_text(
        "✅ <b>LICENSE ADDED / UPDATED</b>\n\n"
        f"🆔 User ID: <code>{user_id}</code>\n"
        "🔑 Individual password set successfully.",
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN: REMOVE LICENSE
# ============================================================

async def admin_remove_license_start(update, context):

    context.user_data["state"] = "remove_license"

    await update.effective_message.reply_text(
        "🗑 <b>REMOVE LICENSE</b>\n\n"
        "User Telegram ID bhejo.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


async def admin_remove_license(update, context):

    try:
        user_id = int(update.effective_message.text.strip())
    except ValueError:

        await update.effective_message.reply_text(
            "❌ Valid Telegram ID bhejo."
        )
        return

    con = get_db()

    cur = con.execute(
        "DELETE FROM licenses WHERE user_id = ?",
        (user_id,),
    )

    con.commit()

    deleted = cur.rowcount

    con.close()

    context.user_data.clear()

    if deleted:
        msg = "✅ License removed."
    else:
        msg = "❌ License nahi mila."

    await update.effective_message.reply_text(
        msg,
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN: LICENSE LIST
# ============================================================

async def admin_license_list(update, context):

    con = get_db()

    rows = con.execute(
        "SELECT user_id, created_at FROM licenses ORDER BY user_id"
    ).fetchall()

    con.close()

    if not rows:

        text = (
            "📋 <b>LICENSE LIST</b>\n\n"
            "No active licenses."
        )

    else:

        lines = [
            "📋 <b>LICENSE LIST</b>\n"
        ]

        for row in rows:

            lines.append(
                f"🆔 <code>{row['user_id']}</code>"
            )

        text = "\n".join(lines)

    await update.effective_message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN: CHANGE PASSWORD
# ============================================================

async def admin_change_password_start(update, context):

    context.user_data["state"] = "change_password_user"

    await update.effective_message.reply_text(
        "🔄 <b>CHANGE PASSWORD</b>\n\n"
        "User Telegram ID bhejo.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


async def admin_change_password_user(update, context):

    try:
        user_id = int(update.effective_message.text.strip())
    except ValueError:

        await update.effective_message.reply_text(
            "❌ Valid Telegram ID bhejo."
        )
        return

    if not has_license(user_id):

        await update.effective_message.reply_text(
            "❌ Is user ki license nahi hai."
        )
        return

    context.user_data["change_password_user"] = user_id
    context.user_data["state"] = "change_password_new"

    await update.effective_message.reply_text(
        "🔑 New password bhejo.",
        reply_markup=cancel_keyboard(),
    )


async def admin_change_password_new(update, context):

    password = update.effective_message.text.strip()

    if len(password) < 4:

        await update.effective_message.reply_text(
            "❌ Password minimum 4 characters ka hona chahiye."
        )
        return

    user_id = context.user_data.get(
        "change_password_user"
    )

    password_hash = hash_password(password)

    con = get_db()

    con.execute(
        """
        UPDATE licenses
        SET password_hash = ?
        WHERE user_id = ?
        """,
        (
            password_hash,
            user_id,
        ),
    )

    con.commit()
    con.close()

    context.user_data.clear()

    await update.effective_message.reply_text(
        "✅ Password changed successfully.",
        reply_markup=admin_keyboard(),
    )


# ============================================================
# BROADCAST
# ============================================================

async def admin_broadcast_start(update, context):

    context.user_data["state"] = "broadcast"

    await update.effective_message.reply_text(
        "📢 <b>BROADCAST</b>\n\n"
        "Ab jo message bhejoge woh users ko broadcast hoga.\n\n"
        "Text, photo, video, document etc. bhej sakte ho.\n\n"
        "Cancel ke liye ❌ Cancel.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


async def do_broadcast(update, context):

    con = get_db()

    rows = con.execute(
        "SELECT user_id FROM users"
    ).fetchall()

    con.close()

    sent = 0
    failed = 0

    for row in rows:

        user_id = row["user_id"]

        try:

            await update.effective_message.copy(
                chat_id=user_id
            )

            sent += 1

        except Exception as e:

            logger.warning(
                "Broadcast failed for %s: %s",
                user_id,
                e,
            )

            failed += 1

    context.user_data.clear()

    await update.effective_message.reply_text(
        "📢 <b>BROADCAST COMPLETED</b>\n\n"
        f"✅ Sent: {sent}\n"
        f"❌ Failed: {failed}",
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN TEXT BUTTONS
# ============================================================

async def handle_admin_button(
    update,
    context,
    text,
):

    if text == "➕ Add Item":

        await admin_add_item_start(
            update,
            context,
        )
        return True

    if text == "➖ Remove Item":

        await admin_remove_item_start(
            update,
            context,
        )
        return True

    if text == "📋 List Items":

        await admin_list_items(
            update,
            context,
        )
        return True

    if text == "➕ Add Channel":

        await admin_add_channel_start(
            update,
            context,
        )
        return True

    if text == "➖ Remove Channel":

        await admin_remove_channel_start(
            update,
            context,
        )
        return True

    if text == "📋 List Channels":

        await admin_list_channels(
            update,
            context,
        )
        return True

    if text == "📢 Broadcast":

        await admin_broadcast_start(
            update,
            context,
        )
        return True

    if text == "📊 Statistics":

        await admin_statistics(
            update,
            context,
        )
        return True

    if text == "👤 Add Admin":

        await admin_add_admin_start(
            update,
            context,
        )
        return True

    if text == "🗑 Remove Admin":

        await admin_remove_admin_start(
            update,
            context,
        )
        return True

    if text == "📋 List Admins":

        await admin_list_admins(
            update,
            context,
        )
        return True

    if text == "🔑 Add License":

        await admin_add_license_start(
            update,
            context,
        )
        return True

    if text == "🗑 Remove License":

        await admin_remove_license_start(
            update,
            context,
        )
        return True

    if text == "📋 License List":

        await admin_license_list(
            update,
            context,
        )
        return True

    if text == "🔄 Change Password":

        await admin_change_password_start(
            update,
            context,
        )
        return True

    return False


# ============================================================
# MAIN TEXT HANDLER
# ============================================================

async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user = update.effective_user
    message = update.effective_message
    text = message.text or ""

    save_user(user)

    # ========================================================
    # CANCEL
    # ========================================================

    if text == "❌ Cancel":

        await cancel_action(
            update,
            context,
        )

        return

    # ========================================================
    # BROADCAST
    # ========================================================

    state = context.user_data.get("state")

    if state == "broadcast":

        await do_broadcast(
            update,
            context,
        )

        return

    # ========================================================
    # ADMIN
    # ========================================================

    if is_admin(user.id):

        # Active admin states first
        if state == "add_item_name":

            await admin_add_item_name(
                update,
                context,
            )
            return

        if state == "add_item_type":

            await admin_add_item_type(
                update,
                context,
            )
            return

        if state == "add_item_content":

            await admin_add_item_content(
                update,
                context,
            )
            return

        if state == "add_item_save":

            if text == "💾 SAVE ✅":

                await admin_add_item_save(
                    update,
                    context,
                )

            else:

                await message.reply_text(
                    "💾 SAVE ✅ button press karo."
                )

            return

        if state == "remove_item":

            await admin_remove_item(
                update,
                context,
            )
            return

        if state == "add_channel":

            await admin_add_channel(
                update,
                context,
            )
            return

        if state == "remove_channel":

            await admin_remove_channel(
                update,
                context,
            )
            return

        if state == "add_admin":

            await admin_add_admin(
                update,
                context,
            )
            return

        if state == "remove_admin":

            await admin_remove_admin(
                update,
                context,
            )
            return

        if state == "license_user_id":

            await admin_license_user_id(
                update,
                context,
            )
            return

        if state == "license_password":

            await admin_license_password(
                update,
                context,
            )
            return

        if state == "remove_license":

            await admin_remove_license(
                update,
                context,
            )
            return

        if state == "change_password_user":

            await admin_change_password_user(
                update,
                context,
            )
            return

        if state == "change_password_new":

            await admin_change_password_new(
                update,
                context,
            )
            return

        # Admin buttons
        if await handle_admin_button(
            update,
            context,
            text,
        ):

            return

    # ========================================================
    # USER LOGIN
    # ========================================================

    if state == "login_password":

        stored_hash = get_password_hash(
            user.id
        )

        if not stored_hash:

            await message.reply_text(
                "❌ License nahi mili."
            )

            context.user_data.clear()
            return

        if verify_password(
            text,
            stored_hash,
        ):

            context.user_data["logged_in"] = True
            context.user_data["state"] = None

            await message.reply_text(
                "✅ <b>LOGIN SUCCESSFUL</b>\n\n"
                "Welcome! 🎀",
                parse_mode="HTML",
                reply_markup=user_keyboard(),
            )

        else:

            await message.reply_text(
                "❌ Wrong password.\n\n"
                "Dobara password enter karo.",
                reply_markup=cancel_keyboard(),
            )

        return

    # ========================================================
    # USER MUST BE LOGGED IN
    # ========================================================

    if not context.user_data.get("logged_in"):

        if has_license(user.id):

            await message.reply_text(
                "🔐 Pehle login karo.\n"
                "Password enter karo."
            )

            context.user_data["state"] = "login_password"

        else:

            await message.reply_text(
                "❌ Aapke account par active license nahi hai."
            )

        return

    # ========================================================
    # USER ITEMS
    # ========================================================

    if text == "🎁 ITEMS":

        await show_items(
            update,
            context,
            0,
        )

        return

    # ========================================================
    # NEXT PAGE
    # ========================================================

    if text == "NEXT ➡️":

        current_page = context.user_data.get(
            "items_page",
            0,
        )

        await show_items(
            update,
            context,
            current_page + 1,
        )

        return

    # ========================================================
    # PREVIOUS PAGE
    # ========================================================

    if text == "⬅️ PREVIOUS":

        current_page = context.user_data.get(
            "items_page",
            0,
        )

        await show_items(
            update,
            context,
            max(0, current_page - 1),
        )

        return

    # ========================================================
    # BACK
    # ========================================================

    if text == "🔙 BACK":

        await show_main_menu(
            update,
        )

        return

    # ========================================================
    # ABOUT
    # ========================================================

    if text == "ℹ️ ABOUT":

        await show_about(
            update,
        )

        return

    # ========================================================
    # ITEM BUTTON
    # ========================================================

    item_buttons = context.user_data.get(
        "item_buttons",
        {},
    )

    if text in item_buttons:

        item_id = item_buttons[text]

        await open_item(
            update,
            context,
            item_id,
        )

        return

    # ========================================================
    # DEFAULT
    # ========================================================

    await message.reply_text(
        "❓ Option samajh nahi aaya.",
        reply_markup=user_keyboard(),
    )


# ============================================================
# MEDIA HANDLER
# ============================================================

async def media_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user = update.effective_user

    if not user:
        return

    save_user(user)

    # Broadcast
    if (
        is_admin(user.id)
        and context.user_data.get("state") == "broadcast"
    ):

        await do_broadcast(
            update,
            context,
        )

        return

    # Admin: file-based item content (ZIP / FILE / APK / PDF)
    if (
        is_admin(user.id)
        and context.user_data.get("state") == "add_item_content"
        and context.user_data.get("new_item_type") in {"zip", "file", "apk", "pdf"}
    ):

        await admin_add_item_content(
            update,
            context,
        )

        return

    await update.effective_message.reply_text(
        "❌ Is type ka message yahan allowed nahi hai."
    )


# ============================================================
# ADMIN COMMAND
# ============================================================

async def admin_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user = update.effective_user

    if not is_admin(user.id):

        await update.effective_message.reply_text(
            "❌ Admin access denied."
        )

        return

    context.user_data.clear()

    await show_admin_panel(
        update,
    )


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(
    update,
    context,
):

    logger.exception(
        "Unhandled exception:",
        exc_info=context.error,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    global context_bot

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN environment variable missing."
        )

    if not OWNER_ID:

        raise RuntimeError(
            "OWNER_ID environment variable missing."
        )

    init_db()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    context_bot = application.bot

    # Commands
    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        CommandHandler(
            "admin",
            admin_command,
        )
    )

    # Verify
    application.add_handler(
        CallbackQueryHandler(
            verify_callback,
            pattern=r"^verify$",
        )
    )

    # Text
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler,
        )
    )

    # Photos/videos/documents/etc.
    application.add_handler(
        MessageHandler(
            (
                filters.PHOTO
                | filters.VIDEO
                | filters.Document.ALL
                | filters.AUDIO
                | filters.VOICE
                | filters.ANIMATION
            )
            & ~filters.COMMAND,
            media_handler,
        )
    )

    application.add_error_handler(
        error_handler
    )

    print("BOT STARTED...")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
