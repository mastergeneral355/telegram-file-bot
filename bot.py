import asyncio
import tempfile
import os
import socket
import ipaddress
from urllib.parse import urlparse

import aiohttp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# === CONFIG ===
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")  # Your token will come from Render environment variable
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024  # 100 MB max per file
# ==============

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi — send me a direct file URL (http/https) and I'll download it and send it back to you."
    )

def is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and parsed.netloc != ""
    except Exception:
        return False

def is_private_network(host: str) -> bool:
    try:
        for res in socket.getaddrinfo(host, None):
            ip = res[4][0]
            ip_obj = ipaddress.ip_address(ip)
            if (ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or
                    ip_obj.is_reserved or ip_obj.is_multicast):
                return True
        return False
    except Exception:
        return True

async def download_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.strip()
    if msg.startswith("/get"):
        parts = msg.split(maxsplit=1)
        if len(parts) < 2:
            await update.message.reply_text("Usage: /get <direct-file-url>")
            return
        url = parts[1].strip()
    else:
        url = msg

    if not is_valid_url(url):
        await update.message.reply_text("That's not a valid http/https URL.")
        return

    host = urlparse(url).hostname or ""
    if is_private_network(host):
        await update.message.reply_text("I cannot download from internal or private network addresses.")
        return

    await update.message.reply_text("Starting download...")

    try:
        timeout = aiohttp.ClientTimeout(total=60*30)  # 30 minutes max
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    await update.message.reply_text(f"Failed to download. HTTP status {resp.status}.")
                    return

                content_length = resp.headers.get("Content-Length")
                if content_length is not None:
                    try:
                        content_length = int(content_length)
                        if content_length > MAX_DOWNLOAD_BYTES:
                            await update.message.reply_text(
                                f"File too large ({content_length} bytes). Max allowed: {MAX_DOWNLOAD_BYTES} bytes."
                            )
                            return
                    except ValueError:
                        pass

                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    total = 0
                    chunk_size = 1024 * 64
                    while True:
                        chunk = await resp.content.read(chunk_size)
                        if not chunk:
                            break
                        tmp.write(chunk)
                        total += len(chunk)
                        if total > MAX_DOWNLOAD_BYTES:
                            tmp_name = tmp.name
                            tmp.close()
                            os.unlink(tmp_name)
                            await update.message.reply_text("Download exceeded max allowed size; aborted.")
                            return
                    tmp_path = tmp.name

        caption = f"Downloaded from: {url}"
        with open(tmp_path, "rb") as f:
            await update.message.reply_document(document=f, filename=os.path.basename(urlparse(url).path) or "file", caption=caption)

        os.unlink(tmp_path)

    except Exception as e:
        await update.message.reply_text(f"Error while downloading or sending: {e}")

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("get", download_and_send))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_and_send))

    print("Bot running...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
