# Gunakan base image Python versi 3.10 yang ramping
FROM python:3.10-slim

# Set direktori kerja di dalam container
WORKDIR /app

# Perbarui daftar paket dan install FFmpeg
# Ini adalah bagian terpenting!
RUN apt-get update && apt-get install -y ffmpeg

# Salin file requirements.txt terlebih dahulu untuk caching
COPY requirements.txt .

# Install semua library Python yang dibutuhkan bot
RUN pip install --no-cache-dir -r requirements.txt

# Salin semua sisa kode bot kamu
COPY . .

# Perintah untuk menjalankan bot saat container dimulai
CMD ["python", "bot.py"]