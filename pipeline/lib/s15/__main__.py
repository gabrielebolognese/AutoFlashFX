"""S15 tools (BUILD_SPEC.md S15, M21). Run as `python pipeline/lib/s15 <command>`:

  run       --run-dir DIR [--manifest FILE] [--stable-dir DIR] [--no-parity] [--reuse-capture]
                                      build runs/<id>/s15-project/ (project/, layers.json, editor.json) from the run's timeline; exit 0 even when the
                                      project is the minimal one (the export goes on); exit 1 only when nothing could be written
  validate  FOLDER [--manifest FILE]  the S15 validator on a project folder (exit 1 when invalid)
  caps      [--stable-dir DIR] [--manifest FILE]
                                      print the capability hash, the schema version and where the manifest came from
  upgrade-keys --old FILE --new FILE  the keys the new manifest adds (the capability upgrade of step 8)
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from s15 import checks, gaps, manifest as smanifest, run as srun, validate as svalidate  # noqa: E402


def load_env():
    import config as reels_config
    import paths
    from motion import common as mcommon
    cfg = reels_config.load()
    editor = dict(cfg.get("editor") or {})
    for env, key in (("EDITOR_STABLE_DIR", "stable_dir"), ("EDITOR_REPO", "repo"), ("EDITOR_PORT", "port")):
        if os.environ.get(env):
            editor[key] = os.environ[env]
    return cfg, editor, paths, mcommon


def cmd_run(a) -> int:
    cfg, editor, paths, mcommon = load_env()
    from timeline import compose
    import subprocess
    root = paths.channel_root() or ""
    try:
        git_hash = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=paths.REPO, capture_output=True, text=True).stdout.strip()
    except OSError:
        git_hash = ""
    try:
        tokens = mcommon.tokens()
    except Exception:  # noqa: BLE001
        tokens = {}
    own_fonts = os.path.join(paths.motionlib(), "assets", "fonts") if root else ""
    opts = srun.Opts(run_dir=a.run_dir.replace("\\", "/"), manifest=a.manifest, stable_dir=a.stable_dir or editor.get("stable_dir"), editor=editor, channel_root=root,
                     tokens_dict=tokens, own_fonts=own_fonts, sfx_dir=compose.sfx_dir(cfg), reuse_capture=a.reuse_capture, no_parity=a.no_parity, git_hash=git_hash,
                     channel=paths.channel_id() or "")
    summary = srun.run_stage(opts)
    # the gaps log of the channel and the root roll-up
    try:
        gl = os.path.join(root, "logs") if root else os.path.join(paths.REPO, "logs")
        gaps.update_logs(gl, os.path.join(paths.REPO, "logs"), os.path.join(paths.REPO, "channels"), summary.get("gaps") or {}, os.path.basename(a.run_dir.rstrip("/\\")))
    except Exception as exc:  # noqa: BLE001
        print(f"@@SAY WARN gaps log: {exc}")
    print(json.dumps({k: summary.get(k) for k in ("level", "native", "sprites", "overlays", "plates", "baked_captions", "seconds")}))
    return 0 if summary.get("level") != "failed" or True else 1


def cmd_validate(a) -> int:
    m = smanifest.load(None, a.manifest)
    doc = json.load(open(os.path.join(a.folder, "project.json"), encoding="utf-8"))
    res = svalidate.validate(doc, a.folder, m)
    for e in res["errors"]:
        print(f"ERROR {e['path']}: {e['message']}")
    for w in res["warnings"]:
        print(f"WARN  {w['path']}: {w['message']}")
    print("valid" if res["ok"] else f"{len(res['errors'])} errors")
    return 0 if res["ok"] else 1


def cmd_caps(a) -> int:
    m = smanifest.load(a.stable_dir, a.manifest)
    print(json.dumps({"hash": m.hash, "schemaVersion": m.schema_version, "source": m.source, "appVersion": m.get("appVersion"), "lastBatch": m.get("lastBatch")}))
    return 0


def cmd_keys(a) -> int:
    old, new = smanifest.load_file(a.old), smanifest.load_file(a.new)
    for k in smanifest.added_keys(old, new):
        print(k)
    return 0


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--run-dir", required=True)
    r.add_argument("--manifest")
    r.add_argument("--stable-dir")
    r.add_argument("--no-parity", action="store_true")
    r.add_argument("--reuse-capture", action="store_true")
    r.set_defaults(func=cmd_run)
    v = sub.add_parser("validate")
    v.add_argument("folder")
    v.add_argument("--manifest")
    v.set_defaults(func=cmd_validate)
    c = sub.add_parser("caps")
    c.add_argument("--stable-dir")
    c.add_argument("--manifest")
    c.set_defaults(func=cmd_caps)
    k = sub.add_parser("upgrade-keys")
    k.add_argument("--old", required=True)
    k.add_argument("--new", required=True)
    k.set_defaults(func=cmd_keys)
    a = ap.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
