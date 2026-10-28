# frame-match: the library components against the style's numbers, the reference strips and the Motion and energy rules

Run 2026-11-07 10:53 by pipeline/bin/frame-match. Tolerances: 1 frame on timings, 10 percent on distances and overshoots; a reference strip must correlate at r >= 0.5 (DECISIONS.md 29). Numbers: styles/paper-cards/vocabulary.md and style.md through tokens.json; strips: styles/paper-cards/analysis/<vXX>/extra/s30_*.png. The life checks (M14, E1): every component is measured for 4.3 s; no visible element stands still for 0.5 s (the calm hold speed over half a second), the main element's inertia ends 2.0 to 4.0 s after its landing, and the energy columns are the component's own frames measured as review/energy.py measures a reel.

**28 pass, 0 fail** of 28 components.

| component | result | checks | best strip | r | moving share | pixels changing | longest still |
|---|---|---|---|---|---|---|---|
| camera-move | pass | 4/4 | v02/extra/s30_zoom27.png | 0.899 | 6.9% | 1.93% | 3.43 s |
| caption-line | pass | 6/6 | v06/extra/s30_031.0_highlight.png | 0.972 | 0% | 0.09% | 4.33 s |
| card | pass | 10/10 | v07/extra/s30_000.0_hook.png | 0.935 | 6.9% | 0.5% | 4 s |
| chart-card | pass | 13/13 | v04/extra/s30_bars_f1426.png | 0.978 | 13.8% | 0.55% | 3.7 s |
| chat-card | pass | 10/10 | v06/extra/s30_070.9_typing_tail.png | 0.954 | 0.8% | 0.28% | 4.07 s |
| check-badge | pass | 6/6 | v04/extra/s30_check_f1200.png | 0.98 | 0% | 0.03% | 4.33 s |
| dark-chip | pass | 6/6 | v07/extra/s30_004.4_caption_tag.png | 0.955 | 0% | 0.02% | 4.33 s |
| dm-card | pass | 7/7 | v03/extra/s30_hook_000.0.png | 0.908 | 6.2% | 0.34% | 4 s |
| end-card | pass | 11/11 | v08/extra/s30_038.9_end.png | 0.975 | 11.5% | 0.64% | 3 s |
| exit-move | pass | 10/10 | v07/extra/s30_034.7_exit_counter.png | 0.967 | 7.7% | 1.07% | 3.2 s |
| fly-in | pass | 7/7 | v01/extra/s30_hook.png | 0.982 | 8.5% | 1.08% | 3.97 s |
| handwritten-callout | pass | 5/5 | none | none | 0% | 0.02% | 4.33 s |
| headline | pass | 6/6 | v01/extra/s30_hook.png | 0.99 | 0% | 0.08% | 4.33 s |
| hero-3d | pass | 5/5 | none | none | 3.8% | 0.4% | 3.93 s |
| icon-3d | pass | 4/4 | none | none | 0% | 0.09% | 4.33 s |
| light-chip | pass | 4/4 | v03/extra/s30_label_042.4.png | 0.972 | 0% | 0.02% | 4.33 s |
| logo-tile | pass | 10/10 | v02/extra/s30_hook.png | 0.889 | 0% | 0.07% | 4.33 s |
| mascot | pass | 4/4 | v08/extra/s30_000.8_mascot_title.png | 0.988 | 0% | 0.11% | 4.33 s |
| paper-canvas | pass | 10/10 | none | none | 0% | 0.01% | 4.33 s |
| pop | pass | 6/6 | v03/extra/s30_cta_058.0.png | 0.992 | 0% | 0.02% | 4.33 s |
| progress-bar | pass | 13/13 | v01/extra/s30_card33.png | 0.897 | 0.8% | 0.27% | 3.8 s |
| speech-bubble | pass | 9/9 | v08/extra/s30_038.9_end.png | 0.987 | 3.8% | 0.29% | 3.87 s |
| stat-number | pass | 9/9 | v04/extra/s30_count_f925.png | 0.945 | 14.6% | 0.32% | 3.23 s |
| strike-through | pass | 5/5 | v06/extra/s30_062.3_xstamp.png | 0.966 | 0% | 0.02% | 4.33 s |
| table-card | pass | 10/10 | v04/extra/s30_scene_f184.png | 0.972 | 8.5% | 0.51% | 3.9 s |
| terminal-card | pass | 9/9 | v06/extra/s30_070.9_typing_tail.png | 0.959 | 10% | 0.76% | 3.03 s |
| thumb-grid | pass | 9/9 | v04/extra/s30_deckgrid_f420.png | 0.984 | 5.4% | 0.22% | 3.97 s |
| window-card | pass | 9/9 | v07/extra/s30_011.4_window_rise.png | 0.956 | 20.8% | 1.93% | 3.1 s |

