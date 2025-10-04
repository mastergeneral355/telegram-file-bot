import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp
import asyncio

# Get your token from Render environment variable
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

# ---------------- Handlers ----------------

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello! Send me a video URL (YouTube, TikTok, etc.), and I will download it for you."
    )

async def download_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    status_msg = await update.message.reply_text("Starting download... ⏳")

    filename = "video.mp4"

    # Define progress hook for yt-dlp
    def progress_hook(d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '').strip()
            asyncio.run_coroutine_threadsafe(
                status_msg.edit_text(f"Downloading: {percent}"), context.application.loop
            )
        elif d['status'] == 'finished':
            asyncio.run_coroutine_threadsafe(
                status_msg.edit_text("Download finished! Sending video... 📤"), context.application.loop
            )

    ydl_opts = {
        "outtmpl": filename,
        "format": "best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "progress_hooks": [progress_hook],
        "quiet": True,
    }

    try:
        # Download using yt-dlp
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Send the downloaded video
        await update.message.reply_video(video=open(filename, "rb"))
        os.remove(filename)
        await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"Failed to download the video: {e}")
        print(f"Download error: {e}")

# ---------------- Main ----------------

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_and_send))

    print("Bot running...")
    app.run_polling()
