#!/usr/bin/env python
"""voiceprofile.py: build library/profile/voice.md and account.md (BUILD_SPEC.md 2.3, PLAN.md M5).

Driven by pipeline/bin/build-voice-profile. Two interpreters run this file: the transcription runs under the
interpreter that has faster-whisper (the one named in library/voice/engine.txt, or .venv-tts), everything else
under the project's `python`. So this file stays compatible with Python 3.11 and imports faster_whisper only
inside `transcribe`.

  voiceprofile.py transcribe AUDIO --out words.json [--model small.en] [--language en]
        faster-whisper on CPU (compute_type int8): segments with word timestamps. The configured model is tried
        from the local cache first, then "small" from the cache, then the configured model with a download.
  voiceprofile.py measure --words words.json [--max-excerpts 5]
        {words, speech_seconds, gross_seconds, wpm, wpm_raw, excerpts: [..]}: the pace in words per minute over
        the recording with pauses longer than 1.5 s removed (wpm_raw keeps them), and 3 to 5 verbatim excerpts
  voiceprofile.py compose --template T.md --out voice.md [--answer OUT.json] [--measure M.json --source LABEL]
                           [--memo-name NAME] [--date D]
        voice.md: the model's draft (answer.voice_md) when there is one, else the template with [FILL IN]
        placeholders; then the Pace line filled from the measurement and a section of verbatim excerpts
  voiceprofile.py account --out account.md [--answer OUT.json] [--date D]
        compose and account also take --keep EXISTING.md [--backup COPY.md] (M13): the existing file's hand-written
        parts are put back into the rebuilt text (merge_keep: account.md's Brand and Content strategy, voice.md's
        How I promote and the FlashFX spelling line, any section the user added, any section filled by hand that
        the rebuild only has placeholders for, the measured pace and excerpts when nothing was measured); the JSON
        output lists them in "kept"
  voiceprofile.py set-wpm --config channels/<id>/channel.json --wpm N        rewrite voice.wpm in place, keeping the layout
  voiceprofile.py is-draft FILE                                exit 0 when the file still holds a [FILL IN]

Texts from the model and from the transcript are cleaned of em dashes (errors.undash). Paths may be C:/... or
/c/... (both work).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    from errors import undash  # noqa: E402
except Exception:  # the whisper interpreter may lack nothing, but stay safe
    def undash(text: str) -> str:  # type: ignore
        return (text or "").replace("\u2014", ", ")

PLACEHOLDER = "[FILL IN"
PAUSE_SECONDS = 1.5


def winpath(path: str) -> str:
    m = re.match(r"^/([A-Za-z])/(.*)$", path or "")
    return f"{m.group(1).upper()}:/{m.group(2)}" if (m and os.name == "nt") else path


def clean(value, one_line: bool = False) -> str:
    s = "" if value is None else str(value)
    s = undash(s.replace("\r\n", "\n").replace("\r", "\n"))
    return " ".join(s.split()) if one_line else s


def read_text(path: str) -> str:
    with open(winpath(path), encoding="utf-8-sig", errors="replace") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")


def load_json(path: str, default=None):
    try:
        with open(winpath(path), encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path: str, data) -> None:
    path = winpath(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")


def save_text(path: str, content: str) -> None:
    path = winpath(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def out_json(data) -> None:
    sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------------------------------------ keep (M13)
# The user's hand-written parts survive a rebuild (BUILD_SPEC.md 2.3): build-voice-profile --force passes the
# existing file as --keep, and merge_keep() puts these back into the freshly generated text.
KEEP_SECTIONS = {
    "account": ("Brand", "Content strategy", "How I promote"),
    "voice": ("How I promote",),
}
# generated sections: never kept as "hand-written additions" (they are rebuilt every time)
GENERATED_SECTIONS = {
    "account": ("Working assumption (used until this file is filled in)", "Brand mark"),
    "voice": ("Verbatim excerpts of my real speech", "Pace"),
}
SPELLING_RE = re.compile(r"FlashFX", re.I)
SPELLING_HINT_RE = re.compile(r"\b(always|written|spell|spelled|spelling|never)\b", re.I)


def split_sections(text: str) -> tuple[str, list[list]]:
    """(the text before the first '## ' heading, [[heading, body text], ...]) for a markdown file."""
    pre, sections = [], []
    for line in text.split("\n"):
        if line.startswith("## "):
            sections.append([line[3:].strip(), []])
        elif sections:
            sections[-1][1].append(line)
        else:
            pre.append(line)
    return "\n".join(pre), [[h, "\n".join(b)] for h, b in sections]


def join_sections(pre: str, sections: list[list]) -> str:
    out = pre.rstrip("\n") + "\n"
    for heading, body in sections:
        out += f"\n## {heading}\n" + ("\n" + body.strip("\n") + "\n" if body.strip() else "")
    return out


def _norm(heading: str) -> str:
    return " ".join(heading.lower().split())


def spelling_lines(body: str) -> list[str]:
    """The hand-written FlashFX spelling lines of a section ('The brand name is always written "FlashFX".')."""
    return [l for l in body.split("\n") if SPELLING_RE.search(l) and SPELLING_HINT_RE.search(l) and PLACEHOLDER not in l]


FIELD_RE = re.compile(r"^\s*-\s+\*\*([^*]+):\*\*\s*(.*)$")


def fill_fields(new_body: str, old_body: str) -> tuple[str, int]:
    """The new section with every '- **Field:** [FILL IN...]' bullet taken from the old section when the user filled
    it there; returns (text, how many)."""
    old_fields = {}
    for line in old_body.split("\n"):
        m = FIELD_RE.match(line)
        if m and m.group(2).strip() and PLACEHOLDER not in m.group(2):
            old_fields[m.group(1).strip().lower()] = line
    out, n = [], 0
    for line in new_body.split("\n"):
        m = FIELD_RE.match(line)
        if m and PLACEHOLDER in m.group(2) and m.group(1).strip().lower() in old_fields:
            out.append(old_fields[m.group(1).strip().lower()]); n += 1
        else:
            out.append(line)
    return "\n".join(out), n


def merge_keep(old: str, new: str, kind: str) -> tuple[str, list[str]]:
    """The new text with the old file's hand-written parts put back; returns (text, what was kept).

    Kept from the old file: the sections of KEEP_SECTIONS[kind] (they replace the new section of that name, or are
    inserted after the section that preceded them in the old file), every other section the new text does not have
    at all (a section the user added; GENERATED_SECTIONS excepted), every section the user filled by hand while the
    new one is still the template's placeholders, the measured Pace line and the excerpts when the new text has
    none, and the FlashFX spelling line (in its own section, after the line it followed)."""
    if not old.strip():
        return new, []
    _, old_secs = split_sections(old)
    pre, new_secs = split_sections(new)
    keep_names = {_norm(h) for h in KEEP_SECTIONS.get(kind, ())}
    generated = {_norm(h) for h in GENERATED_SECTIONS.get(kind, ())}
    kept: list[str] = []
    new_index = {_norm(h): i for i, (h, _) in enumerate(new_secs)}
    previous = None
    for heading, body in old_secs:
        key = _norm(heading)
        if not body.strip():
            previous = key
            continue
        i = new_index.get(key)
        if key in keep_names or (i is None and key not in generated):
            if i is None:
                at = new_index.get(previous, len(new_secs) - 1) + 1 if previous is not None else len(new_secs)
                new_secs.insert(at, [heading, body])
                new_index = {_norm(h): j for j, (h, _) in enumerate(new_secs)}
            else:
                new_secs[i][1] = body
            kept.append(heading)
        elif i is not None and PLACEHOLDER in new_secs[i][1] and \
                " ".join(body.split()) != " ".join(new_secs[i][1].split()):
            if body.count(PLACEHOLDER) < new_secs[i][1].count(PLACEHOLDER):
                new_secs[i][1] = body  # filled by hand (more of it than the rebuild could fill)
                kept.append(heading)
            else:
                merged, n = fill_fields(new_secs[i][1], body)
                if n:
                    new_secs[i][1] = merged
                    kept.append(f"{heading} ({n} {'field' if n == 1 else 'fields'})")
        elif i is not None and key in generated and PLACEHOLDER not in body and \
                (PLACEHOLDER in new_secs[i][1] or not new_secs[i][1].strip()):
            new_secs[i][1] = body
            kept.append(heading)
        previous = key
    if kind == "voice":
        # the measured Pace line, when the rebuild measured nothing
        old_pace = re.search(r"^\s*-\s+\*\*Pace:\*\*(.*)$", old, re.MULTILINE)
        for sec in new_secs:
            m = re.search(r"^\s*-\s+\*\*Pace:\*\*(.*)$", sec[1], re.MULTILINE)
            if m and PLACEHOLDER in m.group(1) and old_pace and PLACEHOLDER not in old_pace.group(1):
                sec[1] = sec[1].replace(m.group(0), old_pace.group(0), 1)
                kept.append("Pace line")
        # the excerpts of an earlier measurement
        if "verbatim excerpts of my real speech" not in {_norm(h) for h, _ in new_secs}:
            for heading, body in old_secs:
                if _norm(heading) == "verbatim excerpts of my real speech" and body.strip():
                    new_secs.append([heading, body])
                    kept.append(heading)
    # the FlashFX spelling line, wherever the user put it
    all_new = "\n".join(b for _, b in new_secs)
    for heading, body in old_secs:
        for line in spelling_lines(body):
            if line.strip() in all_new:
                continue
            target = next((s for s in new_secs if _norm(s[0]) == _norm(heading)), None)
            if target is None:
                target = new_secs[-1] if new_secs else None
            if target is None:
                new_secs.append([heading, line]); kept.append("FlashFX spelling line"); continue
            old_lines = body.split("\n")
            before = old_lines[old_lines.index(line) - 1].strip() if old_lines.index(line) > 0 else ""
            tl = target[1].split("\n")
            pos = next((j + 1 for j, l in enumerate(tl) if before and l.strip() == before), None)
            if pos is None:
                # after the bullet whose field name matched the old preceding line ("- **Words I actually use:**")
                field = re.match(r"^\s*-\s+\*\*([^*]+):\*\*", before)
                pos = next((j + 1 for j, l in enumerate(tl) if field and l.lstrip().startswith(f"- **{field.group(1)}:**")), None)
            if pos is None:
                pos = len(tl)
                while pos > 0 and not tl[pos - 1].strip():
                    pos -= 1
            tl.insert(pos, line)
            target[1] = "\n".join(tl)
            all_new = "\n".join(b for _, b in new_secs)
            kept.append("FlashFX spelling line")
    return join_sections(pre, new_secs), kept


def apply_keep(args, text: str, kind: str) -> tuple[str, list[str]]:
    """merge_keep against args.keep (the existing file) when given; a copy of that file goes next to the work files."""
    path = getattr(args, "keep", "") or ""
    if not path or not os.path.isfile(winpath(path)):
        return text, []
    old = read_text(path)
    if getattr(args, "backup", ""):
        save_text(args.backup, old)
    return merge_keep(old, text, kind)


# ------------------------------------------------------------------------------------------------ transcribe
def cmd_transcribe(args) -> int:
    from faster_whisper import WhisperModel  # the whisper interpreter only

    audio = winpath(args.audio)
    if not os.path.isfile(audio):
        print(f"voiceprofile.py transcribe: {args.audio} does not exist", file=sys.stderr)
        return 2
    attempts = [(args.model, True), ("small", True), (args.model, False)]
    model = None
    used = ""
    last_exc = None
    for name, local_only in attempts:
        try:
            print(f"loading faster-whisper {name} on CPU (int8{', local cache only' if local_only else ', download allowed'})...",
                  flush=True)
            model = WhisperModel(name, device="cpu", compute_type="int8", local_files_only=local_only)
            used = name
            break
        except Exception as exc:  # a model not in the cache, no network
            last_exc = exc
            continue
    if model is None:
        print(f"voiceprofile.py transcribe: no whisper model could be loaded: {last_exc}", file=sys.stderr)
        return 3
    t0 = time.time()
    kwargs = {"word_timestamps": True}
    if args.language:
        kwargs["language"] = args.language
    segments, info = model.transcribe(audio, **kwargs)
    segs = []
    all_words = []
    for seg in segments:
        words = []
        for w in (seg.words or []):
            item = {"word": clean(w.word, one_line=True), "start": round(float(w.start), 3), "end": round(float(w.end), 3)}
            words.append(item)
            all_words.append(item)
        segs.append({"start": round(float(seg.start), 3), "end": round(float(seg.end), 3),
                     "text": clean(seg.text, one_line=True), "words": words})
        print(f"  {seg.start:7.1f}s  {clean(seg.text, one_line=True)}", flush=True)
    data = {
        "audio": args.audio.replace("\\", "/"), "model": used, "language": getattr(info, "language", args.language or ""),
        "duration": round(float(getattr(info, "duration", 0.0) or 0.0), 3), "took_seconds": round(time.time() - t0, 1),
        "segments": segs, "words": all_words,
    }
    save_json(args.out, data)
    print(f"transcribed {len(all_words)} words in {data['took_seconds']}s -> {args.out}", flush=True)
    return 0


# ------------------------------------------------------------------------------------------------ measure
def measure(data: dict, max_excerpts: int = 5) -> dict:
    words = data.get("words") or []
    segs = data.get("segments") or []
    n = len(words)
    if n < 2:
        return {"words": n, "speech_seconds": 0.0, "gross_seconds": 0.0, "wpm": 0, "wpm_raw": 0, "excerpts": [],
                "pauses_removed_seconds": 0.0}
    start = words[0]["start"]
    end = words[-1]["end"]
    gross = max(0.0, end - start)
    pauses = 0.0
    for a, b in zip(words, words[1:]):
        gap = b["start"] - a["end"]
        if gap > PAUSE_SECONDS:
            pauses += gap - PAUSE_SECONDS  # a long pause counts as a normal one
    speech = max(0.1, gross - pauses)
    wpm = int(round(n / (speech / 60.0)))
    wpm_raw = int(round(n / (gross / 60.0))) if gross > 0 else wpm
    # excerpts: whole segments, 10 to 45 words, spread over the recording, verbatim
    candidates = []
    for s in segs:
        text = s.get("text", "").strip()
        k = len(text.split())
        if 10 <= k <= 45:
            candidates.append({"start": s["start"], "end": s["end"], "text": text, "words": k})
    if not candidates:  # short segments: join neighbours until 10 words
        buf, t0 = [], None
        for s in segs:
            if t0 is None:
                t0 = s["start"]
            buf.append(s.get("text", "").strip())
            k = len(" ".join(buf).split())
            if k >= 10:
                candidates.append({"start": t0, "end": s["end"], "text": " ".join(buf), "words": k})
                buf, t0 = [], None
    excerpts = []
    if candidates:
        want = min(max_excerpts, max(3, min(5, len(candidates))))
        if len(candidates) <= want:
            excerpts = candidates
        else:
            step = len(candidates) / float(want)
            picked = sorted({int(i * step) for i in range(want)})
            excerpts = [candidates[i] for i in picked]
    return {"words": n, "speech_seconds": round(speech, 1), "gross_seconds": round(gross, 1), "wpm": wpm,
            "wpm_raw": wpm_raw, "pauses_removed_seconds": round(pauses, 1), "excerpts": excerpts}


def cmd_measure(args) -> int:
    data = load_json(args.words, {})
    m = measure(data, args.max_excerpts)
    m["audio"] = data.get("audio", "")
    m["model"] = data.get("model", "")
    m["duration"] = data.get("duration", 0)
    if args.out:
        save_json(args.out, m)
    out_json(m)
    return 0


# ------------------------------------------------------------------------------------------------ compose
def template_to_draft(template: str) -> str:
    """The vendor's template (headings and "- **Field:** (hint)" bullets) with a [FILL IN] after every field."""
    raw_lines = template.replace("`{{your number}}`", "a placeholder").split("\n")
    # a bullet's hint may wrap onto indented continuation lines: join them first
    lines: list[str] = []
    for line in raw_lines:
        if lines and line.startswith("  ") and line.strip() and re.match(r"^\s*-\s+\*\*", lines[-1]) \
                and not line.lstrip().startswith("-"):
            lines[-1] = lines[-1].rstrip() + " " + line.strip()
        else:
            lines.append(line)
    out = []
    skip_intro = True
    for line in lines:
        if skip_intro:
            if line.startswith("## "):
                skip_intro = False
            else:
                continue  # the vendor's own intro (copy this to ~/.claude/...) is replaced by ours
        m = re.match(r"^(\s*-\s+\*\*[^*]+:\*\*)\s*(.*)$", line)
        if m:
            hint = " ".join(m.group(2).split())
            hint = hint[1:-1] if hint.startswith("(") and hint.endswith(")") else hint
            out.append(f"{m.group(1)} [FILL IN{': ' + hint if hint else ''}]")
            continue
        m = re.match(r"^(\d+)\.\s*$", line)
        if m:
            out.append(f"{m.group(1)}. [FILL IN: a position I hold that some of my audience does not]")
            continue
        if line.strip() == "-":
            out.append("- [FILL IN: a real number, outcome or story I am happy to put my name on]")
            continue
        out.append(line)
    return "\n".join(out).strip() + "\n"


