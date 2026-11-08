#!/usr/bin/env python
"""m17-fixture.py: a small folder shaped like the real one, as its own git repo, for the tests of M17's tools (and a start for M18's rehearsal).

  python pipeline/tests/m17-fixture.py <dest-dir>      (the folder must not exist or be empty)

What it builds (every file is a few bytes; the structure and the git states are the real ones):
  engine        .gitignore, run.sh, config.json (a copy of the repo's), pipeline/ (a shell and a Python file with planted references:
                a path built in code, a config key, an export name, a direct read of config.json; a prompt; a test), tools/, CLAUDE.md,
                build/ (a summary tree), node_modules/ (ignored)
  channel data  ideas.txt, library/ (tracked text, ignored voice files, the runner-written .hooks.stats.json), styles/paper-cards
                (style and tokens tracked; refs and analysis ignored), styles/sfx (audio ignored, the map tracked with the fixture's own
                absolute path in it), motion-lib/ (a component tracked, .harness ignored with a <base href> to the fixture), golden/
  runner state  logs/ (runner.log, status.txt, history.txt with two exports, limits.log, a tool log folder), runs/ with one finished
                run and one unfinished run (their files name old paths in every form), exports/1 and exports/2 (N.mp4, Ncaptions.txt,
                Nhook2.mp4, project/), exports/notes.txt (not an exports/N folder), voicetests/ (ignored, stays)
Everything is committed except the ignored files, so `git status` is clean.
"""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

GITIGNORE = """node_modules/
__pycache__/
*.pyc
/runs/
/exports/
/logs/
/.locks/
voicetests/
library/voice/*
!library/voice/README.txt
library/.hooks.index.json
styles/*/refs/
styles/*/analysis/
styles/sfx/**/*.wav
styles/sfx/**/*.mp3
motion-lib/.harness/
golden/*/golden.mp4
*.mp4
*.wav
"""


def w(root, rel, text, binary=False):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if binary:
        with open(p, "wb") as f:
            f.write(text)
    else:
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)


