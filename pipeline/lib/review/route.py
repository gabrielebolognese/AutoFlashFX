"""pipeline/lib/review/route.py: the verdict of a review round and its fix routing (BUILD_SPEC.md S12, M11).

pass: the mechanical, style and audio checks passed and every edit-review score is at least 4.
fail: every issue (the code's and the model's) is tagged; each tag names the step that owns it ([voice] 08-voiceover,
[animation] 09a-animations, [text] 09b-text, [transition] 09c-transitions, [sfx] 11-sfx); the earliest owner and every
step after it run again (the review included), so a visual fix rebuilds the project and re-mixes the sounds. A [voice]
issue routes only when it names a word in quotes (the voice is deterministic: S8 can respell a named word, it cannot
re-read an opinion); otherwise it becomes a NEEDS REVIEW note. Caps: config caps.review_rounds_opus (3) rounds with the
opus director and builder, then caps.review_rounds_fable (2) with fable; a reel still failing after the last round
goes on to the export with a NEEDS REVIEW flag that carries the review notes. A failing round whose issues route
nowhere also goes on (flagged), never loops.

  decide(ctx, round_n, mech, style, audio, answer) -> the review record (review.json's content)
  feedback_record(review) -> feedback.json's content (what the re-run stages read)
  stage_notes(feedback, stage) -> the markdown section a re-run stage puts in its prompt (empty when none)
"""
from __future__ import annotations

import re

from review import common as rc
from review.edit import SCORE_KEYS, SCORE_TEXT

QUOTED = re.compile(r"[\"“‘']([A-Za-z][A-Za-z0-9'.-]{1,30})[\"”’']")


def model_for_round(ctx: rc.Ctx, round_n: int) -> tuple[str, str]:
    """(label, model name) of the director that fixes before review round round_n."""
    opus_rounds = int(ctx.c("caps.review_rounds_opus", 3))
    if round_n <= opus_rounds:
        return "opus", str(ctx.c("models.visual_director.model", "opus"))
    return "fable", str(ctx.c("models.visual_director_escalation.model", ctx.c("models.builder_escalation.model", "fable")))


def normalize_issue(i: dict, source: str) -> dict | None:
    tag = str(i.get("tag", "")).strip().strip("[]").lower()
    if tag not in rc.TAGS:
        tag = "animation" if source == "model" else tag
    text = rc.undash(str(i.get("text", "")).strip())
    if not text or tag not in rc.TAGS:
        return None
    out = {"tag": tag, "text": text, "source": source, "stage": rc.TAG_STAGE[tag]}
    for k in ("kind", "scene", "instance", "ms", "severity"):
        if i.get(k) not in (None, ""):
            out[k] = i[k]
    return out


def routable(issue: dict) -> bool:
    if issue["tag"] != "voice":
        return True
    return bool(QUOTED.search(issue["text"]))


