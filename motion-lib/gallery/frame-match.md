# frame-match: the library components against the style's numbers and the reference strips

Run 2026-11-01 18:07 by pipeline/bin/frame-match. Tolerances: 1 frame on timings, 10 percent on distances and overshoots; a reference strip must correlate at r >= 0.5 (DECISIONS.md 29). Numbers: styles/paper-cards/vocabulary.md and style.md through tokens.json; strips: styles/paper-cards/analysis/<vXX>/extra/s30_*.png.

**27 pass, 0 fail** of 27 components.

| component | result | checks | best strip | r |
|---|---|---|---|---|
| camera-move | pass | 2/2 | v05/extra/s30_windowshrink_f520.png | 0.641 |
| caption-line | pass | 4/4 | v06/extra/s30_031.0_highlight.png | 0.96 |
| card | pass | 6/6 | v03/extra/s30_hook_000.0.png | 0.911 |
| chart-card | pass | 6/6 | v04/extra/s30_bars_f1426.png | 0.983 |
| chat-card | pass | 5/5 | v06/extra/s30_070.9_typing_tail.png | 0.972 |
| check-badge | pass | 3/3 | v04/extra/s30_check_f1200.png | 0.979 |
| dark-chip | pass | 3/3 | v07/extra/s30_004.4_caption_tag.png | 0.69 |
| dm-card | pass | 4/4 | v03/extra/s30_hook_000.0.png | 0.916 |
| end-card | pass | 3/3 | v09/extra/s30_049.7_end.png | 0.959 |
| exit-move | pass | 6/6 | v07/extra/s30_003.2_badge_exit.png | 0.992 |
| fly-in | pass | 3/3 | v08/extra/s30_000.0_hook.png | 0.958 |
| handwritten-callout | pass | 1/1 | none | none |
| headline | pass | 3/3 | v02/extra/s30_hook.png | 0.929 |
| hero-3d | pass | 2/2 | none | none |
| light-chip | pass | 1/1 | v03/extra/s30_label_042.4.png | 0.937 |
| logo-tile | pass | 6/6 | v08/extra/s30_003.8_logo_chain.png | 0.934 |
| mascot | pass | 1/1 | v08/extra/s30_000.8_mascot_title.png | 0.975 |
| paper-canvas | pass | 1/1 | none | none |
| pop | pass | 3/3 | v08/extra/s30_003.8_logo_chain.png | 0.957 |
| progress-bar | pass | 8/8 | v01/extra/s30_card33.png | 0.965 |
| speech-bubble | pass | 6/6 | v07/extra/s30_041.0_end.png | 0.931 |
| stat-number | pass | 5/5 | v03/extra/s30_count_044.9.png | 0.57 |
| strike-through | pass | 2/2 | v04/extra/s30_strike_f1007.png | 0.977 |
| table-card | pass | 5/5 | v04/extra/s30_scene_f184.png | 0.975 |
| terminal-card | pass | 5/5 | v06/extra/s30_070.9_typing_tail.png | 0.96 |
| thumb-grid | pass | 3/3 | v04/extra/s30_gridsettle_f444.png | 0.746 |
| window-card | pass | 5/5 | v07/extra/s30_011.4_window_rise.png | 0.976 |

## camera-move: pass

| check | expected | measured | ok |
|---|---|---|---|
| shrink: end scale | 0.458 ratio | 0.458 | yes |
| shrink: frames (fit) | 8 frames | 8 | yes |

Strips: v02/extra/s30_zoom27.png r=0.488; v05/extra/s30_windowshrink_f520.png r=0.641

## caption-line: pass

| check | expected | measured | ok |
|---|---|---|---|
| fade: opacity frames | 4 frames | 4 | yes |
| fade: opacity frames | 4 frames | 4 | yes |
| exit: frames to fade out | 2 frames | 3 | yes |
| after: frames after the reference | 1 frames | 2 | yes |

Strips: v03/extra/s30_capswap_008.0.png r=0.75; v01/extra/s30_sc18.png r=0.102; v06/extra/s30_031.0_highlight.png r=0.96

## card: pass

| check | expected | measured | ok |
|---|---|---|---|
| enter: opacity frames | 5 frames | 5 | yes |
| enter: rise px | 38 px | 38 | yes |
| enter: position frames (fit) | 8 frames | 8 | yes |
| enter: ease | ease-out | expo.out | yes |
| after: frames after the reference | 4 frames | 4 | yes |
| fade: opacity frames | 4 frames | 4 | yes |

Strips: v03/extra/s30_hook_000.0.png r=0.911; v06/extra/s30_001.0_card.png r=0.437; v07/extra/s30_000.0_hook.png r=-0.004

## chart-card: pass

| check | expected | measured | ok |
|---|---|---|---|
| enter: opacity frames | 5 frames | 5 | yes |
| enter: rise px | 38 px | 38 | yes |
| enter: position frames (fit) | 8 frames | 8 | yes |
| enter: ease | ease-out | expo.out | yes |
| grow: h growth frames (fit) | 12 frames | 12 | yes |
| stagger: gap frames between neighbours | 2 frames | [2] | yes |

