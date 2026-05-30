"""
Auto Clipper HTTP Server v6
- POST /clip        → proses video + upload ke Facebook + Instagram
- GET  /health      → health check
- GET  /serve?path= → serve file video lokal
- POST /set-ngrok   → update tunnel URL
Port: 5680

Instagram upload pakai Resumable Upload API (tanpa URL publik!)
Facebook upload pakai direct multipart (tanpa URL publik!)
"""

import subprocess, json, sys, os, mimetypes, time
import urllib.request, urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse, unquote, quote

SCRIPT_PATH  = os.path.join(os.path.dirname(__file__), "auto_clipper.py")
OUTPUT_DIR   = "D:\\clips"
PORT         = 5680

FORM_HTML = open(__file__.replace('clipper_server.py','form.html'), encoding='utf-8').read() if __import__('os').path.exists(__file__.replace('clipper_server.py','form.html')) else '<h1>Form not found</h1>'
NGROK_URL    = os.environ.get("NGROK_URL", "").rstrip("/")
FB_API       = "https://graph.facebook.com/v25.0"
IG_UPLOAD    = "https://rupload.facebook.com/video-upload/v25.0"



# ─── Token Management ─────────────────────────────────────────────────────────

def get_ytdlp_env():
    """Pastikan Node.js ada di PATH saat subprocess dijalankan."""
    env = os.environ.copy()
    for p in [r"C:\Program Files\nodejs", r"C:\Program Files (x86)\nodejs",
              os.path.expanduser(r"~\AppData\Roaming\nvm\current")]:
        if os.path.exists(p) and p not in env.get("PATH",""):
            env["PATH"] = p + ";" + env["PATH"]
            break
    return env

CFG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "orca_config.json")

def load_config():
    try:
        if os.path.exists(CFG_PATH):
            with open(CFG_PATH, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_config(cfg):
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

def debug_token(token, app_id, app_secret):
    """Cek info token via Graph API debug_token endpoint."""
    url = f"{FB_API}/debug_token?input_token={token}&access_token={app_id}|{app_secret}"
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read().decode()).get("data", {})

def exchange_token(token, app_id, app_secret):
    """Tukar short/expiring token ke long-lived token (~60 hari)."""
    url = (f"{FB_API}/oauth/access_token"
           f"?grant_type=fb_exchange_token"
           f"&client_id={app_id}"
           f"&client_secret={app_secret}"
           f"&fb_exchange_token={token}")
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read().decode())

def check_and_refresh_tokens():
    """
    Cek expiry token FB & IG. Auto-refresh jika <10 hari.
    Return dict: {status, fb, ig, message}
    - status: "ok" | "refreshed" | "expiring_soon" | "expired" | "no_secret" | "error"
    """
    cfg = load_config()
    fb_token   = cfg.get("fb_page_token", "")
    ig_token   = cfg.get("ig_page_token", "")
    app_id     = cfg.get("app_id", "")
    app_secret = cfg.get("app_secret", "")

    if not fb_token:
        return {"status": "no_token", "message": "Token belum diset di form."}
    if not app_secret:
        return {"status": "no_secret", "message": "App Secret belum diset. Isi di form → Token Meta."}

    now = time.time()
    result = {"fb": {}, "ig": {}}

    try:
        info = debug_token(fb_token, app_id, app_secret)
        expires_at = info.get("expires_at", 0)
        days_left  = round((expires_at - now) / 86400) if expires_at else None

        if expires_at and expires_at < now:
            result["fb"] = {"status": "expired", "days_left": 0}
            return {"status": "expired", "result": result,
                    "message": "Token FB sudah expired. Perlu generate manual via Graph API Explorer."}

        if days_left is not None and days_left <= 10:
            # Auto-refresh
            try:
                new_data  = exchange_token(fb_token, app_id, app_secret)
                new_token = new_data.get("access_token", "")
                if new_token:
                    cfg["fb_page_token"] = new_token
                    cfg["ig_page_token"] = new_token  # biasanya sama
                    save_config(cfg)
                    result["fb"] = {"status": "refreshed", "days_left": days_left}
                    result["ig"] = {"status": "refreshed"}
                    return {"status": "refreshed", "result": result,
                            "message": f"Token berhasil di-refresh otomatis! Sisa {days_left} hari sebelumnya."}
                else:
                    result["fb"] = {"status": "refresh_failed", "days_left": days_left}
                    return {"status": "refresh_failed", "result": result,
                            "message": f"Gagal refresh token otomatis (sisa {days_left} hari). Perlu generate manual."}
            except Exception as re:
                result["fb"] = {"status": "refresh_failed", "days_left": days_left, "error": str(re)}
                return {"status": "refresh_failed", "result": result,
                        "message": f"Gagal refresh token: {re}. Perlu generate manual via Graph API Explorer."}

        result["fb"] = {"status": "ok", "days_left": days_left}
        result["ig"] = {"status": "ok"}
        return {"status": "ok", "result": result,
                "message": f"Token OK — sisa {days_left} hari." if days_left else "Token OK (no expiry)."}

    except Exception as e:
        return {"status": "error", "result": result,
                "message": f"Gagal cek token: {e}"}



