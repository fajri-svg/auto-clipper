#!/usr/bin/env python3
"""
Auto Clipper v7
- Subtitle muncul PER KATA
- Ukuran font seragam (tidak ada yang lebih besar)
- Kata biasa : PUTIH
- Kata penting: KUNING
- Font Impact (bold, tebal, all caps style)
- Posisi: bawah tengah, naik sedikit
"""

import sys, json, os, subprocess, re
from datetime import datetime

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
MARGIN_V     = 220       # jarak dari BAWAH layar (px) — naik dari sebelumnya

def log(msg): print(f"[AutoClipper] {msg}", file=sys.stderr)

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
    name = re.sub(r'[\\/*?:"<>|]', '', name)
    name = re.sub(r'\s+', '_', name.strip())
    name = re.sub(r'_+', '_', name).strip('_')
    return name[:max_len]

def get_video_title(url):
    log("Mengambil judul video...")
    cmd = ["yt-dlp","--print","title","--no-playlist",url]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode == 0 and result.stdout.strip():
        title = result.stdout.strip()
        log(f"Judul: {title}")
        return title
    log("Gagal ambil judul, pakai timestamp")
    return None

def generate_ass_per_word(word_segments, output_path, video_width=1080, video_height=1920):
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

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []

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

def download_video(url, output_dir, video_id):
    output_path = os.path.join(output_dir, f"source_{video_id}.mp4")
    log(f"Downloading: {url}")
    cmd = ["yt-dlp","-f","bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
           "--merge-output-format","mp4","--no-playlist","-o",output_path,url]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
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
    segments_gen, _ = model.transcribe(audio_path, beam_size=5, vad_filter=True, word_timestamps=True)
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
    generate_ass_per_word(clip_words, ass_path)
    ass_escaped = ass_path.replace("\\","\\\\").replace(":","\\:")

    cmd = [
        "ffmpeg","-ss",str(start),"-i",video_path,"-t",str(duration),
        "-vf",(
            f"scale=1080:1920:force_original_aspect_ratio=decrease,"
            f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,"
            f"ass='{ass_escaped}'"
        ),
        "-c:v","libx264","-preset","fast","-crf","23",
        "-c:a","aac","-b:a","128k","-movflags","+faststart",
        output_path,"-y","-loglevel","quiet",
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        log("Warning: subtitle gagal, fallback tanpa subtitle.")
        cmd_fb = [
            "ffmpeg","-ss",str(start),"-i",video_path,"-t",str(duration),
            "-vf","scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black",
            "-c:v","libx264","-preset","fast","-crf","23",
            "-c:a","aac","-b:a","128k","-movflags","+faststart",
            output_path,"-y","-loglevel","quiet",
        ]
        return subprocess.run(cmd_fb, capture_output=True).returncode == 0

    if os.path.exists(ass_path): os.remove(ass_path)
    return True

def main():
    if len(sys.argv) < 3:
        print(json.dumps({"code":9000,"errMsg":"Penggunaan: python auto_clipper.py <url> <output_dir> [min_dur] [max_dur]"},ensure_ascii=False))
        sys.exit(1)

    video_url  = sys.argv[1]
    output_dir = sys.argv[2]
    min_dur    = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    max_dur    = int(sys.argv[4]) if len(sys.argv) > 4 else 90

    log(f"Durasi klip: {min_dur}-{max_dur} detik")
    os.makedirs(output_dir, exist_ok=True)

    try:
        raw_title   = get_video_title(video_url)
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
                videos.append({
                    "videoId":         f"{folder_name}_clip_{idx+1:03d}",
                    "title":           seg["title"],
                    "viralScore":      seg["score"],
                    "viralReason":     seg["reason"],
                    "videoUrl":        clip_path,
                    "clipEditorUrl":   clip_path,
                    "videoMsDuration": int(seg["duration"]*1000),
                    "clipDurationSec": int(seg["duration"]),
                    "videoTitle":      raw_title or folder_name,
                })

        if os.path.exists(audio_path): os.remove(audio_path)
        if not videos: raise Exception("Semua klip gagal dipotong oleh ffmpeg")

        log(f"Selesai! {len(videos)} klip di: {clips_dir}")
        print(json.dumps({
            "code":       2000,
            "projectId":  folder_name,
            "videoTitle": raw_title or folder_name,
            "videos":     videos,
        }, ensure_ascii=False))

    except Exception as e:
        log(f"ERROR: {e}")
        print(json.dumps({"code":9000,"errMsg":str(e)}, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    main()