Strips: v04/extra/s30_bars_f1426.png r=0.983; v06/extra/s30_048.0_bars.png r=0.96

## chat-card: pass

| check | expected | measured | ok |
|---|---|---|---|
| enter: opacity frames | 5 frames | 5 | yes |
| enter: rise px | 38 px | 38 | yes |
| enter: position frames (fit) | 8 frames | 8 | yes |
| enter: ease | ease-out | expo.out | yes |
| typing: frames per character | 1.15 frames | 1.154 | yes |

Strips: v07/extra/s30_004.4_caption_tag.png r=0.003; v06/extra/s30_070.9_typing_tail.png r=0.972

## check-badge: pass

| check | expected | measured | ok |
|---|---|---|---|
| pop: overshoot | 0.13 to 0.16 ratio | 0.16 | yes |
| pop: frames to settle | 12 frames | 12 | yes |
| pop: opacity within 4 frames | <= 4 frames | 4 | yes |

Strips: v07/extra/s30_035.6_checks.png r=0.733; v06/extra/s30_065.6_ticks.png r=0.886; v04/extra/s30_check_f1200.png r=0.979; v03/extra/s30_cta_058.0.png r=0.93

## dark-chip: pass

| check | expected | measured | ok |
|---|---|---|---|
| pop: overshoot | 0.01 to 0.03 ratio | 0.02 | yes |
| pop: frames to settle | 3 frames | 3 | yes |
| pop: opacity within 4 frames | <= 4 frames | 3 | yes |

Strips: v01/extra/s30_sc05.png r=0.116; v07/extra/s30_004.4_caption_tag.png r=0.69

## dm-card: pass

| check | expected | measured | ok |
|---|---|---|---|
| enter: opacity frames | 5 frames | 5 | yes |
| enter: rise px | 38 px | 38 | yes |
| enter: position frames (fit) | 8 frames | 8 | yes |
| enter: ease | ease-out | expo.out | yes |

Strips: v03/extra/s30_hook_000.0.png r=0.916; v06/extra/s30_001.0_card.png r=0.418

## end-card: pass

| check | expected | measured | ok |
|---|---|---|---|
| fade: opacity frames | 6 frames | 5 | yes |
| stagger: gap frames between neighbours | 6 frames | [6, 6, 6] | yes |
| typing: frames per character | 2 frames | 2 | yes |

Strips: v02/extra/s30_cta43.png r=0.627; v07/extra/s30_041.0_end.png r=0.165; v08/extra/s30_038.9_end.png r=0.905; v09/extra/s30_049.7_end.png r=0.959

## exit-move: pass

| check | expected | measured | ok |
|---|---|---|---|
| exit: frames (fit, ease-in) | 10 frames | 10 | yes |
| exit: leaves the frame | yes | yes | yes |
| enter: opacity frames | 5 frames | 5 | yes |
| enter: rise px | 38 px | 38 | yes |
| enter: position frames (fit) | 8 frames | 8 | yes |
| enter: ease | ease-out | expo.out | yes |

Strips: v07/extra/s30_003.2_badge_exit.png r=0.992; v07/extra/s30_034.7_exit_counter.png r=0.76; v08/extra/s30_010.6_scatter.png r=0.873

## fly-in: pass

| check | expected | measured | ok |
|---|---|---|---|
| fly: distance y | 930 px | 899.7 | yes |
| fly: frames (fit) | 14 frames | 14 | yes |
| after: frames after the reference | 4 frames | 4 | yes |

Strips: v08/extra/s30_000.0_hook.png r=0.958; v07/extra/s30_011.4_window_rise.png r=0.921; v01/extra/s30_hook.png r=0.957

## handwritten-callout: pass

| check | expected | measured | ok |
|---|---|---|---|
| fade: opacity frames | 6 frames | 6 | yes |

## headline: pass

| check | expected | measured | ok |
|---|---|---|---|
| visible_at_zero: visible at frame 0 | 1 | 1 | yes |
| stagger: gap frames between neighbours | 3 frames | [3, 3] | yes |
| fade: opacity frames | 3 frames | 3 | yes |

Strips: v02/extra/s30_hook.png r=0.929; v01/extra/s30_hook.png r=0.838; v03/extra/s30_hook_000.0.png r=0.545

## hero-3d: pass

| check | expected | measured | ok |
|---|---|---|---|
| fade: opacity frames | 12 frames | 12 | yes |
| webgl: a WebGL context in the harness | yes | yes | yes |

## light-chip: pass

| check | expected | measured | ok |
|---|---|---|---|
| fade: opacity frames | 4 frames | 4 | yes |

Strips: v03/extra/s30_label_042.4.png r=0.937

## logo-tile: pass

