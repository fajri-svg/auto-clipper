"""
Auto Clipper HTTP Server v5
- POST /clip           → proses video + langsung upload ke Facebook
- GET  /health         → health check
- GET  /serve?path=    → serve file video lokal
- POST /set-ngrok      → update tunnel URL
Port: 5680
"""

import subprocess, json, sys, os, mimetypes
import urllib.request, urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse, unquote, quote

SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "auto_clipper.py")
OUTPUT_DIR  = "D:\\clips"
PORT        = 5680
NGROK_URL   = os.environ.get("NGROK_URL", "").rstrip("/")
FB_GRAPH_URL = "https://graph.facebook.com/v25.0"


def get_serve_url(file_path: str) -> str:
    encoded = quote(file_path, safe="")
    if NGROK_URL:
        return f"{NGROK_URL}/serve?path={encoded}"
    encoded_fb = file_path.replace("\\", "%5C").replace(":", "%3A")
    return f"http://host.docker.internal:{PORT}/serve?path={encoded_fb}"


def upload_video_to_facebook(file_path, page_id, page_token, description=""):
    """Upload video langsung ke Facebook Page — tidak butuh tunnel/URL publik."""
    try:
        boundary = "AutoClipperBoundary7MA4YWx"
        url = f"{FB_GRAPH_URL}/{page_id}/videos"
        file_size = os.path.getsize(file_path)
        print(f"[FB Upload] File  : {os.path.basename(file_path)} ({file_size:,} bytes)")
        print(f"[FB Upload] Target: {url}")

        def field_bytes(name, value):
            return (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode("utf-8")

        parts = []
        parts.append(field_bytes("description", description))
        parts.append(field_bytes("access_token", page_token))
        parts.append((
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="source"; filename="clip.mp4"\r\n'
            f"Content-Type: video/mp4\r\n\r\n"
        ).encode("utf-8"))

        with open(file_path, "rb") as f:
            video_bytes = f.read()

        parts.append(video_bytes)
        parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))

        body = b"".join(parts)
        print(f"[FB Upload] Uploading {len(body):,} bytes...")

        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body)),
            }
        )

        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read().decode())
            print(f"[FB Upload] ✅ Berhasil! id={result.get('id')}")
            return {"success": True, "data": result}

    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"[FB Upload] ❌ HTTP {e.code}: {err}")
        return {"success": False, "error": f"HTTP {e.code}: {err}"}
    except Exception as e:
        print(f"[FB Upload] ❌ Error: {e}")
        return {"success": False, "error": str(e)}


class ClipperHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[Server] {format % args}")

    def send_json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/health":
            self.send_json(200, {
                "status":  "ok",
                "version": "v5",
                "message": "Auto Clipper Server v5 — Direct Facebook Upload!",
                "tunnel":  NGROK_URL or "(tidak diperlukan untuk upload FB)",
            })
            return

        if parsed.path == "/serve":
            params    = parse_qs(parsed.query)
            file_path = unquote(params.get("path", [""])[0])

            if not file_path or not os.path.exists(file_path):
                self.send_json(404, {"error": f"File tidak ditemukan: {file_path}"})
                return

            abs_output = os.path.abspath(OUTPUT_DIR)
            abs_file   = os.path.abspath(file_path)
            if not abs_file.startswith(abs_output):
                self.send_json(403, {"error": "Akses ditolak"})
                return

            mime_type = mimetypes.guess_type(file_path)[0] or "video/mp4"
            file_size = os.path.getsize(file_path)
            print(f"[Server] Serving: {file_path} ({file_size:,} bytes)")

            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
            return

        self.send_json(404, {"error": "Endpoint tidak ditemukan"})

    def do_POST(self):
        global NGROK_URL

        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)

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

        if self.path != "/clip":
            self.send_json(404, {"error": "Endpoint tidak ditemukan"})
            return

        try:
            payload = json.loads(body)
        except Exception:
            self.send_json(400, {"code": 9000, "errMsg": "Body bukan JSON valid"})
            return

        video_url  = payload.get("url", "").strip()
        output_dir = payload.get("output_dir", OUTPUT_DIR).strip()
        min_dur    = int(payload.get("min_dur", 10))
        max_dur    = int(payload.get("max_dur", 90))
        fb_page_id = payload.get("fb_page_id", "").strip()
        fb_token   = payload.get("fb_page_token", "").strip()

        if not video_url:
            self.send_json(400, {"code": 9000, "errMsg": "Field 'url' wajib diisi"})
            return
        if min_dur >= max_dur:
            self.send_json(400, {"code": 9000, "errMsg": f"min_dur ({min_dur}) harus < max_dur ({max_dur})"})
            return

        os.makedirs(output_dir, exist_ok=True)
        print(f"[Server] URL       : {video_url}")
        print(f"[Server] Durasi    : {min_dur}-{max_dur}s")
        print(f"[Server] FB Upload : {'✅' if fb_page_id and fb_token else '❌ (no credentials)'}")

        try:
            result = subprocess.run(
                [sys.executable, SCRIPT_PATH, video_url, output_dir, str(min_dur), str(max_dur)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600,
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
                self.send_json(500, {"code": 9000, "errMsg": "Tidak ada output JSON. " + stderr[:300]})
                return

            output = json.loads(json_line)

            if output.get("code") == 2000 and output.get("videos"):
                for video in output["videos"]:
                    file_path = video.get("videoUrl", "")
                    if file_path:
                        video["serveUrl"] = get_serve_url(file_path)

                    # Upload langsung ke Facebook dari Python (tanpa tunnel!)
                    if fb_page_id and fb_token and file_path and os.path.exists(file_path):
                        desc = (
                            f"{video.get('title', '')}\n\n"
                            f"📌 {video_url}\n\n"
                            f"#viral #shorts #podcast #clip"
                        )
                        fb_result = upload_video_to_facebook(file_path, fb_page_id, fb_token, desc)
                        video["facebookUpload"] = fb_result
                        if fb_result.get("success"):
                            video["facebookVideoId"] = fb_result["data"].get("id", "")

            http_code = 200 if output.get("code") == 2000 else 500
            self.send_json(http_code, output)

        except subprocess.TimeoutExpired:
            self.send_json(500, {"code": 9000, "errMsg": "Timeout: video terlalu panjang"})
        except Exception as e:
            self.send_json(500, {"code": 9000, "errMsg": str(e)})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), ClipperHandler)
    print(f"✅ Auto Clipper Server v5 — http://localhost:{PORT}")
    print(f"   Direct Facebook Upload aktif (tidak butuh tunnel untuk upload!)")
    print(f"   Health : http://localhost:{PORT}/health")
    print(f"   Clip   : POST http://localhost:{PORT}/clip")
    print("   Tekan Ctrl+C untuk stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Server] Stopped.")