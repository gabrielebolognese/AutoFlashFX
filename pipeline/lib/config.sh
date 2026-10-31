# pipeline/lib/config.sh: read config.json. Source common.sh first.
#
#   cfg <dotted.key> [default]      prints the value: scalars as text, true/false, lists and objects as JSON.
#                                   Missing key: prints the default when given, else fails with exit 1.
#   cfg_rows <key> field...         for a list of objects: one line per element, the named fields joined by the
#                                   unit separator (\x1f), empty when a field is absent. Read with
#                                   IFS=$'\x1f' read -r f1 f2 ...
#
# Model names and effort levels come from here and never from code (BUILD_SPEC.md section 3).

cfg() {
  "$REELS_PY" - "$REELS_CONFIG" "$1" "${2-}" "$#" <<'EOF'
import json, sys
sys.stdout.reconfigure(newline="\n")  # Windows Python writes CRLF to pipes otherwise
path, key, default, argc = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
with open(path, encoding="utf-8-sig") as f:
    cur = json.load(f)
for part in key.split("."):
    if isinstance(cur, dict) and part in cur:
        cur = cur[part]
    elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
        cur = cur[int(part)]
    else:
        if argc >= 2:
            print(default)
            sys.exit(0)
        print(f"config: missing key {key} in {path}", file=sys.stderr)
        sys.exit(1)
if isinstance(cur, bool):
    print("true" if cur else "false")
elif isinstance(cur, (dict, list)):
    print(json.dumps(cur, ensure_ascii=False))
elif cur is None:
    print("")
else:
    print(cur)
EOF
}

cfg_rows() {
  "$REELS_PY" - "$REELS_CONFIG" "$@" <<'EOF'
import json, sys
sys.stdout.reconfigure(newline="\n")  # Windows Python writes CRLF to pipes otherwise
path, key, fields = sys.argv[1], sys.argv[2], sys.argv[3:]
with open(path, encoding="utf-8-sig") as f:
    cur = json.load(f)
for part in key.split("."):
    cur = cur.get(part) if isinstance(cur, dict) else None
    if cur is None:
        sys.exit(0)
for row in cur if isinstance(cur, list) else []:
    values = []
    for name in fields:
        value = row.get(name, "") if isinstance(row, dict) else ""
        if isinstance(value, bool):
            value = "true" if value else "false"
        elif isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        values.append("" if value is None else str(value))
    print("\x1f".join(values))
EOF
}
