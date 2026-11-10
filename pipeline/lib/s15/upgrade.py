"""upgrade.py: the state of the capability upgrade (BUILD_SPEC.md S15 step 8, M21).

The runner (pipeline/lib/editor.sh) asks `check` between ideas: does the capability content of the stable copy's manifest (everything but
lastBatch and appVersion) differ from the one S15 last accepted (logs/editor-capabilities.json; the baseline until there is one)? If so,
which keys were added? A manifest whose upgrade failed is not tried again until the capabilities change again or 24 hours have passed
(logs/editor-upgrade.json). `accept` saves the manifest, `fail` records the hash and the reasons.

  python pipeline/lib/s15/upgrade.py check  [--stable-dir DIR] [--now EPOCH]       -> JSON {need, keys, hash, reason}
  python pipeline/lib/s15/upgrade.py accept [--stable-dir DIR]
  python pipeline/lib/s15/upgrade.py fail   [--stable-dir DIR] --reason TEXT [--now EPOCH]
  python pipeline/lib/s15/upgrade.py status                                        -> one line for the status file and doctor
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.dirname(HERE)
sys.path.insert(0, LIB)

from s15 import manifest as smanifest  # noqa: E402

RETRY_SECONDS = 24 * 3600


def root_logs() -> str:
    root = os.environ.get("REELS_ROOT") or os.path.dirname(os.path.dirname(LIB))
    return os.path.join(root, "logs")


def read_json(path: str, default=None):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def stable_dir(arg: str | None) -> str | None:
    return arg or os.environ.get("EDITOR_STABLE_DIR") or None


def check(stable: str | None, now: float) -> dict:
    caps = os.path.join(stable, "capabilities.json") if stable else ""
    if not caps or not os.path.isfile(caps):
        return {"need": False, "keys": [], "hash": "", "reason": "no stable copy yet (no capabilities.json)"}
    new = smanifest.load_file(caps)
    new_hash = smanifest.capability_hash(new)
    saved = read_json(os.path.join(root_logs(), "editor-capabilities.json"))
    old = saved if isinstance(saved, dict) else smanifest.baseline()
    old_hash = smanifest.capability_hash(old)
    if old_hash == new_hash:
        return {"need": False, "keys": [], "hash": new_hash, "reason": "the capabilities are the ones S15 knows"}
    failed = read_json(os.path.join(root_logs(), "editor-upgrade.json"))
    if isinstance(failed, dict) and failed.get("hash") == new_hash and now - float(failed.get("failed_at", 0)) < RETRY_SECONDS:
        return {"need": False, "keys": [], "hash": new_hash, "reason": "an upgrade for these capabilities failed less than 24 hours ago; they stay on fallback"}
    return {"need": True, "keys": smanifest.added_keys(old, new), "hash": new_hash, "reason": "the capabilities changed"}


def accept(stable: str | None) -> int:
    caps = os.path.join(stable, "capabilities.json")
    write_json(os.path.join(root_logs(), "editor-capabilities.json"), smanifest.load_file(caps))
    try:
        os.remove(os.path.join(root_logs(), "editor-upgrade.json"))
    except OSError:
        pass
    return 0


def fail(stable: str | None, reason: str, now: float) -> int:
    caps = os.path.join(stable, "capabilities.json")
    new = smanifest.load_file(caps)
    saved = read_json(os.path.join(root_logs(), "editor-capabilities.json"))
    old = saved if isinstance(saved, dict) else smanifest.baseline()
    write_json(os.path.join(root_logs(), "editor-upgrade.json"),
               {"hash": smanifest.capability_hash(new), "failed_at": now, "keys": smanifest.added_keys(old, new), "reasons": reason.splitlines()[:20]})
    return 0


def status() -> str:
    f = read_json(os.path.join(root_logs(), "editor-upgrade.json"))
    s = read_json(os.path.join(root_logs(), "editor-capabilities.json"))
    parts = [f"accepted manifest {smanifest.capability_hash(s)}" if isinstance(s, dict) else "no accepted manifest yet (the baseline)"]
    if isinstance(f, dict):
        age = (time.time() - float(f.get("failed_at", 0))) / 3600.0
        parts.append(f"last upgrade failed {age:.1f} h ago for {f.get('hash')}")
    return "; ".join(parts)


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["check", "accept", "fail", "status"])
    ap.add_argument("--stable-dir")
    ap.add_argument("--now", type=float, default=None)
    ap.add_argument("--reason", default="")
    a = ap.parse_args(argv)
    now = a.now if a.now is not None else time.time()
    if a.cmd == "check":
        print(json.dumps(check(stable_dir(a.stable_dir), now)))
        return 0
    if a.cmd == "accept":
        return accept(stable_dir(a.stable_dir))
    if a.cmd == "fail":
        return fail(stable_dir(a.stable_dir), a.reason, now)
    print(status())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