def get_serve_url(file_path: str) -> str:
    encoded = quote(file_path, safe="")
    if NGROK_URL:
        return f"{NGROK_URL}/serve?path={encoded}"
    # Tanpa Docker → pakai localhost langsung
    return f"http://localhost:{PORT}/serve?path={encoded}"


def http_post_json(url, data: dict, token: str) -> dict:
    """POST JSON ke Graph API."""
    body = json.dumps(data).encode()
    req  = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type":   "application/json",
        "Authorization":  f"OAuth {token}",
        "Content-Length": str(len(body)),
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def http_get_json(url) -> dict:
    """GET JSON dari Graph API."""
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


# ─── Facebook Upload ───────────────────────────────────────────────────────────


# ── Scheduled upload: Facebook ────────────────────────────────────────────
def upload_to_facebook_scheduled(file_path, page_id, page_token, caption, schedule_ts):
    """Upload video ke Facebook dengan jadwal Meta native."""
    import datetime
    try:
        print(f"[FB-SCHED] Upload: {os.path.basename(file_path)} → {datetime.datetime.fromtimestamp(schedule_ts).strftime('%d %b %Y %H:%M')}")
        with open(file_path,"rb") as f:
            video_bytes = f.read()
        boundary = "----OrcaBoundary" + os.urandom(8).hex()
        def part(name, value):
            return (f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n').encode()
        body = (
            part("description", caption) +
            part("published", "false") +
            part("scheduled_publish_time", str(int(schedule_ts))) +
            part("privacy", '{"value":"EVERYONE"}') +
            part("access_token", page_token) +
            (f"--{boundary}\r\n"
             f'Content-Disposition: form-data; name="source"; filename="{os.path.basename(file_path)}"\r\n'
             f'Content-Type: video/mp4\r\n\r\n').encode() +
            video_bytes +
            f"\r\n--{boundary}--\r\n".encode()
        )
        req = urllib.request.Request(
            f"{FB_API}/{page_id}/videos", data=body, method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                     "Content-Length": str(len(body))}
        )
        with urllib.request.urlopen(req, timeout=600) as r:
            resp = json.loads(r.read().decode())
        video_id = resp.get("id","")
        sched_str = datetime.datetime.fromtimestamp(schedule_ts).strftime("%d %b %Y %H:%M")

        # Ambil post_id (ID yang muncul di Creator Studio) via query tambahan
        post_id = video_id  # fallback ke video_id
        try:
            query_url = f"{FB_API}/{video_id}?fields=post_id&access_token={page_token}"
            with urllib.request.urlopen(query_url, timeout=15) as qr:
                qresp = json.loads(qr.read().decode())
                if qresp.get("post_id"):
                    post_id = qresp["post_id"]
                    print(f"[FB-SCHED] Creator Studio ID: {post_id}")
        except Exception as qe:
            print(f"[FB-SCHED] Gagal ambil post_id: {qe}, pakai video_id")

        print(f"[FB-SCHED] ✅ Dijadwal! post_id={post_id}")
        return {"success":True,"platform":"fb","post_id":post_id,"scheduled_time":sched_str+" WIB"}
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"[FB-SCHED] ❌ HTTP {e.code}: {err}")
        return {"success":False,"platform":"fb","error":f"HTTP {e.code}: {err[:200]}"}
    except Exception as e:
        print(f"[FB-SCHED] ❌ {e}")
        return {"success":False,"platform":"fb","error":str(e)}


