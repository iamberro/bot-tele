# -*- coding: utf-8 -*-
import time
import logging
import os
import subprocess
import re
import json
import http.client
import requests.utils
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler, filters,
                          CallbackContext, CallbackQueryHandler)
import yt_dlp
import imageio_ffmpeg
import httpx
from urllib.parse import urlparse, parse_qs, quote
from datetime import datetime, timedelta
import random

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ['TOKEN']
MAX_FILE_SIZE = 150 * 1024 * 1024  # 150MB maximum download size
TELEGRAM_MAX_SIZE = 50 * 1024 * 1024  # 50MB Telegram limit
# FFMPEG_PATH = r'D:\EDP\INFO\INFO\FIX\ffmpeg-7.1-full_build-shared\bin\ffmpeg.exe'
RAPIDAPI_KEY = os.environ['RAPIDAPI_KEY']

# Dictionary to track message timestamps
message_timestamps = {}

# Fun loading messages
LOADING_MESSAGES = [
    "\U0001F50D Mencari video terbaik...",
    "\u26A1 Mengunduh dengan kecepatan tinggi...",
    "\U0001F501 Memproses permintaan Anda...",
    "\U0001F4E5 Sedang mengunduh konten...",
    "\U0001F3AC Menyiapkan video untuk Anda...",
    "\u23F3 Sabar ya, ini bakal keren banget!",
    "\U0001F4BE Menyimpan video ke database...",
    "\U0001F680 Proses hampir selesai...", "\U0001F9F9 Membersihkan cache...",
    "\U0001F3A5 Rendering video terbaik..."
]

# Fun completion messages
COMPLETION_MESSAGES = [
    "\u2705 Selesai! Video siap dinikmati!",
    "\U0001F389 Berhasil! Silakan ditonton!", "\u2728 Video sudah siap bosku!",
    "\U0001F525 Mantap! Download berhasil!",
    "\U0001F4AF Kualitas HD sudah tersedia!",
    "\U0001F44C Proses selesai dengan sempurna!",
    "\U0001F4F2 Video siap dibagikan ke teman-teman!",
    "\U0001F44D Kerja bagus! Video sudah jadi!",
    "\U0001F60E Keren banget nih videonya!",
    "\U0001F929 Wow! Hasilnya memuaskan!"
]

# Error messages
ERROR_MESSAGES = {
    'generic':
    "\U0001F622 Maaf, ada kesalahan saat memproses video. Coba lagi ya!",
    'private': "\U0001F512 Video ini bersifat private atau memerlukan login.",
    'unavailable': "\u274C Video tidak tersedia atau dihapus.",
    'invalid': "\u26D4 Link yang Anda berikan tidak valid.",
    'size': "\U0001F4CF Ukuran video melebihi batas maksimal (50MB).",
    'timeout': "\u23F1\ufe0f Proses terlalu lama. Coba link lain ya!",
    'compression': "\U0001F4A5 Gagal mengkompresi video. Coba link lain!"
}


