#!/data/data/com.termux/files/usr/bin/bash
set -e
echo "Installing dependencies..."
pip install -r requirements.txt
echo "Starting Telegram bot..."
python bot/main.py
