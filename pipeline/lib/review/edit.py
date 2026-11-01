"""pipeline/lib/review/edit.py: the edit review's material and its verdict (BUILD_SPEC.md S12, M11).

The qa model (config models.qa, a fresh session per round, never the builder) reads: the contact sheet (one still per
beat), a 10 fps filmstrip of the hook and one per transition, two or three stills of the look references, and the
scene list with sound-map.txt beside it. It scores 1 to 5: stop (does frame 1 stop the scroll), hierarchy (hierarchy
and legibility), look (would it sit on the same account), variety (motion variety), sync (with the voice), sound
(sound fit), generic (nothing looks generic), requirements (the problem, the share line and the keyword are visible);
it says whether the branding feels natural (an [animation] issue when it feels like an ad) and lists every issue with
its tag. It passes when every score is at least 4 (route.py).

  digests(ctx, strips) -> {name: markdown} written under 12-review/digest/ by the CLI: scenes (the scene list with
                          the sounds beside it), requirements, images (the paths to read), checks (what the code
                          already verified this round), history (the earlier rounds' issues)
  reference_stills(ctx) -> up to 3 look-reference stills
  SCORE_KEYS, score_table(scores)
"""
from __future__ import annotations

import glob
import os

from review import common as rc

SCORE_KEYS = ("stop", "hierarchy", "look", "variety", "sync", "sound", "generic", "requirements")
SCORE_TEXT = {"stop": "frame 1 stops the scroll", "hierarchy": "hierarchy and legibility", "look": "matches the look (would sit on the same account)",
              "variety": "motion variety", "sync": "sync with the voice", "sound": "sound fit", "generic": "nothing looks generic",
              "requirements": "the requirements are visible (the problem, the share line, the keyword)"}


def reference_stills(ctx: rc.Ctx, n: int = 3) -> list[str]:
    """One full frame from each look reference, the second of each (the first is the empty opening frame), then a
    third from the second reference."""
    out: list[str] = []
    for nick in ("v01", "v02"):
        frames = sorted(glob.glob(os.path.join(ctx.analysis_dir, nick, "full_*.png")))
        if len(frames) >= 2:
            out.append(rc.mixed(frames[1]))
        elif frames:
            out.append(rc.mixed(frames[0]))
    frames2 = sorted(glob.glob(os.path.join(ctx.analysis_dir, "v02", "full_*.png")))
    if len(frames2) >= 4 and len(out) < n:
        out.append(rc.mixed(frames2[3]))
    return out[:n]


def scenes_md(ctx: rc.Ctx) -> str:
    beats = {b.get("id"): b for b in (ctx.script.get("beats") or [])}
    cues = sorted((ctx.cues.get("cues") or []), key=lambda c: c["ms"])
    trans = {t.get("to"): t for t in ctx.plan.get("transitions", [])}
    lines = ["| scene | beat | time | spoken | on screen (components, texts) | arrives by | sounds |", "|---|---|---|---|---|---|---|"]
    for s in ctx.plan.get("scenes", []):
        b = beats.get(s.get("beat"), {})
        comps = []
        for c in s.get("components", []):
            p = c.get("props", {})
            txt = p.get("title") or p.get("text") or p.get("keyword") or p.get("label") or ""
            comps.append(c["component"] + (f' "{str(txt)[:40]}"' if txt else ""))
        snd = [f"{c['ms'] / 1000:.1f}s {c['cue_type']}" for c in cues if int(s["start_ms"]) <= c["ms"] < int(s["end_ms"])]
        t = trans.get(s["id"])
        arrives = f"{t.get('type')} {t.get('duration_ms')} ms" if t else "start"
        lines.append(f"| {s['id']} | {s.get('beat')} ({s.get('beat_type')}) | {s['start_ms'] / 1000:.1f} to {s['end_ms'] / 1000:.1f} s | {rc.undash(str(b.get('spoken', ''))[:90])} | {rc.undash('; '.join(comps))} | {arrives} | {', '.join(snd) or 'none'} |")
    sm = os.path.join(ctx.run_dir, "11-sfx", "sound-map.txt")
    sound_map = open(sm, encoding="utf-8").read().strip() if os.path.isfile(sm) else "(no sound-map.txt: the sound stage did not run)"
    return "\n".join(lines) + "\n\n### sound-map.txt (every sound: time, cue type, file, the visual event it sits on)\n\n```\n" + rc.undash(sound_map) + "\n```\n"


