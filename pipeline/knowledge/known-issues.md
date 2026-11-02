# Known issues: symptom -> fix

One line per fix the runner's fixer applied (BUILD_SPEC.md 4.2), appended automatically in this format:
`- <date> | <stage> | <symptom> -> <fix> (commit <sha>)`. The reviewer reads this file before every review, so a
symptom seen before gets the same fix at once. Edit or prune by hand whenever a line is stale.

- 2026-11-02 | 03-gate | 03-gate dummy: invalid output "'H' is a required property" -> add H, F_kind, model_H to dummy.sh gate.json after schema changes (F1, runs/2026-11-02_0701_idea-a-the-gh-cli)
