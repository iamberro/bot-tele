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
# (Pesan-pesan ini tidak dipakai lagi, karena sekarang pesan status lebih dinamis)

# ==============================================================================
# ======================== FUNGSI-FUNGSI COMMAND HANDLER =======================
# ==============================================================================

async def start(update: Update, context: CallbackContext) -> None:
    welcome_message = """
🤟 <b>Yo, bro! Kenalin, Berro Downloader.</b>

Gue siap bantu sikat video & musik dari:
- YouTube
- TikTok
- Instagram
- Facebook

Langsung aja kirim link-nya ke gue, nanti gue kirim balik file video (MP4) sama audionya (MP3). Simpel, kan?

Kalau butuh bantuan, ketik /help.
"""
    await update.message.reply_text(welcome_message, parse_mode='HTML')

async def help_command(update: Update, context: CallbackContext) -> None:
    help_text = """
🤔 <b>Butuh Bantuan? Tenang, gue bantu.</b>

<b>Perintah Dasar:</b>
/start - Sapa gue lagi
/help - Nampilin pesan ini

<b>Kalau Gagal Download:</b>
1.  <b>Cek Link</b>: Pastiin link-nya bener dan videonya gak di-private.
2.  <b>Coba Lagi</b>: Kadang server lagi sibuk, coba kirim ulang link-nya.
3.  <b>Batas Ukuran</b>: Gue gak bisa kirim file di atas 50MB. Kalau videonya kepanjangan, kemungkinan gagal.

Kalau masih ada masalah, kontak aja developernya di @berrontosaurus. Santai!
"""
    await update.message.reply_text(help_text, parse_mode='HTML')

# ==============================================================================
# ======================== FUNGSI-FUNGSI BANTUAN (HELPERS) =====================
# ==============================================================================

async def get_video_metadata(url: str) -> dict | None:
    logger.info(f"Mengambil metadata untuk URL: {url}")
    ydl_opts = {'quiet': True, 'skip_download': True, 'cookiefile': 'youtube_cookies.txt'}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        title = info.get('title', 'Judul Tidak Ditemukan')
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
# ======================== FUNGSI DOWNLOAD AUDIO & VIDEO =======================
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
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
        expected_path = f'downloads/{unique_id}.mp3'
        if os.path.exists(expected_path):
            return expected_path
        for file in os.listdir('downloads'):
            if file.startswith(unique_id): return os.path.join('downloads', file)
        return None
    except Exception as e:
        logger.error(f"Error saat download audio: {e}")
        return None

async def download_video(url: str) -> str | None:
    logger.info(f"Memulai download VIDEO untuk: {url}")
    unique_id = f"{int(time.time())}_{random.randint(1000, 9999)}"
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': f'downloads/{unique_id}.%(ext)s',
        'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
        'merge_output_format': 'mp4',
        'noplaylist': True, 'ignoreerrors': True, 'max_filesize': MAX_FILE_SIZE,
        'cookiefile': 'youtube_cookies.txt', # Juga berlaku untuk platform lain
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
    except Exception as e:
        logger.error(f"Error download_video: {e}")
        return None

# ==============================================================================
# ======================== HANDLER UTAMA (YANG SUDAH CEREWET) ==================
# ==============================================================================

