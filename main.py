import logging
import os
import sqlite3
from pathlib import Path
from contextlib import closing

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# Load .env locally (Termux). Railway variables are loaded automatically.
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "").strip()
DB_PATH = os.getenv("DB_PATH", "bot.db").strip() or "bot.db"
MAX_ITEMS = 20

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is missing. Add BOT_TOKEN to Railway Variables or your local .env file."
    )

if not ADMIN_ID_RAW.isdigit():
    raise RuntimeError(
        "ADMIN_ID is missing or invalid. Add your numeric Telegram user ID to Railway Variables or .env."
    )

ADMIN_ID = int(ADMIN_ID_RAW)

# Create the database directory automatically (important for Railway Volume).
db_file = Path(DB_PATH)
if db_file.parent != Path("."):
    db_file.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("telegram-content-bot")


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS content (
            position INTEGER PRIMARY KEY AUTOINCREMENT,
            source_chat_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def is_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user and user.id == ADMIN_ID)


def get_content():
    with closing(get_db()) as conn:
        return conn.execute(
            "SELECT position, source_chat_id, message_id "
            "FROM content ORDER BY position"
        ).fetchall()


def clear_content():
    with closing(get_db()) as conn:
        conn.execute("DELETE FROM content")
        conn.execute("DELETE FROM sqlite_sequence WHERE name='content'")
        conn.commit()


def add_content(source_chat_id: int, message_id: int):
    with closing(get_db()) as conn:
        conn.execute(
            "INSERT INTO content(source_chat_id, message_id) VALUES (?, ?)",
            (source_chat_id, message_id),
        )
        conn.commit()


def set_collecting(value: bool):
    with closing(get_db()) as conn:
        conn.execute(
            """
            INSERT INTO settings(key, value) VALUES('collecting', ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            ("1" if value else "0",),
        )
        conn.commit()


def is_collecting() -> bool:
    with closing(get_db()) as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key='collecting'"
        ).fetchone()
    return bool(row and row[0] == "1")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.message:
        return

    # Only the admin sees the control panel.
    if is_admin(update):
        count = len(get_content())
        await update.message.reply_text(
            "Admin Panel\n\n"
            f"Saved items: {count}/{MAX_ITEMS}\n"
            f"Collecting: {'ON' if is_collecting() else 'OFF'}\n\n"
            "/setup - replace the current package\n"
            "/done - finish setup\n"
            "/status - show status\n"
            "/clear - delete the package"
        )
        return

    await send_package(update.effective_chat.id, context)


async def send_package(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    content = get_content()

    if not content:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Content is not available yet. Please try again later.",
        )
        return

    failed = 0

    for _, source_chat_id, message_id in content:
        try:
            await context.bot.copy_message(
                chat_id=chat_id,
                from_chat_id=source_chat_id,
                message_id=message_id,
            )
        except Exception:
            failed += 1
            logger.exception(
                "Failed to copy message %s from %s to %s",
                message_id,
                source_chat_id,
                chat_id,
            )

    if failed:
        logger.error("Package delivery finished with %s failed item(s).", failed)


async def setup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update) or not update.message:
        return

    clear_content()
    set_collecting(True)

    await update.message.reply_text(
        "Setup mode ON.\n\n"
        f"Send up to {MAX_ITEMS} items to this chat in the exact order "
        "you want users to receive them.\n\n"
        "Files, photos, videos, text, captions and supported spoiler media are accepted.\n"
        "When finished, send /done."
    )


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update) or not update.message:
        return

    set_collecting(False)
    count = len(get_content())

    await update.message.reply_text(
        f"Setup complete.\n\n"
        f"Saved: {count}/{MAX_ITEMS} items.\n"
        "Users can now send /start to receive the package."
    )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update) or not update.message:
        return

    clear_content()
    set_collecting(False)
    await update.message.reply_text("All saved content has been cleared.")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update) or not update.message:
        return

    count = len(get_content())

    await update.message.reply_text(
        f"Status\n\n"
        f"Saved items: {count}/{MAX_ITEMS}\n"
        f"Collecting: {'ON' if is_collecting() else 'OFF'}"
    )


async def admin_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update) or not update.message:
        return

    if not is_collecting():
        return

    count = len(get_content())

    if count >= MAX_ITEMS:
        await update.message.reply_text(
            f"Maximum {MAX_ITEMS} items reached. Send /done to finish "
            "or /setup to start a new package."
        )
        return

    add_content(update.effective_chat.id, update.message.message_id)

    await update.message.reply_text(
        f"Saved item {count + 1}/{MAX_ITEMS}."
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Unhandled Telegram error: %s", context.error, exc_info=context.error)


def main():
    # Make sure the database exists before the bot starts polling.
    get_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setup", setup_command))
    app.add_handler(CommandHandler("done", done_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("status", status_command))

    # Save every non-command private message sent by the admin during setup.
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & ~filters.COMMAND,
            admin_content,
        )
    )

    # Ignore non-admin messages other than /start.
    app.add_handler(
        MessageHandler(filters.ALL & ~filters.COMMAND, lambda u, c: None)
    )

    app.add_error_handler(error_handler)

    logger.info("Bot is starting...")
    logger.info("Maximum package items: %s", MAX_ITEMS)
    logger.info("Database: %s", DB_PATH)

    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
