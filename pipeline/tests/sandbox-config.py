#!/usr/bin/env python
"""sandbox-config.py: the config of a test sandbox for the milestones before M16 (called by pipeline/tests/lib.sh sandbox_init).

M16 (Motion and energy rules E8 and E9) added rules and checks that the frozen low-energy plans and drafts of the earlier tests and their
editors that fail the same way every round would trip: the plan validator's energy rules, S12's energy check and liveness checks and the
early stop are turned off in the sandbox config (SANDBOX_ENERGY=on leaves them on, as pipeline/tests/test-m16.sh does).

  python pipeline/tests/sandbox-config.py <channel.json>

Since M20 these keys belong to the format (format.json `config`), so the sandbox sets them in the channel's own config block, which is
merged last (BUILD_SPEC.md 14.4). A plain config.json (a file without an "id") is edited in place as before.
"""
import json
import sys

p = sys.argv[1]
doc = json.load(open(p, encoding="utf-8-sig"))
c = doc.setdefault("config", {}) if "id" in doc else doc
c.setdefault("visual", {})["energy_rules"] = "off"
r = c.setdefault("review", {})
r["energy_check"] = False
r["liveness"] = False
r["early_stop"] = False
with open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write(json.dumps(doc, indent=2) + "\n")
