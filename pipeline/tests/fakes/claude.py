#!/usr/bin/env python
"""The fake claude CLI used by the tests (placed first on PATH as pipeline/tests/fakes/claude).

It accepts the flags ai() passes (-p, --model, --effort, --output-format json, --permission-mode,
--permission-prompts, --resume, --json-schema, --allowedTools, --disallowedTools, --tools, --add-dir,
--max-turns), reads the prompt from the arguments or stdin, appends one JSON line per call to FAKE_CLAUDE_LOG and
answers according to a mode. No model is ever called.

Mode selection:
  FAKE_CLAUDE_SCRIPT=<file>   one mode per line, consumed in order (blank lines and # comments skipped); after the
                              last line the last mode repeats. The position is kept in FAKE_CLAUDE_STATE/script.n.
  FAKE_CLAUDE_MODE=<mode>     otherwise this mode for every call (default: auto)
  FAKE_CLAUDE_STATE=<dir>     counters (default: next to the log, else the system temp folder)

Modes:
  ok | ok:<text>              a success result ("ok" or the text)
  echo                        a success result whose text is the prompt (tests that the prompt arrived)
  auto                        by role: a prompt starting with "# Role: reviewer" answers like a reviewer
                              (FAKE_CLAUDE_REVIEW = yes | no | verify-fails | yes:<verify command>), "# Role: fixer"
                              like a fixer (FAKE_CLAUDE_FIX = ok | fail), anything else "ok"
  review:<policy>, fix:<policy>   the same answers, forced
  limit:<fmt>[:<channel>]     a usage limit. fmt: time ("resets 3:45pm"), time-tz ("resets 3pm (Europe/Rome)"),
                              time-tz-ny ("resets 3pm (America/New_York)"), weekday ("weekly limit, resets Mon
                              12:00am"), date ("resets Nov 3, 10am"), epoch ("usage limit reached|<epoch>"),
                              unparsed ("Try again later."), and the relative forms time+<minutes>, date+<days>,
                              epoch+<minutes> (the moment is now plus that, logged as limit_epoch). channel: json
                              (default: an is_error result), stderr (the text on stderr), plain (no JSON at all).
                              Outside a script the limit fires once and later calls answer ok (FAKE_CLAUDE_REPEAT=1
                              keeps it firing).
  transient[:<n>]             n failures (default 1) with an overloaded 529 result, then ok (counted per mode)
  transient-stderr[:<n>]      n failures with "fetch failed: ECONNRESET" on stderr and no JSON, then ok
  hang[:<seconds>]            sleep (default 600 s) for the timeout tests
  bad-json                    a structured_output that does not match the schema (ai()'s schema retry)
  error:<text>                an is_error result with the text (a code error)
  fatal                       "Not logged in. Please run /login" on stderr, exit 1
  resume-missing              "No conversation found with session ID: <id>" on stderr, exit 1
  fixture:<file>              the file's content as the result (parsed as structured_output when it is JSON)
  tamper                      append a line to FAKE_CLAUDE_TAMPER_FILE, then ok (the protected files guard)
Exit 0 on a success result, 1 on an error.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta

VARIADIC = {"--allowedTools": "allowed", "--allowed-tools": "allowed", "--disallowedTools": "disallowed",
            "--disallowed-tools": "disallowed", "--tools": "tools", "--add-dir": "add_dir"}
SINGLE = {"--model", "--effort", "--output-format", "--permission-mode", "--permission-prompts", "--resume", "-r",
          "--json-schema", "--max-turns", "--session-id", "--append-system-prompt", "--system-prompt",
          "--max-budget-usd", "--fallback-model", "--settings", "--agent", "--name", "-n"}
FLAGS = {"-p", "--print", "--verbose", "--bare", "--no-session-persistence", "--strict-mcp-config", "--restricted",
         "--include-partial-messages", "-c", "--continue"}


def setup_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass


def parse_args(argv: list[str]):
    opts: dict = {"allowed": [], "disallowed": [], "tools": [], "add_dir": []}
    positional: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in VARIADIC:
            key = VARIADIC[a]
            i += 1
            while i < len(argv) and not (argv[i].startswith("-") and len(argv[i]) > 1):
                opts[key].append(argv[i])
                i += 1
        elif a in SINGLE:
            opts[a.lstrip("-")] = argv[i + 1] if i + 1 < len(argv) else ""
            i += 2
        elif a in FLAGS:
            i += 1
        elif a.startswith("--") and "=" in a:
            k, v = a[2:].split("=", 1)
            opts[k] = v
            i += 1
        else:
            positional.append(a)
            i += 1
    return opts, positional


def winpath(path: str) -> str:
    """/c/Users/... from Git Bash -> C:/Users/... for Windows Python (/tmp/... stays as bash gave it)."""
    m = re.match(r"^/([A-Za-z])/(.*)$", path or "")
    return f"{m.group(1).upper()}:/{m.group(2)}" if (m and os.name == "nt") else path


def state_dir() -> str:
    d = winpath(os.environ.get("FAKE_CLAUDE_STATE", ""))
    if not d:
        log = winpath(os.environ.get("FAKE_CLAUDE_LOG", ""))
        d = os.path.join(os.path.dirname(log), "fake-claude-state") if log else os.path.join(tempfile.gettempdir(), "fake-claude-state")
    os.makedirs(d, exist_ok=True)
    return d


def counter(name: str) -> int:
    """Increment a named counter; return its value before the increment."""
    path = os.path.join(state_dir(), re.sub(r"[^A-Za-z0-9_.-]", "_", name) + ".n")
    try:
        with open(path, encoding="utf-8") as f:
            n = int(f.read().strip() or 0)
    except (OSError, ValueError):
        n = 0
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(n + 1))
    return n


def pick_mode() -> tuple[str, bool]:
    script = os.environ.get("FAKE_CLAUDE_SCRIPT")
    if script and os.path.isfile(script):
        with open(script, encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]
        if lines:
            n = counter("script")
            return lines[min(n, len(lines) - 1)], True
    return os.environ.get("FAKE_CLAUDE_MODE", "auto"), False


def fmt_time(dt: datetime) -> str:
    hour = dt.hour % 12 or 12
    ap = "am" if dt.hour < 12 else "pm"
    return f"{hour}:{dt.minute:02d}{ap}" if dt.minute else f"{hour}{ap}"


def limit_message(fmt: str) -> tuple[str, int | None]:
    now = datetime.now()
    m = re.match(r"^(time|date|epoch)\+(\d+)$", fmt)
    if m:
        kind, n = m.group(1), int(m.group(2))
        if kind == "time":
            when = (now + timedelta(minutes=n)).replace(second=0, microsecond=0)
            return f"You've hit your session limit · resets {fmt_time(when)}", int(when.timestamp())
        if kind == "date":
            when = (now + timedelta(days=n)).replace(hour=10, minute=0, second=0, microsecond=0)
            return f"You've hit your session limit · resets {when.strftime('%b')} {when.day}, {fmt_time(when)}", int(when.timestamp())
        epoch = int(now.timestamp()) + n * 60
        return f"Claude AI usage limit reached|{epoch}", epoch
    table = {
        "time": "You've hit your session limit · resets 3:45pm",
        "time-tz": "You've hit your limit · resets 3pm (Europe/Rome)",
        "time-tz-ny": "You've hit your limit · resets 3pm (America/New_York)",
        "weekday": "You've hit your weekly limit · resets Mon 12:00am",
        "weekly": "You've hit your weekly limit · resets Mon 12:00am",
        "date": "You've hit your session limit · resets Nov 3, 10am",
        "epoch": "Claude AI usage limit reached|1793696400",
        "unparsed": "You've hit your usage limit. Try again later.",
    }
    return table.get(fmt, table["time"]), None


def emit(text: str, *, structured=None, is_error=False, status=None, sid: str, extra: dict | None = None) -> None:
    d = {
        "type": "result", "subtype": "success" if not is_error else "error_during_execution", "is_error": is_error,
        "duration_ms": 12, "duration_api_ms": 8, "num_turns": 1, "result": text, "session_id": sid,
        "total_cost_usd": 0.0, "usage": {"input_tokens": 1, "output_tokens": 1}, "permission_denials": [],
        "api_error_status": status, "terminal_reason": "completed" if not is_error else "api_error",
        "uuid": str(uuid.uuid4()), "fake": True,
    }
    if structured is not None:
        d["structured_output"] = structured
    if extra:
        d.update(extra)
    sys.stdout.write(json.dumps(d, ensure_ascii=False) + "\n")


def role_of(prompt: str) -> str:
    m = re.match(r"^\s*# Role: (\w+)", prompt)
    return m.group(1).lower() if m else ""


def stage_of(prompt: str) -> str:
    m = re.search(r"^- stage: (\S+)", prompt, re.M)
    return m.group(1) if m else "10-build"


def error_head(prompt: str) -> str:
    m = re.search(r"^- error: (.+)$", prompt, re.M)
    return m.group(1).strip()[:120] if m else "the stage failed"


def review_answer(policy: str, prompt: str) -> dict:
    stage = stage_of(prompt)
    head = error_head(prompt)
    verify = "true"
    if policy.startswith("yes:"):
        verify = policy[4:]
        policy = "yes"
    if policy == "no":
        return {"root_cause": f"fake reviewer: {head}; the stage needs a file only the user can create",
                "class": "environment problem", "changes": [],
                "verify_command": f"test -f library/keys/service.key",
                "auto_apply": "no",
                "user_action": "create library/keys/service.key with your API key (fake reviewer)",
                "summary": "needs the user's key file (fake reviewer)"}
    if policy == "verify-fails":
        verify = "false"
    return {"root_cause": f"fake reviewer: {head}",
            "class": "pipeline bug",
            "changes": [{"file": f"pipeline/stages/{stage}/run.sh", "change": "no real change (fake reviewer)"}],
            "verify_command": verify, "auto_apply": "yes", "user_action": "",
            "summary": f"fake fix for {stage} (nothing changed)"}


def fix_answer(policy: str, prompt: str) -> dict:
    if policy == "fail":
        return {"applied": False, "verify_passed": False, "files_changed": [], "summary": "fake fixer: could not apply",
                "known_issue": "fake symptom -> fake fixer gave up", "notes": "fake"}
    return {"applied": True, "verify_passed": True, "files_changed": [], "summary": "fake fixer applied the fix",
            "known_issue": f"{error_head(prompt)[:60]} -> fake fix", "notes": "fake"}


def main(argv: list[str]) -> int:
    setup_streams()
    opts, positional = parse_args(argv)
    prompt = " ".join(positional)
    if not prompt and not sys.stdin.isatty():
        prompt = sys.stdin.read()
    mode, scripted = pick_mode()
    role = role_of(prompt)
    sid = opts.get("resume") or f"fake-{uuid.uuid4()}"
    schema = opts.get("json-schema")
    n = counter("calls") + 1
    record = {"n": n, "mode": mode, "role": role, "model": opts.get("model"), "effort": opts.get("effort"),
              "resume": opts.get("resume"), "schema": bool(schema), "tools": opts["tools"], "allowed": opts["allowed"],
              "disallowed": opts["disallowed"], "add_dir": opts["add_dir"], "max_turns": opts.get("max-turns"),
              "prompt_len": len(prompt), "prompt_head": prompt[:200], "cwd": os.getcwd().replace("\\", "/"),
              "limit_epoch": None, "at": int(time.time())}

    def log() -> None:
        path = winpath(os.environ.get("FAKE_CLAUDE_LOG", ""))
        if path:
            with open(path, "a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    if mode == "auto":
        if role == "reviewer":
            mode = "review:" + os.environ.get("FAKE_CLAUDE_REVIEW", "yes")
        elif role == "fixer":
            mode = "fix:" + os.environ.get("FAKE_CLAUDE_FIX", "ok")
        else:
            mode = "ok"
        record["mode"] = mode

    kind, _, arg = mode.partition(":")

    if kind == "limit":
        fmt, _, channel = arg.partition(":")
        fmt = fmt or "time"
        channel = channel or "json"
        if not scripted and not os.environ.get("FAKE_CLAUDE_REPEAT") and counter("limit:" + fmt) >= 1:
            kind, arg = "ok", ""
        else:
            text, epoch = limit_message(fmt)
            record["limit_epoch"] = epoch
            record["limit_text"] = text
            log()
            if channel == "stderr":
                emit("Error: the request failed", is_error=True, sid=sid)
                sys.stderr.write(text + "\n")
            elif channel == "plain":
                sys.stdout.write(text + "\n")
            else:
                emit(text, is_error=True, sid=sid)
            return 1

    if kind in ("transient", "transient-stderr"):
        times = int(arg or 1)
        if counter(kind + ":" + str(times)) < times:
            log()
            if kind == "transient":
                emit('API Error: 529 {"type":"error","error":{"type":"overloaded_error","message":"Overloaded"}}',
                     is_error=True, status=529, sid=sid)
            else:
                sys.stderr.write("TypeError: fetch failed\n    cause: Error: read ECONNRESET\n")
            return 1
        kind, arg = "ok", ""

    if kind == "hang":
        log()
        time.sleep(float(arg or 600))
        emit("ok after the hang", sid=sid)
        return 0

    if kind == "fatal":
        log()
        sys.stderr.write("Not logged in · Please run /login\n")
        return 1

    if kind == "resume-missing":
        log()
        sys.stderr.write(f"No conversation found with session ID: {opts.get('resume') or 'unknown'}\n")
        return 1

    if kind == "error":
        log()
        emit(arg or "Error: something went wrong in the fake", is_error=True, sid=sid)
        return 1

    if kind == "tamper":
        target = winpath(os.environ.get("FAKE_CLAUDE_TAMPER_FILE", ""))
        if target:
            with open(target, "a", encoding="utf-8", newline="\n") as f:
                f.write("tampered by the fake claude\n")
        log()
        emit("tampered", sid=sid)
        return 0

    log()
    if kind == "echo":
        emit(prompt, sid=sid)
        return 0
    if kind == "bad-json":
        bad = {"this_is_not": "what the schema asked for"}
        emit(json.dumps(bad), structured=bad if schema else None, sid=sid)
        return 0
    if kind == "fixture":
        with open(winpath(arg), encoding="utf-8-sig") as f:
            content = f.read()
        structured = None
        if schema:
            try:
                structured = json.loads(content)
            except ValueError:
                structured = None
        emit(content, structured=structured, sid=sid)
        return 0
    if kind == "review":
        answer = review_answer(arg or "yes", prompt)
        emit(json.dumps(answer, ensure_ascii=False), structured=answer if schema else None, sid=sid)
        return 0
    if kind == "fix":
        answer = fix_answer(arg or "ok", prompt)
        emit(json.dumps(answer, ensure_ascii=False), structured=answer if schema else None, sid=sid)
        return 0
    text = arg if (kind == "ok" and arg) else "ok"
    structured = {"ok": True, "text": text} if schema else None
    emit(text, structured=structured, sid=sid)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