def main(dest):
    dest = os.path.abspath(dest)
    if os.path.exists(dest) and os.listdir(dest):
        print("m17-fixture: %s is not empty" % dest, file=sys.stderr)
        return 2
    os.makedirs(dest, exist_ok=True)
    mixed = dest.replace("\\", "/")
    drive = ("/" + mixed[0].lower() + mixed[2:]) if len(mixed) > 2 and mixed[1] == ":" else mixed
    back = mixed.replace("/", "\\")

    w(dest, ".gitignore", GITIGNORE)
    w(dest, ".gitattributes", "* text=auto eol=lf\n")
    w(dest, "README.md", "fixture\n")
    w(dest, "CLAUDE.md", "# fixture\n\nFinished reels are in exports/N/ (N.mp4, Ncaptions.txt, Nhook2.mp4). Hooks: library/hooks.txt.\n")
    shutil.copyfile(os.path.join(REPO, "config.json"), os.path.join(dest, "config.json"))
    w(dest, "run.sh", "#!/usr/bin/env bash\nsource pipeline/lib/common.sh\necho run\n")
    # planted references in the engine
    w(dest, "pipeline/lib/x.sh",
      "#!/usr/bin/env bash\n"
      "# the hooks live in library/hooks.txt (a comment)\n"
      'HOOKS="$REELS_ROOT/library/hooks.txt"\n'
      'WPM="$(cfg voice.wpm)"\n'
      'CAP="exports/$n/${n}captions.txt"\n'
      'echo "$REELS_CONFIG"\n'
      'cp "$FILE" "$REELS_ROOT/logs/history.txt"\n'
      'ls "$ROOT/fixtures/runs/a"\n')
    w(dest, "pipeline/lib/y.py",
      '"""y.py: reads styles/paper-cards/tokens.json (a docstring line)."""\n'
      "import json\n"
      'cfg = json.load(open("config.json"))\n'
      'review = cfg["review"]\n'
      'voice = cfg.get("voice")\n'
      'path = "library/profile/voice.md"\n'
      'out = f"{n}hook2.mp4"\n')
    w(dest, "pipeline/stages/01-x/prompt.md", "Read library/profile/voice.md and styles/paper-cards/style.md.\n")
    w(dest, "pipeline/tests/t.sh", "#!/usr/bin/env bash\ncat \"$SANDBOX/logs/history.txt\"\n# exports/1/1.mp4\n")
    w(dest, "pipeline/tests/fixtures/f.json", '{"path": "runs/test/state.json"}\n')
    w(dest, "tools/voice.py", "print('voice')\n")
    # channel data
    w(dest, "ideas.txt", "{idea one}\n")
    w(dest, "library/hooks.txt", "hook line one\n")
    w(dest, "library/profile/voice.md", "voice\n")
    w(dest, "library/voice/README.txt", "put your voice here\n")
    w(dest, "library/voice/engine.txt", "engine: kokoro\n")
    w(dest, "library/voice/reference.wav", b"RIFFfixture", binary=True)
    w(dest, "library/.hooks.stats.json", "{}\n")
    w(dest, "library/.hooks.index.json", "{}\n")
    w(dest, "styles/paper-cards/style.md", "style\n")
    w(dest, "styles/paper-cards/tokens.json", "{}\n")
    w(dest, "styles/paper-cards/refs/a.mp4", b"mp4fixture", binary=True)
    w(dest, "styles/paper-cards/analysis/v01/x.json", '{"video": "styles/paper-cards/refs/a.mp4"}\n')
    w(dest, "styles/sfx/pop.wav", b"RIFFpop", binary=True)
    w(dest, "styles/sfx/sfx-map.json", json.dumps({"files": [{"path": mixed + "/styles/sfx/pop.wav"}]}, indent=1) + "\n")
    w(dest, "motion-lib/compositions/a.html", "<div>a</div>\n")
    w(dest, "motion-lib/.harness/h.html", '<base href="file:///%s/motion-lib/">\n' % mixed)
    w(dest, "golden/test-idea/plan.json", "{}\n")
    w(dest, "golden/test-idea/golden.mp4", b"mp4golden", binary=True)
    # runner state
    w(dest, "logs/runner.log", "[10:00] READY\n")
    w(dest, "logs/status.txt", "[10:00] READY\n")
    w(dest, "logs/limits.log", "none\n")
    w(dest, "logs/.activity", "0\tbetween ideas\n")
    w(dest, "logs/build-sfx-map/calls/001.json", "{}\n")
    w(dest, "logs/history.txt",
      "2026-11-01 10:30 | idea one | flashfx | exported 1\n2026-11-02 11:30 | idea two | external | exported 2\n"
      "2026-11-02 12:30 | idea three | - | dropped: facts don't hold\n")
    done, openrun = "2026-11-01_1000_done-idea", "2026-11-02_1100_open-idea"
    w(dest, "runs/%s/state.json" % done, json.dumps({"status": "exported", "stages": {"01-research": {"status": "done"}}}) + "\n")
    w(dest, "runs/%s/01-research/research.json" % done,
      json.dumps({"relative": "runs/%s/01-research/assets/x.png" % done, "mixed": mixed + "/styles/paper-cards/style.md",
                  "posix": drive + "/library/hooks.txt"}) + "\n")
    w(dest, "runs/%s/01-research/assets/x.png" % done, b"\x89PNG\0fixture", binary=True)
    w(dest, "runs/%s/01-research/calls/001.out.json" % done, '{"raw": "runs/%s"}\n' % done)
    w(dest, "runs/%s/14-export/export.json" % done, json.dumps({"files": {"reel": "../13-render/final.mp4"}}) + "\n")
    w(dest, "runs/%s/state.json" % openrun, json.dumps({"status": "running", "stages": {"01-research": {"status": "done"}, "02-expansion": {"status": "pending"}}}) + "\n")
    w(dest, "runs/%s/01-research/research.json" % openrun,
      json.dumps({"backslash": back + "\\styles\\paper-cards"}) + "\n")
    w(dest, "runs/%s/01-research/stage.log" % openrun, "wrote " + back + "\\logs\\x\n")
    for n, rid in ((1, done), (2, openrun)):
        w(dest, "exports/%d/%d.mp4" % (n, n), b"mp4reel%d" % n, binary=True)
        w(dest, "exports/%d/%dhook2.mp4" % (n, n), b"mp4hook%d" % n, binary=True)
        w(dest, "exports/%d/%dcaptions.txt" % (n, n),
          "CAPTION\nreel %d\n\nHOOKS\n%d.mp4 uses: \"hook\"\n%dhook2.mp4 uses: \"hook b\"\n\nRUN\nruns/%s\n" % (n, n, n, rid))
        w(dest, "exports/%d/project/p.json" % n, "{}\n")
    w(dest, "exports/notes.txt", "a note the exporter does not know\n")
    w(dest, "voicetests/a.wav", b"RIFFscratch", binary=True)
    w(dest, "build/M17/x.txt", "build\n")
    w(dest, "node_modules/pkg/package.json", "{}\n")

    def g(*args):
        subprocess.run(["git", "-C", dest] + list(args), check=True, capture_output=True)
    g("init", "-q")
    g("config", "user.email", "fixture@example.invalid")
    g("config", "user.name", "fixture")
    g("config", "core.autocrlf", "false")
    g("add", "-A")
    g("commit", "-q", "-m", "fixture")
    print(dest)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
