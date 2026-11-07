# frame-match: the library components against the style's numbers, the reference strips and the Motion and energy rules

Run 2026-11-07 23:04 by pipeline/bin/frame-match. Tolerances: 1 frame on timings, 10 percent on distances and overshoots; a reference strip must correlate at r >= 0.5 (DECISIONS.md 29). Numbers: styles/paper-cards/vocabulary.md and style.md through tokens.json; strips: styles/paper-cards/analysis/<vXX>/extra/s30_*.png. The life checks (M14, E1): every component is measured for 4.3 s; no visible element stands still for 0.5 s (the calm hold speed over half a second), the main element's inertia ends 2.0 to 4.0 s after its landing, and the energy columns are the component's own frames measured as review/energy.py measures a reel.

**2 pass, 0 fail** of 2 components.

| component | result | checks | best strip | r | moving share | pixels changing | longest still |
|---|---|---|---|---|---|---|---|
| caption-group | pass | 7/7 | none | none | 3.1% | 0.23% | 3.67 s |
| caption-word | pass | 5/5 | v06/extra/s30_031.0_highlight.png | 0.955 | 0.8% | 0.29% | 3.13 s |

## caption-group: pass

| check | expected | measured | ok |
|---|---|---|---|
| fade: opacity frames | 5 frames | 5 | yes |
| exit: frames to fade out | 4 frames | 5 | yes |
| life: never static #grp-0 | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #grp-0-w0 | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #grp-0-w1 | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #grp-0-w3 | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 10 | yes |

Energy alone (131 frames): moving share 3.1 percent, middle band 3.8 percent, pixels changing 0.23 percent, longest still 3.67 s, mean change 0.095

## caption-word: pass

| check | expected | measured | ok |
|---|---|---|---|
| fade: opacity frames | 4 frames | 4 | yes |
| fade: opacity frames | 4 frames | 4 | yes |
| exit: frames to fade out | 2 frames | 2 | yes |
| after: frames after the reference | 1 frames | 2 | yes |
| life: pixels never still | < 15 frames frames | 9 | yes |

Strips: v03/extra/s30_capswap_008.0.png r=0.95; v01/extra/s30_sc18.png r=0.939; v06/extra/s30_031.0_highlight.png r=0.955

Energy alone (131 frames): moving share 0.8 percent, middle band 0 percent, pixels changing 0.29 percent, longest still 3.13 s, mean change 0.104

