#!/usr/bin/env python
"""build/M11/patch-2.py: the review stage's result cache and the quoted Python calls in 12-review/run.sh (a record)."""
import os
import subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
os.chdir(ROOT)


def read(p):
    return open(p, encoding="utf-8").read()


def write(p, s):
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)


p = "pipeline/stages/12-review/run.sh"
s = read(p)
if 'PY="$REELS_PY $LIB/review"' in s:
    s = s.replace('PY="$REELS_PY $LIB/review"\n', '')
    s = s.replace(' $PY ', ' "$REELS_PY" "$LIB/review" ')
    assert "$PY " not in s
    write(p, s)
    print("run.sh: patched")
else:
    print("run.sh: already patched")

p = "pipeline/lib/review/__main__.py"
s = read(p)
if "def cache_key" not in s:
    old = '''    if a.cmd == "mechanical":
        from review import mechanical
        rep = mechanical.run(ctx, os.path.join(ctx.stage_dir, "mechanical.json"))'''
    new = '''    if a.cmd == "mechanical":
        from review import mechanical
        out_path = os.path.join(ctx.stage_dir, "mechanical.json")
        key = cache_key(ctx, "mechanical")
        rep = cached(ctx, "mechanical", key) if not a.no_cache else None
        if rep is not None:
            rc.write_json(out_path, rep)
            rc.log("mechanical: the composition is unchanged since the last round, the previous result stands (12-review/cache)")
        else:
            rep = mechanical.run(ctx, out_path)
            remember(ctx, "mechanical", key, rep)'''
    assert old in s
    s = s.replace(old, new)
    old = '''    if a.cmd == "style":
        from review import style_check
        mech = rc.load_json(os.path.join(ctx.stage_dir, "mechanical.json"), None)
        rep = style_check.run(ctx, mech, os.path.join(ctx.stage_dir, "style.json"))'''
    new = '''    if a.cmd == "style":
        from review import style_check
        mech = rc.load_json(os.path.join(ctx.stage_dir, "mechanical.json"), None)
        out_path = os.path.join(ctx.stage_dir, "style.json")
        key = cache_key(ctx, "style")
        rep = cached(ctx, "style", key) if not a.no_cache else None
        if rep is not None:
            rep = style_check.refresh_loudness(ctx, rep)   # the mix changes with every sound pass: its loudness is measured again
            rc.write_json(out_path, rep)
            rc.log("style: the draft is unchanged since the last round, the previous visual result stands (12-review/cache); the loudness was measured again")
        else:
            rep = style_check.run(ctx, mech, out_path)
            remember(ctx, "style", key, rep)'''
    assert old in s
    s = s.replace(old, new)
    old = '''        p.add_argument("--stage-dir", default="")
        if name == "prompt":'''
    new = '''        p.add_argument("--stage-dir", default="")
        p.add_argument("--no-cache", action="store_true", help="mechanical, style: measure again even when the composition or the draft is unchanged")
        if name == "prompt":'''
    assert old in s
    s = s.replace(old, new)
    old = "def run(a) -> int:"
    new = '''def cache_key(ctx: rc.Ctx, what: str) -> str:
    """What a check's result depends on: the composition (index.html, the compositions and assets by name, size and
    date, plan.json) for the mechanical checks; the draft video and the image boxes for the style check's visual parts."""
    import hashlib
    h = hashlib.sha1()
    if what == "mechanical":
        for rel in ("project/index.html", "plan.json"):
            p = os.path.join(ctx.build_dir, rel)
            if os.path.isfile(p):
                h.update(open(p, "rb").read())
        for sub in ("compositions", "assets"):
            d = os.path.join(ctx.project, sub)
            for root, _dirs, files in (os.walk(d) if os.path.isdir(d) else []):
                for f in sorted(files):
                    st = os.stat(os.path.join(root, f))
                    h.update(f"{os.path.relpath(os.path.join(root, f), d)}:{st.st_size}:{int(st.st_mtime)}".encode())
        h.update(json.dumps(ctx.c("review", {}), sort_keys=True).encode())
    else:
        p = ctx.draft
        if os.path.isfile(p):
            st = os.stat(p)
            h.update(f"{st.st_size}:{int(st.st_mtime)}".encode())
        m = os.path.join(ctx.stage_dir, "mechanical.json")
        if os.path.isfile(m):
            h.update(json.dumps((rc.load_json(m, {}) or {}).get("images_by_time"), sort_keys=True).encode())
        h.update(json.dumps(ctx.c("review", {}), sort_keys=True).encode())
    return what + "-" + h.hexdigest()[:16]


def cached(ctx: rc.Ctx, what: str, key: str):
    return rc.load_json(os.path.join(ctx.stage_dir, "cache", key + ".json"), None)


def remember(ctx: rc.Ctx, what: str, key: str, rep: dict) -> None:
    d = os.path.join(ctx.stage_dir, "cache")
    os.makedirs(d, exist_ok=True)
    for old in os.listdir(d):
        if old.startswith(what + "-"):
            try:
                os.remove(os.path.join(d, old))
            except OSError:
                pass
    rc.write_json(os.path.join(d, key + ".json"), rep)


def run(a) -> int:'''
    s = s.replace(old, new, 1)
    write(p, s)
    print("__main__.py: patched")
