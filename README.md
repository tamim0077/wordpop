# wordpop

Word-by-word captions for short-form video (TikTok / Reels / Shorts style), from any
word-level transcript, as an `.ass` subtitle file you can burn in with ffmpeg.

![all 8 styles](https://raw.githubusercontent.com/tamim0077/wordpop/main/docs/demo.gif)

The word being spoken is highlighted, popped or boxed. Lines break on pauses,
sentence ends and a max length, so they read the way people talk.

No dependencies. Works with Whisper, faster-whisper, WhisperX, Deepgram, AssemblyAI,
or your own `{"word", "start", "end"}` list.

I pulled this out of the video clipper I'm building, where it captions real
Twitch / Kick clips every day.

## Install

```bash
pip install wordpop
```

You also need `ffmpeg` (built with libass, which most builds are) to burn captions in.

## Quick start

```python
import json
from wordpop import normalize_words, build_ass, burn

words = normalize_words(json.load(open("transcript.json")))  # Whisper / Deepgram / ...
ass = build_ass(words, style="beast", title="wait for it")
burn("clip.mp4", ass, "clip_captioned.mp4")
```

Cut a clip out of a long video? Shift the words so the clip starts at 0:

```python
from wordpop import clip_words
ass = build_ass(clip_words(words, 44.7, 75.2), duration=30.5, style="pop")
```

## Command line

```bash
wordpop transcript.json -o captions.ass --style pop --title "wait for it"
wordpop transcript.json --video in.mp4 --out out.mp4 --style neon --start 44.7 --end 75.2
```

Use plain captions for a player or editing timeline. Each group becomes one cue.
The default is ASS. Burning a video still uses ASS styling, and you can add a plain file with `-o`.

```sh
wordpop examples/transcript.json --format srt -o captions.srt
wordpop examples/transcript.json --format vtt -o captions.vtt
```

## Styles

| name      | look                                                    | font            |
|-----------|---------------------------------------------------------|-----------------|
| `pop`     | bold caps, spoken word yellow                           | Anton (default) |
| `classic` | heavy white caps, thick outline, spoken word pops       | Archivo Black   |
| `beast`   | rounded cartoon caps, spoken word green and bouncing    | Luckiest Guy    |
| `comic`   | comic-book caps, spoken word red                        | Bangers         |
| `neon`    | heavy caps, spoken word glowing cyan                    | Archivo Black   |
| `box`     | bold caps, spoken word on a bright block                | Anton (default) |
| `minimal` | small sentence case, words fade in as they're said      | Poppins         |
| `clean`   | sentence case on a dark plate, no per-word highlight    | Poppins         |

Make your own:

```python
from wordpop import STYLES, Style

mine = STYLES["pop"].replace(highlight="#FF3EA5", max_words=2, pop_scale=115)
ass = build_ass(words, style=mine, font="Montserrat Black")
```

All `Style` fields are documented in [`styles.py`](src/wordpop/styles.py).

## Fonts

libass finds fonts by family name. Install them, or put the `.ttf` files in a folder
and pass `fonts_dir=` to `burn` (or `--fonts-dir` on the CLI). All are free on
Google Fonts: Anton, Archivo Black, Luckiest Guy, Bangers, Poppins (Bold).
If a font is missing, libass falls back to a system font.

## Layouts

The canvas is 1080x1920 (9:16). `layout` sets where the caption line sits:

- `fill`  – video fills the frame, captions in the lower third
- `blur`  – video in the middle on a blurred background (default)
- `split` – face cam on top, gameplay below; captions and hook sit on the middle line

Need a different spot? `build_ass(..., margin_v=600)`.

## Options

`build_ass(words, duration=None, *, style="pop", title=None, layout="blur", font="Anton",
hook_font=None, watermark=None, watermark_size="small", margin_v=None)`

- `title` – hook text shown at the top for the whole clip
- `watermark` – small text in the corner (`"small"`) or bottom centre (`"full"`)
- emoji are removed (caption fonts don't have them, they'd show as boxes)

## Contributing

Issues and PRs welcome, especially new styles (with a screenshot) and transcript
formats that `normalize_words` doesn't read yet. See [CONTRIBUTING.md](CONTRIBUTING.md)
and the [good first issues](https://github.com/tamim0077/wordpop/labels/good%20first%20issue).

```bash
pip install -e ".[test]"
pytest
```

## License

MIT
