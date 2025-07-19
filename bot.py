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
    "Oke, link diterima! Gue lagi ngintip servernya... 🤫",
    "Gaskeun! Nguuueeengg... Download sekencang kilat! ⚡️",
    "Sabar ya, lagi gue proses. Data sedang ditarik dari alam gaib... 👻",
    "Memanggil jin FFMPEG buat ngeracik videonya... 🧞‍♂️",
    "Dikit lagi kelar... Lagi gue rapiin pixel-nya biar kinclong! ✨",
    "Hampir mateng nih! Baunya udah wangi... eh, maksudnya videonya. 😂",
    "Tahan napas... Sentuhan terakhir dari sang maestro! 🎨"
]
COMPLETION_MESSAGES = [
    "BOOM! 💥 Video pesenan lu udah jadi, nih!",
    "Tadaa! ✨ Hasil mahakarya gue, spesial buat lu!",
    "Beuh, mantap jiwa! Videonya udah siap tempur! 🔥",
    "Nih, anget-anget baru diangkat dari prosesor! 🤩",
    "Kerja bagus, Berro! Eh, maksudnya ini videonya buat lu. 😎",
    "Selesai dengan sempurna! Kualitasnya? Jangan ditanya! 💯",
    "Salam dari Berro, si paling sat set! 🤙"
]

# ==============================================================================
# ======================== FUNGSI-FUNGSI COMMAND HANDLER =======================
# ==============================================================================

async def start(update: Update, context: CallbackContext) -> None:
    welcome_message = """
<b>Wihh, ada yang mau download nih!</b> 🤙

Kenalin, gue <b>Berro</b>, asisten download paling sabi se-Telegram! 😎

Gue bisa nyedot video & audio dari:
- 🎬 YouTube (biasa, shorts, semua bisa!)
- 🕺 TikTok (link panjang pendek, sikat!)
- 👨‍👩‍👧‍👦 Facebook (reels, video biasa, hajar!)
- 📸 Instagram (reels, postingan, libas!)

<b>Gampang banget caranya:</b>
Cukup lempar link video yang lu mau, terus duduk manis. Ntar gue sulap jadi file MP4 & MP3 buat lu! ✨

Gaskeun! 👇
"""
    await update.message.reply_text(welcome_message, parse_mode='HTML')

async def help_command(update: Update, context: CallbackContext) -> None:
    help_text = """
<b>Butuh contekan? Tenang, gue bantu jelasin!</b> 📜

Nih jurus-jurus rahasia yang bisa lu pake:
/start - Kenalan lagi sama gue & liat pesan saktinya.
/help - Nampilin contekan ini lagi.
/status - Cek kondisi gue, siap tempur apa nggak.

<b>Kalau ada drama pas download:</b>
1️⃣ <b>Gagal download?</b>
   - Cek lagi link-nya, jangan sampe typo, bro.
   - Pastiin videonya publik, jangan yang digembok cintanya. 🔒
   - Kadang server lagi ngambek, coba aja lagi beberapa menit kemudian.

2️⃣ <b>File kegedean?</b>
   - Gue cuma bisa kirim file di bawah 50MB. Aturan dari Telegram, bukan gue. 😅
   - Kalau videonya kegedean, gue bakal coba kompres otomatis biar muat.

<b>Masih bingung?</b>
Langsung aja colek bos gue di @berrontosaurus.
"""
    await update.message.reply_text(help_text, parse_mode='HTML')

async def status_command(update: Update, context: CallbackContext) -> None:
    status_message = f"""
<b>Cek kondisi gue, nih!</b> 🤙

<b>🤖 Nama Bot:</b> Berro Downloader
<b>🔥 Kondisi:</b> On fire, siap tempur 24/7!
<b>✨ Versi:</b> 2.5 (Mode Bawel Asyique)
<b>🗓️ Update Terakhir:</b> {datetime.now().strftime("%d %B %Y")}
"""
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
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
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
# ======================== FUNGSI-FUNGSI DOWNLOAD ==============================
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

async def download_youtube(url: str) -> str | None:
    logger.info(f"Memulai download VIDEO (YouTube) untuk: {url}")
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
        logger.error(f"Error download_youtube: {e}")
        return None

async def download_tiktok(url: str) -> str | None:
    logger.info(f"Memulai download VIDEO (TikTok) untuk: {url}")
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
        logger.error(f"Error download_tiktok: {e}")
        return None