async def handle_message(update: Update, context: CallbackContext) -> None:
    url = update.message.text.strip()
    if not re.match(r'https?://', url):
        return

    # --- UPDATE: Pesan status yang lebih hidup ---
    processing_msg = await update.message.reply_text("Oke, link diterima! Gue cek dulu ya... 🤔")
    await asyncio.sleep(1)

    metadata = await get_video_metadata(url)
    if not metadata or not metadata.get('title'):
        await processing_msg.edit_text("Waduh, gue gak bisa dapetin info dari link itu, bro. Coba link lain ya.")
        return
        
    title = metadata['title']
    hashtags = metadata.get('hashtags', [])
    
    await processing_msg.edit_text(f"✅ Siip, ketemu! Judulnya: \"<i>{title[:50]}...</i>\".\n\nSekarang, gue sikat file video sama audionya. Sabar bentar... 🚀", parse_mode='HTML')
    await asyncio.sleep(2)

    # Jalankan download video dan audio secara bersamaan
    video_downloader_func = download_video(url)
    audio_downloader_func = download_audio_only(url)
    
    results = await asyncio.gather(video_downloader_func, audio_downloader_func, return_exceptions=True)
    video_path, audio_path = results

    files_to_delete = []
    if isinstance(video_path, str) and os.path.exists(video_path): files_to_delete.append(video_path)
    if isinstance(audio_path, str) and os.path.exists(audio_path): files_to_delete.append(audio_path)

    try:
        if not files_to_delete:
            await processing_msg.edit_text("❌ Gagal total, bro. Kayaknya link-nya bermasalah atau videonya private.")
            return

        await processing_msg.edit_text("🎁 Udah kelar! Lagi gue bungkus buat dikirim ke elu...")
        await asyncio.sleep(1)
        
        # Kirim Video
        if isinstance(video_path, str) and os.path.exists(video_path):
            final_video_path = video_path
            caption_suffix = ""
            if os.path.getsize(video_path) > TELEGRAM_MAX_SIZE:
                await update.message.reply_text("Videonya kegedean nih (diatas 50MB), gue coba kecilin dulu ya...")
                compressed_path = await compress_video(video_path)
                if compressed_path and os.path.getsize(compressed_path) <= TELEGRAM_MAX_SIZE:
                    final_video_path = compressed_path
                    files_to_delete.append(compressed_path)
                    caption_suffix = " (udah dikecilin)"
                else:
                    await update.message.reply_text(f"🎬 Waduh, gagal dikecilin bro. Videonya terlalu besar.")
                    final_video_path = None
            
            if final_video_path:
                with open(final_video_path, 'rb') as video_file:
                    await update.message.reply_video(video=video_file, caption=f"🎬 Nih videonya, bro!{caption_suffix}")
        else:
            await update.message.reply_text("Maaf, file videonya gagal diproses. 😔")

        # Kirim Audio
        if isinstance(audio_path, str) and os.path.exists(audio_path):
            if os.path.getsize(audio_path) > TELEGRAM_MAX_SIZE:
                await update.message.reply_text(f"🎵 Audionya juga kegedean nih, gak bisa dikirim.")
            else:
                with open(audio_path, 'rb') as audio_file:
                    await update.message.reply_audio(audio=audio_file, title=title, caption="🎧 Musiknya, bro!")
        else:
            await update.message.reply_text("Maaf, file audionya gagal diproses. 😔")
        
        # Kirim Pesan Info Terpisah
        hashtags_text = ' '.join([f'#{tag}' for tag in hashtags])
        
        video_size_text = f"Ukuran Video: {os.path.getsize(video_path)/1024/1024:.1f}MB" if isinstance(video_path, str) and os.path.exists(video_path) else "Ukuran Video: Gagal diproses"
        audio_size_text = f"Ukuran Audio: {os.path.getsize(audio_path)/1024/1024:.1f}MB" if isinstance(audio_path, str) and os.path.exists(audio_path) else "Ukuran Audio: Gagal diproses"
            
        info_message = (
            f"<b>{title}</b>\n\n"
            f"<i>{hashtags_text}</i>\n\n"
            f"--- DETAIL ---\n"
            f"✅ {video_size_text}\n"
            f"✅ {audio_size_text}\n"
            f"🔗 <a href='{url.split('?')[0]}'>Link Asli</a>"
        )
        await update.message.reply_text(text=info_message, parse_mode='HTML', disable_web_page_preview=True)
            
    except Exception as e:
        logger.error(f"Gagal mengirim file: {e}")
        await update.message.reply_text("Waduh, ada error pas ngirim file. Coba lagi nanti ya.")
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
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot dimulai...")
    application.run_polling()

if __name__ == '__main__':
    main()