"""wordpop: word-by-word short-form captions (TikTok / Reels / Shorts style) as ASS subtitles."""
from .burn import burn
from .core import DEFAULT_FONT, LAYOUTS, PLACEMENT, build_ass, build_srt, build_vtt, group_words
from .styles import STYLES, Style, colour, get_style
from .words import clip_words, normalize_words

__version__ = "0.1.0"

__all__ = [
    "build_ass", "build_srt", "build_vtt", "burn", "clip_words", "colour", "get_style", "group_words", "normalize_words",
    "DEFAULT_FONT", "LAYOUTS", "PLACEMENT", "STYLES", "Style", "__version__",
]
