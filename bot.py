import os
import sqlite3
import hashlib
import secrets
import html
import logging

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
DB_PATH = os.getenv("DB_PATH", "bot.db")

ITEMS_PER_PAGE = 6
PASSWORD_ROUNDS = 100_000

WELCOME_TEXT = (
    "🐣🎀𝐇ᴇ𝐋ʟᴏ 𝐌ᴇ𝐑ᴇ 𝐊ᴜᴄʜᴜ 𝐏ᴜᴄʜᴜ ♡🎀🥰"
    "𝐒ᴡᴀɢᴀᴛ 𝐇ᴀɪ 𝐀ᴘᴋᴀ 𝐘ᴀʜᴀ 𝐏ᴀʀ🧸💞"
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# ============================================================
# DATABASE
# ============================================================

def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = get_db()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            first_name TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT UNIQUE NOT NULL,
            title TEXT DEFAULT '',
            username TEXT DEFAULT '',
            invite_link TEXT DEFAULT ''
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            password_hash TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            user_id INTEGER PRIMARY KEY,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    con.commit()
    con.close()

    # Owner ko automatically admin banao.
    if OWNER_ID:
        con = get_db()

        row = con.execute(
            "SELECT user_id FROM admins WHERE user_id=?",
            (OWNER_ID,),
        ).fetchone()

        if not row:
            # Owner ka password login ke liye use nahi hota.
            con.execute(
                "INSERT INTO admins(user_id, password_hash) VALUES(?, ?)",
                (OWNER_ID, ""),
            )
            con.commit()

        con.close()


# ============================================================
# PASSWORD SYSTEM
# ============================================================

def make_password(password: str) -> str:
    salt = secrets.token_hex(16)

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ROUNDS,
    ).hex()

    return f"{salt}${digest}"


def check_password(password: str, stored_hash: str) -> bool:
    try:
        salt, digest = stored_hash.split("$", 1)

        check = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            PASSWORD_ROUNDS,
        ).hex()

        return secrets.compare_digest(
            check,
            digest,
        )

    except Exception:
        return False


def get_user_password(user_id: int):
    con = get_db()

    row = con.execute(
        "SELECT password_hash FROM licenses WHERE user_id=?",
        (user_id,),
    ).fetchone()

    con.close()

    if row:
        return row["password_hash"]

    return None


# ============================================================
# USERS / ADMIN / LICENSE
# ============================================================

def save_user(user):
    con = get_db()

    con.execute(
        """
        INSERT INTO users(
            user_id,
            username,
            first_name
        )
        VALUES(?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name
        """,
        (
            user.id,
            user.username or "",
            user.first_name or "",
        ),
    )

    con.commit()
    con.close()


def is_owner(user_id: int) -> bool:
    return (
        OWNER_ID != 0
        and user_id == OWNER_ID
    )


def is_admin(user_id: int) -> bool:
    if is_owner(user_id):
        return True

    con = get_db()

    row = con.execute(
        "SELECT 1 FROM admins WHERE user_id=?",
        (user_id,),
    ).fetchone()

    con.close()

    return row is not None


def has_license(user_id: int) -> bool:
    if is_owner(user_id) or is_admin(user_id):
        return True

    con = get_db()

    row = con.execute(
        "SELECT 1 FROM licenses WHERE user_id=?",
        (user_id,),
    ).fetchone()

    con.close()

    return row is not None


# ============================================================
# USER REPLY KEYBOARD
# ============================================================

