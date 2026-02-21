import os
import re
import logging
from datetime import datetime
import httpx

from telegram import Bot, Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from apscheduler.schedulers.asyncio import AsyncIOScheduler
import google.generativeai as genai


# ------------------ ЛОГИ ------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ------------------ НАСТРОЙКИ ------------------

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

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")


# ------------------ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ------------------

def _strip_html(s: str) -> str:
    s = s.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    s = re.sub(r"<.*?>", "", s, flags=re.DOTALL)
    return s.strip()


async def fetch_channel_posts(channel: str) -> list[str]:
    url = f"https://t.me/s/{channel}"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; TGMonitor/1.0)",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.warning("Non-200 for %s: %s", channel, resp.status_code)
                return []

            text = resp.text
            messages = re.findall(
                r'<div class="tgme_widget_message_text[^"]*">(.*?)</div>',
                text,
                re.DOTALL,
            )
            cleaned = [_strip_html(m) for m in messages if m and _strip_html(m)]
            return cleaned

    except Exception as e:
        logger.exception("fetch_channel_posts error for %s: %s", channel, e)
        return []


# ------------------ АНАЛИТИКА ------------------

async def build_report() -> str:
    chunks = []

    for ch in CHANNELS:
        posts = await fetch_channel_posts(ch)
        sample = posts[-12:]
        block = f"@{ch}\n" + ("\n\n".join(sample) if sample else "(нет данных)")
        chunks.append(block)

    raw = "\n\n" + ("\n\n" + "=" * 40 + "\n\n").join(chunks)

    prompt = (
        "Ты — стратегический аналитик повестки.\n"
        "На основе текстов телеграм-каналов составь структурированный отчет.\n\n"

        "I. ЦЕНТРАЛЬНЫЕ ПРОЦЕССЫ ДНЯ\n"
        "- 1–3 главных смысловых узла, которые реально формируют поле.\n\n"

        "II. АРХИТЕКТУРА ВЛИЯНИЯ\n"
        "- Кто инициирует темы (@каналы).\n"
        "- Кто усиливает.\n"
        "- Кто спорит.\n"
        "- Есть ли синхронизация.\n\n"

        "III. СЛАБЫЕ СИГНАЛЫ\n"
        "- Второстепенные темы, способные вырасти.\n"
        "- Новые формулировки.\n"
        "- Риторические сдвиги.\n\n"

        "IV. РИСКИ И ТОЧКИ НАПРЯЖЕНИЯ\n"
        "- Где возможен конфликт.\n"
        "- Какие нарративы закрепляются.\n"
        "- Где возможен разворот.\n\n"

        "V. ОКНА ВОЗМОЖНОСТЕЙ\n"
        "- Где стратегически можно действовать.\n"
        "- Какие формулировки выгодны.\n\n"

        "VI. КЛЮЧЕВЫЕ ПУБЛИКАЦИИ\n"
        "- По каждому значимому каналу 3–5 публикаций.\n"
        "- Обязательно указывай @канал.\n\n"

        "Будь точным, структурным, без воды.\n\n"

        f"Тексты каналов:\n{raw[:15000]}"
    )

    resp = model.generate_content(prompt)
    text = resp.text if hasattr(resp, "text") else str(resp)

    now = datetime.now().strftime("%d.%m %H:%M")
    header = f"📡 TG Monitor — стратегическая сводка ({now})\n\n"

    return header + text


def split_long_message(text: str, limit: int = 3900):
    parts = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut == -1:
            cut = limit
        parts.append(text[:cut])
        text = text[cut:]
    parts.append(text)
    return parts


# ------------------ КОМАНДЫ ------------------

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот активен. Используй /report для сводки.")


async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Собираю стратегическую сводку…")
    report = await build_report()
    for part in split_long_message(report):
        await update.message.reply_text(part)


# ------------------ MAIN ------------------

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("report", report_cmd))

    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

    async def scheduled_report():
        bot: Bot = app.bot
        report = await build_report()
        for part in split_long_message(report):
            await bot.send_message(chat_id=USER_ID, text=part)

    scheduler.add_job(scheduled_report, "cron", hour=10, minute=0)
    scheduler.add_job(scheduled_report, "cron", hour=15, minute=0)
    scheduler.add_job(scheduled_report, "cron", hour=22, minute=0)

    scheduler.start()

    print("BOT STARTED (polling)")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()