"""wordpop command line.

  wordpop transcript.json -o captions.ass --style beast --title "wait for it"
  wordpop transcript.json --video in.mp4 --out out.mp4 --start 44.7 --end 75.2
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .burn import burn
from .core import LAYOUTS, build_ass, build_srt, build_vtt
from .styles import STYLES
from .words import clip_words, normalize_words


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="wordpop", description="Word-by-word short-form captions as ASS, SRT or WebVTT subtitles.")
    p.add_argument("transcript", help="JSON with word timings (Whisper, faster-whisper, WhisperX, Deepgram...)")
    p.add_argument("--format", choices=("ass", "srt", "vtt"), default="ass")
    p.add_argument("-o", "--output", help="write the subtitle file here (default: stdout, unless --video)")
    p.add_argument("--style", default="pop", choices=list(STYLES))
    p.add_argument("--layout", default="blur", choices=list(LAYOUTS))
    p.add_argument("--title", help="hook text shown at the top")
    p.add_argument("--font", default="Anton", help="font for styles that don't set one (default: Anton)")
    p.add_argument("--watermark", help="small text in the corner")
    p.add_argument("--start", type=float, help="only caption from here (seconds); times shift so this is 0")
    p.add_argument("--end", type=float, help="only caption up to here (seconds)")
    p.add_argument("--duration", type=float, help="video length in seconds")
    p.add_argument("--ms", action="store_true", help="transcript times are in milliseconds (AssemblyAI)")
    p.add_argument("--video", help="burn the captions into this video (needs ffmpeg)")
    p.add_argument("--out", help="output video path for --video")
    p.add_argument("--fonts-dir", help="folder with caption .ttf files for ffmpeg/libass")
    p.add_argument("--version", action="version", version=f"wordpop {__version__}")
    a = p.parse_args(argv)

    data = json.loads(Path(a.transcript).read_text(encoding="utf-8"))
    words = normalize_words(data, ms=a.ms)
    duration = a.duration
    if a.start is not None or a.end is not None:
        start = a.start or 0.0
        end = a.end if a.end is not None else max((w["e"] for w in words), default=start)
        words = clip_words(words, start, end)
        duration = duration or end - start

    if a.video or a.format == "ass":
        ass = build_ass(words, duration, style=a.style, title=a.title, layout=a.layout,
                        font=a.font, watermark=a.watermark)
    if a.video and a.format != "ass" and not a.output:
        p.error("--format srt/vtt with --video needs -o for the subtitle file")

    if a.video:
        if not a.out:
            p.error("--video needs --out")
        burn(a.video, ass, a.out, fonts_dir=a.fonts_dir)
        print(f"wrote {a.out}", file=sys.stderr)
    if a.output or not a.video:
        if a.format == "ass":
            subtitles = ass
        else:
            builder = build_srt if a.format == "srt" else build_vtt
            subtitles = builder(words, duration, style=a.style)
        if a.output:
            Path(a.output).write_text(subtitles, encoding="utf-8")
        else:
            sys.stdout.write(subtitles)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
