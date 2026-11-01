#!/usr/bin/env python
"""screenshot.py: capture a real web page as a research asset (BUILD_SPEC.md section 5, S1).

  python pipeline/lib/screenshot.py URL NAME [--out-dir DIR] [--width 1080] [--height 1920] [--full-page]
                                    [--timeout 45] [--again]
  The stages and the research model call it through the wrapper: bash pipeline/bin/screenshot URL NAME

Writes DIR/NN-<name>.png (1080 px wide by default, the first screen only; --full-page for the whole page, capped
at 4 screens) and the sidecar DIR/NN-<name>.json with url, final_url, title, status, width, height, full_page,
captured (date and time), checked (date). DIR is --out-dir or $REELS_ASSETS_DIR and must sit inside the runs
folder ($REELS_RUNS, else $REELS_ROOT/runs; the system temp folder only when neither is set): the tool never
writes anywhere else, so a model that calls it cannot touch library/, styles/ or ideas.txt through it. The same URL captured twice in one
folder returns the first capture (--again forces a new one).

It never gets around a site that blocks automated access (BUILD_SPEC.md S1): a 401, 403, 429 or 503 answer, or a
page that is a bot check (Cloudflare's "Just a moment", "Verify you are human", "Access denied", a captcha), is
reported as blocked and nothing is saved. Plain headless Chromium: no user agent spoofing, no stealth plugins.

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
    """Where the tool may write: the runs folder of the state root ($REELS_RUNS, else $REELS_ROOT/runs); the system
    temp folder only when neither is set (a bare call from a shell or a unit test)."""
    roots = []
    runs = os.environ.get("REELS_RUNS")
    if runs:
        roots.append(winpath(runs))
    root = os.environ.get("REELS_ROOT")
    if root:
        roots.append(os.path.join(winpath(root), "runs"))
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
            emit({"ok": True, "reused": True, "file": prior["file"], "path": os.path.join(out_dir, prior["file"]).replace("\\", "/"),
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
    now = time.localtime()
    side = {"ok": True, "file": base + ".png", "name": name, "url": url, "final_url": result["final_url"],
            "title": result["title"], "status": result["status"], "width": result["width"], "height": result["height"],
            "full_page": bool(args.full_page), "captured": time.strftime("%Y-%m-%d %H:%M", now),
            "checked": time.strftime("%Y-%m-%d", now), "seconds": round(time.time() - started, 1)}
    with open(side_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(side, f, ensure_ascii=False, indent=1)
    emit({"ok": True, "reused": False, "file": side["file"], "path": png.replace("\\", "/"), "url": url,
          "final_url": side["final_url"], "title": side["title"], "status": side["status"], "width": side["width"],
          "height": side["height"]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
