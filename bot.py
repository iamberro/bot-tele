# -*- coding: utf-8 -*-
import time
import logging
import os
import re
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler, filters,
                          CallbackContext, CallbackQueryHandler)
import yt_dlp
import imageio_ffmpeg
from urllib.parse import quote
from datetime import datetime, timedelta
import random

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Konfigurasi Utama ---
TOKEN = os.environ.get('TOKEN')
TELEGRAM_MAX_SIZE = 50 * 1024 * 1024  # 50MB

# --- Pesan-pesan Bot ---
LOADING_MESSAGES = [
    "🔎 Mencari media...",
    "⚡️ Mengunduh dengan kecepatan tinggi...",
    "⏳ Memproses permintaan Anda...",
    "📥 Sedang mengunduh file...",
    "🎬 Menyiapkan video dan audio untukmu...",
]

# --- Fungsi Bantuan ---

async def get_video_metadata(url: str) -> dict | None:
    """Mengambil judul dari URL video menggunakan yt-dlp."""
    logger.info(f"Mengambil metadata untuk URL: {url}")
    ydl_opts = {'quiet': True, 'skip_download': True}
    try:
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(
                None, lambda: ydl.extract_info(url, download=False)
            )
        return {'title': info.get('title', 'Judul Tidak Tersedia')}
    except Exception as e:
        logger.error(f"Gagal mengambil metadata: {e}")
        return None

async def download_media(url: str, format_choice: str, unique_id: str) -> str | None:
    """Mengunduh satu jenis media (video atau audio)."""
    logger.info(f"Memulai download {format_choice} untuk {url}")
    
    ydl_opts = {
        'outtmpl': f'downloads/{unique_id}.%(ext)s',
        'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
        'noplaylist': True,
        'ignoreerrors': True,
        'max_filesize': 150 * 1024 * 1024,
    }

    if format_choice == 'audio':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    else:  # video
        ydl_opts.update({
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
        })

    try:
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
        
        expected_ext = 'mp3' if format_choice == 'audio' else 'mp4'
        downloaded_file = f'downloads/{unique_id}.{expected_ext}'
        
        if os.path.exists(downloaded_file):
            return downloaded_file
        return None
    except Exception as e:
        logger.error(f"Error saat download {format_choice}: {e}")
        return None

# --- Handler Perintah Bot ---

async def start(update: Update, context: CallbackContext) -> None:
    """Mengirim pesan selamat datang."""
    welcome_message = "👋 <b>Selamat datang!</b>\n\nKirimkan saya link video, dan saya akan otomatis mengunduh dan mengirimkan file video (MP4) dan audionya (MP3)."
    await update.message.reply_text(welcome_message, parse_mode='HTML')

# --- Handler Utama ---

async def handle_message(update: Update, context: CallbackContext) -> None:
    """Menangani pesan masuk yang berisi link."""
    url = update.message.text.strip()
    
    if not re.match(r'https?://', url):
        await update.message.reply_text("Itu sepertinya bukan link yang valid.")
        return

    processing_msg = await update.message.reply_text(f"{random.choice(LOADING_MESSAGES)}")

    # Buat ID unik untuk sesi download ini
    unique_id = f"{int(time.time())}_{random.randint(1000, 9999)}"
    
    # Ambil metadata
    metadata = await get_video_metadata(url)
    title = metadata['title'] if metadata else "Media"

    # Jalankan download video dan audio secara bersamaan
    video_task = download_media(url, 'video', f"{unique_id}_vid")
    audio_task = download_media(url, 'audio', f"{unique_id}_aud")
    
    results = await asyncio.gather(video_task, audio_task)
    video_path, audio_path = results

    files_to_delete = [p for p in [video_path, audio_path] if p]

    try:
        if not video_path and not audio_path:
            await processing_msg.edit_text("❌ Gagal mengunduh media. Link mungkin tidak valid atau video bersifat pribadi.")
            return

        await processing_msg.edit_text("✅ Download selesai! Mengirim file...")

        # Kirim Video
        if video_path:
            if os.path.getsize(video_path) > TELEGRAM_MAX_SIZE:
                await update.message.reply_text(f"🎬 Video terlalu besar untuk dikirim (batas 50MB).")
            else:
                with open(video_path, 'rb') as video_file:
                    await update.message.reply_video(
                        video=video_file,
                        caption=f"🎬 **{title}**\n\nDiunduh via @{context.bot.username}",
                        parse_mode='Markdown'
                    )
        
        # Kirim Audio
        if audio_path:
            if os.path.getsize(audio_path) > TELEGRAM_MAX_SIZE:
                await update.message.reply_text(f"🎵 Audio terlalu besar untuk dikirim (batas 50MB).")
            else:
                with open(audio_path, 'rb') as audio_file:
                    await update.message.reply_audio(
                        audio=audio_file,
                        title=title,
                        caption=f"🎧 @{context.bot.username}"
                    )

    except Exception as e:
        logger.error(f"Gagal mengirim file: {e}")
        await update.message.reply_text("Terjadi kesalahan saat mengirim file.")
    finally:
        # Hapus pesan "memproses" dan semua file yang di-download
        await processing_msg.delete()
        for file_path in files_to_delete:
            if os.path.exists(file_path):
                os.remove(file_path)

def main() -> None:
    """Menjalankan bot."""
    if not TOKEN:
        logger.error("TOKEN bot tidak ditemukan! Atur di Secrets.")
        return
        
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    application = Application.builder().token(TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Jalankan bot
    logger.info("Bot dimulai...")
    application.run_polling()

if __name__ == '__main__':
    main()