else:
    print("__main__.py: already patched")

p = "pipeline/lib/review/style_check.py"
s = read(p)
if "def refresh_loudness" not in s:
    old = "def run(ctx: rc.Ctx, mech: dict | None, out_path: str) -> dict:"
    new = '''def measure_audio(ctx: rc.Ctx, video: str) -> dict:
    """The mixed draft's loudness (ffmpeg loudnorm) and the check against the targets."""
    sys.path.insert(0, os.path.join(rc.LIB, "sfx"))
    from audioio import measure_loudness
    target_i, target_tp = float(ctx.c("voice.loudness_lufs", -14)), float(ctx.c("voice.true_peak_dbtp", -1.5))
    aac_tol = float(ctx.c("review.aac_peak_tolerance_db", 0.5))
    m = measure_loudness(video, target_i, target_tp)
    lufs, tp = m.get("lufs"), m.get("true_peak_dbtp")
    return {"lufs": lufs, "true_peak_dbtp": tp, "target": [target_i, target_tp], "ok": lufs is not None and abs(lufs - target_i) <= 1.0 and (tp is None or tp <= target_tp + aac_tol)}


def refresh_loudness(ctx: rc.Ctx, rep: dict) -> dict:
    """A cached visual result with the loudness of the current mix (the sound pass changes it, the picture does not)."""
    video = ctx.draft_mixed if os.path.isfile(ctx.draft_mixed) else ctx.draft
    loud = measure_audio(ctx, video)
    rep = dict(rep)
    rep["loudness"] = loud
    issues = [i for i in rep.get("issues", []) if i.get("kind") != "loudness"]
    if not loud["ok"]:
        issues.append(rc.issue("sfx", "loudness", f"the mixed draft measures {loud['lufs']} LUFS, {loud['true_peak_dbtp']} dBTP (target {loud['target'][0]} plus or minus 1, at most {loud['target'][1]} dBTP)"))
    rep["issues"] = issues
    rep["pass"] = not issues
    rep["cached_visual"] = True
    return rep


def run(ctx: rc.Ctx, mech: dict | None, out_path: str) -> dict:'''
    s = s.replace(old, new, 1)
    old = '''    audio = summary.get("audio") or {}
    target_i, target_tp = float(ctx.c("voice.loudness_lufs", -14)), float(ctx.c("voice.true_peak_dbtp", -1.5))
    aac_tol = float(ctx.c("review.aac_peak_tolerance_db", 0.5))
    lufs, tp = audio.get("integrated_lufs"), audio.get("true_peak_dbtp")
    loud = {"lufs": lufs, "true_peak_dbtp": tp, "target": [target_i, target_tp], "ok": lufs is not None and abs(lufs - target_i) <= 1.0 and (tp is None or tp <= target_tp + aac_tol)}
    if not loud["ok"]:
        issues.append(rc.issue("sfx", "loudness", f"the mixed draft measures {lufs} LUFS, {tp} dBTP (target {target_i} plus or minus 1, at most {target_tp} dBTP)"))'''
    new = '''    loud = measure_audio(ctx, video)
    if not loud["ok"]:
        issues.append(rc.issue("sfx", "loudness", f"the mixed draft measures {loud['lufs']} LUFS, {loud['true_peak_dbtp']} dBTP (target {loud['target'][0]} plus or minus 1, at most {loud['target'][1]} dBTP)"))'''
    assert old in s
    s = s.replace(old, new, 1)
    write(p, s)
    print("style_check.py: patched")
else:
    print("style_check.py: already patched")
for f in ("pipeline/lib/review/__main__.py", "pipeline/lib/review/style_check.py"):
    subprocess.run(["python", "-c", f"import ast; ast.parse(open('{f}', encoding='utf-8').read())"], check=True)
subprocess.run(["bash", "-n", "pipeline/stages/12-review/run.sh"], check=True)
print("syntax ok")
