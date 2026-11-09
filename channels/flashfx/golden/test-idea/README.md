# Golden reel: c26c94b17281

The example reel the visual director (S9) reads: plan.json is the merged visual plan (pipeline/stages/09-plan/schema.json), project/ the HyperFrames project built from it by pipeline/lib/motion/golden.py, golden.mp4 the render (ignored by git, rebuilt by `bash pipeline/bin/render-golden`), contact-sheet.png one still per scene.

- Duration: 41460 ms, 11 scenes, 27 component instances, 39 caption chunks
- Solution: external (frontend-design, the Claude Code plugin); branding: the CTA scene s11 carries the DM card (brand/mark/avatar-dark.png) and the lockup (brand/lockup/lockup-gradient-on-light.png); brand slot: None
- Render: 1080x1920 at 30.0 fps, 41.47 s, audio aac 48000 Hz (the render time is in render.json)
- HyperFrames check: ok, runtime warnings 1, contrast warnings 5, craft warnings 2

## Scenes

| scene | beat | type | start | end | components |
|---|---|---|---|---|---|
| s1 | b1 | hook | 0.00 s | 3.46 s | headline (s1-headline-1), mock-site-card (s1-mock-site-card-2), hero-3d (s1-hero-3d-3) |
| s2 | b2 | stake | 3.46 s | 6.64 s | mock-site-card (s2-mock-site-card-1), pop (s2-pop-2), cursor (s2-cursor-3), dark-chip (s2-dark-chip-4) |
| s3 | b3 | comparison | 6.64 s | 11.39 s | screenshot-zoom (s3-screenshot-zoom-1), pop (s3-pop-2), dark-chip (s3-dark-chip-3) |
| s4 | b4 | mechanism | 11.39 s | 15.13 s | video-card (s4-video-card-1), handwritten-callout (s4-handwritten-callout-2) |
| s5 | b5 | comparison | 15.13 s | 18.86 s | mock-site-card (s5-mock-site-card-1), swatch-row (s5-swatch-row-2), strike-through (s5-strike-through-3) |
| s6 | b6 | number | 18.86 s | 22.73 s | video-card (s6-video-card-1), pop (s6-pop-2) |
| s7 | b7 | mechanism | 22.73 s | 26.89 s | video-card (s7-video-card-1), swatch-row (s7-swatch-row-2) |
| s8 | b8 | proof | 26.89 s | 30.11 s | screenshot-zoom (s8-screenshot-zoom-1), stat-number (s8-stat-number-2) |
| s9 | b9 | step | 30.11 s | 34.74 s | terminal-card (s9-terminal-card-1), video-card (s9-video-card-2) |
| s10 | b10 | payoff | 34.74 s | 37.73 s | video-card (s10-video-card-1), check-badge (s10-check-badge-2) |
| s11 | b11 | ask | 37.73 s | 41.46 s | end-card (s11-end-card-1), dm-card (s11-dm-card-2) |

## Transitions

- s1 to s2: fade-blur (133 ms)
- s2 to s3: fall (333 ms)
- s3 to s4: push (267 ms)
- s4 to s5: fade-blur (133 ms)
- s5 to s6: fall (333 ms)
- s6 to s7: cut (0 ms)
- s7 to s8: push (267 ms)
- s8 to s9: fade-blur (133 ms)
- s9 to s10: push (267 ms)
- s10 to s11: fall (333 ms)

## Notes

Planned by hand for the test idea (goldenplan.py DESIGN): the hook headline builds word by word on the spoken words and the 3D card lands in the breath; every body beat has one hero component and one element landing on its key word; the screenshots are real research assets (labelled real); the CTA follows tweaks.md Branding: the FlashFX DM card lands on the word TELLS and the lockup sits under the mascot row. Scene changes: fade-blur by default, a fall or a push where the beat turns (open question 3: B).
