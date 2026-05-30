#!/usr/bin/env python3
"""
Auto Clipper v8
- Subtitle muncul PER KATA
- Ukuran font seragam (tidak ada yang lebih besar)
- Kata biasa : PUTIH
- Kata penting: KUNING
- Font Impact (bold, tebal, all caps style)
- Posisi: bawah tengah, naik sedikit
"""

import sys, json, os, subprocess, re
from datetime import datetime

# Paksa stdout UTF-8 supaya karakter unicode tidak crash di Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

def get_ytdlp_env():
    """Pastikan Node.js ada di PATH saat yt-dlp dijalankan via subprocess."""
    env = os.environ.copy()
    node_candidates = [
        r"C:\Program Files\nodejs",
        r"C:\Program Files (x86)\nodejs",
        os.path.expanduser(r"~\AppData\Roaming\nvm\current"),
        r"C:\tools\nodejs",
    ]
    current_path = env.get("PATH", "")
    for p in node_candidates:
        if os.path.exists(p) and p not in current_path:
            env["PATH"] = p + ";" + current_path
            break
    return env

ENGAGEMENT_WORDS = [
    "luar biasa","rahasia","terbaik","terburuk","cara","kenapa","bagaimana",
    "tips","trik","jangan","harus","wajib","penting","viral","trending",
    "gratis","mudah","cepat","kuat","terungkap","pertama kali","tidak pernah",
    "selalu","fakta","bukti","amazing","incredible","secret","never","always",
    "best","worst","must","important","free","easy","fast","powerful",
    "revealed","finally","proof","tanggung jawab","bisa","lakukan","benar",
    "salah","hidup","mati","sukses","gagal","uang","consider","pertimbangkan",
    "sekarang","ingat","dengarkan","lihat","perhatikan","ketahui","sadar",
]

EMPHASIS_WORDS = [
    "harus","wajib","penting","terbaik","luar biasa","rahasia","viral","fakta",
    "bukti","jangan","bisa","lakukan","tanggung jawab","sukses","gagal",
    "amazing","incredible","secret","never","must","important","powerful",
    "finally","benar","salah","hidup","mati","uang","gratis","cepat","kuat",
    "consider","di-consider","pertimbangkan","sekarang","ingat","dengarkan",
    "tidak","stop","mulai","akhir","awal","nyata","terbukti","pasti","yakin",
    "kickback","gratifikasi","korupsi","suap","bohong","tipu","manipulasi",
]

FONT_SIZE    = 72        # ukuran seragam semua kata
FONT_NAME    = "Impact"  # font bold tebal (tersedia default di Windows)
MARGIN_V     = 390       # jarak dari BAWAH layar (px) — naik dari sebelumnya

PROGRESS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "progress.json")

def write_progress(step, message, percent=0, status="active"):
    """Tulis progress ke file supaya server bisa polling."""
    try:
        import time as _t
        data = {"step": step, "message": message, "percent": percent,
                "status": status, "ts": _t.time()}
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass

def log(msg):
    print(f"[AutoClipper] {msg}", file=sys.stderr)
    # Deteksi step dari isi pesan
    m = msg.lower()
    if "downloading" in m or "download" in m:
        write_progress("download", msg, 10)
    elif "transkripsi" in m or "whisper" in m or "transcrib" in m:
        write_progress("transcribe", msg, 40)
    elif "cutting clip" in m or "subtitle" in m or "hook" in m or "caption" in m:
        # Ekstrak nomor klip kalau ada
        import re as _re
        num = _re.search(r"clip\s*(\d+)", msg, _re.I)
        pct = min(60 + (int(num.group(1)) * 3 if num else 0), 90)
        write_progress("clip", msg, pct)
    elif "selesai" in m:
        write_progress("clip", msg, 92, "done")
    elif "mega" in m or "upload" in m:
        write_progress("mega", msg, 95)
    elif "error" in m or "gagal" in m:
        write_progress("error", msg, 0, "error")

