"""
Telegram bot entry point.
Run: python run_telegram.py
"""
import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from telegram_bot.bot import main

if __name__ == "__main__":
    asyncio.run(main())
