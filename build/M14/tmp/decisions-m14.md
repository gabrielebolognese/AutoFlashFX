
## M14 Motion grammar and energy meter (2026-11-07)

### The energy meter (E0)
288. **The meter is pipeline/lib/review/energy.py, run as `python pipeline/lib/review energy <video> [--plan merged.json]`.**
    ffmpeg decodes the video at 30 fps into 108x192 grayscale frames (the area filter: every source pixel counts), and
    every frame gets the mean absolute change against the previous one (0 to 255): frozen under 0.05, subtle under 0.6,
    medium under 4, big from 4. The moving share counts the medium and big frames; the middle band does the same on
    rows 64 to 127 (y 640 to 1280 at 1080x1920); the pixels changing are the mean share of pixels that change by more
    than 8; a still stretch is a run of frames below medium (frozen or subtle) lasting 1 s or more, the still share is
    the time inside such runs and the longest still is the longest run. "Still" means below medium, not frozen: with
    that reading the M13 reel (build/M13/rerun/1.mp4) measures 15.9, 15.1, 1.21, 31.9 percent and 2.8 s against the
    spec's 16, 15, 1.2, 29 and 2.8 (with "frozen" it would measure 0 percent and 0.67 s, which no reel would ever
    fail). With a plan the scenes are measured one by one on their frame ranges, with the same targets, and the
    report lists the failing scenes (M16's review routes them to 9a). The whole measurement is numpy on raw frames:
    about 1 s per 10 s of video.
289. **Calibration and targets.** `energy calibrate --refs styles/paper-cards/refs --out styles/paper-cards/analysis/energy.json`
    measures the nine references (nicknamed as analysis/index.md does) and keeps every number and the medians per
    group. The look medians on this PC: moving share 58.55 percent, middle band 65.55, pixels changing 4.66, still
    stretches 13.25 percent, longest still 1.95 s (the motion refs: 34.5, 38.1, 2.69, 29.4 and 1.7). The targets: the
    three lower bounds at 70 percent of the look median (41, 46, 3.3; the spec's 42 came from a slightly different
    measurement of the same videos), the two upper bounds at the look median rounded up to the next 5 percent and
    0.5 s (15 percent and 2 s: "70 percent of the median" cannot apply to a bound that must not be exceeded, and the
    spec's numbers are exactly the references' own level rounded up). tokens.py derives tokens.json `energy` from
    energy.json when it exists next to the style (its medians' hash is a third source of tokens.json, so a new
    calibration rebuilds the tokens), else from the spec's paper-cards numbers; an `- **Energy:** moving 45, middle 50,
    pixels 3.5, still 12, longest 1.5` line in tweaks.md overrides any subset. The energy CLI reads the repo's
    tokens.json by default, so every caller judges against the calibrated targets. analysis/ is not in git: another
    machine gets the spec's numbers until it calibrates.
290. **tokens.json `motion.grammar` holds the Motion and energy rules as values** (pipeline/lib/tokens.py GRAMMAR: the
    main animation's combined properties, the inertia, the three hold levels, the exit, the edge and ambient layers,
    the camera and depth step, the mascot idle, E3's caption fonts and ratios and E4's budget for M15, E8's
    composition numbers for M16, and the text zones derived from the zones: the caption band, the hook header, the end
    card's text). tokens.css exposes them as `--m-*` custom properties (and the zones as `--m-zone-<name>: x y w h`),
    which pc-motion.js reads at mount. `verify` exempts motion.grammar and energy: their numbers come from BUILD_SPEC.md
    section 5 and from the calibration, not from style.md or tweaks.md. TOKENS_VERSION is 2, so every tokens.json is
    rebuilt once.

### pc-motion.js, the shared grammar (E1, E2, E6)
291. **HyperFrames seeks GSAP timelines with events suppressed.** Its runtime drives every sub-composition timeline with
    `totalTime(t, true)` (the second argument suppresses callbacks), and a Node check with the vendored GSAP 3.15
    confirmed that `onUpdate` never fires under it, while a tween on an accessor property runs its setter. M9's
    count-up, typing and end-card wobble were onUpdate-driven; the golden render of M9 shows their final states, so
    some capture path did fire them, but nothing in the library relies on callbacks any more: pc-motion.js tweens
    real properties (position, scale, rotation, opacity) or an object whose property setter renders text
    (PCM.driven, PCM.countUp, PCM.typeInto), and a wobble is a pair of yoyo tweens. Every frame is the same whichever
    way the timeline is seeked.
292. **One life per element (PCM.life).** The four phases of E1 are GSAP tweens laid on the component's timeline:
    the main animation (the style's measured enter: rise 38 px over 8 frames expo.out with opacity over 5; the pop
    with its overshoot; the fly-in; a fade; a slide), the combined properties of E2 on top of it (a zoom from 0.85, or
    0.92 for small things, or 1.15 from a close start, over 12 frames power3.inOut, and a parallax rotateY or rotateX
    from 12 degrees to 1 starting 3 frames later), then the inertia and the hold as one tween per property whose ease
    is the closed form d(t) = A (1 - (1 - min(t, D) / D)^3) + v t (PCM.glide: a cubic decelerating tail of amplitude A
    over D = 3 s on top of the hold's constant speed v, so the speed never reaches zero), then the exit. The inertia
    continues the main move's direction: a risen card keeps rising 12 px, a zoomed one keeps growing to 1.03, a turned
    one settles through 0 to minus 1 degree. The hold levels are calm, normal and lively (2, 4, 8 px per second; 0.2,
    0.4, 0.6 degrees per second; 0.2, 0.35, 0.5 percent per second), a `hold` prop on every element component, normal
    by default, and a hold kind per element (drift, rotate, scale or all). The hold ends at the element's exit (every
    exit target is absolute, computed from the hold's end, so the result does not depend on the order frames are
    rendered in) or at a 90 s horizon when the clip ends without one. Children of a holding element (rows, bars,
    caption words, the headline's words) get their own main animation and no hold of their own: the group moves as
    one, as E1 asks.
293. **Each element carries its own perspective** (GSAP transformPerspective 1400 px, the vanishing point at its center)
    instead of one camera on the root. A rotated element then projects symmetrically around its center, so its
    measured center is exact: frame-match fits the main animation on the element's center (cy, cx) and the review's
    pixel checks see no asymmetric growth. E6's depth is per element too: PCM.depth puts a card's image, title and
    body (a chart's title and bars, a table's head and rows, a chat's reply and bar, the DM card's avatar and text)
    at translateZ steps of 24 px under preserve-3d, and the hold's slow rotation is the camera. Elements with
    overflow hidden or a filter (window cards, terminals, the exits' blur) stay flat: the browser flattens them.
294. **Per component.** The headline's blocks hold by rotation and scale only (a drift would carry the kicker above the
    safe top) and move from frame 0; caption chunks drift upward at the calm speed while on screen (E3's two modes
    come in M15); logo tiles turn only 6 degrees and the lockup and the DM avatar only drift (BRAND.md: a logo is
    never turned or distorted); the end card keeps its v02 wobble as yoyo tweens on its 2D rotation while its life
    drives the rest; the camera move's stage drifts its content before the move and holds from where the move ended
    (PCM.camera, PCM.life's `from` state); the mascot idles on its inner svg (a bob, a scaleY breath, the prop group
    `.pc-prop` wiggling, the eyes `.pc-eye` blinking every 2.6 to 3.8 s, seeded) on top of the wrapper's life, in the
    card, window card, fly-in, end card and mascot components; hero-3d's shadow breathes with a scale hold and its
    object spins and bobs from the hf-seek time as before. The three remaining state changes (a struck text dimming,
    a send button recoloring, a screenshot panning inside its window) are PCM.dim, PCM.recolor and PCM.pan, so no
    composition file holds a tween, an ease or an onUpdate of its own (test-m14 greps for them).

### The canvas (E5, E7) and icon-3d (E6)
295. **paper-canvas has a timeline now** (window.__timelines["paper-canvas"]; its host lost data-no-timeline in golden.py
    and the showreel, and carries `seed` and `duration` as variables: the seed from the idea id, the duration the
    reel's length plus 1 s). PCM.canvas builds the edge filler (6 elements, 3 per side: soft surface cards, thumbnail
    frames, dark chips without text, glow shapes and accent stars, 30 to 70 percent outside the frame with the share
    kept 5 points inside that range so the sway never leaves it, the inside part never over 180 px, in three y bands
    that avoid the hook header and are shrunk by the 36 px sway) and the ambient layer (16 stars, dots and small
    clouds in the top and bottom bands and the side margins, never overlapping each other), both as sine sways whose
    period follows from the amplitude and the speed cap (PCM.periodFor: the edge layer at most 20 px per second, the
    ambient at most 10) and a twinkle on the opacity. The placement avoids the text zones of tokens.json with a 10 to
    14 px pad; the layers carry data-layout-ignore, sit under every component (the canvas is z 0) and the review's
    mechanical checks never look at the canvas host (the M14 line of S12). The harness's background copy of the
    canvas stays the static one (its scripts are stripped), so a component measured alone sees no layers.
296. **icon-3d** builds a low-poly Three.js icon in code: a small SVG path parser (M L H V C Q Z, absolute and relative)
    turns one of six paths (bolt, star, play, check, cursor, heart) into a THREE.Shape extruded with a bevel and flat
    shading, or a primitive (a rounded slab from absarc, a torus, an icosahedron), in one palette color, lit like
    hero-3d, turning at `spin` degrees per second with a bob, drawn from the hf-seek time. Without WebGL, or with
    `mode: css`, the CSS-extruded fallback: the same SVG in 8 to 16 depth layers (translateZ, the back layers darker)
    under a preserve-3d stage that PCM.life pops in, PCM.spin turns and PCM.sway bobs; the root reports data-webgl 1
    or 0. The catalog marks it kind 3d with `fallback: css`, so S10 never replaces it with a card; it is allowed in the
    hook and the ask beats only, because tweaks.md's 3D line keeps 3D objects to the hook and the end card (E6's icon
    at the center of any scene needs that line relaxed: HUMAN_TODO). golden.py, events.py, mechanical.py and the plan
    validator treat it as hero-3d (clip_start, the label).

### frame-match, the gallery, the golden
297. **frame-match measures every component for 4.33 s** (130 frames, the move's own frames for the strip correlation)
    and adds the life checks of E1: no visible tracked element stands still for 0.5 s (in every 15-frame window it
    moves 0.9 px, or turns 0.09 degrees, or scales 0.09 percent, or fades, or changes its text: the calm hold over half
    a second less a rounding margin; a canvas is judged on its pixels), the main element's inertia ends 2 to 4 s after
    its landing (the first 10 frames whose motion stays within 15 percent plus 0.02 px of the hold speed, the hold
    speed being the mean motion of the last 15 frames), and the component's own frames measured by review/energy.py
    (108x192, the same thresholds) for the gallery's energy line and catalog.json's `energy`. The fits of M9 read
    their end value just after the expected landing instead of the last frame (the element keeps moving), positions
    are centers, and the scale comes from the length of the transform's x basis vector (m11, m12, m13: a 2D
    hypot(a, b) read a rotated element as smaller). The harness pages take a tag so two harnesses never share a page
    file (a probe next to frame-match corrupted both).
298. **Earlier milestones touched:** M9 (test-m9 section 1 re-proposes the six version 2 lines in its sandbox copy of
    tweaks.md, because the user accepted them on 2026-11-07 and the scenario asserts the proposed state; harness.py's
    tag and 3D-aware measures; golden.py's canvas host and the pc-motion.js copy; gallery.py's showreel host and
    energy line; catalog.py's META), M10 (project.py's replace_3d skips a css fallback; visual/common.py's enter_frames
    and footprint, plan_validate.py and events.py know icon-3d; the frozen fixtures' index.html canvas hosts), M11
    (mechanical.py's clip_start for icon-3d), M1 (config: nothing). The frozen test projects rebuild from the plans
    with the new library, so M10 to M13's fake tests exercise it.
