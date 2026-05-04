# 🎬 Auto Clipper — Free Alternative to Vizard AI

> Sistem otomasi video clipping 100% gratis menggunakan **yt-dlp + faster-whisper + ffmpeg + n8n self-hosted**.
> Mengubah video panjang (podcast, webinar, YouTube) menjadi klip pendek vertikal 9:16 dengan subtitle otomatis — siap upload ke TikTok, Instagram Reels, dan YouTube Shorts.

---

## ✨ Fitur

- ✅ Download video dari YouTube (atau URL apapun)
- ✅ Transkripsi audio otomatis (lokal, tanpa API berbayar)
- ✅ Deteksi segmen viral berdasarkan scoring kata kunci
- ✅ Potong & resize video ke format **9:16 vertikal**
- ✅ Subtitle otomatis — font **Impact**, muncul **per kata**
  - Kata biasa → putih
  - Kata penting → **KUNING** (harus, viral, sukses, dll)
- ✅ Custom durasi klip dari form input (misal: 30–60 detik)
- ✅ Nama folder output = judul video YouTube otomatis
- ✅ Filter klip berdasarkan viral score minimum
- ✅ Log hasil ke Google Sheets (opsional)
- ✅ Workflow otomatis via n8n self-hosted

---

## 🛠️ Stack & Package yang Digunakan

### 1. `yt-dlp` — Video Downloader
- **Jenis**: Python package
- **Install**: `pip install yt-dlp`
- **Fungsi**: Download video dari YouTube, TikTok, Instagram, dan 1000+ situs lainnya
- **Kenapa bukan youtube-dl?**: yt-dlp adalah fork aktif dengan update lebih cepat dan lebih stabil
- **Dokumentasi**: https://github.com/yt-dlp/yt-dlp

### 2. `faster-whisper` — Speech-to-Text
- **Jenis**: Python package
- **Install**: `pip install faster-whisper`
- **Fungsi**: Transkripsi audio ke teks secara lokal (tidak perlu internet/API key)
- **Model yang digunakan**: `small` — keseimbangan antara akurasi dan kecepatan
- **Word timestamps**: Menghasilkan timing per kata untuk subtitle akurat
- **Kenapa faster-whisper?**: 4x lebih cepat dari Whisper original dengan akurasi sama, berjalan di CPU
- **Dokumentasi**: https://github.com/SYSTRAN/faster-whisper

### 3. `ffmpeg` — Video Processing
- **Jenis**: Software binary (bukan Python package)
- **Install**: Download dari https://github.com/BtbN/ffmpeg-builds/releases → tambahkan ke PATH
- **Fungsi**:
  - Extract audio dari video (.wav untuk Whisper)
  - Potong video di timestamp yang tepat
  - Resize & pad video ke format 9:16 (1080×1920)
  - Burn subtitle .ASS ke video
- **Dokumentasi**: https://ffmpeg.org/documentation.html

### 4. `n8n` — Workflow Automation
- **Jenis**: Node.js app (dijalankan via Docker)
- **Install**: `docker run ... docker.n8n.io/n8nio/n8n`
- **Fungsi**: Orkestrator utama — menghubungkan form input → Python server → Google Sheets → output
- **Versi**: 2.18.5 (Community Edition, self-hosted, gratis)
- **Dokumentasi**: https://docs.n8n.io

### 5. `Docker Desktop` — Container Runtime
- **Jenis**: Software
- **Install**: https://www.docker.com/products/docker-desktop/
- **Fungsi**: Menjalankan n8n dalam container terisolasi tanpa perlu install Node.js manual
- **Dokumentasi**: https://docs.docker.com

### 6. `ASS Subtitle Format` — Advanced SubStation Alpha
- **Jenis**: Format file teks (.ass)
- **Fungsi**: Format subtitle yang mendukung styling per kata (warna, ukuran, posisi, bold)
- **Kenapa bukan SRT?**: SRT hanya support teks polos, tidak bisa beda warna per kata
- **Dibuat oleh**: `auto_clipper.py` secara otomatis, lalu di-burn ke video via ffmpeg
- **File bersifat sementara** — otomatis dihapus setelah digunakan

---

## 📁 Struktur Folder

