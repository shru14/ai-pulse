"""English versions of non-English official records (Brazil's bill summaries, China's regulation titles), made offline.

The translation runs on this machine (or the GitHub runner): an OPUS-MT model (Tiedemann & Thottingal,
University of Helsinki, CC BY 4.0) as packaged by Argos Translate, loaded with CTranslate2 and
SentencePiece. No API is called and nothing is billed. The model file (~66 MB) is downloaded once into
data/translate-models/. Each text is translated once and kept in the database (table `translations`).

It's optional: without the two libraries (`pip install ctranslate2 sentencepiece`) or the model, the
records keep their original language and everything else works as before.
"""

from __future__ import annotations

import hashlib
import io
import os
import re
import zipfile
from pathlib import Path

from . import feeds

MODELS = {"pt": "https://argos-net.com/v1/translate-pt_en-1_9.argosmodel",
          "zh": "https://argos-net.com/v1/translate-zh_en-1_9.argosmodel"}
LANGUAGE_NAMES = {"pt": "Portuguese", "zh": "Chinese"}
VERSION = "2"  # part of each stored translation's key: bump it when the term fixes below change

# Fixed terms, per language. BEFORE replaces a phrase in the original that the model mistranslates (only
# where mixing in English doesn't confuse it); AFTER corrects the model's English to the standard term in
# the English versions governments use ("办法" is "Measures", "意见" is "Opinions", "智能体" is "AI agents").
BEFORE = {"zh": [("“人工智能+”", "“AI+”"), ("人工智能+", "AI+")]}
AFTER = {"zh": [(re.compile(p), r) for p, r in (
    (r"^Circular on the issuance of (the )?", "Notice on issuing the "),
    (r"\b[Ii]nterim (approach|method)(es|s)? (to|for) (the )?management of\b", "Interim Measures for the Administration of"),
    (r"\b[Ii]nterim (approach|method)(es|s)?\b", "Interim Measures"),
    (r"\b(approach|method)(es|s)?(?=[”\"]?$)", "Measures"), (r"\bManual for\b", "Measures for"),
    (r"^Views of\b", "Opinions of"), (r"\b[Ii]mplementation (advice|views)\b", "Implementing Opinions"),
    (r"\bgenerated artificial intelligence\b", "generative artificial intelligence"),
    (r"\b(smart|intelligent) bodies\b", "AI agents"), (r"\bhumanized\b", "human-like"),
    (r"“AI\+” (operation|initiative|campaign)", "“AI+” Action"), (r"\bMarking of\b", "Labelling of"))]}
MODEL_DIR = Path(__file__).resolve().parent.parent / "data" / "translate-models"

SCHEMA = """
CREATE TABLE IF NOT EXISTS translations (
    key  TEXT PRIMARY KEY,   -- language + hash of the original text
    lang TEXT NOT NULL,
    text TEXT NOT NULL       -- the English version
);
"""

# The model tends to start legal summaries with a subject ("It amends ..."); official English style doesn't.
_OPENERS = [(re.compile(p, re.I), r) for p, r in (
    (r"^It has on\b", "Provides for"), (r"^It provides (on|for|about)\b", "Provides for"),
    (r"^It deals with\b", "Provides for"), (r"^It (amends|alters|changes)\b", "Amends"),
    (r"^It (establishes|institutes)\b", "Establishes"), (r"^It\s+(\w)", r"\1"))]

_loaded: dict[str, tuple] = {}


def _key(lang: str, text: str) -> str:
    return f"{lang}:{VERSION}:{hashlib.sha1(text.encode('utf-8')).hexdigest()}"


def _model(lang: str):
    """(translator, tokenizer) for `lang` -> English, downloading the model once; None if unavailable."""
    if lang in _loaded:
        return _loaded[lang]
    if os.environ.get("AIPULSE_OFFLINE"):  # tests: stored translations only
        return None
    try:
        import ctranslate2
        import sentencepiece
    except ImportError:
        _loaded[lang] = None
        return None
    url = MODELS.get(lang)
    if not url:
        _loaded[lang] = None
        return None
    name = url.rsplit("/", 1)[1].removesuffix(".argosmodel")
    folder = MODEL_DIR / name
    if not (folder / "model" / "model.bin").exists():
        try:
            data = feeds.fetch(url, timeout=300)
        except Exception:
            _loaded[lang] = None
            return None
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        zipfile.ZipFile(io.BytesIO(data)).extractall(MODEL_DIR)
    _loaded[lang] = (ctranslate2.Translator(str(folder / "model"), device="cpu"),
                     sentencepiece.SentencePieceProcessor(model_file=str(folder / "sentencepiece.model")))
    return _loaded[lang]


def tidy(text: str) -> str:
    """The model's raw output as a clean English sentence."""
    text = re.sub(r"\s+", " ", text.replace("▁", " ")).strip()
    # "e dá outras providências", the closing formula of Brazilian bill summaries
    text = re.sub(r"\b(gives|makes|takes) other (measures|provisions|arrangements)\b", "makes other provisions", text)
    for pattern, repl in _OPENERS:
        new = pattern.sub(repl, text, count=1)
        if new != text:
            text = new
            break
    return text[:1].upper() + text[1:]


def _before(lang: str, text: str) -> str:
    for old, new in BEFORE.get(lang, []):
        text = text.replace(old, new)
    return text


def _after(lang: str, text: str) -> str:
    for pattern, repl in AFTER.get(lang, []):
        text = pattern.sub(repl, text)
    return text


def connect(conn) -> None:
    conn.executescript(SCHEMA)


def english(conn, lang: str, texts: list[str]) -> dict[str, str]:
    """English versions of `texts` (original -> English): from the database, translating the new ones.
    Texts that can't be translated (no model) are left out."""
    connect(conn)
    out, todo = {}, []
    for t in dict.fromkeys(t for t in texts if t):
        row = conn.execute("SELECT text FROM translations WHERE key = ?", (_key(lang, t),)).fetchone()
        if row:
            out[t] = row[0]
        else:
            todo.append(t)
    model = _model(lang) if todo else None
    if model:
        translator, sp = model
        for i in range(0, len(todo), 16):
            batch = todo[i:i + 16]
            results = translator.translate_batch([sp.encode(_before(lang, t), out_type=str) for t in batch],
                                                 beam_size=2, max_decoding_length=400)
            for src, r in zip(batch, results):
                out[src] = _after(lang, tidy("".join(r.hypotheses[0])))
                conn.execute("INSERT OR REPLACE INTO translations VALUES (?, ?, ?)", (_key(lang, src), lang, out[src]))
            conn.commit()
    return out


def cached(conn, lang: str, text: str) -> str | None:
    """The stored English version of `text`, if there is one (no translating)."""
    connect(conn)
    row = conn.execute("SELECT text FROM translations WHERE key = ?", (_key(lang, text),)).fetchone()
    return row[0] if row else None
