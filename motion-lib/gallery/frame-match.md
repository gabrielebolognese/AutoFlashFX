# frame-match: the library components against the style's numbers, the reference strips and the Motion and energy rules

Run 2026-11-07 12:23 by pipeline/bin/frame-match. Tolerances: 1 frame on timings, 10 percent on distances and overshoots; a reference strip must correlate at r >= 0.5 (DECISIONS.md 29). Numbers: styles/paper-cards/vocabulary.md and style.md through tokens.json; strips: styles/paper-cards/analysis/<vXX>/extra/s30_*.png. The life checks (M14, E1): every component is measured for 4.3 s; no visible element stands still for 0.5 s (the calm hold speed over half a second), the main element's inertia ends 2.0 to 4.0 s after its landing, and the energy columns are the component's own frames measured as review/energy.py measures a reel.

**1 pass, 0 fail** of 1 components.

| component | result | checks | best strip | r | moving share | pixels changing | longest still |
|---|---|---|---|---|---|---|---|
| caption-line | pass | 6/6 | v06/extra/s30_031.0_highlight.png | 0.972 | 0% | 0.09% | 4.33 s |

## caption-line: pass

| check | expected | measured | ok |
|---|---|---|---|
| fade: opacity frames | 4 frames | 4 | yes |
| fade: opacity frames | 4 frames | 4 | yes |
| exit: frames to fade out | 2 frames | 3 | yes |
| after: frames after the reference | 1 frames | 2 | yes |
| life: never static #cap-c0 | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 41 | yes |
| | | WARN: the rendered frames show a still stretch (the DOM keeps moving; a subpixel hold) | |

Strips: v03/extra/s30_capswap_008.0.png r=0.857; v01/extra/s30_sc18.png r=0.899; v06/extra/s30_031.0_highlight.png r=0.972

Energy alone (131 frames): moving share 0 percent, middle band 0 percent, pixels changing 0.09 percent, longest still 4.33 s, mean change 0.036

