import os
import re
import math
import logging
import asyncio
import subprocess
import requests
import gc
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
import yt_dlp

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

BOT_TOKEN = "8658976742:AAFMmQsqAAOFaxGnkb0dbpyzrG5F1pIbWkc"
MAX_FILE_SIZE_MB = 48.0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👑 *Global Media Downloader Enterprise Ultra*\n\n"
        "⚡ 24/7 Cloud Engine Active!\n"
        "🔗 *Send any link to download!*"
    )
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

def get_video_duration(file_path):
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries',
            'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', file_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return float(result.stdout)
    except Exception:
        return 0

def split_video_lossless(file_path, target_size_mb=45.0):
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    duration = get_video_duration(file_path)
    if duration <= 0 or file_size_mb <= target_size_mb:
        return [file_path]

    num_parts = math.ceil(file_size_mb / target_size_mb)
    part_duration = duration / num_parts
    output_files = []
    base_name, ext = os.path.splitext(file_path)

    for i in range(num_parts):
        start_time = i * part_duration
        out_part = f"{base_name}_part{i+1}{ext}"
        cmd = [
            'ffmpeg', '-y', '-ss', str(start_time),
            '-i', file_path, '-t', str(part_duration),
            '-c', 'copy', '-map', '0', out_part
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(out_part):
            output_files.append(out_part)

    return output_files if output_files else [file_path]

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("❌ Invalid URL!")
        return

    context.user_data['target_url'] = url
    keyboard = [
        [InlineKeyboardButton("⚡ Best Quality", callback_data="fmt_best")],
        [InlineKeyboardButton("🎵 MP3 Audio Only", callback_data="fmt_mp3")]
    ]
    await update.message.reply_text("🎯 Select format:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data
    url = context.user_data.get('target_url')

    if not url:
        await query.message.reply_text("⚠️ Session Expired!")
        return

    status_msg = await query.message.reply_text("⚡ Processing Media...")
    format_spec = 'bestaudio/best' if choice == "fmt_mp3" else 'bestvideo+bestaudio/best/mp4'

    ydl_opts = {
        'format': format_spec,
        'outtmpl': 'media_%(id)s.%(ext)s',
        'quiet': True,
        'nocheckcertificate': True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        if choice == "fmt_mp3":
            file_path = os.path.splitext(file_path)[0] + ".mp3"

        if file_path and os.path.exists(file_path):
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

            if file_size_mb > MAX_FILE_SIZE_MB and choice != "fmt_mp3":
                await status_msg.edit_text("⚙️ Splitting Large File...")
                parts = split_video_lossless(file_path)
                for part in parts:
                    with open(part, 'rb') as vf:
                        await query.message.reply_video(video=vf)
                    if os.path.exists(part): os.remove(part)
                await status_msg.delete()
                return

            await status_msg.edit_text("📤 Uploading...")
            with open(file_path, 'rb') as f:
                if choice == "fmt_mp3":
                    await query.message.reply_audio(audio=f)
                else:
                    await query.message.reply_video(video=f)

            if os.path.exists(file_path): os.remove(file_path)
            await status_msg.delete()
            return
    except Exception as e:
        logging.error(f"Error: {e}")

    await status_msg.edit_text("⚠️ Download Failed!")

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(button_callback))
    print("🚀 Bot Running 24/7...")
    app.run_polling(drop_pending_updates=True)
