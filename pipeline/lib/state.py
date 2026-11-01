#!/usr/bin/env python
"""Run state: runs/<YYYY-MM-DD_HHMM>_<slug>/state.json (BUILD_SPEC.md section 3, PLAN.md M2).

One run folder per idea, with state.json and one subfolder per stage. The runner (pipeline/lib/runner.sh) calls
this script for every state change; bash never edits state.json itself. Every write is atomic (temp file in the
same folder, then os.replace, retried because OneDrive briefly holds handles), and every command that may write
holds the exclusive lock <run>/state.lock from its load to its save (StateLock: an OS file lock, released by the
OS when the holder exits), because two processes write state.json while a stage runs: the stage (flag, issue,
round, set) and the runner's heartbeat (touch). Read-only commands (summary, get, unfinished) take no lock:
os.replace keeps every read whole. export.py takes the same lock for its export record.

Stage table (the single source of truth for the stage order, labels, default activity text and primary output):
  key              label  activity                      output         initial status
  01-research      S1     researching facts             research.json  pending
  ...              (see STAGES below)
04-angle starts as "skipped": the gate reopens it only when an angle round is needed. A stage that wants other
stages to run again after it writes their keys, one per line, to <run>/<stage>/reopen.txt: "stage-done" reopens
them (status pending, .done removed, attempts back to 0 for the new round, the round counted in "reopened") in
the same write that marks the stage done, so a crash between the two cannot leave the run half-way (the gate names 04-angle, the angle stage names 03-gate, M4; the review loop of
M11 names the owner of each issue, every stage after it and itself). "stage-start" removes a reopen.txt left by an earlier attempt.

A stage is done when its primary JSON output validates against pipeline/stages/<stage>/schema.json and the
marker <run>/<stage>/.done exists (both written by "stage-done"). "next" re-checks the marker, so a stage whose
marker vanished runs again. Status values per stage: pending, running, done, failed, skipped.

Usage:
  state.py stages                                       the table, one line per stage: key, label, activity, output,
                                                        initial status (tab separated)
  state.py new --runs DIR --id ID [--source NAME]       create a run for the idea text given on stdin; prints JSON
                                                        {run_dir, run_id}
  state.py unfinished --runs DIR                        JSON list of unfinished runs (status running), oldest first;
                                                        exit 3 when there is none
  state.py pickup RUN_DIR                               session accounting at start or resume; prints the summary
  state.py summary RUN_DIR                              JSON: idea, status, elapsed, counters, next phase
  state.py next RUN_DIR                                 JSON {phase: stage|export|finalize|finished, stage, ...}
  state.py stage-start RUN_DIR STAGE [--pid N]          mark running, attempts + 1; prints JSON {attempts, started}
  state.py stage-done RUN_DIR STAGE --schemas DIR       validate the output, write .done, mark done, reopen the
                                                        stages named in <stage>/reopen.txt; prints JSON
                                                        {ok, errors, seconds, next_stage, next_activity, reopened, ...}
  state.py stage-fail RUN_DIR STAGE --exit N [--reason TEXT]
  state.py reopen RUN_DIR STAGE...                      back to pending (removes .done), for the gate and review loops
  state.py flag RUN_DIR STAGE TEXT                      append a NEEDS REVIEW flag
  state.py issue RUN_DIR fixed|open DELTA               issue counters for the heartbeat
  state.py round RUN_DIR NAME [VALUE]                   read or set a round counter (angle, script, review_opus, ...)
  state.py get RUN_DIR KEY [DEFAULT]                    dotted key, scalars as text, lists and objects as JSON
  state.py set RUN_DIR KEY=JSON ...                     dotted keys, JSON values (bare text is taken as a string)
  state.py touch RUN_DIR                                refresh last_seen (the heartbeat calls it)
  state.py finish RUN_DIR exported|dropped|blocked --reason TEXT [--stage S] [--number N]
  state.py slug TEXT                                    the slug used in run folder names

Exit codes: 0 ok, 1 usage, 2 state file error (state.lock busy for REELS_STATE_LOCK_WAIT seconds included,
default 30), 3 not found or nothing to do, 5 validation failed (stage-done).
JSON on stdout. Paths may be C:/... or /c/... (both work).
"""
from __future__ import annotations

import argparse
import errno
import functools
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime

