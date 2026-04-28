#!/usr/bin/env bash
# Burns video.zh.srt subtitles into video.mp4 → output_final.mp4
set -euo pipefail

VIDEO_IN="video.mp4"
ZH_SRT="video.zh.srt"
OUTPUT="output_final.mp4"

echo "======================================================"
echo " Burning Chinese Subtitles"
echo "======================================================"

# Check files exist
[ ! -f "$VIDEO_IN" ] && { echo "ERROR: video.mp4 not found in this folder."; exit 1; }
[ ! -f "$ZH_SRT"  ] && { echo "ERROR: video.zh.srt not found in this folder."; exit 1; }

# Find CJK font path
if [ -f "$HOME/Library/Fonts/NotoSansCJK.ttc" ]; then
  FONT_PATH="$HOME/Library/Fonts/NotoSansCJK.ttc"
elif [ -f "/Library/Fonts/NotoSansCJK.ttc" ]; then
  FONT_PATH="/Library/Fonts/NotoSansCJK.ttc"
elif [ -f "/System/Library/Fonts/PingFang.ttc" ]; then
  FONT_PATH="/System/Library/Fonts/PingFang.ttc"
elif [ -f "C:/Windows/Fonts/msyh.ttc" ]; then
  FONT_PATH="C:/Windows/Fonts/msyh.ttc"
elif [ -f "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc" ]; then
  FONT_PATH="/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
else
  echo "ERROR: No CJK font found. Run: brew install font-noto-sans-cjk"
  exit 1
fi
echo "  Font file: $FONT_PATH"

# Burn subtitles directly from SRT using the font file path
echo "  Burning into video (this takes a few minutes)..."
ffmpeg -y \
  -i "$VIDEO_IN" \
  -vf "subtitles=${ZH_SRT}" \
  -c:a copy \
  "$OUTPUT"

echo ""
echo "======================================================"
echo " Done! Output saved as: output_final.mp4"
echo "======================================================"

DURATION=$(ffprobe -v quiet -show_entries format=duration -of csv="p=0" "$OUTPUT" 2>/dev/null || echo "")
if [ -n "$DURATION" ]; then
  python3 -c "d=float('$DURATION'); print(f'  Duration: {int(d//3600):02d}:{int((d%3600)//60):02d}:{int(d%60):02d}')" 2>/dev/null || true
fi
echo "  Lines in subtitle file: $(wc -l < "$ZH_SRT")"
