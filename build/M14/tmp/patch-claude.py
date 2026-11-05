"""CLAUDE.md: the build status after M14 (applied once the M14 test passed)."""
p = "CLAUDE.md"
s = open(p, encoding="utf-8").read()
old_status = '''- M13 Hardening: done (2026-11-02). Next: M14 Motion grammar and energy meter, M15 Kinetic captions and text
  discipline, M16 Director, components and the energy loop (BUILD_SPEC.md section 5, Motion and energy rules), then
  M17 Editable project export (S15): pending. The build is driven by `bash build-runner.sh` (`--until M16` stops
  after M16); its log is build/build.log and its per-milestone reports are in build/M<n>/.'''
new_status = '''- M14 Motion grammar and energy meter: done (2026-11-07). Next: M15 Kinetic captions and text discipline, M16
  Director, components and the energy loop (BUILD_SPEC.md section 5, Motion and energy rules E3, E4, E8, E9), then
  M17 Editable project export (S15): pending. The build is driven by `bash build-runner.sh` (`--until M16` stops
  after M16); its log is build/build.log and its per-milestone reports are in build/M<n>/.'''
assert old_status in s
s = s.replace(old_status, new_status)
old_exists = '''  pipeline/tests/m13-run.sh (the three-idea driver) and pipeline/tests/fixtures/ideas/three-ideas.txt. Run every
  test with `bash pipeline/tests/run-all.sh`'''
new_exists = '''  pipeline/tests/m13-run.sh (the three-idea driver) and pipeline/tests/fixtures/ideas/three-ideas.txt, M14: the
  energy meter pipeline/lib/review/energy.py (`python pipeline/lib/review energy <video> [--plan merged.json]`: the
  moving share, the middle band, the pixels changing, the still stretches and the longest still of a reel and of each
  scene against tokens.json energy.targets; `energy calibrate --refs styles/paper-cards/refs --out
  styles/paper-cards/analysis/energy.json` measures the nine references), tokens.json `motion.grammar` (the Motion and
  energy rules as values: pipeline/lib/tokens.py GRAMMAR, exposed as `--m-*` in motion-lib/assets/tokens.css) and
  `energy` (the targets: 70 percent of the look references' medians, 41, 46, 3.3, 15 percent and 2 s on this PC; an
  `- **Energy:** moving 45, still 12` line in tweaks.md overrides them), the shared motion grammar
  motion-lib/assets/pc-motion.js (PCM.life: main animation, inertia, hold, exit; the combined zoom and parallax
  rotation; PCM.canvas: the edge and ambient layers; PCM.idle: the mascot; PCM.depth: the 2.5D parts; count-ups and
  typing as setter tweens because HyperFrames seeks with GSAP events suppressed) that every component uses (every
  element component has a `hold` prop: calm, normal, lively), paper-canvas with a timeline, `seed` and `duration` props
  and the layers, icon-3d (Three.js extruded SVG paths and primitives, a CSS-extruded fallback, `mode` auto|webgl|css),
  frame-match's life checks (never static for 0.5 s, the inertia 2 to 4 s) and per-component energy (catalog.json
  `energy`, the gallery's energy line), golden/test-idea/energy.json and build/M14/golden-energy-before.json. Run every
  test with `bash pipeline/tests/run-all.sh`'''
assert old_exists in s
s = s.replace(old_exists, new_exists)
old_tests = '''`M12_SECTIONS="1 2 3 5" bash pipeline/tests/test-m12.sh` and `M13_SECTIONS="1 2 4" bash pipeline/tests/test-m13.sh`
  (about 20 minutes) are the fake-only tests).'''
new_tests = '''`M12_SECTIONS="1 2 3 5" bash pipeline/tests/test-m12.sh` and `M13_SECTIONS="1 2 4" bash pipeline/tests/test-m13.sh`
  (about 20 minutes) are the fake-only tests; `bash pipeline/tests/test-m14.sh` makes no model call, about 35 minutes:
  frame-match on every component and the golden render).'''
assert old_tests in s
s = s.replace(old_tests, new_tests)
old_gallery = '''- `motion-lib/`: approved HyperFrames components, candidates/, gallery/. `golden/`: example reels for the visual
  director.'''
new_gallery = '''- `motion-lib/`: approved HyperFrames components, candidates/, gallery/, assets/pc-motion.js (the motion grammar
  every component uses: M14). `golden/`: example reels for the visual director (energy.json: the golden's energy).'''
assert old_gallery in s
s = s.replace(old_gallery, new_gallery)
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("CLAUDE.md patched")