## camera-move: pass

| check | expected | measured | ok |
|---|---|---|---|
| shrink: end scale | 0.458 ratio | 0.458 | yes |
| shrink: frames (fit) | 8 frames | 8 | yes |
| life: never static #cm-window | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 0 | yes |

Strips: v02/extra/s30_zoom27.png r=0.899; v05/extra/s30_windowshrink_f520.png r=0.872

Energy alone (131 frames): moving share 6.9 percent, middle band 7.7 percent, pixels changing 1.93 percent, longest still 3.43 s, mean change 0.994

## caption-line: pass

| check | expected | measured | ok |
|---|---|---|---|
| fade: opacity frames | 4 frames | 4 | yes |
| fade: opacity frames | 4 frames | 4 | yes |
| exit: frames to fade out | 2 frames | 3 | yes |
| after: frames after the reference | 1 frames | 2 | yes |
| life: never static #cap-c0 | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 43 | yes |
| | | WARN: the rendered frames show a still stretch (the DOM keeps moving; a subpixel hold) | |

Strips: v03/extra/s30_capswap_008.0.png r=0.885; v01/extra/s30_sc18.png r=0.89; v06/extra/s30_031.0_highlight.png r=0.972

Energy alone (131 frames): moving share 0 percent, middle band 0 percent, pixels changing 0.09 percent, longest still 4.33 s, mean change 0.037

## card: pass

| check | expected | measured | ok |
|---|---|---|---|
| enter: opacity frames | 5 frames | 5 | yes |
| enter: rise px | 38 px | 38 | yes |
| enter: position frames (fit) | 8 frames | 8 | yes |
| enter: ease | ease-out | expo.out | yes |
| after: frames after the reference | 4 frames | 5 | yes |
| fade: opacity frames | 4 frames | 4 | yes |
| life: never static #card-box | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #card-mascot | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 0 | yes |
| life: inertia after the landing #card-box | 2.0 to 4.0 s s (hold speed 9.21 px/s) | 2.83 | yes |

Strips: v03/extra/s30_hook_000.0.png r=0.925; v06/extra/s30_001.0_card.png r=0.929; v07/extra/s30_000.0_hook.png r=0.935

Energy alone (131 frames): moving share 6.9 percent, middle band 11.5 percent, pixels changing 0.5 percent, longest still 4 s, mean change 0.189

## chart-card: pass

| check | expected | measured | ok |
|---|---|---|---|
| enter: opacity frames | 5 frames | 5 | yes |
| enter: rise px | 38 px | 38 | yes |
| enter: position frames (fit) | 8 frames | 8 | yes |
| enter: ease | ease-out | expo.out | yes |
| grow: h growth frames (fit) | 12 frames | 12 | yes |
| stagger: gap frames between neighbours | 2 frames | [2] | yes |
| life: never static #cc | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #cc-bar-0 | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #cc-bar-1 | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #cc-bar-3 | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #cc-val-3 | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 0 | yes |
| life: inertia after the landing #cc | 2.0 to 4.0 s s (hold speed 9.21 px/s) | 2.83 | yes |

