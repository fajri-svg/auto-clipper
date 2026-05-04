"""
Auto Clipper HTTP Server v2 - Support custom duration
Jalankan: python clipper_server_v2.py
Server  : http://localhost:5680
"""

import subprocess, json, sys, os
from http.server import HTTPServer, BaseHTTPRequestHandler

SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "auto_clipper.py")
OUTPUT_DIR  = "D:\\clips"
PORT        = 5680

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
        if self.path == "/health":
            self.send_json(200, {"status": "ok", "message": "Clipper server berjalan!"})
        else:
            self.send_json(404, {"error": "Endpoint tidak ditemukan"})

    def do_POST(self):
        if self.path != "/clip":
            self.send_json(404, {"error": "Endpoint tidak ditemukan"})
            return

        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)

        try:
            payload = json.loads(body)
        except Exception:
            self.send_json(400, {"code": 9000, "errMsg": "Body bukan JSON valid"})
            return

        video_url  = payload.get("url", "").strip()
        output_dir = payload.get("output_dir", OUTPUT_DIR).strip()

        # ── Parameter durasi dari inputan user ──────────────────────────────
        min_dur = int(payload.get("min_dur", 10))
        max_dur = int(payload.get("max_dur", 90))

        if not video_url:
            self.send_json(400, {"code": 9000, "errMsg": "Field 'url' wajib diisi"})
            return

        if min_dur >= max_dur:
            self.send_json(400, {"code": 9000, "errMsg": f"min_dur ({min_dur}) harus lebih kecil dari max_dur ({max_dur})"})
            return

        os.makedirs(output_dir, exist_ok=True)

        print(f"[Server] Mulai proses: {video_url}")
        print(f"[Server] Output dir : {output_dir}")
        print(f"[Server] Durasi klip: {min_dur}-{max_dur} detik")

        try:
            result = subprocess.run(
                [sys.executable, SCRIPT_PATH, video_url, output_dir, str(min_dur), str(max_dur)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600,
            )

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            if stderr: print(f"[Script log]\n{stderr}")

            json_line = ""
            for line in reversed(stdout.split("\n")):
                line = line.strip()
                if line.startswith("{"):
                    json_line = line
                    break

            if not json_line:
                self.send_json(500, {"code": 9000, "errMsg": "Script tidak menghasilkan output JSON. " + stderr[:300]})
                return

            output    = json.loads(json_line)
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
    print(f"✅ Auto Clipper Server v2 berjalan di http://localhost:{PORT}")
    print(f"   Script : {SCRIPT_PATH}")
    print(f"   Output : {OUTPUT_DIR}")
    print(f"   Health : GET  http://localhost:{PORT}/health")
    print(f"   Clip   : POST http://localhost:{PORT}/clip")
    print("   Tekan Ctrl+C untuk stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Server] Stopped.")