def decide(ctx: rc.Ctx, round_n: int, mech: dict | None, style: dict | None, audio: dict | None, answer: dict | None) -> dict:
    cap_opus, cap_fable = int(ctx.c("caps.review_rounds_opus", 3)), int(ctx.c("caps.review_rounds_fable", 2))
    cap_total = cap_opus + cap_fable
    # no editor's answer (REELS_REVIEW_SKIP_EDIT, tests): the code checks alone decide and the scores count as 5
    scores = {k: int((answer or {}).get("scores", {}).get(k, 5 if answer is None else 0) or 0) for k in SCORE_KEYS}
    branding_natural = bool((answer or {}).get("branding_natural", True))
    issues: list[dict] = []
    for rep, src in ((mech, "mechanical"), (style, "style"), (audio, "audio")):
        for i in (rep or {}).get("issues", []):
            n = normalize_issue(i, src)
            if n:
                issues.append(n)
    model_issues = []
    for i in (answer or {}).get("issues", []) or []:
        n = normalize_issue(i, "model")
        if n:
            model_issues.append(n)
    if answer is not None and not branding_natural:
        model_issues.append({"tag": "animation", "text": "the FlashFX branding feels like an ad, not a natural part of the reel (the edit review): " + rc.undash(str((answer or {}).get("branding_note", "") or (answer or {}).get("summary", "")))[:200],
                             "source": "model", "stage": "09a-animations", "kind": "branding_feel"})
    checks_pass = bool((mech or {}).get("pass")) and bool((style or {}).get("pass")) and bool((audio or {}).get("pass"))
    low = [k for k in SCORE_KEYS if scores[k] < 4]
    scores_pass = not low
    passed = checks_pass and scores_pass
    if not scores_pass:
        issues += model_issues
    else:
        for m in model_issues:
            m["note_only"] = True
    acting = [i for i in issues if not i.get("note_only")]
    routes = [i for i in acting if routable(i)]
    flags_only = [i for i in acting if not routable(i)]
    owners = sorted({i["stage"] for i in routes}, key=rc.STAGE_ORDER.index)
    verdict = "pass"
    reopen: list[str] = []
    activity = ""
    next_model = ["", ""]
    flags: list[str] = []
    cap_reached = round_n >= cap_total
    if not passed:
        if owners and not cap_reached:
            verdict = "fix"
            first = owners[0]
            reopen = rc.STAGE_ORDER[rc.STAGE_ORDER.index(first):]
            tags = sorted({i["tag"] for i in routes if i["stage"] == first}, key=rc.TAGS.index)
            label, model = model_for_round(ctx, round_n + 1)
            next_model = [label, model]
            activity = f"fixing [{tags[0] if tags else 'animation'}] issues (round {round_n + 1}, {label})"
        elif owners and cap_reached:
            verdict = "cap"
            flags.append(f"edit review: still failing after {round_n} rounds ({cap_opus} opus, {cap_fable} fable); exported as it is. Scores: " + ", ".join(f"{k} {scores[k]}" for k in SCORE_KEYS) +
                         ". Open issues: " + " | ".join(f"[{i['tag']}] {i['text'][:120]}" for i in acting[:6]))
        else:
            verdict = "flag"
            flags.append("edit review: issues nothing upstream can act on; exported as it is. " + " | ".join(f"[{i['tag']}] {i['text'][:120]}" for i in acting[:6]))
    for i in flags_only:
        if verdict == "fix":
            flags.append(f"edit review (round {round_n}): [{i['tag']}] {i['text'][:160]}")
    summary = {"round": round_n, "pass": passed, "verdict": verdict, "scores": scores, "low_scores": low, "checks_pass": checks_pass}
    return {"written_by": "12-review", "round": round_n, "pass": passed, "verdict": verdict,
            "mechanical": {"pass": bool((mech or {}).get("pass")), "issues": len((mech or {}).get("issues", [])), "texts": (mech or {}).get("counts", {}).get("texts"), "emphasis": (mech or {}).get("emphasis", {}).get("ok"), "emphasis_checked": (mech or {}).get("emphasis", {}).get("checked")},
            "style": {"pass": bool((style or {}).get("pass")), "issues": len((style or {}).get("issues", [])), "cadence": (style or {}).get("cadence", {}).get("checks"), "palette_share_pct": (style or {}).get("palette", {}).get("share_within_delta_e_pct"), "accent_max_pct": (style or {}).get("accent", {}).get("max_frame_share_pct"), "loudness": (style or {}).get("loudness")},
            "audio": {"pass": bool((audio or {}).get("pass")), "issues": len((audio or {}).get("issues", [])), "wer_pct": (audio or {}).get("intelligible", {}).get("wer_pct"), "sfx_pass": (audio or {}).get("sfx", {}).get("pass")},
            "edit_review": {"scores": scores, "scored": {k: SCORE_TEXT[k] for k in SCORE_KEYS}, "issues": model_issues, "branding_natural": branding_natural, "summary": rc.undash(str((answer or {}).get("summary", "")))[:600], "answered": answer is not None},
            "issues": issues, "routing": {"owners": owners, "reopen": reopen, "activity": activity, "next_model": next_model, "flags_only": [i["text"][:160] for i in flags_only]},
            "cap": {"reached": cap_reached, "rounds_total": cap_total, "opus": cap_opus, "fable": cap_fable}, "flags": flags, "summary": summary}


def feedback_record(review: dict) -> dict:
    by_stage: dict = {}
    for i in review.get("issues", []):
        if i.get("note_only") or not routable(i):
            continue
        by_stage.setdefault(i["stage"], []).append(i)
    return {"written_by": "12-review", "round": review.get("round"), "verdict": review.get("verdict"), "scores": (review.get("edit_review") or {}).get("scores"),
            "summary": (review.get("edit_review") or {}).get("summary"), "issues": [i for i in review.get("issues", []) if not i.get("note_only")], "by_stage": by_stage,
            "reopen": (review.get("routing") or {}).get("reopen", [])}


def stage_notes(feedback: dict | None, stage: str) -> str:
    if not feedback:
        return ""
    mine = (feedback.get("by_stage") or {}).get(stage) or []
    if not mine and stage not in (feedback.get("reopen") or []):
        return ""
    lines = [f"## Notes from the edit review (round {feedback.get('round')})", "",
             "The previous draft of this reel was reviewed (code checks plus an editor's read of the contact sheet, the filmstrips and the sound map) and sent back."]
    sc = feedback.get("scores") or {}
    if sc:
        lines.append("Scores (1 to 5, 4 passes): " + ", ".join(f"{k} {sc.get(k, '?')}" for k in SCORE_KEYS) + ".")
    if feedback.get("summary"):
        lines.append("The editor's summary: " + rc.undash(str(feedback["summary"])))
    if mine:
        lines += ["", "These issues are yours to fix in this pass (keep everything else as it was):"]
        lines += [f"- [{i['tag']}] {rc.undash(i['text'])}" + (f" (scene {i['scene']})" if i.get("scene") else "") for i in mine]
    else:
        lines += ["", "No issue was routed to this pass; it runs again because an earlier pass changed. Keep your earlier choices unless the changes above require otherwise."]
    others = [(s, v) for s, v in (feedback.get("by_stage") or {}).items() if s != stage and v]
    if others:
        lines += ["", "For context, the other passes were asked to fix:"]
        for s, v in others:
            lines += [f"- {s}: " + "; ".join(rc.undash(i["text"])[:120] for i in v[:4])]
    return "\n".join(lines) + "\n"
