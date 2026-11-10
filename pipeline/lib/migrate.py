#!/usr/bin/env python
"""migrate.py: executes a move manifest (BUILD_SPEC.md 14.13). Run it through pipeline/bin/migrate-channels.

  python pipeline/lib/migrate.py run  --ms M18 [--root DIR] [--build-dir DIR] [--manifest FILE] [--plan FILE] [--dry-run]
                                      [--allow-dirty PREFIX ...] [--min-free-gb N] [--no-prepare]
  python pipeline/lib/migrate.py undo --ms M18 [--root DIR] [--build-dir DIR]
  python pipeline/lib/migrate.py verify --ms M18 [--root DIR] [--build-dir DIR] [--manifest FILE]

run:     1. an earlier attempt without its final "verified" line (a kill or a crash during the moves) is undone first and the
            folder is checked against that attempt's before-listing; an attempt that did end "verified" is only verified again
         2. refuses with less than --min-free-gb (2) GB free and with uncommitted git changes outside build/ and the
            --allow-dirty prefixes (the runner check is pipeline/bin/migrate-channels' own: it has ps)
         3. writes the manifest again from the folder as it is now (make-manifest.py, checked by check-manifest.py) to
            <build-dir>/move-manifest.tsv and <build-dir>/manifest-diff.md (what changed since the plan, --plan), unless
            --manifest gives one (--no-prepare uses <build-dir>/move-manifest.tsv as it is)
         4. a full listing of the folder before, the undo script, then every line of the milestone in order: git mv for tracked
            files (a folder is renamed whole, its ignored files included), a rename for the rest (copy, verify, delete only when
            a rename is impossible), the rewrites of old paths in every form (each file copied first to <build-dir>/premigrate/)
         5. verifies: every new path with its checksum or count and bytes, no moved folder at its old path, the listing before
            and after differ only by the manifest's lines, git status shows only renames, git check-ignore passes at the new
            path of every file that was ignored, no old path left in a rewritten file
         6. on a failed check it undoes everything, checks that the folder is back as it was and exits 3 ("BLOCKED: reason")
         every step goes to <build-dir>/migration-log.tsv; the last line of a good run is "verified"
--dry-run prints every step and every check and changes nothing (no git mv, no rename, no rewrite); it writes only the fresh manifest
and manifest-diff.md under <build-dir>.
Exit codes: 0 ok, 2 refused or unusable input, 3 a check failed (undone), 4 an undo did not restore the folder.
Test hooks: MIGRATE_KILL_AFTER=N ends the process (exit 137, no cleanup) after N completed moves.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "pipeline", "tests"))
import manifestlib as ml  # noqa: E402  (the manifest's own definition: the inventory, the old-path forms, the TSV)

CH = ml.CHANNEL


def out(text: str = "") -> None:
    print(text, flush=True)


def die(message: str, code: int = 2):
    print(message, flush=True)
    raise SystemExit(code)


def undash(text: str) -> str:
    return str(text).replace(chr(0x2014), ", ").replace(chr(0x2013), "-")


class Migration:
    def __init__(self, a):
        self.a = a
        self.root = os.path.abspath(a.root)
        self.ms = a.ms
        self.build = os.path.abspath(a.build_dir or os.path.join(self.root, "build", a.ms))
        self.log_path = os.path.join(self.build, "migration-log.tsv")
        self.undo_path = os.path.join(self.build, "undo-migration.sh")
        self.before_path = os.path.join(self.build, "before-listing.tsv")
        self.after_path = os.path.join(self.build, "after-listing.tsv")
        self.pre_dir = os.path.join(self.build, "premigrate")
        self.manifest_path = a.manifest or os.path.join(self.build, "move-manifest.tsv")
        self.rewritten_path = os.path.join(self.build, "rewritten-files.txt")
        self.dry = getattr(a, "dry_run", False)
        self.rows: list[dict] = []
        self.moves: list[tuple[str, str]] = []       # (old, new) of the top lines, in order
        self.inner_moves: list[tuple[str, str]] = [] # (old, new) of the inner renames (M19: the file names inside an export folder), in order
        self.rewritten: list[str] = []               # the files (new paths) a rewrite changed
        self.done_moves = 0

    # ---- log ----------------------------------------------------------------------------------------------------------
    def log(self, step: str, what: str, result: str = "ok") -> None:
        if self.dry:
            return
        os.makedirs(self.build, exist_ok=True)
        new = not os.path.exists(self.log_path)
        with open(self.log_path, "a", encoding="utf-8", newline="\n") as f:
            if new:
                f.write("time\tstep\twhat\tresult\n")
            f.write("%s\t%s\t%s\t%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), step, str(what).replace("\t", " "), str(result).replace("\t", " ")))

    def last_log_step(self) -> str:
        try:
            with open(self.log_path, encoding="utf-8") as f:
                lines = [x for x in f.read().split("\n") if x.strip()]
        except OSError:
            return ""
        return lines[-1].split("\t")[1] if len(lines) > 1 else ""

    # ---- helpers ------------------------------------------------------------------------------------------------------
    def p(self, rel: str) -> str:
        return os.path.join(self.root, rel)

    def git(self, *args, check=True):
        r = subprocess.run(["git", "-C", self.root, *args], capture_output=True)
        if check and r.returncode != 0:
            raise RuntimeError("git %s failed: %s" % (" ".join(args), r.stderr.decode("utf-8", "replace").strip()))
        return r

    def translate(self, path: str) -> str:
        best = None
        for old, new in self.moves:
            if path == old or path.startswith(old + "/"):
                if best is None or len(old) > len(best[0]):
                    best = (old, new)
        return path if best is None else best[1] + path[len(best[0]):]

    def translate_all(self, path: str) -> str:
        """Where a file of the before-listing is after every move: an inner rename of the file itself first, else its folder's move."""
        for old, new in self.inner_moves:
            if path == old:
                return new
        return self.translate(path)

    def inner_back(self, old: str) -> str:
        """Where an inner-renamed file has to go back to while its folder still has the new name: the old file name in the moved folder."""
        return self.translate(old)

    def listing(self) -> dict[str, int]:
        inv = ml.Inventory(self.root)
        return {r["path"]: r["size"] for r in inv.rows if r["kind"] == "file"}

    def listing_states(self) -> dict[str, str]:
        inv = ml.Inventory(self.root)
        return {r["path"]: r["git"] for r in inv.rows if r["kind"] == "file"}

    def write_listing(self, path: str, lst: dict[str, int]) -> None:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            for k in sorted(lst):
                f.write("%s\t%d\n" % (k, lst[k]))

    def read_listing(self, path: str) -> dict[str, int]:
        d = {}
        with open(path, encoding="utf-8") as f:
            for line in f.read().split("\n"):
                if line:
                    k, _, v = line.rpartition("\t")
                    d[k] = int(v)
        return d

    def rename(self, src: str, dst: str) -> str:
        """A same-drive rename with retries (OneDrive and antivirus hold files for a moment); copy, verify, delete only when impossible."""
        last = None
        for attempt in range(6):
            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                os.rename(src, dst)
                return "renamed"
            except OSError as exc:
                last = exc
                time.sleep(0.5 * (attempt + 1))
        f0, b0 = ml.tree_stats(self.root, os.path.relpath(src, self.root))
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        f1, b1 = ml.tree_stats(self.root, os.path.relpath(dst, self.root))
        if (f0, b0) != (f1, b1):
            raise RuntimeError("a rename of %s failed (%s) and the copy does not match (%d files %d bytes, then %d and %d)" % (src, last, f0, b0, f1, b1))
        shutil.rmtree(src) if os.path.isdir(src) else os.remove(src)
        return "copied, verified and deleted the original (the rename failed: %s)" % last

    # ---- the manifest -------------------------------------------------------------------------------------------------
    def prepare(self) -> None:
        a = self.a
        if a.manifest or a.no_prepare:
            if not os.path.exists(self.manifest_path):
                die("migrate: no manifest at %s" % self.manifest_path)
            return
        tests = os.path.join(REPO, "pipeline", "tests")
        os.makedirs(self.build, exist_ok=True)
        target = self.manifest_path if not self.dry else os.path.join(self.build, "move-manifest.tsv")
        r = subprocess.run([sys.executable, os.path.join(tests, "make-manifest.py"), "--root", self.root, "--out", target,
                            "--keys-out", os.path.join(self.build, "config-keys.tsv")], capture_output=True, text=True)
        if r.returncode != 0:
            die("migrate: make-manifest.py failed: " + (r.stdout + r.stderr).strip())
        out(r.stdout.strip())
        r = subprocess.run([sys.executable, os.path.join(tests, "check-manifest.py"), "--root", self.root, "--manifest", target, "--live"],
                           capture_output=True, text=True)
        out(r.stdout.strip())
        if r.returncode != 0:
            die("migrate: the manifest cannot place every file (check-manifest.py): the build ends BLOCKED")
        plan = a.plan or os.path.join(self.root, "build", "M17", "move-manifest.tsv")
        self.write_diff(plan, target)

    def write_diff(self, plan: str, now: str) -> None:
        def keyed(path):
            if not os.path.exists(path):
                return {}
            rows = ml.read_tsv(path)[1]
            return {(r["ms"], r["scope"], r["method"], r["old"], r["new"]): r for r in rows}
        before, after = keyed(plan), keyed(now)
        lines = ["# Manifest difference: %s plan to the manifest written right before the moves" % os.path.basename(os.path.dirname(plan)), "",
                 "Plan: `%s`. Executed: `%s`." % (os.path.relpath(plan, self.root).replace("\\", "/") if os.path.exists(plan) else plan,
                                                  os.path.relpath(now, self.root).replace("\\", "/")), ""]
        gone = [k for k in before if k not in after and k[0] == self.ms]
        new = [k for k in after if k not in before and k[0] == self.ms]
        changed = [k for k in after if k in before and k[0] == self.ms and (before[k]["files"], before[k]["bytes"]) != (after[k]["files"], after[k]["bytes"])]
        lines.append("%d line(s) of %s only in the plan, %d only now, %d with other counts." % (len(gone), self.ms, len(new), len(changed)))
        lines.append("")
        why = ("The video runner, the tests and the build itself keep writing files (runs, logs, caches) between the plan and the move, and "
               "the fresh manifest covers whatever is there. The rules are the same (BUILD_SPEC.md 14.13).")
        for title, keys, src in (("Only in the plan", gone, before), ("Only now", new, after)):
            if keys:
                lines += ["## " + title, ""]
                for k in keys:
                    r = src[k]
                    lines.append("- `%s` %s `%s` to `%s`: %s files, %s bytes" % (k[3], k[2], k[3], k[4], r["files"], r["bytes"]))
                lines.append("")
        if changed:
            lines += ["## Same line, other counts", ""]
            for k in changed:
                lines.append("- `%s`: plan %s files %s bytes, now %s files %s bytes" % (k[3], before[k]["files"], before[k]["bytes"], after[k]["files"], after[k]["bytes"]))
            lines.append("")
        lines += ["## Why", "", why, ""]
        with open(os.path.join(self.build, "manifest-diff.md"), "w", encoding="utf-8", newline="\n") as f:   # a dry run writes this too
            f.write(undash("\n".join(lines)))
        out("manifest-diff: %d only in the plan, %d only now, %d with other counts" % (len(gone), len(new), len(changed)))

    def load_rows(self) -> None:
        header, rows = ml.read_tsv(self.manifest_path)
        if header != ml.MANIFEST_COLUMNS:
            die("migrate: the manifest's columns are %s" % header)
        self.rows = [r for r in rows if r["ms"] == self.ms]
        self.moves = [(r["old"], r["new"]) for r in self.rows if r["scope"] == "top" and r["method"] in ("git-mv", "fs-mv", "rename-in-place")]
        self.inner_moves = [(r["old"], r["new"]) for r in self.rows if r["scope"] == "inner" and r["method"] == "rename-in-place"]

    # ---- refusals -----------------------------------------------------------------------------------------------------
    def refuse(self) -> None:
        free = shutil.disk_usage(self.root).free / (1 << 30)
        if free < self.a.min_free_gb:
            die("migrate: only %.1f GB free, need %s GB" % (free, self.a.min_free_gb))
        if os.path.isdir(self.p(".git")):
            r = self.git("status", "--porcelain", "-z", "--untracked-files=all", check=False)
            dirty = []
            for ent in r.stdout.decode("utf-8", "replace").split("\0"):
                if len(ent) < 4:
                    continue
                path = ent[3:]
                if path.startswith("build/") or any(path.startswith(x) for x in (self.a.allow_dirty or [])):
                    continue
                dirty.append(ent)
            if dirty:
                die("migrate: uncommitted git changes outside build/ (commit or restore them first): " + "; ".join(x.strip() for x in dirty[:8]))

    # ---- undo ---------------------------------------------------------------------------------------------------------
    def write_undo_script(self) -> None:
        lines = ["#!/usr/bin/env bash", "# undo-migration.sh: the exact reverse of %s's moves (written by pipeline/lib/migrate.py before the first move)." % self.ms,
                 "# Safe to run twice: every step checks what is where. Restores the rewritten files from premigrate/ last.",
                 'cd "%s" || exit 1' % self.root.replace("\\", "/")]
        for old, new in reversed(self.inner_moves):   # the file names inside a moved folder go back first, while the folder has its new name
            back = self.inner_back(old)
            lines.append('[ -e "%s" ] && [ ! -e "%s" ] && mv "%s" "%s"' % (new, back, new, back))
        for old, new in reversed(self.moves):
            row = next((r for r in self.rows if r["scope"] == "top" and r["old"] == old and r["new"] == new), None)
            how = "git mv" if row and row["method"] == "git-mv" else "mv"
            lines.append('[ -e "%s" ] && [ ! -e "%s" ] && %s "%s" "%s"' % (new, old, how, new, old))
        lines.append('[ -d "%s" ] && cp -R "%s/." . && echo "restored the rewritten files from premigrate/"' % (self.pre_dir.replace("\\", "/"), self.pre_dir.replace("\\", "/")))
        with open(self.undo_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")

    def undo(self, reason: str = "") -> bool:
        """State-driven: restore the rewritten files, move every top line back in reverse order, then check the folder against the
        before-listing. Returns True when the folder is back as it was."""
        out("UNDO %s" % (reason or "requested"))
        self.log("undo", reason or "requested", "start")
        if os.path.isdir(self.pre_dir):
            # premigrate/ holds each rewritten file at its OLD relative path: put it back where it lives now (the translated path)
            for dp, _dn, fn in os.walk(self.pre_dir):
                for n in fn:
                    src = os.path.join(dp, n)
                    old_rel = ml.posix(os.path.relpath(src, self.pre_dir))
                    cur = self.p(self.translate_all(old_rel))
                    if os.path.isdir(os.path.dirname(cur)):
                        shutil.copy2(src, cur)
        for old, new in reversed(self.inner_moves):   # inner renames back first (their folder still has the new name)
            cur, back = self.p(new), self.p(self.inner_back(old))
            if os.path.lexists(cur) and not os.path.lexists(back):
                self.rename(cur, back)
                out("  moved back %s -> %s" % (new, self.inner_back(old)))
                self.log("undo-move", "%s -> %s" % (new, self.inner_back(old)))
        for old, new in reversed(self.moves):
            if os.path.lexists(self.p(new)) and not os.path.lexists(self.p(old)):
                row = next((r for r in self.rows if r["scope"] == "top" and r["old"] == old and r["new"] == new), None)
                os.makedirs(os.path.dirname(self.p(old)) or self.root, exist_ok=True)
                if row and row["method"] == "git-mv" and os.path.isdir(self.p(".git")):
                    r = self.git("mv", new, old, check=False)
                    if r.returncode != 0:
                        self.rename(self.p(new), self.p(old))
                        self.git("add", "-A", "--", old, new, check=False)
                else:
                    self.rename(self.p(new), self.p(old))
                out("  moved back %s -> %s" % (new, old))
                self.log("undo-move", "%s -> %s" % (new, old))
        self.prune_empty(self.moves)
        ok = True
        if os.path.exists(self.before_path):
            want = self.read_listing(self.before_path)
            have = self.listing()
            if have != want:
                ok = False
                miss = sorted(set(want) - set(have))[:5]
                extra = sorted(set(have) - set(want))[:5]
                diff = [k for k in want if k in have and want[k] != have[k]][:5]
                out("UNDO CHECK FAILED: missing %s, extra %s, other size %s" % (miss, extra, diff))
        self.log("undone" if ok else "undo-failed", reason, "ok" if ok else "listing differs")
        if ok:
            out("UNDO verified: the folder is back as it was (%d files)" % len(self.read_listing(self.before_path)) if os.path.exists(self.before_path) else "UNDO done")
        return ok

    def prune_empty(self, moves) -> None:
        for _old, new in moves:
            d = os.path.dirname(self.p(new))
            while d and d != self.root and os.path.isdir(d):
                try:
                    if os.listdir(d):
                        break
                    # keep channels/<id>/ if channel.json or other files are there (they are): only empty folders go
                    os.rmdir(d)
                except OSError:
                    break
                d = os.path.dirname(d)

    # ---- the moves ----------------------------------------------------------------------------------------------------
    def rewrite_text(self, text: str, check: str) -> str:
        if check == "no-old-path-left":
            old_paths = ml.OldPaths(self.root)
            hits = old_paths.scan(text)
            res, pos = [], 0
            for name, form, start, end, matched in hits:
                if start < pos:
                    continue
                res.append(text[pos:start])
                sep = {"backslash": "\\", "json-backslash": "\\\\"}.get(form, "/")
                head = matched[: len(matched) - len(name)] if len(matched) > len(name) else ""
                res.append(head + "channels" + sep + CH + sep + name)
                pos = end
            res.append(text[pos:])
            return "".join(res)
        if check == "export-names":
            new = re.sub(r"^([0-9]+)((?:hook2)?\.mp4 uses:)", lambda m: "%s-%s%s" % (CH, m.group(1), m.group(2)), text, flags=re.M)
            return re.sub(r"\| exported ([0-9]+) *$", lambda m: "| exported %s-%s" % (CH, m.group(1)), new, flags=re.M)
        return text

    def do_rewrite(self, r: dict) -> int:
        target = self.translate(r["new"]) if self.ms != "M18" else self.translate(r["old"])
        if r["scope"] == "inner" and r["method"] == "rewrite" and self.ms == "M19":
            target = self.translate(r["new"])
        full = self.p(target)
        if not os.path.lexists(full):
            raise RuntimeError("rewrite target %s is missing" % target)
        files = []
        if os.path.isdir(full):
            for dp, dn, fn in os.walk(full):
                dn[:] = [d for d in dn if d not in ml.SKIP_DIRS]
                for n in fn:
                    files.append(ml.posix(os.path.relpath(os.path.join(dp, n), self.root)))
        else:
            files.append(target)
        changed = 0
        inverse = {new: old for old, new in self.moves}
        for rel in files:
            if not ml.is_text_name(rel) or ml.is_raw_model_output(rel):
                continue
            text = ml.read_text(self.p(rel))
            if text is None:
                continue
            new_text = self.rewrite_text(text, r["check"])
            if new_text == text:
                continue
            # the copy sits under premigrate/ at the file's OLD relative path
            old_rel = rel
            inner_inverse = {n_: o_ for o_, n_ in self.inner_moves}
            if rel in inner_inverse:   # an inner-renamed file (the captions file): its old path, name and folder
                old_rel = inner_inverse[rel]
            else:
                for new_prefix, old_prefix in sorted(inverse.items(), key=lambda kv: -len(kv[0])):
                    if rel == new_prefix or rel.startswith(new_prefix + "/"):
                        old_rel = old_prefix + rel[len(new_prefix):]
                        break
            dest = os.path.join(self.pre_dir, old_rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if not os.path.exists(dest):
                shutil.copy2(self.p(rel), dest)
            with open(self.p(rel), "w", encoding="utf-8", newline="\n") as f:
                f.write(new_text)
            self.rewritten.append(rel)
            with open(self.rewritten_path, "a", encoding="utf-8", newline="\n") as lf:
                lf.write(rel + "\n")
            changed += 1
        return changed

    def execute(self) -> None:
        for r in self.rows:
            tag = "%s %s" % (r["method"], r["old"] if r["old"] == r["new"] else "%s -> %s" % (r["old"], r["new"]))
            if r["method"] == "stays":
                out("STEP stays   %s" % r["old"])
                self.log("stays", r["old"])
                continue
            if self.dry:
                out("STEP %-8s %s  (%s files, %s bytes, %s)" % (r["method"], r["old"] if r["old"] == r["new"] else "%s -> %s" % (r["old"], r["new"]), r["files"], r["bytes"], r["check"]))
                continue
            if r["method"] == "rewrite":
                n = self.do_rewrite(r)
                out("STEP rewrite  %s: %d file(s) changed (%s)" % (r["old"], n, r["check"]))
                self.log("rewrite", r["old"], "%d files" % n)
                continue
            src = self.translate(r["old"]) if r["scope"] == "inner" else r["old"]
            dst = self.translate(r["new"]) if r["scope"] == "inner" else r["new"]
            if not os.path.lexists(self.p(src)):
                raise RuntimeError("%s is missing before its move" % src)
            if os.path.lexists(self.p(dst)):
                raise RuntimeError("%s already exists: the move would overwrite it" % dst)
            os.makedirs(os.path.dirname(self.p(dst)) or self.root, exist_ok=True)
            if r["method"] == "git-mv" and os.path.isdir(self.p(".git")):
                res = self.git("mv", src, dst, check=False)
                if res.returncode != 0:
                    how = self.rename(self.p(src), self.p(dst))
                    self.git("add", "-A", "--", src, dst, check=False)
                    how += " (git mv failed: %s)" % res.stderr.decode("utf-8", "replace").strip()[:120]
                else:
                    how = "git mv"
            else:
                how = self.rename(self.p(src), self.p(dst))
            out("STEP %-8s %s -> %s: %s" % (r["method"], src, dst, how))
            self.log(r["method"], "%s -> %s" % (src, dst), how)
            self.done_moves += 1
            kill = os.environ.get("MIGRATE_KILL_AFTER")
            if kill and self.done_moves >= int(kill):
                out("MIGRATE_KILL_AFTER: ending the process after %d move(s), no cleanup" % self.done_moves)
                sys.stdout.flush()
                os._exit(137)

    # ---- verification -------------------------------------------------------------------------------------------------
    def verify(self, before: dict[str, int] | None, states: dict[str, str] | None, strict_git: bool = True) -> list[str]:
        problems: list[str] = []
        rewrites = [r for r in self.rows if r["method"] == "rewrite"]
        has_rewrite_in = lambda r: any(ml.posix(x["old"]).startswith(r["old"] + "/") or x["old"] == r["old"] or x["old"].startswith(r["old"] + "/") for x in rewrites)  # noqa: E731
        for r in self.rows:
            if r["method"] in ("rewrite", "stays"):
                if r["method"] == "stays" and not os.path.lexists(self.p(r["new"])):
                    problems.append("%s should stay and is gone" % r["old"])
                continue
            new = self.translate(r["new"]) if r["scope"] == "inner" else r["new"]
            if not os.path.lexists(self.p(new)):
                problems.append("new path %s is missing" % new)
                continue
            if r["scope"] == "top" and os.path.lexists(self.p(r["old"])):
                problems.append("the moved item is still at its old path %s" % r["old"])
            if r["check"] == "sha256" and r["sha256"] and os.path.isfile(self.p(new)):
                if ml.sha256_file(self.p(new)) != r["sha256"] and not any(w.startswith(new) for w in self.rewritten):
                    problems.append("the checksum of %s changed" % new)
            elif r["check"] == "count-and-bytes" and r["scope"] == "top":
                f, b = ml.tree_stats(self.root, new)
                if f != int(r["files"]):
                    problems.append("%s has %d files, the manifest says %s" % (new, f, r["files"]))
                elif b != int(r["bytes"]) and not any(w == new or w.startswith(new + "/") for w in self.rewritten):
                    problems.append("%s has %d bytes, the manifest says %s" % (new, b, r["bytes"]))
        if before is not None:
            after = self.listing()
            expect = {}
            for path, size in before.items():
                expect[self.translate_all(path)] = size
            miss = sorted(set(expect) - set(after))
            extra = sorted(set(after) - set(expect))
            wrote = set(self.rewritten)
            diff = [k for k in expect if k in after and expect[k] != after[k] and k not in wrote]
            # files the migration itself wrote under build/ are not in the listing (build is a summary tree)
            if miss:
                problems.append("%d file(s) of the listing are missing after the moves, first: %s" % (len(miss), miss[:3]))
            if extra:
                problems.append("%d file(s) appeared that the manifest does not explain, first: %s" % (len(extra), extra[:3]))
            if diff:
                problems.append("%d file(s) changed size without a rewrite, first: %s" % (len(diff), diff[:3]))
            if not self.dry:
                self.write_listing(self.after_path, after)
        if strict_git and os.path.isdir(self.p(".git")):
            r = self.git("status", "--porcelain", "-z", "--untracked-files=all", check=False)
            ents = r.stdout.decode("utf-8", "replace").split("\0")
            bad = []
            i = 0
            while i < len(ents):
                ent = ents[i]
                i += 1
                if len(ent) < 4:
                    continue
                code, path = ent[:2], ent[3:]
                if code[0] == "R":
                    i += 1  # the old path follows
                    continue
                if path.startswith("build/") or any(path.startswith(x) for x in (self.a.allow_dirty or [])):
                    continue
                bad.append(ent.strip())
            if bad:
                problems.append("git status shows more than renames: %s" % "; ".join(bad[:6]))
        if states is not None and os.path.isdir(self.p(".git")):
            ignored_old = [k for k, v in states.items() if v == "ignored"]
            newpaths = [self.translate(k) for k in ignored_old]
            if newpaths:
                proc = subprocess.run(["git", "-C", self.root, "check-ignore", "--stdin", "-z"], input=("\0".join(newpaths) + "\0").encode("utf-8"),
                                      capture_output=True)
                got = set(x.decode("utf-8", "replace") for x in proc.stdout.split(b"\0") if x)
                lost = [x for x in newpaths if x not in got and os.path.lexists(self.p(x))]
                if lost:
                    problems.append("%d formerly ignored file(s) are not ignored at the new path, first: %s" % (len(lost), lost[:3]))
        old_paths = ml.OldPaths(self.root)
        for rel in self.rewritten:
            text = ml.read_text(self.p(rel))
            if text is not None and old_paths.scan(text):
                problems.append("%s still names an old path" % rel)
        return problems

    # ---- the whole run ------------------------------------------------------------------------------------------------
    def run(self) -> int:
        a = self.a
        if not self.dry:
            os.makedirs(self.build, exist_ok=True)
        # 1. an earlier attempt
        last = self.last_log_step()
        if last and last not in ("verified", "undone") and not self.dry:
            out("an earlier attempt ended at '%s' without its final 'verified' line: undoing it first" % last)
            self.prepare_for_undo()
            if not self.undo("the earlier attempt did not finish"):
                out("BLOCKED: the undo of the earlier attempt did not restore the folder (see above)")
                return 4
            os.replace(self.log_path, self.log_path + ".attempt-%s" % time.strftime("%H%M%S"))
        already = last == "verified"
        if not already:
            self.refuse()
        if already and not self.dry:
            out("this migration was verified before: verifying again, nothing is moved")
            self.prepare_for_undo()
            before = self.read_listing(self.before_path) if os.path.exists(self.before_path) else None
            problems = self.verify(before, None)
            for p in problems:
                out("FAIL " + p)
            out("migrate: second verification %s" % ("passed" if not problems else "FAILED"))
            return 0 if not problems else 3
        self.prepare()
        self.load_rows()
        if not self.rows:
            out("migrate: no line of %s in the manifest: nothing to do" % self.ms)
            return 0
        out("migrate %s%s: %d line(s) (%d moves)" % (self.ms, " (dry run)" if self.dry else "", len(self.rows), len(self.moves)))
        if self.dry:
            self.execute()
            out("DRY RUN: the checks that follow the moves: every new path with its checksum or count and bytes, no moved folder at its old path, "
                "the listing before and after differs only by the manifest, git status shows only renames, git check-ignore at the new path of every "
                "formerly ignored file, no old path left in a rewritten file")
            out("DRY RUN: nothing changed")
            return 0
        before = self.listing()
        states = self.listing_states()
        self.write_listing(self.before_path, before)
        if os.path.exists(self.rewritten_path):
            os.remove(self.rewritten_path)
        self.write_undo_script()
        self.log("start", "%s: %d lines, %d files in the listing" % (self.ms, len(self.rows), len(before)))
        try:
            self.execute()
            problems = self.verify(before, states)
        except Exception as exc:  # noqa: BLE001
            problems = ["a step failed: %s" % exc]
        if problems:
            for p in problems:
                out("FAIL " + p)
            ok = self.undo("a check failed: " + problems[0][:120])
            out("BLOCKED: %s" % undash(problems[0]))
            return 3 if ok else 4
        self.log("verified", "%s: %d files, %d rewritten" % (self.ms, len(before), len(self.rewritten)))
        out("migrate %s: verified (%d files in the listing, %d text file(s) rewritten)" % (self.ms, len(before), len(self.rewritten)))
        return 0

    def prepare_for_undo(self) -> None:
        if os.path.exists(self.manifest_path):
            self.load_rows()
        if os.path.exists(self.rewritten_path):
            with open(self.rewritten_path, encoding="utf-8") as f:
                self.rewritten = [x for x in f.read().split("\n") if x]


def main(argv=None) -> int:
    ml.out_stream()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("run", "undo", "verify"))
    ap.add_argument("--ms", default="M18")
    ap.add_argument("--root", default=REPO)
    ap.add_argument("--build-dir", default=None)
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--plan", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-prepare", action="store_true")
    ap.add_argument("--allow-dirty", action="append", default=[])
    ap.add_argument("--min-free-gb", type=float, default=2.0)
    a = ap.parse_args(argv)
    m = Migration(a)
    if a.cmd == "run":
        return m.run()
    m.prepare_for_undo()
    if a.cmd == "undo":
        if not os.path.exists(m.before_path):
            out("migrate undo: no before-listing in %s: nothing to undo" % m.build)
            return 2
        return 0 if m.undo("requested") else 4
    if a.cmd == "verify":
        before = m.read_listing(m.before_path) if os.path.exists(m.before_path) else None
        problems = m.verify(before, None)
        for p in problems:
            out("FAIL " + p)
        out("migrate verify: %s" % ("passed" if not problems else "%d problem(s)" % len(problems)))
        return 0 if not problems else 3
    return 2


if __name__ == "__main__":
    sys.exit(main())
