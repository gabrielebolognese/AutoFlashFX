# Things the build needs from you

Each line: milestone, what to do, where.

- M0: Read PLAN.md and DECISIONS.md. The build continues without you; if you disagree with a choice, edit BUILD_SPEC.md or DECISIONS.md and restart the affected milestone with `bash build-runner.sh --from M<n>`.
- M0: Exclude the instagramReels folder from OneDrive sync (or move the folder out of OneDrive): runs/ and exports/ will hold gigabytes of renders, and OneDrive file locks can break the runner's atomic renames.
- M0: Decide the PROPOSED lines in styles/paper-cards/tweaks.md (delete the word PROPOSED on the ones you accept) before M9 if you can; otherwise M9 applies the defaults in DECISIONS.md item 32.
- M0: hooks.txt has em dashes on lines 43, 64, 73 and 80, and lines 53 and 54 lost their `__` blank. The build never edits this file; fix them yourself whenever you like (the hooks lint in M5 will list them again).
- M0: When you can, record library/voice/reference.wav (10 to 30 s of clean speech at reel energy) and library/voice/memo.* (a 5 to 10 minute voice memo). Until then the pipeline uses the kokoro stock voice and a placeholder voice.md.
