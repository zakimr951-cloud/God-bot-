# ============================================================
# TELEGRAM REWARD BOT
# PART 1 / FINAL BUILD
# ============================================================

import os
import sqlite3
import logging
import secrets
import string
import html
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
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

DB_FILE = os.getenv("DB_FILE", "bot_data.db")

ITEMS_PER_PAGE = 6


# ============================================================
# WELCOME MESSAGE
# ============================================================

WELCOME_MESSAGE = (
    "🐣🎀𝐇ᴇ𝐋ʟᴏ 𝐌ᴇʀᴇ 𝐊ᴜᴄʜᴜ 𝐏ᴜᴄʜᴜ ♡🎀🥰\n"
    "𝐒ᴡᴀɢᴀᴛ 𝐇ᴀɪ 𝐀ᴘᴋᴀ 𝐘ᴀʜᴀ 𝐏ᴀʀ🧸💞"
)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# ============================================================
# DATABASE
# ============================================================

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    # Users
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            first_name TEXT DEFAULT '',
            password TEXT DEFAULT '',
            verified INTEGER DEFAULT 0,
            created_at TEXT DEFAULT ''
        )
    """)

    # Reward / Item table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT ''
        )
    """)

    # Required channels
    cur.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT NOT NULL,
            channel_name TEXT DEFAULT '',
            invite_link TEXT DEFAULT '',
            created_at TEXT DEFAULT ''
        )
    """)

    # Admins
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            added_at TEXT DEFAULT ''
        )
    """)

    # Licenses
    cur.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT ''
        )
    """)

    # Settings
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            setting_name TEXT PRIMARY KEY,
            setting_value TEXT DEFAULT ''
        )
    """)

    # Delivery logs
    cur.execute("""
        CREATE TABLE IF NOT EXISTS item_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            delivered_at TEXT DEFAULT ''
        )
    """)

    conn.commit()
    conn.close()


# ============================================================
# USER DATABASE FUNCTIONS
# ============================================================

def save_user(user):
    conn = get_db()
    cur = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cur.execute("""
        INSERT INTO users (
            user_id,
            username,
            first_name,
            created_at
        )
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name
    """, (
        user.id,
        user.username or "",
        user.first_name or "",
        now,
    ))

    conn.commit()
    conn.close()


def get_user(user_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,)
    )

    row = cur.fetchone()
    conn.close()

    return row


def set_user_password(user_id, password):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET password = ?
        WHERE user_id = ?
    """, (
        password,
        user_id,
    ))

    conn.commit()
    conn.close()


def set_user_verified(user_id, verified=True):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET verified = ?
        WHERE user_id = ?
    """, (
        1 if verified else 0,
        user_id,
    ))

    conn.commit()
    conn.close()


# ============================================================
# ADMIN FUNCTIONS
# ============================================================

def is_admin(user_id):
    if user_id == OWNER_ID:
        return True

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT user_id FROM admins WHERE user_id = ?",
        (user_id,)
    )

    result = cur.fetchone()
    conn.close()

    return result is not None


def add_admin_db(user_id, username=""):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO admins (
            user_id,
            username,
            added_at
        )
        VALUES (?, ?, ?)
    """, (
        user_id,
        username,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ))

    conn.commit()
    conn.close()


def remove_admin_db(user_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM admins WHERE user_id = ?",
        (user_id,)
    )

    conn.commit()
    conn.close()


# ============================================================
# PASSWORD GENERATOR
# ============================================================

def generate_password(length=8):
    characters = string.ascii_letters + string.digits

    return "".join(
        secrets.choice(characters)
        for _ in range(length)
    )


# ============================================================
# USER SIDE KEYBOARD
# ============================================================

def user_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(
                "🎁 Rewards",
                callback_data="user_rewards"
            ),
        ],
        [
            InlineKeyboardButton(
                "👤 My Details",
                callback_data="user_details"
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# ============================================================
# ADMIN PANEL KEYBOARD
# ============================================================

def admin_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(
                "🛠 Admin Panel",
                callback_data="admin_panel"
            ),
        ],
        [
            InlineKeyboardButton(
                "➕ Add Item",
                callback_data="admin_add_item"
            ),
            InlineKeyboardButton(
                "➖ Remove Item",
                callback_data="admin_remove_item"
            ),
        ],
        [
            InlineKeyboardButton(
                "📋 List Items",
                callback_data="admin_list_items"
            ),
        ],
        [
            InlineKeyboardButton(
                "➕ Add Channel",
                callback_data="admin_add_channel"
            ),
            InlineKeyboardButton(
                "➖ Remove Channel",
                callback_data="admin_remove_channel"
            ),
        ],
        [
            InlineKeyboardButton(
                "📋 List Channels",
                callback_data="admin_list_channels"
            ),
        ],
        [
            InlineKeyboardButton(
                "📢 Broadcast",
                callback_data="admin_broadcast"
            ),
            InlineKeyboardButton(
                "📊 Statistics",
                callback_data="admin_stats"
            ),
        ],
        [
            InlineKeyboardButton(
                "👤 Add Admin",
                callback_data="admin_add_admin"
            ),
            InlineKeyboardButton(
                "🗑 Remove Admin",
                callback_data="admin_remove_admin"
            ),
        ],
        [
            InlineKeyboardButton(
                "📋 List Admins",
                callback_data="admin_list_admins"
            ),
        ],
        [
            InlineKeyboardButton(
                "🔑 Add License",
                callback_data="admin_add_license"
            ),
            InlineKeyboardButton(
                "🗑 Remove License",
                callback_data="admin_remove_license"
            ),
        ],
        [
            InlineKeyboardButton(
                "📋 License List",
                callback_data="admin_license_list"
            ),
        ],
        [
            InlineKeyboardButton(
                "🔄 Change Password",
                callback_data="admin_change_password"
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# ============================================================
# COMMON BACK BUTTON
# ============================================================

def back_button(callback_data="back_main"):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data=callback_data
            )
        ]
    ])


# ============================================================
# START COMMAND
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not user:
        return

    save_user(user)

    # Owner/Admin gets admin panel directly.
    if is_admin(user.id):
        await update.message.reply_text(
            WELCOME_MESSAGE,
            reply_markup=admin_keyboard()
        )
        return

    # Normal user flow will continue in Part 2.
    await update.message.reply_text(
        WELCOME_MESSAGE
    )


# ============================================================
# ADMIN COMMAND
# ============================================================

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not user:
        return

    if not is_admin(user.id):
        await update.message.reply_text(
            "❌ You are not authorized to use the admin panel."
        )
        return

    await update.message.reply_text(
        "🛠 <b>Admin Panel</b>\n\nChoose an option:",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


# ============================================================
# CANCEL COMMAND
# ============================================================

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    user = update.effective_user

    if user and is_admin(user.id):
        await update.message.reply_text(
            "❌ Current operation cancelled.",
            reply_markup=admin_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ Current operation cancelled."
        )


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception(
        "Unhandled exception:",
        exc_info=context.error
    )


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

init_db()


# ============================================================
# PART 1 ENDS HERE
# ============================================================
# ============================================================
# PART 2 — REQUIRED CHANNEL SYSTEM
# ============================================================

def get_channels():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM channels
        ORDER BY id ASC
    """)

    rows = cur.fetchall()
    conn.close()

    return rows


def get_channel(channel_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM channels
        WHERE id = ?
    """, (channel_id,))

    row = cur.fetchone()
    conn.close()

    return row


def add_channel_db(channel_id, channel_name, invite_link):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO channels (
            channel_id,
            channel_name,
            invite_link,
            created_at
        )
        VALUES (?, ?, ?, ?)
    """, (
        str(channel_id),
        channel_name,
        invite_link,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ))

    conn.commit()
    conn.close()