Strips: v04/extra/s30_bars_f1426.png r=0.978; v06/extra/s30_048.0_bars.png r=0.923

Energy alone (131 frames): moving share 13.8 percent, middle band 16.9 percent, pixels changing 0.55 percent, longest still 3.7 s, mean change 0.245

## chat-card: pass

| check | expected | measured | ok |
|---|---|---|---|
| enter: opacity frames | 5 frames | 5 | yes |
| enter: rise px | 38 px | 38 | yes |
| enter: position frames (fit) | 8 frames | 8 | yes |
| enter: ease | ease-out | expo.out | yes |
| typing: frames per character | 1.15 frames | 1.154 | yes |
| life: never static #chat | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #chat-input | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #chat-send | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 0 | yes |
| life: inertia after the landing #chat | 2.0 to 4.0 s s (hold speed 9.21 px/s) | 2.83 | yes |

Strips: v07/extra/s30_004.4_caption_tag.png r=0.922; v06/extra/s30_070.9_typing_tail.png r=0.954

Energy alone (131 frames): moving share 0.8 percent, middle band 13.1 percent, pixels changing 0.28 percent, longest still 4.07 s, mean change 0.134

## check-badge: pass

| check | expected | measured | ok |
|---|---|---|---|
| pop: overshoot | 0.13 to 0.16 ratio | 0.16 | yes |
| pop: frames to settle | 12 frames | 12 | yes |
| pop: opacity within 4 frames | <= 4 frames | 4 | yes |
| life: never static #cb-badge | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 87 | yes |
| | | WARN: the rendered frames show a still stretch (the DOM keeps moving; a subpixel hold) | |
| life: inertia after the landing #cb-badge | 2.0 to 4.0 s s (hold speed 4.74 px/s) | 2.07 | yes |

Strips: v07/extra/s30_035.6_checks.png r=0.843; v06/extra/s30_065.6_ticks.png r=0.891; v04/extra/s30_check_f1200.png r=0.98; v03/extra/s30_cta_058.0.png r=0.929

Energy alone (131 frames): moving share 0 percent, middle band 1.5 percent, pixels changing 0.03 percent, longest still 4.33 s, mean change 0.015

## dark-chip: pass

| check | expected | measured | ok |
|---|---|---|---|
| pop: overshoot | 0.01 to 0.03 ratio | 0.02 | yes |
| pop: frames to settle | 3 frames | 3 | yes |
| pop: opacity within 4 frames | <= 4 frames | 3 | yes |
| life: never static #chip | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 114 | yes |
| | | WARN: the rendered frames show a still stretch (the DOM keeps moving; a subpixel hold) | |
| life: inertia after the landing #chip | 2.0 to 4.0 s s (hold speed 5.11 px/s) | 2.53 | yes |

Strips: v01/extra/s30_sc05.png r=0.798; v07/extra/s30_004.4_caption_tag.png r=0.955

Energy alone (131 frames): moving share 0 percent, middle band 2.3 percent, pixels changing 0.02 percent, longest still 4.33 s, mean change 0.021

## dm-card: pass

| check | expected | measured | ok |
|---|---|---|---|
| enter: opacity frames | 5 frames | 5 | yes |
| enter: rise px | 38 px | 38 | yes |
| enter: position frames (fit) | 8 frames | 8 | yes |
| enter: ease | ease-out | expo.out | yes |
| life: never static #dm | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 0 | yes |
| life: inertia after the landing #dm | 2.0 to 4.0 s s (hold speed 8.96 px/s) | 2.83 | yes |

Strips: v03/extra/s30_hook_000.0.png r=0.908; v06/extra/s30_001.0_card.png r=0.871

Energy alone (131 frames): moving share 6.2 percent, middle band 13.1 percent, pixels changing 0.34 percent, longest still 4 s, mean change 0.144

## end-card: pass

