#!/usr/bin/env python
"""screenshot.py: capture a real web page as a research asset (BUILD_SPEC.md section 5, S1).

  python pipeline/lib/screenshot.py URL NAME [--out-dir DIR] [--width 1080] [--height 1920] [--full-page]
                                    [--timeout 45] [--again] [--no-record] [--record-seconds 6]
  The stages and the research model call it through the wrapper: bash pipeline/bin/screenshot URL NAME

Writes DIR/NN-<name>.png (1080 px wide by default, the first screen only; --full-page for the whole page, capped
at 4 screens) and the sidecar DIR/NN-<name>.json with url, final_url, title, status, width, height, full_page,
captured (date and time), checked (date). DIR is --out-dir or $REELS_ASSETS_DIR and must sit inside the runs
folder ($REELS_RUNS, else runs/ of $REELS_CHANNEL_ROOT; the system temp folder only when neither is set): the tool never
writes anywhere else, so a model that calls it cannot touch library/, styles/ or ideas.txt through it. The same URL captured twice in one
folder returns the first capture (--again forces a new one).

It never gets around a site that blocks automated access (BUILD_SPEC.md S1): a 401, 403, 429 or 503 answer, or a
page that is a bot check (Cloudflare's "Just a moment", "Verify you are human", "Access denied", a captcha), is
reported as blocked and nothing is saved. Plain headless Chromium: no user agent spoofing, no stealth plugins.

M16 (Motion and energy rules E8): next to the screenshot it records a scroll video of the page, DIR/NN-<name>.mp4 (H.264,
1080 px wide, 30 fps, no sound, 5 to 8 seconds, 6 by default): a smooth scroll from the top through the page, for the video
card and the window card to play. The sidecar gains recording (the file name) and recording_seconds. A page that does not
scroll (less than 300 px of room) or a recording that fails leaves recording null: the screenshot stands and the failure is
never an error. --no-record skips it.

Prints one JSON line: {"ok": true, "file": "...", "url": ..., "final_url": ..., "title": ..., "status": ...,
"reused": bool} or {"ok": false, "error": "...", "blocked": bool}.
Exit 0 saved or reused, 2 blocked, 3 Playwright or its Chromium missing (bash pipeline/bin/setup-python installs
them), 4 the page could not be loaded (timeout, DNS, a connection error), 1 usage or a refused output folder.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402

BLOCK_STATUSES = {401, 403, 429, 503}
BLOCK_TEXTS = ("just a moment", "verify you are human", "verify that you are human", "access denied",
               "attention required", "are you a robot", "captcha", "checking your browser",
               "enable javascript and cookies to continue", "please verify you are a human",
               "request blocked", "automated access")
MAX_FULL_PAGE_SCREENS = 4


def winpath(path: str) -> str:
    m = re.match(r"^/([A-Za-z])/(.*)$", path or "")
    return f"{m.group(1).upper()}:/{m.group(2)}" if (m and os.name == "nt") else path


def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def norm_url(url: str) -> str:
    url = url.strip()
    if "#" in url:
        url = url.split("#", 1)[0]
    return url.rstrip("/")


def safe_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:40]
    return slug or "page"


def allowed_roots() -> list[str]:
    """Where the tool may write: the runs folder of the channel ($REELS_RUNS, else runs/ of $REELS_CHANNEL_ROOT); the system
    temp folder only when neither is set (a bare call from a shell or a unit test)."""
    roots = []
    runs = os.environ.get("REELS_RUNS")
    if runs:
        roots.append(winpath(runs))
    channel_root = os.environ.get("REELS_CHANNEL_ROOT")
    if channel_root:
        roots.append(os.path.join(winpath(channel_root), paths.RUNS_DIR))
    if not roots:
        roots.append(tempfile.gettempdir())
    return [os.path.normcase(os.path.abspath(r)) for r in roots]


def inside(path: str, root: str) -> bool:
    path = os.path.normcase(os.path.abspath(path))
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:  # different drives
        return False


def next_number(out_dir: str) -> int:
    best = 0
    for entry in os.listdir(out_dir):
        m = re.match(r"^(\d{2})-.*\.png$", entry)
        if m:
            best = max(best, int(m.group(1)))
    return best + 1


def existing_capture(out_dir: str, url: str) -> dict | None:
    want = norm_url(url)
    for entry in sorted(os.listdir(out_dir)):
        if not entry.endswith(".json"):
            continue
        try:
            with open(os.path.join(out_dir, entry), encoding="utf-8-sig") as f:
                side = json.load(f)
        except (OSError, ValueError):
            continue
        if not isinstance(side, dict) or not side.get("ok"):
            continue
        if norm_url(side.get("url", "")) == want and os.path.isfile(os.path.join(out_dir, side.get("file", ""))):
            return side
    return None


def looks_blocked(status: int | None, title: str, body: str) -> bool:
    if status in BLOCK_STATUSES:
        return True
    text = (title + "\n" + body[:3000]).lower()
    return any(marker in text for marker in BLOCK_TEXTS) and len(body) < 6000


def capture(url: str, png: str, width: int, height: int, full_page: bool, timeout_s: float) -> dict:
    """Load the page and save the screenshot. Returns the sidecar fields; raises on navigation failures."""
    from playwright.sync_api import sync_playwright  # imported here so a missing package is exit 3, not a traceback

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=1)
            page = context.new_page()
            response = page.goto(url, wait_until="domcontentloaded", timeout=int(timeout_s * 1000))
            try:
                page.wait_for_load_state("networkidle", timeout=min(15000, int(timeout_s * 1000)))
            except Exception:  # noqa: BLE001  (a page that never goes idle is still a page)
                pass
            page.wait_for_timeout(750)
            status = response.status if response is not None else None
            title = ""
            body = ""
            try:
                title = page.title() or ""
            except Exception:  # noqa: BLE001
                pass
            try:
                body = page.inner_text("body", timeout=3000) or ""
            except Exception:  # noqa: BLE001
                pass
            final_url = page.url
            if looks_blocked(status, title, body):
                return {"ok": False, "blocked": True, "status": status, "title": title[:200], "final_url": final_url}
            if full_page:
                try:
                    total = int(page.evaluate("document.documentElement.scrollHeight") or height)
                except Exception:  # noqa: BLE001
                    total = height
                clip_h = min(total, height * MAX_FULL_PAGE_SCREENS)
                page.screenshot(path=png, clip={"x": 0, "y": 0, "width": width, "height": clip_h}, full_page=True)
                shot_h = clip_h
            else:
                page.screenshot(path=png, full_page=False)
                shot_h = height
            return {"ok": True, "blocked": False, "status": status, "title": title[:200], "final_url": final_url,
                    "width": width, "height": shot_h}
        finally:
            browser.close()


def ffmpeg_exe() -> str | None:
    import shutil
    return shutil.which("ffmpeg")


def record_scroll(url: str, mp4: str, width: int, height: int, seconds: float, timeout_s: float) -> dict:
    """Record the page scrolling from the top (a smooth requestAnimationFrame scroll of `seconds`, easing in and out) and
    encode it to mp4. Returns {"ok": bool, "seconds": float, "reason": str}; never raises."""
    import shutil
    import subprocess
    ffmpeg = ffmpeg_exe()
    if not ffmpeg:
        return {"ok": False, "reason": "ffmpeg is not on PATH"}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"ok": False, "reason": "playwright is not installed"}
    tmp = tempfile.mkdtemp(prefix="rec-", dir=os.path.dirname(mp4))
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                made = time.time()
                context = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=1,
                                              record_video_dir=tmp, record_video_size={"width": width, "height": height})
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=int(timeout_s * 1000))
                try:
                    page.wait_for_load_state("networkidle", timeout=min(12000, int(timeout_s * 1000)))
                except Exception:  # noqa: BLE001
                    pass
                page.wait_for_timeout(600)
                room = 0
                try:
                    room = int(page.evaluate("Math.max(0, document.documentElement.scrollHeight - window.innerHeight)") or 0)
                except Exception:  # noqa: BLE001
                    room = 0
                if room < 300:
                    context.close()
                    return {"ok": False, "reason": f"the page does not scroll ({room} px of room)"}
                dist = min(room, int(height * 2.2))
                start_offset = max(0.0, time.time() - made - 0.15)
                page.evaluate(
                    "([dist, ms]) => new Promise(res => { const t0 = performance.now(); const ease = p => p < 0.5 ? 4*p*p*p : 1 - Math.pow(-2*p + 2, 3) / 2;"
                    " const step = now => { const p = Math.min(1, (now - t0) / ms); window.scrollTo(0, dist * ease(p)); if (p < 1) requestAnimationFrame(step); else res(true); };"
                    " requestAnimationFrame(step); })", [dist, int(seconds * 1000)])
                page.wait_for_timeout(250)
                video = page.video
                context.close()  # flushes the video file
                webm = video.path() if video else ""
            finally:
                browser.close()
        if not webm or not os.path.isfile(webm):
            return {"ok": False, "reason": "Playwright wrote no video"}
        cmd = [ffmpeg, "-v", "error", "-y", "-ss", f"{start_offset:.2f}", "-i", webm, "-t", f"{seconds + 0.2:.2f}",
               "-vf", f"scale={width}:-2:flags=lanczos,fps=30", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
               "-g", "6", "-keyint_min", "6", "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4]  # a key frame every 6 frames: the video card seeks it frame by frame
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, encoding="utf-8", errors="replace")
        if proc.returncode != 0 or not os.path.isfile(mp4):
            return {"ok": False, "reason": "ffmpeg: " + (proc.stderr or "")[-200:].strip()}
        return {"ok": True, "seconds": round(seconds + 0.2, 2)}
    except Exception as exc:  # noqa: BLE001  (a recording is a bonus: whatever goes wrong, the screenshot stands)
        return {"ok": False, "reason": (str(exc).splitlines() or [exc.__class__.__name__])[0][:200]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("url")
    parser.add_argument("name")
    parser.add_argument("--out-dir", default=os.environ.get("REELS_ASSETS_DIR", ""))
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--full-page", action="store_true")
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--again", action="store_true")
    parser.add_argument("--no-record", action="store_true", help="skip the scroll recording next to the screenshot")
    parser.add_argument("--record-seconds", type=float, default=6.0, help="the recording's scroll, 5 to 8 seconds (default 6)")
    args = parser.parse_args(argv)

    url = args.url.strip()
    if not re.match(r"^https?://", url, re.I):
        emit({"ok": False, "blocked": False, "error": f"not an http(s) URL: {url[:80]}"})
        return 1
    if not args.out_dir:
        emit({"ok": False, "blocked": False, "error": "no output folder: pass --out-dir or set REELS_ASSETS_DIR"})
        return 1
    out_dir = os.path.abspath(winpath(args.out_dir))
    if not any(inside(out_dir, root) for root in allowed_roots()):
        emit({"ok": False, "blocked": False,
              "error": f"refusing to write outside the runs folder: {out_dir.replace(os.sep, '/')}"})
        return 1
    os.makedirs(out_dir, exist_ok=True)

    if not args.again:
        prior = existing_capture(out_dir, url)
        if prior:
            emit({"ok": True, "reused": True, "file": prior["file"], "path": os.path.join(out_dir, prior["file"]).replace("\\", "/"), "recording": prior.get("recording"),
                  "url": prior.get("url"), "final_url": prior.get("final_url"), "title": prior.get("title"),
                  "status": prior.get("status")})
            return 0

    try:
        import playwright  # noqa: F401
    except ImportError:
        emit({"ok": False, "blocked": False, "error": "playwright is not installed: run bash pipeline/bin/setup-python"})
        return 3

    name = safe_name(args.name)
    n = next_number(out_dir)
    base = f"{n:02d}-{name}"
    png = os.path.join(out_dir, base + ".png")
    side_path = os.path.join(out_dir, base + ".json")
    started = time.time()
    try:
        result = capture(url, png, args.width, args.height, args.full_page, args.timeout)
    except ImportError as exc:
        emit({"ok": False, "blocked": False, "error": f"playwright import failed: {exc}"})
        return 3
    except Exception as exc:  # noqa: BLE001  (Playwright raises its own classes; the message is what matters)
        msg = str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__
        if "Executable doesn't exist" in msg or "browserType.launch" in msg:
            emit({"ok": False, "blocked": False, "error": f"Chromium for Playwright is missing: run bash pipeline/bin/setup-python ({msg[:160]})"})
            return 3
        emit({"ok": False, "blocked": False, "error": f"could not load {url[:80]}: {msg[:200]}"})
        return 4
    if not result.get("ok"):
        emit({"ok": False, "blocked": True, "status": result.get("status"), "title": result.get("title"),
              "error": f"the site blocks automated access (status {result.get('status')}, title {result.get('title')!r}); nothing saved, do not try to get around it"})
        return 2
    recording, rec_seconds, rec_note = None, None, ""
    if not args.no_record:
        rec_s = max(5.0, min(8.0, args.record_seconds))
        mp4 = os.path.join(out_dir, base + ".mp4")
        rec = record_scroll(url, mp4, args.width, min(args.height, 1350), rec_s, args.timeout)
        if rec.get("ok"):
            recording, rec_seconds = base + ".mp4", rec["seconds"]
        else:
            rec_note = rec.get("reason", "")
    now = time.localtime()
    side = {"ok": True, "file": base + ".png", "name": name, "url": url, "final_url": result["final_url"],
            "title": result["title"], "status": result["status"], "width": result["width"], "height": result["height"],
            "full_page": bool(args.full_page), "captured": time.strftime("%Y-%m-%d %H:%M", now),
            "checked": time.strftime("%Y-%m-%d", now), "seconds": round(time.time() - started, 1),
            "recording": recording, "recording_seconds": rec_seconds, "recording_note": rec_note}
    with open(side_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(side, f, ensure_ascii=False, indent=1)
    emit({"ok": True, "reused": False, "file": side["file"], "path": png.replace("\\", "/"), "url": url,
          "final_url": side["final_url"], "title": side["title"], "status": side["status"], "width": side["width"],
          "height": side["height"], "recording": recording, "recording_note": rec_note})
    return 0


if __name__ == "__main__":
    sys.exit(main())