async def start(update: Update, context: CallbackContext) -> None:
    """Send a welcome message when the command /start is issued"""
    welcome_message = """
\U0001F31F <b>Selamat datang di Berro Downloader!</b> \U0001F31F

Saya bisa mengunduh video dari:
- YouTube (video biasa/shorts)
- TikTok (termasuk link singkat)
- Facebook (reels/feed videos)
- Instagram (reels/feed)

<b>Fitur Unggulan:</b>
\u2705 Kualitas terbaik (sampai 1080p)
\u2705 Kompresi otomatis jika ukuran besar
\u2705 Dukungan multi-platform
\u2705 Proses cepat dan stabil

<b>Cara Pakai:</b>
1. Kirim link video yang ingin diunduh
2. Tunggu proses selesai
3. Nikmati videonya!

<b>Note:</b>
- Maksimal ukuran file 50MB (setelah kompresi)
- Video private mungkin tidak bisa diunduh
- Proses mungkin butuh waktu untuk video besar

Tekan /help untuk bantuan lebih lanjut.
"""

    keyboard = [[
        InlineKeyboardButton("\U0001F4AC Group Support",
                             url="https://t.me/yourgroup")
    ],
                [
                    InlineKeyboardButton("\U0001F4DA Panduan",
                                         url="https://t.me/yourchannel")
                ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_message,
                                    parse_mode='HTML',
                                    reply_markup=reply_markup)


async def help_command(update: Update, context: CallbackContext) -> None:
    """Send help message"""
    help_text = """
<b>\U0001F198 Bantuan Penggunaan Bot</b>

<b>Perintah yang tersedia:</b>
/start - Memulai bot dan menampilkan pesan selamat datang
/help - Menampilkan pesan bantuan ini
/status - Memeriksa status bot

<b>Contoh Link yang Didukung:</b>
- YouTube: https://youtu.be/example
- TikTok: https://vm.tiktok.com/example
- Facebook: https://fb.watch/example
- Instagram: https://instagram.com/reel/example

<b>Pemecahan Masalah:</b>
1. Jika video gagal diunduh:
   - Pastikan link benar
   - Coba lagi setelah beberapa saat
   - Gunakan link alternatif jika ada

2. Jika video terlalu besar:
   - Bot akan otomatis mencoba kompresi
   - Untuk hasil terbaik, gunakan video durasi pendek

3. Jika video private:
   - Bot tidak bisa mengunduh video private
   - Pastikan video bersifat publik

<b>Support:</b>
Untuk pertanyaan lebih lanjut, hubungi @berrontosaurus
"""
    await update.message.reply_text(help_text, parse_mode='HTML')


async def status_command(update: Update, context: CallbackContext) -> None:
    """Send bot status"""
    status_message = """
<b>\U0001F4BB Status Bot</b>

<b>Versi:</b> 2.0
<b>Status:</b> Online \U0001F7E2
<b>Pemakaian:</b> 7/6
<b>Update Terakhir:</b> {}

<b>Fitur Terbaru:</b>
- Peningkatan kecepatan download
- Dukungan format lebih banyak
- Kualitas video lebih baik
""".format(datetime.now().strftime("%d %B %Y"))

    await update.message.reply_text(status_message, parse_mode='HTML')


def get_random_loading_message():
    """Get a random loading message"""
    return random.choice(LOADING_MESSAGES)


def get_random_completion_message():
    """Get a random completion message"""
    return random.choice(COMPLETION_MESSAGES)


def get_error_message(error_type='generic'):
    """Get appropriate error message"""
    return ERROR_MESSAGES.get(error_type, ERROR_MESSAGES['generic'])


async def show_typing(update: Update):
    """Show typing action"""
    try:
        await update.message.chat.send_action(action="typing")
    except Exception as e:
        logger.warning(f"Error showing typing action: {str(e)}")


def is_facebook_url(url: str) -> bool:
    """Check if URL is from Facebook"""
    patterns = [
        r'https?://(?:www\.|m\.|mbasic\.)?facebook\.com/.+/videos/.+',
        r'https?://(?:www\.|m\.|mbasic\.)?facebook\.com/.+/video/.+',
        r'https?://(?:www\.|m\.|mbasic\.)?facebook\.com/watch/?\?v=.+',
        r'https?://(?:www\.|m\.|mbasic\.)?facebook\.com/reel/.+',
        r'https?://fb\.watch/.+', r'https?://www\.facebook\.com/share/.+'
    ]
    return any(re.search(pattern, url) for pattern in patterns)


def is_instagram_url(url: str) -> bool:
    """Check if URL is from Instagram"""
    patterns = [
        r'https?://(?:www\.)?instagram\.com/p/.+',
        r'https?://(?:www\.)?instagram\.com/reel/.+',
        r'https?://(?:www\.)?instagram\.com/tv/.+',
        r'https?://(?:www\.)?instagram\.com/stories/.+',
        r'https?://instagr\.am/p/.+', r'https?://instagr\.am/reel/.+'
    ]
    return any(re.search(pattern, url) for pattern in patterns)


async def compress_video(input_path: str) -> str:
    """
    Optimized video compression function that guarantees smaller output
    with quality preservation
    """
    output_path = os.path.splitext(input_path)[0] + "_compressed.mp4"

    try:
        original_size = os.path.getsize(input_path)
        if original_size <= TELEGRAM_MAX_SIZE:
            return input_path

        logger.info(
            f"File too large ({original_size/1024/1024:.2f}MB), compressing..."
        )

        # First try: Fast preset with optimized settings
        command = [
            imageio_ffmpeg.get_ffmpeg_exe(),
            '-i',
            input_path,
            '-c:v',
            'libx264',
            '-preset',
            'fast',  # Faster compression with good results
            '-crf',
            '28',  # Slightly higher CRF for better compression
            '-vf',
            'scale=-2:720',  # Always scale down to 720p for compression
            '-movflags',
            '+faststart',
            '-pix_fmt',
            'yuv420p',
            '-c:a',
            'aac',
            '-b:a',
            '96k',  # Slightly lower audio bitrate
            '-ac',
            '2',
            '-y',
            output_path
        ]

        logger.info(f"First compression attempt: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            return None

        if not os.path.exists(output_path):
            logger.error("Compressed file not created")
            return None

        compressed_size = os.path.getsize(output_path)
        logger.info(
            f"First compression result: Original: {original_size/1024/1024:.2f}MB, Compressed: {compressed_size/1024/1024:.2f}MB"
        )

        # If still too large, try more aggressive settings
        if compressed_size > TELEGRAM_MAX_SIZE:
            logger.info(
                "File still too large, trying more aggressive compression")
            os.remove(output_path)

            command = [
                imageio_ffmpeg.get_ffmpeg_exe(),
                '-i',
                input_path,
                '-c:v',
                'libx264',
                '-preset',
                'ultrafast',  # Fastest compression
                '-crf',
                '32',  # Higher CRF for smaller files
                '-vf',
                'scale=-2:480',  # Scale down to 480p
                '-movflags',
                '+faststart',
                '-pix_fmt',
                'yuv420p',
                '-c:a',
                'aac',
                '-b:a',
                '64k',  # Lower audio quality
                '-ac',
                '2',
                '-y',
                output_path
            ]

            logger.info(f"Second compression attempt: {' '.join(command)}")
            result = subprocess.run(command, capture_output=True, text=True)

            if result.returncode != 0 or not os.path.exists(output_path):
                return None

            compressed_size = os.path.getsize(output_path)
            logger.info(
                f"Second compression result: {compressed_size/1024/1024:.2f}MB"
            )

            if compressed_size > TELEGRAM_MAX_SIZE:
                os.remove(output_path)
                return None

        return output_path
    except Exception as e:
        logger.error(f"Compression error: {str(e)}")
        return None


async def download_youtube_rapidapi(url: str) -> str:
    """Download YouTube video using RapidAPI with quality selection"""
    filename = None
    try:
        # Extract video ID from URL
        video_id = extract_youtube_video_id(url)
        if not video_id:
            logger.error("Could not extract YouTube video ID")
            return None

        # Step 1: Get video info to check available qualities
        video_info = await get_youtube_video_info(video_id)
        if not video_info or not video_info.get('availableQuality'):
            logger.error("No video info or quality data available")
            return None

        # Step 2: Select the best available quality
        selected_quality = select_best_quality(video_info['availableQuality'])
        if not selected_quality:
            logger.error("No suitable quality found")
            return None

        logger.info(
            f"Selected quality: {selected_quality['quality']} (ID: {selected_quality['id']})"
        )

        # Step 3: Download with selected quality
        filename = await download_with_quality(video_id,
                                               selected_quality['id'])
        return filename

    except Exception as e:
        logger.error(f"YouTube RapidAPI download error: {str(e)}")
        if filename and os.path.exists(filename):
            os.remove(filename)
        return None


async def get_youtube_video_info(video_id: str) -> dict:
    """Get YouTube video info including available qualities"""
    try:
        conn = http.client.HTTPSConnection(
            "youtube-video-fast-downloader-24-7.p.rapidapi.com")
        endpoint = f"/get-video-info/{video_id}"

        headers = {
            'x-rapidapi-key':
            RAPIDAPI_KEY,
            'x-rapidapi-host':
            "youtube-video-fast-downloader-24-7.p.rapidapi.com",
            'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
        }

        conn.request("GET", endpoint, headers=headers)
        res = conn.getresponse()

        if res.status == 200:
            data = json.loads(res.read().decode("utf-8"))
            return data
        else:
            logger.error(f"API returned {res.status}: {res.reason}")
            return None

    except Exception as e:
        logger.error(f"Error getting video info: {str(e)}")
        return None


def select_best_quality(qualities: list) -> dict:
    """Select the best available video quality"""
    try:
        # Filter only video formats (no audio-only)
        video_qualities = [q for q in qualities if q['type'] == 'video']

        if not video_qualities:
            return None

        # Preferred quality order
        preferred_order = ['1080p', '720p', '480p', '360p', '240p', '144p']

        # Find the best available quality
        for quality in preferred_order:
            for q in video_qualities:
                if q['quality'] == quality and q.get(
                        'mime', '').startswith('video/mp4'):
                    return q

        # If no MP4 found, return first available
        return video_qualities[0]

    except Exception as e:
        logger.error(f"Error selecting quality: {str(e)}")
        return None


async def download_with_quality(video_id: str, quality_id: int) -> str:
    """Download video with specific quality ID"""
    try:
        conn = http.client.HTTPSConnection(
            "youtube-video-fast-downloader-24-7.p.rapidapi.com")
        endpoint = f"/download_video/{video_id}?quality={quality_id}"

        headers = {
            'x-rapidapi-key':
            RAPIDAPI_KEY,
            'x-rapidapi-host':
            "youtube-video-fast-downloader-24-7.p.rapidapi.com",
            'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
        }

        conn.request("GET", endpoint, headers=headers)
        res = conn.getresponse()

        if res.status == 200:
            data = json.loads(res.read().decode("utf-8"))
            video_url = data.get('download_url') or data.get(
                'url') or data.get('video_url')

            if not video_url:
                logger.error("No video URL in response")
                return None

            # Download the video
            os.makedirs('downloads', exist_ok=True)
            filename = f"downloads/{video_id}_{quality_id}_{int(time.time())}.mp4"

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    video_url,
                    headers={
                        'User-Agent':
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
                        'Referer': 'https://www.youtube.com/'
                    },
                    follow_redirects=True)
                response.raise_for_status()

                with open(filename, 'wb') as f:
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)

                if os.path.exists(filename) and os.path.getsize(filename) > 0:
                    return filename
                else:
                    raise ValueError("Downloaded file is empty")
        else:
            logger.error(f"Download API returned {res.status}: {res.reason}")
            return None

    except Exception as e:
        logger.error(f"Error downloading with quality {quality_id}: {str(e)}")
        return None


