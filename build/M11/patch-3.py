#!/usr/bin/env python
"""build/M11/patch-3.py: after test-m11 section 1's first run (a record).

1. pipeline/lib/review/mechanical.py: the surface under a logo is measured with the logo hidden (the median of the
   pixels inside its drawn box), not from the ring around its box (a lockup filling a dark window body was judged
   against the light chrome around it).
2. motion-lib/compositions/card.html: a brand image in a card's image slot keeps its aspect ratio (object-fit contain);
   screenshots keep cover.
3. pipeline/tests/test-m11.sh: the activity lines are read from the stage's captured output when it runs outside the
   runner; the planted unplanned sound is long enough to count as a sound (over 30 ms above -55 dBFS).
"""
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
os.chdir(ROOT)


def read(p):
    return open(p, encoding="utf-8").read()


def write(p, s):
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)


def replace_once(p, old, new, label):
    s = read(p)
    if old not in s:
        if new in s:
            print(f"{p}: already patched ({label})")
            return
        raise SystemExit(f"{p}: anchor not found ({label}): {old[:90]!r}")
    write(p, s.replace(old, new, 1))
    print(f"{p}: patched ({label})")


# 1. mechanical.py
p = "pipeline/lib/review/mechanical.py"
replace_once(p, '''        images.push({ id: el.id || "", cls: String(el.className || ""), src: el.getAttribute("src") || "", x: r.left, y: r.top, w: r.width, h: r.height,
                      opacity: effOpacity(el), nw: el.naturalWidth, nh: el.naturalHeight, fit: cs.objectFit, bg: bgOf(el.parentElement) });''',
             '''        images.push({ id: el.id || "", cls: String(el.className || ""), src: el.getAttribute("src") || "", x: r.left, y: r.top, w: r.width, h: r.height,
                      opacity: effOpacity(el), nw: el.naturalWidth, nh: el.naturalHeight, fit: cs.objectFit, bg: bgOf(el.parentElement), idx: parseInt(el.getAttribute("data-rv-idx") || "-1", 10) });''',
             "image idx")
replace_once(p, '''def ring_rgb(img, box: dict, inner: int = 2, outer: int = 7):''',
             '''def inside_rgb(img, box: dict):
    """The median color inside a box (the surface under a logo, measured with the logo hidden)."""
    import numpy as np
    W, H = img.size
    x0, y0 = max(0, int(math.floor(box["x"]))), max(0, int(math.floor(box["y"])))
    x1, y1 = min(W, int(math.ceil(box["x"] + box["w"]))), min(H, int(math.ceil(box["y"] + box["h"])))
    if x1 <= x0 or y1 <= y0:
        return None
    arr = np.asarray(img.crop((x0, y0, x1, y1)).convert("RGB"))
    med = np.median(arr.reshape(-1, 3), axis=0)
    return (float(med[0]), float(med[1]), float(med[2]))


HIDE_JS = """
(args) => { const el = document.querySelector('[data-rv-idx="' + args.idx + '"]'); if (!el) return false; el.style.visibility = args.hide ? "hidden" : ""; return true; }
"""


def ring_rgb(img, box: dict, inner: int = 2, outer: int = 7):''',
             "inside_rgb")
