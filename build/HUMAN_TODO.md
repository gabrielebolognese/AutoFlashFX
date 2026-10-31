# Things the build needs from you

Each line: milestone, what to do, where.

- M0: Read PLAN.md and DECISIONS.md. The build continues without you; if you disagree with a choice, edit BUILD_SPEC.md or DECISIONS.md and restart the affected milestone with `bash build-runner.sh --from M<n>`.
- M0: Exclude the instagramReels folder from OneDrive sync (or move the folder out of OneDrive): runs/ and exports/ will hold gigabytes of renders, and OneDrive file locks can break the runner's atomic renames.
- M0: Decide the PROPOSED lines in styles/paper-cards/tweaks.md (delete the word PROPOSED on the ones you accept) before M9 if you can; otherwise M9 applies the defaults in DECISIONS.md item 32.
- M0: hooks.txt has em dashes on lines 43, 64, 73 and 80, and lines 53 and 54 lost their `__` blank. The build never edits this file; fix them yourself whenever you like (the hooks lint in M5 will list them again).
- M0: When you can, record library/voice/reference.wav (10 to 30 s of clean speech at reel energy) and library/voice/memo.* (a 5 to 10 minute voice memo). Until then the pipeline uses the kokoro stock voice and a placeholder voice.md.
- M1: Fill library/profile/deliverables.txt (one line per comment keyword: `KEYWORD | what they get | link`, or `to create`) and library/profile/pronunciations.txt (`word = how to say it`). The formats are in the file headers. Until then every reel's keyword deliverable is marked NEW and the voice uses default pronunciations.
- M1: From now on add ideas with `bash pipeline/bin/add-idea.sh "{your idea}"` or by pasting braces into a Claude Code session in this folder. Editing ideas.txt by hand is fine while the runner is stopped; while it runs, the script's lock avoids racing its rewrite.
- M2: Nothing required. Know that `bash run.sh` stops with logs/STOPPED.md until the real stages exist (M4 to M12); `REELS_DUMMY=all bash run.sh --once` shows the loop and the terminal lines with dummy stages (it removes the processed ideas from ideas.txt and writes dummy files into exports/, so run it on a copy or re-add the idea afterwards). Blocked ideas appear in logs/blocked.txt as a comment line plus the idea in braces: paste the braces into a Claude Code session or add-idea.sh to retry.
