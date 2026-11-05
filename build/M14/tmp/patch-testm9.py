"""test-m9 section 1 builds tokens in a sandbox from a copy of tweaks.md and asserts the PROPOSED state of the six version 2
lines (captions at 1480, then an accepted Caption position moving them to 1332). The user accepted all six lines on
2026-11-07 (commit 50218ae), so the sandbox copy re-proposes them first; the repo's own tokens.json is checked as it is."""
p = "pipeline/tests/test-m9.sh"
s = open(p, encoding="utf-8").read()
old = '''  cp "$REPO_DIR"/styles/paper-cards/style.md "$REPO_DIR"/styles/paper-cards/tweaks.md "$SANDBOX/styles/paper-cards/"
  SD="$SANDBOX_M/styles/paper-cards"; OUT="$SANDBOX_M/tokens.json"; CSS="$SANDBOX_M/tokens.css"'''
new = '''  cp "$REPO_DIR"/styles/paper-cards/style.md "$REPO_DIR"/styles/paper-cards/tweaks.md "$SANDBOX/styles/paper-cards/"
  # the scenario below starts from the six version 2 lines as proposals (the user accepted them on 2026-11-07, M14)
  python - "$SANDBOX/styles/paper-cards/tweaks.md" <<'EOF'
import re, sys
p = sys.argv[1]; s = open(p, encoding="utf-8").read()
for title in ("Caption position", "Right side, captions", "Hook header", "Length", "Accent-filled cards", "3D"):
    s = re.sub(r"^- \\*\\*" + re.escape(title) + r":\\*\\*(?=.*Proposal:)", "- PROPOSED **" + title + ":**", s, count=1, flags=re.M)
open(p, "w", encoding="utf-8", newline="\\n").write(s)
EOF
  SD="$SANDBOX_M/styles/paper-cards"; OUT="$SANDBOX_M/tokens.json"; CSS="$SANDBOX_M/tokens.css"'''
assert old in s
s = s.replace(old, new)
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("test-m9 patched")
