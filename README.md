# 🎬 Auto Clipper — Free Alternative to Vizard AI

> Sistem otomasi video clipping **100% gratis** menggunakan **yt-dlp + faster-whisper + ffmpeg + n8n self-hosted**.  
> Mengubah video panjang (podcast, webinar, YouTube) menjadi klip pendek vertikal 9:16 dengan subtitle otomatis — lalu **auto-post ke Facebook Page** secara otomatis.

---

## ✨ Fitur

- ✅ Download video dari YouTube (atau URL apapun)
- ✅ Transkripsi audio otomatis (lokal, tanpa API berbayar)
- ✅ Deteksi segmen viral berdasarkan scoring kata kunci
- ✅ Potong & resize video ke format **9:16 vertikal**
- ✅ Subtitle otomatis — font **Impact**, muncul **per kata**
  - Kata biasa → putih
  - Kata penting → **KUNING** (harus, viral, sukses, dll)
- ✅ Custom durasi klip dari form input
- ✅ Filter klip berdasarkan viral score minimum
- ✅ **Auto-post ke Facebook Page** (tanpa tunnel, langsung dari Python)
- ✅ Siap untuk TikTok (setelah API approved)
- ✅ Log hasil ke Google Sheets (opsional)
- ✅ Workflow otomatis via n8n (tanpa Docker!)

---

## 🛠️ Stack & Package

### 1. `yt-dlp` — Video Downloader
- **Install**: `pip install yt-dlp`
- **Fungsi**: Download video dari YouTube, TikTok, Instagram, dan 1000+ situs
- **Dokumentasi**: https://github.com/yt-dlp/yt-dlp

### 2. `faster-whisper` — Speech-to-Text Lokal
- **Install**: `pip install faster-whisper`
- **Fungsi**: Transkripsi audio ke teks secara lokal (tidak perlu internet/API key)
- **Model**: `small` — keseimbangan akurasi dan kecepatan, berjalan di CPU
- **Dokumentasi**: https://github.com/SYSTRAN/faster-whisper

### 3. `ffmpeg` — Video Processing
- **Install**: Download dari https://github.com/BtbN/ffmpeg-builds/releases → tambahkan ke PATH
- **Fungsi**: Extract audio, potong video, resize ke 9:16, burn subtitle ASS
- **Dokumentasi**: https://ffmpeg.org/documentation.html

### 4. `n8n` — Workflow Automation (tanpa Docker!)
- **Install**: `npm install -g n8n`
- **Jalankan**: `n8n start`
- **Fungsi**: Orkestrator utama — form input → Python server → Facebook → output
- **Versi**: 2.19.5+ (Community Edition, self-hosted, gratis)
- **Dokumentasi**: https://docs.n8n.io

### 5. `Node.js` — Runtime untuk n8n
- **Install**: https://nodejs.org/en/download/ → pilih LTS
- **Fungsi**: Diperlukan untuk menjalankan n8n tanpa Docker

---

## 📁 Struktur File

```
D:\Tools\
├── ffmpeg-master-latest-win64-gpl-shared\bin\   ← ffmpeg di PATH
├── n8n_scripts\
│   ├── auto_clipper.py      ← v7: subtitle per kata, Impact font
│   └── clipper_server.py    ← v5: HTTP server + direct Facebook upload
└── jalankan_semua.bat       ← jalankan semua service (2 CMD saja!)

D:\clips\                    ← hasil klip output
└── [Judul_Video_Timestamp]\
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

### Step 1 — Install ffmpeg
```bash
# 1. Download: ffmpeg-master-latest-win64-gpl-shared.zip
#    dari: https://github.com/BtbN/ffmpeg-builds/releases

# 2. Extract ke D:\Tools\

# 3. Tambahkan ke PATH Windows:
#    Windows + S → "Environment Variables" → System variables → Path → Edit → New
D:\Tools\ffmpeg-master-latest-win64-gpl-shared\bin

# 4. Verifikasi (buka CMD baru)
ffmpeg -version
```

### Step 2 — Install Python Dependencies
```bash
pip install yt-dlp faster-whisper
```

### Step 3 — Install Node.js + n8n
```bash
# 1. Download Node.js LTS dari: https://nodejs.org/en/download/
#    Install seperti biasa (Next → Next → Finish)