def fill_pace(text: str, pace_line: str) -> str:
    """Replace the Pace bullet (template or draft) with the measured line, or append it to 'What I sound like'."""
    pattern = re.compile(r"^(\s*-\s+\*\*Pace:\*\*).*$", re.MULTILINE)
    if pattern.search(text):
        # the template's Pace bullet may continue on wrapped lines in parentheses: drop them
        lines = text.split("\n")
        out = []
        i = 0
        while i < len(lines):
            if re.match(r"^\s*-\s+\*\*Pace:\*\*", lines[i]):
                out.append(f"- **Pace:** {pace_line}")
                i += 1
                while i < len(lines) and lines[i].startswith("  ") and not lines[i].lstrip().startswith("-"):
                    i += 1
                continue
            out.append(lines[i])
            i += 1
        return "\n".join(out)
    marker = "## What I sound like"
    if marker in text:
        return text.replace(marker, f"{marker}\n\n- **Pace:** {pace_line}", 1)
    return text.rstrip("\n") + f"\n\n## Pace\n\n- **Pace:** {pace_line}\n"


def cmd_compose(args) -> int:
    date = args.date or time.strftime("%Y-%m-%d")
    answer = load_json(args.answer, {}) if args.answer else {}
    body = clean(answer.get("voice_md", "")) .strip() if isinstance(answer, dict) else ""
    measured = load_json(args.measure, None) if args.measure else None
    source = args.source or ""
    if body:
        head = (f"# voice.md: how I sound (the pipeline's voice profile)\n\n"
                f"Built {date} by pipeline/bin/build-voice-profile from {args.memo_name or 'library/voice/memo.*'}, "
                f"transcribed with faster-whisper on this PC, on the instagram-agent-skill template "
                f"(pipeline/vendor/ig-agent-skill/templates/voice.md). The words are mine as I said them; only real "
                f"errors were fixed. A placeholder in square brackets marks what the memo did not say: edit it by hand, "
                f"or re-record and run `bash pipeline/bin/build-voice-profile --force`. Models that read this file "
                f"treat such a placeholder as unknown and never invent it.\n\n")
        body = re.sub(r"^#\s+voice\.md\s*$", "", body, flags=re.MULTILINE).strip()
        text = head + body + "\n"
    else:
        template = read_text(args.template) if args.template else ""
        draft = template_to_draft(template) if template else "## Who I am\n\n- **Name:** [FILL IN]\n"
        head = (f"# voice.md: how I sound (the pipeline's voice profile)\n\n"
                f"DRAFT built {date} by pipeline/bin/build-voice-profile from the instagram-agent-skill template "
                f"(pipeline/vendor/ig-agent-skill/templates/voice.md). No library/voice/memo.* was found, so every "
                f"[FILL IN] is a placeholder. Two ways to fill it: edit this file by hand (plain English, the way you "
                f"talk; keep your own phrasing), or record a 5 to 10 minute voice memo about who you are, who you "
                f"talk to, what you believe and what you sell, save it as library/voice/memo.wav (or .m4a, .mp3) and "
                f"run `bash pipeline/bin/build-voice-profile --force`. Models that read this file treat a [FILL IN] as "
                f"unknown and never invent it.\n\n")
        text = head + draft
    if measured and measured.get("words", 0) >= 20:
        pace = (f"{measured['wpm']} words per minute, measured from {source or measured.get('audio', 'a recording')}: "
                f"{measured['words']} words in {measured['speech_seconds']} s of speech (pauses over {PAUSE_SECONDS:g} s "
                f"removed; {measured['wpm_raw']} with every pause). beats.py and the hooks use this number.")
        text = fill_pace(text, pace)
        ex = measured.get("excerpts") or []
        if ex:
            text = text.rstrip("\n") + "\n\n## Verbatim excerpts of my real speech\n\n"
            text += (f"Transcribed with faster-whisper ({measured.get('model', 'small')}, CPU) from {source or measured.get('audio', 'a recording')} "
                     f"on {date}. Word for word, my own phrasing kept; the script and judge models use these as the "
                     f"reference for how I actually talk.\n\n")
            for i, e in enumerate(ex, 1):
                text += f"{i}. \"{clean(e['text'], one_line=True)}\" ({e['start']:.0f}s to {e['end']:.0f}s)\n"
    else:
        text = fill_pace(text, "[FILL IN: words per minute, measured; until then config.json voice.wpm (150) is used]")
    text, kept = apply_keep(args, text, "voice")
    save_text(args.out, text.rstrip("\n") + "\n")
    out_json({"out": args.out, "draft": is_draft_text(text), "from_model": bool(body),
              "wpm": (measured or {}).get("wpm", 0), "excerpts": len((measured or {}).get("excerpts", [])),
              "kept": kept})
    return 0


