#!/usr/bin/env bash
# Chinese subtitle pipeline for YouTube video 3juJzFbGpMk
# Usage: bash run_pipeline.sh [video_url]
set -euo pipefail

VIDEO_URL="${1:-https://www.youtube.com/watch?v=3juJzFbGpMk}"
VIDEO_FILE="video.mp4"
EN_SRT="video.en.srt"
ZH_SRT="video.zh.srt"
OUTPUT_FILE="output_final.mp4"
WHISPER_MODEL="${WHISPER_MODEL:-medium}"

# Find the right Python — prefers Anaconda if present
if [ -f "$HOME/anaconda3/bin/python" ]; then
  PYTHON="$HOME/anaconda3/bin/python"
elif [ -f "$HOME/miniconda3/bin/python" ]; then
  PYTHON="$HOME/miniconda3/bin/python"
elif command -v python3 &>/dev/null; then
  PYTHON="python3"
elif command -v python &>/dev/null; then
  PYTHON="python"
else
  echo "ERROR: No Python found. Install Python or Anaconda first."
  exit 1
fi
echo "  Using Python: $PYTHON"

# Auto-detect a CJK font that exists on this machine
if [ -f "/System/Library/Fonts/PingFang.ttc" ]; then
  CJK_FONT_PATH="/System/Library/Fonts/PingFang.ttc"
  FONT_NAME="PingFang SC"
elif [ -f "/Library/Fonts/Arial Unicode MS.ttf" ]; then
  CJK_FONT_PATH="/Library/Fonts/Arial Unicode MS.ttf"
  FONT_NAME="Arial Unicode MS"
elif [ -f "C:/Windows/Fonts/msyh.ttc" ]; then
  CJK_FONT_PATH="C:/Windows/Fonts/msyh.ttc"
  FONT_NAME="Microsoft YaHei"
elif [ -f "C:/Windows/Fonts/simhei.ttf" ]; then
  CJK_FONT_PATH="C:/Windows/Fonts/simhei.ttf"
  FONT_NAME="SimHei"
elif [ -f "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc" ]; then
  CJK_FONT_PATH="/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
  FONT_NAME="WenQuanYi Zen Hei"
else
  echo "  ERROR: No CJK font found. Install one:"
  echo "    Mac:     already included (PingFang)"
  echo "    Windows: already included (Microsoft YaHei)"
  echo "    Linux:   sudo apt install fonts-wqy-zenhei"
  exit 1
fi

echo "======================================================"
echo " Chinese Subtitle Pipeline"
echo "======================================================"

# ── Step 1: Verify dependencies ──────────────────────────
echo ""
echo "[Step 1] Checking dependencies..."
for cmd in yt-dlp ffmpeg; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "  ERROR: '$cmd' not found. Install it first."
    exit 1
  fi
done
"$PYTHON" -c "import whisper" 2>/dev/null || { echo "  ERROR: openai-whisper not installed. Run: pip install openai-whisper"; exit 1; }
# Only require the Anthropic key if actually using Claude as the translator
if [ "${TRANSLATOR:-google}" = "claude" ]; then
  "$PYTHON" -c "import anthropic" 2>/dev/null || { echo "  ERROR: anthropic not installed. Run: pip install anthropic"; exit 1; }
  [ -z "${ANTHROPIC_API_KEY:-}" ] && { echo "  ERROR: ANTHROPIC_API_KEY not set. Export it before running."; exit 1; }
fi
echo "  All dependencies OK."

# ── Step 2: Download video ────────────────────────────────
echo ""
echo "[Step 2] Downloading video..."
if [ -f "$VIDEO_FILE" ]; then
  echo "  $VIDEO_FILE already exists, skipping download."
else
  yt-dlp --no-check-certificate \
    -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best" \
    --merge-output-format mp4 \
    -o "$VIDEO_FILE" \
    "$VIDEO_URL"
  echo "  Download complete: $VIDEO_FILE"
fi

# ── Step 3: Transcribe with Whisper ──────────────────────
echo ""
echo "[Step 3] Transcribing with Whisper (model: $WHISPER_MODEL)..."
if [ -f "$EN_SRT" ]; then
  echo "  $EN_SRT already exists, skipping transcription."