def remove_channel_db(channel_db_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM channels WHERE id = ?",
        (channel_db_id,)
    )

    conn.commit()
    conn.close()


# ============================================================
# CHANNEL JOIN KEYBOARD
# ============================================================

def channel_join_keyboard(channels):
    keyboard = []

    for channel in channels:
        name = channel["channel_name"] or "Join Channel"
        link = channel["invite_link"]

        if link:
            keyboard.append([
                InlineKeyboardButton(
                    f"📢 {name}",
                    url=link
                )
            ])

    keyboard.append([
        InlineKeyboardButton(
            "✅ Verify",
            callback_data="verify_channels"
        )
    ])

    return InlineKeyboardMarkup(keyboard)


# ============================================================
# CHECK CHANNEL MEMBERSHIP
# ============================================================

async def check_channel_membership(bot, user_id, channel_id):
    try:
        member = await bot.get_chat_member(
            chat_id=channel_id,
            user_id=user_id
        )

        allowed_statuses = {
            "member",
            "administrator",
            "creator"
        }

        return member.status in allowed_statuses

    except Exception as e:
        logger.warning(
            "Channel membership check failed for "
            "user %s, channel %s: %s",
            user_id,
            channel_id,
            e
        )

        return False


async def check_all_channels(bot, user_id):
    channels = get_channels()

    if not channels:
        return True

    for channel in channels:
        joined = await check_channel_membership(
            bot,
            user_id,
            channel["channel_id"]
        )

        if not joined:
            return False

    return True


# ============================================================
# SHOW REQUIRED CHANNELS
# ============================================================

async def show_required_channels(
    message,
    channels,
    edit=False
):
    text = (
        "🔐 <b>Verification Required</b>\n\n"
        "Bot use karne ke liye pehle neeche diye gaye "
        "saare channels join karo.\n\n"
        "Join karne ke baad <b>✅ Verify</b> dabao."
    )

    markup = channel_join_keyboard(channels)

    if edit:
        try:
            await message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=markup
            )
        except Exception:
            await message.reply_text(
                text,
                parse_mode="HTML",
                reply_markup=markup
            )
    else:
        await message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=markup
        )


# ============================================================
# VERIFY CHANNELS CALLBACK
# ============================================================

async def verify_channels_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user:
        return

    save_user(user)

    channels = get_channels()

    # No required channels
    if not channels:
        set_user_verified(user.id, True)

        context.user_data["channel_verified"] = True

        await query.message.edit_text(
            WELCOME_MESSAGE,
            reply_markup=user_keyboard()
        )

        return

    all_joined = await check_all_channels(
        context.bot,
        user.id
    )

    if not all_joined:
        await query.answer(
            "❌ Pehle saare required channels join karo!",
            show_alert=True
        )

        await show_required_channels(
            query.message,
            channels,
            edit=True
        )

        return

    # Verification successful
    set_user_verified(user.id, True)

    context.user_data["channel_verified"] = True

    # Password system will be connected in Part 3.
    await query.message.edit_text(
        WELCOME_MESSAGE,
        reply_markup=user_keyboard()
    )


# ============================================================
# ADMIN — ADD CHANNEL START
# ============================================================

async def admin_add_channel_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user or not is_admin(user.id):
        return

    context.user_data["admin_action"] = "add_channel"
    context.user_data["channel_step"] = "id"

    await query.message.reply_text(
        "➕ <b>Add Required Channel</b>\n\n"
        "Step 1/3\n"
        "Channel ID bhejo.\n\n"
        "Example:\n"
        "<code>-1001234567890</code>\n\n"
        "❌ Cancel ke liye /cancel",
        parse_mode="HTML"
    )


# ============================================================
# ADMIN — ADD CHANNEL MESSAGE HANDLER
# ============================================================

async def process_add_channel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user

    if not user or not is_admin(user.id):
        return False

    if context.user_data.get("admin_action") != "add_channel":
        return False

    text = (update.message.text or "").strip()

    step = context.user_data.get("channel_step")

    # --------------------------------------------------------
    # STEP 1 — CHANNEL ID
    # --------------------------------------------------------

    if step == "id":
        if not text:
            await update.message.reply_text(
                "❌ Valid Channel ID bhejo."
            )
            return True

        context.user_data["new_channel_id"] = text
        context.user_data["channel_step"] = "name"

        await update.message.reply_text(
            "Step 2/3\n\n"
            "Channel ka display name bhejo.\n\n"
            "Example:\n"
            "My Channel"
        )

        return True

    # --------------------------------------------------------
    # STEP 2 — CHANNEL NAME
    # --------------------------------------------------------

    if step == "name":
        if not text:
            await update.message.reply_text(
                "❌ Channel name empty nahi ho sakta."
            )
            return True

        context.user_data["new_channel_name"] = text
        context.user_data["channel_step"] = "link"

        await update.message.reply_text(
            "Step 3/3\n\n"
            "Channel ka invite/link bhejo.\n\n"
            "Example:\n"
            "https://t.me/example"
        )

        return True

    # --------------------------------------------------------
    # STEP 3 — INVITE LINK
    # --------------------------------------------------------

    if step == "link":
        if not (
            text.startswith("https://t.me/")
            or text.startswith("http://t.me/")
            or text.startswith("https://telegram.me/")
            or text.startswith("http://telegram.me/")
        ):
            await update.message.reply_text(
                "❌ Valid Telegram link bhejo.\n\n"
                "Example:\n"
                "https://t.me/example"
            )
            return True

        channel_id = context.user_data.get(
            "new_channel_id",
            ""
        )

        channel_name = context.user_data.get(
            "new_channel_name",
            ""
        )

        add_channel_db(
            channel_id,
            channel_name,
            text
        )

        context.user_data.pop("admin_action", None)
        context.user_data.pop("channel_step", None)
        context.user_data.pop("new_channel_id", None)
        context.user_data.pop("new_channel_name", None)

        await update.message.reply_text(
            "✅ <b>Channel Added Successfully!</b>\n\n"
            f"📢 Name: <b>{html.escape(channel_name)}</b>\n"
            f"🆔 ID: <code>{html.escape(channel_id)}</code>\n"
            f"🔗 Link: {html.escape(text)}",
            parse_mode="HTML",
            reply_markup=admin_keyboard()
        )

        return True

    return False


# ============================================================
# ADMIN — REMOVE CHANNEL
# ============================================================

