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
MAX_FILE_SIZE = 150 * 1024 * 1024
TELEGRAM_MAX_SIZE = 50 * 1024 * 1024

# --- Variabel & Pesan-pesan Bot ---
message_timestamps = {}
LOADING_MESSAGES = [
    "🔎 Mencari video terbaik...", "⚡️ Mengunduh dengan kecepatan tinggi...",
    "⏳ Memproses permintaan Anda...", "📥 Sedang mengunduh konten...",
    "🎬 Menyiapkan video untuk Anda...", " sabar ya, ini bakal keren banget!",
    "💾 Menyimpan video ke database...", "🚀 Proses hampir selesai...",
    "🧹 Membersihkan cache...", "🎞 Rendering video terbaik..."
]
COMPLETION_MESSAGES = [
    "✅ Selesai! Video siap dinikmati!", "🎉 Berhasil! Silakan ditonton!",
    "✨ Video sudah siap bosku!", "🔥 Mantap! Download berhasil!",
    "💯 Kualitas HD sudah tersedia!", "👍 Proses selesai dengan sempurna!",
    "📲 Video siap dibagikan!", "👌 Kerja bagus! Video sudah jadi!",
    "😎 Keren banget nih videonya!", "🤩 Wow! Hasilnya memuaskan!"
]
ERROR_MESSAGES = {
    'generic': " Maaf, ada kesalahan saat memproses video. Coba lagi ya!",
    'private': " Video ini bersifat private atau memerlukan login.",
    'unavailable': " Video tidak tersedia atau dihapus.",
    'invalid': " Link yang Anda berikan tidak valid.",
    'size': " Ukuran video melebihi batas maksimal (50MB).",
    'timeout': "️ Proses terlalu lama. Coba link lain ya!",
    'compression': " Gagal mengkompresi video. Coba link lain!"
}

# ==============================================================================
# ======================== FUNGSI-FUNGSI COMMAND HANDLER =======================
# ==============================================================================

