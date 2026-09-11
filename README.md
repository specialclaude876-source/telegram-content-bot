# Telegram Content Delivery Bot — Final V1

A simple Telegram bot where:

- `/start` sends the configured content package automatically.
- Normal users have no admin controls.
- One Telegram user ID is the only admin.
- Admin can configure up to **20 messages/media/files**.
- Content is delivered in the exact order it was saved.
- Telegram-supported formatting, captions, spoiler media, and other copyable message data are preserved as much as Telegram's Bot API allows.
- View-once/self-destructing media is intentionally not supported.
- SQLite stores the configuration so it survives normal restarts.

## Admin commands

`/setup` — clears the old package and starts a fresh setup.

Then send up to **20 items** in the exact order you want users to receive them.

`/done` — finish setup.

`/status` — show saved item count and setup status.

`/clear` — delete all saved content.

## Normal users

Normal users only need:

`/start`

The bot automatically sends the saved package. Other commands/messages from normal users are ignored.

## Supported content

You can send, for example:

- ZIP/document files
- Photos
- Videos
- Text
- Captions
- Spoiler photos/videos
- Other Telegram message types supported by Telegram message copying

## Termux

```bash
pkg update -y
pkg install python git -y
cd telegram_content_bot
pip install -r requirements.txt
cp .env.example .env
nano .env
```

Set:

```text
BOT_TOKEN=YOUR_BOT_TOKEN
ADMIN_ID=YOUR_TELEGRAM_USER_ID
DB_PATH=bot.db
```

Save nano with `CTRL + O`, Enter, then `CTRL + X`.

Start:

```bash
python bot/main.py
```

**Do not run `cp .env.example .env` again after entering your real values**, because it will overwrite the `.env` file.

## Railway

Set these Railway variables:

```text
BOT_TOKEN=your_bot_token
ADMIN_ID=your_numeric_user_id
DB_PATH=/app/data/bot.db
```

Attach a Railway Volume mounted at:

```text
/app/data
```

Recommended Start Command:

```text
python bot/main.py
```

Do not upload `.env` to GitHub.

## Important source-message behavior

The bot stores references to the admin's Telegram messages and later uses Telegram's copy-message functionality to deliver them.

Keep the original setup messages in the admin chat. If an original source message is deleted, that saved item may no longer be copyable.

## Current limits

Maximum saved items: **20**.
