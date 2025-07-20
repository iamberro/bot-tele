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
MAX_FILE_SIZE = 150 * 1024 * 1024
TELEGRAM_MAX_SIZE = 50 * 1024 * 1024

# --- Variabel & Pesan-pesan Bot ---
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
    # ... (Fungsi ini tidak diubah, tetap sama)
    welcome_message = """
<pre>
██╗  ██╗███████╗██╗     ██╗      ██████╗ ██╗
██║  ██║██╔════╝██║     ██║     ██╔═══██╗██║
███████║█████╗  ██║     ██║     ██║   ██║██║
██╔══██║██╔══╝  ██║     ██║     ██║   ██║╚═╝
██║  ██║███████╗███████╗███████╗╚██████╔╝██╗
</pre>
<b>Yoo, whats up bro!</b> 🤙

Kenalin, gue <b>Bot Berro</b>, partner download lo yang paling gercep ⚡ dan paling asique se-antero Telegram!

Gue siap sedot video atau audio dari mana aja:
🔴 <b>YouTube</b>: Video biasa, shorts, sampe playlist... sikaaat!
⚫️ <b>TikTok</b>: Link standar, link aneh... semua gue lahap!
🟣 <b>Instagram</b>: Reels, IGTV, foto-foto... amankeuun!
🔵 <b>Facebook</b>: Video, reels, siaran langsung... hajar bleh!

<b>Caranya? Cuma 3 langkah santuy:</b>
1️⃣ Lempar link-nya ke gue
2️⃣ Pilih format yang lo mau
3️⃣ Voila! ✨ File langsung jadi!

Tunggu apa lagi? Langsung aja lempar link pertama lo! Gaskeun! 🔥👇
"""
    await update.message.reply_text(welcome_message, parse_mode='HTML')