def extract_youtube_video_id(url: str) -> str:
    """Extract YouTube video ID from various URL formats including shorts"""
    try:
        # Handle YouTube Shorts URLs
        if '/shorts/' in url.lower():
            match = re.search(r'/shorts/([^?/]+)', url, re.IGNORECASE)
            if match:
                return match.group(1)

        # Handle YouTube Live URLs
        if '/live/' in url.lower():
            match = re.search(r'/live/([^?/]+)', url, re.IGNORECASE)
            if match:
                return match.group(1)

        # Standard YouTube URLs
        patterns = [
            r"youtube\.com/watch\?v=([^&]+)", r"youtu\.be/([^?]+)",
            r"youtube\.com/embed/([^/]+)", r"youtube\.com/v/([^/]+)"
        ]

        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                return match.group(1)

        return None
    except Exception as e:
        logger.error(f"Error extracting YouTube video ID: {str(e)}")
        return None


async def download_youtube(url: str) -> str:
    """Download YouTube video with RapidAPI fallback to yt-dlp"""
    try:
        # First try with RapidAPI
        video_path = await download_youtube_rapidapi(url)
        if video_path:
            # Check file size
            file_size = os.path.getsize(video_path)
            if file_size > TELEGRAM_MAX_SIZE:
                compressed_path = await compress_video(video_path)
                os.remove(video_path)
                return compressed_path if compressed_path else "TOO_LARGE"
            return video_path

        # Fallback to yt-dlp if API fails
        logger.info("RapidAPI failed, falling back to yt-dlp")
        return await download_youtube_ytdlp(url)

    except Exception as e:
        logger.error(f"Error in YouTube download: {str(e)}")
        return await download_youtube_ytdlp(url)


