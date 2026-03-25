import asyncio
import base64
import logging
import os
from typing import Dict

import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS","").split(",") if x}
TEBEX_PUBLIC_TOKEN = os.getenv("TEBEX_PUBLIC_TOKEN")
TEBEX_PRIVATE_KEY = os.getenv("TEBEX_PRIVATE_KEY")
TEBEX_STORE_IDENTIFIER = os.getenv("TEBEX_STORE_IDENTIFIER")
PACKAGE_170 = os.getenv("PACKAGE_170")
PACKAGE_250 = os.getenv("PACKAGE_250")

BASE_URL = "https://headless.tebex.io/api"

def auth_headers():
    token = base64.b64encode(f"{TEBEX_PUBLIC_TOKEN}:{TEBEX_PRIVATE_KEY}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

def tebex_post(path, payload):
    return requests.post(BASE_URL+path, headers=auth_headers(), json=payload).json()

def tebex_get(path):
    return requests.get(BASE_URL+path, headers=auth_headers()).json()

def create_link(username, package_id):
    basket = tebex_post(f"/accounts/{TEBEX_PUBLIC_TOKEN}/baskets", {
        "complete_url": f"https://{TEBEX_STORE_IDENTIFIER}.tebex.io/",
        "cancel_url": f"https://{TEBEX_STORE_IDENTIFIER}.tebex.io/",
        "username": username
    })["data"]["ident"]

    tebex_post(f"/baskets/{basket}/packages", {"package_id": package_id})

    link = tebex_get(f"/accounts/{TEBEX_PUBLIC_TOKEN}/baskets/{basket}")["data"]["links"]["checkout"]

    return link + "/payment"

def get_package(price):
    return PACKAGE_170 if price=="170" else PACKAGE_250

async def links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = int(context.args[0])
    price = context.args[1]
    username = context.args[2]

    package = get_package(price)

    result = []
    for i in range(count):
        link = await asyncio.to_thread(create_link, username, package)
        result.append(link)

    await update.message.reply_text("\n".join(result))

async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("links", links))
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
