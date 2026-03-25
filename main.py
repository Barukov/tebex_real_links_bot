import asyncio
import base64
import logging
import os
from typing import Dict

import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("tebex-real-links-bot")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
TEBEX_PUBLIC_TOKEN = os.getenv("TEBEX_PUBLIC_TOKEN", "").strip()
TEBEX_PRIVATE_KEY = os.getenv("TEBEX_PRIVATE_KEY", "").strip()
TEBEX_STORE_IDENTIFIER = os.getenv("TEBEX_STORE_IDENTIFIER", "").strip()
PACKAGE_ID = os.getenv("PACKAGE_ID", "").strip()

BASE_URL = "https://headless.tebex.io/api"

for name, value in {
    "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
    "TEBEX_PUBLIC_TOKEN": TEBEX_PUBLIC_TOKEN,
    "TEBEX_PRIVATE_KEY": TEBEX_PRIVATE_KEY,
    "TEBEX_STORE_IDENTIFIER": TEBEX_STORE_IDENTIFIER,
    "PACKAGE_ID": PACKAGE_ID,
}.items():
    if not value:
        raise RuntimeError(f"Missing env: {name}")

def is_admin(user_id: int) -> bool:
    return (not ADMIN_IDS) or (user_id in ADMIN_IDS)

def auth_headers() -> Dict[str, str]:
    token = base64.b64encode(
        f"{TEBEX_PUBLIC_TOKEN}:{TEBEX_PRIVATE_KEY}".encode("utf-8")
    ).decode("utf-8")
    return {
        "Authorization": f"Basic {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

def tebex_post(path: str, payload: Dict) -> Dict:
    url = f"{BASE_URL}{path}"
    r = requests.post(url, headers=auth_headers(), json=payload, timeout=30)
    r.raise_for_status()
    return r.json() if r.text.strip() else {}

def tebex_get(path: str) -> Dict:
    url = f"{BASE_URL}{path}"
    r = requests.get(url, headers=auth_headers(), timeout=30)
    r.raise_for_status()
    return r.json()

def create_checkout_link(username: str, created_by: int) -> str:
    basket_payload = {
        "complete_url": f"https://{TEBEX_STORE_IDENTIFIER}.tebex.io/",
        "cancel_url": f"https://{TEBEX_STORE_IDENTIFIER}.tebex.io/",
        "complete_auto_redirect": False,
        "username": username,
        "custom": {
            "created_by_telegram": str(created_by),
            "minecraft_username": username,
        },
    }
    basket = tebex_post(f"/accounts/{TEBEX_PUBLIC_TOKEN}/baskets", basket_payload).get("data", {})
    basket_ident = basket.get("ident")
    if not basket_ident:
        raise RuntimeError("Tebex did not return basket ident")

    tebex_post(f"/baskets/{basket_ident}/packages", {"package_id": str(PACKAGE_ID), "quantity": 1})
    basket_info = tebex_get(f"/accounts/{TEBEX_PUBLIC_TOKEN}/baskets/{basket_ident}").get("data", {})
    link = (((basket_info.get("links") or {}).get("checkout")) or "").strip()
    if not link:
        raise RuntimeError("Tebex did not return checkout link")
    return link

def split_chunks(lines, max_len=3500):
    out = []
    current = ""
    for line in lines:
        candidate = current + line + "\n"
        if len(candidate) > max_len and current:
            out.append(current.rstrip())
            current = line + "\n"
        else:
            current = candidate
    if current:
        out.append(current.rstrip())
    return out

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "Бот работает.\n\nКоманда:\n/links <количество> <ник>\n\nПример:\n/links 10 Steve123"
    )

async def cmd_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Используй: /links <количество> <ник>\nПример: /links 10 Steve123")
        return
    try:
        count = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Количество должно быть числом.")
        return
    if count < 1 or count > 25:
        await update.message.reply_text("Можно сделать от 1 до 25 ссылок за раз.")
        return

    username = context.args[1].strip()
    if not username:
        await update.message.reply_text("Укажи ник Minecraft.")
        return

    await update.message.reply_text(f"Генерирую {count} ссылок для ника {username}...")
    lines = [f"Ник: {username}", f"Количество: {count}", ""]
    success = 0

    for i in range(1, count + 1):
        try:
            link = await asyncio.to_thread(create_checkout_link, username, update.effective_user.id)
            lines.append(f"{i}. {link}")
            success += 1
            await asyncio.sleep(0.35)
        except Exception as e:
            log.exception("Failed on link %s", i)
            lines.append(f"{i}. ОШИБКА: {e}")

    for part in split_chunks(lines):
        await update.message.reply_text(part, disable_web_page_preview=True)

    await update.message.reply_text(f"Готово. Успешно: {success}/{count}")

async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("links", cmd_links))
    log.info("Bot started")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