async def download_youtube_ytdlp(url: str) -> str:
    """Fallback YouTube download using yt-dlp"""
    try:
        ydl_opts = {
            'format':
            '(bestvideo[vcodec^=avc1][height<=4320][ext=mp4]/bestvideo[height<=4320][ext=mp4]/bestvideo)+bestaudio/best',
            'outtmpl':
            'downloads/%(id)s.%(ext)s',
            'ffmpeg_location':
            imageio_ffmpeg.get_ffmpeg_exe(),
            'merge_output_format':
            'mp4',
            'windows_filenames':
            True,
            'ignoreerrors':
            True,
            'retries':
            3,
            'fragment_retries':
            10,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'player_skip': ['configs', 'webpage'],
                    'skip': ['dash', 'hls']
                }
            },
            'postprocessor_args': ['-threads', '4', '-preset', 'fast'],
            'noplaylist':
            True,
            'max_filesize':
            MAX_FILE_SIZE,
            'http_headers': {
                'User-Agent':
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9'
            },
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }]
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info:
                original_path = ydl.prepare_filename(info)

                if '_' in os.path.basename(original_path):
                    base_path = os.path.splitext(original_path)[0]
                    new_path = base_path + '.mp4'
                    if os.path.exists(new_path):
                        original_path = new_path

                file_size = os.path.getsize(original_path)
                logger.info(
                    f"Downloaded file size: {file_size/1024/1024:.2f}MB")

                if file_size > TELEGRAM_MAX_SIZE:
                    compressed_path = await compress_video(original_path)
                    os.remove(original_path)

                    if not compressed_path:
                        return "TOO_LARGE"
                    return compressed_path
                return original_path

        return None
    except yt_dlp.utils.DownloadError as e:
        if 'Private video' in str(e):
            return "PRIVATE"
        if 'is not available' in str(e):
            return "UNAVAILABLE"
        logger.error(f"YouTube download error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected YouTube download error: {str(e)}")
        return None


