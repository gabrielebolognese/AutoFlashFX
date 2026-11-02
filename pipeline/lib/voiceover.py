#!/usr/bin/env python
"""voiceover.py: the voiceover stage (S8, BUILD_SPEC.md section 5) and its helpers. No model calls of its own.

Driven by pipeline/stages/08-voiceover/run.sh. Runs under the project's `python` (3.13, numpy); the engine and the
transcriber run in their own interpreters through the workers in pipeline/lib/tts/ (kokoro_worker.py under the
interpreter of library/voice/engine.txt, whisper_worker.py under the interpreter that has faster-whisper).

  voiceover.py engine [--brief] [--json]      the effective voice config: library/voice/engine.txt (REELS_ENGINE_FILE
                                              overrides the path) with the defaults of BUILD_SPEC.md 2.5 for missing
                                              lines, or the defaults alone when the file is missing or names an
                                              engine other than kokoro (this pipeline voices every reel with kokoro
                                              af_bella; nothing else is ever installed or used)
  voiceover.py engine-check                   the preflight check: the voice interpreter exists and imports kokoro,
                                              one interpreter imports faster_whisper. Problems on stdout, "WARN: ..."
                                              lines for the notes, exit 1 on a hard problem
  voiceover.py run RUN_DIR --stage-dir DIR --s7 RUN_SH   the stage: pronunciations, beat by beat generation with
                                              silence tightening, the transcription of every line, the word error
                                              rate ladder (respelling, one rewrite through S7, flag or block), the
                                              15 percent overrun check, hook 2, the assembly, loudness, words.json.
                                              Relay lines on stdout for run.sh: "@@ACTIVITY text", "@@SAY TAG text",
                                              "@@FLAG text", "@@ERROR text". Exit 0 done, 20 block (the reason in
                                              voiceover.json verdict), 1 a code error
  voiceover.py wer --ref TEXT --hyp TEXT      the word error rate of two texts (JSON: wer_pct, errors, misheard, heard)
  voiceover.py pronounce --text TEXT [--file pronunciations.txt] [--respell WORD=SAY ...]   the TTS text
  voiceover.py respell WORD                   the automatic respelling of one word, or "" when no rule applies
  voiceover.py silences --wav FILE [--threshold-db -40] [--min-s 0.0]   the silent runs of a wav (JSON)
  voiceover.py energy --wav FILE --from-ms A --to-ms B       the RMS level in dBFS of a window
  voiceover.py measure --wav FILE             integrated loudness and true peak through ffmpeg (JSON)

Every text that comes from outside (a transcription, a worker's message) is cleaned of em dashes (errors.undash).
Paths may be C:/... or /c/... (both work).
"""
from __future__ import annotations

import argparse
import difflib
import json
import math
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from errors import undash  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", "..")).replace("\\", "/")
STAGE = "08-voiceover"
ENGINE_DEFAULTS = {
    "engine": "kokoro",
    "python": "C:/Users/there/venvs/kokoro/Scripts/python.exe",
    "voice": "af_bella",
    "lang": "a",
    "speed": 1.0,
    "silence_threshold_db": -40.0,
    "min_pause_s": 0.3,
    "keep_pause_s": 0.1,
    "breath_after_hook_s": 1.0,
}
ENGINE_RANGES = {
    "speed": (0.5, 2.0),
    "silence_threshold_db": (-80.0, -10.0),
    "min_pause_s": (0.05, 2.0),
    "keep_pause_s": (0.0, 1.0),
    "breath_after_hook_s": (0.0, 3.0),
}
MARKUP_RE = re.compile(r"\[([^\]]+)\]\(/[^)]*/\)")  # Kokoro's inline phonemes: [word](/phonemes/)
ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
        "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
ORDINALS = {"1st": "first", "2nd": "second", "3rd": "third", "4th": "fourth", "5th": "fifth", "6th": "sixth",
            "7th": "seventh", "8th": "eighth", "9th": "ninth", "10th": "tenth"}
ALIASES = {"ok": "okay", "vs": "versus", "etc": "etcetera", "mr": "mister", "dr": "doctor"}
# Spellings the transcriber chooses freely (British forms, homophones): the voice said the same sounds, so both
# sides are mapped to one form before the comparison (DECISIONS.md, M7).
VARIANTS = {
    "grey": "gray", "colour": "color", "colours": "colors", "favourite": "favorite", "centre": "center", "theatre": "theater",
    "organise": "organize", "organised": "organized", "realise": "realize", "realised": "realized", "analyse": "analyze",
    "catalogue": "catalog", "dialogue": "dialog", "licence": "license", "defence": "defense", "programme": "program",
    "cancelled": "canceled", "travelling": "traveling", "modelling": "modeling", "labelled": "labeled", "behaviour": "behavior",
    "honour": "honor", "neighbour": "neighbor", "flavour": "flavor", "humour": "humor", "metre": "meter", "litre": "liter",
    "fibre": "fiber", "cheque": "check", "tyre": "tire", "aluminium": "aluminum", "jewellery": "jewelry", "ageing": "aging",
    "judgement": "judgment", "practise": "practice", "learnt": "learned", "spelt": "spelled", "dreamt": "dreamed", "burnt": "burned",
    "optimise": "optimize", "optimised": "optimized", "customise": "customize", "customised": "customized", "summarise": "summarize",
    "their": "there", "theyre": "there", "youre": "your", "whos": "whose", "alright": "allright",
}


# ------------------------------------------------------------------------------------------------ small helpers
def winpath(path: str) -> str:
    m = re.match(r"^/([A-Za-z])/(.*)$", path or "")
    return f"{m.group(1).upper()}:/{m.group(2)}" if (m and os.name == "nt") else (path or "")


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


def out_json(data) -> None:
    sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def clean(value) -> str:
    return " ".join(undash("" if value is None else str(value)).split())


def rel(path: str, root: str) -> str:
    p, r = winpath(path).replace("\\", "/"), winpath(root).replace("\\", "/").rstrip("/") + "/"
    return p[len(r):] if p.lower().startswith(r.lower()) else p


def n_words(text: str) -> int:
    return len([t for t in strip_markup(text).split() if re.search(r"[A-Za-z0-9]", t)])


def strip_markup(text: str) -> str:
    return MARKUP_RE.sub(lambda m: m.group(1), text or "")


def relay(kind: str, text: str) -> None:
    sys.stdout.write(f"@@{kind} {clean(text)}\n")
    sys.stdout.flush()


def log(text: str) -> None:
    sys.stdout.write(undash(text) + "\n")
    sys.stdout.flush()


def say(tag: str, text: str) -> None:
    relay("SAY", f"{tag} {text}")


def fmt_s(x: float) -> str:
    return f"{x:.1f}"


# ------------------------------------------------------------------------------------------------ context
class Ctx:
    def __init__(self, config_path: str = "", root: str = "", repo: str = ""):
        self.repo = (repo or os.environ.get("REELS_REPO") or REPO).replace("\\", "/")
        self.root = (root or os.environ.get("REELS_ROOT") or self.repo).replace("\\", "/")
        cfg = config_path or os.environ.get("REELS_CONFIG") or ""
        if not cfg:
            cfg = f"{self.root}/config.json" if os.path.isfile(winpath(f"{self.root}/config.json")) else f"{self.repo}/config.json"
        self.config_path = cfg
        self.config = load_json(cfg, {}) or {}

    def cfg(self, key: str, default=None):
        cur = self.config
        for part in key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return default
        return cur


# ------------------------------------------------------------------------------------------------ engine.txt
def engine_file(ctx: Ctx) -> str:
    env = os.environ.get("REELS_ENGINE_FILE")
    if env:
        return winpath(env).replace("\\", "/")
    return f"{ctx.root}/{ctx.cfg('paths.voice_dir', 'library/voice')}/engine.txt"


def parse_engine_file(path: str) -> dict:
    raw: dict = {}
    for line in read_text(path).split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip().lower(), value.strip().strip('"').strip("'")
        if key:
            raw[key] = value
    return raw


def engine_config(ctx: Ctx) -> dict:
    """The effective engine config: {"engine": {...}, "file", "exists", "status", "notes", "problems", "raw"}."""
    path = engine_file(ctx)
    default_py = str(ctx.cfg("paths.kokoro_python", ENGINE_DEFAULTS["python"]))
    eff = dict(ENGINE_DEFAULTS)
    eff["python"] = default_py
    info = {"file": path, "exists": os.path.isfile(winpath(path)), "status": "defaults", "notes": [], "problems": [], "raw": {}}
    shown = rel(path, ctx.root)
    defaults_text = f"engine kokoro, voice af_bella, interpreter {default_py}, speed 1.0, pauses of 0.3 s or more cut to 0.1 s below -40 dB, 1.0 s breath after the hook"
    if not info["exists"]:
        info["notes"].append(f"{shown} is missing: the kokoro defaults of BUILD_SPEC.md 2.5 are used ({defaults_text})")
    else:
        raw = parse_engine_file(path)
        info["raw"] = raw
        engine = (raw.get("engine") or "kokoro").lower()
        if engine != "kokoro":
            info["status"] = "defaults-unsupported"
            info["notes"].append(f"{shown} names engine '{engine}'; this pipeline voices every reel with kokoro af_bella "
                                 f"(BUILD_SPEC.md 2.5) and uses the defaults ({defaults_text}) until the file is rewritten with the kokoro block")
        else:
            missing = [k for k in ENGINE_DEFAULTS if k not in raw]
            for key, value in raw.items():
                if key in ENGINE_DEFAULTS:
                    eff[key] = value
            info["status"] = "file" if not missing else "file+defaults"
            if missing:
                info["notes"].append(f"{shown} has no line for {', '.join(missing)}: the defaults of BUILD_SPEC.md 2.5 apply to them")
    for key, (lo, hi) in ENGINE_RANGES.items():
        try:
            eff[key] = float(eff[key])
        except (TypeError, ValueError):
            info["problems"].append(f"{shown}: {key} = {eff[key]!r} is not a number")
            eff[key] = ENGINE_DEFAULTS[key]
            continue
        if not (lo <= eff[key] <= hi):
            info["problems"].append(f"{shown}: {key} = {eff[key]} is outside {lo} to {hi}")
    if eff["keep_pause_s"] > eff["min_pause_s"]:
        info["problems"].append(f"{shown}: keep_pause_s ({eff['keep_pause_s']}) is longer than min_pause_s ({eff['min_pause_s']})")
    eff["engine"] = "kokoro"
    eff["python"] = str(eff["python"]).replace("\\", "/").strip()
    eff["voice"] = str(eff["voice"]).strip() or "af_bella"
    eff["lang"] = str(eff["lang"]).strip() or "a"
    if not eff["python"]:
        info["problems"].append(f"{shown}: the python line is empty")
    info["engine"] = eff
    return info