| check | expected | measured | ok |
|---|---|---|---|
| pop: overshoot | 0.13 to 0.16 ratio | 0.13 | yes |
| pop: frames to settle | 14 frames | 14 | yes |
| pop: opacity within 4 frames | <= 4 frames | 4 | yes |
| fly: distance x | 188 px | 188 | yes |
| fly: overshoot px | 6 px | 6 | yes |
| fly: frames to settle | 9 frames | 9 | yes |

Strips: v08/extra/s30_003.8_logo_chain.png r=0.934; v02/extra/s30_hook.png r=0.634

## mascot: pass

| check | expected | measured | ok |
|---|---|---|---|
| fade: opacity frames | 4 frames | 4 | yes |

Strips: v02/extra/s30_hook.png r=0.496; v08/extra/s30_000.8_mascot_title.png r=0.975

## paper-canvas: pass

| check | expected | measured | ok |
|---|---|---|---|
| static: renders | no page errors | 0 | yes |

## pop: pass

| check | expected | measured | ok |
|---|---|---|---|
| pop: overshoot | 0.13 to 0.16 ratio | 0.13 | yes |
| pop: frames to settle | 14 frames | 14 | yes |
| pop: opacity within 4 frames | <= 4 frames | 4 | yes |

Strips: v08/extra/s30_003.8_logo_chain.png r=0.957; v03/extra/s30_cta_058.0.png r=0.888; v09/extra/s30_002.3_stickers.png r=0.464

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

Strips: v01/extra/s30_card33.png r=0.965

## speech-bubble: pass

| check | expected | measured | ok |
|---|---|---|---|
| bubble: overshoot y px | 40 px | 40 | yes |
| bubble: frames to the peak | 7 frames | 7 | yes |
| bubble: settle frames after the peak | 9 frames | 8 | yes |
| pop: overshoot | 0.01 to 0.03 ratio | 0.02 | yes |
| pop: frames to settle | 7 frames | 7 | yes |
| pop: opacity within 4 frames | <= 4 frames | 4 | yes |

Strips: v07/extra/s30_041.0_end.png r=0.931; v08/extra/s30_038.9_end.png r=0.302

## stat-number: pass

| check | expected | measured | ok |
|---|---|---|---|
| enter: opacity frames | 5 frames | 5 | yes |
| enter: rise px | 38 px | 38 | yes |
| enter: position frames (fit) | 8 frames | 8 | yes |
| enter: ease | ease-out | expo.out | yes |
| count: frames to the final value | 27.5 frames | 27 | yes |

Strips: v08/extra/s30_007.8_countup.png r=0.467; v03/extra/s30_count_044.9.png r=0.57; v04/extra/s30_count_f925.png r=0.567

## strike-through: pass

| check | expected | measured | ok |
|---|---|---|---|
| grow: w growth frames (fit) | 4 frames | 4 | yes |
| typing: frames per character | 2 frames | 2 | yes |

Strips: v04/extra/s30_strike_f1007.png r=0.977; v06/extra/s30_062.3_xstamp.png r=0.939

## table-card: pass

| check | expected | measured | ok |
|---|---|---|---|
| enter: opacity frames | 5 frames | 5 | yes |
| enter: rise px | 28 px | 28 | yes |
| enter: position frames (fit) | 7 frames | 7 | yes |
| enter: ease | ease-out | expo.out | yes |
| stagger: gap frames between neighbours | 3 frames | [3] | yes |

Strips: v04/extra/s30_scene_f184.png r=0.975

## terminal-card: pass

| check | expected | measured | ok |
|---|---|---|---|
| enter: opacity frames | 5 frames | 5 | yes |
| enter: rise px | 38 px | 38 | yes |
| enter: position frames (fit) | 8 frames | 8 | yes |
| enter: ease | ease-out | expo.out | yes |
| typing: frames per character | 0.5 frames | 0.491 | yes |

Strips: v04/extra/s30_rewrite_f982.png r=0.02; v06/extra/s30_070.9_typing_tail.png r=0.96

## thumb-grid: pass

| check | expected | measured | ok |
|---|---|---|---|
| fade: opacity frames | 4 frames | 4 | yes |
| stagger: gap frames between neighbours | 1 frames | [1, 1] | yes |
| stagger: gap frames between neighbours | 7 frames | [7] | yes |

Strips: v02/extra/s30_grid34.png r=0.171; v04/extra/s30_deckgrid_f420.png r=0.409; v04/extra/s30_gridsettle_f444.png r=0.746

## window-card: pass

| check | expected | measured | ok |
|---|---|---|---|
| enter: opacity frames | 5 frames | 5 | yes |
| enter: rise px | 38 px | 38 | yes |
| enter: position frames (fit) | 8 frames | 8 | yes |
| enter: ease | ease-out | expo.out | yes |
| after: frames after the reference | 4 frames | 4 | yes |

Strips: v07/extra/s30_011.4_window_rise.png r=0.976; v01/extra/s30_hook.png r=0.892; v03/extra/s30_hook_000.0.png r=0.912

