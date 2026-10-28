"""The review stage's tools (S12, BUILD_SPEC.md S12, M11). Run as `python pipeline/lib/review <command> [options]`:

  mechanical   the mechanical checks of the built composition (review/mechanical.py) -> 12-review/mechanical.json
  style        the style conformance check on the mixed draft (review/style_check.py) -> 12-review/style.json
  audio        the audio checks: S11's verification and the voice's intelligibility (review/audio_check.py) -> audio.json
  filmstrips   the 10 fps filmstrips of the hook and the transitions (review/filmstrip.py) -> 12-review/filmstrips/
  prompt       the digests of the edit review's prompt (review/edit.py) -> 12-review/digest/*.md
  verdict      combine the checks and the qa model's answer into review.json, feedback.json, notes.md; print the
               routing as JSON (review/route.py)
  feedback     print the markdown notes a re-run stage puts in its prompt (empty when none): --stage 09b-text
  strip        one filmstrip: strip VIDEO START SECONDS OUT.png [--fps 10]
  energy       the energy meter (Motion and energy rules E0, review/energy.py): energy VIDEO [--plan merged.json] [--out energy.json]
               [--tokens tokens.json]; `energy calibrate --refs styles/paper-cards/refs --out styles/paper-cards/analysis/energy.json`
               measures the style's reference videos; exit 0 when the video meets every target, 1 when not
Progress lines for the stage script: "@@ACTIVITY text", "@@SAY TAG text", "@@FLAG text", "@@ERROR text".
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from review import common as rc  # noqa: E402


def main(argv: list[str]) -> int:
    rc.mcommon.setup_streams()
    ap = argparse.ArgumentParser(prog="python pipeline/lib/review", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("mechanical", "style", "audio", "filmstrips", "prompt"):
        p = sub.add_parser(name)
        p.add_argument("--run-dir", required=True)
        p.add_argument("--stage-dir", default="")
        p.add_argument("--no-cache", action="store_true", help="mechanical, style: measure again even when the composition or the draft is unchanged")
        if name == "prompt":
            p.add_argument("--round", type=int, default=1)
    v = sub.add_parser("verdict")
    v.add_argument("--run-dir", required=True)
    v.add_argument("--stage-dir", default="")
    v.add_argument("--round", type=int, required=True)
    v.add_argument("--answer", default="", help="the qa model's structured answer (ai() AI_OUT); empty when the call was skipped")
    f = sub.add_parser("feedback")
    f.add_argument("--run-dir", required=True)
    f.add_argument("--stage", required=True)
    s = sub.add_parser("strip")
    s.add_argument("video")
    s.add_argument("start", type=float)
    s.add_argument("seconds", type=float)
    s.add_argument("out")
    s.add_argument("--fps", type=int, default=10)
    e = sub.add_parser("energy")
    e.add_argument("video", help="the video to measure, or `calibrate`")
    e.add_argument("--plan", default="", help="a merged plan: the scenes are measured one by one")
    e.add_argument("--out", default="", help="write the report as JSON")
    e.add_argument("--tokens", default="", help="tokens.json with the energy targets (default: the spec's paper-cards targets)")
    e.add_argument("--targets", default="", help="a JSON file of targets (overrides --tokens)")
    e.add_argument("--refs", default="", help="calibrate: the style's refs folder (look/ and motion/)")
    e.add_argument("--index", default="", help="calibrate: analysis/index.md with the nicknames (default: next to --out)")
    e.add_argument("--still-threshold", type=float, default=None, help="experiments only: the still frame threshold (default frozen, 0.05)")
    a = ap.parse_args(argv)
    try:
        return run(a)
    except Exception as exc:  # the stage turns the message into a code error with the traceback in its log
        traceback.print_exc()
        rc.error(f"{type(exc).__name__}: {exc}")
        return 1


def cache_key(ctx: rc.Ctx, what: str) -> str:
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


def run(a) -> int:
    if a.cmd == "energy":
        from review import energy
        return energy.run_cli(a)
    if a.cmd == "strip":
        from review import filmstrip
        print(filmstrip.strip(rc.mixed(a.video), a.start, a.seconds, rc.mixed(a.out), fps=a.fps))
        return 0
    if a.cmd == "feedback":
        from review import route
        fb = rc.load_json(os.path.join(rc.mixed(a.run_dir), "12-review", "feedback.json"), None)
        sys.stdout.write(route.stage_notes(fb, a.stage))
        return 0
    ctx = rc.Ctx(a.run_dir, a.stage_dir)
    os.makedirs(ctx.stage_dir, exist_ok=True)
    if a.cmd == "mechanical":
        from review import mechanical
        out_path = os.path.join(ctx.stage_dir, "mechanical.json")
        key = cache_key(ctx, "mechanical")
        rep = cached(ctx, "mechanical", key) if not a.no_cache else None
        if rep is not None:
            rc.write_json(out_path, rep)
            rc.log("mechanical: the composition is unchanged since the last round, the previous result stands (12-review/cache)")
        else:
            rep = mechanical.run(ctx, out_path)
            remember(ctx, "mechanical", key, rep)
        rc.log(f"mechanical: {'pass' if rep['pass'] else str(len(rep['issues'])) + ' issues'}; {rep['counts']['hosts']} hosts, {rep['counts']['texts']} text boxes, {rep['counts']['images']} images at {rep['counts']['times']} times; "
               f"emphasis {rep['emphasis']['ok']}/{rep['emphasis']['checked']}; lockup {'ok' if rep['branding'].get('lockup') else 'MISSING'}, avatar {'ok' if rep['branding'].get('avatar') else 'MISSING'}")
        for i in rep["issues"][:12]:
            rc.log(f"  [{i['tag']}] {i['kind']}: {i['text'][:160]}")
        print(json.dumps({"ok": True, "pass": rep["pass"], "issues": len(rep["issues"])}))
        return 0
    if a.cmd == "style":
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
            remember(ctx, "style", key, rep)
        cad = rep["cadence"]["checks"]
        rc.log(f"style: {'pass' if rep['pass'] else str(len(rep['issues'])) + ' issues'}; hero-zone gap median {cad['gap_median_s']['value']} s (allowed {cad['gap_median_s']['allowed']}), gap max {cad['gap_max_s']['value']} s (allowed {cad['gap_max_s']['allowed']}); "
               f"palette {rep['palette']['share_within_delta_e_pct']} percent within delta E {rep['palette']['delta_e']:g}; accent max {rep['accent']['max_frame_share_pct']} percent; mix {rep['loudness']['lufs']} LUFS, {rep['loudness']['true_peak_dbtp']} dBTP")
        for i in rep["issues"]:
            rc.log(f"  [{i['tag']}] {i['kind']}: {i['text'][:160]}")
        print(json.dumps({"ok": True, "pass": rep["pass"], "issues": len(rep["issues"])}))
        return 0
    if a.cmd == "audio":
        from review import audio_check
        rep = audio_check.run(ctx, os.path.join(ctx.stage_dir, "audio.json"))
        rc.log(f"audio: {'pass' if rep['pass'] else str(len(rep['issues'])) + ' issues'}; sfx verification {'ok' if rep['sfx']['pass'] else 'NOT ok'} ({rep['sfx']['sounds']} sounds); voice WER {rep['intelligible']['wer_pct']} percent over {rep['intelligible']['words']} words ({rep['intelligible']['model']})")
        for i in rep["issues"]:
            rc.log(f"  [{i['tag']}] {i['kind']}: {i['text'][:160]}")
        print(json.dumps({"ok": True, "pass": rep["pass"], "issues": len(rep["issues"]), "wer_pct": rep["intelligible"]["wer_pct"]}))
        return 0
    if a.cmd == "filmstrips":
        from review import filmstrip
        out = filmstrip.run_all(ctx)
        rc.write_json(os.path.join(ctx.stage_dir, "filmstrips.json"), out)
        rc.log(f"filmstrips: the hook and {len(out['transitions'])} transitions -> {os.path.join(ctx.stage_dir, 'filmstrips')}")
        print(json.dumps({"ok": True, "hook": out["hook"], "transitions": len(out["transitions"])}))
        return 0
    if a.cmd == "prompt":
        from review import edit
        strips = rc.load_json(os.path.join(ctx.stage_dir, "filmstrips.json"), {}) or {}
        mech = rc.load_json(os.path.join(ctx.stage_dir, "mechanical.json"), None)
        style = rc.load_json(os.path.join(ctx.stage_dir, "style.json"), None)
        audio = rc.load_json(os.path.join(ctx.stage_dir, "audio.json"), None)
        out_dir = os.path.join(ctx.stage_dir, "digest")
        os.makedirs(out_dir, exist_ok=True)
        d = edit.digests(ctx, strips, mech, style, audio, a.round)
        for name, text in d.items():
            rc.write_text(os.path.join(out_dir, name + ".md"), rc.undash(text))
        print(json.dumps({"ok": True, "files": sorted(d), "dir": out_dir, "stills": edit.reference_stills(ctx)}))
        return 0
    if a.cmd == "verdict":
        from review import route
        mech = rc.load_json(os.path.join(ctx.stage_dir, "mechanical.json"), None)
        style = rc.load_json(os.path.join(ctx.stage_dir, "style.json"), None)
        audio = rc.load_json(os.path.join(ctx.stage_dir, "audio.json"), None)
        answer = rc.load_json(rc.mixed(a.answer), None) if a.answer else None
        rev = route.decide(ctx, a.round, mech, style, audio, answer)
        rc.write_json(os.path.join(ctx.stage_dir, "review.json"), rev)
        rc.write_json(os.path.join(ctx.stage_dir, f"review-r{a.round}.json"), rev)
        if answer is not None:
            rc.write_json(os.path.join(ctx.stage_dir, f"edit-r{a.round}.json"), answer)
        fb = route.feedback_record(rev)
        if rev["verdict"] == "fix":
            rc.write_json(os.path.join(ctx.stage_dir, "feedback.json"), fb)
        notes = [f"# Review notes, round {a.round}: {rev['verdict']}", "", "Scores (1 to 5, 4 passes): " + ", ".join(f"{k} {rev['edit_review']['scores'][k]}" for k in route.SCORE_KEYS), ""]
        if rev["edit_review"].get("summary"):
            notes += ["The editor's summary: " + rev["edit_review"]["summary"], ""]
        notes += [f"- [{i['tag']}] {i['text']}" + (" (note only)" if i.get("note_only") else "") for i in rev["issues"]] or ["No issues."]
        rc.write_text(os.path.join(ctx.stage_dir, "notes.md"), "\n".join(notes) + "\n")
        print(json.dumps({"ok": True, "pass": rev["pass"], "verdict": rev["verdict"], "scores": rev["edit_review"]["scores"], "low_scores": rev["summary"]["low_scores"],
                          "issues": len(rev["issues"]), "owners": rev["routing"]["owners"], "reopen": rev["routing"]["reopen"], "activity": rev["routing"]["activity"],
                          "next_model": rev["routing"]["next_model"], "flags": rev["flags"], "cap_reached": rev["cap"]["reached"], "rounds_total": rev["cap"]["rounds_total"]}))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