def user_keyboard():
    return ReplyKeyboardMarkup(
        [
            [
                "🎁 ITEMS",
                "ℹ️ ABOUT",
            ]
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


# ============================================================
# ADMIN REPLY KEYBOARD
# Screenshot jaisa layout
# ============================================================

def admin_keyboard():
    return ReplyKeyboardMarkup(
        [
            [
                "➕ Add Item",
                "➖ Remove Item",
            ],
            [
                "📋 List Items",
            ],
            [
                "➕ Add Channel",
                "➖ Remove Channel",
            ],
            [
                "📋 List Channels",
            ],
            [
                "📢 Broadcast",
                "📊 Statistics",
            ],
            [
                "👤 Add Admin",
                "🗑 Remove Admin",
            ],
            [
                "📋 List Admins",
            ],
            [
                "🔑 Add License",
                "🗑 Remove License",
            ],
            [
                "📋 License List",
            ],
            [
                "🔄 Change Password",
            ],
            [
                "❌ Cancel",
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def cancel_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["❌ Cancel"],
        ],
        resize_keyboard=True,
    )


# ============================================================
# CHANNEL FUNCTIONS
# ============================================================

def get_channels():
    con = get_db()

    rows = con.execute(
        "SELECT * FROM channels ORDER BY id DESC"
    ).fetchall()

    con.close()

    return rows


def channel_keyboard(channels):
    buttons = []

    for channel in channels:

        link = ""

        if channel["invite_link"]:
            link = channel["invite_link"]

        elif channel["username"]:
            link = (
                "https://t.me/"
                + channel["username"].lstrip("@")
            )

        if not link:
            continue

        title = (
            channel["title"]
            or channel["username"]
            or "Join Channel"
        )

        buttons.append(
            [
                InlineKeyboardButton(
                    f"📢 {title}",
                    url=link,
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

    return InlineKeyboardMarkup(buttons)


async def check_channels(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
):
    channels = get_channels()

    if not channels:
        return True

    for channel in channels:

        try:

            member = await context.bot.get_chat_member(
                chat_id=channel["chat_id"],
                user_id=user_id,
            )

            if member.status in (
                "left",
                "kicked",
            ):
                return False

        except Exception as e:

            logger.warning(
                "Channel check error: %s",
                e,
            )

            return False

    return True


# ============================================================
# PFP + WELCOME
# ============================================================

async def send_welcome(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    keyboard=None,
):
    user = update.effective_user

    try:

        photos = await context.bot.get_user_profile_photos(
            user.id,
            limit=1,
        )

        if photos.total_count > 0:

            file_id = photos.photos[0][-1].file_id

            await update.effective_message.reply_photo(
                photo=file_id,
                caption=WELCOME_TEXT,
                reply_markup=keyboard,
            )

            return

    except Exception as e:

        logger.warning(
            "PFP error: %s",
            e,
        )

    await update.effective_message.reply_text(
        WELCOME_TEXT,
        reply_markup=keyboard,
    )


# ============================================================
# START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    context.user_data.clear()

    user = update.effective_user

    save_user(user)

    # ---------------- ADMIN ----------------

    if is_admin(user.id):

        await send_welcome(
            update,
            context,
            admin_keyboard(),
        )

        await update.effective_message.reply_text(
            "🛠️ <b>ADMIN PANEL</b>\n\n"
            "Neeche se option select karein.",
            parse_mode="HTML",
            reply_markup=admin_keyboard(),
        )

        return

    # ---------------- LICENSE ----------------

    if not has_license(user.id):

        await send_welcome(
            update,
            context,
        )

        await update.effective_message.reply_text(
            "🔒 <b>LICENSE REQUIRED</b>\n\n"
            f"🆔 Your Telegram ID:\n"
            f"<code>{user.id}</code>\n\n"
            "Aapke ID par license active nahi hai.",
            parse_mode="HTML",
        )

        return

    # ---------------- CHANNEL ----------------

    channels = get_channels()

    if channels:

        verified = await check_channels(
            context,
            user.id,
        )

        if not verified:

            await send_welcome(
                update,
                context,
                channel_keyboard(channels),
            )

            await update.effective_message.reply_text(
                "📢 <b>JOIN REQUIRED CHANNELS</b>\n\n"
                "Sabhi channels join karke "
                "<b>VERIFY</b> dabayein.",
                parse_mode="HTML",
            )

            return

    # ---------------- PASSWORD ----------------

    context.user_data["state"] = "login"

    await send_welcome(
        update,
        context,
    )

    await update.effective_message.reply_text(
        "🔐 <b>PASSWORD LOGIN</b>\n\n"
        "Apna assigned password bhejiye.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


# ============================================================
# VERIFY
# ============================================================

async def verify_button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    if is_admin(user_id):

        context.user_data["logged_in"] = True

        await query.message.reply_text(
            "🛠️ <b>Admin access verified.</b>",
            parse_mode="HTML",
            reply_markup=admin_keyboard(),
        )

        return

    if not has_license(user_id):

        await query.answer(
            "❌ License not found.",
            show_alert=True,
        )

        return

    if not await check_channels(
        context,
        user_id,
    ):

        await query.answer(
            "❌ Please join all required channels.",
            show_alert=True,
        )

        return

    context.user_data["state"] = "login"

    await query.message.reply_text(
        "🔐 <b>PASSWORD LOGIN</b>\n\n"
        "Apna assigned password bhejiye.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


# ============================================================
# MAIN MENU
# ============================================================

async def show_main_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    context.user_data.pop("state", None)

    await update.effective_message.reply_text(
        "✅ <b>VERIFICATION SUCCESSFUL</b>\n\n"
        "Neeche menu se option choose karein.",
        parse_mode="HTML",
        reply_markup=user_keyboard(),
    )


# ============================================================
# ITEMS
# ============================================================

async def show_items(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
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

    buttons = []

    # 6 items = 3 rows × 2 columns
    for i in range(
        0,
        len(rows),
        2,
    ):

        row = []

        for item in rows[i:i + 2]:

            row.append(
                InlineKeyboardButton(
                    f"🎁 {item['name']}",
                    callback_data=f"item_{item['id']}",
                )
            )

        buttons.append(row)

    # Navigation.
    navigation = []

    if page > 0:

        navigation.append(
            InlineKeyboardButton(
                "⬅️ Previous",
                callback_data=f"items_{page - 1}",
            )
        )

    if (
        (page + 1) * ITEMS_PER_PAGE
        < total
    ):

        navigation.append(
            InlineKeyboardButton(
                "Next ➡️",
                callback_data=f"items_{page + 1}",
            )
        )

    if navigation:
        buttons.append(navigation)

    buttons.append(
        [
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="items_back",
            )
        ]
    )

    if total == 0:

        text = (
            "🎁 <b>ITEMS</b>\n\n"
            "❌ No items available right now."
        )

    else:

        total_pages = (
            total + ITEMS_PER_PAGE - 1
        ) // ITEMS_PER_PAGE

        text = (
            "🎁 <b>ITEMS</b>\n\n"
            "Select an item below.\n\n"
            f"📄 Page {page + 1}/{total_pages}"
        )

    await update.effective_message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ============================================================
# ITEM DETAILS
# ============================================================

async def item_details(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    item_id: int,
):

    query = update.callback_query

    con = get_db()

    item = con.execute(
        "SELECT * FROM items WHERE id=?",
        (item_id,),
    ).fetchone()

    con.close()

    if not item:

        await query.answer(
            "❌ Item not found.",
            show_alert=True,
        )

        return

    text = (
        f"🎁 <b>{html.escape(item['name'])}</b>\n\n"
        f"{html.escape(item['content'])}"
    )

    await query.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔙 Back",
                        callback_data="items_0",
                    )
                ]
            ]
        ),
    )


# ============================================================
# ADMIN: ADD ITEM
# ============================================================

async def add_item_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    context.user_data.clear()
    context.user_data["state"] = "item_name"

    await update.effective_message.reply_text(
        "➕ <b>ADD ITEM</b>\n\n"
        "Step 1/3\n\n"
        "🎁 Item Name bhejiye.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


# ============================================================
# ADMIN: REMOVE ITEM
# ============================================================

async def remove_item_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    con = get_db()

    rows = con.execute(
        "SELECT * FROM items ORDER BY id DESC"
    ).fetchall()

    con.close()

    if not rows:

        await update.effective_message.reply_text(
            "➖ <b>REMOVE ITEM</b>\n\n"
            "❌ No items available.",
            parse_mode="HTML",
            reply_markup=admin_keyboard(),
        )

        return

    buttons = []

    for item in rows:

        buttons.append(
            [
                InlineKeyboardButton(
                    f"🗑 {item['name']}",
                    callback_data=f"remove_item_{item['id']}",
                )
            ]
        )

    await update.effective_message.reply_text(
        "➖ <b>REMOVE ITEM</b>\n\n"
        "Item select karein:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ============================================================
# ADMIN: LIST ITEMS
# ============================================================

async def list_items(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    con = get_db()

    rows = con.execute(
        "SELECT * FROM items ORDER BY id DESC"
    ).fetchall()

    con.close()

    if not rows:

        text = (
            "📋 <b>LIST ITEMS</b>\n\n"
            "❌ No items."
        )

    else:

        text = (
            "📋 <b>LIST ITEMS</b>\n\n"
            + "\n".join(
                [
                    f"🎁 {html.escape(x['name'])}"
                    f" — ID <code>{x['id']}</code>"
                    for x in rows
                ]
            )
        )

    await update.effective_message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN: ADD CHANNEL
# ============================================================

async def add_channel_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    context.user_data["state"] = "channel"

    await update.effective_message.reply_text(
        "➕ <b>ADD CHANNEL</b>\n\n"
        "Channel username bhejiye.\n\n"
        "Example:\n"
        "<code>@mychannel</code>\n\n"
        "⚠️ Bot ko channel ka admin banana zaroori hai.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


# ============================================================
# ADMIN: REMOVE CHANNEL
# ============================================================

async def remove_channel_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    rows = get_channels()

    if not rows:

        await update.effective_message.reply_text(
            "➖ <b>REMOVE CHANNEL</b>\n\n"
            "❌ No channels.",
            parse_mode="HTML",
            reply_markup=admin_keyboard(),
        )

        return

    buttons = []

    for channel in rows:

        name = (
            channel["title"]
            or channel["username"]
            or channel["chat_id"]
        )

        buttons.append(
            [
                InlineKeyboardButton(
                    f"🗑 {name}",
                    callback_data=f"remove_channel_{channel['id']}",
                )
            ]
        )

    await update.effective_message.reply_text(
        "➖ <b>REMOVE CHANNEL</b>\n\n"
        "Channel select karein:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ============================================================
# ADMIN: LIST CHANNELS
# ============================================================

async def list_channels(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    rows = get_channels()

    if not rows:

        text = (
            "📋 <b>LIST CHANNELS</b>\n\n"
            "❌ No channels."
        )

    else:

        lines = []

        for channel in rows:

            name = (
                channel["title"]
                or channel["username"]
                or channel["chat_id"]
            )

            lines.append(
                f"📢 {html.escape(name)}"
            )

        text = (
            "📋 <b>LIST CHANNELS</b>\n\n"
            + "\n".join(lines)
        )

    await update.effective_message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN: ADD ADMIN
# ============================================================

async def add_admin_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not is_owner(
        update.effective_user.id
    ):

        await update.effective_message.reply_text(
            "❌ Owner only."
        )

        return

    context.user_data["state"] = "add_admin"

    await update.effective_message.reply_text(
        "👤 <b>ADD ADMIN</b>\n\n"
        "Admin ka Telegram numeric ID bhejiye.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


# ============================================================
# ADMIN: REMOVE ADMIN
# ============================================================

async def remove_admin_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not is_owner(
        update.effective_user.id
    ):

        await update.effective_message.reply_text(
            "❌ Owner only."
        )

        return

    con = get_db()

    rows = con.execute(
        """
        SELECT user_id
        FROM admins
        WHERE user_id != ?
        ORDER BY user_id
        """,
        (OWNER_ID,),
    ).fetchall()

    con.close()

    if not rows:

        await update.effective_message.reply_text(
            "🗑 <b>REMOVE ADMIN</b>\n\n"
            "❌ No extra admins.",
            parse_mode="HTML",
            reply_markup=admin_keyboard(),
        )

        return

    buttons = []

    for row in rows:

        buttons.append(
            [
                InlineKeyboardButton(
                    f"🗑 {row['user_id']}",
                    callback_data=f"remove_admin_{row['user_id']}",
                )
            ]
        )

    await update.effective_message.reply_text(
        "🗑 <b>REMOVE ADMIN</b>\n\n"
        "Admin select karein:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ============================================================
# ADMIN: LIST ADMINS
# ============================================================

async def list_admins(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    con = get_db()

    rows = con.execute(
        "SELECT user_id FROM admins ORDER BY user_id"
    ).fetchall()

    con.close()

    extra_admins = [
        f"👤 <code>{row['user_id']}</code>"
        for row in rows
        if row["user_id"] != OWNER_ID
    ]

    text = (
        "📋 <b>LIST ADMINS</b>\n\n"
        f"👑 Owner:\n<code>{OWNER_ID}</code>\n\n"
        "🛠️ Admins:\n"
    )

    if extra_admins:
        text += "\n".join(extra_admins)
    else:
        text += "No extra admins."

    await update.effective_message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN: ADD LICENSE
# IMPORTANT:
# User ID -> Separate Password
# ============================================================

async def add_license_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    context.user_data["state"] = "license_user_id"

    await update.effective_message.reply_text(
        "🔑 <b>ADD LICENSE</b>\n\n"
        "Step 1/2\n\n"
        "User ka Telegram numeric ID bhejiye.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


# ============================================================
# ADMIN: REMOVE LICENSE
# ============================================================

async def remove_license_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    con = get_db()

    rows = con.execute(
        "SELECT user_id FROM licenses ORDER BY user_id"
    ).fetchall()

    con.close()

    if not rows:

        await update.effective_message.reply_text(
            "🗑 <b>REMOVE LICENSE</b>\n\n"
            "❌ No licenses.",
            parse_mode="HTML",
            reply_markup=admin_keyboard(),
        )

        return

    buttons = []

    for row in rows:

        buttons.append(
            [
                InlineKeyboardButton(
                    f"🗑 {row['user_id']}",
                    callback_data=f"remove_license_{row['user_id']}",
                )
            ]
        )

    await update.effective_message.reply_text(
        "🗑 <b>REMOVE LICENSE</b>\n\n"
        "User select karein:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ============================================================
# ADMIN: LIST LICENSES
# ============================================================

async def list_licenses(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    con = get_db()

    rows = con.execute(
        "SELECT user_id FROM licenses ORDER BY user_id"
    ).fetchall()

    con.close()

    if not rows:

        text = (
            "📋 <b>LICENSE LIST</b>\n\n"
            "❌ No licenses."
        )

    else:

        text = (
            "📋 <b>LICENSE LIST</b>\n\n"
            + "\n".join(
                [
                    f"🔑 <code>{x['user_id']}</code>"
                    for x in rows
                ]
            )
        )

    await update.effective_message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


# ============================================================
# ADMIN: CHANGE USER PASSWORD
# User ID -> New Password
# ============================================================

async def change_password_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    context.user_data["state"] = "change_password_user"

    await update.effective_message.reply_text(
        "🔄 <b>CHANGE PASSWORD</b>\n\n"
        "Step 1/2\n\n"
        "Jis user ka password change karna hai "
        "uska Telegram ID bhejiye.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


# ============================================================
# ADMIN: BROADCAST
# ============================================================

async def broadcast_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    context.user_data["state"] = "broadcast"

    await update.effective_message.reply_text(
        "📢 <b>BROADCAST</b>\n\n"
        "Ab broadcast message bhejiye.\n\n"
        "Text / Photo / Video / Document etc. supported.",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )


# ============================================================
# ADMIN: STATISTICS
# ============================================================

async def statistics(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

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
        f"👤 Users: <b>{users}</b>\n"
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
# ADMIN REPLY KEYBOARD ROUTER
# ============================================================

async def admin_router(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
):

    user_id = update.effective_user.id

    if not is_admin(user_id):
        return

    if text == "➕ Add Item":
        await add_item_start(update, context)
        return

    if text == "➖ Remove Item":
        await remove_item_start(update, context)
        return

    if text == "📋 List Items":
        await list_items(update, context)
        return

    if text == "➕ Add Channel":
        await add_channel_start(update, context)
        return

    if text == "➖ Remove Channel":
        await remove_channel_start(update, context)
        return

    if text == "📋 List Channels":
        await list_channels(update, context)
        return

    if text == "📢 Broadcast":
        await broadcast_start(update, context)
        return

    if text == "📊 Statistics":
        await statistics(update, context)
        return

    if text == "👤 Add Admin":
        await add_admin_start(update, context)
        return

    if text == "🗑 Remove Admin":
        await remove_admin_start(update, context)
        return

    if text == "📋 List Admins":
        await list_admins(update, context)
        return

    if text == "🔑 Add License":
        await add_license_start(update, context)
        return

    if text == "🗑 Remove License":
        await remove_license_start(update, context)
        return

    if text == "📋 License List":
        await list_licenses(update, context)
        return

    if text == "🔄 Change Password":
        await change_password_start(update, context)
        return


# ============================================================
# CALLBACK HANDLER
# ============================================================

async def callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = query.from_user.id

    # ---------------- VERIFY ----------------

    if data == "verify":

        await verify_button(
            update,
            context,
        )

        return

    # ---------------- ITEMS PAGE ----------------

    if data.startswith("items_"):

        if not context.user_data.get(
            "logged_in"
        ):

            await query.answer(
                "❌ Login first.",
                show_alert=True,
            )

            return

        page = int(
            data.split("_")[1]
        )

        await query.message.reply_text(
            "🎁 <b>ITEMS</b>",
            parse_mode="HTML",
        )

        await show_items(
            update,
            context,
            page,
        )

        return

    # ---------------- ITEMS BACK ----------------

    if data == "items_back":

        await query.message.reply_text(
            "🏠 Main Menu",
            reply_markup=user_keyboard(),
        )

        return

    # ---------------- ITEM DETAILS ----------------

    if data.startswith("item_"):

        if not context.user_data.get(
            "logged_in"
        ):

            await query.answer(
                "❌ Login first.",
                show_alert=True,
            )

            return

        item_id = int(
            data.split("_")[1]
        )

        await item_details(
            update,
            context,
            item_id,
        )

        return

    # ---------------- REMOVE ITEM ----------------

    if data.startswith("remove_item_"):

        if not is_admin(user_id):
            return

        item_id = int(
            data.rsplit("_", 1)[1]
        )

        con = get_db()

        con.execute(
            "DELETE FROM items WHERE id=?",
            (item_id,),
        )

        con.commit()
        con.close()

        await query.message.reply_text(
            "✅ <b>ITEM REMOVED</b>",
            parse_mode="HTML",
            reply_markup=admin_keyboard(),
        )

        return

    # ---------------- REMOVE CHANNEL ----------------

    if data.startswith("remove_channel_"):

        if not is_admin(user_id):
            return

        channel_id = int(
            data.rsplit("_", 1)[1]
        )

        con = get_db()

        con.execute(
            "DELETE FROM channels WHERE id=?",
            (channel_id,),
        )

        con.commit()
        con.close()

        await query.message.reply_text(
            "✅ <b>CHANNEL REMOVED</b>",
            parse_mode="HTML",
            reply_markup=admin_keyboard(),
        )

        return

    # ---------------- REMOVE ADMIN ----------------

    if data.startswith("remove_admin_"):

        if not is_owner(user_id):
            return

        target_id = int(
            data.rsplit("_", 1)[1]
        )

        if target_id == OWNER_ID:

            await query.message.reply_text(
                "❌ Owner cannot be removed.",
                reply_markup=admin_keyboard(),
            )

            return

        con = get_db()

        con.execute(
            "DELETE FROM admins WHERE user_id=?",
            (target_id,),
        )

        con.commit()
        con.close()

        await query.message.reply_text(
            "✅ <b>ADMIN REMOVED</b>",
            parse_mode="HTML",
            reply_markup=admin_keyboard(),
        )

        return

    # ---------------- REMOVE LICENSE ----------------

    if data.startswith("remove_license_"):

        if not is_admin(user_id):
            return

        target_id = int(
            data.rsplit("_", 1)[1]
        )

        con = get_db()

        con.execute(
            "DELETE FROM licenses WHERE user_id=?",
            (target_id,),
        )

        con.commit()
        con.close()

        await query.message.reply_text(
            "✅ <b>LICENSE REMOVED</b>",
            parse_mode="HTML",
            reply_markup=admin_keyboard(),
        )

        return


# ============================================================
# TEXT HANDLER
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

        context.user_data.clear()

        if is_admin(user.id):

            await message.reply_text(
                "❌ Cancelled.",
                reply_markup=admin_keyboard(),
            )

        else:

            await message.reply_text(
                "❌ Cancelled.",
                reply_markup=user_keyboard(),
            )

        return

    # ========================================================
    # USER MENU
    # ========================================================

    if text == "🎁 ITEMS":

        if not context.user_data.get(
            "logged_in"
        ):

            await message.reply_text(
                "❌ Please login first."
            )

            return

        await show_items(
            update,
            context,
            0,
        )

        return

    if text == "ℹ️ ABOUT":

        await message.reply_text(
            "ℹ️ <b>ABOUT</b>\n\n"
            "🎁 Items are managed by the admin.\n"
            "🔐 Access is protected by Telegram ID, "
            "license and individual password.",
            parse_mode="HTML",
            reply_markup=user_keyboard(),
        )

        return

    # ========================================================
    # ADMIN BUTTONS
    # ========================================================

    admin_buttons = {
        "➕ Add Item",
        "➖ Remove Item",
        "📋 List Items",
        "➕ Add Channel",
        "➖ Remove Channel",
        "📋 List Channels",
        "📢 Broadcast",
        "📊 Statistics",
        "👤 Add Admin",
        "🗑 Remove Admin",
        "📋 List Admins",
        "🔑 Add License",
        "🗑 Remove License",
        "📋 License List",
        "🔄 Change Password",
    }

    if text in admin_buttons:

        await admin_router(
            update,
            context,
            text,
        )

        return

    # ========================================================
    # STATE
    # ========================================================

    state = context.user_data.get(
        "state"
    )

    # ========================================================
    # USER LOGIN
    # ========================================================

    if state == "login":

        if not has_license(user.id):

            context.user_data.clear()

            await message.reply_text(
                "❌ License inactive."
            )

            return

        stored_hash = get_user_password(
            user.id
        )

        if not stored_hash:

            await message.reply_text(
                "❌ Password not configured for this license."
            )

            return

        if not check_password(
            text,
            stored_hash,
        ):

            await message.reply_text(
                "❌ Wrong password.\n\n"
                "Please try again."
            )

            return

        context.user_data["logged_in"] = True
        context.user_data.pop("state", None)

        await message.reply_text(
            "✅ <b>LOGIN SUCCESSFUL</b>",
            parse_mode="HTML",
            reply_markup=user_keyboard(),
        )

        return

    # ========================================================
    # ADD ITEM - NAME
    # ========================================================

    if state == "item_name":

        if not is_admin(user.id):
            return

        if not text.strip():

            await message.reply_text(
                "❌ Item name empty nahi ho sakta."
            )

            return

        context.user_data["item_name"] = (
            text.strip()
        )

        context.user_data["state"] = (
            "item_content"
        )

        await message.reply_text(
            "➕ <b>ADD ITEM</b>\n\n"
            "Step 2/3\n\n"
            "📝 Item Content / Details bhejiye.",
            parse_mode="HTML",
            reply_markup=cancel_keyboard(),
        )

        return

    # ========================================================
    # ADD ITEM - CONTENT
    # ========================================================

    if state == "item_content":

        if not is_admin(user.id):
            return

        if not text.strip():

            await message.reply_text(
                "❌ Content empty nahi ho sakta."
            )

            return

        context.user_data["item_content"] = (
            text.strip()
        )

        context.user_data["state"] = (
            "item_save"
        )

        save_keyboard = ReplyKeyboardMarkup(
            [
                ["💾 SAVE ✅"],
                ["❌ Cancel"],
            ],
            resize_keyboard=True,
        )

        await message.reply_text(
            "➕ <b>ADD ITEM</b>\n\n"
            "Step 3/3\n\n"
            "Details received.\n"
            "<b>💾 SAVE ✅</b> press karein.",
            parse_mode="HTML",
            reply_markup=save_keyboard,
        )

        return

    # ========================================================
    # ADD ITEM - SAVE
    # ========================================================

    if state == "item_save":

        if not is_admin(user.id):
            return

        if text != "💾 SAVE ✅":

            await message.reply_text(
                "👇 <b>💾 SAVE ✅</b> press karein.",
                parse_mode="HTML",
            )

            return

        name = context.user_data.get(
            "item_name",
            "",
        )

        content = context.user_data.get(
            "item_content",
            "",
        )

        if not name or not content:

            context.user_data.clear()

            await message.reply_text(
                "❌ Item data missing.",
                reply_markup=admin_keyboard(),
            )

            return

        con = get_db()

        cur = con.cursor()

        cur.execute(
            """
            INSERT INTO items(
                name,
                content
            )
            VALUES(?, ?)
            """,
            (
                name,
                content,
            ),
        )

        item_id = cur.lastrowid

        con.commit()
        con.close()

        context.user_data.clear()

        await message.reply_text(
            "✅ <b>ITEM SAVED</b>\n\n"
            f"🎁 {html.escape(name)}\n"
            f"🆔 ID: <code>{item_id}</code>",
            parse_mode="HTML",
            reply_markup=admin_keyboard(),
        )

        return

    # ========================================================
    # ADD CHANNEL
    # ========================================================

    if state == "channel":

        if not is_admin(user.id):
            return

        value = text.strip()

        if not value.startswith("@"):

            await message.reply_text(
                "❌ Public channel username bhejiye.\n\n"
                "Example:\n"
                "<code>@mychannel</code>",
                parse_mode="HTML",
            )

            return

        try:

            chat = await context.bot.get_chat(
                value
            )

            title = (
                chat.title
                or "Channel"
            )

            username = (
                "@"
                + chat.username
                if chat.username
                else value
            )

            invite_link = (
                f"https://t.me/{chat.username}"
                if chat.username
                else ""
            )

            real_chat_id = str(
                chat.id
            )

        except Exception as e:

            logger.warning(
                "Channel error: %s",
                e,
            )

            await message.reply_text(
                "❌ Channel nahi mila.\n\n"
                "Check username aur bot ko channel me admin banayein."
            )

            return

        con = get_db()

        con.execute(
            """
            INSERT INTO channels(
                chat_id,
                title,
                username,
                invite_link
            )
            VALUES(?, ?, ?, ?)
            ON CONFLICT(chat_id)
            DO UPDATE SET
                title=excluded.title,
                username=excluded.username,
                invite_link=excluded.invite_link
            """,
            (
                real_chat_id,
                title,
                username,
                invite_link,
            ),
        )

        con.commit()
        con.close()

        context.user_data.clear()

        await message.reply_text(
            "✅ <b>CHANNEL ADDED</b>\n\n"
            f"📢 {html.escape(title)}",
            parse_mode="HTML",
            reply_markup=admin_keyboard(),
        )

        return

    # ========================================================
    # ADD ADMIN
    # ========================================================

    if state == "add_admin":

        if not is_owner(user.id):

            await message.reply_text(
                "❌ Owner only."
            )

            return

        try:

            target_id = int(
                text.strip()
            )

        except ValueError:

            await message.reply_text(
                "❌ Valid numeric Telegram ID bhejiye."
            )

            return

        if target_id == OWNER_ID:

            await message.reply_text(
                "❌ Owner already admin hai."
            )

            return

        # Admin ke liye random password.
        generated_password = (
            secrets.token_urlsafe(10)
        )

        con = get_db()

        con.execute(
            """
            INSERT INTO admins(
                user_id,
                password_hash
            )
            VALUES(?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET
                password_hash=excluded.password_hash
            """,
            (
                target_id,
                make_password(
                    generated_password
                ),
            ),
        )

        con.commit()
        con.close()

        context.user_data.clear()

        await message.reply_text(
            "✅ <b>ADMIN ADDED</b>\n\n"
            f"👤 ID: <code>{target_id}</code>\n"
            f"🔑 Password: <code>{generated_password}</code>",
            parse_mode="HTML",
            reply_markup=admin_keyboard(),
        )

        return

    # ========================================================
    # ADD LICENSE - USER ID
    # ========================================================

    if state == "license_user_id":

        if not is_admin(user.id):
            return

        try:

            target_id = int(
                text.strip()
            )

        except ValueError:

            await message.reply_text(
                "❌ Valid numeric Telegram ID bhejiye."
            )

            return

        context.user_data[
            "license_user_id"
        ] = target_id

        context.user_data[
            "state"
        ] = "license_password"

        await message.reply_text(
            "🔑 <b>ADD LICENSE</b>\n\n"
            "Step 2/2\n\n"
            f"👤 User ID: <code>{target_id}</code>\n\n"
            "Ab is user ka <b>alag password</b> bhejiye.",
            parse_mode="HTML",
            reply_markup=cancel_keyboard(),
        )

        return

    # ========================================================
    # ADD LICENSE - PASSWORD
    # ========================================================

    if state == "license_password":

        if not is_admin(user.id):
            return

        target_id = context.user_data.get(
            "license_user_id"
        )

        if not target_id:

            context.user_data.clear()

            await message.reply_text(
                "❌ User ID missing.",
                reply_markup=admin_keyboard(),
            )

            return

        if len(text.strip()) < 4:

            await message.reply_text(
                "❌ Password minimum 4 characters ka hona chahiye."
            )

            return

        con = get_db()

        con.execute(
            """
            INSERT INTO licenses(
                user_id,
                password_hash
            )
            VALUES(?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET
                password_hash=excluded.password_hash
            """,
            (
                target_id,
                make_password(
                    text.strip()
                ),
            ),
        )

        con.commit()
        con.close()

        context.user_data.clear()

        await message.reply_text(
            "✅ <b>LICENSE ADDED</b>\n\n"
            f"👤 User ID: <code>{target_id}</code>\n"
            "🔐 Separate password successfully saved.",
            parse_mode="HTML",
            reply_markup=admin_keyboard(),
        )

        return

    # ========================================================
    # CHANGE PASSWORD - USER ID
    # ========================================================

    if state == "change_password_user":

        if not is_admin(user.id):
            return

        try:

            target_id = int(
                text.strip()
            )

        except ValueError:

            await message.reply_text(
                "❌ Valid numeric Telegram ID bhejiye."
            )

            return

        if not has_license(target_id):

            await message.reply_text(
                "❌ Is user ka license nahi mila."
            )

            return

        context.user_data[
            "change_password_user_id"
        ] = target_id

        context.user_data[
            "state"
        ] = "change_password_value"

        await message.reply_text(
            "🔄 <b>CHANGE PASSWORD</b>\n\n"
            "Step 2/2\n\n"
            f"👤 User ID: <code>{target_id}</code>\n\n"
            "New password bhejiye.",
            parse_mode="HTML",
            reply_markup=cancel_keyboard(),
        )

        return

    # ========================================================
    # CHANGE PASSWORD - NEW PASSWORD
    # ========================================================

    if state == "change_password_value":

        if not is_admin(user.id):
            return

        target_id = context.user_data.get(
            "change_password_user_id"
        )

        if not target_id:

            context.user_data.clear()

            await message.reply_text(
                "❌ User ID missing.",
                reply_markup=admin_keyboard(),
            )

            return

        if len(text.strip()) < 4:

            await message.reply_text(
                "❌ Password minimum 4 characters ka hona chahiye."
            )

            return

        con = get_db()

        con.execute(
            """
            UPDATE licenses
            SET password_hash=?
            WHERE user_id=?
            """,
            (
                make_password(
                    text.strip()
                ),
                target_id,
            ),
        )

        con.commit()
        con.close()

        context.user_data.clear()

        await message.reply_text(
            "✅ <b>PASSWORD CHANGED</b>\n\n"
            f"👤 User ID: <code>{target_id}</code>",
            parse_mode="HTML",
            reply_markup=admin_keyboard(),
        )

        return

    # ========================================================
    # BROADCAST
    # ========================================================

    if state == "broadcast":

        if not is_admin(user.id):
            return

        con = get_db()

        users = con.execute(
            "SELECT user_id FROM users"
        ).fetchall()

        con.close()

        sent = 0
        failed = 0

        for row in users:

            try:

                await message.copy(
                    chat_id=row["user_id"]
                )

                sent += 1

            except Exception as e:

                failed += 1

                logger.warning(
                    "Broadcast failed: %s",
                    e,
                )

        context.user_data.clear()

        await message.reply_text(
            "📢 <b>BROADCAST COMPLETE</b>\n\n"
            f"✅ Sent: {sent}\n"
            f"❌ Failed: {failed}",
            parse_mode="HTML",
            reply_markup=admin_keyboard(),
        )

        return


# ============================================================
# /ADMIN
# ============================================================

async def admin_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not is_admin(
        update.effective_user.id
    ):

        await update.effective_message.reply_text(
            "❌ Admin only."
        )

        return

    await update.effective_message.reply_text(
        "🛠️ <b>ADMIN PANEL</b>\n\n"
        "Neeche se option select karein.",
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


# ============================================================
# /CANCEL
# ============================================================

async def cancel_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    context.user_data.clear()

    if is_admin(
        update.effective_user.id
    ):

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
# ERROR HANDLER
# ============================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):

    logger.exception(
        "Unhandled exception:",
        exc_info=context.error,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN environment variable missing."
        )

    if OWNER_ID == 0:

        raise RuntimeError(
            "OWNER_ID environment variable missing."
        )

    init_db()

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Commands.
    app.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    app.add_handler(
        CommandHandler(
            "admin",
            admin_command,
        )
    )

    app.add_handler(
        CommandHandler(
            "cancel",
            cancel_command,
        )
    )

    # Callback buttons.
    app.add_handler(
        CallbackQueryHandler(
            callback_handler
        )
    )

    # Reply Keyboard + normal text.
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler,
        )
    )

    app.add_error_handler(
        error_handler
    )

    logger.info(
        "Bot started successfully."
    )

    app.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