| check | expected | measured | ok |
|---|---|---|---|
| fade: opacity frames | 6 frames | 5 | yes |
| stagger: gap frames between neighbours | 6 frames | [6, 6, 6] | yes |
| typing: frames per character | 2 frames | 2 | yes |
| life: never static #ec-card | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #ec-verb | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #ec-pill | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #ec-lines | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #ec-lockup | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #ec-mascot-0 | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 0 | yes |
| life: inertia after the landing #ec-card | 2.0 to 4.0 s s (hold speed 9.86 px/s) | 2.7 | yes |

Strips: v02/extra/s30_cta43.png r=0.925; v07/extra/s30_041.0_end.png r=0.947; v08/extra/s30_038.9_end.png r=0.975; v09/extra/s30_049.7_end.png r=0.97

Energy alone (131 frames): moving share 11.5 percent, middle band 13.8 percent, pixels changing 0.64 percent, longest still 3 s, mean change 0.249

## exit-move: pass

| check | expected | measured | ok |
|---|---|---|---|
| exit: frames (fit, ease-in) | 10 frames | 10 | yes |
| exit: leaves the frame | yes | yes | yes |
| enter: opacity frames | 5 frames | 5 | yes |
| enter: rise px | 38 px | 38 | yes |
| enter: position frames (fit) | 8 frames | 8 | yes |
| enter: ease | ease-out | expo.out | yes |
| life: never static #xm-leaving | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #xm-next | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 0 | yes |
| life: inertia after the landing #xm-next | 2.0 to 4.0 s s (hold speed 9.57 px/s) | 2.83 | yes |

Strips: v07/extra/s30_003.2_badge_exit.png r=0.95; v07/extra/s30_034.7_exit_counter.png r=0.967; v08/extra/s30_010.6_scatter.png r=0.932

Energy alone (131 frames): moving share 7.7 percent, middle band 9.2 percent, pixels changing 1.07 percent, longest still 3.2 s, mean change 0.34

## fly-in: pass

| check | expected | measured | ok |
|---|---|---|---|
| fly: distance y | 930 px | 930 | yes |
| fly: frames (fit) | 14 frames | 14 | yes |
| after: frames after the reference | 4 frames | 5 | yes |
| life: never static #fi | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #fi-mascot | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 0 | yes |
| life: inertia after the landing #fi | 2.0 to 4.0 s s (hold speed 9.03 px/s) | 2.63 | yes |

Strips: v08/extra/s30_000.0_hook.png r=0.976; v07/extra/s30_011.4_window_rise.png r=0.966; v01/extra/s30_hook.png r=0.982

Energy alone (131 frames): moving share 8.5 percent, middle band 8.5 percent, pixels changing 1.08 percent, longest still 3.97 s, mean change 0.459

## handwritten-callout: pass

| check | expected | measured | ok |
|---|---|---|---|
| fade: opacity frames | 6 frames | 6 | yes |
| life: never static #hc-wrap | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #hc-arrow | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 87 | yes |
| | | WARN: the rendered frames show a still stretch (the DOM keeps moving; a subpixel hold) | |
| life: inertia after the landing #hc-wrap | 2.0 to 4.0 s s (hold speed 5.42 px/s) | 2.43 | yes |

Energy alone (131 frames): moving share 0 percent, middle band 0 percent, pixels changing 0.02 percent, longest still 4.33 s, mean change 0.016

## headline: pass

| check | expected | measured | ok |
|---|---|---|---|
| visible_at_zero: visible at frame 0 | 1 | 1 | yes |
| stagger: gap frames between neighbours | 3 frames | [3, 3] | yes |
| fade: opacity frames | 3 frames | 3 | yes |
| life: never static #hl-kicker | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #hl-lines | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 17 | yes |
| | | WARN: the rendered frames show a still stretch (the DOM keeps moving; a subpixel hold) | |

Strips: v02/extra/s30_hook.png r=0.979; v01/extra/s30_hook.png r=0.99; v03/extra/s30_hook_000.0.png r=0.956

