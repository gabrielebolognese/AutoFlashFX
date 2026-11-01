"""pipeline/lib/motion/captions.py: caption chunks from words.json (style.md Captions: 1 to 4 words per chunk, each
word shown when spoken, 1 to 3 emphasis words per chunk on accent boxes). A deterministic chunker: it breaks at a
sentence end, at a pause of pause_ms or more, at a beat boundary and at the word limit. The golden plan uses it;
9b (M10) can use it as its baseline before the model refines the chunks.

  chunk_words(words, emphasis_terms, max_words=4, pause_ms=150) -> [{"start_ms", "end_ms", "scene"?, "words": [{"word", "start_ms", "end_ms", "emphasis"}]}]
      words: words.json entries [{"word", "start_ms", "end_ms", "beat"}] of one or more beats
      emphasis_terms: {beat id: ["term", ...]} from script.json (a term may be several words)
  to_component_chunks(chunks, clip_start_ms) -> the caption-line component's chunks_json (seconds local to the clip)
"""
from __future__ import annotations

import re

SENTENCE_END = re.compile(r"[.!?]$")
CLAUSE_END = re.compile(r"[,;:]$")


def norm(word: str) -> str:
    return re.sub(r"[^a-z0-9#'%/.@-]", "", word.lower()).strip(".")


def emphasis_flags(words: list[dict], terms: list[str]) -> list[bool]:
    """Mark the words of every term (a term may span several words); case and punctuation do not count."""
    flags = [False] * len(words)
    normed = [norm(w["word"]) for w in words]
    for term in terms or []:
        parts = [norm(p) for p in str(term).split() if norm(p)]
        if not parts:
            continue
        for i in range(len(normed) - len(parts) + 1):
            if normed[i:i + len(parts)] == parts:
                for j in range(len(parts)):
                    flags[i + j] = True
                break
    return flags


def chunk_words(words: list[dict], emphasis_terms: dict | None, max_words: int = 4, pause_ms: int = 150, max_emphasis: int = 3) -> list[dict]:
    chunks = []
    by_beat: dict[str, list[dict]] = {}
    order = []
    for w in words:
        b = w.get("beat", "")
        if b not in by_beat:
            by_beat[b] = []
            order.append(b)
        by_beat[b].append(w)
    for beat in order:
        ws = by_beat[beat]
        flags = emphasis_flags(ws, (emphasis_terms or {}).get(beat, []))
        cur: list[dict] = []
        for i, w in enumerate(ws):
            entry = {"word": w["word"], "start_ms": int(w["start_ms"]), "end_ms": int(w["end_ms"]), "emphasis": bool(flags[i])}
            cur.append(entry)
            nxt = ws[i + 1] if i + 1 < len(ws) else None
            boundary = (nxt is None or len(cur) >= max_words or SENTENCE_END.search(w["word"]) is not None
                        or (nxt is not None and int(nxt["start_ms"]) - int(w["end_ms"]) >= pause_ms)
                        or (CLAUSE_END.search(w["word"]) is not None and len(cur) >= 2))
            if boundary:
                em = [e for e in cur if e["emphasis"]]
                for extra in em[max_emphasis:]:
                    extra["emphasis"] = False
                chunks.append({"scene": beat, "start_ms": cur[0]["start_ms"], "end_ms": cur[-1]["end_ms"], "words": cur})
                cur = []
    # a chunk stays until the next one starts (the component keeps a frame of air), the last one holds 400 ms
    for a, b in zip(chunks, chunks[1:]):
        a["end_ms"] = max(a["end_ms"], b["start_ms"])
    if chunks:
        chunks[-1]["end_ms"] = chunks[-1]["end_ms"] + 400
    return chunks


def to_component_chunks(chunks: list[dict], clip_start_ms: int) -> list[dict]:
    out = []
    for c in chunks:
        out.append({
            "start": round((c["start_ms"] - clip_start_ms) / 1000, 3),
            "end": round((c["end_ms"] - clip_start_ms) / 1000, 3),
            "words": [{"w": w["word"], "t": round((w["start_ms"] - clip_start_ms) / 1000, 3), "em": bool(w.get("emphasis"))} for w in c["words"]],
        })
    return out
