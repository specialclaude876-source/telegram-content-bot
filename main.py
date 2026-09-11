
import logging
import os
import sqlite3

from dotenv import load_dotenv

load_dotenv()
from contextlib import closing

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "").strip()
DB_PATH = os.getenv("DB_PATH", "bot.db")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing. Put it in .env before starting the bot.")
if not ADMIN_ID_RAW.isdigit():
    raise RuntimeError("ADMIN_ID is missing or invalid. Put your numeric Telegram user ID in .env.")

ADMIN_ID = int(ADMIN_ID_RAW)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("content-bot")


def db():
    conn = sqlite3.connect(DB_PATH)
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
    with closing(db()) as conn:
        rows = conn.execute(
            "SELECT position, source_chat_id, message_id FROM content ORDER BY position"
        ).fetchall()
    return rows


def set_collecting(value: bool):
    with closing(db()) as conn:
        conn.execute(
            """
            INSERT INTO settings(key, value) VALUES('collecting', ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            ("1" if value else "0",),
        )
        conn.commit()


def is_collecting() -> bool:
    with closing(db()) as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key='collecting'"
        ).fetchone()
    return bool(row and row[0] == "1")


def clear_content():
    with closing(db()) as conn:
        conn.execute("DELETE FROM content")
        conn.commit()


def add_content(source_chat_id: int, message_id: int):
    with closing(db()) as conn:
        conn.execute(
            "INSERT INTO content(source_chat_id, message_id) VALUES(?, ?)",
            (source_chat_id, message_id),
        )
        conn.commit()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Admin gets a private control message instead of the public content package.
    if is_admin(update):
        count = len(get_content())
        await update.message.reply_text(
            f"Admin panel\n\n"
            f"Saved items: {count}/20\n"
            f"Collecting mode: {'ON' if is_collecting() else 'OFF'}\n\n"
            f"/setup - start collecting content\n"
            f"/done - finish collecting\n"
            f"/clear - delete all saved content\n"
            f"/status - show current status\n\n"
            f"During setup, send up to 20 messages/files/media to this chat."
        )
        return

    await send_package(update.effective_chat.id, context)


async def send_package(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    content = get_content()

    if not content:
        # Keep this short and avoid exposing admin functionality to normal users.
        await context.bot.send_message(
            chat_id=chat_id,
            text="Content is not available yet. Please try again later."
        )
        return

    for _, source_chat_id, message_id in content:
        try:
            await context.bot.copy_message(
                chat_id=chat_id,
                from_chat_id=source_chat_id,
                message_id=message_id,
            )
        except Exception:
            logger.exception(
                "Failed to copy source message %s from chat %s to %s",
                message_id, source_chat_id, chat_id
            )


async def setup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    clear_content()
    set_collecting(True)
    await update.message.reply_text(
        "Setup mode is ON.\n\n"
        "Now send the content to this chat in the exact order you want users to receive it.\n"
        "You can send up to 20 messages/files/media.\n\n"
        "When finished, send /done."
    )


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    set_collecting(False)
    count = len(get_content())
    await update.message.reply_text(
        f"Setup complete.\n\nSaved: {count}/20 items.\n"
        "Users will receive these items automatically when they press /start."
    )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    clear_content()
    set_collecting(False)
    await update.message.reply_text("All saved content has been cleared.")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    count = len(get_content())
    await update.message.reply_text(
        f"Status\n\nSaved items: {count}/20\n"
        f"Collecting mode: {'ON' if is_collecting() else 'OFF'}"
    )


async def admin_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update) or not update.message:
        return

    if not is_collecting():
        return

    count = len(get_content())
    if count >= 20:
        await update.message.reply_text(
            "The maximum of 20 items is already saved. Send /done or /setup to replace them."
        )
        return

    # Store only the source message reference. Telegram keeps the actual media;
    # the bot later copies it to each user, preserving Telegram-supported message data.
    add_content(update.effective_chat.id, update.message.message_id)

    new_count = count + 1
    await update.message.reply_text(
        f"Saved item {new_count}/20. Send the next item or /done."
    )


async def unknown_or_other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Normal users have no controls. Ignore everything except /start.
    if not is_admin(update):
        return


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setup", setup_command))
    app.add_handler(CommandHandler("done", done_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("status", status_command))

    # Capture all ordinary admin messages while setup mode is active.
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & ~filters.COMMAND,
            admin_content,
        )
    )

    # Keep all other user messages ignored.
    app.add_handler(
        MessageHandler(filters.ALL & ~filters.COMMAND, unknown_or_other)
    )

    logger.info("Bot started.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