# 2. Install n8n (buka CMD baru)
npm install -g n8n

# 3. Verifikasi
n8n --version
```

### Step 4 — Clone Repository
```bash
git clone https://github.com/fajri-svg/auto-clipper.git D:\Tools\n8n_scripts
mkdir D:\clips
```

### Step 5 — Setup n8n Workflow
```bash
# Jalankan n8n
n8n start

# Buka browser → http://localhost:5678
# Import file: Auto_Clipper_-_GRATIS_v4__Facebook_Auto_Post_.json
# (Workflows → Import from file)
```

### Step 6 — Setup Facebook Auto Post

**Buat Facebook App di Meta for Developers:**
1. Buka https://developers.facebook.com → My Apps → Create App
2. Pilih use case: **Other** → **Business**
3. Di **App Settings → Basic**: catat `App ID` dan `App Secret`
4. Tambahkan product **Facebook Login for Business**

**Tambahkan Permission:**
- Di App Dashboard → Add Use Cases → **Manage Pages**
- Tambahkan permission: `pages_manage_posts`, `pages_read_engagement`

**Generate Page Access Token (berlaku ~60 hari):**
1. Buka [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
2. Pilih app kamu → pilih **Page** (bukan User) di dropdown token
3. Centang: `pages_manage_posts`, `pages_read_engagement`
4. Generate token → exchange ke long-lived token via browser:

```
https://graph.facebook.com/oauth/access_token
  ?grant_type=fb_exchange_token
  &client_id={APP_ID}
  &client_secret={APP_SECRET}
  &fb_exchange_token={SHORT_LIVED_TOKEN}
```

5. Ambil Page Access Token:
```
https://graph.facebook.com/v25.0/{PAGE_ID}?fields=access_token&access_token={LONG_LIVED_USER_TOKEN}
```

**Update di n8n:**
- Buka node **Configuration**
- Isi `fb_page_id` dan `fb_page_token`

---

## 🚀 Cara Menjalankan (Setiap Hari)

### Opsi A — Otomatis (Recommended)
Klik dua kali `jalankan_semua.bat` — akan membuka 2 CMD:
1. **Clipper Server** di port 5680
2. **n8n** di port 5678

### Opsi B — Manual
```bash
# CMD 1 — Python Server
python D:\Tools\n8n_scripts\clipper_server.py

# CMD 2 — n8n
n8n start
```

### Verifikasi
```
http://localhost:5680/health  → harus muncul {"status":"ok","version":"v5"}
http://localhost:5678         → buka n8n editor
```

### Jalankan Workflow
1. Buka `http://localhost:5678`
2. Buka workflow **Auto Clipper - GRATIS v4**
3. Klik **"Execute workflow from On form submission"**
4. Isi form:
   - **URL Video**: URL YouTube
   - **Skor Viral Minimum**: `70` (rekomendassi)
   - **Durasi Min**: `80` detik
   - **Durasi Maks**: `130` detik
5. Klik **"Generate & Post ke Facebook!"**
6. Tunggu ~15–20 menit

Klip otomatis ter-upload ke **Facebook Page** setelah selesai!

---

## 📊 Cara Kerja (Alur)

```
[Input Form n8n]
      ↓
[Configuration Node]  ← fb_page_id, fb_page_token, output_dir
      ↓
[HTTP POST → clipper_server.py :5680]
      ↓
[auto_clipper.py]
      ├── yt-dlp         → download video
      ├── ffmpeg         → extract audio (.wav)
      ├── faster-whisper → transkripsi + word timestamps
      ├── scoring        → deteksi segmen viral
      ├── generate_ass() → subtitle per kata (putih/kuning)
      └── ffmpeg         → potong + resize 9:16 + burn subtitle
      ↓
[clipper_server.py v5]
      └── upload_video_to_facebook() → POST langsung ke FB API ✅
      ↓
[JSON response ke n8n]
      ↓
[Split → Filter viral score → Limit Clips]
      ↓
[Facebook Result] + [Ready for TikTok]
```

> 💡 **Arsitektur baru v5**: Tidak perlu ngrok/Cloudflare tunnel!  
> Python server upload langsung ke Facebook API dari Windows, bukan dari Docker.

---

## ⏱️ Estimasi Waktu Proses