VERSION = 1
REPLACE_TRIES = 5
LOCK_WAIT_S = 30.0       # how long a writer waits for state.lock (REELS_STATE_LOCK_WAIT overrides it, in seconds)
LOCK_POLL_S = 0.02
LOCK_BUSY_ERRNOS = (errno.EACCES, errno.EAGAIN, errno.EDEADLOCK, errno.EPERM)

# key, label, default activity, primary output, initial status
STAGES = [
    ("01-research", "S1", "researching facts", "research.json", "pending"),
    ("02-expansion", "S2", "expanding idea", "expansion.json", "pending"),
    ("03-gate", "S3", "checking idea (gate)", "gate.json", "pending"),
    ("04-angle", "S4", "finding a better angle", "angle.json", "skipped"),
    ("05-hooks", "S5", "picking hooks", "hooks.json", "pending"),
    ("06-judge", "S6", "judging hooks", "judge.json", "pending"),
    ("07-script", "S7", "writing script", "script.json", "pending"),
    ("08-voiceover", "S8", "generating voiceover", "words.json", "pending"),
    ("09a-animations", "S9a", "planning animations", "plan.json", "pending"),
    ("09b-text", "S9b", "planning text", "plan.json", "pending"),
    ("09c-transitions", "S9c", "planning transitions", "plan.json", "pending"),
    ("10-build", "S10", "building visuals", "events.json", "pending"),
    ("11-sfx", "S11", "adding sound effects", "cues.json", "pending"),
    ("12-review", "S12", "reviewing: mechanical checks", "review.json", "pending"),
    ("13-render", "S13", "rendering final video", "render.json", "pending"),
    ("14-export", "S14", "writing caption", "export.json", "pending"),
]
STAGE_BY_KEY = {s[0]: s for s in STAGES}
ROUNDS = ("angle", "script", "review_opus", "review_fable")


class StateError(Exception):
    """A problem with the run folder or state.json (exit 2)."""


def winpath(path: str) -> str:
    """Accept /c/Users/... from Git Bash as well as C:/Users/...; Windows Python needs the latter."""
    m = re.match(r"^/([A-Za-z])/(.*)$", path)
    if m and os.name == "nt":
        return f"{m.group(1).upper()}:/{m.group(2)}"
    return path


def now_epoch() -> int:
    return int(time.time())


def iso(epoch) -> str:
    return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M") if epoch else ""


def normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFC", text)
    return " ".join(text.split())


def slug_of(text: str, words: int = 5, max_len: int = 40) -> str:
    plain = text.replace("'", "").replace("\u2019", "")
    plain = unicodedata.normalize("NFKD", plain).encode("ascii", "ignore").decode("ascii")
    parts = re.findall(r"[A-Za-z0-9]+", plain)
    slug = "-".join(p.lower() for p in parts[:words])[:max_len].strip("-")
    return slug or "idea"


def state_path(run_dir: str) -> str:
    return os.path.join(run_dir, "state.json").replace("\\", "/")  # one separator style in every message and log


def load(run_dir: str) -> dict:
    path = state_path(run_dir)
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except FileNotFoundError as exc:
        raise StateError(f"no state.json in {run_dir}") from exc
    except (OSError, ValueError) as exc:
        raise StateError(f"cannot read {path}: {exc}") from exc


def save(run_dir: str, state: dict) -> None:
    state["updated"] = now_epoch()
    state["updated_iso"] = iso(state["updated"])
    path = state_path(run_dir)
    tmp = f"{path}.tmp.{os.getpid()}"
    data = json.dumps(state, ensure_ascii=False, indent=2) + "\n"
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        for attempt in range(REPLACE_TRIES):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == REPLACE_TRIES - 1:
                    raise
                time.sleep(0.2)
    except OSError as exc:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise StateError(f"cannot write {path}: {exc}") from exc


def lock_wait_seconds() -> float:
    try:
        return float(os.environ.get("REELS_STATE_LOCK_WAIT") or LOCK_WAIT_S)
    except ValueError:
        return LOCK_WAIT_S