async def download_facebook(url: str) -> str | None:
    logger.info(f"Memulai download VIDEO (Facebook) untuk: {url}")
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
    logger.info(f"Memulai download VIDEO (Instagram) untuk: {url}")
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
# ======================== HANDLER UTAMA (ALUR PESAN BARU) =====================
# ==============================================================================

async def handle_message(update: Update, context: CallbackContext) -> None:
    url = update.message.text.strip()
    if not re.match(r'https?://', url):
        return

    processing_msg = await update.message.reply_text("Siaap! Link-nya gue terima, laksanakan! Cekidot dulu yaa... 🕵️‍♂️")

    metadata = await get_video_metadata(url)
    if not metadata or not metadata.get('title'):
        await processing_msg.edit_text("Waduh, error, Bro! Link-nya kayaknya aneh atau digembok nih. 🧐 Coba cari link lain yang publik, ya!")
        return
        
    title = metadata['title']
    hashtags = metadata.get('hashtags', [])
    
    await processing_msg.edit_text(f"KETEMU! ✅ Judulnya \"<i>{title[:50]}...</i>\", mantul! Siap-siap, gue lagi ngeracik video & audionya. Prosesor gue sampe ngebul nih! 🔥", parse_mode='HTML')

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

    audio_downloader_func = download_audio_only(url)
    
    results = await asyncio.gather(video_downloader_func, audio_downloader_func, return_exceptions=True)
    video_path, audio_path = results

    files_to_delete = []
    if isinstance(video_path, str) and os.path.exists(video_path): files_to_delete.append(video_path)
    if isinstance(audio_path, str) and os.path.exists(audio_path): files_to_delete.append(audio_path)

    try:
        if not files_to_delete:
            await processing_msg.edit_text("Yah, gagal maning, gagal maning... 😭 Kayaknya videonya diproteksi alien atau emang link-nya keliru, bro. Coba lagi pake link sakti lainnya!")
            return

        await processing_msg.edit_text(f"Asiiik, udah jadi! 🎁 {get_random_completion_message()} Gue kirim filenya sekarang juga!")
        
        # --- ALUR PENGIRIMAN PESAN SESUAI PERMINTAAN ---
        
        # 1. Kirim Video dengan Caption Lengkap
        if isinstance(video_path, str) and os.path.exists(video_path):
            final_video_path = video_path
            caption_suffix = ""
            if os.path.getsize(video_path) > TELEGRAM_MAX_SIZE:
                compressed_path = await compress_video(video_path)
                if compressed_path and os.path.getsize(compressed_path) <= TELEGRAM_MAX_SIZE:
                    final_video_path = compressed_path
                    files_to_delete.append(compressed_path)
                    caption_suffix = " (dikompres)"
                else:
                    await update.message.reply_text(f"🎬 Video terlalu besar untuk dikirim (batas 50MB).")
                    final_video_path = None
            
            if final_video_path:
                hashtags_text = ' '.join([f'#{tag}' for tag in hashtags])
                video_size_text = f"Ukuran Video: {os.path.getsize(final_video_path)/1024/1024:.1f}MB"
                
                video_full_caption = (
                    f"<b>{title}{caption_suffix}</b>\n\n"
                    f"<i>{hashtags_text}</i>\n\n"
                    f"{get_random_completion_message()}\n"
                    f"{video_size_text}\n"
                    f"<a href='{url.split('?')[0]}'>Link Asli</a>"
                )
                with open(final_video_path, 'rb') as video_file:
                    await update.message.reply_video(video=video_file, caption=video_full_caption, parse_mode='HTML')
        else:
            logger.error(f"Proses video gagal atau file tidak ditemukan: {video_path}")

        # 2. Kirim Audio
        if isinstance(audio_path, str) and os.path.exists(audio_path):
            if os.path.getsize(audio_path) > TELEGRAM_MAX_SIZE:
                await update.message.reply_text(f"🎵 Audio terlalu besar untuk dikirim (batas 50MB).")
            else:
                with open(audio_path, 'rb') as audio_file:
                    await update.message.reply_audio(audio=audio_file, title=title)
        else:
            logger.error(f"Proses audio gagal atau file tidak ditemukan: {audio_path}")

        # 3. Kirim Pesan Teks Terpisah (Judul + Tag)
        hashtags_text_only = ' '.join([f'#{tag}' for tag in hashtags])
        title_hashtag_message = f"{title}\n\n{hashtags_text_only}"
        await update.message.reply_text(text=title_hashtag_message)
            
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

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot dimulai...")
    application.run_polling()

if __name__ == '__main__':
    main()