def requirements_md(ctx: rc.Ctx) -> str:
    exp = rc.load_json(os.path.join(ctx.run_dir, "02-expansion", "expansion.json"), {}) or {}
    ask = ctx.script.get("ask") or {}
    hook = ctx.script.get("hook") or {}
    sol = ctx.solution
    lines = [f"- The viewer's problem: {rc.undash(exp.get('problem', '(not recorded)'))}",
             f"- The share line (identity plus takeaway): {rc.undash(exp.get('share_identity', ''))}; {rc.undash(exp.get('takeaway', ''))}",
             f"- The comment keyword: {ask.get('keyword', '(none)')} (the ask line: {rc.undash(ask.get('line', ''))})",
             f"- The hook (spoken): {rc.undash(hook.get('spoken', ''))}; on screen: {rc.undash(hook.get('on_screen', ''))}",
             f"- The solution of this reel: {sol.get('type')}" + (f" ({sol.get('name')})" if sol.get("name") else "") + ". FlashFX branding is allowed only at the CTA (the DM card and the lockup) unless the solution is flashfx.",
             f"- Length: {ctx.duration_ms / 1000:.1f} s, {len(ctx.plan.get('scenes', []))} scenes, {len(ctx.cues.get('cues') or [])} sounds."]
    return "\n".join(lines) + "\n"


def images_md(ctx: rc.Ctx, strips: dict) -> str:
    lines = [f"- Contact sheet, one still per beat (plus the hook breath): {rc.mixed(os.path.join(ctx.build_dir, 'contact-sheet.png'))}",
             f"- Filmstrip of the hook, 10 fps: {rc.mixed(strips.get('hook', ''))}"]
    for t in strips.get("transitions", []):
        lines.append(f"- Filmstrip of the transition {t['from']} to {t['to']} ({t['type']}, {t['transition_ms']} ms, at {t['ms'] / 1000:.1f} s), 10 fps: {rc.mixed(t['png'])}")
    refs = reference_stills(ctx)
    if refs:
        lines.append("- Stills from the look references (the account this reel must sit beside):")
        lines += [f"  - {p}" for p in refs]
    else:
        lines.append("- (no look-reference stills available on this machine: judge the look against style.md)")
    return "\n".join(lines) + "\n"


def checks_md(mech: dict | None, style: dict | None, audio: dict | None) -> str:
    def part(name: str, rep: dict | None) -> str:
        if not rep:
            return f"- {name}: not run"
        if rep.get("pass"):
            return f"- {name}: passed"
        return f"- {name}: {len(rep.get('issues', []))} issue(s): " + "; ".join(rc.undash(i.get("text", ""))[:140] for i in rep.get("issues", [])[:6])
    lines = ["The code checked these already (do not repeat them, build on them):", part("mechanical checks (zones, right rail, fonts, overlaps, contrast, emphasis timing, branding)", mech),
             part("style conformance (cadence, palette, accent share, loudness)", style), part("audio (the sound verification, the voice's intelligibility in the mix)", audio)]
    if mech and mech.get("branding"):
        b = mech["branding"]
        lk, av = b.get("lockup") or {}, b.get("avatar") or {}
        lines.append(f"- branding measured: lockup {lk.get('file', 'none')} {lk.get('box', {}).get('w', 0)} px wide on a {lk.get('surface', '?')} surface; avatar {av.get('file', 'none')} {av.get('box', {}).get('w', 0)} px; FlashFX logos outside the CTA: {len(b.get('outside_cta', []))}")
    return "\n".join(lines) + "\n"


def history_md(ctx: rc.Ctx, round_n: int) -> str:
    rows = []
    for r in range(1, round_n):
        rep = rc.load_json(os.path.join(ctx.stage_dir, f"review-r{r}.json"), None)
        if not rep:
            continue
        sc = (rep.get("edit_review") or {}).get("scores") or {}
        rows.append(f"- Round {r}: scores " + ", ".join(f"{k} {sc.get(k, '?')}" for k in SCORE_KEYS) + f"; {len(rep.get('issues', []))} issues; routed to {', '.join(rep.get('routing', {}).get('owners', []) or ['nothing'])}")
        for i in rep.get("issues", [])[:8]:
            rows.append(f"  - [{i.get('tag')}] {rc.undash(i.get('text', ''))[:160]}")
    if not rows:
        return "This is the first round: no earlier review of this reel.\n"
    return "Earlier rounds of this reel (the draft was rebuilt after each; check whether the issues are gone):\n" + "\n".join(rows) + "\n"


def digests(ctx: rc.Ctx, strips: dict, mech: dict | None, style: dict | None, audio: dict | None, round_n: int) -> dict:
    return {"scenes": scenes_md(ctx), "requirements": requirements_md(ctx), "images": images_md(ctx, strips), "checks": checks_md(mech, style, audio), "history": history_md(ctx, round_n)}


def score_table(scores: dict) -> str:
    return ", ".join(f"{k} {scores.get(k, '?')}" for k in SCORE_KEYS)
