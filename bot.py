import os
import asyncio
import logging
from datetime import datetime, timedelta
import httpx
from telegram import Bot
from telegram.error import TelegramError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import google.generativeai as genai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
USER_ID = int(os.environ.get("USER_ID", "1151040138"))

CHANNELS = [
    "russicaru",
    "TheInsider",
    "ejdailyru",
    "russ_orientalist",
    "brieflyru",
    "tolk_tolk",
    "istrkalkglk",
    "SergdfcEfimsa",
]

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")


async def fetch_channel_posts(channel: str, hours: int = 8) -> list[str]:
    url = f"https://t.me/s/{channel}"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; TGMonitor/1.0)",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }
    posts = []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                return posts
            text = resp.text
            import re
            messages = re.findall(
    r'<div class="tgme_widget_message_text">(.*?)</div>',
    text,
    re.DOTALL
)
except Exception as e:
    print("fetch_channel_posts error:", e)
    return posts