# ── Scheduled upload: Instagram ───────────────────────────────────────────
def upload_to_instagram_scheduled(file_path, ig_user_id, page_token, caption, schedule_ts):
    """Upload Reels ke Instagram dengan jadwal Meta native. Tidak perlu media_publish."""
    import datetime, requests as req_lib
    try:
        encoded_path = reencode_for_instagram(file_path)
        file_size    = os.path.getsize(encoded_path)
        duration_ms  = get_video_duration_ms(encoded_path)
        sched_str    = datetime.datetime.fromtimestamp(schedule_ts).strftime("%d %b %Y %H:%M")
        print(f"[IG-SCHED] Upload: {os.path.basename(file_path)} → {sched_str}")
        print(f"[IG-SCHED] file_size={file_size}, duration_ms={duration_ms}")

        # Step 1: Init container — kirim sebagai integer, bukan string
        init_url = f"{FB_API}/{ig_user_id}/media?access_token={page_token}"
        init_body = json.dumps({
            "media_type": "REELS",
            "upload_type": "resumable",
            "caption": caption,
            "share_to_feed": "true",
            "video_duration": int(duration_ms),        # integer!
            "video_size_bytes": int(file_size),        # integer!
            "scheduled_publish_time": int(schedule_ts),
            "status": "SCHEDULED",
        }).encode()
        req_init = urllib.request.Request(init_url, data=init_body, method="POST", headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(init_body)),
        })
        try:
            with urllib.request.urlopen(req_init, timeout=60) as r:
                init_resp = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            print(f"[IG-SCHED] ❌ Init container gagal HTTP {e.code}: {err_body}")
            raise Exception(f"HTTP {e.code}: {err_body[:300]}")

        upload_id  = init_resp.get("id")
        upload_uri = init_resp.get("uri")
        if not upload_id:
            raise Exception(f"Gagal init container: {init_resp}")
        print(f"[IG-SCHED] Container ID: {upload_id}")

        # Step 2: Upload binary
        upload_url = upload_uri or f"{IG_UPLOAD}/{upload_id}"
        CHUNK = 10 * 1024 * 1024
        with open(encoded_path,"rb") as f:
            offset = 0; n = 0
            while True:
                chunk = f.read(CHUNK)
                if not chunk: break
                n += 1
                r = req_lib.post(upload_url, data=chunk, timeout=300, headers={
                    "Authorization": f"OAuth {page_token}",
                    "offset": str(offset),
                    "file_size": str(file_size),
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(len(chunk)),
                })
                print(f"[IG-SCHED] Chunk {n} → HTTP {r.status_code}")
                if r.status_code >= 400:
                    raise Exception(f"Chunk {n} gagal HTTP {r.status_code}: {r.text[:200]}")
                offset += len(chunk)

        # Step 3: Tidak perlu media_publish — Meta auto-publish saat jadwal tiba
        if encoded_path != file_path and os.path.exists(encoded_path):
            os.remove(encoded_path)
        print(f"[IG-SCHED] ✅ Dijadwal! container_id={upload_id}")
        return {"success":True,"platform":"ig","container_id":upload_id,"scheduled_time":sched_str+" WIB"}

    except Exception as e:
        print(f"[IG-SCHED] ❌ {e}")
        return {"success":False,"platform":"ig","error":str(e)}

def upload_to_facebook(file_path, page_id, page_token, description=""):
    """Upload video langsung ke Facebook Page via multipart (tanpa URL publik)."""
    try:
        boundary = "AutoClipperFBv6"
        url      = f"{FB_API}/{page_id}/videos"
        file_size = os.path.getsize(file_path)
        print(f"[FB] Upload: {os.path.basename(file_path)} ({file_size:,} bytes)")

        def field(name, value):
            return (f"--{boundary}\r\nContent-Disposition: form-data; "
                    f'name="{name}"\r\n\r\n{value}\r\n').encode()

        parts = [
            field("description", description),
            field("published",   "true"),
            field("access_token", page_token),
            (f"--{boundary}\r\nContent-Disposition: form-data; "
             f'name="source"; filename="clip.mp4"\r\nContent-Type: video/mp4\r\n\r\n').encode(),
        ]
        with open(file_path, "rb") as f:
            parts.append(f.read())
        parts.append(f"\r\n--{boundary}--\r\n".encode())
        body = b"".join(parts)

        req = urllib.request.Request(url, data=body, method="POST", headers={
            "Content-Type":   f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        })
        with urllib.request.urlopen(req, timeout=300) as r:
            result = json.loads(r.read().decode())
            print(f"[FB] ✅ Berhasil! id={result.get('id')}")
            return {"success": True, "platform": "facebook", "data": result}

    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"[FB] ❌ HTTP {e.code}: {err}")
        return {"success": False, "platform": "facebook", "error": f"HTTP {e.code}: {err}"}
    except Exception as e:
        print(f"[FB] ❌ Error: {e}")
        return {"success": False, "platform": "facebook", "error": str(e)}


# ─── Instagram Upload (Resumable, tanpa URL publik!) ──────────────────────────


def reencode_for_instagram(input_path):
    """Re-encode video dengan setting Instagram-compatible (H.264 Main profile)."""
    import subprocess, tempfile, os
    out_path = input_path.replace(".mp4", "_ig.mp4")
    cmd = [
        "ffmpeg", "-i", input_path,
        "-vf", "scale=720:-2",  # 720p — file lebih kecil untuk IG
        "-c:v", "libx264",
        "-profile:v", "main",
        "-level:v", "4.0",
        "-pix_fmt", "yuv420p",
        "-crf", "30",           # CRF 30 — target file < 10MB
        "-preset", "fast",
        "-c:a", "aac",
        "-b:a", "96k",
        "-ar", "44100",
        "-ac", "2",
        "-movflags", "+faststart",
        "-y", out_path,
        "-loglevel", "quiet"
    ]
    print(f"[IG] Re-encoding for Instagram compatibility...")
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0 or not os.path.exists(out_path):
        print(f"[IG] Re-encode gagal, pakai file original")
        return input_path
    print(f"[IG] Re-encode selesai: {os.path.getsize(out_path):,} bytes")
    return out_path

def get_video_duration_ms(file_path):
    """Ambil durasi video dalam milidetik pakai ffprobe."""
    try:
        import subprocess
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_streams", file_path],
            capture_output=True, text=True
        )
        import json as _json
        data = _json.loads(result.stdout)
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                dur = float(stream.get("duration", 0))
                return int(dur * 1000)
    except Exception as e:
        print(f"[IG] ffprobe error: {e}")
    return 30000  # fallback 30 detik