Energy alone (131 frames): moving share 0 percent, middle band 0 percent, pixels changing 0.08 percent, longest still 4.33 s, mean change 0.043

## hero-3d: pass

| check | expected | measured | ok |
|---|---|---|---|
| fade: opacity frames | 12 frames | 12 | yes |
| webgl: a WebGL context in the harness | yes | yes | yes |
| life: never static #h3-shadow | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #h3-label | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still (a canvas draws itself) | < 15 frames frames | 0 | yes |

Energy alone (131 frames): moving share 3.8 percent, middle band 14.6 percent, pixels changing 0.4 percent, longest still 3.93 s, mean change 0.186

## icon-3d: pass

| check | expected | measured | ok |
|---|---|---|---|
| fade: opacity frames | 12 frames | 12 | yes |
| webgl: a WebGL context in the harness | yes | yes | yes |
| life: never static #i3-shadow | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still (a canvas draws itself) | < 15 frames frames | 11 | yes |

Energy alone (131 frames): moving share 0 percent, middle band 3.8 percent, pixels changing 0.09 percent, longest still 4.33 s, mean change 0.044

## light-chip: pass

| check | expected | measured | ok |
|---|---|---|---|
| fade: opacity frames | 4 frames | 4 | yes |
| life: never static #lchip | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 62 | yes |
| | | WARN: the rendered frames show a still stretch (the DOM keeps moving; a subpixel hold) | |
| life: inertia after the landing #lchip | 2.0 to 4.0 s s (hold speed 4.92 px/s) | 2.5 | yes |

Strips: v03/extra/s30_label_042.4.png r=0.972

Energy alone (131 frames): moving share 0 percent, middle band 0 percent, pixels changing 0.02 percent, longest still 4.33 s, mean change 0.011

## logo-tile: pass

| check | expected | measured | ok |
|---|---|---|---|
| pop: overshoot | 0.13 to 0.16 ratio | 0.13 | yes |
| pop: frames to settle | 14 frames | 14 | yes |
| pop: opacity within 4 frames | <= 4 frames | 4 | yes |
| fly: distance x | 188 px | 188 | yes |
| fly: overshoot px | 6 px | 6 | yes |
| fly: frames to settle | 9 frames | 9 | yes |
| life: never static #lt-main | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #lt-second | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 67 | yes |
| | | WARN: the rendered frames show a still stretch (the DOM keeps moving; a subpixel hold) | |
| life: inertia after the landing #lt-main | 2.0 to 4.0 s s (hold speed 4.88 px/s) | 2.17 | yes |

Strips: v08/extra/s30_003.8_logo_chain.png r=0.873; v02/extra/s30_hook.png r=0.889

Energy alone (131 frames): moving share 0 percent, middle band 3.1 percent, pixels changing 0.07 percent, longest still 4.33 s, mean change 0.033

## mascot: pass

| check | expected | measured | ok |
|---|---|---|---|
| fade: opacity frames | 4 frames | 4 | yes |
| life: never static #ms-wrap | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 20 | yes |
| | | WARN: the rendered frames show a still stretch (the DOM keeps moving; a subpixel hold) | |
| life: inertia after the landing #ms-wrap | 2.0 to 4.0 s s (hold speed 5.43 px/s) | 2.5 | yes |

Strips: v02/extra/s30_hook.png r=0.936; v08/extra/s30_000.8_mascot_title.png r=0.988

Energy alone (131 frames): moving share 0 percent, middle band 1.5 percent, pixels changing 0.11 percent, longest still 4.33 s, mean change 0.036

## paper-canvas: pass

| check | expected | measured | ok |
|---|---|---|---|
| canvas: renders | no page errors | 0 | yes |
| canvas: the edge and ambient layers exist | elements | 7 | yes |
| life: never static #paper-edge-0 | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #paper-edge-1 | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #paper-edge-2 | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #paper-edge-3 | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #paper-ambient-0 | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #paper-ambient-1 | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #paper-ambient-2 | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 4 | yes |

