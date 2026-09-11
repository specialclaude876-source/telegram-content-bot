# Telegram Content Delivery Bot — Railway Ready

## What it does

- `/start` sends the saved package to normal users.
- Only one configured Telegram ID is the admin.
- Normal users have no admin controls.
- Admin can save up to **20 items** in exact order.
- Supports Telegram messages that can be copied by the Bot API: files, photos, videos, text, captions, and supported spoiler media.
- View-once/self-destructing media is not used.
- SQLite stores the package.
- Designed for Railway with a persistent Volume.

## Admin workflow

1. Send `/setup`
2. Send up to 20 items in the desired order.
3. Send `/done`
4. Users send `/start`

Other admin commands:

- `/status`
- `/clear`

## Railway

Add these Variables:

```text
BOT_TOKEN=YOUR_BOTFATHER_TOKEN
ADMIN_ID=YOUR_NUMERIC_TELEGRAM_USER_ID
DB_PATH=/app/data/bot.db
```

Attach a Railway Volume with mount path:

```text
/app/data
```

The included `railway.toml` and `Procfile` both use:

```text
python main.py
```

Do not upload `.env` to GitHub.

## GitHub structure

```text
README.md
main.py
requirements.txt
.env.example
.gitignore
Procfile
railway.toml
run_termux.sh
```

## Termux

```bash
pip install -r requirements.txt
cp .env.example .env
nano .env
python main.py
```

After entering your real `.env` values, do not run `cp .env.example .env` again because that would overwrite them.

## Important

The bot saves references to the admin's source messages and later copies those messages to users. Keep the original setup messages in the admin chat. If a source message is deleted or Telegram does not permit it to be copied, that item cannot be delivered.