class StateLock:
    """The exclusive lock on <run_dir>/state.lock that every command changing state.json holds from its load to
    its save. It is an OS file lock (msvcrt.locking on Windows, fcntl.flock elsewhere) on one byte of a file that
    is never written, so the OS releases it when the holder exits, a kill -9 included: no stale lock to clean up.
    Without it two processes (the stage's flag and the heartbeat's touch, for example) each load, change and save
    the file, and the later save silently drops the earlier change. A waiter polls every LOCK_POLL_S seconds and
    gives up with a StateError (exit 2) after wait_s seconds; EACCES at os.open (OneDrive or an antivirus holding
    the lock file) is retried the same way."""

    def __init__(self, run_dir: str, wait_s: float | None = None):
        self.run_dir = run_dir
        self.path = os.path.join(run_dir, "state.lock").replace("\\", "/")
        self.wait_s = lock_wait_seconds() if wait_s is None else wait_s
        self.fd = None

    def __enter__(self) -> "StateLock":
        if not os.path.isfile(state_path(self.run_dir)):
            raise StateError(f"no state.json in {self.run_dir}")
        deadline = time.monotonic() + self.wait_s
        while True:
            try:
                if self.fd is None:
                    self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o666)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(self.fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError as exc:
                if exc.errno not in LOCK_BUSY_ERRNOS:
                    self._close()
                    raise StateError(f"cannot lock {self.path}: {exc}") from exc
                if time.monotonic() > deadline:
                    self._close()
                    raise StateError(f"the lock {self.path} stayed busy for {self.wait_s:g}s ({exc})") from exc
                time.sleep(LOCK_POLL_S)

    def __exit__(self, *exc) -> None:
        if self.fd is not None:
            try:
                if os.name == "nt":
                    import msvcrt
                    os.lseek(self.fd, 0, os.SEEK_SET)
                    msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.fd, fcntl.LOCK_UN)
            except OSError:
                pass
        self._close()

    def _close(self) -> None:
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None


def locked(func):
    """Run a command under the StateLock of its run folder: every command that may write state.json."""
    @functools.wraps(func)
    def wrapper(args):
        with StateLock(args.run_dir):
            return func(args)
    return wrapper


def emit(payload) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def new_stage_record(initial: str) -> dict:
    return {"status": initial, "attempts": 0, "started": None, "finished": None, "seconds": 0,
            "session_id": None, "exit_code": None, "error": None, "pid": None}


def stage_info(key: str) -> dict:
    _, label, activity, output, initial = STAGE_BY_KEY[key]
    return {"stage": key, "label": label, "activity": activity, "output": output, "initial": initial}


def elapsed_seconds(state: dict, now: int | None = None) -> int:
    now = now or now_epoch()
    timing = state.get("timing", {})
    started = timing.get("session_started") or state.get("created") or now
    return int(timing.get("accumulated", 0)) + max(0, now - int(started))


def first_open_stage(state: dict, run_dir: str) -> str | None:
    """The first stage that still has to run. A done stage without its .done marker is reopened."""
    for key in state["stage_order"]:
        rec = state["stages"][key]
        if rec["status"] == "done" and not os.path.exists(os.path.join(run_dir, key, ".done")):
            rec["status"] = "pending"
            rec["error"] = "the .done marker was missing on resume; running the stage again"
        if rec["status"] in ("pending", "running", "failed"):
            return key
    return None


def next_phase(state: dict, run_dir: str) -> dict:
    if state.get("status") != "running":
        return {"phase": "finished", "status": state.get("status")}
    key = first_open_stage(state, run_dir)
    if key:
        rec = state["stages"][key]
        info = stage_info(key)
        info.update({"phase": "stage", "attempts": rec["attempts"], "stage_status": rec["status"],
                     "pid": rec.get("pid")})
        return info
    if state["export"].get("number") is None:
        return {"phase": "export"}
    return {"phase": "finalize", "number": state["export"]["number"]}


def summary(state: dict, run_dir: str, now: int | None = None) -> dict:
    now = now or now_epoch()
    done = sum(1 for k in state["stage_order"] if state["stages"][k]["status"] == "done")
    skipped = sum(1 for k in state["stage_order"] if state["stages"][k]["status"] == "skipped")
    nxt = next_phase(state, run_dir)
    return {
        "run_dir": run_dir.replace("\\", "/"),
        "run_id": state["run_id"],
        "idea_id": state["idea"]["id"],
        "idea_text": state["idea"]["text"],
        "idea_raw": state["idea"]["raw"],
        "status": state["status"],
        "created": state["created"],
        "elapsed": elapsed_seconds(state, now),
        "session_started": state["timing"]["session_started"],
        "accumulated": state["timing"]["accumulated"],
        "stages_done": done,
        "stages_skipped": skipped,
        "stages_total": len(state["stage_order"]),
        "issues_fixed": state["issues"]["fixed"],
        "issues_open": state["issues"]["open"],
        "flags": len(state["flags"]),
        "export_number": state["export"].get("number"),
        "next": nxt,
    }


