#!/usr/bin/env bash
# Converts audio (MP3, M4A, MP4, AAC, AIFF, WAV, ...) into a WAV that Lindefense can play (pygame / SDL WAV).
#
# usage: scripts/convert-music.sh <input> [output.wav] [--pcm]
#   default output : assets/music/<input name>.wav   (name it menu / battle / battle_late / battle_onn / boss /
#                    palantir / victory / defeat so the game finds it)
#   default format : WAV, G.711 mu-law, 22.05 kHz, stereo   (~2.6 MB per minute)
#   --pcm          : 16-bit PCM, 22.05 kHz, mono            (~2.6 MB per minute, cleaner but mono)
#
# Accepts MP3, WAV, AIFF, AAC, M4A (including Opus-in-M4A) and MP4 (with or without video).
# macOS only (uses afconvert / avconvert). For Windows and Linux use the ffmpeg commands in README.md (Audio).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

PCM=0
ARGS=()
for a in "$@"; do
  if [ "$a" = "--pcm" ]; then PCM=1; else ARGS+=("$a"); fi
done
if [ "${#ARGS[@]}" -lt 1 ]; then
  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
  exit 1
fi
IN="${ARGS[0]}"
BASE="$(basename "${IN%.*}")"
OUT="${ARGS[1]:-$ROOT/assets/music/$BASE.wav}"
[ -f "$IN" ] || { echo "No such file: $IN" >&2; exit 1; }
command -v afconvert >/dev/null || { echo "afconvert not found (macOS only). See README.md (Audio) for the ffmpeg equivalent." >&2; exit 1; }
mkdir -p "$(dirname "$OUT")"

SRC="$IN"
TMP=""
case "$(echo "${IN##*.}" | tr '[:upper:]' '[:lower:]')" in
  mp4|mov|m4v|m4a)
    # Always re-mux M4A / MP4 through avconvert first: it extracts the audio of an MP4 with video and transcodes
    # Opus-in-M4A to AAC, which afconvert cannot decode directly ('pck?' error).
    if command -v avconvert >/dev/null; then
      TMP="$(mktemp -d)"
      if avconvert --source "$IN" --preset PresetAppleM4A --output "$TMP/audio.m4a" --replace >/dev/null 2>&1; then
        SRC="$TMP/audio.m4a"
      else
        echo "avconvert could not process the file; trying afconvert directly" >&2
      fi
    fi
    ;;
esac

if [ "$PCM" = 1 ]; then
  afconvert -f WAVE -d LEI16@22050 -c 1 "$SRC" "$OUT"
else
  afconvert -f WAVE -d ulaw@22050 -c 2 "$SRC" "$OUT"
fi
[ -n "$TMP" ] && rm -rf "$TMP"
echo "Wrote $OUT ($(du -h "$OUT" | cut -f1))"
