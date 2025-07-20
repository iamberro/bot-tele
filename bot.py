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
    "Siap laksanakan! Gue lagi nyelam ke server buat ngambil datanya... 🌊 Dapet nih!",
    "Gaskeun! Mesin download udah gue panasin, meluncur dengan kecepatan cahaya! ⚡️💨",
    "Sabar ya, ini bagian paling serunya. Lagi gue tarik-tarik datanya, semoga jaringnya kuat! 🎣",
    "Memanggil seluruh kekuatan FFMPEG! Video dan audio lagi gue jodohin biar jadi satu... 💍",
    "Dikit lagi kelar nih... Lagi gue poles pixel-nya satu-satu biar kinclong maksimal! ✨💅",
    "Hampir mateng nih! Wangi-wangi render udah kecium... eh, itu kopi gue. 😂 Videonya juga tapi!",
    "Tahan napas... Ini sentuhan terakhir dari sang maestro digital! 🎨 Siap-siap terpesona!"
]
COMPLETION_MESSAGES = [
    "BOOM! 💥 Pesenan spesial buat lu udah mendarat dengan selamat!",
    "TADAA! ✨ Inilah hasil mahakarya gue setelah bertapa beberapa saat. Silakan dinikmati!",
    "Beuh, mantap jiwa! Videonya udah siap tempur buat menuhin galeri lu! 🔥",
    "Nih, masih anget, baru diangkat dari prosesor! Awas panas! 🤩",
    "Misi selesai dengan gemilang! Kata sandinya: 'Berro Paling Keren'. 😎 Ini filenya!",
    "Selesai dengan nilai 100/100! Kualitasnya? Udah pasti yang terbaik buat bosku! 💯",
    "Salam dari Berro, si paling sat set se-antero Telegram! 🤙 Nih, mahakaryanya!"
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

def generate_progress_bar(percent):
    """Membuat string progress bar: [████░░░░░░] 40%"""
    bar = '█' * int(percent / 10)
    bar += '░' * (10 - len(bar))
    return f"[{bar}] {int(percent)}%"

async def get_video_metadata(url: str) -> dict | None:
    logger.info(f"Mengambil metadata untuk URL: {url}")

    # Tentukan file cookies berdasarkan URL
    cookie_file = None
    if 'instagram.com' in url:
        cookie_file = 'instagram_cookies.txt'
    elif 'facebook.com' in url or 'fb.watch' in url:
        cookie_file = 'facebook_cookies.txt'
    elif 'youtube.com' in url or 'youtu.be' in url:
        cookie_file = 'youtube_cookies.txt'

    ydl_opts = {'quiet': True, 'skip_download': True}
    if cookie_file and os.path.exists(cookie_file):
        ydl_opts['cookiefile'] = cookie_file

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
        
        logger.info(f"File video terlalu besar ({original_size / 1024 / 1024:.2f}MB), mengompres dengan cepat...")
        
        command = [
            imageio_ffmpeg.get_ffmpeg_exe(), '-i', input_path,
            '-c:v', 'libx264',
            '-preset', 'veryfast',  # <-- DIUBAH DARI 'fast' KE 'veryfast' UNTUK KECEPATAN
            '-crf', '28',
            '-vf', 'scale=-2:720',
            '-movflags', '+faststart',
            '-pix_fmt', 'yuv420p',
            '-c:a', 'aac',
            '-b:a', '96k',
            '-y', output_path
        ]
        
        # Menjalankan kompresi di thread terpisah agar tidak memblokir bot
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(f"FFmpeg error saat kompresi: {stderr.decode()}")
            return None

        if os.path.exists(output_path):
            logger.info(f"Kompresi berhasil, ukuran baru: {os.path.getsize(output_path) / 1024 / 1024:.2f}MB")
            return output_path
            
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
    
    # Logika untuk memilih cookie file yang benar
    cookie_file = None
    if 'instagram.com' in url:
        cookie_file = 'instagram_cookies.txt'
    elif 'facebook.com' in url or 'fb.watch' in url:
        cookie_file = 'facebook_cookies.txt'
    elif 'youtube.com' in url or 'youtu.be' in url:
        cookie_file = 'youtube_cookies.txt'

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'downloads/{unique_id}.%(ext)s',
        'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
        'noplaylist': True, 'ignoreerrors': True, 'max_filesize': MAX_FILE_SIZE,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
    }
    
    # Tambahkan cookie file jika ada dan filenya tersedia
    if cookie_file and os.path.exists(cookie_file):
        ydl_opts['cookiefile'] = cookie_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Menjalankan download di thread terpisah agar tidak memblokir
            await asyncio.to_thread(ydl.extract_info, url, download=True)
            
        expected_path = f'downloads/{unique_id}.mp3'
        if os.path.exists(expected_path):
            return expected_path
        # Fallback jika nama file tidak sesuai ekspektasi
        for file in os.listdir('downloads'):
            if file.startswith(unique_id) and file.endswith('.mp3'):
                return os.path.join('downloads', file)
        return None
    except Exception as e:
        logger.error(f"Error saat download audio: {e}")
        return None