def upload_to_instagram(file_path, ig_user_id, page_token, caption="", video_url=""):
    """
    Upload video ke Instagram Reels via Resumable Upload API.
    Flow:
    1. Init container (dengan video_duration + video_size_bytes)
    2. Upload binary ke rupload.facebook.com
    3. Tunggu status FINISHED
    4. Publish
    """
    try:
        # Re-encode untuk kompatibilitas Instagram (H.264 Main profile)
        encoded_path = reencode_for_instagram(file_path)
        file_size    = os.path.getsize(encoded_path)
        duration_ms  = get_video_duration_ms(encoded_path)
        print(f"[IG] Upload: {os.path.basename(file_path)} ({file_size:,} bytes, {duration_ms}ms)")

        # ── Step 1: Init upload container ─────────────────────────────────────
        print("[IG] Step 1/4 — Init upload container...")
        init_url  = f"{FB_API}/{ig_user_id}/media"
        init_data = {
            "media_type":       "REELS",
            "upload_type":      "resumable",
            "caption":          caption,
            "share_to_feed":    "true",
            "video_duration":   str(duration_ms),
            "video_size_bytes": str(file_size),
            "access_token":     page_token,
        }
        init_resp  = http_post_json(init_url, init_data, page_token)
        upload_id  = init_resp.get("id")
        upload_uri = init_resp.get("uri")
        if not upload_id:
            raise Exception(f"Gagal init container: {init_resp}")
        print(f"[IG] Upload ID : {upload_id}")
        print(f"[IG] Upload URI: {upload_uri}")

        # ── Step 2: Upload binary ──────────────────────────────────────────────
        print("[IG] Step 2/4 — Uploading video binary...")
        upload_url = upload_uri or f"{IG_UPLOAD}/{upload_id}"

        try:
            import requests as req_lib
        except ImportError:
            import subprocess as _sp, sys as _sys
            _sp.run([_sys.executable, "-m", "pip", "install", "requests", "-q"], check=True)
            import requests as req_lib

        CHUNK_SIZE = 15 * 1024 * 1024  # 15MB — pastikan file 720p < 15MB = single chunk
        print(f"[IG] Upload URL: {upload_url}")
        print(f"[IG] File size: {file_size:,} bytes | Chunk size: {CHUNK_SIZE//1024//1024}MB")

        with open(encoded_path, "rb") as f:
            offset = 0
            chunk_num = 0
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                chunk_len = len(chunk)
                chunk_num += 1
                upload_headers = {
                    "Authorization":  f"OAuth {page_token}",
                    "offset":         str(offset),
                    "file_size":      str(file_size),
                    "Content-Type":   "application/octet-stream",
                    "Content-Length": str(chunk_len),
                }
                print(f"[IG] Chunk {chunk_num}: offset={offset}, size={chunk_len}")
                r2  = req_lib.post(upload_url, data=chunk, headers=upload_headers, timeout=120)
                raw = r2.text
                print(f"[IG] Chunk {chunk_num} HTTP {r2.status_code}: {raw[:100]}")
                if r2.status_code >= 400:
                    raise Exception(f"Upload chunk {chunk_num} gagal HTTP {r2.status_code}: {raw}")
                offset += chunk_len

        print(f"[IG] Semua {chunk_num} chunk berhasil diupload")

        # ── Step 3: Tunggu status FINISHED ────────────────────────────────────
        print("[IG] Step 3/4 — Menunggu video diproses...")
        status_url = f"{FB_API}/{upload_id}?fields=status_code&access_token={page_token}"
        for attempt in range(20):
            time.sleep(5)
            status = http_get_json(status_url)
            code   = status.get("status_code", "")
            print(f"[IG] Status: {code} (attempt {attempt+1}/20)")
            if code == "FINISHED":
                break
            if code == "ERROR":
                raise Exception(f"Video processing error: {status}")
        else:
            raise Exception("Timeout menunggu video diproses Instagram")

        # ── Step 4: Publish ───────────────────────────────────────────────────
        print("[IG] Step 4/4 — Publishing Reel...")
        publish_url  = f"{FB_API}/{ig_user_id}/media_publish"
        publish_data = {
            "creation_id":  upload_id,
            "access_token": page_token,
        }
        publish_resp = http_post_json(publish_url, publish_data, page_token)
        ig_media_id  = publish_resp.get("id")
        if not ig_media_id:
            raise Exception(f"Publish gagal: {publish_resp}")

        print(f"[IG] ✅ Berhasil! media_id={ig_media_id}")
        # Hapus file re-encoded sementara
        if encoded_path != file_path and os.path.exists(encoded_path):
            os.remove(encoded_path)
        return {"success": True, "platform": "instagram", "data": {"id": ig_media_id}}

    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"[IG] ❌ HTTP {e.code}: {err}")
        return {"success": False, "platform": "instagram", "error": f"HTTP {e.code}: {err}"}
    except Exception as e:
        print(f"[IG] ❌ Error: {e}")
        return {"success": False, "platform": "instagram", "error": str(e)}


