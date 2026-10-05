"""Story vectors for the weekly briefing's search, made offline.

Each story (headline and the publisher's short description, nothing more) becomes a list of 384 numbers that
places stories about the same thing near each other, whatever words they use. The model is BGE-base-en-v1.5
(Xiao et al., BAAI, MIT licence; https://huggingface.co/BAAI/bge-base-en-v1.5), as converted for CTranslate2
(https://huggingface.co/michaelfeil/ct2fast-bge-base-en-v1.5, pinned below), and runs on this machine
or the GitHub runner with the same library as the translator. No API is called and nothing is billed. The
model (~220 MB) is downloaded once into data/embed-models/. The vector of each of the last DAYS days' stories is kept in the database
(table `vectors`) and made again only when its text changes.

It's optional: without ctranslate2 or the model, nothing is embedded and everything else works as before.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import unicodedata
from pathlib import Path

from . import feeds

REPO = "michaelfeil/ct2fast-bge-base-en-v1.5"
REVISION = "2de9369ae5d9ea282d10ebf838f312780e923fff"  # pinned: the vectors stay comparable run to run
FILES = ("config.json", "model.bin", "vocabulary.txt", "vocab.txt")  # vocabulary.txt: the encoder's; vocab.txt: WordPiece's
MODEL = "bge-base-en-v1.5"  # stored with each vector, so a new model re-embeds everything
DIM = 768
# BGE is told which side a text is on: a reader's question carries this instruction, a story nothing
QUERY = "Represent this sentence for searching relevant passages: "
MAX_TOKENS = 128  # a headline and a short description fit; longer text is cut
BATCH = 64
DAYS = 45  # stories this recent are embedded: last week and the month before it (the dossier's "Dig deeper"); older dropped
MODEL_DIR = Path(__file__).resolve().parent.parent / "data" / "embed-models" / MODEL

SCHEMA = """
CREATE TABLE IF NOT EXISTS vectors (
    id    TEXT PRIMARY KEY,  -- the story's id (items.id)
    model TEXT NOT NULL,
    hash  TEXT NOT NULL,     -- of the text embedded: a changed headline or description is embedded again
    vec   BLOB NOT NULL      -- DIM float16 numbers, length 1
);
"""


def connect(conn) -> None:
    conn.executescript(SCHEMA)


# ---------- The tokenizer: BERT's WordPiece (lower case, accents off), as the model was trained ----------

class WordPiece:
    def __init__(self, vocab: Path):
        self.ids = {t: i for i, t in enumerate(vocab.read_text(encoding="utf-8").splitlines())}

    @staticmethod
    def _cjk(cp: int) -> bool:
        return (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or 0x20000 <= cp <= 0x2A6DF or 0x2A700 <= cp <= 0x2B73F
                or 0x2B740 <= cp <= 0x2B81F or 0x2B820 <= cp <= 0x2CEAF or 0xF900 <= cp <= 0xFAFF or 0x2F800 <= cp <= 0x2FA1F)

    @staticmethod
    def _punct(ch: str) -> bool:
        cp = ord(ch)
        return 33 <= cp <= 47 or 58 <= cp <= 64 or 91 <= cp <= 96 or 123 <= cp <= 126 or unicodedata.category(ch).startswith("P")

    def _words(self, text: str) -> list[str]:
        out = []
        for ch in unicodedata.normalize("NFD", text.lower()):
            cp = ord(ch)
            if cp in (0, 0xFFFD) or unicodedata.category(ch) == "Mn" or (unicodedata.category(ch) in ("Cc", "Cf") and ch not in "\t\n\r"):
                continue
            if ch.isspace():
                out.append(" ")
            elif self._cjk(cp) or self._punct(ch):
                out += [" ", ch, " "]
            else:
                out.append(ch)
        return "".join(out).split()

    def tokens(self, text: str, limit: int = MAX_TOKENS) -> list[str]:
        pieces = []
        for word in self._words(text):
            if len(word) > 100:
                pieces.append("[UNK]")
                continue
            start, sub = 0, []
            while start < len(word):
                end = len(word)
                while end > start and (("##" if start else "") + word[start:end]) not in self.ids:
                    end -= 1
                if end == start:
                    sub = ["[UNK]"]
                    break
                sub.append(("##" if start else "") + word[start:end])
                start = end
            pieces += sub
            if len(pieces) >= limit - 2:
                break
        return ["[CLS]", *pieces[:limit - 2], "[SEP]"]


# ---------- The model ----------

_loaded: dict = {}


def _model():
    """(encoder, tokenizer), downloading the model once; None if unavailable."""
    if "m" in _loaded:
        return _loaded["m"]
    _loaded["m"] = None
    if os.environ.get("AIPULSE_OFFLINE") and not (MODEL_DIR / "model.bin").exists():  # tests: never download
        return None
    try:
        import ctranslate2
    except ImportError:
        return None
    if importlib.util.find_spec("numpy") is None:  # comes with ctranslate2
        return None
    if not all((MODEL_DIR / f).exists() for f in FILES):
        try:
            MODEL_DIR.mkdir(parents=True, exist_ok=True)
            for f in FILES:
                data = feeds.fetch(f"https://huggingface.co/{REPO}/resolve/{REVISION}/{f}", timeout=300)
                (MODEL_DIR / (f + ".part")).write_bytes(data)
                (MODEL_DIR / (f + ".part")).replace(MODEL_DIR / f)
        except Exception:
            return None
    _loaded["m"] = (ctranslate2.Encoder(str(MODEL_DIR), device="cpu", compute_type="float32"),
                    WordPiece(MODEL_DIR / "vocab.txt"))
    return _loaded["m"]


def available() -> bool:
    return _model() is not None


def encode(texts: list[str], query: bool = False):
    """Unit-length vectors (numpy float32, len(texts) x DIM) for these texts: a reader's question (`query`) or
    stories."""
    import numpy as np
    model = _model()
    if model is None:
        raise RuntimeError("the embedding model isn't available")
    encoder, wp = model
    prefix = QUERY if query else ""
    out = np.zeros((len(texts), DIM), dtype=np.float32)
    tokens = [wp.tokens(prefix + t) for t in texts]
    order = sorted(range(len(texts)), key=lambda j: len(tokens[j]))  # similar lengths together: less padding
    for k in range(0, len(order), BATCH):
        batch = order[k:k + BATCH]
        hidden = np.array(encoder.forward_batch([tokens[j] for j in batch]).last_hidden_state, dtype=np.float32)
        for row, j in enumerate(batch):  # BGE's vector is its first token's ([CLS])
            v = hidden[row, 0]
            out[j] = v / (np.linalg.norm(v) or 1.0)
    return out


def story_text(title: str, summary: str) -> str:
    return f"{(title or '').strip()}. {(summary or '').strip()}".strip(" .")


def update(conn, limit: int | None = None, log=print) -> int:
    """Embed the last DAYS days' stories that are new or changed since the last run; returns how many."""
    import numpy as np
    connect(conn)
    if not available():
        log("embed: the model isn't available; nothing embedded")
        return 0
    have = {i: (m, h) for i, m, h in conn.execute("SELECT id, model, hash FROM vectors")}
    todo = []
    for i, title, summary in conn.execute("SELECT id, title, summary FROM items WHERE date >= date('now', ?) ORDER BY date DESC",
                                          (f"-{DAYS} days",)):
        text = story_text(title, summary)
        h = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
        if have.get(i) != (MODEL, h):
            todo.append((i, h, text))
        if limit and len(todo) >= limit:
            break
    for k in range(0, len(todo), 512):
        chunk = todo[k:k + 512]
        vecs = encode([t for _, _, t in chunk]).astype(np.float16)
        conn.executemany("INSERT OR REPLACE INTO vectors (id, model, hash, vec) VALUES (?, ?, ?, ?)",
                         [(i, MODEL, h, v.tobytes()) for (i, h, _), v in zip(chunk, vecs)])
        conn.commit()
    # stories that are gone (merged or purged) or older than DAYS lose their vectors too
    conn.execute("DELETE FROM vectors WHERE id NOT IN (SELECT id FROM items WHERE date >= date('now', ?))", (f"-{DAYS} days",))
    conn.commit()
    log(f"embed: {len(todo)} stories embedded")
    return len(todo)
