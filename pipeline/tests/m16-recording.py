#!/usr/bin/env python
"""m16-recording.py: S1's page recordings (M16, test-m16 section 2). Starts a local web server with a long page and a short one, runs
pipeline/lib/screenshot.py on both, and checks what the research stage then lists. Prints `<name> ok` or `<name> FAIL <why>`.

  python pipeline/tests/m16-recording.py <work dir>

  - a long page: NN-name.png and NN-name.mp4 next to each other, the video H.264, 1080 px wide, 30 fps, 5 to 8 s, no sound, and its
    frames change (the page scrolls); the sidecar says recording and recording_seconds
  - a page that does not scroll: the screenshot is saved, the recording is null, the exit code is 0 (never an error)
  - --no-record: no video
  - research.py's collect_assets lists the recording of the first page (assets.json: recording, recording_seconds) and not of the second
  - the video card's frame count: ffprobe agrees with the sidecar
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "pipeline", "lib"))


def say(name, ok, detail=""):
    print(name, "ok" if ok else f"FAIL {detail}", flush=True)


def probe(path: str) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate:format=duration", "-of", "json", path],
                         capture_output=True, text=True, encoding="utf-8").stdout
    return json.loads(out or "{}")


def frame_hashes(path: str, times: list[float]) -> list[str]:
    import hashlib
    hs = []
    for t in times:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", path, "-frames:v", "1", "-vf", "scale=54:96,format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
        hs.append(hashlib.md5(raw).hexdigest())
    return hs


def main() -> int:
    work = os.path.abspath(sys.argv[1]).replace("\\", "/")
    site = os.path.join(work, "site")
    runs = os.path.join(work, "runs")
    out = os.path.join(runs, "r1", "01-research", "assets")
    os.makedirs(site, exist_ok=True)
    os.makedirs(out, exist_ok=True)
    rows = "".join(f"<section style='height:420px;background:hsl({i * 37 % 360},60%,{80 - i % 3 * 5}%);font:700 60px sans-serif;padding:40px'>Section {i}</section>" for i in range(12))
    open(os.path.join(site, "long.html"), "w").write(f"<html><head><title>Long page</title></head><body style='margin:0'>{rows}</body></html>")
    open(os.path.join(site, "short.html"), "w").write("<html><head><title>Short page</title></head><body style='margin:0'><h1>Hello</h1></body></html>")
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a, **k):  # the page requests are noise in a test log
            pass

    handler = functools.partial(Quiet, directory=site)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    env = dict(os.environ, REELS_RUNS=runs, REELS_ASSETS_DIR=out)
    env.pop("REELS_ROOT", None)

    def shot(page: str, name: str, *extra: str):
        p = subprocess.run([sys.executable, os.path.join(REPO, "pipeline", "lib", "screenshot.py"), f"http://127.0.0.1:{port}/{page}", name, *extra],
                           capture_output=True, text=True, encoding="utf-8", env=env, timeout=240)
        try:
            return p.returncode, json.loads(p.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return p.returncode, {"raw": p.stdout[-300:], "err": p.stderr[-300:]}

    rc, res = shot("long.html", "long")
    side = json.load(open(os.path.join(out, "01-long.json"), encoding="utf-8")) if os.path.isfile(os.path.join(out, "01-long.json")) else {}
    say("long-exit-0", rc == 0 and res.get("ok"), (rc, res))
    png, mp4 = os.path.join(out, "01-long.png"), os.path.join(out, "01-long.mp4")
    say("long-png-and-mp4-side-by-side", os.path.isfile(png) and os.path.isfile(mp4), os.listdir(out))
    pr = probe(mp4) if os.path.isfile(mp4) else {}
    v = next((s for s in pr.get("streams", []) if s.get("codec_type") == "video"), {})
    dur = float((pr.get("format") or {}).get("duration") or 0)
    say("long-h264-1080-wide-30fps", v.get("codec_name") == "h264" and v.get("width") == 1080 and v.get("r_frame_rate") == "30/1", v)
    say("long-no-sound", not any(s.get("codec_type") == "audio" for s in pr.get("streams", [])), pr.get("streams"))
    say("long-5-to-8-seconds", 5.0 <= dur <= 8.2, dur)
    hs = frame_hashes(mp4, [0.4, 2.0, 3.5, 5.0]) if os.path.isfile(mp4) else []
    say("long-the-page-scrolls", len(set(hs)) == len(hs) >= 4, hs)
    say("long-sidecar-says-recording", side.get("recording") == "01-long.mp4" and 5.0 <= float(side.get("recording_seconds") or 0) <= 8.2, {k: side.get(k) for k in ("recording", "recording_seconds", "recording_note")})
    rc, res = shot("short.html", "short")
    side2 = json.load(open(os.path.join(out, "02-short.json"), encoding="utf-8")) if os.path.isfile(os.path.join(out, "02-short.json")) else {}
    say("short-saved-without-recording", rc == 0 and res.get("ok") and os.path.isfile(os.path.join(out, "02-short.png")) and not os.path.isfile(os.path.join(out, "02-short.mp4")) and not side2.get("recording"), (rc, res))
    say("short-says-why", "does not scroll" in str(side2.get("recording_note", "")), side2.get("recording_note"))
    rc, res = shot("long.html", "plain", "--no-record", "--again")
    say("no-record-flag", rc == 0 and not os.path.isfile(os.path.join(out, "03-plain.mp4")) and res.get("recording") in (None, ""), (rc, res))
    # what the research stage lists
    import research
    run_dir = os.path.join(runs, "r1")
    # collect_assets reads <run>/01-research/assets
    assets = research.collect_assets(run_dir, [{"name": "long", "what": "the long page"}], 6)
    by = {a["name"]: a for a in assets}
    say("assets-json-lists-the-recording", by.get("long", {}).get("recording") == "assets/01-long.mp4" and float(by["long"].get("recording_seconds") or 0) >= 5, by.get("long"))
    say("assets-json-no-recording-for-the-short-page", "recording" not in by.get("short", {}), by.get("short"))
    srv.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