def cmd_account(args) -> int:
    date = args.date or time.strftime("%Y-%m-%d")
    answer = load_json(args.answer, {}) if args.answer else {}
    body = clean(answer.get("account_md", "")).strip() if isinstance(answer, dict) else ""
    if body:
        head = (f"# account.md: who this account is for\n\n"
                f"Built {date} by pipeline/bin/build-voice-profile from the voice memo. A placeholder in square brackets "
                f"marks what the memo did not say; edit this file by hand whenever you like.\n\n")
        body = re.sub(r"^#\s+account\.md.*$", "", body, flags=re.MULTILINE).strip()
        text = head + body + "\n"
    else:
        text = (
            f"# account.md: who this account is for\n\n"
            f"DRAFT with placeholders, built {date} by pipeline/bin/build-voice-profile. The research, expansion and "
            f"hooks stages read this file to aim every reel. Until the placeholders are filled they also keep the "
            f"working assumption below, and every export carries a NEEDS REVIEW flag. Replace each [FILL IN] by "
            f"hand (plain sentences), then the flag goes away.\n\n"
            f"## Working assumption (used until this file is filled in)\n\n"
            f"The reels are for people who build and publish with AI and developer tools (Claude Code, agents, "
            f"skills, automation) and want practical, verified information they can use the same day.\n\n"
            f"## Who the account is for\n\n"
            f"[FILL IN: the audience in one or two sentences, as specific as \"solo developers who ship client sites "
            f"with AI tools\", not \"creatives\"]\n\n"
            f"## The audience's problems\n\n"
            f"- [FILL IN: a problem they say in their own words]\n"
            f"- [FILL IN]\n"
            f"- [FILL IN]\n\n"
            f"## Topics in\n\n"
            f"- [FILL IN: topics every reel may cover]\n\n"
            f"## Topics out\n\n"
            f"- [FILL IN: topics the account never covers]\n\n"
            f"## What I sell\n\n"
            f"[FILL IN: the product, service or offer, and what the comment keywords lead to]\n\n"
            f"## Brand\n\n"
            f"- Brand kit: library/brand/ (rules in library/brand/BRAND.md, data in library/brand/brand.json)\n"
            f"- Name: always \"FlashFX\"\n"
            f"- Where the brand appears in reels: styles/paper-cards/tweaks.md, section \"Branding (FlashFX account)\"\n"
        )
    text, kept = apply_keep(args, text, "account")
    save_text(args.out, text.rstrip("\n") + "\n")
    out_json({"out": args.out, "draft": is_draft_text(text), "from_model": bool(body), "kept": kept})
    return 0


