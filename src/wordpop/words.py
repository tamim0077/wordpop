"""Read word timings from whatever your transcriber gives you.

Everything is normalised to a list of {"w": text, "s": start_sec, "e": end_sec}.

Understood inputs:
  - a list of dicts with word/text + start/end keys
    (OpenAI Whisper verbose_json, faster-whisper, WhisperX, Deepgram, AssemblyAI*)
  - a list of objects with .word/.start/.end attributes (faster-whisper `Word`)
  - a full response dict: {"words": [...]}, {"segments": [{"words": [...]}]},
    or Deepgram's {"results": {"channels": [{"alternatives": [{"words": [...]}]}]}}

* Full AssemblyAI responses with audio_url, status and words are detected
  automatically. For bare word lists in milliseconds, pass `ms=True`.

whisper.cpp full JSON (-ojf) is also supported. Token offsets are converted
from milliseconds to seconds, special tokens are skipped, and word pieces
are joined using leading whitespace as word boundaries.
"""
from __future__ import annotations

from typing import Any, Iterable

Word = dict  # {"w": str, "s": float, "e": float}

_TEXT_KEYS = ("w", "punctuated_word", "word", "text")
_START_KEYS = ("s", "start")
_END_KEYS = ("e", "end")


def _get(item: Any, keys: tuple[str, ...]):
    for k in keys:
        if isinstance(item, dict):
            if item.get(k) is not None:
                return item[k]
        elif getattr(item, k, None) is not None:
            return getattr(item, k)
    return None


def _unwrap(data: Any) -> Iterable[Any]:
    if isinstance(data, dict):
        if "results" in data:  # Deepgram
            try:
                return data["results"]["channels"][0]["alternatives"][0]["words"]
            except (KeyError, IndexError, TypeError):
                raise ValueError("Deepgram response has no words") from None
        if isinstance(data.get("transcription"), list):
            tokens = []
            for segment in data["transcription"]:
                if not isinstance(segment.get("tokens"), list):
                    raise ValueError("whisper.cpp response needs full JSON tokens")

                segment_words = []
                for token in segment["tokens"]:
                    text = token.get("text", "")
                    if text.startswith("[_") and text.endswith("_]"):
                        continue
                    if not text.strip():
                        continue

                    offsets = token.get("offsets") or {}
                    start = offsets.get("from")
                    end = offsets.get("to")
                    if start is None or end is None:
                        raise ValueError(f"token needs start and end offsets: {token!r}")

                    if segment_words and not text[0].isspace():
                        segment_words[-1]["text"] += text
                        segment_words[-1]["end"] = max(
                            float(segment_words[-1]["end"]), float(end)
                        )
                    else:
                        segment_words.append({
                            "text": text,
                            "start": start,
                            "end": end,
                        })

                tokens.extend(segment_words)
            return tokens
        if isinstance(data.get("words"), list):
            return data["words"]
        if isinstance(data.get("segments"), list):
            out: list = []
            for seg in data["segments"]:
                ws = _get(seg, ("words",))
                if ws:
                    out.extend(ws)
            return out
        raise ValueError("no 'words' or 'segments' in this transcript")
    return data


def normalize_words(data: Any, ms: bool = False) -> list[Word]:
    """Return [{"w", "s", "e"}] sorted by start time. Empty words are dropped."""
    is_assemblyai = (
        isinstance(data, dict)
        and isinstance(data.get("words"), list)
        and "audio_url" in data
        and "status" in data
    )
    is_whisper_cpp = (
        isinstance(data, dict)
        and isinstance(data.get("transcription"), list)
    )
    scale = 0.001 if ms or is_assemblyai or is_whisper_cpp else 1.0
    words: list[Word] = []
    for item in _unwrap(data):
        text, start, end = _get(item, _TEXT_KEYS), _get(item, _START_KEYS), _get(item, _END_KEYS)
        if text is None or start is None or end is None:
            raise ValueError(f"word needs text, start and end: {item!r}")
        text = str(text).strip()
        if not text:
            continue
        s, e = float(start) * scale, float(end) * scale
        words.append({"w": text, "s": s, "e": max(e, s)})
    words.sort(key=lambda w: w["s"])
    return words


def clip_words(words: list[Word], start: float, end: float) -> list[Word]:
    """Words between `start` and `end`, with times moved so `start` is 0.

    Use this when you cut a clip out of a long video and need its captions.
    """
    out = []
    for w in words:
        if w["e"] > start and w["s"] < end:
            out.append({"w": w["w"], "s": max(0.0, w["s"] - start), "e": min(end, w["e"]) - start})
    return out
