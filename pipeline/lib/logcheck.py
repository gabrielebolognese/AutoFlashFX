#!/usr/bin/env python
"""logcheck.py: check the runner's status lines and the story logs/runner.log tells (BUILD_SPEC.md sections 6 and 7,
PLAN.md M13). Used by pipeline/tests/test-m13.sh and pipeline/bin/doctor.

  logcheck.py line "TEXT"            exit 0 when TEXT is one valid status line ([HH:MM] TAG  details)
  logcheck.py status FILE            logs/status.txt: exactly one valid line whose tag may replace the status
  logcheck.py samples FILE           a sampler's file (one "epoch<TAB>content" per sample, content "<missing>" when
                                     status.txt did not exist yet): every sample after the first status is valid
  logcheck.py story LOG [LOG...] [--json OUT] [--allow-crash] [--live] [--no-gate-line] [--max-gap MIN]
                        [--heartbeat MIN]
                                     the timeline of logs/runner.log (several files: read in that order, as
                                     one timeline, so runner.log.2 runner.log.1 runner.log after a rotation), session by session (a session starts at the
                                     banner "START  reels autopilot v..."): every line valid; every idea STARTs,
                                     moves by STEP lines whose "-> next" is the next STEP's activity, has its GATE line
                                     before it goes past the gate, and ends with DONE, DROP or BLOCK (a session may
                                     end inside an idea only with --allow-crash, and the next session must START that
                                     idea again "resumed at" the stage it was in); NEXT announces the next idea with
                                     the same position; the heartbeat (REEL) has the right idea position, text,
                                     an activity of the table of spec section 7 (so has every STEP), minute, stage
                                     time and issue counters (ERROR and FIXED lines, plus S12's review issue: round 1
                                     failing opens one, a later round passing fixes it, read at the stage's end), and no idea goes silent for longer than
                                     --max-gap minutes (default the heartbeat plus 2); the exports are numbered 1, 2,
                                     3 ... without gaps; every LIMIT line is followed by its RESUME line; the last
                                     session ends with the summary (IDLE queue empty: this session E exported, D
                                     dropped, B blocked) whose counts match its DONE, DROP and BLOCK lines; no STOP.
                                     --live (the doctor, on a runner that may still be running): the log may end
                                     inside an idea and without the summary. --no-gate-line: a run with the
                                     dummy gate (REELS_DUMMY), which prints no GATE line.
                                     Prints a JSON report (sessions, ideas, exports, limits, problems); exit 1 when
                                     there is a problem.

Every check works on the minute stamps, so a time difference may be off by one minute either way.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

TAGS = {"REEL", "IDLE", "START", "STEP", "GATE", "ANGLE", "FLAG", "LIMIT", "RESUME", "RETRY", "ERROR", "FIXED",
        "ESCAL", "DONE", "DROP", "BLOCK", "NEW", "NEXT", "STOP", "INFO", "WARN", "QUEUE", "READY"}
NOT_STATUS = {"QUEUE", "INFO"}   # say() never writes these into status.txt
LINE_RE = re.compile(r"^\[(\d\d):(\d\d)\] ([A-Z]{2,6}) {1,5}(\S.*)$")
EM_DASH, EN_DASH = "\u2014", "\u2013"
ANSI_RE = re.compile(r"\x1b\[")
DUR_RE = r"(?:\d+h\d\dm|\d+m\d\ds|\d+s)"

REEL_RE = re.compile(r'^#idea (\d+)/(\d+) "(.*)" \| (.+) \| minute (\d+) \| stage (' + DUR_RE + r') \| issues: (\d+) fixed, (\d+) open$')
START_IDEA_RE = re.compile(r'^idea (\d+)/(\d+) "(.*)" -> runs/(\S+)( \(resumed at (.+), (\d+) stages? done\))?$')
STEP_RE = re.compile(r"^(.+) done \((" + DUR_RE + r")\) -> (.+)$")
DONE_RE = re.compile(r"^exported #(\d+) -> exports/(\d+)/ \((\d+ min|\d+s), (\d+) issues? fixed\)$")
DROP_RE = re.compile(r'^idea "(.*)" dropped: (.+)\. Removed from ideas\.txt$')
BLOCK_RE = re.compile(r'^idea "(.*)" blocked at (\S+): (.+)\. Moved to logs/blocked\.txt$')
NEXT_RE = re.compile(r'^idea (\d+)/(\d+) "(.*)"$')
SUMMARY_RE = re.compile(r"^queue empty: this session (\d+) exported, (\d+) dropped, (\d+) blocked in (" + DUR_RE +
                        r") \| today: (\d+) exported, (\d+) dropped(?:, (\d+) blocked)?$")
IDLE_RE = re.compile(r"^no ideas in ideas\.txt, checking every (\d+ min|\d+ s) \(idle (\d+) min\) \| today: \d+ exported, \d+ dropped(?:, \d+ blocked)?$")
LIMIT_RE = re.compile(r"^(\S+) limit hit, resuming at (\d\d:\d\d|\w{3} \d\d:\d\d) \(\+(\d+ min|\d+s) margin\)$")
LIMIT_UNPARSED_RE = re.compile(r"^(\S+) limit hit but no reset time found")
BANNER_RE = re.compile(r"^reels autopilot v\S+( \(\w+\))? \| queue: (\d+) ideas? \| style: (\S+) \| voice: (.+) \| sfx map: (.+)$")
GATE_RE = re.compile(r"^(passed|failed|dropped)?\s*\(?P(\d) S(\d) C(\d) F (ok|fail) H (ok|fail)\)?")


# the activity texts of spec section 7 (the table and the texts that replace the activity), as regexes; the part in
# parentheses is optional where the runner announces a stage by its base text before the stage itself adds the detail
ACTIVITIES = [re.compile("^(?:" + a + ")$") for a in (
    r"researching facts", r"expanding idea", r"checking idea \(gate\)", r"finding a better angle(?: \(round \d+/\d+\))?",
    r"picking hooks", r"judging hooks",
    r"writing script(?: \(draft \d+/\d+, round \d+/\d+\))?", r"cutting script", r"checking script",
    r"generating voiceover(?: \(beat \d+/\d+\))?", r"tightening silences", r"aligning words",
    r"fixing pronunciation \(line [\w ]+\)", r"rewriting line [\w ]+",
    r"planning animations", r"planning text", r"planning transitions", r"validating plan",
    r"building visuals", r"rendering draft",
    r"adding sound effects(?: \(\d+ sounds?\)| \(checking the sound map\))?", r"verifying sound sync and loudness",
    r"reviewing: mechanical checks", r"reviewing: style check", r"reviewing: edit review \(round \d+/\d+\)",
    # two steps the table does not name (DECISIONS.md 284): S12's audio check (M11) and S8's loudness pass
    r"reviewing: audio check", r"normalizing loudness",
    r"fixing (?:\[[a-z0-9_-]+\],? ?(?:and )?)+issues \(round \d+, \w+\)",
    r"rendering final video", r"rendering hook 2 clip", r"writing caption", r"exporting #\d+",
    r"waiting for usage limit \([\w ]+\) until [\w: ]+ \((?:\d+h)?\d+m(?:\d+s)? left\)",
    r"waiting for usage limit \([\w ]+\), (?:no reset time given, probing every \d+ min|probe \d+ failed, next probe in \d+ min)",
    r"retrying after temporary error \(.+\), next try in \S+ \(try \d+/\d+\)",
    r"error in [^:]+: (?:reviewing \(cycle \d+/\d+, \w+\)|applying fix F\d+ \(\w+\)|escalated review \(\w+\)|verifying fix F\d+)",
    r"starting", r"between ideas", r"working")]


def known_activity(text: str) -> bool:
    return any(a.match(text) for a in ACTIVITIES)


def check_line(line: str) -> str:
    """'' when the line is a valid status line, else what is wrong with it."""
    if not line:
        return "empty line"
    if "\r" in line:
        return "carriage return in the line"
    if ANSI_RE.search(line):
        return "ANSI color codes in the line (NO_COLOR or a file should get plain text)"
    if EM_DASH in line:
        return "em dash in the line"
    m = LINE_RE.match(line)
    if not m:
        return "not in the format [HH:MM] TAG  details"
    hh, mm, tag = int(m.group(1)), int(m.group(2)), m.group(3)
    if hh > 23 or mm > 59:
        return "impossible time %02d:%02d" % (hh, mm)
    if tag not in TAGS:
        return "unknown tag %s" % tag
    if line[8:14] != tag.ljust(6) or line[14:15] != " ":
        return "the tag is not padded to 6 characters"
    return ""


def minutes(stamp: str) -> int:
    return int(stamp[1:3]) * 60 + int(stamp[4:6])


def diff_min(a: int, b: int) -> int:
    """Minutes from stamp a to stamp b (both minute-of-day), across midnight."""
    return (b - a) % 1440


def parse_dur(text: str) -> int:
    m = re.match(r"^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$", text)
    if not m:
        return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


def cut_text(text: str, n: int = 40) -> str:
    return text[:n] + "..." if len(text) > n else text


# ------------------------------------------------------------------------------------------------ the story
def story(lines: list[str], allow_crash: bool = False, max_gap: int | None = None, heartbeat: int = 5,
          live: bool = False, gate_line: bool = True) -> dict:
    allow_crash = allow_crash or live
    problems: list[str] = []
    max_gap = max_gap if max_gap is not None else heartbeat + 2

    def problem(i: int, text: str) -> None:
        problems.append("line %d: %s" % (i + 1, text))

    sessions: list[dict] = []
    ideas: list[dict] = []
    exports: list[int] = []
    limits: list[dict] = []
    tags_seen: dict[str, int] = {}
    activities_seen: set[str] = set()
    sess = None
    idea = None
    pending_next = None      # the NEXT line waiting for its START
    pending_limit = None
    last_stamp = None
    prev_minute_line = None  # (index, minute of day) of the previous line inside an idea, for the gap check
    crashed_idea = None      # an idea a session left unfinished: the next session must resume it

    def close_idea(i: int, outcome: str) -> None:
        nonlocal idea, prev_minute_line
        if idea is not None:
            idea["outcome"] = outcome
            idea["end_line"] = i + 1
        idea = None
        prev_minute_line = None

    def close_session(i: int, end: str) -> None:
        nonlocal sess, idea, crashed_idea, pending_limit
        if sess is None:
            return
        sess["end"] = end
        if idea is not None:
            if allow_crash:
                sess["crashed_in"] = idea["run"]
                crashed_idea = idea
                close_idea(i, "running" if live and sess is sessions[-1] else "interrupted")
            else:
                problem(i, "the session ended inside idea %s (%s) without DONE, DROP or BLOCK" % (idea["k"], idea["run"]))
                close_idea(i, "unfinished")
        if pending_limit is not None and not allow_crash:
            problem(pending_limit["line"] - 1, "LIMIT without its RESUME line")
        sess = None

    for i, raw in enumerate(lines):
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        bad = check_line(line)
        if bad:
            problem(i, "%s: %r" % (bad, line[:120]))
            continue
        m = LINE_RE.match(line)
        stamp, tag, text = line[:7], m.group(3), m.group(4)
        now = minutes(stamp)
        tags_seen[tag] = tags_seen.get(tag, 0) + 1
        last_stamp = now
        if tag == "START" and text.startswith("reels autopilot v"):
            close_session(i, "banner of the next session")
            bm = BANNER_RE.match(text)
            if not bm:
                problem(i, "the banner lacks version, queue, style, voice or sfx map: %r" % text)
            sess = {"line": i + 1, "start": stamp[1:6], "queue": int(bm.group(2)) if bm else None, "ideas": [],
                    "exported": 0, "dropped": 0, "blocked": 0, "summary": None, "end": None}
            sessions.append(sess)
            pending_next = None
            continue
        if sess is None or (idea is None and tag in ("WARN", "READY", "INFO") and text.startswith(("preflight", "removed logs/STOPPED.md"))):
            # the preflight (a runner's, or bash pipeline/bin/preflight alone) writes before the banner
            if tag == "STOP":
                problem(i, "STOP line: %r" % text)
            elif tag not in ("WARN", "READY", "INFO"):
                problem(i, "a %s line outside a runner session: %r" % (tag, line[:80]))
            continue
        # the gap check: an idea in progress prints at least a heartbeat every few minutes
        if idea is not None and prev_minute_line is not None:
            gap = diff_min(prev_minute_line[1], now)
            if gap > max_gap:
                problem(i, "idea %s was silent for %d minutes (lines %d to %d): a hang, or the heartbeat stopped"
                        % (idea["k"], gap, prev_minute_line[0] + 1, i + 1))
        if idea is not None:
            prev_minute_line = (i, now)
        if tag == "START":
            sm = START_IDEA_RE.match(text)
            if not sm:
                problem(i, "START line not understood: %r" % text)
                continue
            if idea is not None:
                problem(i, "START of a new idea while idea %s had no DONE, DROP or BLOCK" % idea["k"])
                close_idea(i, "unfinished")
            k, total = int(sm.group(1)), int(sm.group(2))
            if k != len(sess["ideas"]) + 1:
                problem(i, "START says idea %d but it is idea %d of this session" % (k, len(sess["ideas"]) + 1))
            if total < k:
                problem(i, "START position %d/%d" % (k, total))
            if pending_next is not None and (pending_next["k"] != k or pending_next["text"] != sm.group(3)):
                problem(i, "NEXT announced idea %s %r but START is idea %d %r" % (pending_next["k"], pending_next["text"], k, sm.group(3)))
            if k > 1 and pending_next is None:
                problem(i, "idea %d STARTs without a NEXT line after the previous idea" % k)
            pending_next = None
            resumed = bool(sm.group(5))
            idea = {"session": len(sessions), "k": k, "total": total, "text": sm.group(3), "run": sm.group(4),
                    "resumed": resumed, "resumed_at": sm.group(6) or "", "line": i + 1, "start": now,
                    "steps": [], "gate": None, "outcome": None, "export": None, "heartbeats": 0, "fixed": 0,
                    "errors": 0, "angles": 0, "flags": 0, "limits": 0,
                    # S12 (12-review/run.sh): round 1 failing opens one issue, a later round passing fixes it; the
                    # runner reads these from state.json when the stage ends, so they count from the next STEP line
                    "rev_open": 0, "rev_fixed": 0, "rev_pending": None}
            if crashed_idea is not None:
                if not resumed or idea["run"] != crashed_idea["run"]:
                    problem(i, "the session after the crash did not resume %s first (START %r)" % (crashed_idea["run"], text))
                idea["resumed_after_crash"] = True
                crashed_idea = None
            sess["ideas"].append(idea)
            ideas.append(idea)
            prev_minute_line = (i, now)
            continue
        if tag in ("STEP", "GATE", "ANGLE", "DONE", "DROP", "BLOCK", "REEL", "FIXED", "ERROR", "ESCAL", "RESUME",
                   "LIMIT", "RETRY") and idea is None:
            problem(i, "%s line outside an idea: %r" % (tag, line[:100]))
            continue
        if tag == "STEP":
            st = STEP_RE.match(text)
            if not st:
                problem(i, "STEP line not understood: %r" % text)
                continue
            act, nxt = st.group(1), st.group(3)
            expected = idea["steps"][-1]["next"] if idea["steps"] else (idea["resumed_at"] or None)
            if expected is not None and expected != act and not expected.startswith("exporting"):
                problem(i, "STEP %r but the previous line announced %r" % (act, expected))
            idea["steps"].append({"activity": act, "seconds": parse_dur(st.group(2)), "next": nxt, "line": i + 1})
            if idea["rev_pending"] == "open":
                idea["rev_open"] = 1
            elif idea["rev_pending"] == "fixed":
                idea["rev_open"], idea["rev_fixed"] = 0, idea["rev_fixed"] + 1
            idea["rev_pending"] = None
            for a in (act, nxt):
                if a not in ("done", "finishing") and not known_activity(a):
                    problem(i, "STEP activity %r is not in the activity table of spec section 7" % a)
            if pending_limit is not None:
                problem(pending_limit["line"] - 1, "LIMIT without its RESUME line before the stage ended")
                pending_limit = None
        elif tag == "GATE":
            idea["gate"] = text
            if not GATE_RE.match(text):
                problem(i, "GATE line without the scores P S C F H: %r" % text)
        elif tag == "ANGLE":
            idea["angles"] += 1
        elif tag == "FIXED":
            idea["fixed"] += 1
        elif tag == "ERROR":
            idea["errors"] += 1
        elif tag == "FLAG":
            idea["flags"] += 1
        elif tag == "WARN" and idea is not None and re.match(r"^S12: review round 1 failed", text):
            idea["rev_pending"] = "open"
        elif tag == "INFO" and idea is not None and re.match(r"^S12: review round ([2-9]|\d\d+) passed", text):
            idea["rev_pending"] = "fixed"
        elif tag == "LIMIT":
            lm = LIMIT_RE.match(text)
            if not lm and not LIMIT_UNPARSED_RE.match(text):
                problem(i, "LIMIT line not understood: %r" % text)
            if pending_limit is not None:
                problem(pending_limit["line"] - 1, "LIMIT without its RESUME line before the next LIMIT")
            pending_limit = {"line": i + 1, "text": text, "kind": lm.group(1) if lm else "",
                             "resume_at": lm.group(2) if lm else "", "idea": idea["k"], "session": len(sessions),
                             "run": idea["run"], "stamp": stamp[1:6]}
            idea["limits"] += 1
        elif tag == "RESUME":
            if pending_limit is None:
                problem(i, "RESUME without a LIMIT line before it")
            else:
                pending_limit["resume_line"] = i + 1
                pending_limit["resume_text"] = text
                pending_limit["resume_stamp"] = stamp[1:6]
                limits.append(pending_limit)
                pending_limit = None
        elif tag == "REEL":
            rm = REEL_RE.match(text)
            if not rm:
                problem(i, "heartbeat not in the spec's format: %r" % text)
                continue
            idea["heartbeats"] += 1
            k, total, htext, act = int(rm.group(1)), int(rm.group(2)), rm.group(3), rm.group(4)
            minute, stage_s, fixed, open_ = int(rm.group(5)), parse_dur(rm.group(6)), int(rm.group(7)), int(rm.group(8))
            if k != idea["k"] or total < k:
                problem(i, "heartbeat position %d/%d while idea %d runs" % (k, total, idea["k"]))
            if htext != idea["text"]:
                problem(i, "heartbeat names %r, the idea is %r" % (htext, idea["text"]))
            since = diff_min(idea["start"], now)
            if not idea["resumed"] and abs(minute - since) > 1:
                problem(i, "heartbeat minute %d, but the idea started %d minutes ago" % (minute, since))
            if idea["resumed"] and minute + 1 < since:
                problem(i, "heartbeat minute %d is less than the %d minutes since this session resumed the idea" % (minute, since))
            if stage_s // 60 > minute + 1 and not idea["resumed"]:
                problem(i, "heartbeat stage time %ds longer than the idea's %d minutes" % (stage_s, minute))
            if not idea["resumed"]:
                want_fixed = idea["fixed"] + idea["rev_fixed"]
                want_open = max(0, idea["errors"] - idea["fixed"]) + idea["rev_open"]
                if fixed != want_fixed:
                    problem(i, "heartbeat says %d fixed, the log has %d FIXED lines and %d recovered review rounds for this idea"
                            % (fixed, idea["fixed"], idea["rev_fixed"]))
                if open_ != want_open:
                    problem(i, "heartbeat says %d open, the log has %d ERROR, %d FIXED and %d failing review lines"
                            % (open_, idea["errors"], idea["fixed"], idea["rev_open"]))
            elif fixed < idea["fixed"]:
                problem(i, "heartbeat says %d fixed, fewer than this session's %d FIXED lines" % (fixed, idea["fixed"]))
            if not known_activity(act):
                problem(i, "heartbeat activity %r is not in the activity table of spec section 7" % act)
            activities_seen.add(act)
        elif tag == "DONE":
            dm = DONE_RE.match(text)
            if not dm or dm.group(1) != dm.group(2):
                problem(i, "DONE line not understood: %r" % text)
                close_idea(i, "done")
                continue
            n = int(dm.group(1))
            idea["export"] = n
            exports.append(n)
            done_fixed = idea["fixed"] + idea["rev_fixed"] + (1 if idea["rev_pending"] == "fixed" else 0)
            if int(dm.group(4)) != done_fixed and not idea["resumed"]:
                problem(i, "DONE says %s issues fixed, the log has %d FIXED lines and %d recovered review rounds"
                        % (dm.group(4), idea["fixed"], done_fixed - idea["fixed"]))
            if idea["gate"] is None and not idea["resumed"] and gate_line:
                problem(i, "idea %d was exported without a GATE line" % idea["k"])
            sess["exported"] += 1
            close_idea(i, "done")
        elif tag == "DROP":
            dm = DROP_RE.match(text)
            if not dm:
                problem(i, "DROP line not understood: %r" % text)
            elif dm.group(1) != idea["text"]:
                problem(i, "DROP names %r, the idea is %r" % (dm.group(1), idea["text"]))
            idea["reason"] = dm.group(2) if dm else text
            sess["dropped"] += 1
            close_idea(i, "dropped")
        elif tag == "BLOCK":
            bm = BLOCK_RE.match(text)
            if not bm:
                problem(i, "BLOCK line not understood: %r" % text)
            elif bm.group(1) != idea["text"]:
                problem(i, "BLOCK names %r, the idea is %r" % (bm.group(1), idea["text"]))
            idea["reason"] = bm.group(3) if bm else text
            sess["blocked"] += 1
            close_idea(i, "blocked")
        elif tag == "NEXT":
            nm = NEXT_RE.match(text)
            if not nm:
                problem(i, "NEXT line not understood: %r" % text)
                continue
            if idea is not None:
                problem(i, "NEXT while idea %d is still running" % idea["k"])
            if int(nm.group(1)) != len(sess["ideas"]) + 1:
                problem(i, "NEXT says idea %s, it will be idea %d of this session" % (nm.group(1), len(sess["ideas"]) + 1))
            pending_next = {"k": int(nm.group(1)), "text": nm.group(3)}
        elif tag == "IDLE":
            if idea is not None:
                problem(i, "IDLE while idea %d is running" % idea["k"])
            sm = SUMMARY_RE.match(text)
            if sm:
                sess["summary"] = text
                got = tuple(int(x) for x in sm.groups()[:3])
                want = (sess["exported"], sess["dropped"], sess["blocked"])
                if got != want:
                    problem(i, "summary says %d exported, %d dropped, %d blocked; this session's lines say %d, %d, %d" % (got + want))
            elif IDLE_RE.match(text):
                sess.setdefault("idle_lines", 0)
                sess["idle_lines"] = sess.get("idle_lines", 0) + 1
            else:
                problem(i, "IDLE line not understood: %r" % text)
        elif tag == "STOP":
            problem(i, "STOP line: %r" % text)
    close_session(len(lines), "end of the log")

    # the exports: 1, 2, 3 ... in order, no gap, no repeat
    if exports and exports != list(range(exports[0], exports[0] + len(exports))):
        problems.append("exports are not numbered without gaps: %s" % exports)
    if not sessions:
        problems.append("no banner: the log has no runner session")
    elif sessions[-1]["summary"] is None and not live:
        problems.append("the last session has no summary line (IDLE queue empty: ...)")
    for s in sessions[:-1]:
        if s.get("crashed_in") is None and s["summary"] is None and s.get("end") == "banner of the next session":
            pass  # a session stopped by the user: allowed
    return {"sessions": sessions, "ideas": ideas, "exports": exports, "limits": limits, "tags": tags_seen,
            "activities": sorted(activities_seen), "problems": problems}


def read_lines(path: str) -> list[str]:
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        return f.read().split("\n")


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("line"); sp.add_argument("text")
    sp = sub.add_parser("status"); sp.add_argument("file")
    sp = sub.add_parser("samples"); sp.add_argument("file")
    sp = sub.add_parser("story"); sp.add_argument("log", nargs="+"); sp.add_argument("--json", default="")
    sp.add_argument("--allow-crash", action="store_true"); sp.add_argument("--max-gap", type=int, default=None)
    sp.add_argument("--heartbeat", type=int, default=5); sp.add_argument("--live", action="store_true")
    sp.add_argument("--no-gate-line", action="store_true")
    args = p.parse_args(argv)
    if args.cmd == "line":
        bad = check_line(args.text)
        print(bad or "ok")
        return 1 if bad else 0
    if args.cmd == "status":
        try:
            content = open(args.file, "rb").read().decode("utf-8", "replace")
        except OSError as exc:
            print("cannot read %s: %s" % (args.file, exc))
            return 1
        lines = content.split("\n")
        if len(lines) != 2 or lines[1] != "":
            print("status.txt must hold exactly one line ending in a newline (it holds %d)" % (len(lines) - 1))
            return 1
        bad = check_line(lines[0])
        if not bad and lines[0][8:14].strip() in NOT_STATUS:
            bad = "a %s line never replaces the status" % lines[0][8:14].strip()
        print(bad or "ok")
        return 1 if bad else 0
    if args.cmd == "samples":
        n = bad_n = 0
        seen_status = False
        out = []
        for raw in read_lines(args.file):
            if not raw.strip():
                continue
            epoch, _, content = raw.partition("\t")
            n += 1
            if content == "<missing>" and not seen_status:
                continue
            bad = check_line(content)
            if not bad and content[8:14].strip() in NOT_STATUS:
                bad = "a %s line in status.txt" % content[8:14].strip()
            if bad:
                bad_n += 1
                out.append("sample at %s: %s: %r" % (epoch, bad, content[:100]))
            else:
                seen_status = True
        print(json.dumps({"samples": n, "invalid": bad_n, "problems": out[:20]}, ensure_ascii=False))
        return 1 if bad_n or not seen_status else 0
    all_lines: list[str] = []
    for path in args.log:  # rotated files first (runner.log.3 runner.log.2 runner.log.1 runner.log)
        all_lines += [l for l in read_lines(path) if l.strip()]
    report = story(all_lines, allow_crash=args.allow_crash, max_gap=args.max_gap, heartbeat=args.heartbeat,
                   live=args.live, gate_line=not args.no_gate_line)
    text = json.dumps(report, ensure_ascii=False, indent=1)
    if args.json:
        with open(args.json, "w", encoding="utf-8", newline="\n") as f:
            f.write(text + "\n")
    print(json.dumps({"sessions": len(report["sessions"]), "ideas": len(report["ideas"]),
                      "outcomes": [i["outcome"] for i in report["ideas"]], "exports": report["exports"],
                      "limits": len(report["limits"]), "problems": report["problems"]}, ensure_ascii=False))
    return 1 if report["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