def cmd_set_wpm(args) -> int:
    path = winpath(args.config)
    raw = read_text(path)
    new, n = re.subn(r'("wpm"\s*:\s*)\d+', lambda m: m.group(1) + str(int(args.wpm)), raw, count=1)
    if n == 0:
        print("voiceprofile.py set-wpm: no \"wpm\" key in the file", file=sys.stderr)
        return 2
    if new != raw:
        save_text(path, new)
    out_json({"config": args.config, "wpm": int(args.wpm), "changed": new != raw})
    return 0


def is_draft_text(text: str) -> bool:
    """A placeholder in the body counts; the intro paragraph (which explains the placeholders) does not."""
    body = text.split("\n## ", 1)[1] if "\n## " in text else text
    return PLACEHOLDER in body


def cmd_is_draft(args) -> int:
    try:
        return 0 if is_draft_text(read_text(args.file)) else 1
    except OSError:
        return 2


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("transcribe"); sp.add_argument("audio"); sp.add_argument("--out", required=True)
    sp.add_argument("--model", default="small.en"); sp.add_argument("--language", default="en"); sp.set_defaults(func=cmd_transcribe)
    sp = sub.add_parser("measure"); sp.add_argument("--words", required=True); sp.add_argument("--out")
    sp.add_argument("--max-excerpts", type=int, default=5); sp.set_defaults(func=cmd_measure)
    sp = sub.add_parser("compose"); sp.add_argument("--template"); sp.add_argument("--out", required=True)
    sp.add_argument("--answer"); sp.add_argument("--measure"); sp.add_argument("--source", default="")
    sp.add_argument("--memo-name", default=""); sp.add_argument("--date", default="")
    sp.add_argument("--keep", default=""); sp.add_argument("--backup", default=""); sp.set_defaults(func=cmd_compose)
    sp = sub.add_parser("account"); sp.add_argument("--out", required=True); sp.add_argument("--answer")
    sp.add_argument("--date", default=""); sp.add_argument("--keep", default=""); sp.add_argument("--backup", default="")
    sp.set_defaults(func=cmd_account)
    sp = sub.add_parser("set-wpm"); sp.add_argument("--config", required=True); sp.add_argument("--wpm", type=int, required=True)
    sp.set_defaults(func=cmd_set_wpm)
    sp = sub.add_parser("is-draft"); sp.add_argument("file"); sp.set_defaults(func=cmd_is_draft)
    args = p.parse_args(argv)
    try:
        return args.func(args)
    except OSError as exc:
        print(f"voiceprofile.py {args.cmd}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