def extract_tiktok_video_id(url: str) -> str:
    """Extract TikTok video ID from various URL formats"""
    try:
        if 'vm.tiktok.com' in url or 'vt.tiktok.com' in url:
            return None  # Will be resolved in download_tiktok

        patterns = [
            r"https?://(?:www\.)?tiktok\.com/@[^/]+/video/(\d+)",
            r"https?://(?:www\.)?tiktok\.com/t/([a-zA-Z0-9]+)/",
            r"https?://(?:www\.)?tiktok\.com/v/(\d+)\.html",
            r"https?://m\.tiktok\.com/v/(\d+)\.html"
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None
    except Exception as e:
        logger.error(f"Error extracting TikTok video ID: {str(e)}")
        return None


async def download_tiktok(url: str) -> str:
    """Download TikTok video using RapidAPI with fallback to yt-dlp"""
    try:
        # First try with RapidAPI
        video_path = await download_tiktok_rapidapi(url)
        if video_path:
            return video_path

        # If RapidAPI fails, fall back to yt-dlp
        logger.info("RapidAPI failed, falling back to yt-dlp")
        return await download_tiktok_ytdlp(url)
    except Exception as e:
        logger.error(f"Error in TikTok download: {str(e)}")
        return await download_tiktok_fallback(url)


async def download_tiktok_rapidapi(url: str) -> str:
    """Download TikTok video using RapidAPI's POST endpoint"""
    filename = None
    try:
        # Prepare the request
        conn = http.client.HTTPSConnection(
            "tiktok-video-no-watermark2.p.rapidapi.com")

        # URL encode the TikTok URL
        encoded_url = f"url={quote(url)}&hd=1"  # hd=1 requests higher quality

        headers = {
            'x-rapidapi-key': RAPIDAPI_KEY,
            'x-rapidapi-host': "tiktok-video-no-watermark2.p.rapidapi.com",
            'Content-Type': "application/x-www-form-urlencoded"
        }

        # Make the POST request
        conn.request("POST", "/", encoded_url, headers)
        res = conn.getresponse()

        if res.status != 200:
            logger.error(f"RapidAPI error: {res.status} - {res.reason}")
            return None

        data = json.loads(res.read().decode("utf-8"))

        # Extract video URL from response
        if not data or not data.get('data'):
            logger.error("No video data in API response")
            return None

        video_url = data['data'].get('play') or data['data'].get(
            'video_url') or data['data'].get('hdplay')
        if not video_url:
            logger.error("No video URL in API response")
            return None

        # Download the video
        os.makedirs('downloads', exist_ok=True)
        filename = f"downloads/{int(time.time())}.mp4"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                video_url,
                headers={
                    'User-Agent':
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
                    'Referer': 'https://www.tiktok.com/'
                })
            response.raise_for_status()

            with open(filename, 'wb') as f:
                f.write(response.content)

        # Verify the downloaded file
        if not os.path.exists(filename) or os.path.getsize(filename) == 0:
            logger.error("Downloaded file is empty or missing")
            if os.path.exists(filename):
                os.remove(filename)
            return None

        return filename

    except Exception as e:
        logger.error(f"RapidAPI download error: {str(e)}")
        if filename and os.path.exists(filename):
            os.remove(filename)
        return None


async def download_tiktok_ytdlp(url: str) -> str:
    """Fallback TikTok download using yt-dlp"""
    try:
        ydl_opts = {
            'format':
            'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl':
            'downloads/%(id)s.%(ext)s',
            'ffmpeg_location':
            imageio_ffmpeg.get_ffmpeg_exe(),
            'merge_output_format':
            'mp4',
            'windows_filenames':
            True,
            'ignoreerrors':
            True,
            'retries':
            3,
            'fragment_retries':
            5,
            'noplaylist':
            True,
            'max_filesize':
            MAX_FILE_SIZE,
            'http_headers': {
                'User-Agent':
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
                'Referer': 'https://www.tiktok.com/'
            },
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }]
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info:
                original_path = ydl.prepare_filename(info)

                # Check file size
                file_size = os.path.getsize(original_path)
                if file_size > TELEGRAM_MAX_SIZE:
                    compressed_path = await compress_video(original_path)
                    os.remove(original_path)
                    return compressed_path if compressed_path else "TOO_LARGE"

                return original_path
        return None
    except Exception as e:
        logger.error(f"yt-dlp download error: {str(e)}")
        return None