async def admin_remove_channel_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user or not is_admin(user.id):
        return

    channels = get_channels()

    if not channels:
        await query.message.reply_text(
            "📭 Abhi koi required channel add nahi hai.",
            reply_markup=admin_keyboard()
        )
        return

    keyboard = []

    for channel in channels:
        name = channel["channel_name"] or "Unnamed Channel"

        keyboard.append([
            InlineKeyboardButton(
                f"🗑 {name}",
                callback_data=f"remove_channel:{channel['id']}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 Back",
            callback_data="admin_panel"
        )
    ])

    await query.message.reply_text(
        "🗑 <b>Remove Channel</b>\n\n"
        "Jis channel ko remove karna hai us par tap karo:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ============================================================
# REMOVE CHANNEL CALLBACK
# ============================================================

async def remove_channel_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user or not is_admin(user.id):
        return

    try:
        channel_db_id = int(
            query.data.split(":", 1)[1]
        )
    except (ValueError, IndexError):
        await query.message.reply_text(
            "❌ Invalid channel."
        )
        return

    channel = get_channel(channel_db_id)

    if not channel:
        await query.message.reply_text(
            "❌ Channel not found."
        )
        return

    remove_channel_db(channel_db_id)

    await query.message.reply_text(
        "✅ Channel successfully removed.",
        reply_markup=admin_keyboard()
    )


# ============================================================
# ADMIN — LIST CHANNELS
# ============================================================

async def admin_list_channels(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user or not is_admin(user.id):
        return

    channels = get_channels()

    if not channels:
        await query.message.reply_text(
            "📭 <b>No Required Channels</b>\n\n"
            "Abhi koi channel configured nahi hai.",
            parse_mode="HTML",
            reply_markup=admin_keyboard()
        )
        return

    lines = [
        "📋 <b>Required Channels</b>",
        ""
    ]

    for index, channel in enumerate(channels, 1):
        name = html.escape(
            channel["channel_name"] or "Unnamed"
        )

        channel_id = html.escape(
            str(channel["channel_id"])
        )

        link = html.escape(
            channel["invite_link"] or "-"
        )

        lines.append(
            f"<b>{index}. {name}</b>\n"
            f"🆔 <code>{channel_id}</code>\n"
            f"🔗 {link}\n"
        )

    await query.message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


# ============================================================
# PART 2 ENDS HERE
# ============================================================
# ============================================================
# PART 3 — PASSWORD + USER ACCESS SYSTEM
# ============================================================

def get_user_password(user_id):
    user = get_user(user_id)

    if not user:
        return ""

    return user["password"] or ""


def has_user_password(user_id):
    password = get_user_password(user_id)
    return bool(password)


def password_is_correct(user_id, password):
    saved_password = get_user_password(user_id)

    if not saved_password:
        return False

    return secrets.compare_digest(
        str(saved_password),
        str(password)
    )


# ============================================================
# USER PASSWORD KEYBOARD
# ============================================================

def password_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔑 Enter Password",
                callback_data="enter_password"
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 Verify Channels Again",
                callback_data="verify_channels"
            )
        ]
    ])


# ============================================================
# ASK USER FOR PASSWORD
# ============================================================

async def ask_user_password(
    message,
    context,
    edit=False
):
    context.user_data["waiting_for_password"] = True
    context.user_data["password_verified"] = False

    text = (
        "🔐 <b>Password Required</b>\n\n"
        "Channel verification successful hai.\n"
        "Ab apna password enter karo."
    )

    if edit:
        try:
            await message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=password_keyboard()
            )
        except Exception:
            await message.reply_text(
                text,
                parse_mode="HTML",
                reply_markup=password_keyboard()
            )
    else:
        await message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=password_keyboard()
        )


# ============================================================
# USER PASSWORD CALLBACK
# ============================================================

async def enter_password_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user:
        return

    save_user(user)

    if not context.user_data.get("channel_verified"):
        channels = get_channels()

        if channels:
            await query.message.reply_text(
                "❌ Pehle channel verification complete karo."
            )

            await show_required_channels(
                query.message,
                channels,
                edit=False
            )

            return

    if not has_user_password(user.id):
        await query.message.reply_text(
            "⚠️ <b>Password abhi set nahi hai.</b>\n\n"
            "Admin se password set karwane ke baad "
            "bot use kar sakte ho.",
            parse_mode="HTML"
        )
        return

    context.user_data["waiting_for_password"] = True
    context.user_data["password_verified"] = False

    await query.message.reply_text(
        "🔑 Apna password send karo.\n\n"
        "❌ Cancel ke liye /cancel"
    )


# ============================================================
# PASSWORD TEXT HANDLER
# ============================================================

async def password_text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user
    message = update.message

    if not user or not message:
        return False

    if not context.user_data.get("waiting_for_password"):
        return False

    password = (message.text or "").strip()

    if not password:
        await message.reply_text(
            "❌ Password empty nahi ho sakta."
        )
        return True

    # Check password
    if not password_is_correct(user.id, password):
        context.user_data["password_verified"] = False

        await message.reply_text(
            "❌ <b>Wrong Password</b>\n\n"
            "Please correct password enter karo.",
            parse_mode="HTML"
        )

        return True

    # Password correct
    context.user_data["waiting_for_password"] = False

    # IMPORTANT:
    # Successful password ke baad user access milta hai.
    context.user_data["password_verified"] = True

    await message.reply_text(
        "✅ <b>Password Verified!</b>\n\n"
        "Welcome! Ab neeche se option choose karo.",
        parse_mode="HTML",
        reply_markup=user_keyboard()
    )

    return True


# ============================================================
# USER ACCESS CHECK
# ============================================================

async def user_has_access(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user

    if not user:
        return False

    # Admin always has access
    if is_admin(user.id):
        return True

    # Channel verification
    if not context.user_data.get("channel_verified"):
        return False

    # Password verification
    if not context.user_data.get("password_verified"):
        return False

    return True


# ============================================================
# REQUIRE USER ACCESS
# ============================================================

async def require_user_access(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user

    if not user:
        return False

    # Admin bypass
    if is_admin(user.id):
        return True

    # Check channels live
    channels = get_channels()

    if channels:
        joined = await check_all_channels(
            context.bot,
            user.id
        )

        if not joined:
            context.user_data["channel_verified"] = False
            context.user_data["password_verified"] = False

            if update.callback_query:
                await update.callback_query.answer(
                    "❌ Required channel join nahi hai.",
                    show_alert=True
                )

                await show_required_channels(
                    update.callback_query.message,
                    channels,
                    edit=True
                )
            else:
                await show_required_channels(
                    update.message,
                    channels,
                    edit=False
                )

            return False

        context.user_data["channel_verified"] = True

    # Password check
    if not context.user_data.get("password_verified"):
        if has_user_password(user.id):
            if update.callback_query:
                await update.callback_query.message.reply_text(
                    "🔐 Password required hai.",
                    reply_markup=password_keyboard()
                )
            else:
                await ask_user_password(
                    update.message,
                    context
                )
        else:
            if update.callback_query:
                await update.callback_query.message.reply_text(
                    "⚠️ Aapka password admin ne abhi set nahi kiya hai."
                )
            else:
                await update.message.reply_text(
                    "⚠️ Aapka password admin ne abhi set nahi kiya hai."
                )

        return False

    return True


# ============================================================
# USER DETAILS
# ============================================================

async def user_details_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user:
        return

    if not await require_user_access(update, context):
        return

    db_user = get_user(user.id)

    username = (
        f"@{html.escape(user.username)}"
        if user.username
        else "Not set"
    )

    first_name = html.escape(
        user.first_name or "Unknown"
    )

    verified_status = (
        "✅ Verified"
        if db_user and db_user["verified"]
        else "❌ Not Verified"
    )

    text = (
        "👤 <b>My Details</b>\n\n"
        f"🆔 User ID: <code>{user.id}</code>\n"
        f"👤 Name: {first_name}\n"
        f"🔗 Username: {username}\n"
        f"🔐 Password: {'Set' if has_user_password(user.id) else 'Not Set'}\n"
        f"✅ Status: {verified_status}"
    )

    await query.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=back_button("user_main")
    )


# ============================================================
# USER MAIN MENU CALLBACK
# ============================================================

async def user_main_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user:
        return

    if not await require_user_access(update, context):
        return

    await query.message.edit_text(
        WELCOME_MESSAGE,
        reply_markup=user_keyboard()
    )


# ============================================================
# REDEFINED VERIFY CALLBACK
# ============================================================
# This version connects channel verification directly
# with the password system.

async def verify_channels_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user:
        return

    save_user(user)

    # Admin bypass
    if is_admin(user.id):
        context.user_data["channel_verified"] = True
        context.user_data["password_verified"] = True

        await query.message.edit_text(
            WELCOME_MESSAGE,
            reply_markup=admin_keyboard()
        )

        return

    channels = get_channels()

    # No channels configured
    if not channels:
        set_user_verified(user.id, True)

        context.user_data["channel_verified"] = True

        if has_user_password(user.id):
            await ask_user_password(
                query.message,
                context,
                edit=True
            )
        else:
            await query.message.edit_text(
                WELCOME_MESSAGE,
                reply_markup=user_keyboard()
            )

        return

    # Check all channels
    all_joined = await check_all_channels(
        context.bot,
        user.id
    )

    if not all_joined:
        context.user_data["channel_verified"] = False
        context.user_data["password_verified"] = False

        await query.answer(
            "❌ Pehle saare channels join karo!",
            show_alert=True
        )

        await show_required_channels(
            query.message,
            channels,
            edit=True
        )

        return

    # Successfully verified
    set_user_verified(user.id, True)

    context.user_data["channel_verified"] = True

    # Password exists → ask password
    if has_user_password(user.id):
        await ask_user_password(
            query.message,
            context,
            edit=True
        )
        return

    # Password not set by admin yet
    context.user_data["password_verified"] = False

    await query.message.edit_text(
        WELCOME_MESSAGE +
        "\n\n⚠️ <b>Password admin ne abhi set nahi kiya hai.</b>",
        parse_mode="HTML"
    )


# ============================================================
# PART 3 ENDS HERE
# ============================================================
# ============================================================
# PART 4 — REWARD / ITEM SYSTEM
# ============================================================


# ============================================================
# ITEM DATABASE FUNCTIONS
# ============================================================

def add_item_db(name, content):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO items (
            name,
            content,
            created_at
        )
        VALUES (?, ?, ?)
    """, (
        name,
        content,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ))

    item_id = cur.lastrowid

    conn.commit()
    conn.close()

    return item_id


def get_items():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM items
        ORDER BY id ASC
    """)

    rows = cur.fetchall()
    conn.close()

    return rows


