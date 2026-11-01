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
  voiceprofile.py set-wpm --config config.json --wpm N        rewrite voice.wpm in place, keeping the layout
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
    save_text(args.out, text.rstrip("\n") + "\n")
    out_json({"out": args.out, "draft": is_draft_text(text), "from_model": bool(body),
              "wpm": (measured or {}).get("wpm", 0), "excerpts": len((measured or {}).get("excerpts", []))})
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
            f"## Brand mark\n\n"
            f"- file: [FILL IN: path to the logo or mark file, for example library/profile/brand-mark.png]\n"
        )
    save_text(args.out, text)
    out_json({"out": args.out, "draft": is_draft_text(text), "from_model": bool(body)})
    return 0


def cmd_set_wpm(args) -> int:
    path = winpath(args.config)
    raw = read_text(path)
    new, n = re.subn(r'("wpm"\s*:\s*)\d+', lambda m: m.group(1) + str(int(args.wpm)), raw, count=1)
    if n == 0:
        print("voiceprofile.py set-wpm: no \"wpm\" key in config.json", file=sys.stderr)
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
    sp.add_argument("--memo-name", default=""); sp.add_argument("--date", default=""); sp.set_defaults(func=cmd_compose)
    sp = sub.add_parser("account"); sp.add_argument("--out", required=True); sp.add_argument("--answer")
    sp.add_argument("--date", default=""); sp.set_defaults(func=cmd_account)
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