```
D:\Tools\
├── ffmpeg-master-latest-win64-gpl-shared\
│   └── bin\
│       ├── ffmpeg.exe          ← binary utama
│       ├── ffprobe.exe
│       └── ffplay.exe
├── auto-clipper\               ← folder ini (repository)
│   ├── auto_clipper.py         ← script utama clipper
│   ├── clipper_server.py       ← HTTP server wrapper
│   ├── Auto_Clipper_*.json     ← workflow n8n
│   ├── jalankan_semua.bat      ← shortcut run semua service
│   ├── .gitignore
│   └── README.md
└── jalankan_semua.bat

D:\clips\
└── [Judul_Video_Timestamp]\    ← hasil klip
    ├── clip_001.mp4
    ├── clip_002.mp4
    └── clip_003.mp4
```

---

## ⚙️ Cara Install (Dari Nol)

### Prasyarat
- Windows 10/11 64-bit
- Python 3.10+ ([download](https://www.python.org/downloads/))
- Git ([download](https://git-scm.com/download/win))

### Step 1 — Install Docker Desktop
```bash
# 1. Aktifkan WSL 2 (PowerShell sebagai Administrator)
wsl --install

# 2. Restart komputer

# 3. Download & install Docker Desktop dari:
#    https://www.docker.com/products/docker-desktop/
#    Klik kanan installer → Run as administrator

# 4. Verifikasi
docker --version
```

### Step 2 — Install ffmpeg
```bash
# 1. Download: ffmpeg-master-latest-win64-gpl-shared.zip
#    dari: https://github.com/BtbN/ffmpeg-builds/releases

# 2. Extract ke D:\Tools\

# 3. Tambahkan ke PATH Windows:
#    Windows + S → "Environment Variables" → System variables
#    → Path → Edit → New → masukkan:
D:\Tools\ffmpeg-master-latest-win64-gpl-shared\bin

# 4. Verifikasi (buka CMD baru)
ffmpeg -version
```

### Step 3 — Install Python Dependencies
```bash
pip install yt-dlp
pip install faster-whisper
```

### Step 4 — Setup Script Files
```bash
# Clone repository ini
git clone https://github.com/fajri-svg/auto-clipper.git D:\Tools\auto-clipper

# Buat folder output klip
mkdir D:\clips
```

### Step 5 — Setup n8n Workflow
```bash
# Jalankan n8n
docker volume create n8n_data
docker run -it --rm --name n8n -p 5678:5678 -v n8n_data:/home/node/.n8n docker.n8n.io/n8nio/n8n

# Buka browser → http://localhost:5678
# Import file: Auto_Clipper_Free_v3_n8n.json
# (Workflows → "..." → Import from file)
```

### Step 6 — Konfigurasi Node di n8n

Buka node **Configuration** dan sesuaikan:

| Field | Default | Keterangan |
|-------|---------|------------|
| `output_dir` | `D:\clips` | Folder output klip |
| `server_url` | `http://host.docker.internal:5680/clip` | URL Python server |
| `viral_score` | dari form | Skor minimum (0-100) |
| `min_dur` | dari form | Durasi minimum klip (detik) |
| `max_dur` | dari form | Durasi maksimum klip (detik) |

Buka node **Run Auto Clipper** → pastikan URL dalam mode **Fixed** (bukan Expression):
```
http://host.docker.internal:5680/clip
```

---

## 🚀 Cara Menjalankan

### Setiap Kali Ingin Pakai:

**1. Buka Docker Desktop** — tunggu icon di taskbar berhenti berputar (~30–60 detik)

**2. Jalankan 2 CMD secara bersamaan:**

```bash
# CMD 1 — Python Server (port 5680)
python D:\Tools\auto-clipper\clipper_server.py

# CMD 2 — n8n Docker
docker run -it --rm --name n8n -p 5678:5678 -v n8n_data:/home/node/.n8n docker.n8n.io/n8nio/n8n
```

> 💡 **Shortcut**: Gunakan `jalankan_semua.bat` untuk menjalankan keduanya sekaligus

**3. Test server aktif:**
```
http://localhost:5680/health
```
Harus muncul: `{"status": "ok", "message": "Clipper server berjalan!"}`

**4. Buka n8n:**
```
http://localhost:5678
```

**5. Jalankan workflow:**
- Klik node **"On form submission"** → **Test step**
- Isi form: URL video + Skor viral + Durasi min + Durasi max
- Klik **"Generate Short Video"**

---

## 📊 Cara Kerja (Alur)

```
[Input Form n8n]
      ↓
[Configuration Node]  ← set output_dir, server_url, viral_score, min/max dur
      ↓
[HTTP POST → clipper_server.py :5680]
      ↓
[auto_clipper.py]
      ├── yt-dlp         → download video dari URL
      ├── ffmpeg         → extract audio (.wav)
      ├── faster-whisper → transkripsi + word timestamps
      ├── scoring        → deteksi segmen viral (kata kunci + durasi ideal)
      ├── generate_ass() → buat subtitle .ASS per kata
      └── ffmpeg         → potong + resize 9:16 + burn subtitle
      ↓
[JSON response ke n8n]
      ↓
[Split Clips] → [Filter viral score] → [Limit Clips]
      ↓                    ↓
[Append Clips]      [Ready for TikTok]
[Google Sheets]     [Ready for Instagram]
      ↓
[Output: MP4 9:16 dengan subtitle di D:\clips\[Judul Video]\]
```

---

## ⏱️ Estimasi Waktu Proses

| Tahap | Estimasi | Catatan |
|-------|----------|---------|
| Download video | 2–5 menit | Tergantung kecepatan internet |
| Extract audio | ~30 detik | Cepat |
| Download model Whisper | 5–10 menit | **Hanya pertama kali** (~500MB) |
| Transkripsi audio | 10–20 menit | Video 1 jam di CPU |
| Scoring + potong klip | 2–5 menit | 10 klip output |
| **Total (pertama kali)** | **~20–40 menit** | Run berikutnya lebih cepat |

---

## 🎨 Kustomisasi Subtitle

Edit variabel di `auto_clipper.py`:

```python
FONT_SIZE    = 72        # ukuran font (px) — seragam semua kata
FONT_NAME    = "Impact"  # font (Impact = bold tebal, tersedia default di Windows)
MARGIN_V     = 220       # jarak dari bawah layar (px) — makin besar = makin ke atas
```

Tambah/kurangi kata yang otomatis di-highlight kuning:
```python
EMPHASIS_WORDS = [
    "harus", "wajib", "penting", "viral", "fakta",
    # tambahkan kata lain di sini...
]
```

---

## 📈 Tips Penggunaan

| Platform | Min Durasi | Max Durasi | Keterangan |
|----------|-----------|------------|------------|
| TikTok standar | 30 | 60 | Sweet spot engagement |
| YouTube Shorts | 15 | 60 | Max 60 detik |
| Instagram Reels | 15 | 90 | Bisa lebih panjang |
| Klip panjang | 60 | 180 | Untuk konten edukatif |

**Skor viral > 70** = klip berkualitas tinggi
**Skor viral 50–70** = klip standar
**Skor viral < 50** = pertimbangkan untuk skip

---

## ⚠️ Catatan Penting

### Copyright
- Gunakan tool ini untuk **konten milik sendiri** (rekaman pribadi, podcast sendiri)
- Jika menggunakan konten orang lain → minta izin terlebih dahulu
- Tambahkan credit di caption: `"Credit: @namaChannel | Sumber: [link]"`
- Cari video Creative Commons: YouTube → Filter → **Creative Commons**

### Troubleshooting

| Error | Solusi |
|-------|--------|
| `docker not running` | Buka Docker Desktop, tunggu ready |
| `'ffmpeg' is not recognized` | Cek PATH, buka CMD baru |
| `can't open file auto_clipper.py` | Cek path script di clipper_server.py |
| `port 5679 conflict` | n8n Task Broker pakai 5679, clipper server pakai **5680** |
| `Invalid URL: =http://...` | Di node Run Auto Clipper, ganti ke mode **Fixed** (bukan Expression) |
| `Hanya 3 klip keluar` | Kurangi durasi klip (coba 30–60 detik) atau perlebar overlap threshold |
| `Subtitle tidak muncul` | Pastikan ffmpeg versi terbaru dan path .ass tidak ada karakter aneh |

---

## 🗺️ Roadmap

- [x] Auto download & clip video
- [x] Subtitle otomatis per kata (putih/kuning)
- [x] Custom durasi dari form input
- [x] Nama folder dari judul video
- [ ] Connect Google Sheets untuk logging
- [ ] Auto posting ke TikTok via API
- [ ] Auto posting ke Instagram via Meta Graph API
- [ ] YouTube OAuth untuk ambil video channel otomatis
- [ ] GPU acceleration untuk transkripsi lebih cepat

---

## 📦 Versi

| Versi | Perubahan |
|-------|-----------|
| v1 | Workflow dasar, ganti Vizard dengan Python lokal |
| v2 | Ganti executeCommand → HTTP server (port 5680) |
| v3 | Tambah input durasi min/max dari form |
| v4 | Subtitle random position |
| v5 | Dynamic font size per kata |
| v6 | Subtitle fixed di bawah + nama folder dari judul video |
| v7 | **Current** — Per kata, Impact font, ukuran seragam, kuning/putih |

---

*Dibuat dengan bantuan Claude AI (Anthropic) · Mei 2026*
