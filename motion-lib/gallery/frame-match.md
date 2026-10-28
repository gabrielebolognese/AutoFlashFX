# frame-match: the library components against the style's numbers, the reference strips and the Motion and energy rules

Run 2026-11-07 13:19 by pipeline/bin/frame-match. Tolerances: 1 frame on timings, 10 percent on distances and overshoots; a reference strip must correlate at r >= 0.5 (DECISIONS.md 29). Numbers: styles/paper-cards/vocabulary.md and style.md through tokens.json; strips: styles/paper-cards/analysis/<vXX>/extra/s30_*.png. The life checks (M14, E1): every component is measured for 4.3 s; no visible element stands still for 0.5 s (the calm hold speed over half a second), the main element's inertia ends 2.0 to 4.0 s after its landing, and the energy columns are the component's own frames measured as review/energy.py measures a reel.

**1 pass, 0 fail** of 1 components.

| component | result | checks | best strip | r | moving share | pixels changing | longest still |
|---|---|---|---|---|---|---|---|
| window-card | pass | 9/9 | v07/extra/s30_011.4_window_rise.png | 0.973 | 79.2% | 2.36% | 0.03 s |

## window-card: pass

| check | expected | measured | ok |
|---|---|---|---|
| enter: opacity frames | 5 frames | 5 | yes |
| enter: rise px | 38 px | 38 | yes |
| enter: position frames (fit) | 8 frames | 8 | yes |
| enter: ease | ease-out | expo.out | yes |
| after: frames after the reference | 4 frames | 5 | yes |
| life: never static #wc | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #wc-mascot | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 0 | yes |
| life: inertia after the landing #wc | 2.0 to 4.0 s s (hold speed 9.21 px/s) | 2.83 | yes |

Strips: v07/extra/s30_011.4_window_rise.png r=0.973; v01/extra/s30_hook.png r=0.96; v03/extra/s30_hook_000.0.png r=0.924

Energy alone (131 frames): moving share 79.2 percent, middle band 82.3 percent, pixels changing 2.36 percent, longest still 0.03 s, mean change 0.732

