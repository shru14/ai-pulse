"""The daily listen: a two-minute clip of the day's top six stories, one from each stream, read aloud by a voice.

Which six (picks): each stream's biggest story of the day (digest._rank: most outlets first), so every stream is
heard; a stream with nothing that day gives its place to the biggest story left from the other streams. A reader who
chose streams or "More of" topics gets their own six: only their streams, what they left out never, and within each
stream their own picks first. Readers whose six come out the same share one clip (its name is made from the stories,
never from the reader).

The script is filled in from what the email already shows (headline, who reported it, the summary's
first sentence), so nothing is written by AI. The voice is Gemini's "Iapetus" (GEMINI_VOICE; owner's choice, 24 Nov
2026): Gemini only reads our script aloud, on the free tier (GEMINI_API_KEY, no billing account, nothing billed). Without
the key, or when Gemini refuses or the day's allowance is used up, Piper reads (MIT licence, offline on the CPU;
VOICE_NAME); without either (`pip install piper-tts lameenc` and the VOICE model) no clip is made and the email has no button.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any
import base64
import hashlib
import io
import json
import re
import shutil
import urllib.error
import urllib.request
import wave
from datetime import date, timedelta
from pathlib import Path

from . import config, digest, rss

TOP = 6  # one per stream
WEEK_ALSO = 8  # Sunday: the week's other important updates, after the story of the week
IMPORTANT = 4  # outlets: a week's story this widely carried is always in Sunday's clip (up to WEEK_ALSO)
# The voice: Piper's (MIT), trained on public-domain recordings only (LJ Speech), so the clips can be published.
# Not Lessac or Hi-Fi Captain: their recordings are licensed for research or non-commercial use only.
VOICE_NAME, VOICE_PATH = "en_US-ljspeech-high", "en/en_US/ljspeech/high"
VOICE = Path(__file__).resolve().parent.parent / "data" / "voice" / f"{VOICE_NAME}.onnx"
VOICE_URL = f"https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/{VOICE_PATH}/{VOICE_NAME}"  # + .onnx, .onnx.json
# The daily clip's voice since 24 Nov 2026 (owner's choice): Gemini's Iapetus ("clear"), free tier; it reads the
# script as given and writes nothing. Topic beats (topics.speak) keep Piper.
GEMINI_VOICE, GEMINI_TTS, GEMINI_RATE = "Iapetus", "gemini-2.5-flash-preview-tts", 24000  # 16-bit mono PCM back
GEMINI_API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_STYLE = "Read this news briefing in a calm, clear newsreader voice:\n\n"
FOLDER = "listen"  # on the site: listen/<day>-<setup>.mp3
KEEP_DAYS = 7  # clips older than this are taken off the site (emails link only the newest)
BITRATE = 48  # kbps, mono: about 0.7 MB for two minutes
_SPOKEN = {"releases": "Releases", "news": "Industry", "research": "Research", "regulation": "Regulation",
           "policy": "Policy", "infra": "Infrastructure"}


def _key(prefs: dict):
    """How a story ranks for a reader: their own picks first (if they chose any), then digest._rank."""
    _, theirs = digest._mine(prefs)
    tuned = bool(prefs.get("more") or prefs.get("words"))
    return lambda c: (tuned and theirs(c), *digest._rank(c))


def _one_each(by_stream: dict[str, list[dict]], streams: list[str], prefs: dict, n: int,
              skip: Sequence[dict] = ()) -> list[tuple[str, dict]]:
    """Up to n stories as (stream, story), biggest first: each stream's biggest, then, for streams with nothing, the
    biggest left from the others."""
    key = _key(prefs)
    ranked = {s: sorted([c for c in by_stream.get(s, []) if digest._fits_top(c) and c not in skip
                         and c.get("kind") not in digest.SIDE_KINDS], key=key, reverse=True) for s in streams}
    out = [(s, ranked[s][0]) for s in streams if ranked[s]][:n]
    out += sorted(((s, c) for s in streams for c in ranked[s][1:]), key=lambda sc: key(sc[1]), reverse=True)[:n - len(out)]
    return sorted(out, key=lambda sc: key(sc[1]), reverse=True)


def plan(cards: list[dict], day: date, streams: list[str], prefs: dict | None = None) -> dict:
    """What a reader's clip holds: "six", the day's top stories (TOP, one per stream). On Sunday (the day is a Saturday)
    the week comes first: "week", the story of the week as the email picks it (digest._week_story), and "also", the
    week's other important updates: every story IMPORTANT outlets carried, and each stream's biggest one 2+ carried
    (so every stream is heard), at most WEEK_ALSO. Saturday's six then leave out what the week already said."""
    prefs = prefs or {}
    said: list[dict] = []
    out: dict[str, Any] = {}
    if digest.weekly(day):
        week = digest._week_story(cards, day, prefs)
        monday, _ = digest._span(day)
        whole: dict[str, list[dict]] = {s: [] for s in streams}
        for k in range((day - monday).days + 1):
            for s, cs in digest._leave_out(digest.by_streams(cards, streams, monday + timedelta(days=k)), prefs)[0].items():
                whole[s] += [c for c in cs if digest._outlets(c) >= 2 and c is not week]
        key = _key(prefs)
        also = _one_each(whole, streams, prefs, len(streams))
        also += [(s, c) for s in streams for c in whole[s] if digest._outlets(c) >= IMPORTANT and (s, c) not in also]
        out["week"], out["also"] = week, sorted(also, key=lambda sc: key(sc[1]), reverse=True)[:WEEK_ALSO] if week else []
        said = ([week] if week else []) + [c for _, c in out["also"]]
    by_stream, _ = digest._leave_out(digest.by_streams(cards, streams, day), prefs)
    out["six"] = _one_each(by_stream, streams, prefs, TOP, said)
    return out