def bash_exe() -> str:
    """Git's bash, never the WSL launcher: from a Windows Python a bare `bash` resolves to System32\\bash.exe
    (which answers "Class not registered" when WSL is absent). run.sh exports REELS_BASH (its own $BASH)."""
    env = os.environ.get("REELS_BASH", "")
    if env and exe_exists(env):
        return winpath(env)
    for cand in ("C:/Program Files/Git/usr/bin/bash.exe", "C:/Program Files/Git/bin/bash.exe", "C:/Program Files (x86)/Git/usr/bin/bash.exe"):
        if os.path.isfile(cand):
            return cand
    return "bash"


def syllables(word: str) -> int:
    """A syllable count good enough for timing: vowel groups, a silent final e dropped, at least one."""
    w = re.sub(r"[^a-z]", "", strip_markup(word).lower())
    if not w:
        return 1 if re.search(r"\d", word) else 0
    groups = re.findall(r"[aeiouy]+", w)
    n = len(groups)
    if w.endswith("e") and n > 1 and not w.endswith(("ee", "ye", "oe")) and not re.search(r"[^aeiouy]le$", w):
        n -= 1  # a silent final e (file, same, convergence), not table or little
    if w.endswith("ed") and not w.endswith(("ted", "ded")) and n > 1 and re.search(r"[^aeiouy]ed$", w):
        n -= 1
    return max(1, n)


def text_syllables(text: str) -> int:
    return sum(syllables(t) for t in strip_markup(text).split() if re.search(r"[A-Za-z0-9]", t))


def exe_exists(path: str) -> bool:
    exe = winpath(path)
    if "/" in exe or "\\" in exe:
        return os.path.isfile(exe)
    return shutil.which(exe) is not None


def worker_env() -> dict:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("REELS_SAY_FD", None)  # a child's say lines go to our stdout (the stage log), the runner's fd is not inherited
    return env