Energy alone (131 frames): moving share 0 percent, middle band 0 percent, pixels changing 0.01 percent, longest still 4.33 s, mean change 0.023

## pop: pass

| check | expected | measured | ok |
|---|---|---|---|
| pop: overshoot | 0.13 to 0.16 ratio | 0.13 | yes |
| pop: frames to settle | 14 frames | 14 | yes |
| pop: opacity within 4 frames | <= 4 frames | 4 | yes |
| life: never static #pop-el | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 80 | yes |
| | | WARN: the rendered frames show a still stretch (the DOM keeps moving; a subpixel hold) | |
| life: inertia after the landing #pop-el | 2.0 to 4.0 s s (hold speed 4.88 px/s) | 2.17 | yes |

Strips: v08/extra/s30_003.8_logo_chain.png r=0.967; v03/extra/s30_cta_058.0.png r=0.992; v09/extra/s30_002.3_stickers.png r=0.641

Energy alone (131 frames): moving share 0 percent, middle band 0 percent, pixels changing 0.02 percent, longest still 4.33 s, mean change 0.009

## progress-bar: pass

| check | expected | measured | ok |
|---|---|---|---|
| enter: opacity frames | 5 frames | 5 | yes |
| enter: rise px | 38 px | 38 | yes |
| enter: position frames (fit) | 8 frames | 8 | yes |
| enter: ease | ease-out | expo.out | yes |
| grow: w growth frames (fit) | 6 frames | 6 | yes |
| pop: overshoot | 0.16 ratio | 0.16 | yes |
| pop: frames to settle | 3 frames | 3 | yes |
| pop: opacity within 4 frames | <= 4 frames | 3 | yes |
| life: never static #pb | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #pb-fill | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #pb-check | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 0 | yes |
| life: inertia after the landing #pb | 2.0 to 4.0 s s (hold speed 8.83 px/s) | 2.83 | yes |

Strips: v01/extra/s30_card33.png r=0.897

Energy alone (131 frames): moving share 0.8 percent, middle band 13.8 percent, pixels changing 0.27 percent, longest still 3.8 s, mean change 0.109

## speech-bubble: pass

| check | expected | measured | ok |
|---|---|---|---|
| bubble: overshoot y px | 40 px | 41 | yes |
| bubble: frames to the peak | 7 frames | 7 | yes |
| bubble: settle frames after the peak | 9 frames | 8 | yes |
| pop: overshoot | 0.01 to 0.03 ratio | 0.02 | yes |
| pop: frames to settle | 7 frames | 7 | yes |
| pop: opacity within 4 frames | <= 4 frames | 4 | yes |
| life: never static #sb | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #sb-pill | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 8 | yes |

Strips: v07/extra/s30_041.0_end.png r=0.926; v08/extra/s30_038.9_end.png r=0.987

Energy alone (131 frames): moving share 3.8 percent, middle band 20 percent, pixels changing 0.29 percent, longest still 3.87 s, mean change 0.125

## stat-number: pass

| check | expected | measured | ok |
|---|---|---|---|
| enter: opacity frames | 5 frames | 5 | yes |
| enter: rise px | 38 px | 38 | yes |
| enter: position frames (fit) | 8 frames | 8 | yes |
| enter: ease | ease-out | expo.out | yes |
| count: frames to the final value | 27.5 frames | 27 | yes |
| life: never static #stat-wrap | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #stat-num | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 0 | yes |
| life: inertia after the landing #stat-wrap | 2.0 to 4.0 s s (hold speed 8.6 px/s) | 2.83 | yes |

Strips: v08/extra/s30_007.8_countup.png r=0.93; v03/extra/s30_count_044.9.png r=0.932; v04/extra/s30_count_f925.png r=0.945

