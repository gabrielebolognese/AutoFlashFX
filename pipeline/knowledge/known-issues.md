# Known issues: symptom -> fix

One line per fix the runner's fixer applied (BUILD_SPEC.md 4.2), appended automatically in this format:
`- <date> | <stage> | <symptom> -> <fix> (commit <sha>)`. The reviewer reads this file before every review, so a
symptom seen before gets the same fix at once. Edit or prune by hand whenever a line is stale.

- 2026-11-02 | 03-gate | 03-gate dummy: invalid output "'H' is a required property" -> add H, F_kind, model_H to dummy.sh gate.json after schema changes; a dummy must follow its stage's schema.json (commit b7ea7e3)
- 2026-11-02 | 12-review | style check TimeoutExpired on tools/analyze_refs.py in review round 2 or later (its ffmpeg waits at "Overwrite? [y/N]" for a still from the previous round) -> style_check.py removes analysis/v01 first and runs the analyzer with stdin=DEVNULL; kill a leftover waiting ffmpeg (commit 9b47167)
- 2026-11-02 | any model call | "You've reached your Fable limit. Switch to another model" (api error 429, model_requires_usage_credits) retried as a rate limit, then a code error -> ai.sh retries that call with models.limit_fallback (opus); nothing to fix in the stage (commit 89a2925)
