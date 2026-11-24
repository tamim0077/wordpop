"""Build an ASS subtitle file with word-by-word highlighted captions."""
from __future__ import annotations

from html import escape
from typing import Optional, Union

from .styles import BLACK, WHITE, Style, colour, get_style
from .words import Word

LAYOUTS = ("fill", "blur", "split")

# (alignment, marginV) for the caption line, per layout, on a 1080x1920 canvas
PLACEMENT = {
    "fill": (2, 560),    # video fills the frame: captions in the lower third
    "blur": (2, 470),    # video in the middle on a blurred background
    "split": (8, 880),   # face cam on top, gameplay below: just under the middle line
}

DEFAULT_FONT = "Anton"


def _ts(t: float) -> str:
    cs = int(round(max(0.0, t) * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _clean(text: str) -> str:
    # Caption fonts have no emoji glyphs (they'd burn in as boxes): drop emoji and
    # pictographic symbols, keep letters, accents, punctuation and currency.
    text = "".join(ch for ch in text if ord(ch) < 0x2300 or 0x3000 <= ord(ch) < 0x1F000)
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ").strip()


def group_words(words: list[Word], max_words: int, max_span: float, max_gap: float = 0.6):
    """Split words into caption lines: by count, by length in time, at pauses and at sentence ends."""
    group: list[Word] = []
    for w in words:
        if group and (len(group) >= max_words or w["s"] - group[-1]["e"] > max_gap
                      or w["e"] - group[0]["s"] > max_span
                      or group[-1]["w"].endswith((".", "?", "!"))):
            yield group
            group = []
        group.append(w)
    if group:
        yield group


def _timed_groups(words, duration, st):
    words = [w for w in words if w["e"] > 0 and w["s"] < duration]
    groups = list(group_words(words, max_words=st.max_words, max_span=st.max_span))

    for gi, group in enumerate(groups):
        nxt = groups[gi + 1][0]["s"] if gi + 1 < len(groups) else duration
        group_end = min(nxt, group[-1]["e"] + 0.35, duration)
        yield group, group_end


def _subtitle_stamp(ms, separator):
    hours, ms = divmod(ms, 3_600_000)
    minutes, ms = divmod(ms, 60_000)
    seconds, ms = divmod(ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{ms:03d}"


def _plain_captions(words, duration, style, vtt):
    if duration is None:
        duration = max((w["e"] for w in words), default=0) + 0.35
    blocks = []
    separator = "." if vtt else ","
    for group, end in _timed_groups(words, duration, get_style(style)):
        start_ms = round(max(0, group[0]["s"]) * 1000)
        end_ms = round(end * 1000)
        if end_ms <= start_ms:
            continue
        timing = f"{_subtitle_stamp(start_ms, separator)} --> {_subtitle_stamp(end_ms, separator)}"
        text = " ".join(" ".join(w["w"].split()) for w in group)
        cue = [timing, escape(text, quote=False)]
        if not vtt:
            cue.insert(0, str(len(blocks) + 1))
        blocks.append("\n".join(cue))
    return ("WEBVTT\n\n" if vtt else "") + "\n\n".join(blocks) + ("\n" if blocks else "")


def build_srt(words: list[Word], duration=None, *, style="pop") -> str:
    """Return one numbered SRT cue per caption group."""
    return _plain_captions(words, duration, style, vtt=False)


def build_vtt(words: list[Word], duration=None, *, style="pop") -> str:
    """Return one WebVTT cue per caption group."""
    return _plain_captions(words, duration, style, vtt=True)


def _header(st: Style, font: str, hook_font: str, align: int, margin_v: int) -> str:
    face = st.font or font
    bold = -1 if st.bold else 0
    if st.plate:
        cap = (f"Style: Cap,{face},{st.size},{WHITE},{WHITE},&H70000000,&H70000000,{bold},0,0,0,"
               f"100,100,0,0,3,16,0,{align},90,90,{margin_v},1")
    else:
        cap = (f"Style: Cap,{face},{st.size},{WHITE},{WHITE},{BLACK},&H90000000,{bold},0,0,0,"
               f"100,100,0,0,1,{st.outline},{st.shadow},{align},70,70,{margin_v},1")
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{cap}
Style: Hook,{hook_font},78,{WHITE},{WHITE},&H00000000,&H00000000,-1,0,0,0,100,100,0,0,3,22,0,8,80,80,200,1
Style: MarkFull,Arial,34,&H50FFFFFF,&H50FFFFFF,&H90000000,&H00000000,-1,0,0,0,100,100,1,0,1,2,0,2,40,40,80,1
Style: MarkSmall,Arial,24,&H70FFFFFF,&H70FFFFFF,&H90000000,&H00000000,-1,0,0,0,100,100,1,0,1,1,0,3,36,36,36,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _live(text: str, st: Style) -> str:
    """Override tags for the word being spoken right now."""
    hi = colour(st.highlight)
    if st.box:
        return f"{{\\c{hi}&\\3c{colour(st.box_colour)}&\\bord16\\shad0}}{text}{{\\r}}"
    tags = f"\\c{hi}&"
    if st.glow:
        tags += f"\\3c{hi}&\\blur4"
    if st.pop_scale != 100:  # quick pop: start a bit bigger, settle halfway back
        s = st.pop_scale
        half = 100 + (s - 100) // 2
        tags += f"\\fscx{s}\\fscy{s}\\t(0,90,\\fscx{half}\\fscy{half})"
    return f"{{{tags}}}{text}{{\\r}}"


def build_ass(
    words: list[Word],
    duration: Optional[float] = None,
    *,
    style: Union[str, Style] = "pop",
    title: Optional[str] = None,
    layout: str = "blur",
    font: str = DEFAULT_FONT,
    hook_font: Optional[str] = None,
    watermark: Optional[str] = None,
    watermark_size: str = "small",
    margin_v: Optional[int] = None,
) -> str:
    """Return the text of an .ass subtitle file.

    words:      [{"w", "s", "e"}] relative to the start of the video
                (see `normalize_words` / `clip_words`).
    duration:   video length in seconds; default = last word end + 0.35 s.
    style:      preset name (see STYLES) or a Style.
    title:      optional hook text shown at the top for the whole video.
    layout:     "fill", "blur" or "split" - where the captions sit (see PLACEMENT).
    font:       font for styles that don't name one, e.g. "pop" and "box".
    hook_font:  font for the title (default: `font`).
    watermark:  optional text in the corner ("small") or bottom centre ("full").
    margin_v:   override the vertical margin of the caption line.

    The canvas is 1080x1920 (9:16). libass scales it to the real video size.
    """
    st = get_style(style)
    if layout not in PLACEMENT:
        raise ValueError(f"unknown layout {layout!r}; pick one of {', '.join(LAYOUTS)}")
    if watermark_size not in ("small", "full"):
        raise ValueError("watermark_size must be 'small' or 'full'")
    if duration is None:
        duration = (max(w["e"] for w in words) + 0.35) if words else 0.0

    align, mv = PLACEMENT[layout]
    if margin_v is not None:
        mv = margin_v
    lines: list[str] = []
    for group, group_end in _timed_groups(words, duration, st):
        if st.plate:
            text = " ".join(_clean(w["w"]) for w in group)
            lines.append(f"Dialogue: 0,{_ts(group[0]['s'])},{_ts(group_end)},Cap,,0,0,0,,{text}")
            continue
        texts = [_clean(w["w"]).upper() if st.uppercase else _clean(w["w"]) for w in group]
        for i, w in enumerate(group):
            end = group[i + 1]["s"] if i + 1 < len(group) else group_end
            if end <= w["s"]:
                continue
            parts = []
            for j, t in enumerate(texts):
                if j == i:
                    parts.append(_live(t, st))
                elif st.dim_upcoming and j > i:
                    parts.append(f"{{\\alpha&H99&}}{t}{{\\r}}")  # not said yet: dimmed
                else:
                    parts.append(t)
            lines.append(f"Dialogue: 0,{_ts(w['s'])},{_ts(end)},Cap,,0,0,0,,{' '.join(parts)}")

    if title:
        # The hook stays up the whole video (people join mid-loop). In split it
        # sits on the line between the cam and the gameplay, off the face.
        pos = "\\an5\\pos(540,768)" if layout == "split" else ""
        lines.append(f"Dialogue: 1,{_ts(0)},{_ts(duration)},Hook,,0,0,0,,"
                     f"{{{pos}\\fad(150,0)}}{_clean(title).upper()}")
    if watermark:
        mark = "MarkFull" if watermark_size == "full" else "MarkSmall"
        lines.append(f"Dialogue: 2,{_ts(0)},{_ts(duration)},{mark},,0,0,0,,{_clean(watermark)}")

    return _header(st, font, hook_font or font, align, mv) + "\n".join(lines) + "\n"
