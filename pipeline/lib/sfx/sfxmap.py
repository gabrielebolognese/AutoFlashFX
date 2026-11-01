#!/usr/bin/env python
"""sfxmap.py: the steps of pipeline/bin/build-sfx-map (BUILD_SPEC.md 2.6). The bash script runs them in order and
makes the one model call between classify-plan and build through ai().

  plan          --dir PACK --map MAP --config CFG [--force] [--reclassify]
                prints JSON: unchanged (the map is current: same folder hash, overrides, settings, nothing
                missing), reason, n_files, n_new, n_changed, n_removed, missing_cache, missing_previews,
                pending_model (files still waiting for the indexer model)
  measure       --dir PACK --map MAP --config CFG --work WORK [--force] [--reclassify]
                measures the new and changed files (the others keep their numbers and their model answer from the
                map), classifies every file by rules, writes WORK/measured.json; progress lines on stdout
  classify-plan --work WORK --config CFG --template FILE --out PROMPT [--only ID,ID] [--reclassify]
                writes the prompt for the unclear files; prints JSON: n_unclear, ids
  build         --dir PACK --map MAP --config CFG --work WORK [--answer FILE]... [--model NAME] [--calls N]
                merges the model answers, applies overrides.txt, the quality filter, the pools, writes the map,
                SFX-MAP.md, the previews and prunes stale cache files; prints the summary JSON
  check         --dir PACK --map MAP --config CFG      one human line; exit 0 when the map is current, else 1

Paths may be C:/... or /c/... (both work). Output is UTF-8 with LF.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import classify  # noqa: E402
import overrides as ov  # noqa: E402
import pools as pools_mod  # noqa: E402
import previews as previews_mod  # noqa: E402
import writemap  # noqa: E402
from common import (CUE_TYPES, MAP_VERSION, MEASURE_VERSION, clean, file_id, folder_hash, list_audio_files,  # noqa: E402
                    load_json, now_text, out_json, read_text, save_json, save_text, setup_streams, sha1_text, winpath)
from measure import measure_many  # noqa: E402

DERIVED = ("excluded", "waiting", "unclassified", "banned", "pinned", "notes", "fit", "pooled")


def load_config(path: str) -> dict:
    cfg = load_json(path, {}) or {}
    return cfg if isinstance(cfg, dict) else {}


def settings_of(cfg: dict) -> dict:
    return pools_mod.settings_from_config(cfg.get("sfx") or {})


def settings_hash(settings: dict) -> str:
    return sha1_text(json.dumps({"settings": settings, "map": MAP_VERSION, "measure": MEASURE_VERSION,
                                 "rules": classify.RULES_VERSION}, sort_keys=True))


def pack_paths(pack_dir: str, map_path: str) -> dict:
    pack = winpath(pack_dir)
    return {
        "pack": pack,
        "map": winpath(map_path) if map_path else os.path.join(pack, "sfx-map.json"),
        "md": os.path.join(pack, "SFX-MAP.md"),
        "overrides": os.path.join(pack, "overrides.txt"),
        "previews": os.path.join(pack, "previews"),
        "cache": os.path.join(pack, ".cache"),
    }


def pack_label(pack: str) -> str:
    """styles/sfx for the repo's pack, the folder's base name elsewhere."""
    norm = pack.replace("\\", "/").rstrip("/")
    m = re.search(r"(styles/[^/]+)$", norm)
    return m.group(1) if m else os.path.basename(norm)


def current_state(args) -> dict:
    cfg = load_config(args.config)
    settings = settings_of(cfg)
    paths = pack_paths(args.dir, getattr(args, "map", None))
    entries = list_audio_files(paths["pack"])
    old = load_json(paths["map"]) or {}
    old_files = {f["path"]: f for f in (old.get("files") or []) if isinstance(f, dict) and f.get("path")}
    new, changed, same = [], [], []
    for e in entries:
        o = old_files.get(e["path"])
        if o is None:
            new.append(e)
        elif (o.get("size") != e["size"] or o.get("mtime") != e["mtime"] or o.get("measure_version") != MEASURE_VERSION):
            changed.append(e)
        else:
            same.append(e)
    removed = [p for p in old_files if p not in {e["path"] for e in entries}]
    missing_cache = [e["path"] for e in same
                     if old_files[e["path"]].get("cache") and not os.path.isfile(os.path.join(paths["pack"], old_files[e["path"]]["cache"]))]
    missing_previews = previews_mod.missing_previews(paths["previews"], old.get("pools") or {}) if old else []
    pending_model = [f["path"] for f in old_files.values()
                     if f.get("unclear") and not f.get("model") and not f.get("decode_error")]
    ov_text = read_text(paths["overrides"])
    hashes = {"folder_sha1": folder_hash(entries), "overrides_sha1": ov.effective_hash(ov_text), "settings_sha1": settings_hash(settings)}
    reasons = []
    if not old:
        reasons.append("no map yet")
    else:
        if old.get("version") != MAP_VERSION:
            reasons.append(f"map version {old.get('version')} (code: {MAP_VERSION})")
        if old.get("folder_sha1") != hashes["folder_sha1"]:
            reasons.append(f"folder changed ({len(new)} new, {len(changed)} changed, {len(removed)} removed)")
        if old.get("overrides_sha1") != hashes["overrides_sha1"]:
            reasons.append("overrides.txt changed")
        if old.get("settings_sha1") != hashes["settings_sha1"]:
            reasons.append("settings changed")
        if missing_cache:
            reasons.append(f"{len(missing_cache)} cache copies missing")
        if missing_previews:
            reasons.append(f"{len(missing_previews)} previews missing")
    if getattr(args, "force", False):
        reasons.append("--force")
    if getattr(args, "reclassify", False):
        reasons.append("--reclassify")
    return {
        "cfg": cfg, "settings": settings, "paths": paths, "entries": entries, "old": old, "old_files": old_files,
        "new": new, "changed": changed, "same": same, "removed": removed, "missing_cache": missing_cache,
        "missing_previews": missing_previews, "pending_model": pending_model, "hashes": hashes,
        "unchanged": not reasons, "reason": "; ".join(reasons) if reasons else "up to date",
    }


def cmd_plan(args) -> int:
    st = current_state(args)
    out_json({
        "unchanged": st["unchanged"], "reason": st["reason"], "n_files": len(st["entries"]), "n_new": len(st["new"]),
        "n_changed": len(st["changed"]), "n_removed": len(st["removed"]), "missing_cache": len(st["missing_cache"]),
        "missing_previews": len(st["missing_previews"]), "pending_model": len(st["pending_model"]),
        "folder_sha1": st["hashes"]["folder_sha1"], "map": st["paths"]["map"], "pack": st["paths"]["pack"],
        "has_map": bool(st["old"]),
    })
    return 0


def cmd_check(args) -> int:
    st = current_state(args)
    n = len(st["entries"])
    if st["unchanged"] and not st["pending_model"]:
        print(f"sfx map up to date: {n} audio files, {st['old'].get('counts', {}).get('mapped', '?')} mapped, "
              f"{st['old'].get('counts', {}).get('excluded', '?')} excluded, built {st['old'].get('built', '?')}")
        return 0
    why = st["reason"] if not st["unchanged"] else f"{len(st['pending_model'])} file(s) still wait for the indexer model"
    print(f"sfx map needs a rebuild: {why} ({n} audio files); run bash pipeline/bin/build-sfx-map")
    return 1


def cmd_measure(args) -> int:
    st = current_state(args)
    settings = st["settings"]
    paths = st["paths"]
    force = bool(args.force)
    old_norm = ((st["old"].get("settings") or {}).get("normalize_peak_dbfs") if st["old"] else None)
    renorm = old_norm is not None and float(old_norm) != float(settings["normalize_peak_dbfs"])
    to_measure, reused = [], []
    for e in st["entries"]:
        o = st["old_files"].get(e["path"])
        cache_ok = bool(o) and (not o.get("cache") or os.path.isfile(os.path.join(paths["pack"], o["cache"])))
        if (not force and o and e not in st["new"] and e not in st["changed"] and cache_ok and not renorm
                and not (o.get("decode_error") or "").startswith("measurement failed")):
            keep = {k: v for k, v in o.items() if k not in DERIVED}
            reused.append(keep)
        else:
            to_measure.append(e)
    if to_measure:
        print(f"measuring {len(to_measure)} of {len(st['entries'])} audio files under {pack_label(paths['pack'])}/ "
              f"({len(reused)} unchanged, kept from the map)")
    else:
        print(f"nothing to measure: {len(reused)} files unchanged")
    sys.stdout.flush()
    started = time.time()
    last = [started]

    def progress(done, total, r):
        now = time.time()
        if done == total or now - last[0] >= 5:
            last[0] = now
            print(f"  measured {done}/{total} ({r['path']})")
            sys.stdout.flush()

    measured = measure_many(paths["pack"], to_measure, settings, progress=progress)
    for m in measured:
        o = st["old_files"].get(m["path"])
        if o and o.get("model") and not args.reclassify and o.get("size") == m["size"] and o.get("mtime") == m["mtime"]:
            m["model"] = o["model"]
    by_path = {f["path"]: f for f in reused + measured}
    files = [by_path[e["path"]] for e in st["entries"] if e["path"] in by_path]
    windows = pools_mod.windows_of(settings)
    factor = float(settings["quality"]["too_long_factor"])
    max_eff = float(settings["quality"]["max_effective_s"])
    for f in files:
        cached_model = None if args.reclassify else f.get("model")
        f.pop("contradiction", None)
        classify.classify_rules(f, settings)
        if (not f["unclear"] and not f.get("decode_error") and classify.contradicts_name(f, windows, factor)
                and float(f.get("effective_s") or 0.0) <= max_eff):
            f["unclear"] = True
            f["contradiction"] = (f"the name says {f['category']} but the effective sound lasts "
                                  f"{float(f.get('effective_s') or 0):.1f} s")
        if f["unclear"] and pools_mod.hard_exclusion(f, settings):
            f["unclear"] = False  # silent, clipped, noisy or far too long: excluded whatever its name, nothing to ask
        f["model"] = cached_model
    n_dec = sum(1 for f in files if f.get("decode_error"))
    print(f"measured {len(measured)} files in {time.time() - started:.1f} s"
          + (f", {n_dec} cannot be decoded" if n_dec else ""))
    save_json(os.path.join(args.work, "measured.json"), {
        "folder_sha1": st["hashes"]["folder_sha1"], "measured": len(measured), "reused": len(reused),
        "removed": st["removed"], "files": files,
    })
    return 0


def unclear_files(files: list[dict], reclassify: bool, only: set[str] | None) -> list[dict]:
    out = []
    for f in files:
        if f.get("decode_error"):
            continue
        if only is not None:
            if f["id"] in only:
                out.append(f)
            continue
        if reclassify and (f.get("unclear") or f.get("source") == "model" or f.get("model")):
            out.append(f)
        elif f.get("unclear") and not f.get("model"):
            out.append(f)
    return out


def render_template(path: str, values: dict) -> str:
    text = read_text(path)
    missing = []

    def sub(m):
        key = m.group(1)
        if key not in values:
            missing.append(key)
            return ""
        return clean(values[key], one_line=False)
    text = re.sub(r"\{\{([A-Z][A-Z0-9_]*)\}\}", sub, text)
    if missing:
        raise KeyError(", ".join(missing))
    return text


def cmd_classify_plan(args) -> int:
    work = load_json(os.path.join(args.work, "measured.json")) or {}
    files = work.get("files") or []
    only = set(x for x in (args.only or "").split(",") if x) or None
    unclear = unclear_files(files, bool(args.reclassify), only)
    cue_lines = "\n".join(f"- {cue}: {desc}" for cue, desc in CUE_TYPES.items())
    if unclear:
        prompt = render_template(args.template, {"FILES": classify.prompt_lines(unclear), "CUE_TYPES": cue_lines,
                                                  "N": str(len(unclear))})
        save_text(args.out, prompt)
    out_json({"n_unclear": len(unclear), "ids": [f["id"] for f in unclear]})
    return 0


def prune_cache(cache_dir: str, files: list[dict]) -> int:
    keep = {os.path.basename(f["cache"]) for f in files if f.get("cache")}
    n = 0
    try:
        names = os.listdir(winpath(cache_dir))
    except OSError:
        return 0
    for name in names:
        if name.lower().endswith(".wav") and name not in keep:
            try:
                os.remove(os.path.join(winpath(cache_dir), name))
                n += 1
            except OSError:
                pass
    return n


def cmd_build(args) -> int:
    st = current_state(args)
    settings = st["settings"]
    paths = st["paths"]
    work = load_json(os.path.join(args.work, "measured.json")) or {}
    files = work.get("files") or []
    if not files and st["entries"]:
        print("build-sfx-map: measured.json is missing or empty; run the measure step first", file=sys.stderr)
        return 2
    answers = [a for a in (load_json(p) for p in (args.answer or [])) if isinstance(a, dict)]
    applied = classify.merge_answers(files, answers, now_text())
    for f in files:
        if f.get("model") and f["id"] not in applied:
            classify.apply_model(f)
    created = ov.ensure_file(paths["overrides"])
    ov_text, parsed = ov.load(paths["overrides"])
    resolved = ov.resolve(parsed, files)
    pools, waiting, unclassified, short = pools_mod.build_pools(files, settings, resolved)
    files_by_id = {f["id"]: f for f in files}
    previews = previews_mod.render_all(paths["pack"], pools, files_by_id, paths["previews"], float(settings["preview_gap_s"]))
    matched_ban_lines = set(resolved["banned"].values())
    unmatched_lines = {u["line"] for u in resolved["unmatched"]}
    overrides_info = {
        "file": "overrides.txt", "created": created,
        "bans": [{"line": b["line"], "path": b["path"], "matched": b["line"] in matched_ban_lines} for b in parsed["bans"]],
        "pins": [{"line": p["line"], "cue": p["cue"], "path": p["path"], "matched": p["line"] not in unmatched_lines}
                 for p in parsed["pins"]],
        "unknown": parsed["unknown"] + resolved["unmatched"],
    }
    hashes = dict(st["hashes"])
    hashes["overrides_sha1"] = ov.effective_hash(ov_text)
    m = writemap.assemble(pack_label(paths["pack"]), files, pools, waiting, unclassified, short, overrides_info,
                          settings, hashes, args.model or (st["old"].get("model") if st["old"] else "") or "",
                          previews, int(args.calls or 0))
    save_json(paths["map"], m)
    save_text(paths["md"], writemap.render_md(m))
    pruned = prune_cache(paths["cache"], files)
    out_json({
        "files": m["counts"]["files"], "mapped": m["counts"]["mapped"], "excluded": m["counts"]["excluded"],
        "waiting": m["counts"]["waiting"], "unclassified": m["counts"]["unclassified"], "pooled": m["counts"]["pooled"],
        "short_pools": short, "pools": m["counts"]["by_cue_type"], "answered": len(applied), "pruned_cache": pruned,
        "overrides_created": created, "unknown_overrides": len(overrides_info["unknown"]),
        "map": paths["map"], "md": paths["md"], "previews": len(previews),
    })
    return 0


def main(argv=None) -> int:
    setup_streams()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, work=False, pack=True):
        if pack:
            sp.add_argument("--dir", required=True)
            sp.add_argument("--map", default="")
        sp.add_argument("--config", required=True)
        if work:
            sp.add_argument("--work", required=True)

    sp = sub.add_parser("plan"); common(sp); sp.add_argument("--force", action="store_true"); sp.add_argument("--reclassify", action="store_true")
    sp.set_defaults(func=cmd_plan)
    sp = sub.add_parser("check"); common(sp); sp.set_defaults(func=cmd_check, force=False, reclassify=False)
    sp = sub.add_parser("measure"); common(sp, work=True); sp.add_argument("--force", action="store_true"); sp.add_argument("--reclassify", action="store_true")
    sp.set_defaults(func=cmd_measure)
    sp = sub.add_parser("classify-plan"); common(sp, work=True, pack=False)
    sp.add_argument("--template", required=True); sp.add_argument("--out", required=True)
    sp.add_argument("--only", default=""); sp.add_argument("--reclassify", action="store_true")
    sp.set_defaults(func=cmd_classify_plan)
    sp = sub.add_parser("build"); common(sp, work=True); sp.add_argument("--answer", action="append", default=[])
    sp.add_argument("--model", default=""); sp.add_argument("--calls", default="0")
    sp.set_defaults(func=cmd_build, force=False, reclassify=False)
    args = p.parse_args(argv)
    for key in ("dir", "map", "config", "work", "template", "out"):
        if getattr(args, key, None):
            setattr(args, key, winpath(getattr(args, key)))
    if getattr(args, "answer", None):
        args.answer = [winpath(a) for a in args.answer]
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