async def download_tiktok_fallback(url: str) -> str:
    """Final fallback for TikTok download"""
    try:
        # Try with simpler yt-dlp options
        ydl_opts = {
            'format': 'best',
            'outtmpl': 'downloads/%(id)s.%(ext)s',
            'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
            'windows_filenames': True,
            'ignoreerrors': True,
            'retries': 2,
            'noplaylist': True,
            'max_filesize': MAX_FILE_SIZE,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info:
                return ydl.prepare_filename(info)
        return None
    except Exception as e:
        logger.error(f"Final fallback error: {str(e)}")
        return None


async def resolve_facebook_url(short_url: str) -> str:
    """Resolve Facebook share/short URLs to canonical video URL"""
    try:
        headers = {
            'User-Agent':
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }

        async with httpx.AsyncClient(follow_redirects=True) as client:
            # First resolve the share URL
            response = await client.get(short_url, headers=headers)
            final_url = str(response.url)

            # If it's a watch page, try to extract video ID
            if 'facebook.com/watch/' in final_url:
                match = re.search(r'v=(\d+)', final_url)
                if match:
                    video_id = match.group(1)
                    return f'https://www.facebook.com/watch/?v={video_id}'

            return final_url
    except Exception as e:
        logger.error(f"Error resolving Facebook URL: {str(e)}")
        return None


async def download_facebook(url: str) -> str:
    """Download Facebook video with improved handling"""
    try:
        # First resolve the URL if it's a share link
        if 'facebook.com/share/' in url or 'fb.watch/' in url:
            resolved_url = await resolve_facebook_url(url)
            if resolved_url:
                url = resolved_url
                logger.info(f"Resolved Facebook URL: {url}")
            else:
                logger.error("Failed to resolve Facebook share URL")
                return "UNAVAILABLE"

        ydl_opts = {
            # More flexible format selection
            'format':
            '(bestvideo[vcodec^=avc1][height<=1080][ext=mp4]/bestvideo[height<=1080][ext=mp4]/bestvideo)+(bestaudio)',
            'outtmpl': 'downloads/%(id)s.%(ext)s',
            'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
            'merge_output_format': 'mp4',
            'windows_filenames': True,
            'ignoreerrors': True,
            'retries': 3,
            'fragment_retries': 10,
            'noplaylist': True,
            'max_filesize': MAX_FILE_SIZE,
            'http_headers': {
                'User-Agent':
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
                'Referer': 'https://www.facebook.com/',
                'Accept-Language': 'en-US,en;q=0.9',
            },
            'extractor_args': {
                'facebook': {
                    'skip_dash_manifest': True,
                    'referer': 'https://www.facebook.com/',
                }
            },
            'cookiefile':
            'facebook_cookies.txt',  # Recommended for private videos
            'force_generic_extractor': True  # Bypass some restrictions
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # First try to extract info without downloading
                info = ydl.extract_info(url, download=False)
                if not info:
                    logger.error("Failed to extract video info")
                    return None

                # Check if video requires login
                if info.get('is_private',
                            False) or info.get('availability') == 'needs_auth':
                    logger.error("Video requires login")
                    return "UNAVAILABLE"

                # Log available formats for debugging
                logger.info(f"Available formats for {url}:")
                if 'formats' in info:
                    for f in info['formats']:
                        logger.info(
                            f"Format: {f.get('format_id')} - {f.get('height')}p - {f.get('ext')}"
                        )

                # Now proceed with download
                info = ydl.extract_info(url, download=True)
                if info:
                    original_path = ydl.prepare_filename(info)

                    file_size = os.path.getsize(original_path)
                    if file_size > TELEGRAM_MAX_SIZE:
                        compressed_path = await compress_video(original_path)
                        os.remove(original_path)

                        if not compressed_path:
                            return "TOO_LARGE"
                        return compressed_path
                    return original_path
            except yt_dlp.utils.DownloadError as e:
                if "login" in str(e).lower() or "sign in" in str(e).lower():
                    logger.error("Facebook requires login for this video")
                    return "UNAVAILABLE"
                logger.error(f"yt-dlp download error: {str(e)}")
                return None
            except Exception as e:
                logger.error(f"Facebook download error: {str(e)}")
                return None
        return None
    except Exception as e:
        logger.error(f"Facebook download error: {str(e)}")
        return None


async def download_instagram(url: str) -> str:
    """Improved Instagram video download with better error handling"""
    try:
        ydl_opts = {
            'format':
            'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl':
            'downloads/%(id)s.%(ext)s',
            'ffmpeg_location':
            imageio_ffmpeg.get_ffmpeg_exe(),
            'merge_output_format':
            'mp4',
            'windows_filenames':
            True,
            'ignoreerrors':
            True,
            'retries':
            3,
            'fragment_retries':
            10,
            'noplaylist':
            True,
            'max_filesize':
            MAX_FILE_SIZE,
            'http_headers': {
                'User-Agent':
                'Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36',
                'Referer': 'https://www.instagram.com/',
                'X-IG-App-ID': '936619743392459'
            },
            'cookiefile':
            'instagram_cookies.txt',
            'extractor_args': {
                'instagram': {
                    'native': True,
                    'feed_retry': True,
                    'story': False,
                    'igtv': False,
                    'reel': True,
                    'post': True
                }
            },
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }]
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # First get info without downloading
            info = ydl.extract_info(url, download=False)
            if not info:
                logger.error("Failed to get video info")
                return None

            # Check if video is private or requires login
            if info.get('is_private', False):
                logger.error("Video is private")
                return "PRIVATE"

            # Now download
            info = ydl.extract_info(url, download=True)
            if info:
                filename = ydl.prepare_filename(info)

                # Ensure the file is in mp4 format
                if not filename.endswith('.mp4'):
                    new_path = os.path.splitext(filename)[0] + '.mp4'
                    os.rename(filename, new_path)
                    filename = new_path

                # Check file size
                file_size = os.path.getsize(filename)
                if file_size > TELEGRAM_MAX_SIZE:
                    compressed = await compress_video(filename)
                    os.remove(filename)
                    return compressed if compressed else "TOO_LARGE"

                return filename

        return None
    except yt_dlp.utils.DownloadError as e:
        if 'private' in str(e).lower():
            return "PRIVATE"
        if 'login' in str(e).lower():
            return "LOGIN_REQUIRED"
        logger.error(f"Instagram download error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected Instagram error: {str(e)}")
        return None


def generate_share_buttons(video_title: str, url: str) -> tuple:
    """Generate share buttons markup with hashtags"""
    try:
        # Clean the title and URL for safe usage
        safe_title = video_title[:50] + "..." if len(
            video_title) > 50 else video_title
        safe_url = url.split('?')[0]
        short_url = safe_url[:27] + "..." if len(safe_url) > 30 else safe_url

        # Generate hashtags
        words = [
            word for word in re.findall(r'\w+', safe_title) if len(word) > 3
        ][:5]
        hashtags = ' '.join([f'#{word}'
                             for word in words]) + ' #viral #trending'

        # Create message text
        message = (f"\u2705 Video berhasil diunduh!\n\n"
                   f"\u23F3 Jika video tidak ada diatas, tunggu sebentar ya!\n"
                   f"\u2705 Sedang proses pengiriman kok!\n\n"
                   f"\U0001F3AC {safe_title}\n"
                   f"\U0001F517 {short_url}\n\n"
                   f"<b>Bagikan ke:</b>")

        # Create safe callback data (limited to 64 bytes)
        callback_data = f"redownload_{safe_url[:30]}"
        if len(callback_data.encode()) > 64:
            callback_data = "redownload_0"

        # Create buttons
        keyboard = [[
            InlineKeyboardButton(
                "\U0001F4E4 Bagikan ke Teman",
                switch_inline_query=f"Lihat video: {safe_title[:50]}")
        ],
                    [
                        InlineKeyboardButton("\U0001F4BE Unduh Ulang",
                                             callback_data=callback_data)
                    ],
                    [
                        InlineKeyboardButton("\u2B50 Beri Rating",
                                             callback_data="rate_bot")
                    ]]

        return message, InlineKeyboardMarkup(keyboard)

    except Exception as e:
        logger.error(f"Error generating share buttons: {str(e)}")
        # Fallback message without buttons
        fallback_msg = (
            f"\u2705 Video berhasil diunduh!\n\n"
            f"\u23F3 Jika video tidak ada diatas, tunggu sebentar ya!\n"
            f"\u2705 Sedang proses pengiriman kok!\n\n"
            f"\U0001F3AC {video_title[:50]}\n"
            f"\U0001F517 {url.split('?')[0][:30]}")
        return fallback_msg, None


async def send_video_once(update: Update, video_path: str,
                          caption: str) -> bool:
    """Send video with a single attempt and proper timeout handling"""
    try:
        with open(video_path, 'rb') as video_file:
            await update.message.reply_video(
                video=video_file,
                caption=caption,
                supports_streaming=True,
                write_timeout=300,  # Increased to 5 minutes
                connect_timeout=120  # Increased to 2 minutes
            )
            return True
    except Exception as e:
        logger.error(f"Failed to send video: {str(e)}")
        return False


async def get_video_metadata(url: str) -> dict | None:
    """Mengambil judul dan hashtag dari URL video menggunakan yt-dlp."""
    logger.info(f"Mengambil metadata untuk URL: {url}")
    ydl_opts = {
        'quiet': True,
        'skip_download': True,  # Hanya ambil info, jangan download
        'force_generic_extractor': False,
    }

    try:
        # Menjalankan yt-dlp di thread terpisah agar tidak memblokir bot
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(
                None, lambda: ydl.extract_info(url, download=False))

        title = info.get('title', 'Judul Tidak Tersedia')
        description = info.get('description', '')

        # TikTok seringkali sudah menyediakan hashtag secara langsung
        hashtags = info.get('hashtags', [])

        # Jika tidak ada, kita cari manual dari judul atau deskripsi
        if not hashtags:
            full_text = f"{title} {description}"
            # Menggunakan regex untuk menemukan semua kata yang diawali #
            found_hashtags = re.findall(r'#(\w+)', full_text)
            if found_hashtags:
                hashtags = list(
                    dict.fromkeys(found_hashtags))  # Hapus duplikat

        return {'title': title, 'hashtags': hashtags}

    except Exception as e:
        logger.error(f"Gagal mengambil metadata: {e}")
        return None


async def handle_message(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    current_time = datetime.now()

    # Rate limiting
    if user_id in message_timestamps:
        last_message_time = message_timestamps[user_id]
        if current_time - last_message_time < timedelta(seconds=5):
            await update.message.reply_text(
                "? Tunggu sebentar ya, jangan terlalu cepat. Bot butuh waktu untuk memproses."
            )
            return

    message_timestamps[user_id] = current_time

    url = update.message.text.strip()

    # 1. Ambil metadata dulu
    metadata = await get_video_metadata(url)

    # Siapkan judul fallback jika metadata gagal diambil
    fallback_title = "Video"

    # Show typing action
    await show_typing(update)

    # Send initial processing message
    processing_msg = await update.message.reply_text(
        f"{get_random_loading_message()}\n\n"
        "\u23F3 Estimasi waktu: 10-30 detik\n"
        "\U0001F4C8 Ukuran maksimal: 50MB\n"
        "\u26A1 Proses mungkin lebih lama untuk video besar\n"
        "\u23F3 Estimasi Ukuran besar bisa 5-10 menit\n")

    video_path = None
    try:
        # Bagian download
        if 'youtube.com' in url or 'youtu.be' in url:
            video_path = await download_youtube(url)
        elif 'tiktok.com' in url or 'vm.tiktok.com' in url or 'vt.tiktok.com' in url:
            video_path = await download_tiktok(url)
        elif is_facebook_url(url):
            video_path = await download_facebook(url)
        elif is_instagram_url(url):
            video_path = await download_instagram(url)
        else:
            await processing_msg.edit_text(
                "\u2753 Format link tidak dikenali\n\n"
                "Pastikan link dari:\n"
                "- YouTube\n- TikTok\n- Facebook\n- Instagram\n\n"
                "Contoh: https://www.youtube.com/watch?v=...")
            return

        # Penanganan error download
        if video_path in ["TOO_LARGE", "UNAVAILABLE"] or not video_path:
            error_message = ""
            if video_path == "TOO_LARGE":
                error_message = (
                    "\U0001F4CF Ukuran video melebihi batas maksimal (50MB)\n\n"
                    "Tips:\n- Cari video dengan durasi lebih pendek.")
            elif video_path == "UNAVAILABLE":
                error_message = (
                    "\U0001F512 Video tidak tersedia atau memerlukan login.\n\n"
                    "Pastikan video bersifat publik.")
            else:
                error_message = (
                    "\u274C Gagal mengunduh video.\n\n"
                    "Penyebab mungkin:\n- Link tidak valid\n- Video dihapus")
            await processing_msg.edit_text(error_message)
            return

        # Gunakan judul asli dari metadata, jika gagal pakai fallback
        video_title = metadata['title'] if metadata and metadata.get(
            'title') else fallback_title

        # Potong judul jika terlalu panjang
        if len(video_title) > 80:
            video_title = video_title[:77] + "..."

        await processing_msg.edit_text(
            f"\u2705 Video berhasil diunduh!\n\n"
            f"\U0001F3AC {video_title}\n"
            f"\U0001F4C6 Ukuran: {os.path.getsize(video_path)/1024/1024:.1f}MB\n"
            f"\U0001F4E4 Mengunggah ke Telegram...")

        # 1. Buat caption HANYA untuk video (judul & hashtag)
        hashtags_text = ' '.join([
            f'#{tag}' for tag in metadata['hashtags']
        ]) if metadata and metadata.get('hashtags') else ''
        video_caption = (
            f"<b>{video_title}</b>\n"
            f"<i>{hashtags_text}</i>\n\n"
            f"{get_random_completion_message()}\n\n"
            f"<a href='{url.split('?')[0]}'>Link Asli</a> | "
            f"Ukuran: {os.path.getsize(video_path)/1024/1024:.1f}MB")

        # 2. Buat teks untuk pesan kedua (info tambahan)
        info_message = (f"<b>{video_title}</b>"
                        f"<i>{hashtags_text}</i>")

        try:
            # Kirim pesan pertama: Video + Caption Judul
            with open(video_path, 'rb') as video_file:
                await update.message.reply_video(video=video_file,
                                                 caption=video_caption,
                                                 parse_mode='HTML',
                                                 supports_streaming=True,
                                                 write_timeout=300,
                                                 connect_timeout=120)

            # Kirim pesan kedua: Teks Info Tambahan
            await update.message.reply_text(text=info_message,
                                            parse_mode='HTML',
                                            disable_web_page_preview=True)

        except Exception as e:
            logger.error(f"Gagal mengirim video: {str(e)}")
            await update.message.reply_text(
                "Video berhasil diunduh tapi gagal dikirim. Coba lagi nanti.")

    finally:
        # Hapus file video setelah semua proses selesai
        if video_path and os.path.exists(video_path):
            os.remove(video_path)

        # Hapus pesan "sedang memproses"
        if processing_msg:
            try:
                await processing_msg.delete()
            except Exception as e:
                logger.warning(f"Gagal menghapus pesan proses: {str(e)}")


async def button_handler(update: Update, context: CallbackContext) -> None:
    """Handle button callbacks with proper validation"""
    query = update.callback_query
    await query.answer()

    try:
        if query.data.startswith('redownload_'):
            # Get the original URL from context or reconstruct it
            original_url = query.data.split('_', 1)[1]
            if original_url == "0":
                await query.edit_message_text(
                    "⚠️ Tidak bisa mengunduh ulang. Kirim link lagi.")
                return

            await handle_message(update.message, context)

        elif query.data == 'rate_bot':
            await query.edit_message_text(
                "Silakan beri rating bot ini:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⭐ Bagus", callback_data="rate_good")
                ], [
                    InlineKeyboardButton("👎 Kurang", callback_data="rate_bad")
                ]]))

        elif query.data.startswith('rate_'):
            rating = query.data.split('_')[1]
            responses = {
                'good': "Terima kasih atas rating bagusnya!",
                'bad': "Maaf atas ketidaknyamanan. Kami akan memperbaiki."
            }
            await query.edit_message_text(
                responses.get(rating, "Terima kasih!"))

    except Exception as e:
        logger.error(f"Button handler error: {str(e)}")
        await query.edit_message_text(
            "⚠️ Terjadi kesalahan. Silakan coba lagi.")


def main() -> None:
    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    # try:
    #   yt_dlp.utils.update._real_main(['--update'])
    # except:
    #    logger.warning(f"Failed to update yt-dlp: {e}")

    application = Application.builder().token(TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))

    # Message handler
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Button handler
    application.add_handler(CallbackQueryHandler(button_handler))

    application.run_polling()


if __name__ == '__main__':
    main()