replace_once(p, '''                for im in row.get("images", []):
                    if im["opacity"] < VISIBLE or im["w"] < 1 or im["h"] < 1:
                        continue
                    im.update({"instance": host["id"], "component": host["component"], "scene": host["scene"]})
                    if shot is not None:
                        im["bg_rgb"] = ring_rgb(shot, {"x": im["x"], "y": im["y"], "w": im["w"], "h": im["h"]}, inner=3, outer=9)
                    per_time[T]["images"].append(im)''',
             '''                for im in row.get("images", []):
                    if im["opacity"] < VISIBLE or im["w"] < 1 or im["h"] < 1:
                        continue
                    im.update({"instance": host["id"], "component": host["component"], "scene": host["scene"]})
                    if shot is not None and im["src"].startswith("assets/brand/") and im.get("idx", -1) >= 0:
                        # the surface under a logo: the pixels behind it, with the logo hidden for one screenshot
                        png2 = os.path.join(shots_dir, f"{host['id']}-{T}-nologo.png")
                        if h.page.evaluate(HIDE_JS, {"idx": im["idx"], "hide": True}):
                            h.page.screenshot(path=png2)
                            counts["screenshots"] += 1
                            with Image.open(png2) as bare:
                                im["bg_rgb"] = inside_rgb(bare.convert("RGB"), drawn_box(im))
                            h.page.evaluate(HIDE_JS, {"idx": im["idx"], "hide": False})
                            try:
                                os.remove(png2)
                            except OSError:
                                pass
                    elif shot is not None:
                        im["bg_rgb"] = ring_rgb(shot, {"x": im["x"], "y": im["y"], "w": im["w"], "h": im["h"]}, inner=3, outer=9)
                    per_time[T]["images"].append(im)''',
             "surface under the logo")
replace_once(p, """                with its aspect ratio locked, its use_on matching the luminance of the surface under it and readable
                against it (3:1), the bolt at least 64 px tall, clear space of a quarter of the bolt's height [animation]""",
             """                with its aspect ratio locked, its use_on matching the luminance of the surface under it (the pixels behind
                it, measured with the logo hidden) and readable against it (3:1), the bolt at least 64 px tall, clear
                space of a quarter of the bolt's height                                                       [animation]""",
             "doc")

# 2. card.html: a brand image keeps its aspect ratio
p = "motion-lib/compositions/card.html"
replace_once(p, '''    #card-image img { display: block; width: 100%; height: 100%; object-fit: cover; object-position: top center; }''',
             '''    #card-image img { display: block; width: 100%; height: 100%; object-fit: cover; object-position: top center; }
    #card-image img.pc-logo-fit { object-fit: contain; object-position: center; }  /* a logo file keeps its aspect ratio (tweaks.md Branding) */''',
             "logo css")
replace_once(p, '''        document.getElementById("card-img").src = v.image;''',
             '''        document.getElementById("card-img").src = v.image;
        if (/\\/brand\\//.test(v.image)) document.getElementById("card-img").className = "pc-logo-fit";''',
             "logo class")

# 3. test-m11.sh
p = "pipeline/tests/test-m11.sh"
replace_once(p, '''  assert_grep "^activity: adding sound effects \\([0-9]+ sounds\\)$" "$RD/11-sfx/stage.log" "activity \\"adding sound effects (N sounds)\\" was published"
  assert_grep "^activity: verifying sound sync and loudness$" "$RD/11-sfx/stage.log" "activity \\"verifying sound sync and loudness\\" was published"''',
             '''  # a stage run outside the runner prints its log to the captured output (the runner would route it into stage.log)
  assert_grep "^activity: adding sound effects \\([0-9]+ sounds\\)$" "$SANDBOX/s11.out" "activity \\"adding sound effects (N sounds)\\" was published"
  assert_grep "^activity: verifying sound sync and loudness$" "$SANDBOX/s11.out" "activity \\"verifying sound sync and loudness\\" was published"''',
             "activities")
replace_once(p, '''stem2 = stem.copy()
n = int(0.05 * sr); i = int(quiet * sr / 1000)
stem2[i:i + n] += 0.1 * np.exp(-np.arange(n) / (0.01 * sr)).astype(np.float32)''',
             '''stem2 = stem.copy()
n = int(0.25 * sr); i = int(quiet * sr / 1000)   # a 250 ms burst at -20 dBFS, decaying: well over the 30 ms a stray sound needs
stem2[i:i + n] += (0.1 * np.exp(-np.arange(n) / (0.08 * sr)) * np.sin(np.arange(n) * 2 * np.pi * 1800 / sr)).astype(np.float32)''',
             "planted click")
print("done")