def set_dotted(obj: dict, key: str, value) -> None:
    parts = key.split(".")
    cur = obj
    for part in parts[:-1]:
        if part not in cur or not isinstance(cur[part], dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value


def get_dotted(obj, key: str):
    cur = obj
    for part in key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            raise KeyError(key)
    return cur


# ---------------------------------------------------------------- commands

def cmd_stages(args) -> int:
    for key, label, activity, output, initial in STAGES:
        print("\t".join((key, label, activity, output, initial)))
    return 0


def cmd_slug(args) -> int:
    print(slug_of(args.text))
    return 0


def cmd_new(args) -> int:
    raw = sys.stdin.buffer.read().decode("utf-8-sig", errors="replace")
    raw = raw.replace("\r\n", "\n").replace("\r", "\n").strip()
    if raw.startswith("{") and raw.endswith("}") and raw.count("{") == 1:
        raw = raw[1:-1].strip()
    text = normalize(raw)
    if not text:
        print("state.py new: give the idea text on stdin", file=sys.stderr)
        return 1
    runs = args.runs
    os.makedirs(runs, exist_ok=True)
    now = now_epoch()
    base = f"{datetime.fromtimestamp(now):%Y-%m-%d_%H%M}_{slug_of(text)}"
    run_id = base
    n = 2
    while os.path.exists(os.path.join(runs, run_id)):
        run_id = f"{base}-{n}"
        n += 1
    run_dir = os.path.join(runs, run_id).replace("\\", "/")
    os.makedirs(run_dir)
    for key, *_ in STAGES:
        os.makedirs(os.path.join(run_dir, key), exist_ok=True)
    os.makedirs(os.path.join(run_dir, "errors"), exist_ok=True)
    os.makedirs(os.path.join(run_dir, "fixes"), exist_ok=True)
    state = {
        "version": VERSION,
        "run_id": run_id,
        "idea": {"id": args.id, "text": text, "raw": raw, "source": args.source},
        "status": "running",
        "created": now,
        "created_iso": iso(now),
        "timing": {"session_started": now, "accumulated": 0, "last_seen": now, "sessions": 1},
        "stage_order": [s[0] for s in STAGES],
        "stages": {s[0]: new_stage_record(s[4]) for s in STAGES},
        "current_stage": None,
        "flags": [],
        "issues": {"fixed": 0, "open": 0},
        "rounds": {name: 0 for name in ROUNDS},
        "sessions": {},
        "export": {"number": None, "intent": None, "assembled": False, "moved": False, "dir": None},
        "result": None,
    }
    save(run_dir, state)
    with open(os.path.join(run_dir, "idea.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(raw + "\n")
    emit({"run_dir": run_dir, "run_id": run_id, "idea_id": args.id})
    return 0


def cmd_unfinished(args) -> int:
    runs = args.runs
    found = []
    if os.path.isdir(runs):
        for name in sorted(os.listdir(runs)):
            run_dir = os.path.join(runs, name).replace("\\", "/")
            path = state_path(run_dir)
            if not os.path.isfile(path):
                continue
            try:
                with open(path, encoding="utf-8-sig") as f:
                    state = json.load(f)
            except (OSError, ValueError):
                print(f"state.py: warning: unreadable {path}, skipped", file=sys.stderr)
                continue
            if state.get("status") == "running":
                found.append({"run_dir": run_dir, "run_id": state.get("run_id", name),
                              "created": state.get("created", 0), "idea_id": state.get("idea", {}).get("id")})
    found.sort(key=lambda r: (r["created"], r["run_id"]))
    emit(found)
    return 0 if found else 3


@locked
def cmd_pickup(args) -> int:
    state = load(args.run_dir)
    now = now_epoch()
    timing = state["timing"]
    resumed = bool(state.get("picked_up"))
    if resumed:
        last_seen = max(int(timing.get("last_seen") or 0), int(state.get("updated") or 0))
        started = int(timing.get("session_started") or state["created"])
        timing["accumulated"] = int(timing.get("accumulated", 0)) + max(0, last_seen - started)
        timing["sessions"] = int(timing.get("sessions", 1)) + 1
    timing["session_started"] = now
    timing["last_seen"] = now
    state["picked_up"] = True
    # a stage left "running" by a crash is interrupted: it runs again (attempt + 1 at stage-start)
    for key in state["stage_order"]:
        rec = state["stages"][key]
        if rec["status"] == "running":
            rec["error"] = "interrupted (the runner stopped while this stage was running)"
    save(args.run_dir, state)
    out = summary(state, args.run_dir, now)
    out["resumed"] = resumed
    emit(out)
    return 0


def cmd_summary(args) -> int:
    state = load(args.run_dir)
    emit(summary(state, args.run_dir))
    return 0


@locked
def cmd_next(args) -> int:
    state = load(args.run_dir)
    before = json.dumps(state["stages"], sort_keys=True)
    nxt = next_phase(state, args.run_dir)
    if json.dumps(state["stages"], sort_keys=True) != before:
        save(args.run_dir, state)
    emit(nxt)
    return 0


@locked
def cmd_stage_start(args) -> int:
    state = load(args.run_dir)
    if args.stage not in state["stages"]:
        raise StateError(f"unknown stage {args.stage}")
    rec = state["stages"][args.stage]
    now = now_epoch()
    rec.update({"status": "running", "attempts": int(rec["attempts"]) + 1, "started": now, "finished": None,
                "exit_code": None, "error": None, "pid": args.pid})
    state["current_stage"] = args.stage
    state["timing"]["last_seen"] = now
    os.makedirs(os.path.join(args.run_dir, args.stage), exist_ok=True)
    done_marker = os.path.join(args.run_dir, args.stage, ".done")
    if os.path.exists(done_marker):
        os.remove(done_marker)
    stale = os.path.join(args.run_dir, args.stage, "reopen.txt")
    if os.path.exists(stale):
        os.remove(stale)
    save(args.run_dir, state)
    out = stage_info(args.stage)
    out.update({"attempts": rec["attempts"], "started": now})
    emit(out)
    return 0


def validate_output(schemas_dir: str, run_dir: str, stage: str) -> list[str]:
    output = STAGE_BY_KEY[stage][3]
    schema_path = os.path.join(schemas_dir, stage, "schema.json")
    out_path = os.path.join(run_dir, stage, output)
    if not os.path.isfile(schema_path):
        return [f"schema missing: {schema_path}"]
    if not os.path.isfile(out_path):
        return [f"output missing: {stage}/{output}"]
    try:
        with open(schema_path, encoding="utf-8-sig") as f:
            schema = json.load(f)
    except (OSError, ValueError) as exc:
        return [f"schema unreadable: {schema_path}: {exc}"]
    try:
        with open(out_path, encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        return [f"{stage}/{output}: not valid JSON: {exc}"]
    try:
        import jsonschema
    except ImportError:
        return ["the jsonschema package is missing: run bash pipeline/bin/setup-python"]
    cls = jsonschema.validators.validator_for(schema)
    errors = []
    for err in sorted(cls(schema).iter_errors(data), key=lambda e: [str(p) for p in e.absolute_path]):
        where = "/".join(str(p) for p in err.absolute_path) or "$"
        errors.append(f"{stage}/{output}: {where}: {err.message}")
    return errors


def reopen_stage(state: dict, run_dir: str, key: str) -> None:
    """Back to pending for another round: .done removed, attempts restart at 0 (the runner reads attempts as the
    tries of the current round), the round counted in "reopened"."""
    rec = state["stages"][key]
    rec.update({"status": "pending", "finished": None, "exit_code": None, "error": None, "pid": None,
                "attempts": 0, "reopened": int(rec.get("reopened") or 0) + 1})
    marker = os.path.join(run_dir, key, ".done")
    if os.path.exists(marker):
        os.remove(marker)


def apply_reopen_file(state: dict, run_dir: str, stage: str) -> list[str]:
    """Reopen the stages named in <stage>/reopen.txt (one key per line) and remove the file. The caller saves."""
    path = os.path.join(run_dir, stage, "reopen.txt")
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8-sig") as f:
            wanted = [line.strip() for line in f if line.strip()]
    except OSError:
        wanted = []
    reopened = []
    for key in wanted:
        if key not in state["stages"]:
            print(f"state.py: {stage}/reopen.txt names {key!r}, which is not a stage; ignored", file=sys.stderr)
            continue
        # a stage may name itself (the review loop of M11 reopens 12-review with the steps it routes to): it is
        # marked done first, then pending again for the next round, in the same write
        reopen_stage(state, run_dir, key)
        reopened.append(key)
    try:
        os.remove(path)
    except OSError:
        pass
    return reopened


@locked
def cmd_stage_done(args) -> int:
    state = load(args.run_dir)
    if args.stage not in state["stages"]:
        raise StateError(f"unknown stage {args.stage}")
    rec = state["stages"][args.stage]
    now = now_epoch()
    errors = validate_output(args.schemas, args.run_dir, args.stage)
    seconds = max(0, now - int(rec.get("started") or now))
    if errors:
        rec.update({"status": "failed", "finished": now, "seconds": seconds, "exit_code": args.exit_code,
                    "error": "output invalid: " + "; ".join(errors)[:1000], "pid": None})
        state["timing"]["last_seen"] = now
        save(args.run_dir, state)
        emit({"ok": False, "errors": errors, "seconds": seconds})
        return 5
    with open(os.path.join(args.run_dir, args.stage, ".done"), "w", encoding="utf-8", newline="\n") as f:
        f.write(f"{iso(now)} attempt {rec['attempts']} {seconds}s\n")
    rec.update({"status": "done", "finished": now, "seconds": seconds, "exit_code": args.exit_code,
                "error": None, "pid": None})
    state["current_stage"] = None
    state["timing"]["last_seen"] = now
    reopened = apply_reopen_file(state, args.run_dir, args.stage)
    nxt = next_phase(state, args.run_dir)
    save(args.run_dir, state)
    emit({"ok": True, "errors": [], "seconds": seconds, "attempts": rec["attempts"], "reopened": reopened,
          "next_phase": nxt["phase"], "next_stage": nxt.get("stage"), "next_activity": nxt.get("activity"),
          "next_label": nxt.get("label"), "next_attempts": nxt.get("attempts", 0),
          "export_number": state["export"].get("number"),
          "issues_fixed": state["issues"]["fixed"], "issues_open": state["issues"]["open"],
          "elapsed": elapsed_seconds(state, now)})
    return 0


@locked
def cmd_stage_fail(args) -> int:
    state = load(args.run_dir)
    if args.stage not in state["stages"]:
        raise StateError(f"unknown stage {args.stage}")
    rec = state["stages"][args.stage]
    now = now_epoch()
    seconds = max(0, now - int(rec.get("started") or now))
    rec.update({"status": "failed", "finished": now, "seconds": seconds, "exit_code": args.exit_code,
                "error": (args.reason or f"exit {args.exit_code}")[:1000], "pid": None})
    state["timing"]["last_seen"] = now
    save(args.run_dir, state)
    emit({"ok": False, "seconds": seconds, "attempts": rec["attempts"]})
    return 0


@locked
def cmd_reopen(args) -> int:
    state = load(args.run_dir)
    for stage in args.stages:
        if stage not in state["stages"]:
            raise StateError(f"unknown stage {stage}")
        reopen_stage(state, args.run_dir, stage)
    save(args.run_dir, state)
    emit({"reopened": args.stages, "next": next_phase(state, args.run_dir)})
    return 0


@locked
def cmd_flag(args) -> int:
    state = load(args.run_dir)
    now = now_epoch()
    state["flags"].append({"stage": args.stage, "text": args.text, "at": now, "at_iso": iso(now)})
    save(args.run_dir, state)
    emit({"flags": len(state["flags"])})
    return 0


@locked
def cmd_issue(args) -> int:
    state = load(args.run_dir)
    state["issues"][args.kind] = max(0, int(state["issues"][args.kind]) + int(args.delta))
    save(args.run_dir, state)
    emit(state["issues"])
    return 0


@locked
def cmd_round(args) -> int:
    state = load(args.run_dir)
    if args.value is not None:
        state["rounds"][args.name] = int(args.value)
        save(args.run_dir, state)
    print(state["rounds"].get(args.name, 0))
    return 0


def parse_value(text: str):
    try:
        return json.loads(text)
    except ValueError:
        return text


@locked
def cmd_set(args) -> int:
    state = load(args.run_dir)
    for pair in args.pairs:
        if "=" not in pair:
            print(f"state.py set: expected KEY=VALUE, got {pair!r}", file=sys.stderr)
            return 1
        key, value = pair.split("=", 1)
        set_dotted(state, key, parse_value(value))
    save(args.run_dir, state)
    emit({"ok": True})
    return 0


def cmd_get(args) -> int:
    state = load(args.run_dir)
    try:
        value = get_dotted(state, args.key)
    except KeyError:
        if args.default is not None:
            print(args.default)
            return 0
        print(f"state.py get: no key {args.key}", file=sys.stderr)
        return 3
    if isinstance(value, bool):
        print("true" if value else "false")
    elif isinstance(value, (dict, list)):
        print(json.dumps(value, ensure_ascii=False))
    elif value is None:
        print("")
    else:
        print(value)
    return 0


@locked
def cmd_touch(args) -> int:
    state = load(args.run_dir)
    state["timing"]["last_seen"] = now_epoch()
    save(args.run_dir, state)
    return 0


@locked
def cmd_finish(args) -> int:
    state = load(args.run_dir)
    now = now_epoch()
    state["status"] = args.kind
    state["result"] = {"kind": args.kind, "reason": args.reason or "", "stage": args.stage,
                       "number": args.number, "at": now, "at_iso": iso(now),
                       "elapsed": elapsed_seconds(state, now)}
    state["current_stage"] = None
    state["timing"]["last_seen"] = now
    if args.number is not None:
        state["export"]["number"] = args.number
    save(args.run_dir, state)
    emit(state["result"])
    return 0


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows Python writes CRLF to pipes otherwise
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add(name, func, run_dir=True):
        sp = sub.add_parser(name)
        if run_dir:
            sp.add_argument("run_dir")
        sp.set_defaults(func=func)
        return sp

    add("stages", cmd_stages, run_dir=False)
    sp = add("slug", cmd_slug, run_dir=False); sp.add_argument("text")
    sp = add("new", cmd_new, run_dir=False)
    sp.add_argument("--runs", required=True); sp.add_argument("--id", required=True)
    sp.add_argument("--source", default="ideas.txt")
    sp = add("unfinished", cmd_unfinished, run_dir=False); sp.add_argument("--runs", required=True)
    add("pickup", cmd_pickup)
    add("summary", cmd_summary)
    add("next", cmd_next)
    sp = add("stage-start", cmd_stage_start); sp.add_argument("stage"); sp.add_argument("--pid", type=int)
    sp = add("stage-done", cmd_stage_done); sp.add_argument("stage")
    sp.add_argument("--schemas", required=True, help="pipeline/stages")
    sp.add_argument("--exit", dest="exit_code", type=int, default=0)
    sp = add("stage-fail", cmd_stage_fail); sp.add_argument("stage")
    sp.add_argument("--exit", dest="exit_code", type=int, required=True); sp.add_argument("--reason")
    sp = add("reopen", cmd_reopen); sp.add_argument("stages", nargs="+")
    sp = add("flag", cmd_flag); sp.add_argument("stage"); sp.add_argument("text")
    sp = add("issue", cmd_issue); sp.add_argument("kind", choices=("fixed", "open")); sp.add_argument("delta")
    sp = add("round", cmd_round); sp.add_argument("name"); sp.add_argument("value", nargs="?")
    sp = add("set", cmd_set); sp.add_argument("pairs", nargs="+")
    sp = add("get", cmd_get); sp.add_argument("key"); sp.add_argument("default", nargs="?")
    add("touch", cmd_touch)
    sp = add("finish", cmd_finish); sp.add_argument("kind", choices=("exported", "dropped", "blocked"))
    sp.add_argument("--reason"); sp.add_argument("--stage"); sp.add_argument("--number", type=int)

    args = parser.parse_args(argv)
    for attr in ("run_dir", "runs", "schemas"):
        if getattr(args, attr, None):
            setattr(args, attr, winpath(getattr(args, attr)))
    try:
        return args.func(args)
    except StateError as exc:
        print(f"state.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