def _own(streams: list[str], prefs: dict | None) -> bool:
    """Did the reader make their clip their own (fewer streams, or topics, words or left-outs of their own)?"""
    prefs = prefs or {}
    return set(streams) != set(rss.FEEDS) or bool(prefs.get("more") or prefs.get("words") or prefs.get("less"))


def line(plan_: dict, streams: list[str], prefs: dict | None, seconds: int) -> str:
    """The email bar's line under "Listen to the digest": how long, then what's in it, true for this reader's clip
    ("one from each stream" only when each of the six streams gave one)."""
    six = plan_["six"]
    if _own(streams, prefs):
        what = f"your top {len(six)}, from your streams and choices"
    elif len({n for n, _ in six}) == len(rss.FEEDS) == len(six):
        what = f"the day's top {len(six)}, one from each stream"
    else:
        what = f"the day's top {len(six)}"
    if plan_.get("week"):
        what = "the week's important updates, then Saturday in short"
    minutes = max(1, round(seconds / 60))
    return f"{minutes} minute{'s' if minutes > 1 else ''} · {what}"


def name(day: date, plan_: dict) -> str:
    """A clip's file in the store: the day and a short fingerprint of its stories (setups with the same ones share
    it, so it's spoken once)."""
    stories = [plan_.get("week")] + [c for k in ("also", "six") for _, c in plan_.get(k, [])]
    ids = "\n".join(c["url"] for c in stories if c)
    return f"{day.isoformat()}-{hashlib.sha1(ids.encode()).hexdigest()[:10]}.mp3"


def setup(streams: list[str], prefs: dict | None) -> str:
    """A reader's clip's name on the site: "everyone", or a short code of the settings that change it (streams, More
    of, Leave out, own words), the same for every reader who set the same; nothing about who they are. The email
    finds the clip by it, so a later site run that adds late stories updates the clip at the same address."""
    if not _own(streams, prefs):
        return "everyone"
    prefs = prefs or {}
    said = {"streams": sorted(streams), **{k: sorted(prefs.get(k) or []) for k in ("more", "less", "words")}}
    return hashlib.sha1(json.dumps(said, sort_keys=True).encode()).hexdigest()[:12]


def url(day: date, streams: list[str], prefs: dict | None) -> str:
    return f"{rss.SITE}{FOLDER}/{day.isoformat()}-{setup(streams, prefs)}.mp3"