def ts(sec):
    h  = int(sec // 3600)
    m  = int((sec % 3600) // 60)
    s  = int(sec % 60)
    cs = int((sec % 1) * 100)
    return f"{h:01d}:{m:02d}:{s:02d}.{cs:02d}"

def is_emphasis(word):
    w = word.lower().strip(".,!?;:-\"'")
    return any(e in w or w in e for e in EMPHASIS_WORDS) or (word.isupper() and len(word) > 2)

def sanitize_filename(name, max_len=60):
    # Buang karakter unicode bermasalah (termasuk \ufffd replacement char)
    name = name.encode('ascii', errors='replace').decode('ascii')
    name = re.sub(r'[\\/*?:"<>|?]', '', name)
    name = re.sub(r'\s+', '_', name.strip())
    name = re.sub(r'_+', '_', name).strip('_')
    return name[:max_len]

def get_video_title(url):
    log("Mengambil judul video...")
    cmd = ["yt-dlp","--print","title","--no-playlist",
           "--cookies", r"D:\Tools\n8n_scripts\cookies.txt", url]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=get_ytdlp_env())
    if result.returncode == 0 and result.stdout.strip():
        title = result.stdout.strip()
        log(f"Judul: {title}")
        return title
    log("Gagal ambil judul, pakai timestamp")
    return None


HOOK_DURATION = 2.5  # detik hook ditampilkan di awal clip

def extract_hook_text(seg_text, max_words=8):
    """
    Ekstrak teks hook dari transkrip — kalimat paling menarik & singkat.
    Prioritas: pertanyaan > kalimat dengan engagement words > awal segmen.
    """
    import re as _re
    sentences = _re.split(r"(?<=[.!?])\s+", seg_text.strip())
    sentences = [s.strip() for s in sentences if len(s.strip()) > 8]

    # Prioritas 1: Pertanyaan yang cukup pendek
    for s in sentences:
        words = s.split()
        if "?" in s and 3 <= len(words) <= max_words:
            return _clean_hook(s)

    # Prioritas 2: Kalimat dengan banyak engagement words, cukup pendek
    best, best_score = None, 0
    for s in sentences:
        words = s.split()
        if not (3 <= len(words) <= max_words):
            continue
        score = sum(2 for w in ENGAGEMENT_WORDS if w.lower() in s.lower())
        if score > best_score:
            best_score, best = score, s

    if best and best_score >= 2:
        return _clean_hook(best)

    # Prioritas 3: Kalimat pertama yang cukup pendek
    for s in sentences:
        if len(s.split()) <= max_words:
            return _clean_hook(s)

    # Fallback: 6 kata pertama + "..."
    words = seg_text.split()
    return _clean_hook(" ".join(words[:6])) + "..."


def _clean_hook(text):
    """Bersihkan dan format hook text ke UPPERCASE."""
    import re as _re
    text = _re.sub(r" +", " ", text).strip().strip(".,;:")
    return text.upper()

def generate_ass_per_word(word_segments, output_path, video_width=1080, video_height=1920, hook_text=None):
    """
    Generate subtitle ASS:
    - Muncul PER KATA (satu kata per dialogue)
    - Font Impact, ukuran seragam
    - Putih untuk kata biasa, Kuning untuk kata penting
    - Posisi bawah tengah
    """
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: White,{FONT_NAME},{FONT_SIZE},&H00FFFFFF,&H000000FF,&H00000000,&HA0000000,-1,0,0,0,100,100,2,0,1,5,3,2,60,60,{MARGIN_V},1
Style: Yellow,{FONT_NAME},{FONT_SIZE},&H0000BBFF,&H000000FF,&H00000000,&HA0000000,-1,0,0,0,100,100,2,0,1,5,3,2,60,60,{MARGIN_V},1
Style: Hook,{FONT_NAME},92,&H0000CCFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,2,0,1,6,4,5,60,60,960,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []

    # ── Hook overlay di awal clip ──────────────────────────────────────────
    if hook_text:
        fade_ms = 300
        hold_ms = int((HOOK_DURATION - 0.6) * 1000)
        hook_end = ts(HOOK_DURATION)
        # \fad(fade_in_ms, fade_out_ms) \an5 = center screen
        lines.append(
            f"Dialogue: 1,0:00:00.00,{hook_end},Hook,,0,0,0,,"
            f"{{\an5\fad({fade_ms},{fade_ms})}}{hook_text}"
        )

    for i, w in enumerate(word_segments):
        word = w["word"].strip()
        if not word: continue

        start_time = w["start"]
        # Durasi per kata = sampai kata berikutnya mulai, max 1.2 detik
        if i + 1 < len(word_segments):
            end_time = min(w["end"], word_segments[i+1]["start"])
        else:
            end_time = w["end"]

        # Minimal 0.15 detik agar terbaca
        if end_time - start_time < 0.15:
            end_time = start_time + 0.15

        # Style & teks
        style     = "Yellow" if is_emphasis(word) else "White"
        display   = word.upper()  # semua uppercase — sesuai style image 2
        lines.append(f"Dialogue: 0,{ts(start_time)},{ts(end_time)},{style},,0,0,0,,{display}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(lines))

    log(f"Subtitle per kata: {len(lines)} kata")
    return output_path


def get_channel_name(url):
    log("Mengambil nama channel...")
    cmd = ["yt-dlp","--print","channel","--no-playlist",
           "--cookies", r"D:\Tools\n8n_scripts\cookies.txt", url]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=get_ytdlp_env())
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return ""


def download_video(url, output_dir, video_id):
    output_path = os.path.join(output_dir, f"source_{video_id}.mp4")
    log(f"Downloading: {url}")
    cmd = [
        "yt-dlp",
        "-f","bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format","mp4",
        "--no-playlist",
        "--retries","5",
        "--sleep-interval","2",
        "--cookies", r"D:\Tools\n8n_scripts\cookies.txt",
        "-o", output_path, url
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=get_ytdlp_env())
    if result.returncode != 0:
        raise Exception(f"yt-dlp gagal: {result.stderr[:300]}")
    if not os.path.exists(output_path):
        candidates = [f for f in os.listdir(output_dir) if f.startswith(f"source_{video_id}") and f.endswith(".mp4")]
        if candidates: output_path = os.path.join(output_dir, candidates[0])
        else: raise Exception("File video tidak ditemukan setelah download")
    log(f"Download selesai: {output_path}")
    return output_path

def extract_audio(video_path):
    audio_path = os.path.splitext(video_path)[0] + "_audio.wav"
    log("Extracting audio...")
    cmd = ["ffmpeg","-i",video_path,"-vn","-acodec","pcm_s16le",
           "-ar","16000","-ac","1",audio_path,"-y","-loglevel","quiet"]
    if subprocess.run(cmd, capture_output=True).returncode != 0:
        raise Exception("ffmpeg gagal extract audio")
    log("Audio extracted.")
    return audio_path

def transcribe_audio(audio_path):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise Exception("pip install faster-whisper")
    log("Loading Whisper model...")
    model = WhisperModel("small", device="cpu", compute_type="int8")
    log("Transcribing (word timestamps)...")
    segments_gen, _ = model.transcribe(audio_path, beam_size=5, language="id", vad_filter=True, word_timestamps=True)
    segments  = []
    all_words = []
    for seg in segments_gen:
        text = seg.text.strip()
        if not text: continue
        segments.append({"start":round(seg.start,2),"end":round(seg.end,2),"text":text})
        if seg.words:
            for w in seg.words:
                all_words.append({"word":w.word,"start":round(w.start,2),"end":round(w.end,2)})
    log(f"Transkripsi: {len(segments)} segmen | {len(all_words)} kata")
    return segments, all_words

def score_segments(segments, min_dur=10, max_dur=90):
    if not segments: return []
    avg_seg_dur = max(sum(s["end"]-s["start"] for s in segments)/len(segments), 1)
    target_dur  = (min_dur + max_dur) / 2
    window_size = max(2, min(int(target_dur / avg_seg_dur), len(segments)))
    log(f"Durasi target: {min_dur}-{max_dur}s | Window: {window_size} segmen")
    ideal_min = min_dur + (max_dur - min_dur) * 0.25
    ideal_max = min_dur + (max_dur - min_dur) * 0.75
    candidates = []
    for i in range(len(segments) - window_size + 1):
        window   = segments[i: i + window_size]
        start    = window[0]["start"]
        end      = window[-1]["end"]
        duration = end - start
        if duration < min_dur or duration > max_dur: continue
        text    = " ".join(s["text"] for s in window)
        score   = 50
        reasons = []
        if ideal_min <= duration <= ideal_max:
            score += 20; reasons.append(f"durasi ideal ({int(duration)}s)")
        else:
            score += 10
        found = [w for w in ENGAGEMENT_WORDS if w.lower() in text.lower()]
        if found:
            score += min(len(found)*5,15); reasons.append(f"kata kunci: {', '.join(found[:3])}")
        if "?" in text: score += 10; reasons.append("pertanyaan")
        if "!" in text: score += 5
        sentences = [s for s in text.replace("!",".").replace("?",".").split(".") if len(s.strip())>10]
        if 2 <= len(sentences) <= 5: score += 5
        title  = (text[:57]+"...") if len(text)>60 else text
        reason = "Segmen terdeteksi: " + ", ".join(reasons) if reasons else "Konten konsisten"
        candidates.append({"start":start,"end":end,"text":text,"title":title,
                           "score":min(int(score),100),"reason":reason,"duration":duration})
    candidates.sort(key=lambda x: x["score"], reverse=True)
    final = []
    for cand in candidates:
        overlap = any(
            (min(cand["end"],a["end"]) - max(cand["start"],a["start"])) / cand["duration"] > 0.5
            for a in final
        )
        if not overlap: final.append(cand)
    log(f"Scoring selesai: {len(final)} klip unik")
    return final

def cut_clip_with_subtitle(video_path, start, end, output_path, all_words, clips_dir):
    duration   = end - start
    clip_words = [
        {"word":w["word"],"start":round(w["start"]-start,2),"end":round(w["end"]-start,2)}
        for w in all_words
        if w["start"] >= start and w["end"] <= end + 0.5
    ]
    ass_path    = os.path.join(clips_dir, os.path.basename(output_path).replace(".mp4",".ass"))
    # Ekstrak hook dari teks segmen
    seg_text    = " ".join(w["word"] for w in clip_words)
    hook_text   = extract_hook_text(seg_text)
    log(f"Hook: {hook_text}")
    generate_ass_per_word(clip_words, ass_path, hook_text=hook_text)
    # Escape path untuk filter_complex (backslash & colon)
    ass_esc = ass_path.replace("\\", "/").replace(":", "\\:")

    # ── Filter: blur background + video di tengah + subtitle ──────────────
    # [bg]  : video di-scale fill 1080x1920, crop, blur
    # [fg]  : video di-scale fit lebar 1080px, tinggi auto
    # overlay fg di tengah bg, lalu tambah subtitle
    filter_complex = (
        f"[0:v]split=2[bg_in][fg_in];"
        f"[bg_in]scale=1080:1920:force_original_aspect_ratio=increase,"
        f"crop=1080:1920,gblur=sigma=30[bg];"
        f"[fg_in]scale=1080:-2[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2[base];"
        f"[base]ass='{ass_esc}'[out]"
    )

    cmd = [
        "ffmpeg","-ss",str(start),"-i",video_path,"-t",str(duration),
        "-filter_complex", filter_complex,
        "-map","[out]","-map","0:a",
        "-c:v","libx264","-preset","fast","-crf","23",
        "-c:a","aac","-b:a","128k","-movflags","+faststart",
        output_path,"-y","-loglevel","quiet",
    ]
    result = subprocess.run(cmd, capture_output=True)

    if result.returncode != 0:
        log("Warning: subtitle gagal, fallback blur tanpa subtitle.")
        # Fallback: blur background tanpa subtitle
        filter_fb = (
            f"[0:v]split=2[bg_in][fg_in];"
            f"[bg_in]scale=1080:1920:force_original_aspect_ratio=increase,"
            f"crop=1080:1920,gblur=sigma=30[bg];"
            f"[fg_in]scale=1080:-2[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2[out]"
        )
        cmd_fb = [
            "ffmpeg","-ss",str(start),"-i",video_path,"-t",str(duration),
            "-filter_complex", filter_fb,
            "-map","[out]","-map","0:a",
            "-c:v","libx264","-preset","fast","-crf","23",
            "-c:a","aac","-b:a","128k","-movflags","+faststart",
            output_path,"-y","-loglevel","quiet",
        ]
        result_fb = subprocess.run(cmd_fb, capture_output=True)
        if os.path.exists(ass_path): os.remove(ass_path)
        return result_fb.returncode == 0

    if os.path.exists(ass_path): os.remove(ass_path)
    return True


# Filler words bahasa Indonesia yang perlu dibuang
FILLER_WORDS = {
    "ya","yaa","yaaa","loh","lho","tuh","kan","deh","nih","sih","dong",
    "aja","gue","lu","lo","gitu","kayak","banget","emang","terus","eh",
    "hmm","uh","um","hm","nah","oke","ok","yep","yup","wah","woi","lah",
    "cuy","bro","sis","guys","well","like","uhh","ahh","eeh",
}

# Tema dan hashtag-nya
THEME_HASHTAGS = {
    "agama":     ["#islam","#muslim","#dakwah","#religi","#quran","#hijrah"],
    "bisnis":    ["#bisnis","#entrepreneur","#sukses","#investasi","#startup"],
    "motivasi":  ["#motivasi","#inspirasi","#mindset","#growth","#quotes"],
    "uang":      ["#finansial","#investasi","#uang","#cuan","#keuangan"],
    "kesehatan": ["#kesehatan","#health","#wellness","#hidup","#sehat"],
    "teknologi": ["#teknologi","#tech","#digital","#ai","#coding"],
    "politik":   ["#politik","#indonesia","#pemerintah","#berita","#news"],
    "pendidikan":["#pendidikan","#belajar","#edukasi","#ilmu","#kuliah"],
    "podcast":   ["#podcast","#ngobrol","#diskusi","#talkshow"],
    "ekonomi":   ["#ekonomi","#makroekonomi","#finansial","#inflasi"],
    "hiburan":   ["#entertainment","#komedi","#lucu","#seru","#viral"],
    "olahraga":  ["#olahraga","#sport","#fitness","#gym","#sehat"],
    "gaming":    ["#gaming","#gamer","#game","#esport","#gameplay","#streamer","#fyp"],
    "valorant":  ["#valorant","#valo","#valorantindonesia","#valorantclips","#valorantmemes","#fyp"],
    "mobilelegends":["#mobilelegends","#mlbb","#mlbangbang","#mlbb","#mobileledgends","#fyp"],
}

THEME_KEYWORDS = {
    "agama":     ["allah","islam","muslim","quran","sholat","rosul","rasul","nabi",
                  "dakwah","hijrah","iman","doa","sedekah","surga","dosa"],
    "bisnis":    ["bisnis","startup","perusahaan","brand","produk","marketing",
                  "sales","omzet","profit","customer","founder","ceo"],
    "motivasi":  ["sukses","gagal","semangat","mimpi","tujuan","target","impian",
                  "kerja keras","pantang menyerah","percaya diri","mental"],
    "uang":      ["uang","duit","gaji","investasi","saham","kripto","tabungan",
                  "hutang","kaya","miskin","finansial","cuan","rupiah"],
    "kesehatan": ["sehat","sakit","dokter","obat","diet","tidur","stres",
                  "mental health","olahraga","nutrisi","tubuh","jiwa"],
    "teknologi": ["teknologi","ai","robot","coding","aplikasi","software",
                  "internet","digital","komputer","smartphone","data"],
    "politik":   ["pemerintah","presiden","menteri","dpr","kebijakan","hukum",
                  "pemilu","partai","negara","rakyat","demokrasi"],
    "pendidikan":["belajar","sekolah","kuliah","kampus","guru","mahasiswa",
                  "pendidikan","ilmu","pengetahuan","riset","akademik"],
    "podcast":   ["podcast","episode","guest","host","ngobrol","cerita","sharing"],
    "ekonomi":   ["ekonomi","inflasi","gdp","pertumbuhan","resesi","pasar",
                  "ekspor","impor","subsidi","harga","komoditas"],
    "hiburan":   ["lucu","comedy","jokes","film","musik","konser","entertainment"],
    "olahraga":  ["futsal","bola","basket","renang","lari","gym","atlet"],
    "gaming":    ["game","gaming","gamer","streamer","stream","fps","moba","battle","rank",
                  "gameplay","esport","tournament","meta","patch","update","hero","skill"],
    "valorant":  ["valorant","valo","agent","spike","haven","split","ascent","bind","jett",
                  "reyna","sage","phoenix","viper","omen","killjoy","cypher","sova","chamber",
                  "neon","fade","harbor","gekko","iso","clove","radiant","immortal","plat","diamond"],
    "mobilelegends":["mobile legends","mlbb","ml bang bang","moonton","hero","rank","push rank",
                  "hyper carry","marksman","mage","tank","assassin","support","fighter",
                  "roamer","jungler","lord","turtle","savage","maniac","gord","layla","fanny",
                  "chou","lancelot","kagura","vale","gusion","claude","granger","ling","wanwan",
                  "benedetta","julian","fredrinn","joy","arlott","nolan","zhuxin","lukas"],
}


def detect_themes(text):
    """Deteksi tema dari teks, return list tema yang relevan."""
    text_lower = text.lower()
    scores     = {}
    for theme, keywords in THEME_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[theme] = score
    # Ambil top 3 tema
    return sorted(scores, key=scores.get, reverse=True)[:3]


def extract_key_sentences(text, max_sentences=2, max_chars=200):
    """Ekstrak kalimat terbaik dari teks transkripsi."""
    import re

    # Split jadi kalimat
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

    if not sentences:
        return text[:max_chars]

    # Bersihkan filler words dan score tiap kalimat
    def clean_sentence(s):
        words    = s.split()
        cleaned  = [w for w in words if w.lower().strip(".,!?") not in FILLER_WORDS]
        return " ".join(cleaned).strip()

    def score_sentence(s):
        s_lower = s.lower()
        score   = 0
        for w in ENGAGEMENT_WORDS:
            if w in s_lower:
                score += 2
        # Bonus panjang ideal (10-25 kata)
        word_count = len(s.split())
        if 8 <= word_count <= 25:
            score += 3
        # Penalti kalimat terlalu pendek
        if word_count < 5:
            score -= 5
        return score

    # Score dan sort
    scored = [(score_sentence(s), clean_sentence(s), s) for s in sentences]
    scored = [(sc, cl, orig) for sc, cl, orig in scored if len(cl) > 15]
    scored.sort(key=lambda x: x[0], reverse=True)

    # Ambil top sentences, jaga urutan asli
    top_originals = set(orig for _, _, orig in scored[:max_sentences])
    result_sents  = [clean_sentence(s) for s in sentences if s in top_originals]
    result_sents  = [s for s in result_sents if s]

    result = ". ".join(result_sents[:max_sentences])
    if result and not result.endswith("."):
        result += "."

    # Fallback kalau terlalu pendek
    if len(result) < 30:
        result = clean_sentence(sentences[0])

    return result[:max_chars].strip()


def build_hashtags(text, themes):
    """Bangun hashtag berdasarkan tema yang terdeteksi."""
    hashtags = {"#shorts", "#reels", "#fyp", "#orcaclip"}

    for theme in themes[:2]:  # max 2 tema utama
        tags = THEME_HASHTAGS.get(theme, [])
        hashtags.update(tags[:3])

    # Tambah dari engagement words
    text_lower = text.lower()
    for word in ENGAGEMENT_WORDS:
        if word in text_lower and len(word) > 5:
            clean = word.replace(" ", "").replace("-", "")
            hashtags.add(f"#{clean}")

    return " ".join(sorted(hashtags)[:15])


def generate_caption(seg, video_title, video_url, channel_name, idx):
    """Generate caption bersih untuk upload manual Instagram/Facebook."""
    raw_text = seg["text"].strip()

    # Ekstrak inti dari teks
    key_text = extract_key_sentences(raw_text, max_sentences=2, max_chars=250)

    # Deteksi tema dan build hashtag
    themes      = detect_themes(raw_text)
    hashtag_str = build_hashtags(raw_text, themes)

    credit_line = f"📺 {channel_name}" if channel_name else ""
    url_line    = f"🔗 {video_url}"    if video_url    else ""

    parts = [key_text, "", credit_line, url_line, "", hashtag_str]
    caption = "\n".join(p for p in parts if p is not None).strip()

    return caption

def main():
    if len(sys.argv) < 3:
        print(json.dumps({"code":9000,"errMsg":"Penggunaan: python auto_clipper.py <url> <output_dir> [min_dur] [max_dur]"},ensure_ascii=True))
        sys.exit(1)

    video_url  = sys.argv[1]
    output_dir = sys.argv[2]
    min_dur    = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    max_dur    = int(sys.argv[4]) if len(sys.argv) > 4 else 90

    write_progress("start", "Memulai proses...", 2)
    log(f"Durasi klip: {min_dur}-{max_dur} detik")
    os.makedirs(output_dir, exist_ok=True)

    try:
        write_progress("download", "Mengambil info video dari YouTube...", 5)
        raw_title    = get_video_title(video_url)
        write_progress("download", f"Judul: {raw_title or 'tidak ditemukan'}", 8)
        channel_name = get_channel_name(video_url)
        write_progress("download", f"Channel: {channel_name or '-'} — mulai download...", 10)
        timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_name = f"{sanitize_filename(raw_title)}_{timestamp}" if raw_title else timestamp

        log(f"Folder output: {folder_name}")

        video_path          = download_video(video_url, output_dir, timestamp)
        audio_path          = extract_audio(video_path)
        segments, all_words = transcribe_audio(audio_path)

        if not segments: raise Exception("Tidak ada dialog/narasi terdeteksi")

        scored = score_segments(segments, min_dur=min_dur, max_dur=max_dur)
        if not scored:
            raise Exception(f"Tidak ada segmen dengan durasi {min_dur}-{max_dur} detik.")

        clips_dir = os.path.join(output_dir, folder_name)
        os.makedirs(clips_dir, exist_ok=True)
        log(f"Klip disimpan di: {clips_dir}")

        videos = []
        for idx, seg in enumerate(scored[:10]):
            clip_path = os.path.join(clips_dir, f"clip_{idx+1:03d}.mp4")
            log(f"Cutting clip {idx+1}: {seg['start']:.1f}s-{seg['end']:.1f}s | {seg['duration']:.1f}s | score:{seg['score']}")
            success = cut_clip_with_subtitle(video_path, seg["start"], seg["end"], clip_path, all_words, clips_dir)
            if success and os.path.exists(clip_path):
                # Generate dan simpan caption .txt
                caption_text = generate_caption(seg, raw_title or folder_name, video_url, channel_name, idx+1)
                caption_path = os.path.join(clips_dir, f"clip_{idx+1:03d}.txt")
                with open(caption_path, "w", encoding="utf-8") as cf:
                    cf.write(caption_text)
                log(f"Caption saved: clip_{idx+1:03d}.txt")

                videos.append({
                    "videoId":         f"{folder_name}_clip_{idx+1:03d}",
                    "title":           seg["title"],
                    "viralScore":      seg["score"],
                    "viralReason":     seg["reason"],
                    "videoUrl":        clip_path,
                    "captionFile":     caption_path,
                    "clipEditorUrl":   clip_path,
                    "videoMsDuration": int(seg["duration"]*1000),
                    "clipDurationSec": int(seg["duration"]),
                    "videoTitle":      raw_title or folder_name,
                })

        if os.path.exists(audio_path): os.remove(audio_path)
        if not videos: raise Exception("Semua klip gagal dipotong oleh ffmpeg")

        log(f"Selesai! {len(videos)} klip di: {clips_dir}")
        write_progress("done", f"Selesai! {len(videos)} klip siap", 100, "done")
        print(json.dumps({
            "code":       2000,
            "projectId":  folder_name,
            "videoTitle": raw_title or folder_name,
            "videos":     videos,
        }, ensure_ascii=True))

    except Exception as e:
        log(f"ERROR: {e}")
        safe_msg = str(e).encode("ascii", errors="replace").decode("ascii")
        write_progress("error", safe_msg, 0, "error")
        print(json.dumps({"code":9000,"errMsg":safe_msg}, ensure_ascii=True))
        sys.exit(1)

if __name__ == "__main__":
    main()