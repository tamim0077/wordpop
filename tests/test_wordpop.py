import json
from types import SimpleNamespace

import pytest

from wordpop import STYLES, Style, build_ass, clip_words, colour, normalize_words
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


@pytest.mark.parametrize("ms", [False, True])
def test_normalize_assemblyai_auto_detect(ms):
    # Shortened sample from AssemblyAI's Get a transcript API reference:
    # https://www.assemblyai.com/docs/pre-recorded-audio/api-reference/transcripts/get
    data = {
        "id": "9ea68fd3-f953-42c1-9742-976c447fb463",
        "status": "completed",
        "audio_url": "https://assembly.ai/wildfires.mp3",
        "words": [
            {
                "text": "Smoke",
                "start": 250,
                "end": 650,
                "confidence": 0.97465,
                "speaker": None,
            },
            {
                "text": "from",
                "start": 730,
                "end": 1022,
                "confidence": 0.99999,
                "speaker": None,
            },
        ],
    }

    words = normalize_words(data, ms=ms)

    assert [w["w"] for w in words] == ["Smoke", "from"]
    assert [w["s"] for w in words] == pytest.approx([0.25, 0.73])
    assert [w["e"] for w in words] == pytest.approx([0.65, 1.022])


@pytest.mark.parametrize("ms", [False, True])
def test_normalize_whisper_cpp(ms):
    # Shortened real output from:
    # https://github.com/ggml-org/whisper.cpp/discussions/3698
    data = {
        "transcription": [
            {
                "text": " And so",
                "tokens": [
                    {
                        "text": "[_BEG_]",
                        "id": 50363,
                        "offsets": {"from": 0, "to": 0},
                    },
                    {
                        "text": " And",
                        "id": 843,
                        "offsets": {"from": 320, "to": 370},
                    },
                    {
                        "text": " so",
                        "id": 523,
                        "offsets": {"from": 370, "to": 530},
                    },
                ],
            },
        ],
    }

    words = normalize_words(data, ms=ms)

    assert [w["w"] for w in words] == ["And", "so"]
    assert [w["s"] for w in words] == pytest.approx([0.32, 0.37])
    assert [w["e"] for w in words] == pytest.approx([0.37, 0.53])


def test_normalize_whisper_cpp_joins_word_pieces():
    data = {
        "transcription": [{
            "tokens": [
                {"text": " hel", "offsets": {"from": 100, "to": 200}},
                {"text": "lo", "offsets": {"from": 200, "to": 300}},
                {"text": "!", "offsets": {"from": 300, "to": 350}},
                {"text": " world", "offsets": {"from": 400, "to": 600}},
            ],
        }],
    }

    words = normalize_words(data)

    assert [w["w"] for w in words] == ["hello!", "world"]
    assert [w["s"] for w in words] == pytest.approx([0.1, 0.4])
    assert [w["e"] for w in words] == pytest.approx([0.35, 0.6])


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
