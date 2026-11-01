"""writemap.py: styles/sfx/sfx-map.json and styles/sfx/SFX-MAP.md (BUILD_SPEC.md 2.6, item 7).

  assemble(...) -> the map dict (everything measured, classified and ranked; the pools; the excluded files with
                   their reasons; the waiting and unclassified files; the overrides in force; the settings)
  render_md(map) -> the readable report: counts per category, the pools, short pools, waiting files, excluded
                    files, overrides, thresholds
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CUE_TYPES, MAP_VERSION, MEASURE_VERSION, clean, now_text  # noqa: E402

FILE_FIELDS = [
    "id", "path", "folder", "name", "ext", "size", "mtime", "measure_version", "decode_error", "cache",
    "codec", "channels", "source_channels", "sample_rate", "bits",
    "duration_s", "peak_dbfs", "true_peak_dbtp", "lufs", "noise_floor_db", "snr_db", "floor_p5_db",
    "onset_s", "peak_s", "attack_s", "tail_s", "end_s", "effective_s", "rise_s", "pad_start_s", "pad_end_s",
    "centroid_hz", "clipped_samples", "clip_runs", "gain_db",
    "tags", "category", "whoosh_speed", "source", "confidence", "candidates", "fit", "model", "contradiction",
    "unclear", "hint", "excluded", "waiting", "unclassified", "banned", "pinned", "notes",
]


def assemble(pack_label: str, files: list[dict], pools: dict, waiting: list, unclassified: list, short: list,
             overrides_info: dict, settings: dict, hashes: dict, model_name: str, previews: dict,
             model_calls: int) -> dict:
    files_out = []
    for f in files:
        entry = {k: f.get(k) for k in FILE_FIELDS}
        entry["pooled"] = sorted(cue for cue, pool in pools.items() if any(e["id"] == f["id"] for e in pool))
        files_out.append(entry)
    excluded = [{"id": f["id"], "path": f["path"], "reason": f["excluded"]} for f in files if f.get("excluded")]
    by_category: dict[str, int] = {}
    for f in files:
        cat = f.get("category") or ("unclassified" if f.get("unclear") else "none")
        if cat == "whoosh" and f.get("whoosh_speed"):
            cat = f"whoosh {f['whoosh_speed']}"
        by_category[cat] = by_category.get(cat, 0) + 1
    n_model = sum(1 for f in files if f.get("source") == "model")
    n_rules = sum(1 for f in files if f.get("source") == "rules" and not f.get("unclear") and not f.get("decode_error"))
    return {
        "version": MAP_VERSION,
        "measure_version": MEASURE_VERSION,
        "built": now_text(),
        "source": pack_label,
        "folder_sha1": hashes.get("folder_sha1", ""),
        "overrides_sha1": hashes.get("overrides_sha1", ""),
        "settings_sha1": hashes.get("settings_sha1", ""),
        "model": model_name,
        "settings": settings,
        "cue_types": dict(CUE_TYPES),
        "counts": {
            "files": len(files),
            "mapped": len(files) - len(excluded),
            "excluded": len(excluded),
            "waiting": len(waiting),
            "unclassified": len(unclassified),
            "pooled": sum(1 for f in files_out if f["pooled"]),
            "by_rules": n_rules,
            "by_model": n_model,
            "model_calls_this_build": model_calls,
            "by_category": dict(sorted(by_category.items())),
            "by_cue_type": {cue: len(pools.get(cue) or []) for cue in CUE_TYPES},
        },
        "short_pools": short,
        "pools": {cue: pools.get(cue) or [] for cue in CUE_TYPES},
        "waiting": waiting,
        "unclassified": unclassified,
        "excluded": excluded,
        "overrides": overrides_info,
        "previews": previews,
        "files": files_out,
    }


def fmt(v, digits=2, unit=""):
    if v is None:
        return "-"
    try:
        return f"{float(v):.{digits}f}{unit}"
    except (TypeError, ValueError):
        return str(v)


def render_md(m: dict) -> str:
    c = m["counts"]
    s = m["settings"]
    lines = [f"# SFX map: {m['source']}", ""]
    lines.append(f"Built {m['built']} by pipeline/bin/build-sfx-map (map version {m['version']}). {c['files']} audio files: "
                 f"{c['mapped']} mapped ({c['pooled']} in at least one pool), {c['excluded']} excluded, {c['waiting']} waiting for "
                 f"your approval, {c['unclassified']} not classified yet. {c['by_rules']} classified by name rules, {c['by_model']} by the "
                 f"indexer model ({m['model'] or 'none'}) from their names and measurements"
                 f"{' (' + str(c['model_calls_this_build']) + ' model call(s) in this build)' if c.get('model_calls_this_build') else ', no model call in this build'}.")
    lines += ["", "## How to use it", "",
              "- Listen: `styles/sfx/previews/<cue type>.wav` plays that pool's sounds 1 second apart, best fit first, in the order of `previews/<cue type>.txt`.",
              "- Ban or pin: a line in `styles/sfx/overrides.txt` (`ban: <path>` or `pin: <cue type>: <path>`), then `bash pipeline/bin/build-sfx-map`. A pin goes first in its pool and approves a file from the waiting list.",
              "- The map rebuilds itself when the folder changes (new, removed or edited files) or overrides.txt changes; an unchanged folder is not re-measured and makes no model call. The sound stage (S11) runs the script before picking sounds.",
              "- Levels: every file has a gain that brings its sample peak to "
              f"{fmt(s['normalize_peak_dbfs'], 0)} dBFS; the normalized 48 kHz copies live in `styles/sfx/.cache/` (the originals are never modified).",
              ""]
    lines += ["## Pools", ""]
    for cue in CUE_TYPES:
        pool = m["pools"].get(cue) or []
        short = " (SHORT: fewer than " + str(s["min_pool"]) + ")" if cue in m["short_pools"] else ""
        lines.append(f"### {cue} ({len(pool)} sound{'s' if len(pool) != 1 else ''}){short}")
        lines.append("")
        lines.append(f"{CUE_TYPES[cue]}.")
        lines.append("")
        if not pool:
            lines.append("(no sound fits; add files to styles/sfx/ or pin one in overrides.txt)")
            lines.append("")
            continue
        lines.append("| # | file | sound | attack | fit | gain | from |")
        lines.append("|---|------|-------|--------|-----|------|------|")
        for i, e in enumerate(pool, start=1):
            src = "pinned" if e.get("pinned") else ("rules" if e.get("source") == "rules" else f"model {fmt(e.get('confidence'), 2)}")
            if e.get("whoosh_speed"):
                src += f", {e['whoosh_speed']} whoosh"
            lines.append(f"| {i} | {clean(e['path'])} | {fmt(e.get('effective_s'))} s | {fmt(e.get('attack_s'))} s | "
                         f"{fmt(e.get('fit'))} | {fmt(e.get('gain_db'), 1, ' dB')} | {src} |")
        lines.append("")
    lines += ["## Short pools", ""]
    if m["short_pools"]:
        lines.append(f"These cue types have fewer than {s['min_pool']} sounds: " + ", ".join(m["short_pools"]) +
                     ". Add files to styles/sfx/ (a sorted subfolder or a descriptive name), or pin a waiting file in overrides.txt.")
    else:
        lines.append(f"None: every cue type has at least {s['min_pool']} sounds.")
    lines += ["", "## Waiting for your approval (low confidence)", ""]
    if m["waiting"]:
        lines.append(f"The indexer model could not tell from the name and the measurements (confidence under {s['min_confidence']}). "
                     "They stay out of the pools until you pin them: `pin: <cue type>: <path>` in overrides.txt.")
        lines.append("")
        for w in m["waiting"]:
            lines.append(f"- {clean(w['path'])}: maybe {', '.join(w['cue_types']) or 'nothing'} (confidence {fmt(w.get('confidence'))}"
                         + (f"; {clean(w['note'])}" if w.get("note") else "") + ")")
    else:
        lines.append("None.")
    if m["unclassified"]:
        lines += ["", "## Not classified yet", "", "The indexer model has not seen these files (the build ran with --no-model or the call failed). "
                  "Run `bash pipeline/bin/build-sfx-map` again.", ""]
        for u in m["unclassified"]:
            lines.append(f"- {clean(u['path'])}")
    lines += ["", "## Excluded files", ""]
    if m["excluded"]:
        for e in m["excluded"]:
            lines.append(f"- {clean(e['path'])}: {clean(e['reason'])}")
    else:
        lines.append("None.")
    ov = m["overrides"]
    lines += ["", "## Overrides in force (styles/sfx/overrides.txt)", ""]
    if not (ov.get("bans") or ov.get("pins") or ov.get("unknown") or ov.get("unmatched")):
        lines.append("None.")
    for b in ov.get("bans", []):
        lines.append(f"- ban: {clean(b['path'])}" + ("" if b.get("matched") else " (no such file)"))
    for p in ov.get("pins", []):
        lines.append(f"- pin: {p['cue']}: {clean(p['path'])}" + ("" if p.get("matched") else " (no such file)"))
    for u in ov.get("unknown", []):
        lines.append(f"- line {u['line']} not understood: `{clean(u['text'])}` ({clean(u['reason'])})")
    lines += ["", "## Counts per category", ""]
    for cat, n in c["by_category"].items():
        lines.append(f"- {cat}: {n}")
    lines += ["", "## Thresholds (config.json sfx, DECISIONS.md M8)", ""]
    w = s["whoosh"]
    q = s["quality"]
    lines.append(f"- whoosh speed: fast when the effective sound is {w['fast_max_s']} s or shorter, or {w['fast_sharp_max_s']} s or shorter with an attack of "
                 f"{w['sharp_attack_s']} s or shorter; slow when it is {w['slow_min_s']} s or longer with an attack of {w['swell_attack_s']} s or longer, or "
                 f"{w['long_min_s']} s or longer; medium otherwise. Effective sound = onset (30 dB under the loudest 5 ms frame) to the end of the tail (40 dB under).")
    lines.append(f"- quality: clipped at {int(q['clip_runs'])} or more runs of 3 full-scale samples; high noise floor when the 5th percentile of the 20 ms frame RMS is "
                 f"within {q['min_snr_db']:.0f} dB of the peak (files of {q['min_snr_duration_s']} s or longer); far too long over {q['max_effective_s']:.0f} s of "
                 f"effective sound (typing excepted) or over {q['too_long_factor']:.0f} times a cue type's window.")
    lines.append(f"- pools: fit at least {s['min_fit']}, at most {s['pool_size'][1]} sounds, short under {s['min_pool']}; model answers under confidence {s['min_confidence']} wait for a pin.")
    lines.append("- duration windows (seconds of effective sound): " + "; ".join(f"{cue} {lo:g} to {hi:g}" for cue, (lo, hi) in s["cue_windows"].items()))
    lines.append("")
    return "\n".join(lines)
