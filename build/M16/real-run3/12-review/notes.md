# Review notes, round 3: fix

Scores (1 to 5, 4 passes): stop 3, hierarchy 3, look 4, variety 3, sync 3, sound 3, generic 3, requirements 3, energy 3

The editor's summary: The paper-cards look is mostly on target, and several moments land well: the real GitHub screenshot zoom, the dark "Bold by design" site, the 1,134,112 installs pill and the handwritten "safest choices" callout. But almost every scene change goes through blank paper frames, frame 1 is a ghosted half-built screen, the terminal never shows the install command, and the share line's tells only appear as one-word captions. Fix the transitions so no frame is empty, then type the real command in s7, label the tells in s3 and show LINK clearly on the end-card.

- [animation] scene s1 (hook, 0.0 to 3.3 s) lacks energy: moving share 21.6% (at least 32.8%), pixels changing 2.22% (at least 2.64%), still stretches 47.4% (at most 18.75%); more of the frames must carry real motion (a recording or a clip playing in a card, a camera move, a fan or a grid building, a count or typing)
- [animation] scene s3 (comparison, 6.8 to 12.1 s) lacks energy: moving share 32.5% (at least 32.8%), middle band 36.3% (at least 36.8%), pixels changing 1.48% (at least 2.64%); more of the frames must carry real motion (a recording or a clip playing in a card, a camera move, a fan or a grid building, a count or typing)
- [animation] scene s4 (mechanism, 12.1 to 16.0 s) lacks energy: middle band 30.3% (at least 36.8%); the middle of the screen must move: put the moving content (a recording, a zoom over a page, a stack) in the hero zone
- [animation] scene s6 (mechanism, 19.4 to 23.8 s) lacks energy: moving share 30.5% (at least 32.8%), middle band 30.5% (at least 36.8%), pixels changing 1.11% (at least 2.64%); more of the frames must carry real motion (a recording or a clip playing in a card, a camera move, a fan or a grid building, a count or typing)
- [animation] scene s7 (step, 23.8 to 27.4 s) lacks energy: pixels changing 2.3% (at least 2.64%), still stretches 43.6% (at most 18.75%); more of the picture must change from frame to frame: a bigger moving card, a second moving layer, content that plays inside the card
- [animation] scene s10 (payoff, 34.4 to 38.2 s) lacks energy: pixels changing 1.72% (at least 2.64%); more of the picture must change from frame to frame: a bigger moving card, a second moving layer, content that plays inside the card
- [animation] "AI slop" (s4-card-fan-1) and "Safe colors" (s4-card-fan-1) overlap at 12.67s (beat b4 (mechanism) settled)
- [animation] text "claude.com/blog" (window-card s4-window-card-2, scene s4, 15.00s) starts at y 223, above the safe top 230
- [animation] text "Claude Code" (terminal-card s7-terminal-card-1, scene s7, 27.39s) runs x -1076..-906, outside the 60 px side margins
- [animation] text "Claude Code" (terminal-card s7-terminal-card-1, scene s7, 27.39s) is off the canvas (x -1076..-906, y 584..622)
- [animation] text "$" (terminal-card s7-terminal-card-1, scene s7, 27.39s) runs x -1171..-1138, outside the 60 px side margins
- [animation] text "$" (terminal-card s7-terminal-card-1, scene s7, 27.39s) is off the canvas (x -1171..-1138, y 675..713)
- [animation] text "illustrative" (terminal-card s7-terminal-card-1, scene s7, 27.39s) runs x -501..-340, outside the 60 px side margins
- [animation] text "illustrative" (terminal-card s7-terminal-card-1, scene s7, 27.39s) is off the canvas (x -501..-340, y 663..691)
- [animation] text "one command" (light-chip s7-light-chip-3, scene s7, 27.39s) runs x -1155..-952, outside the 60 px side margins
- [animation] text "one command" (light-chip s7-light-chip-3, scene s7, 27.39s) is off the canvas (x -1155..-952, y 496..533)
- [animation] text "illustrative" (card-grid s7-card-grid-5, scene s7, 27.39s) runs x -483..-326, outside the 60 px side margins
- [animation] text "illustrative" (card-grid s7-card-grid-5, scene s7, 27.39s) is off the canvas (x -483..-326, y 865..891)
- [animation] text "installs" (stat-number s9-stat-number-2, scene s9, 33.00s) reaches x 878 in the lower half: the right 230 px are Instagram's buttons
- [animation] text "real" (stat-number s9-stat-number-2, scene s9, 33.00s) reaches x 884 in the lower half: the right 230 px are Instagram's buttons
- [text] the emphasis on "verified" at 31.14s (scene s9) has no accent box in the caption line
- [transition] At almost every scene change (3.2, 6.8, 12.0, 16.0, 19.4, 27.4, 30.7, 34.4, 38.2 to 38.4 s) the outgoing scene disappears and one or more frames of empty paper show before the next card arrives; overlap the out and in moves so the incoming hero is already on screen as the outgoing one leaves.
- [animation] The terminal-card stays at a bare "$" from 24.0 to 27.3 s while the voice says "You'll type one command", so the install command (the how-to-install half of the idea) is never shown; type the real /plugin install command into the terminal starting at "type" and keep it readable until the scope pick.
- [animation] Frame 1 (0.0 s) is a ghosted grey "Claude" and a faint translucent card, and the on-screen hook "NOT YOUR FAULT. IT'S DEFAULTS" only shows as a tiny eyebrow label; open on the full-opacity card-fan already in place and make "IT'S DEFAULTS" a big kinetic caption group under the headline by 2.0 s.
- [animation] The hero-3d at 2.2 s is just a small doc card sliding onto the fan's right corner, too small to read as the hook's payoff; scale it up into the middle of the frame or tilt it toward the camera so the hook_hit lands on a real move.
- [animation] The yourbrand.com mock-site-card arrives empty and stays a blank white panel from 3.3 to about 3.9 s; land it with the generic site content already filled in so the "everyone's" problem reads at once.
- [animation] s3 rebuilds the same yourbrand.com card from blank at 6.9 s and re-types "Your brand, live", repeating s2; carry the filled card over and spend s3 zooming onto the cream background, the terracotta button, the rounded cards and the FEATURES label as each is named.
- [text] The share line tells (cream background, terracotta accent, identical rounded cards, ALL-CAPS eyebrow labels) only exist as one-word captions, with no labelled swatches or callouts on screen from 6.8 to 12.1 s; add short labels "cream", "terracotta", "same cards", "CAPS labels" pinned to each part of the mock site as it is spoken.
- [animation] s10 repeats the s6 swatch-row move (empty white bars filling from the bottom under a title card), so the payoff looks like a rerun; change it to a before and after flip of the yourbrand.com card from cream to the bold palette.
- [animation] A cursor drifts aimlessly in s1 to s8 without clicking anything that matters, and every card carries an "ILLUSTRATIVE" tag, which clutters the frame; keep the cursor only where it clicks (the s7 scope pick) and make the tag smaller and only on the first mock card.
- [animation] At 19.3 s the falling GitHub card drops right over the "plugin." caption, and the two collide for a frame; fade the caption first or drop the card behind it.
- [animation] The voice says "Anthropic verified badge" at 30.8 s but no badge is highlighted on the screenshot; zoom onto the verified mark at "verified" before the install count rises.
- [animation] Up to 38.8 s the end-card shows only "Comment" and an empty orange pill, and LINK and the lockup are not visible yet; put "LINK" in the pill when the voice says it (about 38.6 s) and bring in the FlashFX lockup by 39.5 s so the keyword holds for at least 1.5 s.
- [sfx] The two typing sounds are trimmed to about 66 ms and 0 ms (one at +42.4 dB) so the typing is inaudible or clicks; use one typing bed from 24.1 s across the whole command typing, at a normal gain under the voice.
- [sfx] A cash-register kaching on the DM card at 38.7 s sounds like a sale and pushes the ad feel; replace it with a soft message notification.
- [sfx] The transitions at 27.4 s (push), 34.4 s (fall) and 38.2 s (fade-blur) have no whoosh while the others do; add matching fast or slow whooshes so the scene changes sound consistent.
- [sfx] The s6 and s8 check-badges use a discord notification while s7 and s10 use a ding; use the same ding for every checkmark and save notification sounds for the DM card.