async def download_youtube(url: str, progress_hook=None) -> str | None:
    logger.info(f"Memulai download VIDEO (YouTube) untuk: {url}")
    unique_id = f"{int(time.time())}_{random.randint(1000, 9999)}"
    ydl_opts = {
        'format': '(bv[height<=1080][ext=mp4]+ba[ext=m4a])/(b[ext=mp4][height<=720])/best[ext=mp4]/best',
        'outtmpl': f'downloads/{unique_id}.%(ext)s',
        'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
        'merge_output_format': 'mp4',
        'noplaylist': True, 'ignoreerrors': True, 'max_filesize': MAX_FILE_SIZE,
        'cookiefile': 'youtube_cookies.txt',
        'progress_hooks': [progress_hook] if progress_hook else [],
    }
    try:
        # Menjalankan download di thread terpisah agar tidak memblokir bot
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            return ydl.prepare_filename(info)
    except Exception as e:
        logger.error(f"Error download_youtube: {e}")
        return None

async def download_tiktok(url: str, progress_hook=None) -> str | None:
    logger.info(f"Memulai download VIDEO (TikTok) untuk: {url}")
    unique_id = f"{int(time.time())}_{random.randint(1000, 9999)}"
    ydl_opts = {
        'format': '(bv[height<=1080][ext=mp4]+ba[ext=m4a])/(b[ext=mp4][height<=720])/best[ext=mp4]/best',
        'outtmpl': f'downloads/{unique_id}.%(ext)s',
        'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
        'merge_output_format': 'mp4',
        'noplaylist': True, 'ignoreerrors': True, 'max_filesize': MAX_FILE_SIZE,
        'progress_hooks': [progress_hook] if progress_hook else [],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            return ydl.prepare_filename(info)
    except Exception as e:
        logger.error(f"Error download_tiktok: {e}")
        return None

async def download_facebook(url: str, progress_hook=None) -> str | None:
    logger.info(f"Memulai download VIDEO (Facebook) untuk: {url}")
    unique_id = f"{int(time.time())}_{random.randint(1000, 9999)}"
    ydl_opts = {
        'format': '(bv[height<=1080][ext=mp4]+ba[ext=m4a])/(b[ext=mp4][height<=720])/best[ext=mp4]/best',
        'outtmpl': f'downloads/{unique_id}.%(ext)s',
        'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
        'merge_output_format': 'mp4',
        'noplaylist': True, 'ignoreerrors': True, 'max_filesize': MAX_FILE_SIZE,
        'cookiefile': 'facebook_cookies.txt',
        'progress_hooks': [progress_hook] if progress_hook else [],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            return ydl.prepare_filename(info)
    except Exception as e:
        logger.error(f"Error download_facebook: {e}")
        return None

async def download_instagram(url: str, progress_hook=None) -> str | None:
    logger.info(f"Memulai download VIDEO (Instagram) untuk: {url}")
    unique_id = f"{int(time.time())}_{random.randint(1000, 9999)}"
    ydl_opts = {
        'format': '(bv[height<=1080][ext=mp4]+ba[ext=m4a])/(b[ext=mp4][height<=720])/best[ext=mp4]/best',
        'outtmpl': f'downloads/{unique_id}.%(ext)s',
        'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
        'merge_output_format': 'mp4',
        'noplaylist': True, 'ignoreerrors': True, 'max_filesize': MAX_FILE_SIZE,
        'cookiefile': 'instagram_cookies.txt',
        'progress_hooks': [progress_hook] if progress_hook else [],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
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

    # --- 1. Tahap Awal: Cek Link & Metadata ---
    processing_msg = await update.message.reply_text("Siaap! Link-nya gue terima, laksanakan! Cekidot dulu yaa... 🕵️‍♂️")

    metadata = await get_video_metadata(url)
    if not metadata or not metadata.get('title'):
        await processing_msg.edit_text("Waduh, error, Bro! Link-nya kayaknya aneh atau digembok nih. 🧐 Coba cari link lain yang publik, ya!")
        return

    title = metadata['title']
    hashtags = metadata.get('hashtags', [])

    # --- 2. Setup Progress Hook (VERSI BARU YANG SUDAH DIPERBAIKI) ---
    last_update_time = 0
    last_status_text = "" # Variabel untuk menyimpan teks terakhir yang dikirim
    main_loop = asyncio.get_running_loop()

    def sync_progress_hook(d):
        nonlocal last_update_time, last_status_text
        if d['status'] == 'downloading':
            current_time = time.time()
            if current_time - last_update_time > 2:  # Batasi update setiap 2 detik
                try:
                    percent_str = d.get('_percent_str', '0.0%').strip().replace('%', '')
                    percent = float(percent_str)
                    progress_bar = generate_progress_bar(percent)
                    downloaded = d.get('_downloaded_bytes_str', 'N/A')
                    total = d.get('_total_bytes_str', 'N/A')
                    speed = d.get('_speed_str', 'N/A')
                    eta = d.get('_eta_str', 'N/A')

                    status_text = (
                        f"<b>Nguuueeengg... Lagi nyedot video!</b> 🚀\n\n"
                        f"Judul: <i>{title[:30]}...</i>\n\n"
                        f"<b>{progress_bar}</b>\n\n"
                        f"📦 {downloaded} / {total}\n"
                        f"⚡️ {speed}\n"
                        f"⏳ Estimasi: {eta}\n\n"
                        "Harap sabar ya, lagi gue perjuangin nih! 💪"
                    )
                    
                    # Cek apakah teksnya berubah sebelum mengedit pesan
                    if status_text != last_status_text:
                        main_loop.call_soon_threadsafe(
                            asyncio.create_task,
                            processing_msg.edit_text(text=status_text, parse_mode='HTML')
                        )
                        last_status_text = status_text # Update teks terakhir
                        last_update_time = current_time
                except Exception as e:
                    logger.warning(f"Gagal update progress: {e}")

        elif d['status'] == 'finished':
            finished_text = "Mantap! Download video kelar. Sekarang gue gabungin sama audionya... 🪄"
            if finished_text != last_status_text:
                main_loop.call_soon_threadsafe(
                    asyncio.create_task,
                    processing_msg.edit_text(finished_text)
                )
                last_status_text = finished_text
    
    # (Sisa kode handle_message lainnya tetap sama seperti sebelumnya)
    # ... (lanjutkan dengan blok "Tentukan Fungsi Download", "Eksekusi Download & Kirim File", dst.)
    # ... (Tidak perlu mengubah bagian setelah ini, karena sudah benar)
    # --- 3. Tentukan Fungsi Download ---
    downloader_map = {
        'youtube.com': download_youtube,
        'youtu.be': download_youtube,
        'https://youtube.com/shorts/obNvALGz7oo?si=NRd0jTr9VETBvCqh': download_youtube,
        'tiktok.com': download_tiktok,
        'facebook.com': download_facebook,
        'fb.watch': download_facebook,
        'instagram.com': download_instagram,
    }

    video_downloader_func = None
    for domain, func in downloader_map.items():
        if domain in url:
            video_downloader_func = func
            break
    
    if not video_downloader_func:
        await processing_msg.edit_text("Waduh, platform ini belum gue kenal, bro. Coba link dari YouTube, TikTok, FB, atau IG ya! 🙏")
        return

    # --- 4. Eksekusi Download & Kirim File ---
    video_path = None
    audio_path = None
    files_to_delete = []

    try:
        # Menjalankan download video dengan progress hook
        video_path = await video_downloader_func(url, progress_hook=sync_progress_hook)
        if video_path:
            files_to_delete.append(video_path)
            
            # Kompresi jika perlu
            if os.path.getsize(video_path) > TELEGRAM_MAX_SIZE:
                await processing_msg.edit_text("File-nya bongsor banget, Bro! Gue kompres dulu ya biar muat dikirim... ⏳")
                compressed_path = await compress_video(video_path)
                if compressed_path and os.path.getsize(compressed_path) <= TELEGRAM_MAX_SIZE:
                    video_path = compressed_path
                    files_to_delete.append(compressed_path)
                else:
                    await update.message.reply_text("Gagal kompres atau hasilnya masih kegedean, Bro. Maaf, videonya nggak bisa dikirim. 😢")
                    video_path = None
            
            # Kirim video jika berhasil
            if video_path:
                await processing_msg.edit_text("Udah siap! Gue lagi siap-siap ngirim videonya ke lu... 🚀")
                hashtags_text = ' '.join([f'#{tag}' for tag in hashtags])
                video_size_text = f"Ukuran Video: {os.path.getsize(video_path)/1024/1024:.1f}MB"
                video_full_caption = (
                    f"<b>{title}</b>\n\n"
                    f"<i>{hashtags_text}</i>\n\n"
                    f"{get_random_completion_message()}\n\n"
                    f"{video_size_text}\n"
                    f"<a href='{url.split('?')[0]}'>Link Asli</a>"
                )
                with open(video_path, 'rb') as video_file:
                    await update.message.reply_video(video=video_file, caption=video_full_caption, parse_mode='HTML')

        # Download dan kirim audio secara terpisah
        await processing_msg.edit_text("Sip, video udah kekirim! Sekarang giliran audionya... 🎶")
        audio_path = await download_audio_only(url)
        if audio_path:
            files_to_delete.append(audio_path)
            if os.path.getsize(audio_path) <= TELEGRAM_MAX_SIZE:
                with open(audio_path, 'rb') as audio_file:
                    await update.message.reply_audio(audio=audio_file, title=title)
            else:
                await update.message.reply_text("Audionya kegedean, Bro, nggak bisa dikirim. 😢")
        
        # Kirim pesan teks terpisah
        hashtags_text_only = ' '.join([f'#{tag}' for tag in hashtags])
        title_hashtag_message = f"{title}\n\n{hashtags_text_only}"
        await update.message.reply_text(text=title_hashtag_message)

    except Exception as e:
        logger.error(f"Gagal di alur utama: {e}")
        await processing_msg.edit_text("Waduh, ada error misterius di tengah jalan, Bro! Coba lagi ya. 😭")
    finally:
        # Hapus pesan status dan file sementara
        try:
            await processing_msg.delete()
        except Exception:
            pass # Abaikan jika pesan sudah terhapus
        
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