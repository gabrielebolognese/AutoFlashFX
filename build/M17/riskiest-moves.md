# The riskiest moves (M17)

Ranked by the bytes git cannot restore, the files, and mixed git state. From move-manifest.tsv.

1. `styles` -> `channels/flashfx/styles` (git-mv, 1167 files, 392.2 MB; M18): 392.0 MB of files git does not hold (only the undo script can bring them back); tracked and ignored files in one folder (git mv carries both; git check-ignore must pass at the new path); 1167 files
2. `motion-lib` -> `channels/flashfx/motion-lib` (git-mv, 5409 files, 79.6 MB; M18): 69.3 MB of files git does not hold (only the undo script can bring them back); tracked and ignored files in one folder (git mv carries both; git check-ignore must pass at the new path); 5409 files
3. `golden` -> `channels/flashfx/golden` (git-mv, 82 files, 40.4 MB; M18): 38.8 MB of files git does not hold (only the undo script can bring them back); tracked and ignored files in one folder (git mv carries both; git check-ignore must pass at the new path)
4. `library` -> `channels/flashfx/library` (git-mv, 43 files, 10.3 MB; M18): 8.3 MB of files git does not hold (only the undo script can bring them back); tracked and ignored files in one folder (git mv carries both; git check-ignore must pass at the new path); curated by the user: never to be lost or edited
5. `logs/build-sfx-map` -> `channels/flashfx/logs/build-sfx-map` (fs-mv, 6 files, 151.3 KB; M18): 151.3 KB of files git does not hold (only the undo script can bring them back); a log the runner appends to: moves only with the runner stopped
6. `logs/index-hooks` -> `channels/flashfx/logs/index-hooks` (fs-mv, 9 files, 37.6 KB; M18): 37.6 KB of files git does not hold (only the undo script can bring them back); a log the runner appends to: moves only with the runner stopped
7. `logs/voice-profile` -> `channels/flashfx/logs/voice-profile` (fs-mv, 4 files, 34.5 KB; M18): 34.5 KB of files git does not hold (only the undo script can bring them back); a log the runner appends to: moves only with the runner stopped
8. `logs/runner.log` -> `channels/flashfx/logs/runner.log` (fs-mv, 1 files, 5.4 KB; M18): 5.4 KB of files git does not hold (only the undo script can bring them back); a log the runner appends to: moves only with the runner stopped
9. `logs/status.txt` -> `channels/flashfx/logs/status.txt` (fs-mv, 1 files, 78 B; M18): 78 B of files git does not hold (only the undo script can bring them back); a log the runner appends to: moves only with the runner stopped
10. `ideas.txt` -> `channels/flashfx/ideas.txt` (git-mv, 1 files, 139 B; M18): curated by the user: never to be lost or edited

M18 also rewrites text: old paths in the run folders, the captions files and the history lines, and the config keys move from config.json into channel.json (config-keys.tsv); those are the riskiest edits that are not moves.