async def help_command(update: Update, context: CallbackContext) -> None:
    # ... (Fungsi ini tidak diubah, tetap sama)
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
    # ... (Fungsi ini tidak diubah, tetap sama)
    status_message = f"""
<pre>
███████╗████████╗ █████╗ ████████╗██╗   ██╗███████╗
██╔════╝╚══██╔══╝██╔══██╗╚══██╔══╝██║   ██║██╔════╝
███████╗   ██║   ███████║   ██║   ██║   ██║███████╗
╚════██║   ██║   ██╔══██║   ██║   ██║   ██║╚════██║
███████║   ██║   ██║  ██║   ██║   ╚██████╔╝███████║
</pre>
<b>Laporan situasi terkini dari markas!</b> 📣

🤖 <b>Nama Bot:</b> Berro Downloader
✅ <b>Status:</b> ONLINE & SIAP BERAKSI! 💨
⚙️ <b>Versi:</b> 3.0 (Mode Interaktif)
🧠 <b>Otak Gue:</b> Baru di-upgrade pada {datetime.now().strftime("%d %B %Y")}

Gue siap menerima perintah, Komandan! 👇
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
    bar = '█' * int(percent / 10)
    bar += '░' * (10 - len(bar))
    return f"[{bar}] {int(percent)}%"

async def compress_video(input_path: str) -> str | None:
    # ... (Fungsi ini tidak diubah, tetap sama)
    output_path = os.path.splitext(input_path)[0] + "_compressed.mp4"
    try:
        original_size = os.path.getsize(input_path)
        if original_size <= TELEGRAM_MAX_SIZE:
            return input_path
        
        logger.info(f"File video terlalu besar ({original_size / 1024 / 1024:.2f}MB), mengompres dengan cepat...")
        
        command = [
            imageio_ffmpeg.get_ffmpeg_exe(), '-i', input_path,
            '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '28',
            '-vf', 'scale=-2:720', '-movflags', '+faststart',
            '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '96k',
            '-y', output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
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
# ======================== FUNGSI-FUNGSI DOWNLOAD (DISIMPLIFY) =================
# ==============================================================================

async def download_file(url: str, format_choice: str, progress_hook=None) -> str | None:
    """Fungsi download universal untuk video dan audio."""
    logger.info(f"Memulai download format '{format_choice}' untuk: {url}")
    unique_id = f"{int(time.time())}_{random.randint(1000, 9999)}"
    
    cookie_file = None
    if 'instagram.com' in url: cookie_file = 'instagram_cookies.txt'
    elif 'facebook.com' in url or 'fb.watch' in url: cookie_file = 'facebook_cookies.txt'
    elif 'youtube.com' in url or 'youtu.be' in url: cookie_file = 'youtube_cookies.txt'

    # Opsi dasar
    ydl_opts = {
        'outtmpl': f'downloads/{unique_id}.%(ext)s',
        'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
        'noplaylist': True, 'ignoreerrors': True, 'max_filesize': MAX_FILE_SIZE,
        'progress_hooks': [progress_hook] if progress_hook else [],
    }

    # Opsi spesifik berdasarkan pilihan
    if format_choice == 'audio':
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
    else: # Jika video
        ydl_opts['format'] = f"{format_choice}+bestaudio/best" # Pilih video stream + audio stream terbaik
        ydl_opts['merge_output_format'] = 'mp4'

    if cookie_file and os.path.exists(cookie_file):
        ydl_opts['cookiefile'] = cookie_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            return ydl.prepare_filename(info)
    except Exception as e:
        logger.error(f"Error saat download: {e}")
        return None

# ==============================================================================
# ======================== HANDLER BARU DENGAN TOMBOL ==========================
# ==============================================================================

### FUNGSI 1: Menerima link dan menampilkan pilihan format
async def handle_link(update: Update, context: CallbackContext) -> None:
    url = update.message.text.strip()
    if not re.match(r'https?://', url):
        return

    processing_msg = await update.message.reply_text("Siaap! Gue intip dulu link-nya ya... 🕵️‍♂️")

    # Simpan URL di memori chat untuk digunakan nanti
    context.chat_data['current_url'] = url

    ydl_opts = {'quiet': True, 'skip_download': True, 'noplaylist': True}
    cookie_file = None
    if 'instagram.com' in url: cookie_file = 'instagram_cookies.txt'
    elif 'facebook.com' in url or 'fb.watch' in url: cookie_file = 'facebook_cookies.txt'
    elif 'youtube.com' in url or 'youtu.be' in url: cookie_file = 'youtube_cookies.txt'
    if cookie_file and os.path.exists(cookie_file):
        ydl_opts['cookiefile'] = cookie_file

    try:
        logger.info(f"Mengambil info format untuk URL: {url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=False)
        
        title = info.get('title', 'Judul Tidak Tersedia')
        context.chat_data['video_title'] = title

        formats = info.get('formats', [])
        buttons = []

        # Pilihan Audio (selalu ada)
        buttons.append([InlineKeyboardButton("🎵 Audio (MP3 Kualitas Terbaik)", callback_data="download|audio")])
        
        # Filter format video MP4 (hanya stream video, tanpa audio)
        # INI PERBAIKAN PENTING UNTUK FACEBOOK/INSTAGRAM
        video_formats = [f for f in formats if f.get('vcodec') not in ['none', None] and f.get('ext') == 'mp4' and f.get('filesize')]
        video_formats.sort(key=lambda f: f.get('height', 0), reverse=True)

        added_heights = set()
        for f in video_formats:
            height = f.get('height')
            if height and height not in added_heights:
                filesize_mb = f.get('filesize', 0) / 1024 / 1024
                format_id = f.get('format_id')
                buttons.append([InlineKeyboardButton(f"🎥 Video ({height}p) - {filesize_mb:.1f} MB", callback_data=f"download|{format_id}")])
                added_heights.add(height)
                if len(added_heights) >= 3: break

        if len(buttons) <= 1:
            await processing_msg.edit_text("Waduh, nggak ada format video MP4 yang bisa gue download dari link itu, Bro.")
            return
        
        buttons.append([InlineKeyboardButton("❌ Batalin Aja", callback_data="cancel_action")])

        reply_markup = InlineKeyboardMarkup(buttons)
        await processing_msg.edit_text(f"<b>{title}</b>\n\nPilih format yang mau lo sikat, Bro:", reply_markup=reply_markup, parse_mode='HTML')

    except Exception as e:
        logger.error(f"Gagal mengambil format: {e}", exc_info=True)
        await processing_msg.edit_text("Waduh, error, Bro! Link-nya kayaknya aneh, digembok, atau platformnya lagi ngambek. 🧐")

### FUNGSI 2: Menangani pilihan download dari user
async def handle_download_choice(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    url = context.chat_data.get('current_url')
    if not url:
        await query.edit_message_text("Waduh, sesi ini udah kedaluwarsa, Bro. Coba kirim ulang link-nya ya.")
        return

    _, choice = query.data.split('|', 1)
    title = context.chat_data.get('video_title', 'Judul Tidak Tersedia')
    
    await query.edit_message_text(text=f"Oke, gaskeun download format '{choice}'! {get_random_loading_message()}")

    file_path = None
    final_path = None
    try:
        file_path = await download_file(url, choice)
        
        if not file_path:
            raise ValueError("Download gagal, file tidak ditemukan.")

        if choice == 'audio':
            final_path = file_path
            with open(final_path, 'rb') as audio_file:
                await query.message.reply_audio(audio=audio_file, title=title)
            await query.edit_message_text(text=f"Nih audionya, Bro! {get_random_completion_message()}")
        else: # Jika video
            final_path = file_path
            if os.path.getsize(file_path) > TELEGRAM_MAX_SIZE:
                await query.edit_message_text("File-nya bongsor banget, Bro! Gue kompres dulu ya biar muat dikirim... ⏳")
                compressed_path = await compress_video(file_path)
                if compressed_path and os.path.getsize(compressed_path) <= TELEGRAM_MAX_SIZE:
                    final_path = compressed_path
                else:
                    await query.message.reply_text("Gagal kompres atau hasilnya masih kegedean, Bro. Maaf, videonya nggak bisa dikirim. 😢")
                    final_path = None
            
            if final_path:
                await query.edit_message_text("Udah siap! Gue lagi siap-siap ngirim videonya ke lu... 🚀")
                caption = f"<b>{title}</b>\n\n{get_random_completion_message()}"
                with open(final_path, 'rb') as video_file:
                    await query.message.reply_video(video=video_file, caption=caption, parse_mode='HTML')
                await query.delete_message()
    
    except Exception as e:
        logger.error(f"Gagal saat download pilihan user: {e}", exc_info=True)
        await query.edit_message_text("Waduh, ada error misterius pas download, Bro! Coba lagi ya. 😭")
    finally:
        # Hapus semua file sementara yang mungkin dibuat
        if file_path and os.path.exists(file_path):
            try: os.remove(file_path)
            except Exception as e: logger.error(f"Gagal hapus file_path: {e}")
        if final_path and final_path != file_path and os.path.exists(final_path):
            try: os.remove(final_path)
            except Exception as e: logger.error(f"Gagal hapus final_path: {e}")


### FUNGSI 3: Menangani tombol batal
async def handle_cancel_action(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Oke, dibatalin. Santuy... 😎")

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

    # --- INI BAGIAN YANG DIUBAH ---
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    
    # 1. MessageHandler sekarang memanggil 'handle_link' untuk menampilkan tombol
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    
    # 2. Tambahkan CallbackQueryHandler untuk menangani tombol yang ditekan
    application.add_handler(CallbackQueryHandler(handle_download_choice, pattern='^download\|'))
    application.add_handler(CallbackQueryHandler(handle_cancel_action, pattern='^cancel_action$'))
    # --- BATAS PERUBAHAN ---

    logger.info("Bot dimulai...")
    application.run_polling()

if __name__ == '__main__':
    main()