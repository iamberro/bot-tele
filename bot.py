# -*- coding: utf-8 -*-
import time
import logging
import os
import subprocess
import re
import json
import http.client
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler, filters,
                          CallbackContext, CallbackQueryHandler)
import yt_dlp
import imageio_ffmpeg
import httpx
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
RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY')
TELEGRAM_MAX_SIZE = 50 * 1024 * 1024  # 50MB

# --- Pesan-pesan Bot ---
LOADING_MESSAGES = [
    "🔎 Mencari video terbaik...",
    "⚡️ Mengunduh dengan kecepatan tinggi...",
    "⏳ Memproses permintaan Anda...",
    "📥 Sedang mengunduh konten...",
    "🎬 Menyiapkan media untuk Anda...",
    " sabar ya, ini bakal keren banget!",
    "💾 Menyimpan file...",
    "🚀 Proses hampir selesai...",
]
COMPLETION_MESSAGES = [
    "✅ Selesai! Siap dinikmati!",
    "🎉 Berhasil! Silakan diputar!",
    "✨ Sudah siap bosku!",
    "🔥 Mantap! Download berhasil!",
    "💯 Kualitas terbaik sudah tersedia!",
]

# --- Fungsi Universal untuk Download ---

async def download_media(url: str, format_choice: str) -> str | None:
    """
    Mengunduh media dari URL sebagai video (mp4) atau audio (mp3).
    """
    logger.info(f"Memulai download untuk URL: {url} dengan format: {format_choice}")
    
    unique_id = f"{int(time.time())}_{random.randint(1000, 9999)}"
    
    ydl_opts = {
        'outtmpl': f'downloads/{unique_id}.%(ext)s',
        'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
        'noplaylist': True,
        'ignoreerrors': True,
        'max_filesize': 150 * 1024 * 1024, # 150MB
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
    else: # format_choice == 'video'
        ydl_opts.update({
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
        })

    try:
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(
                None, lambda: ydl.extract_info(url, download=True)
            )
            
            if not info:
                logger.error("Gagal mendapatkan info dari yt-dlp.")
                return None

            # Cari file yang sudah di-download
            expected_ext = 'mp3' if format_choice == 'audio' else 'mp4'
            downloaded_file = f'downloads/{unique_id}.{expected_ext}'
            
            if os.path.exists(downloaded_file):
                return downloaded_file
            else:
                # Cek jika ada file lain dengan ID yang sama (misal: .webm)
                for file in os.listdir('downloads'):
                    if file.startswith(unique_id):
                        return os.path.join('downloads', file)
                logger.error(f"File yang diunduh tidak ditemukan: {downloaded_file}")
                return None

    except Exception as e:
        logger.error(f"Error saat download media: {e}")
        return None

# --- Fungsi Bantuan Lainnya ---

async def get_video_metadata(url: str) -> dict | None:
    """Mengambil judul dan hashtag dari URL video menggunakan yt-dlp."""
    logger.info(f"Mengambil metadata untuk URL: {url}")
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'force_generic_extractor': False,
    }
    try:
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(
                None, lambda: ydl.extract_info(url, download=False)
            )
        title = info.get('title', 'Judul Tidak Tersedia')
        description = info.get('description', '')
        hashtags = info.get('hashtags', [])
        if not hashtags:
            full_text = f"{title} {description}"
            found_hashtags = re.findall(r'#(\w+)', full_text)
            if found_hashtags:
                hashtags = list(dict.fromkeys(found_hashtags))
        return {'title': title, 'hashtags': hashtags}
    except Exception as e:
        logger.error(f"Gagal mengambil metadata: {e}")
        return None

# --- Handler Perintah Bot ---

async def start(update: Update, context: CallbackContext) -> None:
    """Mengirim pesan selamat datang."""
    welcome_message = "👋 <b>Selamat datang di Berro Downloader!</b>\n\nKirimkan saya link video dari YouTube, TikTok, Instagram, atau Facebook, dan saya akan memberikan pilihan untuk mengunduhnya sebagai video (MP4) atau audio (MP3)."
    await update.message.reply_text(welcome_message, parse_mode='HTML')

# --- Handler Utama ---

async def handle_message(update: Update, context: CallbackContext) -> None:
    """Menangani pesan masuk yang berisi link."""
    url = update.message.text.strip()
    
    # Validasi URL sederhana
    if not re.match(r'https?://', url):
        await update.message.reply_text("Hmm, sepertinya itu bukan link yang valid. Coba lagi ya.")
        return

    keyboard = [
        [
            InlineKeyboardButton("🎬 Video (MP4)", callback_data=f"dl_video"),
            InlineKeyboardButton("🎵 Audio (MP3)", callback_data=f"dl_audio"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("Pilih format yang ingin kamu unduh:", reply_markup=reply_markup)


async def button_handler(update: Update, context: CallbackContext) -> None:
    """Menangani pilihan format dari tombol."""
    query = update.callback_query
    await query.answer()

    format_choice = query.data.split('_')[1] # 'video' or 'audio'
    original_message = query.message.reply_to_message

    if not original_message or not original_message.text:
        await query.edit_message_text("❌ Gagal! Pesan asli yang berisi link tidak ditemukan.")
        return

    url = original_message.text.strip()
    
    await query.edit_message_text(f"{random.choice(LOADING_MESSAGES)}")

    # Ambil metadata
    metadata = await get_video_metadata(url)
    fallback_title = "Media"
    video_title = metadata['title'] if metadata and metadata.get('title') else fallback_title

    # Proses download
    file_path = await download_media(url, format_choice)

    if not file_path:
        await query.edit_message_text("❌ Maaf, gagal mengunduh media. Link mungkin tidak valid atau video bersifat pribadi.")
        return

    file_size = os.path.getsize(file_path)
    if file_size > TELEGRAM_MAX_SIZE:
        await query.edit_message_text(f" Ukuran file ({file_size / 1024 / 1024:.1f}MB) melebihi batas 50MB.")
        os.remove(file_path)
        return
        
    await query.edit_message_text(f"✅ Download selesai! Mengirim file...")

    # Kirim file sesuai format
    try:
        if format_choice == 'audio':
            with open(file_path, 'rb') as audio_file:
                await original_message.reply_audio(
                    audio=audio_file,
                    title=video_title,
                    caption=f"🎧 @{context.bot.username}"
                )
        else: # video
            with open(file_path, 'rb') as video_file:
                await original_message.reply_video(
                    video=video_file,
                    caption=f"🎬 @{context.bot.username}"
                )
    except Exception as e:
        logger.error(f"Gagal mengirim file: {e}")
        await original_message.reply_text("Gagal mengirim file. Mungkin ada masalah dengan formatnya.")
    finally:
        # Hapus pesan tombol dan file
        await query.delete_message()
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
    application.add_handler(CallbackQueryHandler(button_handler, pattern=r'^dl_'))

    # Jalankan bot
    logger.info("Bot dimulai...")
    application.run_polling()

if __name__ == '__main__':
    main()