else
  "$PYTHON" - <<'PYEOF'
import sys, whisper, os

model_name = os.environ.get("WHISPER_MODEL", "medium")
print(f"  Loading whisper model '{model_name}'...")
model = whisper.load_model(model_name)

print("  Transcribing audio (this may take a few minutes)...")
result = model.transcribe(
    "video.mp4",
    language="en",
    task="transcribe",
    verbose=False,
    condition_on_previous_text=True,
    word_timestamps=False,
)

def format_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

segments = result["segments"]
with open("video.en.srt", "w", encoding="utf-8") as f:
    for i, seg in enumerate(segments, 1):
        start = format_timestamp(seg["start"])
        end = format_timestamp(seg["end"])
        text = seg["text"].strip()
        f.write(f"{i}\n{start} --> {end}\n{text}\n\n")

print(f"  Transcription complete: video.en.srt ({len(segments)} segments)")
PYEOF
fi

# ── Step 4: Translate to Simplified Chinese ──────────────
echo ""
echo "[Step 4] Translating to Simplified Chinese..."
if [ -f "$ZH_SRT" ]; then
  echo "  $ZH_SRT already exists, skipping translation."
else
  "$PYTHON" translate_srt.py "$EN_SRT" "$ZH_SRT"
fi

# ── Step 5: Burn subtitles into video ────────────────────
echo ""
echo "[Step 5] Burning Chinese subtitles into video..."

"$PYTHON" - <<PYEOF
import subprocess, os, sys

zh_srt = "$ZH_SRT"
video_in = "$VIDEO_FILE"
video_out = "$OUTPUT_FILE"
font_path = "$CJK_FONT_PATH"
font_name = "$FONT_NAME"

tmp_ass = "video.zh.ass"
subprocess.run(
    ["ffmpeg", "-y", "-i", zh_srt, tmp_ass],
    check=True, capture_output=True
)

with open(tmp_ass, "r", encoding="utf-8") as fh:
    ass_content = fh.read()
ass_content = ass_content.replace("Arial", font_name).replace("Fontname: Arial", f"Fontname: {font_name}")
with open(tmp_ass, "w", encoding="utf-8") as fh:
    fh.write(ass_content)

fontsdir = os.path.dirname(font_path)
cmd = [
    "ffmpeg", "-y",
    "-i", video_in,
    "-vf", f"ass={tmp_ass}:fontsdir={fontsdir}",
    "-c:a", "copy",
    video_out
]
print(f"  Running: {' '.join(cmd)}")
result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    print("STDERR:", result.stderr[-2000:])
    sys.exit(1)
print(f"  Done: {video_out}")
PYEOF

# ── Step 6: Confirmation ──────────────────────────────────
echo ""
echo "[Step 6] Summary"
echo "-----------------------------------"

DURATION=$(ffprobe -v quiet -show_entries format=duration -of csv="p=0" "$OUTPUT_FILE" 2>/dev/null || echo "unknown")
if [ "$DURATION" != "unknown" ]; then
  DURATION_FMT=$("$PYTHON" -c "d=float('$DURATION'); print(f'{int(d//3600):02d}:{int((d%3600)//60):02d}:{int(d%60):02d}')")
  echo "  Output duration : $DURATION_FMT"
fi

LINE_COUNT=$(wc -l < "$ZH_SRT")
echo "  Chinese SRT lines: $LINE_COUNT"

echo ""
echo "  First 5 Chinese subtitle entries:"
"$PYTHON" - <<'PYEOF'
entries = []
with open("video.zh.srt", encoding="utf-8") as f:
    block = []
    for line in f:
        line = line.rstrip("\n")
        if line.strip() == "" and block:
            entries.append(block)
            block = []
            if len(entries) == 5:
                break
        else:
            block.append(line)

for e in entries:
    for l in e:
        print("    " + l)
    print()
PYEOF

echo "======================================================"
echo " Pipeline complete! Output: $OUTPUT_FILE"
echo "======================================================"
