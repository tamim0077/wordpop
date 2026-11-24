import json
from types import SimpleNamespace

import pytest

from wordpop import STYLES, Style, build_ass, build_srt, build_vtt, clip_words, colour, normalize_words
from wordpop.cli import main

WORDS = [
    {"w": "no", "s": 0.5, "e": 0.8},
    {"w": "way", "s": 0.9, "e": 1.2},
    {"w": "he", "s": 1.3, "e": 1.6},
    {"w": "did", "s": 1.7, "e": 2.0},
    {"w": "that.", "s": 2.1, "e": 2.4},
    {"w": "chat", "s": 3.5, "e": 3.8},
]


def dialogues(ass, style="Cap"):
    return [l for l in ass.splitlines() if l.startswith("Dialogue:") and f",{style}," in l]


# --- words ---------------------------------------------------------------

def test_normalize_openai_segments():
    data = {"segments": [{"words": [{"word": " Hi", "start": 0.0, "end": 0.4}]},
                         {"words": [{"word": " there", "start": 0.5, "end": 0.9}]}]}
    assert normalize_words(data) == [{"w": "Hi", "s": 0.0, "e": 0.4}, {"w": "there", "s": 0.5, "e": 0.9}]


def test_normalize_deepgram_prefers_punctuated():
    data = {"results": {"channels": [{"alternatives": [{"words": [
        {"word": "hello", "punctuated_word": "Hello,", "start": 1, "end": 1.5}]}]}]}}
    assert normalize_words(data) == [{"w": "Hello,", "s": 1.0, "e": 1.5}]


def test_normalize_objects_and_ms():
    items = [SimpleNamespace(word=" yo", start=1000, end=1500), SimpleNamespace(word=" ", start=1, end=2)]
    assert normalize_words(items, ms=True) == [{"w": "yo", "s": 1.0, "e": 1.5}]


def test_normalize_rejects_missing_times():
    with pytest.raises(ValueError):
        normalize_words([{"word": "x"}])


def test_clip_words_shifts_to_zero():
    out = clip_words(WORDS, 1.0, 2.2)
    assert [w["w"] for w in out] == ["way", "he", "did", "that."]
    assert out[0]["s"] == 0.0 and out[-1]["e"] == pytest.approx(1.2)


# --- styles --------------------------------------------------------------

def test_colour():
    assert colour("#FFE14D") == "&H004DE1FF"
    assert colour("ffffff80") == "&H7FFFFFFF"
    assert colour("&h00ffffff") == "&H00FFFFFF"
    with pytest.raises(ValueError):
        colour("red")


# --- build_ass -----------------------------------------------------------

@pytest.mark.parametrize("name", list(STYLES))
def test_every_style_builds(name):
    ass = build_ass(WORDS, 5.0, style=name, title="wait for it", watermark="made with wordpop")
    assert ass.startswith("[Script Info]")
    assert "PlayResX: 1080" in ass
    assert dialogues(ass)
    assert len(dialogues(ass, "Hook")) == 1


def test_one_event_per_spoken_word_with_highlight():
    ass = build_ass(WORDS, 5.0, style="pop")
    caps = dialogues(ass)
    assert len(caps) == len(WORDS)
    assert "{\\c&H004DE1FF&}NO{\\r} WAY HE" in caps[0]


def test_lines_break_at_sentence_end_and_pause():
    ass = build_ass(WORDS, 5.0, style="clean")
    texts = [l.split(",Cap,,0,0,0,,", 1)[1] for l in dialogues(ass)]
    # max 5 words, but "that." ends a sentence and "chat" comes after a pause
    assert texts == ["no way he did that.", "chat"]


def test_custom_style_and_emoji_stripped():
    st = STYLES["pop"].replace(highlight="#FF00AA", max_words=1)
    ass = build_ass([{"w": "fire🔥", "s": 0, "e": 1}], style=st, font="Impact")
    assert "Style: Cap,Impact," in ass
    assert "{\\c&H00AA00FF&}FIRE{\\r}" in ass


def test_unknown_style_and_layout():
    with pytest.raises(ValueError):
        build_ass(WORDS, style="nope")
    with pytest.raises(ValueError):
        build_ass(WORDS, layout="nope")


def test_default_duration_and_empty():
    ass = build_ass(WORDS)
    assert dialogues(ass)[-1].split(",")[2] == "0:00:04.15"
    assert dialogues(build_ass([])) == []


def test_ass_override_chars_escaped():
    ass = build_ass([{"w": "{\\b1}x", "s": 0, "e": 1}], 1.0, style=Style(uppercase=False))
    assert "\\b1" not in ass


# --- cli -----------------------------------------------------------------

def test_cli_writes_file(tmp_path):
    src = tmp_path / "t.json"
    src.write_text(json.dumps({"words": WORDS}))
    out = tmp_path / "c.ass"
    assert main([str(src), "-o", str(out), "--style", "beast", "--start", "1", "--end", "3"]) == 0
    text = out.read_text(encoding="utf-8")
    assert "Luckiest Guy" in text and "Dialogue:" in text


@pytest.mark.parametrize("builder,sep", [(build_srt, ","), (build_vtt, ".")])
def test_plain_captions(builder, sep):
    words = normalize_words([{"w": "café", "s": 59.9996, "e": 60.1},
                             {"w": "<&>!", "s": 60.1, "e": 60.2},
                             {"w": "Bye", "s": 60.3, "e": 61}])
    result = builder(words, duration=60.55)
    assert result.count(" --> ") == 2
    assert f"00:01:00{sep}000 --> 00:01:00{sep}300\ncafé &lt;&amp;&gt;!" in result
    assert f"00:01:00{sep}300 --> 00:01:00{sep}550\nBye" in result
    if builder is build_srt:
        assert result.startswith("1\n") and "\n\n2\n" in result
    else:
        assert result.startswith("WEBVTT\n\n")


def test_plain_empty():
    assert build_srt([]) == ""
    assert build_vtt([]) == "WEBVTT\n\n"


@pytest.mark.parametrize("fmt,builder", [("srt", build_srt), ("vtt", build_vtt)])
def test_plain_cli(fmt, builder, tmp_path):
    transcript = tmp_path / "words.json"
    transcript.write_text(json.dumps(WORDS))
    out = tmp_path / f"captions.{fmt}"
    assert main([str(transcript), "--format", fmt, "-o", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == builder(WORDS)