def make(cards: list[dict], day: date, setups: list[tuple[list[str], dict]], folder: Path, log=print) -> int:
    """Every setup's clip for `day` in `folder` (the site's listen/, kept between runs): each distinct set of
    stories spoken once into store/, then copied to <day>-<setup>.mp3. Files older than KEEP_DAYS go. Returns how
    many were spoken this run (0 without any voice: then no clip, and the email shows no bar). Gemini reads while
    it answers; after its first refusal Piper reads the rest of the run."""
    store = folder / "store"
    store.mkdir(parents=True, exist_ok=True)
    first = (day - timedelta(days=KEEP_DAYS - 1)).isoformat()
    for f in [*folder.glob("*.mp3"), *store.glob("*.mp3")]:
        if f.name[:10] < first:
            f.unlink()
    voice, spoken, key = None, 0, config.gemini_key()
    for streams, prefs in [(list(rss.FEEDS), {})] + setups:
        plan_ = plan(cards, day, streams, prefs)
        if not plan_["six"] and not plan_.get("week"):
            continue
        kept = store / name(day, plan_)
        if not kept.exists():
            text = script(day, plan_, _own(streams, prefs))
            mp3 = gemini(text, key, log) if key else None
            if key and not mp3:  # refused, busy or out of allowance: Piper reads the rest of this run
                key = ""
            if not mp3:
                voice = voice or _voice()
                mp3 = speak(text, voice) if voice else None
            if not mp3:
                log("listen: no voice (GEMINI_API_KEY, or pip install piper-tts lameenc and the VOICE model); "
                    "no more clips")
                return spoken
            kept.write_bytes(mp3)
            spoken += 1
        shutil.copyfile(kept, folder / f"{day.isoformat()}-{setup(streams, prefs)}.mp3")
    return spoken


def seconds(link: str) -> int | None:
    """How long a published clip runs (from its size: mono 48 kbps), or None if the site doesn't have it."""
    try:
        with urllib.request.urlopen(urllib.request.Request(link, method="HEAD"), timeout=10) as r:
            size = int(r.headers.get("Content-Length") or 0) if r.status == 200 else 0
    except (OSError, ValueError):
        return None
    return round(size * 8 / (BITRATE * 1000)) if size else None


def _clean(text: str) -> str:
    """Text a voice reads well: no links, symbols spoken as words, no trailing ellipsis."""
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\$\s?(\d[\d.,]*)\s?(trillion|billion|million|bn|mn|tn|B|M)\b",
                  lambda m: f"{m[1]} {dict(bn='billion', mn='million', tn='trillion', B='billion', M='million').get(m[2], m[2])} dollars",
                  text)
    text = re.sub(r"\$\s?(\d[\d.,]*)", r"\1 dollars", text)
    text = text.replace("&", " and ").replace("%", " percent").replace("…", ".").replace("|", ",")
    return re.sub(r"\s+", " ", text).strip()


def _first_sentence(c: dict) -> str:
    """The summary's first sentence, if its outlet allows a part of it (digest.AS_PROVIDED: only as given) and it
    says more than the headline."""
    from .poster import _sentences
    summary = re.sub(r"\s*Machine-translated from \w+;.*$", "", (c.get("summary") or "").strip())  # our own note
    if not summary or c.get("source") in digest.AS_PROVIDED:
        return ""
    first = _sentences(summary)[0].strip()
    if len(first.split()) > 40 or first.lower().startswith(c["title"].lower()[:40]):
        return ""
    return first if first.endswith((".", "!", "?")) and not first.endswith("..") else ""  # never a cut-off one


def _nth(day: date) -> str:
    return f"{day.day}{'th' if 10 <= day.day % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(day.day % 10, 'th')}"


def _said(c: dict) -> str:
    """The headline as a sentence."""
    title = c["title"].strip()
    return title if title.endswith((".", "?", "!")) else title + "."


def _reported(c: dict) -> str:
    if c.get("source") in digest._OWN_BLOGS:  # a lab's or company's own post
        return f"From {c['source']}."
    return f"Reported by {c.get('source', '')}."  # who, never how many (counts read out sound odd)


def _stream(c: dict) -> str:
    return next((_SPOKEN[n] for n in rss.FEEDS if rss.FEEDS[n][0] == c.get("category")), "")