async def start(update: Update, context: CallbackContext) -> None:
    welcome_message = """
<b>Selamat datang di Berro Downloader!</b> 

Saya bisa mengunduh video & audio dari:
- YouTube (video biasa/shorts)
- TikTok (termasuk link singkat)
- Facebook (reels/feed videos)
- Instagram (reels/feed)

<b>Cara Pakai:</b>
Kirim link video yang ingin diunduh, dan saya akan mengirimkan file video (MP4) dan audionya (MP3) secara otomatis.

Tekan /help untuk bantuan lebih lanjut.
"""
    keyboard = [[
        InlineKeyboardButton(" Group Support", url="https://t.me/yourgroup")
    ], [
        InlineKeyboardButton(" Panduan", url="https://t.me/yourchannel")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_message,
                                     parse_mode='HTML',
                                     reply_markup=reply_markup)

async def help_command(update: Update, context: CallbackContext) -> None:
    help_text = """
<b> Bantuan Penggunaan Bot</b>

<b>Perintah yang tersedia:</b>
/start - Memulai bot dan menampilkan pesan selamat datang
/help - Menampilkan pesan bantuan ini
/status - Memeriksa status bot

<b>Pemecahan Masalah:</b>
1. Jika media gagal diunduh:
   - Pastikan link benar dan video bersifat publik.
   - Coba lagi setelah beberapa saat.

2. Jika file terlalu besar:
   - Bot tidak akan mengirim file di atas 50MB.
   - Bot akan mencoba kompresi otomatis untuk video jika memungkinkan.

<b>Support:</b>
Untuk pertanyaan lebih lanjut, hubungi @berrontosaurus
"""
    await update.message.reply_text(help_text, parse_mode='HTML')

async def status_command(update: Update, context: CallbackContext) -> None:
    status_message = """
<b> Status Bot</b>

<b>Versi:</b> 2.1 (Fitur MP3)
<b>Status:</b> Online 
<b>Update Terakhir:</b> {}
""".format(datetime.now().strftime("%d %B %Y"))
    await update.message.reply_text(status_message, parse_mode='HTML')

# ==============================================================================
# ======================== FUNGSI-FUNGSI BANTUAN (HELPERS) =====================
# ==============================================================================

def get_random_loading_message():
    return random.choice(LOADING_MESSAGES)

def get_random_completion_message():
    return random.choice(COMPLETION_MESSAGES)

async def get_video_metadata(url: str) -> dict | None:
    logger.info(f"Mengambil metadata untuk URL: {url}")
    ydl_opts = {'quiet': True, 'skip_download': True, 'cookiefile': 'youtube_cookies.txt'}
    try:
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
        return {'title': info.get('title', 'Judul Tidak Tersedia')}
    except Exception as e:
        logger.error(f"Gagal mengambil metadata: {e}")
        return None

def is_facebook_url(url: str) -> bool:
    patterns = [
        r'https?://(?:www\.|m\.|mbasic\.)?facebook\.com/.+/videos/.+',
        r'https?://(?:www\.|m\.|mbasic\.)?facebook\.com/.+/video/.+',
        r'https?://(?:www\.|m\.|mbasic\.)?facebook\.com/watch/?\?v=.+',
        r'https?://(?:www\.|m\.|mbasic\.)?facebook\.com/reel/.+',
        r'https?://fb\.watch/.+', r'https?://www\.facebook\.com/share/.+'
    ]
    return any(re.search(pattern, url) for pattern in patterns)

def is_instagram_url(url: str) -> bool:
    patterns = [
        r'https?://(?:www\.)?instagram\.com/p/.+',
        r'https?://(?:www\.)?instagram\.com/reel/.+',
        r'https?://(?:www\.)?instagram\.com/tv/.+',
        r'https?://(?:www\.)?instagram\.com/stories/.+',
        r'https?://instagr\.am/p/.+', r'https?://instagr\.am/reel/.+'
    ]
    return any(re.search(pattern, url) for pattern in patterns)

async def compress_video(input_path: str) -> str | None:
    output_path = os.path.splitext(input_path)[0] + "_compressed.mp4"
    try:
        original_size = os.path.getsize(input_path)
        if original_size <= TELEGRAM_MAX_SIZE:
            return input_path
        logger.info(f"File video terlalu besar ({original_size / 1024 / 1024:.2f}MB), mengompres...")
        command = [
            imageio_ffmpeg.get_ffmpeg_exe(), '-i', input_path,
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '28',
            '-vf', 'scale=-2:720', '-movflags', '+faststart',
            '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '96k',
            '-y', output_path
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        if os.path.exists(output_path):
            logger.info(f"Kompresi berhasil, ukuran baru: {os.path.getsize(output_path) / 1024 / 1024:.2f}MB")
            return output_path
        return None
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg error saat kompresi: {e.stderr.decode()}")
        return None
    except Exception as e:
        logger.error(f"Error kompresi: {str(e)}")
        return None

# ==============================================================================
# ======================== FUNGSI BARU UNTUK DOWNLOAD AUDIO ====================
# ==============================================================================

async def download_audio_only(url: str) -> str | None:
    logger.info(f"Memulai download AUDIO untuk: {url}")
    unique_id = f"{int(time.time())}_{random.randint(1000, 9999)}"
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'downloads/{unique_id}.%(ext)s',
        'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
        'noplaylist': True, 'ignoreerrors': True, 'max_filesize': MAX_FILE_SIZE,
        'cookiefile': 'youtube_cookies.txt',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
        expected_path = f'downloads/{unique_id}.mp3'
        if os.path.exists(expected_path):
            return expected_path
        # Fallback jika ekstensi tidak terduga
        for file in os.listdir('downloads'):
            if file.startswith(unique_id):
                return os.path.join('downloads', file)
        return None
    except Exception as e:
        logger.error(f"Error saat download audio: {e}")
        return None

# ==============================================================================
# ======================== FUNGSI DOWNLOAD VIDEO LAMA ANDA =====================
# ==============================================================================
# Semua fungsi download video asli Anda dipertahankan di sini tanpa perubahan.

def extract_youtube_video_id(url: str) -> str | None:
    try:
        if '/shorts/' in url.lower():
            match = re.search(r'/shorts/([^?/]+)', url, re.IGNORECASE)
            if match: return match.group(1)
        if '/live/' in url.lower():
            match = re.search(r'/live/([^?/]+)', url, re.IGNORECASE)
            if match: return match.group(1)
        patterns = [
            r"youtube\.com/watch\?v=([^&]+)", r"youtu\.be/([^?]+)",
            r"youtube\.com/embed/([^/]+)", r"youtube\.com/v/([^/]+)"
        ]
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match: return match.group(1)
        return None
    except Exception as e:
        logger.error(f"Error extracting YouTube video ID: {str(e)}")
        return None

async def download_youtube_ytdlp(url: str) -> str | None:
    logger.info(f"Memulai download VIDEO (yt-dlp) untuk: {url}")
    unique_id = f"{int(time.time())}_{random.randint(1000, 9999)}"
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': f'downloads/{unique_id}.%(ext)s',
        'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
        'merge_output_format': 'mp4',
        'noplaylist': True, 'ignoreerrors': True, 'max_filesize': MAX_FILE_SIZE,
        'cookiefile': 'youtube_cookies.txt',
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
    except Exception as e:
        logger.error(f"Error download_youtube_ytdlp: {e}")
        return None

async def download_youtube(url: str) -> str | None:
    return await download_youtube_ytdlp(url)

async def download_tiktok_ytdlp(url: str) -> str | None:
    logger.info(f"Memulai download VIDEO (yt-dlp) untuk: {url}")
    unique_id = f"{int(time.time())}_{random.randint(1000, 9999)}"
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': f'downloads/{unique_id}.%(ext)s',
        'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
        'merge_output_format': 'mp4',
        'noplaylist': True, 'ignoreerrors': True, 'max_filesize': MAX_FILE_SIZE,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
    except Exception as e:
        logger.error(f"Error download_tiktok_ytdlp: {e}")
        return None

async def download_tiktok(url: str) -> str | None:
    return await download_tiktok_ytdlp(url)

async def download_facebook(url: str) -> str | None:
    logger.info(f"Memulai download VIDEO (yt-dlp) untuk: {url}")
    unique_id = f"{int(time.time())}_{random.randint(1000, 9999)}"
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': f'downloads/{unique_id}.%(ext)s',
        'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
        'merge_output_format': 'mp4',
        'noplaylist': True, 'ignoreerrors': True, 'max_filesize': MAX_FILE_SIZE,
        'cookiefile': 'facebook_cookies.txt',
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
    except Exception as e:
        logger.error(f"Error download_facebook: {e}")
        return None

async def download_instagram(url: str) -> str | None:
    logger.info(f"Memulai download VIDEO (yt-dlp) untuk: {url}")
    unique_id = f"{int(time.time())}_{random.randint(1000, 9999)}"
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': f'downloads/{unique_id}.%(ext)s',
        'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
        'merge_output_format': 'mp4',
        'noplaylist': True, 'ignoreerrors': True, 'max_filesize': MAX_FILE_SIZE,
        'cookiefile': 'instagram_cookies.txt',
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
    except Exception as e:
        logger.error(f"Error download_instagram: {e}")
        return None

# ==============================================================================
# ======================== HANDLER UTAMA (DIRUBAH TOTAL) =======================
# ==============================================================================

async def handle_message(update: Update, context: CallbackContext) -> None:
    url = update.message.text.strip()
    if not re.match(r'https?://', url):
        return

    processing_msg = await update.message.reply_text(f"{get_random_loading_message()}")

    metadata = await get_video_metadata(url)
    title = metadata['title'] if metadata else "Media"

    # Tentukan fungsi download video yang akan digunakan
    video_downloader_func = None
    if 'youtube.com' in url or 'youtu.be' in url:
        video_downloader_func = download_youtube(url)
    elif 'tiktok.com' in url or 'vt.tiktok.com' in url:
        video_downloader_func = download_tiktok(url)
    elif is_facebook_url(url):
        video_downloader_func = download_facebook(url)
    elif is_instagram_url(url):
        video_downloader_func = download_instagram(url)
    else:
        await processing_msg.edit_text("❌ Format link tidak dikenali.")
        return

    # Jalankan download video dan audio secara bersamaan
    audio_downloader_func = download_audio_only(url)
    
    await processing_msg.edit_text("📥 Mengunduh video dan audio...")
    results = await asyncio.gather(video_downloader_func, audio_downloader_func, return_exceptions=True)
    video_path, audio_path = results

    # Siapkan daftar file untuk dihapus nanti
    files_to_delete = []
    if isinstance(video_path, str) and os.path.exists(video_path): files_to_delete.append(video_path)
    if isinstance(audio_path, str) and os.path.exists(audio_path): files_to_delete.append(audio_path)

    try:
        if not files_to_delete:
            await processing_msg.edit_text("❌ Gagal mengunduh media. Link mungkin tidak valid atau video bersifat pribadi.")
            return

        await processing_msg.edit_text("✅ Download selesai! Mengirim file...")

        # Kirim Video
        if isinstance(video_path, str) and os.path.exists(video_path):
            if os.path.getsize(video_path) > TELEGRAM_MAX_SIZE:
                logger.info("Video terlalu besar, mencoba kompresi...")
                compressed_path = await compress_video(video_path)
                if compressed_path and os.path.getsize(compressed_path) <= TELEGRAM_MAX_SIZE:
                    with open(compressed_path, 'rb') as video_file:
                        await update.message.reply_video(video=video_file, caption=f"🎬 {title} (dikompres)")
                    files_to_delete.append(compressed_path)
                else:
                    await update.message.reply_text(f"🎬 Video terlalu besar untuk dikirim (batas 50MB).")
            else:
                with open(video_path, 'rb') as video_file:
                    await update.message.reply_video(video=video_file, caption=f"🎬 {title}")
        else:
            logger.error(f"Proses video gagal atau file tidak ditemukan: {video_path}")
            await update.message.reply_text("Gagal memproses file video.")

        # Kirim Audio
        if isinstance(audio_path, str) and os.path.exists(audio_path):
            if os.path.getsize(audio_path) > TELEGRAM_MAX_SIZE:
                await update.message.reply_text(f"🎵 Audio terlalu besar untuk dikirim (batas 50MB).")
            else:
                with open(audio_path, 'rb') as audio_file:
                    await update.message.reply_audio(audio=audio_file, title=title)
        else:
            logger.error(f"Proses audio gagal atau file tidak ditemukan: {audio_path}")
            await update.message.reply_text("Gagal memproses file audio.")
            
    except Exception as e:
        logger.error(f"Gagal mengirim file: {e}")
        await update.message.reply_text("Terjadi kesalahan saat mengirim file.")
    finally:
        await processing_msg.delete()
        for file_path in files_to_delete:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"File dihapus: {file_path}")
                except Exception as e:
                    logger.error(f"Gagal menghapus file {file_path}: {e}")

# ==============================================================================
# ======================== FUNGSI UTAMA (MAIN) =================================
# ==============================================================================

def main() -> None:
    if not TOKEN:
        logger.error("TOKEN bot tidak ditemukan! Atur di Secrets.")
        return
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    application = Application.builder().token(TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    # handler tombol tidak diperlukan lagi karena alur kerja diubah

    logger.info("Bot dimulai...")
    application.run_polling()

if __name__ == '__main__':
    main()