# ─── MEGA Upload ──────────────────────────────────────────────────────────────

MEGACMD_PUT = r"C:\Users\mfajr\AppData\Local\MEGAcmd\mega-put.bat"
MEGA_FOLDERS = {
    "gaming":                 "/OrcaClip/Gaming",
    "ekonomi":                "/OrcaClip/Ekonom, Edukasi, Dakwah",
    "edukasi":                "/OrcaClip/Ekonom, Edukasi, Dakwah",
    "dakwah":                 "/OrcaClip/Ekonom, Edukasi, Dakwah",
    "ekonomi_edukasi_dakwah": "/OrcaClip/Ekonom, Edukasi, Dakwah",
}

def upload_to_mega(clips_dir, tema):
    """Upload seluruh folder klip ke MEGA dengan struktur subfolder. Return (success, msg)."""
    base_folder = MEGA_FOLDERS.get((tema or "").lower(), "/OrcaClip")
    folder_name = os.path.basename(clips_dir.rstrip("\\/"))
    mega_dest   = base_folder + "/"
    print(f"[MEGA] Upload folder: {folder_name} → {base_folder}/{folder_name}/")
    try:
        # mega-put -c dengan folder → otomatis buat subfolder di MEGA
        result = subprocess.run(
            [MEGACMD_PUT, "-c", clips_dir, mega_dest],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=600
        )
        out = (result.stdout + result.stderr).strip()
        if result.returncode == 0:
            print(f"[MEGA] ✅ Folder {folder_name} berhasil diupload ke {base_folder}/")
            return True, f"Upload ke {base_folder}/{folder_name}/ berhasil"
        else:
            print(f"[MEGA] ❌ Gagal: {out[:200]}")
            return False, out[:200]
    except Exception as e:
        print(f"[MEGA] ❌ Exception: {e}")
        return False, str(e)


# ─── HTTP Server ───────────────────────────────────────────────────────────────

class ClipperHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[Server] {format % args}")

    def send_json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type",   "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/progress":
            progress_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "progress.json")
            try:
                if os.path.exists(progress_path):
                    with open(progress_path, encoding="utf-8") as f:
                        self.send_json(200, json.load(f))
                else:
                    self.send_json(200, {"step":"idle","message":"","percent":0,"status":"idle"})
            except Exception:
                self.send_json(200, {"step":"idle","message":"","percent":0,"status":"idle"})
            return

        if parsed.path == "/token-status":
            result = check_and_refresh_tokens()
            self.send_json(200, result)
            return

        if parsed.path == "/health":
            self.send_json(200, {
                "status":  "ok",
                "version": "v6",
                "message": "Auto Clipper v6 — FB + IG Direct Upload!",
                "tunnel":  NGROK_URL or "(tidak diperlukan)",
            })
            return

        if parsed.path == "/serve":
            params    = parse_qs(parsed.query)
            file_path = unquote(params.get("path", [""])[0])
            if not file_path or not os.path.exists(file_path):
                self.send_json(404, {"error": f"File tidak ditemukan: {file_path}"})
                return
            abs_out  = os.path.abspath(OUTPUT_DIR)
            abs_file = os.path.abspath(file_path)
            if not abs_file.startswith(abs_out):
                self.send_json(403, {"error": "Akses ditolak"})
                return
            mime      = mimetypes.guess_type(file_path)[0] or "video/mp4"
            file_size = os.path.getsize(file_path)
            print(f"[Server] Serving: {file_path} ({file_size:,} bytes)")
            self.send_response(200)
            self.send_header("Content-Type",   mime)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            try:
                with open(encoded_path, "rb") as f:
                    while chunk := f.read(65536):
                        self.wfile.write(chunk)
            except (ConnectionAbortedError, BrokenPipeError, OSError):
                pass  # Client disconnect di tengah stream — normal, abaikan
            return

        self.send_json(404, {"error": "Endpoint tidak ditemukan"})

    def do_POST(self):
        global NGROK_URL
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)

        if self.path == "/save-tokens":
            try:
                payload = json.loads(body)
            except Exception:
                self.send_json(400, {"error": "Body bukan JSON valid"}); return
            cfg = load_config()
            if payload.get("fb_page_token"):  cfg["fb_page_token"] = payload["fb_page_token"]
            if payload.get("ig_page_token"):  cfg["ig_page_token"] = payload["ig_page_token"]
            if payload.get("app_secret"):     cfg["app_secret"]    = payload["app_secret"]
            if payload.get("fb_page_id"):     cfg["fb_page_id"]    = payload["fb_page_id"]
            if payload.get("ig_user_id"):     cfg["ig_user_id"]    = payload["ig_user_id"]
            cfg.setdefault("app_id", "800167919632211")
            save_config(cfg)
            print("[Server] Tokens disimpan ke orca_config.json")
            self.send_json(200, {"ok": True})
            return

        if self.path == "/set-ngrok":
            try:
                payload = json.loads(body)
                new_url = payload.get("url", "").strip().rstrip("/")
                if not new_url.startswith("http"):
                    self.send_json(400, {"error": "URL tidak valid"})
                    return
                NGROK_URL = new_url
                print(f"[Server] ✅ Tunnel URL: {NGROK_URL}")
                self.send_json(200, {"status": "ok", "tunnel_url": NGROK_URL})
            except Exception as e:
                self.send_json(400, {"error": str(e)})
            return

        if self.path == "/schedule-upload":
            try:
                length  = int(self.headers.get("Content-Length",0))
                payload = json.loads(self.rfile.read(length).decode())
            except Exception as e:
                self.send_json(400,{"error":str(e)}); return

            clips = payload.get("clips",[])
            # Load cached tokens — gunakan load_config() terpusat
            cfg = load_config()
            fb_page_id = payload.get("fb_page_id") or cfg.get("fb_page_id","")
            fb_token   = payload.get("fb_page_token") or cfg.get("fb_page_token","")
            ig_user_id = payload.get("ig_user_id") or cfg.get("ig_user_id","")
            ig_token   = payload.get("ig_page_token") or cfg.get("ig_page_token","")

            import time as _time
            results = []
            for i, clip in enumerate(clips):
                vpath    = clip.get("video_path","")
                caption  = clip.get("caption","")
                title    = clip.get("title","") or os.path.basename(vpath) or f"Clip {i+1}"
                fb_ts    = clip.get("fb_schedule")
                ig_ts    = clip.get("ig_schedule")
                name     = os.path.basename(vpath) if vpath else f"clip_{i+1}"
                now      = _time.time()
                MIN_GAP  = 1200  # 20 menit

                if fb_ts:
                    if not (fb_page_id and fb_token):
                        results.append({"clip":name,"title":title,"platform":"fb","success":False,"error":"Token FB tidak ada"})
                    elif fb_ts < now + MIN_GAP:
                        results.append({"clip":name,"title":title,"platform":"fb","success":False,"error":"Jadwal harus ≥20 menit dari sekarang"})
                    elif not os.path.exists(vpath):
                        results.append({"clip":name,"title":title,"platform":"fb","success":False,"error":"File tidak ditemukan"})
                    else:
                        r = upload_to_facebook_scheduled(vpath, fb_page_id, fb_token, caption, fb_ts)
                        r["clip"] = name; r["title"] = title; results.append(r)

                if ig_ts:
                    if not (ig_user_id and ig_token):
                        results.append({"clip":name,"title":title,"platform":"ig","success":False,"error":"Token IG tidak ada"})
                    elif ig_ts < now + MIN_GAP:
                        results.append({"clip":name,"title":title,"platform":"ig","success":False,"error":"Jadwal harus ≥20 menit dari sekarang"})
                    elif not os.path.exists(vpath):
                        results.append({"clip":name,"title":title,"platform":"ig","success":False,"error":"File tidak ditemukan"})
                    else:
                        r = upload_to_instagram_scheduled(vpath, ig_user_id, ig_token, caption, ig_ts)
                        r["clip"] = name; r["title"] = title; results.append(r)

            ok  = sum(1 for r in results if r.get("success"))
            fail = len(results) - ok
            print(f"[Server] Schedule-upload selesai: {ok} berhasil, {fail} gagal")
            self.send_json(200,{"results":results,"ok":ok,"fail":fail})
            return

        if self.path == "/run-bat":
            bat = r"D:\Tools\jalankan_semua.bat"
            try:
                import subprocess as _sp
                _sp.Popen(f'start cmd /k "{bat}"', shell=True)
                self.send_json(200, {"success": True})
            except Exception as e:
                self.send_json(500, {"success": False, "msg": str(e)})
            return

        if self.path != "/clip":
            self.send_json(404, {"error": "Endpoint tidak ditemukan"})
            return

        try:
            payload = json.loads(body)
        except Exception:
            self.send_json(400, {"code": 9000, "errMsg": "Body bukan JSON valid"})
            return

        video_url       = payload.get("url",            "").strip()
        # Strip karakter '=' di awal URL (artefak n8n expression syntax)
        import re as _re
        video_url = _re.sub(r'^=+', '', video_url).strip()
        output_dir      = payload.get("output_dir",     OUTPUT_DIR).strip()
        min_dur         = int(payload.get("min_dur",    10))
        max_dur         = int(payload.get("max_dur",    90))
        min_viral_score = int(payload.get("min_viral_score", 0))
        yt_mode         = str(payload.get("yt_mode",    "false")).lower() in ("true","1","yes")
        upload_fb       = str(payload.get("upload_fb",  "true")).lower()  not in ("false","0","no")
        upload_ig       = str(payload.get("upload_ig",  "true")).lower()  not in ("false","0","no")
        fb_page_id      = payload.get("fb_page_id",     "").strip()
        fb_token        = payload.get("fb_page_token",  "").strip()
        ig_user_id      = payload.get("ig_user_id",     "").strip()
        ig_token        = payload.get("ig_page_token",  "").strip()
        app_secret      = payload.get("app_secret",     "").strip()
        schedule_mode   = str(payload.get("schedule_mode","false")).lower() in ("true","1","yes")

        if not video_url:
            self.send_json(400, {"code": 9000, "errMsg": "Field 'url' wajib diisi"})
            return
        if min_dur >= max_dur:
            self.send_json(400, {"code": 9000, "errMsg": f"min_dur harus < max_dur"})
            return

        os.makedirs(output_dir, exist_ok=True)
        # Reset progress file
        progress_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "progress.json")
        try:
            with open(progress_path, "w", encoding="utf-8") as f:
                json.dump({"step":"start","message":"Memulai proses...","percent":2,"status":"active","ts":0}, f)
        except Exception:
            pass
        print(f"[Server] URL         : {video_url}")
        print(f"[Server] Durasi      : {min_dur}-{max_dur}s")
        print(f"[Server] Min score   : {min_viral_score}")
        print(f"[Server] YT Mode     : {'✅ AKTIF — skip upload' if yt_mode else '❌'}")
        print(f"[Server] FB upload   : {'✅' if upload_fb and fb_page_id and fb_token else '❌'}")
        print(f"[Server] IG upload   : {'✅' if upload_ig and ig_user_id and ig_token else '❌'}")
        print(f"[Server] Sched mode  : {'✅ AKTIF' if schedule_mode else '❌'}")
        # Cache tokens
        if fb_page_id and fb_token and ig_user_id and ig_token:
            cfg = load_config()
            cfg.update({"fb_page_id": fb_page_id, "fb_page_token": fb_token,
                        "ig_user_id": ig_user_id, "ig_page_token": ig_token,
                        "app_id": "800167919632211"})
            if app_secret:
                cfg["app_secret"] = app_secret
            save_config(cfg)

        try:
            env = get_ytdlp_env()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"
            result = subprocess.run(
                [sys.executable, SCRIPT_PATH, video_url, output_dir,
                 str(min_dur), str(max_dur)],
                capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=7200,
                env=env,
            )
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            if stderr:
                print(f"[Script]\n{stderr}")

            json_line = ""
            for line in reversed(stdout.split("\n")):
                line = line.strip()
                if line.startswith("{"):
                    json_line = line
                    break

            if not json_line:
                err_msg = "Tidak ada output JSON. " + stderr[:300]
                try:
                    with open(progress_path,"w",encoding="utf-8") as f:
                        json.dump({"step":"error","message":err_msg,"percent":0,"status":"error","ts":0},f)
                except Exception: pass
                self.send_json(500, {"code": 9000, "errMsg": err_msg})
                return

            output = json.loads(json_line)

            if output.get("code") != 2000:
                err_msg = output.get("errMsg","Error tidak diketahui")
                try:
                    with open(progress_path,"w",encoding="utf-8") as f:
                        json.dump({"step":"error","message":err_msg,"percent":0,"status":"error","ts":0},f)
                except Exception: pass
                self.send_json(500, {"code": 9000, "errMsg": err_msg})
                return

            if output.get("code") == 2000 and output.get("videos"):
                videos = output["videos"]

                # ── Filter berdasarkan min_viral_score ─────────────────────────
                if min_viral_score > 0:
                    before = len(videos)
                    videos = [v for v in videos if v.get("viralScore", 0) >= min_viral_score]
                    print(f"[Server] Filter score ≥{min_viral_score}: {before} → {len(videos)} klip")
                    output["videos"] = videos

                if not videos:
                    self.send_json(200, {**output, "videos": [],
                        "errMsg": f"Tidak ada klip dengan viral score ≥ {min_viral_score}"})
                    return

                # ── YT Mode: skip semua upload ─────────────────────────────────
                if yt_mode:
                    tema = payload.get("tema","").strip().lower()
                    print(f"[Server] YT Mode aktif — skip semua upload, {len(videos)} klip siap")
                    print(f"[Server] Tema MEGA: {tema or '(tidak diset)'}")

                    # Set serveUrl untuk semua video
                    for video in videos:
                        file_path = video.get("videoUrl", "")
                        if file_path:
                            video["serveUrl"] = get_serve_url(file_path)
                        video["facebookUpload"]   = {"success": False, "platform": "facebook",  "error": "YT Mode aktif"}
                        video["instagramUpload"]  = {"success": False, "platform": "instagram", "error": "YT Mode aktif"}
                        video["facebookVideoId"]  = ""
                        video["instagramMediaId"] = ""

                    # Upload seluruh folder sekaligus (termasuk .txt)
                    mega_result = {"success": False, "msg": "Tema tidak diset"}
                    if tema and videos:
                        first_path = videos[0].get("videoUrl", "")
                        clips_dir  = os.path.dirname(first_path) if first_path else ""
                        if clips_dir and os.path.isdir(clips_dir):
                            ok, msg = upload_to_mega(clips_dir, tema)
                            mega_result = {"success": ok, "msg": msg,
                                           "folder": MEGA_FOLDERS.get(tema, "/OrcaClip")}
                        else:
                            mega_result = {"success": False, "msg": "Folder klip tidak ditemukan"}

                    for video in videos:
                        video["megaUpload"] = mega_result

                    self.send_json(200, output)
                    return

                # ── Persiapan: set serveUrl & caption tiap video ───────────────
                for video in videos:
                    file_path   = video.get("videoUrl", "")
                    video_title = video.get("videoTitle", "")
                    clip_title  = video.get("title", "")
                    if file_path:
                        video["serveUrl"] = get_serve_url(file_path)

                    # Baca caption dari .txt yang digenerate auto_clipper
                    caption_file = video.get("captionFile", "")
                    if caption_file and os.path.exists(caption_file):
                        with open(caption_file, "r", encoding="utf-8") as cf:
                            caption = cf.read().strip()
                        print(f"[Server] Caption dari file: {os.path.basename(caption_file)}")
                    else:
                        # Fallback kalau .txt tidak ada
                        caption = (
                            f"{clip_title}\n\n"
                            f"📺 {video_title}\n"
                            f"🔗 {video_url}\n\n"
                            f"#shorts #reels #fyp #orcaclip"
                        )
                        print(f"[Server] Caption fallback untuk: {clip_title[:40]}")
                    video["_caption"] = caption

                # ── Facebook upload ────────────────────────────────────────────
                for video in videos:
                    file_path = video.get("videoUrl", "")
                    if upload_fb and fb_page_id and fb_token and file_path and os.path.exists(file_path):
                        fb_result = upload_to_facebook(file_path, fb_page_id, fb_token, video["_caption"])
                        video["facebookUpload"]  = fb_result
                        video["facebookVideoId"] = fb_result.get("data", {}).get("id", "") if fb_result["success"] else ""
                    else:
                        reason = "YT Mode" if yt_mode else ("upload_fb=false" if not upload_fb else "token tidak ada")
                        video["facebookUpload"]  = {"success": False, "platform": "facebook", "error": reason}
                        video["facebookVideoId"] = ""
                # ── (uncomment blok di bawah untuk aktifkan FB auto-upload) ────
                # for video in videos:
                #     file_path = video.get("videoUrl", "")
                #     if not (file_path and os.path.exists(file_path)):
                #         continue
                #     if fb_page_id and fb_token:
                #         fb_result = upload_to_facebook(
                #             file_path, fb_page_id, fb_token, video["_caption"])
                #         video["facebookUpload"]  = fb_result
                #         video["facebookVideoId"] = (
                #             fb_result.get("data", {}).get("id", "")
                #             if fb_result["success"] else ""
                #         )

                # ── Instagram upload (BEST-EFFORT + RETRY 3x) ──────────────────
                if upload_ig and ig_user_id and ig_token:
                    MAX_RETRY    = 3
                    RETRY_DELAY  = 10  # detik antar retry
                    ig_ok_count  = 0
                    ig_fail_count = 0

                    for video in videos:
                        file_path = video.get("videoUrl", "")
                        if not (file_path and os.path.exists(file_path)):
                            continue

                        ig_result = None
                        for attempt in range(1, MAX_RETRY + 1):
                            if attempt > 1:
                                print(f"[IG] ⏳ Retry {attempt}/{MAX_RETRY} — tunggu {RETRY_DELAY}s...")
                                time.sleep(RETRY_DELAY)
                            ig_result = upload_to_instagram(
                                file_path, ig_user_id, ig_token, video["_caption"])
                            if ig_result["success"]:
                                break
                            print(f"[IG] Attempt {attempt} gagal: {ig_result.get('error','')[:80]}")

                        video["instagramUpload"]  = ig_result
                        video["instagramMediaId"] = (
                            ig_result.get("data", {}).get("id", "")
                            if ig_result["success"] else ""
                        )

                        if ig_result["success"]:
                            ig_ok_count += 1
                            print(f"[IG] ✅ {os.path.basename(file_path)} berhasil ({ig_ok_count} total)")
                        else:
                            ig_fail_count += 1
                            print(f"[IG] ⚠️ {os.path.basename(file_path)} dilewati setelah {MAX_RETRY}x retry")

                        # Jeda antar clip untuk hindari rate limit
                        time.sleep(3)

                    print(f"[IG] Selesai: {ig_ok_count} berhasil, {ig_fail_count} gagal")

            http_code = 200 if output.get("code") == 2000 else 500
            self.send_json(http_code, output)

        except subprocess.TimeoutExpired:
            self.send_json(500, {"code": 9000, "errMsg": "Timeout (>2 jam): video kemungkinan terlalu panjang atau Whisper berjalan lambat. Coba video yang lebih pendek (<60 menit)."})
        except Exception as e:
            self.send_json(500, {"code": 9000, "errMsg": str(e)})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), ClipperHandler)
    print(f"✅ Auto Clipper Server v6 — http://localhost:{PORT}")
    print(f"   Facebook  : Direct multipart upload ✅")
    print(f"   Instagram : Resumable upload (tanpa URL publik) ✅")
    print(f"   Health    : http://localhost:{PORT}/health")
    print(f"   Clip      : POST http://localhost:{PORT}/clip")
    print("   Tekan Ctrl+C untuk stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Server] Stopped.")