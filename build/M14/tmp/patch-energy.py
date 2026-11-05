p = "pipeline/lib/review/energy.py"
s = open(p, encoding="utf-8").read()
s = s.replace("STILL_MAX = FROZEN_MAX        # a still frame: frozen (DECISIONS.md M14)",
              "STILL_MAX = SUBTLE_MAX        # a still frame: below medium motion, frozen or subtle (DECISIONS.md M14)")
s = s.replace("  still_share_pct          the share of time inside still stretches of 1 s or more (a still frame is a frozen one)",
              "  still_share_pct          the share of time inside still stretches of 1 s or more (a still frame is below medium motion:\n                           frozen or subtle; the M13 reel's 29 percent and 2.8 s of the spec come out this way)")
s = s.replace('''The targets live in tokens.json `energy.targets` (70 percent of the look references' median for the three lower
bounds, the median over 0.7 for the two upper bounds, or the spec's paper-cards numbers when the style was not
calibrated);''', '''The targets live in tokens.json `energy.targets` (70 percent of the look references' median for the three lower
bounds, the median rounded up to the next 5 percent and 0.5 s for the two upper bounds, or the spec's paper-cards
numbers when the style was not calibrated; pipeline/lib/tokens.py derives them);''')
s = s.replace('''def derive_targets(look_medians: dict, share: float = TARGET_SHARE) -> dict:
    out = {}
    for name, direction, nd in MEASURES:
        v = look_medians.get(name)
        if v is None:
            out[name] = SPEC_TARGETS[name]
            continue
        raw = v * share if direction == "min" else v / share
        out[name] = round(raw, nd) if nd else int(round(raw))
    return out''', '''def derive_targets(look_medians: dict, share: float = TARGET_SHARE) -> dict:
    """The same rule as tokens.py energy_targets_from_medians: the lower bounds at 70 percent of the look median, the
    upper bounds at the median rounded up to the next 5 percent and 0.5 s."""
    import math
    out = dict(SPEC_TARGETS)
    for name, direction, nd in MEASURES:
        v = look_medians.get(name)
        if v is None:
            continue
        if direction == "min":
            out[name] = round(v * share, nd) if nd else int(round(v * share))
        elif name == "still_share_pct":
            out[name] = int(math.ceil(v / 5.0 - 1e-9) * 5)
        else:
            out[name] = round(math.ceil(v / 0.5 - 1e-9) * 0.5, 1)
    return out''')
s = s.replace('''           "note": "targets: the lower bounds (moving share, middle band, pixels changing) are 70 percent of the look references' median; the upper bounds (still stretches, longest still) the median over 0.7; tokens.json energy.targets carries them unless an Energy line in tweaks.md overrides them"}''',
              '''           "note": "targets: the lower bounds (moving share, middle band, pixels changing) are 70 percent of the look references' median; the upper bounds (still stretches, longest still) the median rounded up to the next 5 percent and 0.5 s; tokens.json energy.targets carries them unless an Energy line in tweaks.md overrides them"}''')
s = s.replace('''    print("targets (70 percent rule): " + ", ".join''', '''    print("targets (the 70 percent rule): " + ", ".join''')
open(p, "w", encoding="utf-8", newline="\n").write(s)
assert "STILL_MAX = SUBTLE_MAX" in s
print("energy.py patched")
