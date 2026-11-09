#!/usr/bin/env python
"""The daily quota of a channel (BUILD_SPEC.md 14.4 and 14.6): channel.json `daily_quota` exports per calendar day in the
channel's timezone (channel.json `timezone`, else config runner.timezone); 0 means no limit.

    python pipeline/lib/quota.py status [--channel ID]

prints one JSON line:  {"quota": 2, "exported_today": 2, "reached": true, "next_reset": <epoch>, "next_reset_clock": "00:00",
                        "timezone": "Europe/Rome", "today": "2026-11-09"}

An export counts when the channel's history.txt has a line "<date time> | ... | exported <id>-N" whose date, read as the
machine's local time (the way history.sh writes it), falls on today's date in the channel's timezone.

Tests move the clock: REELS_NOW=<epoch>, or REELS_NOW_FILE=<file holding an epoch> (read at every call), instead of the real time.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths  # noqa: E402

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None


def now_epoch() -> float:
    f = os.environ.get("REELS_NOW_FILE")
    if f and os.path.isfile(f):
        try:
            with open(f, encoding="utf-8") as fh:
                return float(fh.read().strip())
        except (OSError, ValueError):
            pass
    v = os.environ.get("REELS_NOW")
    if v:
        try:
            return float(v)
        except ValueError:
            pass
    return time.time()


def read_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def tzinfo(name: str):
    if name and ZoneInfo is not None:
        try:
            return ZoneInfo(name)
        except Exception:  # noqa: BLE001
            pass
    return None


def status(cid: str, now: float | None = None) -> dict:
    now = now_epoch() if now is None else now
    data = read_json(paths.channel_json(cid))
    quota = int(data.get("daily_quota") or 0)
    tzname = data.get("timezone") or ""
    if not tzname:
        tzname = ((read_json(os.path.join(paths.root(), "config.json")).get("runner") or {}).get("timezone")) or ""
    tz = tzinfo(tzname)
    local_now = datetime.fromtimestamp(now, tz) if tz else datetime.fromtimestamp(now)
    today = local_now.date()
    history = os.path.join(paths.channel_root(cid), paths.LOGS_DIR, "history.txt")
    count = 0
    pat = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d) \|.*\| exported %s-\d+\s*$" % re.escape(cid))
    try:
        with open(history, encoding="utf-8-sig") as f:
            for line in f:
                m = pat.match(line)
                if not m:
                    continue
                naive = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M")
                stamp = naive.astimezone(tz) if tz else naive   # history.sh writes the machine's local time
                if stamp.date() == today:
                    count += 1
    except OSError:
        pass
    midnight = datetime.combine(today + timedelta(days=1), datetime.min.time())
    if tz:
        midnight = midnight.replace(tzinfo=tz)
    nxt = midnight.timestamp()
    return {"quota": quota, "exported_today": count, "reached": bool(quota) and count >= quota, "next_reset": int(nxt),
            "next_reset_clock": "00:00", "timezone": tzname or "local", "today": str(today)}


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    args = list(argv)
    if "--channel" in args:
        i = args.index("--channel")
        os.environ["REELS_CHANNEL"] = args[i + 1]
        del args[i:i + 2]
    if not args or args[0] != "status":
        print(__doc__, file=sys.stderr)
        return 2
    cid = paths.require_channel()
    print(json.dumps(status(cid)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