def script(day: date, plan_: dict, own: bool = False) -> str:
    """What the voice reads. Every day: the day, then its stories (stream, headline, who reported it, a sentence) and a
    sign-off. On Sunday the week comes first (the important updates: the story of the week with its sentence, then the
    others, headline and who reported it), then Saturday in short (headline and outlet only), so the week stays first.
    `own`: the reader made the clip their own (_own), so it says "your" stories, never "one from each stream"."""
    count = ["first", "second", "third", "fourth", "fifth", "sixth"]
    six, week, lines = plan_["six"], plan_.get("week"), []
    yours = "your" if own else "the"
    if week:
        monday, _ = digest._span(day)
        lines.append(f"This is Pulse Weekly for the week of {monday:%A} the {_nth(monday)} to {day:%A} the {_nth(day)} of "
                     f"{day:%B}. These were the important updates this week.")
        lines.append(f"The story of the week, from {_stream(week)}. {_said(week)} {_reported(week)} {_first_sentence(week)}")
        lines += [f"In {_SPOKEN[n]}. {_said(c)} {_reported(c)}" for n, c in plan_.get("also") or []]
        if six:
            lines.append(f"Now, {day:%A} the {_nth(day)}, in short. "
                         + " ".join(f"From {_SPOKEN[n]}: {_said(c)} {_reported(c)}" for n, c in six))
    else:
        lines.append(f"This is Pulse Daily for {day:%A} the {_nth(day)} of {day:%B}. Here are {yours} {len(six)} "
                     + ("top stories, from the streams and choices you picked." if own else "stories that mattered most."))
        for i, (n, c) in enumerate(six):
            lines.append(f"{'Up first' if i == 0 else 'The ' + count[i] + ' story'}, from {_SPOKEN[n]}. "
                         f"{_said(c)} {_reported(c)} {_first_sentence(c)}")
    lines.append(f"Every story, with links, is in {'this week' if week else 'today'}'s email and on project AI pulse dot com. "
                 + ("See you next week." if week else "See you tomorrow."))
    return "\n\n".join(_clean(line) for line in lines)


def _voice():
    try:
        from piper import PiperVoice
    except ImportError:
        return None
    return PiperVoice.load(str(VOICE)) if VOICE.exists() else None


_SPOKEN_PARTS: dict[str, tuple[int, bytes]] = {}  # a part's sound, spoken once a run: clips share most stories


def _part(part: str, voice) -> tuple[int, bytes]:
    if part not in _SPOKEN_PARTS:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            voice.synthesize_wav(part, w)
        buf.seek(0)
        with wave.open(buf) as w:
            _SPOKEN_PARTS[part] = (w.getframerate(), w.readframes(w.getnframes()))
    return _SPOKEN_PARTS[part]


def speak(text: str, voice=None) -> bytes | None:
    """The script as an MP3 (mono, 48 kbps: about 0.7 MB for two minutes), or None without Piper and its voice."""
    voice = voice or _voice()
    if voice is None:
        return None
    rate, pcm = 0, b""
    for part in text.split("\n\n"):  # a story at a time, with a short pause after each
        rate, sound = _part(part, voice)
        pcm += sound + b"\x00\x00" * int(rate * 0.6)
    return _mp3(pcm, rate)


def gemini(text: str, key: str, log=print) -> bytes | None:
    """The script read by Gemini's GEMINI_VOICE, as an MP3; None when Gemini refuses, is busy, is out of the day's
    free allowance or sends no sound (the log names the HTTP code only, never the key or the text)."""
    body = json.dumps({"contents": [{"parts": [{"text": GEMINI_STYLE + text}]}],
                       "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {
                           "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": GEMINI_VOICE}}}}}).encode()
    req = urllib.request.Request(GEMINI_API.format(model=GEMINI_TTS), data=body, method="POST",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})  # key in a header
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            pcm = base64.b64decode(json.loads(r.read())["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
    except urllib.error.HTTPError as e:
        log(f"listen: Gemini voice unavailable (HTTP {e.code}); Piper reads instead")
        return None
    except Exception as e:  # no answer, or no sound in it
        log(f"listen: Gemini voice unavailable ({type(e).__name__}); Piper reads instead")
        return None
    return _mp3(pcm, GEMINI_RATE) if len(pcm) > GEMINI_RATE else None  # under half a second: nothing was read


def _mp3(pcm: bytes, rate: int) -> bytes:
    import lameenc
    enc = lameenc.Encoder()
    enc.set_bit_rate(BITRATE)
    enc.set_in_sample_rate(rate)
    enc.set_channels(1)
    enc.set_quality(2)
    return enc.encode(pcm) + enc.flush()