Energy alone (131 frames): moving share 14.6 percent, middle band 23.8 percent, pixels changing 0.32 percent, longest still 3.23 s, mean change 0.205

## strike-through: pass

| check | expected | measured | ok |
|---|---|---|---|
| grow: w growth frames (fit) | 4 frames | 4 | yes |
| typing: frames per character | 2 frames | 2 | yes |
| life: never static #st-text | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 80 | yes |
| | | WARN: the rendered frames show a still stretch (the DOM keeps moving; a subpixel hold) | |
| life: inertia after the landing #st-text | 2.0 to 4.0 s s (hold speed 4.02 px/s) | 1.87 | yes |

Strips: v04/extra/s30_strike_f1007.png r=0.961; v06/extra/s30_062.3_xstamp.png r=0.966

Energy alone (131 frames): moving share 0 percent, middle band 0 percent, pixels changing 0.02 percent, longest still 4.33 s, mean change 0.012

## table-card: pass

| check | expected | measured | ok |
|---|---|---|---|
| enter: opacity frames | 5 frames | 5 | yes |
| enter: rise px | 28 px | 28 | yes |
| enter: position frames (fit) | 7 frames | 7 | yes |
| enter: ease | ease-out | expo.out | yes |
| stagger: gap frames between neighbours | 3 frames | [3] | yes |
| life: never static #tb | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #tb-row-0 | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #tb-row-1 | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 0 | yes |
| life: inertia after the landing #tb | 2.0 to 4.0 s s (hold speed 9.21 px/s) | 2.87 | yes |

Strips: v04/extra/s30_scene_f184.png r=0.972

Energy alone (131 frames): moving share 8.5 percent, middle band 11.5 percent, pixels changing 0.51 percent, longest still 3.9 s, mean change 0.22

## terminal-card: pass

| check | expected | measured | ok |
|---|---|---|---|
| enter: opacity frames | 5 frames | 5 | yes |
| enter: rise px | 38 px | 38 | yes |
| enter: position frames (fit) | 8 frames | 8 | yes |
| enter: ease | ease-out | expo.out | yes |
| typing: frames per character | 0.5 frames | 0.491 | yes |
| life: never static #tc | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #tc-line-0 | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 0 | yes |
| life: inertia after the landing #tc | 2.0 to 4.0 s s (hold speed 9.21 px/s) | 2.83 | yes |

Strips: v04/extra/s30_rewrite_f982.png r=0.777; v06/extra/s30_070.9_typing_tail.png r=0.959

Energy alone (131 frames): moving share 10 percent, middle band 10.8 percent, pixels changing 0.76 percent, longest still 3.03 s, mean change 0.356

## thumb-grid: pass

| check | expected | measured | ok |
|---|---|---|---|
| fade: opacity frames | 4 frames | 4 | yes |
| stagger: gap frames between neighbours | 1 frames | [1, 1] | yes |
| stagger: gap frames between neighbours | 7 frames | [7] | yes |
| life: never static #tg-wrap | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #tg-card-0 | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #tg-card-1 | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #tg-card-2 | 0 still windows of 0.5 s windows | 0 | yes |
| life: never static #tg-card-3 | 0 still windows of 0.5 s windows | 0 | yes |
| life: pixels never still | < 15 frames frames | 0 | yes |

Strips: v02/extra/s30_grid34.png r=0.889; v04/extra/s30_deckgrid_f420.png r=0.984; v04/extra/s30_gridsettle_f444.png r=0.945

Energy alone (131 frames): moving share 5.4 percent, middle band 13.8 percent, pixels changing 0.22 percent, longest still 3.97 s, mean change 0.156

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

Strips: v07/extra/s30_011.4_window_rise.png r=0.956; v01/extra/s30_hook.png r=0.94; v03/extra/s30_hook_000.0.png r=0.915

Energy alone (131 frames): moving share 20.8 percent, middle band 100 percent, pixels changing 1.93 percent, longest still 3.1 s, mean change 0.584