| Tahap | Estimasi | Catatan |
|---|---|---|
| Download video | 2–5 menit | Tergantung internet |
| Extract audio | ~30 detik | |
| Download model Whisper | 5–10 menit | **Hanya pertama kali** (~500MB) |
| Transkripsi audio | 10–15 menit | Video 1 jam di CPU |
| Potong + subtitle | 2–5 menit | 10 klip |
| Upload ke Facebook | 1–3 menit per klip | Tergantung ukuran file & internet |
| **Total** | **~15–25 menit** | Run berikutnya lebih cepat |

---

## 🎨 Kustomisasi Subtitle

Edit di `auto_clipper.py`:
```python
FONT_SIZE    = 72        # ukuran font — seragam semua kata
FONT_NAME    = "Impact"  # font tebal (tersedia default di Windows)
MARGIN_V     = 220       # jarak dari bawah layar (px)
```

Tambah kata highlight kuning:
```python
EMPHASIS_WORDS = [
    "harus", "wajib", "penting", "viral", "fakta",
    # tambahkan kata lain di sini...
]
```

---

## 📈 Tips Durasi per Platform

| Platform | Min (detik) | Maks (detik) |
|---|---|---|
| TikTok | 30 | 60 |
| YouTube Shorts | 15 | 60 |
| Instagram Reels | 15 | 90 |
| Facebook Reels | 60 | 130 |

**Skor viral > 80** = klip berkualitas tinggi  
**Skor viral 60–80** = klip standar  
**Skor viral < 60** = pertimbangkan skip

---

## ⚠️ Troubleshooting

| Error | Solusi |
|---|---|
| `'ffmpeg' is not recognized` | Cek PATH, buka CMD baru |
| `'n8n' is not recognized` | Pastikan Node.js terinstall, jalankan `npm install -g n8n` ulang |
| `faster-whisper not found` | `pip install faster-whisper` |
| `port 5679 conflict` | n8n Task Broker pakai 5679, clipper server pakai **5680** |
| `No permission to publish` | Token salah tipe — harus **Page Access Token**, bukan User Token |
| `Unable to fetch video file` | Tidak perlu tunnel di v5 — pastikan clipper_server.py v5 dipakai |
| `Token expired` | Generate ulang di Graph API Explorer setiap ~60 hari |
| `Hanya 3 klip` | Kurangi durasi atau turunkan viral score minimum |
| `Subtitle tidak muncul` | Pastikan ffmpeg versi terbaru |

---

## 🗺️ Roadmap

- [x] Auto download & clip video
- [x] Subtitle otomatis per kata (putih/kuning, Impact font)
- [x] Custom durasi dari form input
- [x] Auto-post ke Facebook Page ✅
- [x] n8n tanpa Docker (install langsung di Windows)
- [ ] Auto posting ke TikTok (menunggu API approval)
- [ ] Connect Google Sheets untuk logging
- [ ] GPU acceleration untuk transkripsi lebih cepat
- [ ] Schedule otomatis (posting rutin tanpa manual trigger)

---

## 📦 Changelog

| Versi | Komponen | Perubahan |
|---|---|---|
| auto_clipper v7 | Python | Subtitle per kata, Impact font, ukuran seragam, kuning/putih |
| clipper_server v5 | Python | Direct Facebook upload — tidak butuh ngrok/Cloudflare tunnel |
| Workflow v4 | n8n | Facebook Auto Post, filter viral score, limit clips |
| jalankan_semua v4 | BAT | Hapus Docker — cukup 2 CMD: clipper server + n8n Windows |

---

## 📋 File di Repository

| File | Keterangan |
|---|---|
| `auto_clipper.py` | Script utama — download, clip, subtitle (v7) |
| `clipper_server.py` | HTTP server + Facebook uploader (v5) |
| `Auto_Clipper_-_GRATIS_v4__Facebook_Auto_Post_.json` | Workflow n8n siap import |
| `jalankan_semua.bat` | Shortcut jalankan semua service |

---

## ⚖️ Copyright

- Gunakan untuk **konten milik sendiri** (podcast, rekaman pribadi)
- Jika pakai konten orang lain → minta izin terlebih dahulu
- Tambahkan credit di caption

---

*Dibuat dengan bantuan Claude AI (Anthropic) · Mei 2026*