def import_ok(py: str, module: str, timeout: int = 180) -> tuple[bool, str]:
    if not exe_exists(py):
        return False, f"{py} does not exist"
    try:
        r = subprocess.run([winpath(py), "-c", f"import {module}"], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=worker_env(), stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return False, f"{py}: 'import {module}' did not finish in {timeout} s"
    except OSError as exc:
        return False, f"{py}: cannot run it ({exc})"
    if r.returncode != 0:
        lines = [ln for ln in (r.stderr or r.stdout or "").strip().splitlines() if ln.strip()]
        return False, f"{py} cannot import {module}" + (f" ({clean(lines[-1])[:160]})" if lines else "")
    return True, ""


def tts_python(ctx: Ctx, info: dict) -> str:
    return (os.environ.get("REELS_TTS_PYTHON") or info["engine"]["python"]).replace("\\", "/")


def whisper_candidates(ctx: Ctx, tts_py: str) -> list[str]:
    venv = str(ctx.cfg("paths.venv_python", ".venv-tts/Scripts/python.exe") or "")
    if venv and not re.match(r"^([A-Za-z]:|/)", venv):
        venv = f"{ctx.repo}/{venv}"
    out: list[str] = []
    for p in [os.environ.get("REELS_WHISPER_PYTHON", ""), str(ctx.cfg("tts.whisper_python", "") or ""), tts_py, venv, "python"]:
        p = (p or "").replace("\\", "/").strip()
        if p and p not in out:
            out.append(p)
    return out


def resolve_whisper(ctx: Ctx, tts_py: str) -> tuple[str, list[str]]:
    """The first candidate interpreter that imports faster_whisper, and the reasons the others failed."""
    if os.environ.get("REELS_WHISPER_WORKER"):
        return (os.environ.get("REELS_WHISPER_PYTHON") or "python"), []
    tried: list[str] = []
    for cand in whisper_candidates(ctx, tts_py):
        if not exe_exists(cand):
            tried.append(f"{cand}: does not exist")
            continue
        ok, why = import_ok(cand, "faster_whisper")
        if ok:
            return cand, tried
        tried.append(why)
    return "", tried


def cmd_engine(args) -> int:
    ctx = Ctx(args.config, args.root, args.repo)
    info = engine_config(ctx)
    if args.brief:
        sys.stdout.write(f"{info['engine']['engine']} {info['engine']['voice']}\n")
        return 0
    out_json(info)
    return 0


def cmd_engine_check(args) -> int:
    ctx = Ctx(args.config, args.root, args.repo)
    info = engine_config(ctx)
    problems: list[str] = list(info["problems"])
    for note in info["notes"]:
        sys.stdout.write(f"WARN: {note}\n")
    tts_py = tts_python(ctx, info)
    if os.environ.get("REELS_TTS_WORKER"):
        sys.stdout.write(f"WARN: REELS_TTS_WORKER is set ({os.environ['REELS_TTS_WORKER']}): a fake voice engine is in use, the kokoro import check is skipped\n")
    else:
        ok, why = import_ok(tts_py, "kokoro")
        if not ok:
            problems.append(f"the voice interpreter cannot be used: {why}")
    whisper_py, tried = resolve_whisper(ctx, tts_py)
    if not whisper_py:
        problems.append("no interpreter imports faster_whisper (tried: " + "; ".join(tried) + ")")
    for p in problems:
        sys.stdout.write(p + "\n")
    if problems:
        return 1
    sys.stdout.write(f"ok: {info['engine']['engine']} {info['engine']['voice']} through {tts_py}; faster-whisper through {whisper_py}\n")
    return 0


# ------------------------------------------------------------------------------------------------ pronunciations
def read_pronunciations(path: str) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    if not path or not os.path.isfile(winpath(path)):
        return items
    for line in read_text(path).split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        word, _, say_text = line.partition("=")
        word, say_text = clean(word), clean(say_text)
        if word and say_text:
            items.append((word, say_text))
    items.sort(key=lambda p: -len(p[0]))
    return items


def _sub_outside_markup(text: str, pattern: re.Pattern, repl) -> tuple[str, int]:
    """Apply a substitution to the parts of the text that are not inside [word](/phonemes/) spans."""
    out: list[str] = []
    n = 0
    pos = 0
    for m in MARKUP_RE.finditer(text):
        piece, k = pattern.subn(repl, text[pos:m.start()])
        out.append(piece)
        n += k
        out.append(m.group(0))
        pos = m.end()
    piece, k = pattern.subn(repl, text[pos:])
    out.append(piece)
    return "".join(out), n + k


def tts_text(spoken: str, entries: list[tuple[str, str]], respellings: dict | None = None) -> tuple[str, list[str]]:
    """The text sent to the engine: pronunciations.txt applied first (a respelling, or inline phonemes when the
    value is written between slashes), then this reel's own respellings. Returns (text, applied)."""
    text = clean(spoken)
    applied: list[str] = []
    for word, say_text in entries:
        pattern = re.compile(r"(?<![A-Za-z0-9])" + re.escape(word) + r"(?![A-Za-z0-9])", re.I)
        if say_text.startswith("/") and say_text.endswith("/") and len(say_text) > 2:
            text, k = _sub_outside_markup(text, pattern, lambda m, s=say_text: f"[{m.group(0)}]({s})")
        else:
            text, k = _sub_outside_markup(text, pattern, say_text)
        if k:
            applied.append(f"{word} -> {say_text}")
    for word, say_text in sorted((respellings or {}).items(), key=lambda p: -len(p[0])):
        pattern = re.compile(r"(?<![A-Za-z0-9])" + re.escape(word) + r"(?![A-Za-z0-9])")
        text, k = _sub_outside_markup(text, pattern, say_text)
        if k:
            applied.append(f"{word} -> {say_text} (respelled)")
    return text, applied


def hotwords(texts: list[str], extra: list[str] | None = None, limit: int = 40) -> str:
    """The reel's names for faster-whisper's hotwords (M13, DECISIONS.md 283): the words with a capital that is not
    just a sentence's first letter (Claude, MCP, CLAUDE.md, FlashFX, GitHub), in order, each once, plus extra words
    (the keys of pronunciations.txt). Whisper's small model does not know "Claude" and writes "clod" or "clawed" for
    a voice that says it right; a viewer who knows the topic hears the name, and so does whisper with the hint, while
    a word the voice really gets wrong still fails (the hint biases spelling, it does not invent sounds)."""
    seen: list[str] = []

    def add(word: str) -> None:
        w = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", word)
        if len(w) >= 2 and re.search(r"[A-Za-z]", w) and w.lower() not in {x.lower() for x in seen}:
            seen.append(w)

    initial: dict[str, int] = {}   # capitalized only at a sentence start: a name when it happens twice
    for text in texts:
        plain = strip_markup(clean(text))
        for sentence in re.split(r"(?<=[.!?])\s+", plain):
            for k, word in enumerate(sentence.split()):
                core = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", word)
                if not core or not re.search(r"[A-Z]", core) or core in ("I", "I'm", "I've", "I'll", "I'd"):
                    continue
                if k == 0 and core[0].isupper() and core[1:] == core[1:].lower() and "." not in core:
                    initial[core] = initial.get(core, 0) + 1  # "Start", "You're": maybe just the sentence start
                    continue
                add(core)
    for word, n in initial.items():
        if n >= 2 or word.lower() in {x.lower() for x in seen}:
            add(word)
    for word in extra or []:
        add(word)
    return " ".join(seen[:limit])


def auto_respell(word: str) -> str:
    """A deterministic respelling for a word the voice got wrong: camelCase split, acronyms of 2 to 5 capitals
    spelled letter by letter, digits written out, dots, slashes, at-signs and dashes named or dropped. A plain word
    (letters only, lowercase or capitalized) has no rule: the empty string means "nothing to respell"."""
    core = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", strip_markup(word or ""))
    if not core:
        return ""
    if re.fullmatch(r"[A-Za-z]+", core) and (core.islower() or core.istitle() or len(core) == 1):
        return ""
    out = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", core)
    out = re.sub(r"(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])", " ", out)
    out = re.sub(r"(?<=[A-Za-z0-9])\.(?=[A-Za-z0-9])", " dot ", out)
    out = out.replace("_", " ").replace("-", " ").replace("/", " slash ").replace("@", " at ").replace("+", " plus ").replace("#", " hash ")
    pieces: list[str] = []
    for p in out.split():
        if re.fullmatch(r"[A-Z]{2,5}", p):
            pieces.append(" ".join(p))
        elif re.fullmatch(r"\d+", p):
            pieces.extend(num_words(int(p)))
        else:
            pieces.append(p)
    res = " ".join(pieces)
    return res if res != core else ""


# ------------------------------------------------------------------------------------------------ normalization and WER
def num_words(n: int) -> list[str]:
    if n < 0:
        return ["minus"] + num_words(-n)
    if n < 20:
        return [ONES[n]]
    if n < 100:
        return [TENS[n // 10]] + ([ONES[n % 10]] if n % 10 else [])
    if n < 1000:
        return [ONES[n // 100], "hundred"] + (num_words(n % 100) if n % 100 else [])
    for div, name in ((10 ** 12, "trillion"), (10 ** 9, "billion"), (10 ** 6, "million"), (1000, "thousand")):
        if n >= div:
            return num_words(n // div) + [name] + (num_words(n % div) if n % div else [])
    return [str(n)]


def year_words(n: int) -> list[str] | None:
    if 1100 <= n <= 2099 and n % 100 != 0:
        return num_words(n // 100) + num_words(n % 100)
    return None


def _number_items(piece: str, context: str) -> list[str]:
    """Digits as words; the year reading when the other side says it that way."""
    digits = piece.replace(",", "")
    if re.fullmatch(r"\d+", digits):
        n = int(digits)
        year = year_words(n)
        if year and " ".join(year) in context:
            return year
        return num_words(n)
    m = re.fullmatch(r"(\d+)\.(\d+)", digits)
    if m:
        return num_words(int(m.group(1))) + ["point"] + [ONES[int(d)] for d in m.group(2)]
    return [digits]


def norm_items(tokens: list[str], context: str = "") -> list[tuple[str, int]]:
    """Normalized comparable items (text, raw token index). A raw token can give several items (a hyphenated word,
    a number written in digits) or none (punctuation alone)."""
    items: list[tuple[str, int]] = []
    for i, raw in enumerate(tokens):
        tok = strip_markup(raw).lower()
        tok = tok.replace("&", " and ").replace("%", " percent ")
        tok = re.sub(r"\$\s*(\d[\d,]*(?:\.\d+)?)", r"\1 dollars ", tok)
        for piece in re.split(r"[\s\-/_]+", tok):
            piece = piece.strip()
            if not piece:
                continue
            if piece in ORDINALS:
                items.append((ORDINALS[piece], i))
                continue
            m = re.fullmatch(r"(\d+)(st|nd|rd|th)\.?", piece)
            if m:
                for w in num_words(int(m.group(1))):
                    items.append((w, i))
                items[-1] = (items[-1][0] + "th", i)
                continue
            if re.fullmatch(r"\d[\d,]*(\.\d+)?\.?", piece):
                for w in _number_items(piece.rstrip("."), context):
                    items.append((w, i))
                continue
            word = re.sub(r"[^a-z0-9]+", "", piece)
            if not word:
                continue
            word = ALIASES.get(word, word)
            items.append((VARIANTS.get(word, word), i))
    return items


def lenient_equal(a: str, b: str) -> bool:
    """The same word up to a plural or possessive s (the transcriber drops or adds one freely: "Anthropic's" is
    heard as "Anthropic", "card" as "cards"); the voice said the word either way."""
    if a == b:
        return True
    if min(len(a), len(b)) < 3:
        return False
    return a + "s" == b or b + "s" == a


def align(ref_items: list[tuple[str, int]], hyp_items: list[tuple[str, int]]) -> dict:
    """Word-level alignment of a reference against a hypothesis. A block where the joined reference words equal the
    joined hypothesis words (plug in / plugin, F X / FX) counts as a match. Returns errors, the blocks and the WER."""
    a = [t for t, _ in ref_items]
    b = [t for t, _ in hyp_items]
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    errors = 0
    blocks: list[dict] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            blocks.append({"tag": "equal", "ref": (i1, i2), "hyp": (j1, j2)})
            continue
        if tag == "replace" and "".join(a[i1:i2]) == "".join(b[j1:j2]):
            blocks.append({"tag": "joined", "ref": (i1, i2), "hyp": (j1, j2)})
            continue
        if tag == "replace" and (i2 - i1) == (j2 - j1):
            pairs = list(zip(a[i1:i2], b[j1:j2]))
            if all(lenient_equal(x, y) for x, y in pairs):
                blocks.append({"tag": "equal", "ref": (i1, i2), "hyp": (j1, j2)})
                continue
            # a mixed block: only the pairs that really differ count, each as its own block
            for k, (x, y) in enumerate(pairs):
                if lenient_equal(x, y):
                    blocks.append({"tag": "equal", "ref": (i1 + k, i1 + k + 1), "hyp": (j1 + k, j1 + k + 1)})
                else:
                    errors += 1
                    blocks.append({"tag": "replace", "ref": (i1 + k, i1 + k + 1), "hyp": (j1 + k, j1 + k + 1)})
            continue
        if tag == "replace":
            errors += max(i2 - i1, j2 - j1)
        elif tag == "delete":
            errors += i2 - i1
        else:
            errors += j2 - j1
        blocks.append({"tag": tag, "ref": (i1, i2), "hyp": (j1, j2)})
    n = max(1, len(a))
    return {"errors": errors, "n": len(a), "wer_pct": round(100.0 * errors / n, 1), "blocks": blocks}


def wer_report(ref_text: str, hyp_text: str) -> dict:
    ref_tokens = strip_markup(ref_text).split()
    hyp_tokens = strip_markup(hyp_text).split()
    ref_items = norm_items(ref_tokens)
    context = " ".join(t for t, _ in ref_items)
    hyp_items = norm_items(hyp_tokens, context)
    res = align(ref_items, hyp_items)
    misheard: list[str] = []
    heard: list[str] = []
    for blk in res["blocks"]:
        if blk["tag"] in ("equal", "joined"):
            continue
        i1, i2 = blk["ref"]
        j1, j2 = blk["hyp"]
        seen = set()
        for _, idx in ref_items[i1:i2]:
            if idx not in seen:
                seen.add(idx)
                misheard.append(re.sub(r"^[^A-Za-z0-9\[]+|[^A-Za-z0-9\]\)]+$", "", ref_tokens[idx]))
        heard.append((" ".join(t for t, _ in ref_items[i1:i2]) or "(nothing)") + " -> " + (" ".join(t for t, _ in hyp_items[j1:j2]) or "(nothing)"))
    return {"wer_pct": res["wer_pct"], "errors": res["errors"], "n": res["n"], "misheard": misheard, "heard": heard,
            "ref_items": ref_items, "hyp_items": hyp_items, "blocks": res["blocks"]}


def item_times(items: list[tuple[str, int]], raw_times: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Each item's (start, end): a raw token's span split evenly among the items it produced."""
    groups: dict[int, list[int]] = {}
    for k, (_, idx) in enumerate(items):
        groups.setdefault(idx, []).append(k)
    out: list[tuple[float, float]] = [(0.0, 0.0)] * len(items)
    for idx, ks in groups.items():
        s, e = raw_times[idx] if idx < len(raw_times) else (0.0, 0.0)
        step = (e - s) / len(ks) if ks else 0.0
        for j, k in enumerate(ks):
            out[k] = (s + j * step, s + (j + 1) * step)
    return out


def transfer_times(ref_items, hyp_items, blocks, hyp_times: list[tuple[float, float]]) -> list[tuple[float, float] | None]:
    """The time span of every reference item from the hypothesis items it was aligned with (None when unheard)."""
    out: list[tuple[float, float] | None] = [None] * len(ref_items)
    for blk in blocks:
        i1, i2 = blk["ref"]
        j1, j2 = blk["hyp"]
        if i2 <= i1:
            continue
        if blk["tag"] == "equal":
            for k in range(i2 - i1):
                out[i1 + k] = hyp_times[j1 + k]
        elif blk["tag"] in ("joined", "replace") and j2 > j1:
            start, end = hyp_times[j1][0], hyp_times[j2 - 1][1]
            lengths = [max(1, len(ref_items[i][0])) for i in range(i1, i2)]
            total = float(sum(lengths))
            pos = start
            for k, ln in enumerate(lengths):
                nxt = pos + (end - start) * ln / total
                out[i1 + k] = (pos, nxt)
                pos = nxt
    # unheard items: between their neighbours
    n = len(out)
    k = 0
    while k < n:
        if out[k] is not None:
            k += 1
            continue
        j = k
        while j < n and out[j] is None:
            j += 1
        prev_end = out[k - 1][1] if k > 0 else (out[j][0] if j < n else 0.0)
        next_start = out[j][0] if j < n else prev_end
        if next_start < prev_end:
            next_start = prev_end
        step = (next_start - prev_end) / (j - k)
        for m in range(k, j):
            out[m] = (prev_end + (m - k) * step, prev_end + (m - k + 1) * step)
        k = j
    return out


def raw_token_times(tokens: list[str], items: list[tuple[str, int]], times: list[tuple[float, float] | None]) -> list[tuple[float, float] | None]:
    out: list[tuple[float, float] | None] = [None] * len(tokens)
    for (_, idx), span in zip(items, times):
        if span is None:
            continue
        cur = out[idx]
        out[idx] = span if cur is None else (min(cur[0], span[0]), max(cur[1], span[1]))
    return out


def line_words(spoken: str, tts: str, transcript: list[dict], offset_s: float, beat: str) -> list[dict]:
    """words.json entries for one line: the spoken track's words timed from the transcription of the line's audio,
    through the TTS text (pronunciations and respellings) when it differs from the spoken track."""
    hyp_tokens = [w["word"] for w in transcript]
    hyp_raw_times = [(float(w["start"]), float(w["end"])) for w in transcript]
    tts_tokens = strip_markup(tts).split()
    tts_items = norm_items(tts_tokens)
    context = " ".join(t for t, _ in tts_items)
    hyp_items = norm_items(hyp_tokens, context)
    res = align(tts_items, hyp_items)
    tts_item_times = transfer_times(tts_items, hyp_items, res["blocks"], item_times(hyp_items, hyp_raw_times))
    tts_tok_times = raw_token_times(tts_tokens, tts_items, tts_item_times)
    spoken_tokens = strip_markup(spoken).split()
    spoken_items = norm_items(spoken_tokens)
    res2 = align(spoken_items, tts_items)
    spoken_item_times = transfer_times(spoken_items, tts_items, res2["blocks"], item_times(tts_items, [t or (0.0, 0.0) for t in tts_tok_times]))
    spoken_tok_times = raw_token_times(spoken_tokens, spoken_items, spoken_item_times)
    heard_by_item: dict[int, str] = {}
    for blk in res["blocks"]:
        if blk["tag"] in ("equal", "joined"):
            continue
        heard = " ".join(t for t, _ in hyp_items[blk["hyp"][0]:blk["hyp"][1]]) or "(nothing)"
        for i in range(blk["ref"][0], blk["ref"][1]):
            heard_by_item[i] = heard
    heard_by_tts_token: dict[int, str] = {}
    for k, (_, idx) in enumerate(tts_items):
        if k in heard_by_item:
            heard_by_tts_token[idx] = heard_by_item[k]
    out: list[dict] = []
    last_end = 0.0
    for i, tok in enumerate(spoken_tokens):
        if not re.search(r"[A-Za-z0-9]", tok):
            continue
        span = spoken_tok_times[i] or (last_end, last_end)
        start, end = max(0.0, span[0]), max(span[0], span[1])
        last_end = end
        entry = {"word": tok, "start_ms": int(round((offset_s + start) * 1000)), "end_ms": int(round((offset_s + end) * 1000)), "beat": beat}
        heard = None
        for k, (_, idx) in enumerate(spoken_items):
            if idx == i:
                for blk in res2["blocks"]:
                    if blk["ref"][0] <= k < blk["ref"][1]:
                        for t in range(blk["hyp"][0], blk["hyp"][1]):
                            if tts_items[t][1] in heard_by_tts_token:
                                heard = heard_by_tts_token[tts_items[t][1]]
                        break
        if heard:
            entry["heard"] = clean(heard)
        out.append(entry)
    for a, b in zip(out, out[1:]):  # monotonic, never overlapping
        if b["start_ms"] < a["end_ms"]:
            b["start_ms"] = a["end_ms"]
        if b["end_ms"] < b["start_ms"]:
            b["end_ms"] = b["start_ms"]
    return out


# ------------------------------------------------------------------------------------------------ audio files
def read_pcm16(path: str):
    import numpy as np
    with wave.open(winpath(path), "rb") as w:
        sr, ch, width, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
        data = w.readframes(n)
    if width != 2:
        raise ValueError(f"{path}: {width * 8}-bit samples, expected 16-bit PCM")
    arr = np.frombuffer(data, dtype="<i2")
    if ch > 1:
        arr = arr.reshape(-1, ch).mean(axis=1).astype("<i2")
    return arr, sr


def write_pcm16(path: str, arr, sr: int) -> None:
    import numpy as np
    path = winpath(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(np.asarray(arr, dtype="<i2").tobytes())


def wav_duration(path: str) -> float:
    with wave.open(winpath(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def silent_runs(path: str, threshold_db: float = -40.0, frame_s: float = 0.01) -> list[dict]:
    import numpy as np
    arr, sr = read_pcm16(path)
    x = arr.astype("float32") / 32768.0
    hop = max(1, int(sr * frame_s))
    n = len(x) // hop
    if n == 0:
        return [{"start_s": 0.0, "end_s": len(x) / sr, "seconds": len(x) / sr}] if len(x) else []
    rms = np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(axis=1)) + 1e-12
    silent = 20 * np.log10(rms) < threshold_db
    runs: list[dict] = []
    i = 0
    while i < n:
        if not silent[i]:
            i += 1
            continue
        j = i
        while j < n and silent[j]:
            j += 1
        start, end = i * hop / sr, (j * hop if j < n else len(x)) / sr
        runs.append({"start_s": round(start, 3), "end_s": round(end, 3), "seconds": round(end - start, 3)})
        i = j
    return runs


def window_db(path: str, from_ms: float, to_ms: float) -> float:
    import numpy as np
    arr, sr = read_pcm16(path)
    a, b = int(from_ms / 1000 * sr), int(to_ms / 1000 * sr)
    seg = arr[max(0, a):max(a + 1, b)].astype("float32") / 32768.0
    if len(seg) == 0:
        return -120.0
    return float(20 * np.log10(np.sqrt((seg ** 2).mean()) + 1e-12))


def ffmpeg_measure(path: str, target_i: float, target_tp: float, timeout: int = 300) -> dict:
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", winpath(path), "-af",
           f"loudnorm=I={target_i}:TP={target_tp}:LRA=11:print_format=json", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, stdin=subprocess.DEVNULL)
    m = re.search(r"\{.*\}", r.stderr or "", re.S)
    if not m:
        raise RuntimeError(f"ffmpeg loudnorm gave no measurement for {path}: {clean((r.stderr or '')[-300:])}")
    d = json.loads(m.group(0))

    def num(key):
        try:
            v = float(d[key])
        except (KeyError, ValueError, TypeError):
            return None
        return None if math.isinf(v) or math.isnan(v) else v
    return {"lufs": num("input_i"), "true_peak_dbtp": num("input_tp"), "lra": num("input_lra"), "threshold": num("input_thresh")}


def loudness_normalize(src: str, dst: str, target_i: float, target_tp: float, sr: int = 48000, timeout: int = 300) -> dict:
    """Linear gain plus a light true-peak limiter, re-measured, up to 5 passes: integrated loudness within 0.4 LU
    of the target with the true peak at or under the ceiling. (Two-pass loudnorm alone lands a decibel low on
    Kokoro's voice, because its peaks sit 16 dB above its loudness: the ceiling binds first.)"""
    first = ffmpeg_measure(src, target_i, target_tp, timeout)
    if first["lufs"] is None:  # digital silence or too short to measure: convert only
        subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-y", "-i", winpath(src), "-ar", str(sr), "-ac", "1", "-c:a", "pcm_s16le", winpath(dst)],
                       capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL, check=True)
        return {"input": first, "lufs": None, "true_peak_dbtp": None, "gain_db": 0.0, "passes": 0, "ok": False}
    gain = target_i - first["lufs"]
    margin = 0.8
    result = None
    passes = 0
    last_i = None
    for _ in range(8):
        passes += 1
        limit = 10 ** ((target_tp - margin) / 20.0)
        af = f"volume={gain:.2f}dB,alimiter=limit={limit:.4f}:attack=3:release=100:level=0"
        cmd = ["ffmpeg", "-hide_banner", "-nostats", "-y", "-i", winpath(src), "-af", af, "-ar", str(sr), "-ac", "1", "-c:a", "pcm_s16le", winpath(dst)]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg failed on {src}: {clean((r.stderr or '')[-300:])}")
        m = ffmpeg_measure(dst, target_i, target_tp, timeout)
        result = {"input": first, "lufs": m["lufs"], "true_peak_dbtp": m["true_peak_dbtp"], "gain_db": round(gain, 2), "passes": passes,
                  "limiter_db": round(target_tp - margin, 2)}
        if m["lufs"] is None:
            break
        ok_i = abs(m["lufs"] - target_i) <= 0.4
        ok_tp = m["true_peak_dbtp"] is None or m["true_peak_dbtp"] <= target_tp
        if ok_i and ok_tp:
            break
        if ok_tp and last_i is not None and abs(m["lufs"] - last_i) < 0.05:
            break  # the limiter eats every further decibel: the level has stopped moving
        last_i = m["lufs"]
        gain += target_i - m["lufs"]
        if not ok_tp:
            margin += (m["true_peak_dbtp"] - target_tp) + 0.1
    result["ok"] = result["lufs"] is not None and abs(result["lufs"] - target_i) <= 1.0 and \
        (result["true_peak_dbtp"] is None or result["true_peak_dbtp"] <= target_tp + 0.05)
    return result


# ------------------------------------------------------------------------------------------------ workers
def run_streaming(cmd: list[str], timeout: float | None, on_line, prefix: str, cwd: str | None = None) -> int:
    """Run a command, echo its output to the stage log line by line (on_line sees stdout lines), kill it after the
    timeout. Returns the exit code; raises TimeoutError."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                            env=worker_env(), cwd=cwd, stdin=subprocess.DEVNULL, bufsize=1)
    q: queue.Queue = queue.Queue()

    def reader(stream, kind):
        try:
            for line in iter(stream.readline, ""):
                q.put((kind, line.rstrip("\r\n")))
        finally:
            q.put((kind, None))
    threads = [threading.Thread(target=reader, args=(proc.stdout, "out"), daemon=True),
               threading.Thread(target=reader, args=(proc.stderr, "err"), daemon=True)]
    for t in threads:
        t.start()
    open_streams = 2
    deadline = time.time() + timeout if timeout else None
    while open_streams > 0:
        try:
            kind, line = q.get(timeout=1.0)
        except queue.Empty:
            if deadline and time.time() > deadline:
                proc.kill()
                raise TimeoutError(f"{os.path.basename(cmd[1]) if len(cmd) > 1 else cmd[0]} did not finish in {int(timeout)} s (killed)")
            continue
        if line is None:
            open_streams -= 1
            continue
        if kind == "out":
            on_line(line)
            log(f"{prefix}{line}")
        elif line.strip():
            log(f"{prefix}stderr: {line}")
    return proc.wait()


class Stage:
    def __init__(self, args):
        self.ctx = Ctx(args.config, args.root, args.repo)
        self.run_dir = winpath(args.run_dir).replace("\\", "/")
        self.out = winpath(args.stage_dir or f"{self.run_dir}/{STAGE}").replace("\\", "/")
        self.s7 = winpath(args.s7 or f"{self.ctx.repo}/pipeline/stages/07-script/run.sh").replace("\\", "/")
        self.work = f"{self.out}/work"
        self.lines_dir = f"{self.out}/lines"
        os.makedirs(self.work, exist_ok=True)
        os.makedirs(self.lines_dir, exist_ok=True)
        cfg = self.ctx.cfg
        self.wer_fail = float(cfg("tts.wer_fail_pct", 3))
        self.wer_flag_max = float(cfg("tts.wer_flag_max_pct", 8))
        self.overrun_pct = float(cfg("tts.overrun_pct", 15))
        self.overrun_min_s = float(cfg("tts.overrun_min_s", 0.4))
        self.lead_s = float(cfg("tts.lead_s", 0.05))
        self.tail_s = float(cfg("tts.tail_s", 0.2))
        self.pad_s = float(cfg("tts.whisper_pad_s", 0.5))
        self.whisper_model = str(cfg("tts.whisper_model", "small"))
        self.wpm = float(cfg("voice.wpm", 170))
        self.target_i = float(cfg("voice.loudness_lufs", -14))
        self.target_tp = float(cfg("voice.true_peak_dbtp", -1.5))
        self.t_tts = int(cfg("timeouts.tts_seconds", 1800))
        self.t_align = int(cfg("timeouts.align_seconds", 1800))
        self.t_loud = int(cfg("timeouts.loudness_seconds", 300))
        self.flags: list[str] = []
        self.spw = 1.5  # syllables per word, replaced by the script's own average in set_pace_shape
        self.calls = 0
        self.timing = {"tts_wall_s": 0.0, "tts_load_s": 0.0, "tts_synth_s": 0.0, "tts_tighten_s": 0.0, "align_wall_s": 0.0,
                       "align_model_load_s": 0.0, "loudness_s": 0.0, "rewrite_s": 0.0, "total_s": 0.0}
        self.lines: list[dict] = []
        self.entries: list[tuple[str, str]] = []
        self.script: dict = {}
        self.script_path = f"{self.run_dir}/07-script/script.json"

    # ---------------------------------------------------------------- setup
    def flag(self, text: str) -> None:
        text = clean(text)
        if text not in self.flags:
            self.flags.append(text)
            relay("FLAG", text)

    def setup(self) -> None:
        info = engine_config(self.ctx)
        self.engine_info = info
        self.engine = info["engine"]
        for note in info["notes"]:
            say("WARN", f"S8: {note}")
        if info["problems"]:
            raise RuntimeError("engine.txt is not usable: " + "; ".join(info["problems"]))
        self.tts_py = tts_python(self.ctx, info)
        if not exe_exists(self.tts_py):
            raise RuntimeError(f"the voice interpreter {self.tts_py} does not exist (library/voice/engine.txt, python line)")
        self.whisper_py, tried = resolve_whisper(self.ctx, self.tts_py)
        if not self.whisper_py:
            raise RuntimeError("no interpreter imports faster_whisper (tried: " + "; ".join(tried) + "); set config tts.whisper_python or run bash pipeline/bin/setup-venv")
        self.tts_worker = os.environ.get("REELS_TTS_WORKER") or f"{self.ctx.repo}/pipeline/lib/tts/kokoro_worker.py"
        self.whisper_worker = os.environ.get("REELS_WHISPER_WORKER") or f"{self.ctx.repo}/pipeline/lib/tts/whisper_worker.py"
        self.script = load_json(self.script_path, None)
        if not self.script or not self.script.get("beats"):
            raise RuntimeError("07-script/script.json is missing or has no beats")
        pron_path = f"{self.ctx.root}/{self.ctx.cfg('paths.profile', 'library/profile')}/pronunciations.txt"
        self.entries = read_pronunciations(pron_path)
        self.pron_path = pron_path
        for b in self.script["beats"]:
            self.lines.append(self.new_line(b["id"], "beat", b.get("type", ""), b.get("spoken", "") or b.get("display", "")))
        hook2 = self.script.get("hook2") or {}
        if (hook2.get("spoken") or "").strip():
            self.lines.append(self.new_line("hook2", "hook2", "hook", hook2["spoken"]))
        else:
            self.flag("voice: script.json has no hook 2 line, so there is no vo_hook2.wav for the alternate clip")
        self.apply_review_feedback()
        self.set_pace_shape()
        eng = self.engine
        n_beats = sum(1 for ln in self.lines if ln["kind"] == "beat")
        words = sum(ln["words"] for ln in self.lines if ln["kind"] == "beat")
        src = {"file": "library/voice/engine.txt", "file+defaults": "library/voice/engine.txt plus defaults", "defaults": "the defaults, no engine.txt",
               "defaults-unsupported": "the defaults, engine.txt names another engine"}.get(info["status"], info["status"])
        say("INFO", f"S8: {eng['engine']} {eng['voice']} ({src}), speed {eng['speed']:g}: {n_beats} beats"
                    f"{' plus hook 2' if n_beats < len(self.lines) else ''}, {words} spoken words at {self.wpm:.0f} wpm; pauses of {eng['min_pause_s']:g} s or more cut to "
                    f"{eng['keep_pause_s']:g} s below {eng['silence_threshold_db']:g} dB, {eng['breath_after_hook_s']:g} s breath after the hook"
                    f"{'; ' + str(len(self.entries)) + ' pronunciation' + ('s' if len(self.entries) != 1 else '') + ' from pronunciations.txt' if self.entries else ''}")
        log(f"voice interpreter: {self.tts_py}; whisper interpreter: {self.whisper_py} (model {self.whisper_model}); worker {self.tts_worker}")

    def apply_review_feedback(self) -> None:
        """The edit review (S12, M11) routes a [voice] issue here only when it names a word in quotes: that word gets a
        respelling in every line that says it, before the first generation (the voice is deterministic, so a plain
        re-run would change nothing)."""
        fb = load_json(f"{self.run_dir}/12-review/feedback.json", None)
        if not isinstance(fb, dict):
            return
        words: list[str] = []
        for issue in (fb.get("by_stage") or {}).get("08-voiceover", []) or []:
            for m in re.finditer(r"[\"“‘']([A-Za-z][A-Za-z0-9'.-]{1,30})[\"”’']", str(issue.get("text", ""))):
                w = m.group(1).strip(".'")
                if w and w.lower() not in [x.lower() for x in words]:
                    words.append(w)
        if not words:
            return
        hit = 0
        for ln in self.lines:
            for w in words:
                if re.search(r"" + re.escape(w) + r"", ln["spoken"], re.IGNORECASE) and w not in ln["respellings"]:
                    ln["respellings"][w] = auto_respell(w)
                    hit += 1
            self.refresh_text(ln)
        if hit:
            say("INFO", f"S8: the edit review named {len(words)} word{'s' if len(words) != 1 else ''} ({', '.join(words)}): respelled in {hit} line{'s' if hit != 1 else ''}")

    def new_line(self, lid: str, kind: str, btype: str, spoken: str) -> dict:
        ln = {"id": lid, "kind": kind, "type": btype, "spoken": clean(spoken), "respellings": {}, "attempts": [], "attempt": 0,
              "rewritten": False, "respelled": False, "status": "pending", "wer_pct": None, "misheard": [], "heard": [],
              "transcript": [], "duration_s": None, "raw_s": None, "wav": "", "flag_text": "", "steps": []}
        self.refresh_text(ln)
        return ln

    def refresh_text(self, ln: dict) -> None:
        ln["tts"], ln["applied"] = tts_text(ln["spoken"], self.entries, ln["respellings"])
        ln["words"] = n_words(ln["spoken"])
        ln["syllables"] = text_syllables(ln["spoken"])
        # the estimate at config voice.wpm, spread over the lines by syllables (the script's own average syllables
        # per word keeps the total equal to words / wpm): a line of long words gets its time, a line of short
        # words less, so the 15 percent overrun check catches a slow line and not a long word
        ln["estimate_s"] = round(max(1, ln["syllables"]) / max(0.5, self.spw) * 60.0 / self.wpm, 2)

    def set_pace_shape(self) -> None:
        beats = [ln for ln in self.lines if ln["kind"] == "beat"]
        words = sum(ln["words"] for ln in beats)
        syl = sum(ln["syllables"] for ln in beats)
        self.spw = (syl / words) if words else 1.5
        for ln in self.lines:
            self.refresh_text(ln)

    # ---------------------------------------------------------------- generation and transcription
    def generate(self, lines: list[dict], activity: str) -> None:
        if not lines:
            return
        self.calls += 1
        n = self.calls
        for ln in lines:
            ln["attempt"] += 1
        job = {"tools_dir": f"{self.ctx.repo}/tools", "sr": 24000, "out_dir": self.lines_dir,
               "settings": {"voice": self.engine["voice"], "lang": self.engine["lang"], "speed": self.engine["speed"],
                            "silence_threshold_db": self.engine["silence_threshold_db"], "min_pause_s": self.engine["min_pause_s"],
                            "keep_pause_s": self.engine["keep_pause_s"]},
               "lines": [{"id": ln["id"], "name": f"{ln['id']}.a{ln['attempt']}", "text": ln["tts"], "estimate_s": ln["estimate_s"]} for ln in lines],
               "result": f"{self.work}/tts-{n}.result.json"}
        job_path = f"{self.work}/tts-{n}.json"
        save_json(job_path, job)
        total = len(lines)

        def on_line(line: str) -> None:
            m = re.match(r"^LINE (\d+)/(\d+) (\S+)", line)
            if m:
                if activity:
                    relay("ACTIVITY", activity)
                else:
                    relay("ACTIVITY", f"generating voiceover (beat {m.group(1)}/{m.group(2)})")
            elif line.startswith("TIGHTEN "):
                relay("ACTIVITY", "tightening silences")
        relay("ACTIVITY", activity or f"generating voiceover (beat 1/{total})")
        t0 = time.time()
        try:
            rc = run_streaming([winpath(self.tts_py), winpath(self.tts_worker), winpath(job_path)], self.t_tts, on_line, "  kokoro: ")
        except TimeoutError as exc:
            raise RuntimeError(f"the voice engine hung: {exc}") from exc
        wall = time.time() - t0
        self.timing["tts_wall_s"] += wall
        if rc != 0:
            raise RuntimeError(f"the voice engine failed (kokoro_worker.py exit {rc}, call {n}); see the kokoro: lines above")
        res = load_json(job["result"], None)
        if not res or "lines" not in res:
            raise RuntimeError(f"the voice engine wrote no result ({job['result']})")
        by_id = {item["id"]: item for item in res["lines"]}
        for ln in lines:
            item = by_id.get(ln["id"])
            if not item or not item.get("wav") or not os.path.isfile(winpath(item["wav"])):
                raise RuntimeError(f"the voice engine produced no audio for line {ln['id']}")
            ln["wav"] = item["wav"].replace("\\", "/")
            ln["duration_s"] = round(float(item["duration_s"]), 3)
            ln["raw_s"] = round(float(item.get("raw_s", item["duration_s"])), 3)
            ln["shortened"] = int(item.get("shortened", 0))
            ln["removed_s"] = round(float(item.get("removed_s", 0.0)), 3)
            if ln["duration_s"] <= 0.05:
                raise RuntimeError(f"the voice engine produced {ln['duration_s']} s of audio for line {ln['id']}")
        t = res.get("timing", {})
        self.timing["tts_load_s"] = max(self.timing["tts_load_s"], float(t.get("import_s", 0)) + float(t.get("load_s", 0)))
        self.timing["tts_synth_s"] += float(t.get("synth_s", 0))
        self.timing["tts_tighten_s"] += float(t.get("tighten_s", 0))
        self.last_tts = res
        audio = sum(ln["raw_s"] for ln in lines)
        synth = float(t.get("synth_s", 0)) or wall
        log(f"call {n}: {len(lines)} lines, {audio:.1f} s of raw voice in {synth:.1f} s of synthesis ({synth / max(audio, 0.01):.2f}x real time), "
            f"import+load {float(t.get('import_s', 0)) + float(t.get('load_s', 0)):.1f} s, tightened to {sum(ln['duration_s'] for ln in lines):.1f} s")

    def transcribe(self, lines: list[dict]) -> None:
        if not lines:
            return
        self.calls += 1
        n = self.calls
        job = {"model": self.whisper_model, "language": "en", "pad_s": self.pad_s, "compute_type": "int8", "device": "cpu",
               "items": [{"id": ln["id"], "wav": ln["wav"], "text": strip_markup(ln["tts"])} for ln in lines],
               "result": f"{self.work}/whisper-{n}.result.json",
               # the names of the whole reel (not only these lines), so whisper spells them as the script does
               "hotwords": hotwords([x["spoken"] for x in getattr(self, "lines", None) or lines], [w for w, _ in self.entries])}
        job_path = f"{self.work}/whisper-{n}.json"
        save_json(job_path, job)
        relay("ACTIVITY", "aligning words")
        t0 = time.time()
        try:
            rc = run_streaming([winpath(self.whisper_py), winpath(self.whisper_worker), winpath(job_path)], self.t_align, lambda s: None, "  whisper: ")
        except TimeoutError as exc:
            raise RuntimeError(f"the transcription hung: {exc}") from exc
        self.timing["align_wall_s"] += time.time() - t0
        if rc != 0:
            raise RuntimeError(f"the transcription failed (whisper_worker.py exit {rc}, call {n}); see the whisper: lines above")
        res = load_json(job["result"], None)
        if not res or "items" not in res:
            raise RuntimeError(f"the transcription wrote no result ({job['result']})")
        self.timing["align_model_load_s"] = max(self.timing["align_model_load_s"], float(res.get("timing", {}).get("load_s", 0)))
        self.whisper_used = res.get("model", self.whisper_model)
        by_id = {item["id"]: item for item in res["items"]}
        for ln in lines:
            item = by_id.get(ln["id"])
            if item is None:
                raise RuntimeError(f"the transcription has no entry for line {ln['id']}")
            words = [{"word": clean(w.get("word", "")), "start": float(w.get("start", 0)), "end": float(w.get("end", 0))}
                     for w in item.get("words", []) if clean(w.get("word", ""))]
            ln["transcript"] = words
            heard_text = clean(item.get("text", "")) or " ".join(w["word"] for w in words)
            rep = wer_report(ln["tts"], heard_text)
            ln["wer_pct"], ln["misheard"], ln["heard"], ln["heard_text"] = rep["wer_pct"], rep["misheard"], rep["heard"], heard_text
            ln["attempts"].append({"attempt": ln["attempt"], "tts": ln["tts"], "wav": ln["wav"], "duration_s": ln["duration_s"], "raw_s": ln["raw_s"],
                                   "wer_pct": ln["wer_pct"], "heard": heard_text, "misheard": ln["misheard"], "steps": list(ln["steps"])})

    def failing(self, lines: list[dict]) -> list[dict]:
        return [ln for ln in lines if ln["wer_pct"] is None or ln["wer_pct"] > self.wer_fail]

    def describe(self, ln: dict) -> str:
        heard = "; ".join(ln["heard"][:3])
        return f"WER {ln['wer_pct']:.1f}%: {heard}" if heard else f"WER {ln['wer_pct']:.1f}%"

    # ---------------------------------------------------------------- the ladder
    def step_respell(self, lines: list[dict]) -> list[dict]:
        changed: list[dict] = []
        for ln in lines:
            new = {}
            for word in ln["misheard"]:
                core = re.sub(r"^[^A-Za-z0-9\[]+|[^A-Za-z0-9\]\)]+$", "", word)
                if not core or core in ln["respellings"] or core in new:
                    continue
                say_text = auto_respell(core)
                if say_text:
                    new[core] = say_text
            if not new:
                log(f"line {ln['id']}: misheard {ln['misheard']} but no respelling rule applies (plain words): on to the rewrite")
                ln["steps"].append("no respelling rule")
                continue
            ln["respellings"].update(new)
            ln["respelled"] = True
            ln["steps"].append("respelled " + ", ".join(f"{k} -> {v}" for k, v in new.items()))
            self.refresh_text(ln)
            say("WARN", f"S8: line {ln['id']} misheard ({self.describe(ln)}), fixing the pronunciation: " + ", ".join(f"{k} -> {v}" for k, v in new.items()))
            changed.append(ln)
        return changed

    def rewrite_line(self, ln: dict, reason: str) -> bool:
        """One rewrite of a beat's line through S7 in simpler words. True when script.json changed."""
        if ln["kind"] != "beat":
            return False
        relay("ACTIVITY", f"rewriting line {ln['id']}")
        t0 = time.time()
        cmd = [bash_exe(), winpath(self.s7), winpath(self.run_dir), "--rewrite-line", ln["id"], "--reason", clean(reason)]
        try:
            rc = run_streaming(cmd, None, lambda s: None, "  S7: ", cwd=winpath(self.ctx.root))
        except TimeoutError as exc:  # no timeout is set; kept for completeness
            raise RuntimeError(str(exc)) from exc
        self.timing["rewrite_s"] += time.time() - t0
        ln["rewritten"] = True
        if rc == 4:
            ln["steps"].append("rewrite: S7 gave no usable line")
            say("WARN", f"S8: S7 could not rewrite line {ln['id']} (no usable line twice); continuing with the current line")
            return False
        if rc != 0:
            raise RuntimeError(f"the S7 rewrite of line {ln['id']} failed (exit {rc}); see the S7: lines above")
        self.script = load_json(self.script_path, self.script)
        beat = next((b for b in self.script.get("beats", []) if b["id"] == ln["id"]), None)
        if beat is None:
            raise RuntimeError(f"script.json lost beat {ln['id']} after the rewrite")
        before = ln["spoken"]
        ln["spoken"] = clean(beat.get("spoken", "") or beat.get("display", ""))
        ln["respellings"] = {}
        self.refresh_text(ln)
        ln["steps"].append(f"rewritten by S7: \"{before}\" -> \"{ln['spoken']}\"")
        say("INFO", f"S8: line {ln['id']} rewritten by S7 in simpler words: \"{ln['spoken'][:90]}\"")
        return ln["spoken"] != before

    def ladder(self) -> None:
        # attempt 1: every line
        self.generate(self.lines, "")
        self.transcribe(self.lines)
        self.report_round("first pass")
        # step 2: the pronunciation of the misheard words
        bad = self.failing(self.lines)
        changed = self.step_respell(bad)
        if changed:
            self.generate(changed, f"fixing pronunciation (line {changed[0]['id']})" if len(changed) == 1 else "fixing pronunciation")
            self.transcribe(changed)
            for ln in changed:
                if ln["wer_pct"] <= self.wer_fail:
                    say("INFO", f"S8: line {ln['id']} ok after the pronunciation fix (WER {ln['wer_pct']:.1f}%)")
        # step 3: one rewrite through S7 for the beats still failing
        bad = [ln for ln in self.failing(self.lines) if ln["kind"] == "beat"]
        changed = []
        for ln in bad:
            say("WARN", f"S8: line {ln['id']} still misheard ({self.describe(ln)}) after the pronunciation step, rewriting it through S7")
            reason = f"the voice is misheard at: {', '.join(ln['misheard'][:6]) or 'several words'} (word error rate {ln['wer_pct']:.0f} percent)"
            if self.rewrite_line(ln, reason):
                changed.append(ln)
        if changed:
            self.generate(changed, f"generating voiceover (line {changed[0]['id']})" if len(changed) == 1 else "generating voiceover")
            self.transcribe(changed)
            for ln in changed:
                if ln["wer_pct"] <= self.wer_fail:
                    say("INFO", f"S8: line {ln['id']} ok after the rewrite (WER {ln['wer_pct']:.1f}%)")
        # the overrun check: a beat running more than overrun_pct over its estimate (and at least overrun_min_s) is rewritten once
        over = [ln for ln in self.lines if ln["kind"] == "beat" and self.overrun(ln) and not ln["rewritten"]]
        changed = []
        for ln in over:
            pct = 100.0 * (ln["duration_s"] - ln["estimate_s"]) / ln["estimate_s"]
            say("WARN", f"S8: line {ln['id']} runs {pct:.0f}% over its estimate ({ln['duration_s']:.1f} s against {ln['estimate_s']:.1f} s at {self.wpm:.0f} wpm), rewriting it through S7")
            reason = f"the line runs {pct:.0f} percent over its time ({ln['duration_s']:.1f} s against {ln['estimate_s']:.1f} s): make it shorter"
            if self.rewrite_line(ln, reason):
                changed.append(ln)
        if changed:
            self.generate(changed, f"generating voiceover (line {changed[0]['id']})" if len(changed) == 1 else "generating voiceover")
            self.transcribe(changed)
            again = self.step_respell(self.failing(changed))
            if again:
                self.generate(again, f"fixing pronunciation (line {again[0]['id']})")
                self.transcribe(again)
            for ln in changed:
                if not self.overrun(ln):
                    say("INFO", f"S8: line {ln['id']} fits after the rewrite ({ln['duration_s']:.1f} s against {ln['estimate_s']:.1f} s)")

    def overrun(self, ln: dict) -> bool:
        if ln["duration_s"] is None:
            return False
        return ln["duration_s"] > ln["estimate_s"] * (1 + self.overrun_pct / 100.0) and ln["duration_s"] - ln["estimate_s"] > self.overrun_min_s

    def report_round(self, label: str) -> None:
        bad = self.failing(self.lines)
        worst = max((ln["wer_pct"] or 0 for ln in self.lines), default=0)
        if not bad:
            say("INFO", f"S8: {label}: every line transcribes back within {self.wer_fail:g}% word error rate (worst {worst:.1f}%)")
        else:
            say("WARN", f"S8: {label}: {len(bad)} of {len(self.lines)} lines misheard: " + "; ".join(f"{ln['id']} {self.describe(ln)}" for ln in bad[:4]))

    def verdicts(self) -> dict:
        blocks: list[str] = []
        for ln in self.lines:
            steps = ", ".join(s for s in ln["steps"]) or "no fix tried"
            if ln["wer_pct"] is not None and ln["wer_pct"] <= self.wer_fail:
                ln["status"] = "ok"
            elif ln["kind"] == "beat" and (ln["wer_pct"] is None or ln["wer_pct"] > self.wer_flag_max):
                ln["status"] = "block"
                blocks.append(f"line {ln['id']} cannot be said clearly by {self.engine['voice']} ({self.describe(ln)}) after {steps}")
            else:
                ln["status"] = "flag"
                where = "hook 2" if ln["kind"] == "hook2" else f"line {ln['id']}"
                ln["flag_text"] = f"voice: {where} is misheard by faster-whisper ({self.describe(ln)}) after {steps}; listen to {'vo_hook2.wav' if ln['kind'] == 'hook2' else 'vo.wav'}"
            if ln["kind"] == "beat" and self.overrun(ln) and ln["status"] != "block":
                pct = 100.0 * (ln["duration_s"] - ln["estimate_s"]) / ln["estimate_s"]
                ln["status"] = "flag" if ln["status"] == "ok" else ln["status"]
                ln["overrun_text"] = f"voice: line {ln['id']} runs {pct:.0f}% over its estimate ({ln['duration_s']:.1f} s against {ln['estimate_s']:.1f} s at {self.wpm:.0f} wpm)" + \
                    (" after a rewrite" if ln["rewritten"] else " (no rewrite: S7 gave no usable line)" if "rewrite: S7 gave no usable line" in ln["steps"] else "")
        for ln in self.lines:
            if ln.get("flag_text"):
                self.flag(ln["flag_text"])
            if ln.get("overrun_text"):
                self.flag(ln["overrun_text"])
        if blocks:
            return {"status": "block", "reason": "voice: " + "; ".join(blocks)[:400]}
        return {"status": "flag" if any(ln["status"] == "flag" for ln in self.lines) else "ok", "reason": ""}

    # ---------------------------------------------------------------- assembly, loudness, words.json
    def assemble(self, lines: list[dict], out24: str) -> dict:
        import numpy as np
        sr = 24000
        pieces = []
        timeline: list[dict] = []
        breath = None
        lead = np.zeros(int(round(self.lead_s * sr)), dtype="<i2")
        pieces.append(lead)
        pos = len(lead)
        for k, ln in enumerate(lines):
            arr, lsr = read_pcm16(ln["wav"])
            if lsr != sr:
                raise RuntimeError(f"{ln['wav']} is {lsr} Hz, expected {sr}")
            pieces.append(arr)
            start, end = pos, pos + len(arr)
            timeline.append({"id": ln["id"], "type": ln["type"], "start_ms": int(round(start * 1000 / sr)), "end_ms": int(round(end * 1000 / sr)),
                             "start_s": start / sr})
            pos = end
            if k < len(lines) - 1:
                gap = self.engine["keep_pause_s"]
                if ln["type"] == "hook" or k == 0:
                    gap = max(self.engine["breath_after_hook_s"], self.engine["keep_pause_s"])
                    breath = {"after": ln["id"], "start_ms": int(round(pos * 1000 / sr)), "end_ms": int(round((pos + int(round(gap * sr))) * 1000 / sr)),
                              "seconds": round(gap, 3)}
                gap_n = int(round(gap * sr))
                pieces.append(np.zeros(gap_n, dtype="<i2"))
                pos += gap_n
        pieces.append(np.zeros(int(round(self.tail_s * sr)), dtype="<i2"))
        wav = np.concatenate(pieces)
        write_pcm16(out24, wav, sr)
        return {"timeline": timeline, "breath": breath, "duration_s": len(wav) / sr, "sample_rate": sr}

    def words_for(self, lines: list[dict], asm: dict) -> list[dict]:
        out: list[dict] = []
        by_id = {t["id"]: t for t in asm["timeline"]}
        for ln in lines:
            out.extend(line_words(ln["spoken"], ln["tts"], ln["transcript"], by_id[ln["id"]]["start_s"], ln["id"]))
        for a, b in zip(out, out[1:]):
            if b["start_ms"] < a["end_ms"]:
                b["start_ms"] = a["end_ms"]
            if b["end_ms"] < b["start_ms"]:
                b["end_ms"] = b["start_ms"]
        return out

    def write_outputs(self, verdict: dict) -> dict:
        beats = [ln for ln in self.lines if ln["kind"] == "beat"]
        hook2 = [ln for ln in self.lines if ln["kind"] == "hook2"]
        relay("ACTIVITY", "normalizing loudness")
        t0 = time.time()
        asm = self.assemble(beats, f"{self.work}/vo.24k.wav")
        loud = loudness_normalize(f"{self.work}/vo.24k.wav", f"{self.out}/vo.wav", self.target_i, self.target_tp, 48000, self.t_loud)
        duration_s = wav_duration(f"{self.out}/vo.wav")
        words = self.words_for(beats, asm)
        wpm_speech = sum(ln["words"] for ln in beats) / max(0.01, sum(ln["duration_s"] for ln in beats)) * 60.0
        gaps = self.engine["keep_pause_s"] * max(0, len(beats) - 1)
        wpm_pace = sum(ln["words"] for ln in beats) / max(0.01, sum(ln["duration_s"] for ln in beats) + gaps) * 60.0
        pace = {"wpm": int(round(wpm_pace)), "wpm_speech_only": int(round(wpm_speech)), "words": sum(ln["words"] for ln in beats),
                "speech_s": round(sum(ln["duration_s"] for ln in beats), 2), "gaps_s": round(gaps, 2)}
        if not loud.get("ok"):
            self.flag(f"voice: vo.wav loudness is {loud.get('lufs')} LUFS, true peak {loud.get('true_peak_dbtp')} dBTP (target {self.target_i:g} LUFS, at most {self.target_tp:g} dBTP) after {loud.get('passes')} passes")
        words_json = {
            "written_by": STAGE, "engine": self.engine["engine"], "voice": self.engine["voice"], "sample_rate": 48000,
            "duration_ms": int(round(duration_s * 1000)), "wpm": pace["wpm"], "whisper_model": getattr(self, "whisper_used", self.whisper_model),
            "beats": [{"id": t["id"], "type": t["type"], "start_ms": t["start_ms"], "end_ms": t["end_ms"], "words": ln["words"],
                       "wer_pct": ln["wer_pct"], "status": ln["status"], "estimate_s": ln["estimate_s"], "seconds": ln["duration_s"]}
                      for t, ln in zip(asm["timeline"], beats)],
            "breath": asm["breath"], "loudness": {"lufs": loud.get("lufs"), "true_peak_dbtp": loud.get("true_peak_dbtp")},
            "words": words, "flags": list(self.flags),
        }
        save_json(f"{self.out}/words.json", words_json)
        hook2_info = None
        if hook2:
            asm2 = self.assemble(hook2, f"{self.work}/vo_hook2.24k.wav")
            loud2 = loudness_normalize(f"{self.work}/vo_hook2.24k.wav", f"{self.out}/vo_hook2.wav", self.target_i, self.target_tp, 48000, self.t_loud)
            d2 = wav_duration(f"{self.out}/vo_hook2.wav")
            w2 = self.words_for(hook2, asm2)
            hook2_json = {"written_by": STAGE, "engine": self.engine["engine"], "voice": self.engine["voice"], "sample_rate": 48000,
                          "duration_ms": int(round(d2 * 1000)), "wpm": pace["wpm"], "whisper_model": words_json["whisper_model"],
                          "beats": [{"id": "hook2", "type": "hook", "start_ms": asm2["timeline"][0]["start_ms"], "end_ms": asm2["timeline"][0]["end_ms"],
                                     "words": hook2[0]["words"], "wer_pct": hook2[0]["wer_pct"], "status": hook2[0]["status"],
                                     "estimate_s": hook2[0]["estimate_s"], "seconds": hook2[0]["duration_s"]}],
                          "breath": None, "loudness": {"lufs": loud2.get("lufs"), "true_peak_dbtp": loud2.get("true_peak_dbtp")}, "words": w2, "flags": []}
            save_json(f"{self.out}/words_hook2.json", hook2_json)
            hook2_info = {"duration_s": round(d2, 3), "loudness": loud2, "wer_pct": hook2[0]["wer_pct"]}
        self.timing["loudness_s"] = round(time.time() - t0, 2)
        return {"asm": asm, "loud": loud, "duration_s": duration_s, "pace": pace, "hook2": hook2_info, "words": len(words)}

    def write_trail(self, verdict: dict, outputs: dict | None, error: str = "") -> None:
        audio = sum((ln["raw_s"] or 0) for ln in self.lines if ln["attempts"])
        trail = {
            "written_by": STAGE, "engine": self.engine_info["engine"] if hasattr(self, "engine_info") else None,
            "engine_file": {"path": self.engine_info["file"], "status": self.engine_info["status"], "notes": self.engine_info["notes"]} if hasattr(self, "engine_info") else None,
            "interpreters": {"tts": getattr(self, "tts_py", ""), "whisper": getattr(self, "whisper_py", ""), "tts_worker": getattr(self, "tts_worker", ""),
                             "whisper_worker": getattr(self, "whisper_worker", "")},
            "whisper_model": getattr(self, "whisper_used", self.whisper_model),
            "thresholds": {"wer_fail_pct": self.wer_fail, "wer_flag_max_pct": self.wer_flag_max, "overrun_pct": self.overrun_pct, "overrun_min_s": self.overrun_min_s,
                           "wpm": self.wpm, "lead_s": self.lead_s, "tail_s": self.tail_s, "loudness_lufs": self.target_i, "true_peak_dbtp": self.target_tp},
            "pronunciations": [f"{w} = {s}" for w, s in self.entries],
            "lines": [{k: v for k, v in ln.items() if k not in ("transcript",)} | {"transcript": ln["transcript"]} for ln in self.lines],
            "timing": {k: round(v, 2) for k, v in self.timing.items()} | {"audio_raw_s": round(audio, 2),
                       "speed_x_realtime": round(self.timing["tts_synth_s"] / audio, 3) if audio else None, "calls": self.calls},
            "pace": outputs["pace"] if outputs else None,
            "timeline": outputs["asm"]["timeline"] if outputs else None, "breath": outputs["asm"]["breath"] if outputs else None,
            "loudness": {"vo": outputs["loud"], "hook2": outputs["hook2"]["loudness"] if outputs and outputs["hook2"] else None} if outputs else None,
            "duration_s": round(outputs["duration_s"], 3) if outputs else None,
            "flags": list(self.flags), "verdict": verdict, "error": error,
        }
        save_json(f"{self.out}/voiceover.json", trail)
        # a small file for run.sh: the trail above is too large to pass through a command line (Windows caps it)
        save_json(f"{self.out}/verdict.json", {"status": verdict.get("status", ""), "reason": verdict.get("reason", ""), "flags": list(self.flags),
                                               "error": error})

    def run(self) -> int:
        t0 = time.time()
        verdict = {"status": "error", "reason": ""}
        try:
            self.setup()
            self.ladder()
            verdict = self.verdicts()
            outputs = self.write_outputs(verdict)
            self.timing["total_s"] = time.time() - t0
            self.write_trail(verdict, outputs)
        except Exception as exc:  # a code error: the review and fix path (BUILD_SPEC.md 4.2)
            self.timing["total_s"] = time.time() - t0
            try:
                self.write_trail(verdict, None, error=clean(str(exc)))
            except Exception:
                pass
            import traceback
            log(traceback.format_exc())
            relay("ERROR", str(exc))
            return 1
        t = self.timing
        audio = t["audio_raw_s"] if "audio_raw_s" in t else sum((ln["raw_s"] or 0) for ln in self.lines)
        speed = (t["tts_synth_s"] / audio) if audio else 0
        say("INFO", f"S8: generated {len(self.lines)} lines in {t['tts_wall_s']:.0f} s ({speed:.2f}x real time for {audio:.1f} s of raw voice, "
                    f"model load {t['tts_load_s']:.0f} s), aligned in {t['align_wall_s']:.0f} s; pace {outputs['pace']['wpm']} wpm after tightening "
                    f"({outputs['pace']['wpm_speech_only']} on speech alone)")
        hook2_text = f"; vo_hook2.wav {outputs['hook2']['duration_s']:.1f} s" if outputs["hook2"] else ""
        loud = outputs["loud"]
        say("INFO", f"S8: vo.wav {outputs['duration_s']:.1f} s at {loud.get('lufs')} LUFS, true peak {loud.get('true_peak_dbtp')} dBTP "
                    f"({loud.get('passes')} passes); words.json {outputs['words']} words, {len([ln for ln in self.lines if ln['kind'] == 'beat'])} beats{hook2_text}")
        if verdict["status"] == "block":
            log(f"block: {verdict['reason']}")
            return 20
        log(f"done ({verdict['status']}) in {t['total_s']:.0f} s")
        return 0


# ------------------------------------------------------------------------------------------------ CLI
def cmd_run(args) -> int:
    return Stage(args).run()


def cmd_wer(args) -> int:
    rep = wer_report(args.ref, args.hyp)
    out_json({k: rep[k] for k in ("wer_pct", "errors", "n", "misheard", "heard")})
    return 0


def cmd_pronounce(args) -> int:
    entries = read_pronunciations(args.file) if args.file else []
    respell = {}
    for item in args.respell or []:
        w, _, s = item.partition("=")
        if w and s:
            respell[w.strip()] = s.strip()
    text, applied = tts_text(args.text, entries, respell)
    out_json({"text": text, "applied": applied, "words": n_words(args.text)})
    return 0


def cmd_respell(args) -> int:
    sys.stdout.write(auto_respell(args.word) + "\n")
    return 0


def cmd_silences(args) -> int:
    runs = [r for r in silent_runs(args.wav, args.threshold_db) if r["seconds"] >= args.min_s]
    out_json({"wav": args.wav, "duration_s": round(wav_duration(args.wav), 3), "threshold_db": args.threshold_db, "runs": runs,
              "longest_s": max((r["seconds"] for r in runs), default=0.0)})
    return 0


def cmd_energy(args) -> int:
    sys.stdout.write(f"{window_db(args.wav, args.from_ms, args.to_ms):.1f}\n")
    return 0


def cmd_measure(args) -> int:
    out_json(ffmpeg_measure(args.wav, -14.0, -1.5))
    return 0


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default="")
    p.add_argument("--root", default="")
    p.add_argument("--repo", default="")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("engine"); sp.add_argument("--brief", action="store_true"); sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_engine)
    sp = sub.add_parser("engine-check"); sp.set_defaults(func=cmd_engine_check)
    sp = sub.add_parser("run"); sp.add_argument("run_dir"); sp.add_argument("--stage-dir", default=""); sp.add_argument("--s7", default="")
    sp.set_defaults(func=cmd_run)
    sp = sub.add_parser("wer"); sp.add_argument("--ref", required=True); sp.add_argument("--hyp", required=True); sp.set_defaults(func=cmd_wer)
    sp = sub.add_parser("pronounce"); sp.add_argument("--text", required=True); sp.add_argument("--file", default="")
    sp.add_argument("--respell", action="append"); sp.set_defaults(func=cmd_pronounce)
    sp = sub.add_parser("respell"); sp.add_argument("word"); sp.set_defaults(func=cmd_respell)
    sp = sub.add_parser("silences"); sp.add_argument("--wav", required=True); sp.add_argument("--threshold-db", type=float, default=-40.0)
    sp.add_argument("--min-s", type=float, default=0.0); sp.set_defaults(func=cmd_silences)
    sp = sub.add_parser("energy"); sp.add_argument("--wav", required=True); sp.add_argument("--from-ms", type=float, required=True)
    sp.add_argument("--to-ms", type=float, required=True); sp.set_defaults(func=cmd_energy)
    sp = sub.add_parser("measure"); sp.add_argument("--wav", required=True); sp.set_defaults(func=cmd_measure)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