def get_item(item_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM items
        WHERE id = ?
    """, (item_id,))

    row = cur.fetchone()
    conn.close()

    return row


def remove_item_db(item_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM items WHERE id = ?",
        (item_id,)
    )

    deleted = cur.rowcount > 0

    conn.commit()
    conn.close()

    return deleted


def get_items_page(page):
    offset = page * ITEMS_PER_PAGE

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM items
        ORDER BY id ASC
        LIMIT ? OFFSET ?
    """, (
        ITEMS_PER_PAGE,
        offset,
    ))

    rows = cur.fetchall()
    conn.close()

    return rows


def get_total_items():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS total FROM items")

    row = cur.fetchone()
    conn.close()

    return row["total"]


# ============================================================
# ITEM DELIVERY LOG
# ============================================================

def log_item_delivery(user_id, item_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO item_logs (
            user_id,
            item_id,
            delivered_at
        )
        VALUES (?, ?, ?)
    """, (
        user_id,
        item_id,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ))

    conn.commit()
    conn.close()


# ============================================================
# LAST PAGE / EMPTY REWARD MESSAGE
# ============================================================

REWARD_END_MESSAGE = (
    "🤖 Bot, you want anything?\n\n"
    "DM here:\n"
    "@cozxf / @godxrin"
)


# ============================================================
# BUILD USER REWARD KEYBOARD
# ============================================================

def build_reward_keyboard(page=0):
    items = get_items_page(page)
    total = get_total_items()

    keyboard = []

    # --------------------------------------------------------
    # Reward / Item buttons
    # Exactly 6 items per page
    # --------------------------------------------------------

    for item in items:
        item_name = item["name"]

        keyboard.append([
            InlineKeyboardButton(
                f"🎁 {item_name}",
                callback_data=f"reward_item:{item['id']}"
            )
        ])

    # --------------------------------------------------------
    # Pagination
    # --------------------------------------------------------

    navigation = []

    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                "🔙 Back",
                callback_data=f"reward_page:{page - 1}"
            )
        )

    if (page + 1) * ITEMS_PER_PAGE < total:
        navigation.append(
            InlineKeyboardButton(
                "➡️ Next",
                callback_data=f"reward_page:{page + 1}"
            )
        )

    if navigation:
        keyboard.append(navigation)

    # --------------------------------------------------------
    # Main menu
    # --------------------------------------------------------

    keyboard.append([
        InlineKeyboardButton(
            "🏠 Main Menu",
            callback_data="user_main"
        )
    ])

    return InlineKeyboardMarkup(keyboard)


# ============================================================
# SHOW REWARDS
# ============================================================

async def show_rewards(
    message,
    context,
    page=0,
    edit=False
):
    # Access check
    user = None

    if hasattr(message, "chat"):
        pass

    items = get_items_page(page)
    total = get_total_items()

    # --------------------------------------------------------
    # No rewards available
    # --------------------------------------------------------

    if total == 0:
        text = (
            "🎁 <b>Rewards</b>\n\n"
            "📭 Abhi koi reward available nahi hai.\n\n"
            f"{REWARD_END_MESSAGE}"
        )

        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🏠 Main Menu",
                    callback_data="user_main"
                )
            ]
        ])

        if edit:
            try:
                await message.edit_text(
                    text,
                    parse_mode="HTML",
                    reply_markup=markup
                )
            except Exception:
                await message.reply_text(
                    text,
                    parse_mode="HTML",
                    reply_markup=markup
                )
        else:
            await message.reply_text(
                text,
                parse_mode="HTML",
                reply_markup=markup
            )

        return

    # --------------------------------------------------------
    # Page information
    # --------------------------------------------------------

    total_pages = (
        (total + ITEMS_PER_PAGE - 1)
        // ITEMS_PER_PAGE
    )

    current_page = page + 1

    text = (
        "🎁 <b>Rewards</b>\n\n"
        "Neeche se reward choose karo.\n\n"
        f"📄 Page {current_page}/{total_pages}"
    )

    # Last page → required footer
    if (page + 1) * ITEMS_PER_PAGE >= total:
        text += f"\n\n{REWARD_END_MESSAGE}"

    markup = build_reward_keyboard(page)

    if edit:
        try:
            await message.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=markup
            )
        except Exception:
            await message.reply_text(
                text,
                parse_mode="HTML",
                reply_markup=markup
            )
    else:
        await message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=markup
        )


# ============================================================
# USER — REWARDS BUTTON
# ============================================================

async def user_rewards_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user:
        return

    # Verify access
    if not await require_user_access(
        update,
        context
    ):
        return

    await show_rewards(
        query.message,
        context,
        page=0,
        edit=True
    )


# ============================================================
# USER — REWARD PAGE CALLBACK
# ============================================================

async def reward_page_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user:
        return

    # Verify access again
    if not await require_user_access(
        update,
        context
    ):
        return

    try:
        page = int(
            query.data.split(":", 1)[1]
        )
    except (ValueError, IndexError):
        await query.answer(
            "❌ Invalid page.",
            show_alert=True
        )
        return

    if page < 0:
        page = 0

    total = get_total_items()

    max_page = max(
        0,
        (total - 1) // ITEMS_PER_PAGE
    )

    if page > max_page:
        page = max_page

    await show_rewards(
        query.message,
        context,
        page=page,
        edit=True
    )


# ============================================================
# USER — SELECT REWARD / ITEM
# ============================================================

async def reward_item_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user:
        return

    # Verify access before delivery
    if not await require_user_access(
        update,
        context
    ):
        return

    try:
        item_id = int(
            query.data.split(":", 1)[1]
        )
    except (ValueError, IndexError):
        await query.answer(
            "❌ Invalid reward.",
            show_alert=True
        )
        return

    item = get_item(item_id)

    if not item:
        await query.answer(
            "❌ Ye reward ab available nahi hai.",
            show_alert=True
        )
        return

    item_name = html.escape(
        item["name"]
    )

    content = item["content"]

    # --------------------------------------------------------
    # Deliver stored reward
    # --------------------------------------------------------

    await query.message.reply_text(
        f"🎁 <b>{item_name}</b>\n\n"
        f"{html.escape(content)}",
        parse_mode="HTML"
    )

    # Save delivery log
    log_item_delivery(
        user.id,
        item_id
    )


# ============================================================
# ADMIN — ADD REWARD / ITEM START
# ============================================================

async def admin_add_item_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user or not is_admin(user.id):
        return

    context.user_data["admin_action"] = "add_item"
    context.user_data["item_step"] = "name"

    await query.message.reply_text(
        "➕ <b>Add Reward / Item</b>\n\n"
        "Step 1/2\n\n"
        "Reward ka naam bhejo.\n\n"
        "Example:\n"
        "<code>Flwrs Panel</code>\n\n"
        "❌ Cancel ke liye /cancel",
        parse_mode="HTML"
    )


# ============================================================
# ADMIN — PROCESS ADD REWARD
# ============================================================

async def process_add_item(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user
    message = update.message

    if not user or not message:
        return False

    if not is_admin(user.id):
        return False

    if context.user_data.get("admin_action") != "add_item":
        return False

    text = (message.text or "").strip()

    if not text:
        await message.reply_text(
            "❌ Empty value allowed nahi hai."
        )
        return True

    step = context.user_data.get("item_step")

    # --------------------------------------------------------
    # STEP 1 — REWARD NAME
    # --------------------------------------------------------

    if step == "name":
        context.user_data["new_item_name"] = text
        context.user_data["item_step"] = "content"

        await message.reply_text(
            "Step 2/2\n\n"
            f"🎁 Reward Name: <b>{html.escape(text)}</b>\n\n"
            "Ab jo reward/item user ko dena hai "
            "woh send karo.\n\n"
            "Example:\n"
            "<code>https://example.com/panel</code>\n\n"
            "Ya normal text bhi de sakte ho.",
            parse_mode="HTML"
        )

        return True

    # --------------------------------------------------------
    # STEP 2 — REWARD CONTENT
    # --------------------------------------------------------

    if step == "content":
        name = context.user_data.get(
            "new_item_name",
            ""
        )

        if not name:
            context.user_data.clear()

            await message.reply_text(
                "❌ Item session expired. Dobara try karo.",
                reply_markup=admin_keyboard()
            )

            return True

        item_id = add_item_db(
            name,
            text
        )

        context.user_data.pop(
            "admin_action",
            None
        )
        context.user_data.pop(
            "item_step",
            None
        )
        context.user_data.pop(
            "new_item_name",
            None
        )

        await message.reply_text(
            "✅ <b>Reward Added Successfully!</b>\n\n"
            f"🎁 Name: <b>{html.escape(name)}</b>\n"
            f"🆔 Item ID: <code>{item_id}</code>\n\n"
            "Ab ye reward userside ke "
            "🎁 Rewards section me button ke roop me dikhega.",
            parse_mode="HTML",
            reply_markup=admin_keyboard()
        )

        return True

    return False


# ============================================================
# ADMIN — LIST REWARDS / ITEMS
# ============================================================

async def admin_list_items(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user or not is_admin(user.id):
        return

    items = get_items()

    if not items:
        await query.message.reply_text(
            "📭 <b>No Rewards</b>\n\n"
            "Abhi koi reward/item save nahi hai.",
            parse_mode="HTML",
            reply_markup=admin_keyboard()
        )
        return

    lines = [
        "📋 <b>Saved Rewards / Items</b>",
        ""
    ]

    for index, item in enumerate(items, 1):
        name = html.escape(
            item["name"]
        )

        item_id = item["id"]

        content = item["content"]

        if len(content) > 100:
            content = content[:100] + "..."

        content = html.escape(content)

        lines.append(
            f"<b>{index}. {name}</b>\n"
            f"🆔 ID: <code>{item_id}</code>\n"
            f"📦 {content}\n"
        )

    await query.message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


# ============================================================
# ADMIN — REMOVE REWARD / ITEM START
# ============================================================

async def admin_remove_item_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user or not is_admin(user.id):
        return

    items = get_items()

    if not items:
        await query.message.reply_text(
            "📭 Abhi koi reward/item save nahi hai.",
            reply_markup=admin_keyboard()
        )
        return

    keyboard = []

    for item in items:
        name = item["name"]

        keyboard.append([
            InlineKeyboardButton(
                f"🗑 {name}",
                callback_data=f"remove_item:{item['id']}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 Back",
            callback_data="admin_panel"
        )
    ])

    await query.message.reply_text(
        "🗑 <b>Remove Reward</b>\n\n"
        "Jis reward ko delete karna hai "
        "us par tap karo:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ============================================================
# REMOVE REWARD CALLBACK
# ============================================================

async def remove_item_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user or not is_admin(user.id):
        return

    try:
        item_id = int(
            query.data.split(":", 1)[1]
        )
    except (ValueError, IndexError):
        await query.message.reply_text(
            "❌ Invalid item."
        )
        return

    item = get_item(item_id)

    if not item:
        await query.message.reply_text(
            "❌ Reward not found."
        )
        return

    item_name = item["name"]

    deleted = remove_item_db(item_id)

    if not deleted:
        await query.message.reply_text(
            "❌ Reward delete nahi hua."
        )
        return

    await query.message.reply_text(
        "✅ <b>Reward Removed!</b>\n\n"
        f"🎁 {html.escape(item_name)}",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


# ============================================================
# PART 4 ENDS HERE
# ============================================================
# ============================================================
# PART 5 — ADMIN USER / PASSWORD MANAGEMENT
# ============================================================


# ============================================================
# FIND USER BY ID
# ============================================================

def find_user_by_id(user_id):
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        return None

    return get_user(user_id)


# ============================================================
# ADMIN — CHANGE PASSWORD START
# ============================================================

async def admin_change_password_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user or not is_admin(user.id):
        return

    context.user_data["admin_action"] = "change_user_password"
    context.user_data["password_step"] = "user_id"

    await query.message.reply_text(
        "🔄 <b>Change User Password</b>\n\n"
        "Step 1/2\n\n"
        "Jis user ka password change/set karna hai "
        "uska Telegram User ID bhejo.\n\n"
        "Example:\n"
        "<code>123456789</code>\n\n"
        "❌ Cancel ke liye /cancel",
        parse_mode="HTML"
    )


# ============================================================
# ADMIN — PROCESS PASSWORD CHANGE
# ============================================================

async def process_change_user_password(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user
    message = update.message

    if not user or not message:
        return False

    if not is_admin(user.id):
        return False

    if context.user_data.get("admin_action") != "change_user_password":
        return False

    text = (message.text or "").strip()

    if not text:
        await message.reply_text(
            "❌ Valid value bhejo."
        )
        return True

    step = context.user_data.get(
        "password_step"
    )

    # --------------------------------------------------------
    # STEP 1 — USER ID
    # --------------------------------------------------------

    if step == "user_id":

        try:
            target_user_id = int(text)
        except ValueError:
            await message.reply_text(
                "❌ Invalid User ID.\n\n"
                "Example:\n"
                "123456789"
            )
            return True

        target_user = find_user_by_id(
            target_user_id
        )

        if not target_user:
            await message.reply_text(
                "❌ Ye user bot me registered nahi hai.\n\n"
                "User ko pehle /start karna hoga."
            )
            return True

        context.user_data["password_user_id"] = (
            target_user_id
        )

        context.user_data["password_step"] = (
            "new_password"
        )

        await message.reply_text(
            "Step 2/2\n\n"
            f"👤 User ID: <code>{target_user_id}</code>\n\n"
            "Ab naya password bhejo.\n\n"
            "Example:\n"
            "<code>ABC12345</code>",
            parse_mode="HTML"
        )

        return True

    # --------------------------------------------------------
    # STEP 2 — NEW PASSWORD
    # --------------------------------------------------------

    if step == "new_password":

        new_password = text

        if len(new_password) < 4:
            await message.reply_text(
                "❌ Password kam se kam 4 characters ka hona chahiye."
            )
            return True

        if len(new_password) > 64:
            await message.reply_text(
                "❌ Password maximum 64 characters ka ho sakta hai."
            )
            return True

        target_user_id = context.user_data.get(
            "password_user_id"
        )

        if not target_user_id:
            context.user_data.clear()

            await message.reply_text(
                "❌ Password session expired.",
                reply_markup=admin_keyboard()
            )

            return True

        set_user_password(
            target_user_id,
            new_password
        )

        # Agar admin password change karta hai,
        # target user ki current session ko force
        # nahi kiya ja raha. Next access par new
        # password use hoga.
        context.user_data.pop(
            "admin_action",
            None
        )
        context.user_data.pop(
            "password_step",
            None
        )
        context.user_data.pop(
            "password_user_id",
            None
        )

        await message.reply_text(
            "✅ <b>Password Updated Successfully!</b>\n\n"
            f"👤 User ID: <code>{target_user_id}</code>\n"
            "🔐 New password set ho gaya hai.",
            parse_mode="HTML",
            reply_markup=admin_keyboard()
        )

        return True

    return False


# ============================================================
# ADMIN — ADD ADMIN START
# ============================================================

async def admin_add_admin_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user or not is_admin(user.id):
        return

    context.user_data["admin_action"] = "add_admin"

    await query.message.reply_text(
        "👤 <b>Add Admin</b>\n\n"
        "New admin ka Telegram User ID bhejo.\n\n"
        "Example:\n"
        "<code>123456789</code>\n\n"
        "❌ Cancel ke liye /cancel",
        parse_mode="HTML"
    )


# ============================================================
# ADMIN — PROCESS ADD ADMIN
# ============================================================

async def process_add_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user
    message = update.message

    if not user or not message:
        return False

    if not is_admin(user.id):
        return False

    if context.user_data.get("admin_action") != "add_admin":
        return False

    text = (message.text or "").strip()

    try:
        target_user_id = int(text)
    except ValueError:
        await message.reply_text(
            "❌ Invalid Telegram User ID."
        )
        return True

    if target_user_id == OWNER_ID:
        await message.reply_text(
            "ℹ️ Owner already has full admin access."
        )

        context.user_data.pop(
            "admin_action",
            None
        )

        return True

    target_user = find_user_by_id(
        target_user_id
    )

    username = ""

    if target_user:
        username = target_user["username"] or ""

    add_admin_db(
        target_user_id,
        username
    )

    context.user_data.pop(
        "admin_action",
        None
    )

    await message.reply_text(
        "✅ <b>Admin Added Successfully!</b>\n\n"
        f"🆔 User ID: <code>{target_user_id}</code>",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )

    return True


# ============================================================
# ADMIN — REMOVE ADMIN START
# ============================================================

async def admin_remove_admin_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user or not is_admin(user.id):
        return

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM admins
        ORDER BY user_id ASC
    """)

    admins = cur.fetchall()
    conn.close()

    if not admins:
        await query.message.reply_text(
            "📭 Abhi koi additional admin nahi hai.",
            reply_markup=admin_keyboard()
        )
        return

    keyboard = []

    for admin in admins:
        username = (
            f"@{admin['username']}"
            if admin["username"]
            else str(admin["user_id"])
        )

        keyboard.append([
            InlineKeyboardButton(
                f"🗑 {username}",
                callback_data=f"remove_admin:{admin['user_id']}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 Back",
            callback_data="admin_panel"
        )
    ])

    await query.message.reply_text(
        "🗑 <b>Remove Admin</b>\n\n"
        "Jis admin ko remove karna hai "
        "us par tap karo:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ============================================================
# REMOVE ADMIN CALLBACK
# ============================================================

async def remove_admin_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user or not is_admin(user.id):
        return

    try:
        target_user_id = int(
            query.data.split(":", 1)[1]
        )
    except (ValueError, IndexError):
        await query.message.reply_text(
            "❌ Invalid admin."
        )
        return

    if target_user_id == OWNER_ID:
        await query.answer(
            "❌ Owner ko remove nahi kar sakte.",
            show_alert=True
        )
        return

    remove_admin_db(
        target_user_id
    )

    await query.message.reply_text(
        "✅ Admin successfully removed.\n\n"
        f"🆔 User ID: <code>{target_user_id}</code>",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


# ============================================================
# ADMIN — LIST ADMINS
# ============================================================

async def admin_list_admins(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user or not is_admin(user.id):
        return

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM admins
        ORDER BY user_id ASC
    """)

    admins = cur.fetchall()
    conn.close()

    lines = [
        "📋 <b>Admin List</b>",
        "",
        f"👑 Owner ID: <code>{OWNER_ID}</code>",
        ""
    ]

    if not admins:
        lines.append(
            "📭 No additional admins."
        )
    else:
        for index, admin in enumerate(admins, 1):

            username = (
                f"@{html.escape(admin['username'])}"
                if admin["username"]
                else "No username"
            )

            lines.append(
                f"<b>{index}. {username}</b>\n"
                f"🆔 <code>{admin['user_id']}</code>\n"
            )

    await query.message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


# ============================================================
# ADMIN PANEL CALLBACK
# ============================================================

async def admin_panel_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user or not is_admin(user.id):
        return

    await query.message.edit_text(
        "🛠 <b>Admin Panel</b>\n\n"
        "Choose an option:",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


# ============================================================
# PART 5 ENDS HERE
# ============================================================
# ============================================================
# PART 6 — LICENSE + STATISTICS + BROADCAST
# ============================================================


# ============================================================
# LICENSE DATABASE FUNCTIONS
# ============================================================

def add_license_db(license_key):
    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO licenses (
                license_key,
                status,
                created_at
            )
            VALUES (?, 'active', ?)
        """, (
            license_key,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ))

        conn.commit()
        success = True

    except sqlite3.IntegrityError:
        success = False

    conn.close()

    return success


def get_licenses():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM licenses
        ORDER BY id ASC
    """)

    rows = cur.fetchall()
    conn.close()

    return rows


def get_license(license_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM licenses
        WHERE id = ?
    """, (license_id,))

    row = cur.fetchone()
    conn.close()

    return row


def remove_license_db(license_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM licenses WHERE id = ?",
        (license_id,)
    )

    deleted = cur.rowcount > 0

    conn.commit()
    conn.close()

    return deleted


# ============================================================
# ADMIN — ADD LICENSE START
# ============================================================

async def admin_add_license_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user or not is_admin(user.id):
        return

    context.user_data["admin_action"] = "add_license"

    await query.message.reply_text(
        "🔑 <b>Add License</b>\n\n"
        "License key bhejo.\n\n"
        "Example:\n"
        "<code>VIP-ABC123-2026</code>\n\n"
        "❌ Cancel ke liye /cancel",
        parse_mode="HTML"
    )


# ============================================================
# ADMIN — PROCESS ADD LICENSE
# ============================================================

async def process_add_license(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user
    message = update.message

    if not user or not message:
        return False

    if not is_admin(user.id):
        return False

    if context.user_data.get("admin_action") != "add_license":
        return False

    license_key = (message.text or "").strip()

    if not license_key:
        await message.reply_text(
            "❌ License key empty nahi ho sakti."
        )
        return True

    if len(license_key) > 100:
        await message.reply_text(
            "❌ License key bahut long hai."
        )
        return True

    success = add_license_db(
        license_key
    )

    context.user_data.pop(
        "admin_action",
        None
    )

    if not success:
        await message.reply_text(
            "❌ Ye license key already exist karti hai.",
            reply_markup=admin_keyboard()
        )
        return True

    await message.reply_text(
        "✅ <b>License Added Successfully!</b>\n\n"
        f"🔑 Key: <code>{html.escape(license_key)}</code>",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )

    return True


# ============================================================
# ADMIN — REMOVE LICENSE START
# ============================================================

async def admin_remove_license_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user or not is_admin(user.id):
        return

    licenses = get_licenses()

    if not licenses:
        await query.message.reply_text(
            "📭 Abhi koi license available nahi hai.",
            reply_markup=admin_keyboard()
        )
        return

    keyboard = []

    for license_row in licenses:
        key = license_row["license_key"]

        if len(key) > 25:
            display_key = key[:25] + "..."
        else:
            display_key = key

        keyboard.append([
            InlineKeyboardButton(
                f"🗑 {display_key}",
                callback_data=f"remove_license:{license_row['id']}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            "🔙 Back",
            callback_data="admin_panel"
        )
    ])

    await query.message.reply_text(
        "🗑 <b>Remove License</b>\n\n"
        "Jis license ko remove karna hai "
        "us par tap karo:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ============================================================
# REMOVE LICENSE CALLBACK
# ============================================================

async def remove_license_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user or not is_admin(user.id):
        return

    try:
        license_id = int(
            query.data.split(":", 1)[1]
        )
    except (ValueError, IndexError):
        await query.message.reply_text(
            "❌ Invalid license."
        )
        return

    license_row = get_license(
        license_id
    )

    if not license_row:
        await query.message.reply_text(
            "❌ License not found."
        )
        return

    license_key = license_row["license_key"]

    remove_license_db(
        license_id
    )

    await query.message.reply_text(
        "✅ <b>License Removed!</b>\n\n"
        f"🔑 <code>{html.escape(license_key)}</code>",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


# ============================================================
# ADMIN — LICENSE LIST
# ============================================================

async def admin_license_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user or not is_admin(user.id):
        return

    licenses = get_licenses()

    if not licenses:
        await query.message.reply_text(
            "📭 <b>No Licenses</b>\n\n"
            "Abhi koi license saved nahi hai.",
            parse_mode="HTML",
            reply_markup=admin_keyboard()
        )
        return

    lines = [
        "📋 <b>License List</b>",
        ""
    ]

    for index, license_row in enumerate(licenses, 1):

        key = html.escape(
            license_row["license_key"]
        )

        status = html.escape(
            license_row["status"]
        )

        lines.append(
            f"<b>{index}. {key}</b>\n"
            f"🆔 ID: <code>{license_row['id']}</code>\n"
            f"📌 Status: {status}\n"
        )

    await query.message.reply_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


# ============================================================
# STATISTICS
# ============================================================

def get_statistics():
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) AS total FROM users"
    )
    total_users = cur.fetchone()["total"]

    cur.execute(
        "SELECT COUNT(*) AS total FROM users WHERE verified = 1"
    )
    verified_users = cur.fetchone()["total"]

    cur.execute(
        "SELECT COUNT(*) AS total FROM items"
    )
    total_items = cur.fetchone()["total"]

    cur.execute(
        "SELECT COUNT(*) AS total FROM channels"
    )
    total_channels = cur.fetchone()["total"]

    cur.execute(
        "SELECT COUNT(*) AS total FROM admins"
    )
    total_admins = cur.fetchone()["total"]

    cur.execute(
        "SELECT COUNT(*) AS total FROM licenses"
    )
    total_licenses = cur.fetchone()["total"]

    cur.execute(
        "SELECT COUNT(*) AS total FROM item_logs"
    )
    total_deliveries = cur.fetchone()["total"]

    conn.close()

    return {
        "users": total_users,
        "verified": verified_users,
        "items": total_items,
        "channels": total_channels,
        "admins": total_admins,
        "licenses": total_licenses,
        "deliveries": total_deliveries,
    }


# ============================================================
# ADMIN — STATISTICS
# ============================================================

async def admin_stats(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user or not is_admin(user.id):
        return

    stats = get_statistics()

    text = (
        "📊 <b>Bot Statistics</b>\n\n"
        f"👥 Total Users: <b>{stats['users']}</b>\n"
        f"✅ Verified Users: <b>{stats['verified']}</b>\n"
        f"🎁 Total Rewards: <b>{stats['items']}</b>\n"
        f"📢 Required Channels: <b>{stats['channels']}</b>\n"
        f"👤 Additional Admins: <b>{stats['admins']}</b>\n"
        f"🔑 Licenses: <b>{stats['licenses']}</b>\n"
        f"📦 Reward Deliveries: <b>{stats['deliveries']}</b>"
    )

    await query.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


# ============================================================
# BROADCAST START
# ============================================================

async def admin_broadcast_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    await query.answer()

    user = update.effective_user

    if not user or not is_admin(user.id):
        return

    context.user_data["admin_action"] = "broadcast"

    await query.message.reply_text(
        "📢 <b>Broadcast</b>\n\n"
        "Ab jo message sab users ko bhejna hai "
        "woh send karo.\n\n"
        "⚠️ Currently text broadcast supported hai.\n\n"
        "❌ Cancel ke liye /cancel",
        parse_mode="HTML"
    )


# ============================================================
# BROADCAST USERS
# ============================================================

def get_all_user_ids():
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT user_id FROM users ORDER BY user_id ASC"
    )

    rows = cur.fetchall()
    conn.close()

    return [
        row["user_id"]
        for row in rows
    ]


# ============================================================
# PROCESS BROADCAST
# ============================================================

async def process_broadcast(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user
    message = update.message

    if not user or not message:
        return False

    if not is_admin(user.id):
        return False

    if context.user_data.get("admin_action") != "broadcast":
        return False

    broadcast_text = (
        message.text or ""
    ).strip()

    if not broadcast_text:
        await message.reply_text(
            "❌ Broadcast message empty nahi ho sakta."
        )
        return True

    context.user_data.pop(
        "admin_action",
        None
    )

    user_ids = get_all_user_ids()

    if not user_ids:
        await message.reply_text(
            "📭 Abhi koi registered user nahi hai.",
            reply_markup=admin_keyboard()
        )
        return True

    sent = 0
    failed = 0

    await message.reply_text(
        "📢 Broadcast started...\n\n"
        f"👥 Users: {len(user_ids)}"
    )

    for user_id in user_ids:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=broadcast_text
            )

            sent += 1

        except Exception as e:
            failed += 1

            logger.warning(
                "Broadcast failed for %s: %s",
                user_id,
                e
            )

    await message.reply_text(
        "✅ <b>Broadcast Completed!</b>\n\n"
        f"📨 Sent: <b>{sent}</b>\n"
        f"❌ Failed: <b>{failed}</b>",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )

    return True


# ============================================================
# PART 6 ENDS HERE
# ============================================================
# ============================================================
# PART 7 — CALLBACK ROUTER + MESSAGE ROUTER
# ============================================================


# ============================================================
# CALLBACK QUERY ROUTER
# ============================================================

async def callback_router(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    if not query:
        return

    data = query.data or ""

    # --------------------------------------------------------
    # USER SIDE
    # --------------------------------------------------------

    if data == "user_rewards":
        await user_rewards_callback(
            update,
            context
        )
        return

    if data == "user_details":
        await user_details_callback(
            update,
            context
        )
        return

    if data == "user_main":
        await user_main_callback(
            update,
            context
        )
        return

    if data == "enter_password":
        await enter_password_callback(
            update,
            context
        )
        return

    if data == "verify_channels":
        await verify_channels_callback(
            update,
            context
        )
        return

    # --------------------------------------------------------
    # REWARD PAGINATION
    # --------------------------------------------------------

    if data.startswith("reward_page:"):
        await reward_page_callback(
            update,
            context
        )
        return

    # --------------------------------------------------------
    # REWARD ITEM DELIVERY
    # --------------------------------------------------------

    if data.startswith("reward_item:"):
        await reward_item_callback(
            update,
            context
        )
        return

    # --------------------------------------------------------
    # ADMIN PANEL
    # --------------------------------------------------------

    if data == "admin_panel":
        await admin_panel_callback(
            update,
            context
        )
        return

    # --------------------------------------------------------
    # ADMIN — ITEMS / REWARDS
    # --------------------------------------------------------

    if data == "admin_add_item":
        await admin_add_item_start(
            update,
            context
        )
        return

    if data == "admin_remove_item":
        await admin_remove_item_start(
            update,
            context
        )
        return

    if data == "admin_list_items":
        await admin_list_items(
            update,
            context
        )
        return

    if data.startswith("remove_item:"):
        await remove_item_callback(
            update,
            context
        )
        return

    # --------------------------------------------------------
    # ADMIN — CHANNELS
    # --------------------------------------------------------

    if data == "admin_add_channel":
        await admin_add_channel_start(
            update,
            context
        )
        return

    if data == "admin_remove_channel":
        await admin_remove_channel_start(
            update,
            context
        )
        return

    if data == "admin_list_channels":
        await admin_list_channels(
            update,
            context
        )
        return

    if data.startswith("remove_channel:"):
        await remove_channel_callback(
            update,
            context
        )
        return

    # --------------------------------------------------------
    # ADMIN — BROADCAST
    # --------------------------------------------------------

    if data == "admin_broadcast":
        await admin_broadcast_start(
            update,
            context
        )
        return

    # --------------------------------------------------------
    # ADMIN — STATISTICS
    # --------------------------------------------------------

    if data == "admin_stats":
        await admin_stats(
            update,
            context
        )
        return

    # --------------------------------------------------------
    # ADMIN — ADMINS
    # --------------------------------------------------------

    if data == "admin_add_admin":
        await admin_add_admin_start(
            update,
            context
        )
        return

    if data == "admin_remove_admin":
        await admin_remove_admin_start(
            update,
            context
        )
        return

    if data == "admin_list_admins":
        await admin_list_admins(
            update,
            context
        )
        return

    if data.startswith("remove_admin:"):
        await remove_admin_callback(
            update,
            context
        )
        return

    # --------------------------------------------------------
    # ADMIN — LICENSES
    # --------------------------------------------------------

    if data == "admin_add_license":
        await admin_add_license_start(
            update,
            context
        )
        return

    if data == "admin_remove_license":
        await admin_remove_license_start(
            update,
            context
        )
        return

    if data == "admin_license_list":
        await admin_license_list(
            update,
            context
        )
        return

    if data.startswith("remove_license:"):
        await remove_license_callback(
            update,
            context
        )
        return

    # --------------------------------------------------------
    # UNKNOWN CALLBACK
    # --------------------------------------------------------

    await query.answer(
        "❌ Unknown option.",
        show_alert=True
    )


# ============================================================
# ADMIN ACTION MESSAGE ROUTER
# ============================================================

async def admin_action_router(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user
    message = update.message

    if not user or not message:
        return False

    if not is_admin(user.id):
        return False

    action = context.user_data.get(
        "admin_action"
    )

    # --------------------------------------------------------
    # ADD ITEM
    # --------------------------------------------------------

    if action == "add_item":
        return await process_add_item(
            update,
            context
        )

    # --------------------------------------------------------
    # ADD CHANNEL
    # --------------------------------------------------------

    if action == "add_channel":
        return await process_add_channel(
            update,
            context
        )

    # --------------------------------------------------------
    # ADD ADMIN
    # --------------------------------------------------------

    if action == "add_admin":
        return await process_add_admin(
            update,
            context
        )

    # --------------------------------------------------------
    # CHANGE USER PASSWORD
    # --------------------------------------------------------

    if action == "change_user_password":
        return await process_change_user_password(
            update,
            context
        )

    # --------------------------------------------------------
    # ADD LICENSE
    # --------------------------------------------------------

    if action == "add_license":
        return await process_add_license(
            update,
            context
        )

    # --------------------------------------------------------
    # BROADCAST
    # --------------------------------------------------------

    if action == "broadcast":
        return await process_broadcast(
            update,
            context
        )

    return False


# ============================================================
# TEXT MESSAGE ROUTER
# ============================================================

async def text_message_router(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user
    message = update.message

    if not user or not message:
        return

    save_user(user)

    # --------------------------------------------------------
    # CANCEL
    # --------------------------------------------------------

    if (message.text or "").strip().lower() == "/cancel":
        await cancel_command(
            update,
            context
        )
        return

    # --------------------------------------------------------
    # ADMIN ACTIONS
    # --------------------------------------------------------

    if is_admin(user.id):
        handled = await admin_action_router(
            update,
            context
        )

        if handled:
            return

    # --------------------------------------------------------
    # USER PASSWORD
    # --------------------------------------------------------

    handled = await password_text_handler(
        update,
        context
    )

    if handled:
        return

    # --------------------------------------------------------
    # NORMAL USER TEXT
    # --------------------------------------------------------

    await message.reply_text(
        "👇 Please use the buttons.",
        reply_markup=(
            admin_keyboard()
            if is_admin(user.id)
            else user_keyboard()
        )
    )


# ============================================================
# PART 7 ENDS HERE
# ============================================================
# ============================================================
# PART 8 — HANDLERS + MAIN
# ============================================================


# ============================================================
# APPLICATION SETUP
# ============================================================

def build_application():
    if not BOT_TOKEN:
        raise ValueError(
            "BOT_TOKEN is not set. "
            "Railway Variables me BOT_TOKEN add karo."
        )

    if OWNER_ID <= 0:
        raise ValueError(
            "OWNER_ID is not set correctly. "
            "Railway Variables me numeric OWNER_ID add karo."
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # --------------------------------------------------------
    # COMMAND HANDLERS
    # --------------------------------------------------------

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "admin",
            admin_command
        )
    )

    application.add_handler(
        CommandHandler(
            "cancel",
            cancel_command
        )
    )

    # --------------------------------------------------------
    # CALLBACK HANDLER
    # --------------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            callback_router
        )
    )

    # --------------------------------------------------------
    # TEXT HANDLER
    # --------------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_message_router
        )
    )

    # --------------------------------------------------------
    # ERROR HANDLER
    # --------------------------------------------------------

    application.add_error_handler(
        error_handler
    )

    return application


# ============================================================
# MAIN
# ============================================================

def main():
    logger.info("Starting Telegram Reward Bot...")

    init_db()

    application = build_application()

    logger.info(
        "Bot started successfully."
    )

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


# ============================================================
# RUN BOT
# ============================================================

if __name__ == "__main__":
    main()


# ============================================================
# END OF BOT.PY
# ============================================================
