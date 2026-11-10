# S15 capability upgrade: the reviewer session

A builder session just extended S15 (the stage that writes a Shorts Editor project folder for each reel; BUILD_SPEC.md section 5, S15) for new editor capabilities:

{{KEYS}}

The editor's stable copy is `{{STABLE}}`. Review the uncommitted changes in `pipeline/lib/s15/`, `pipeline/stages/s15-project/` and `pipeline/tests/` (`git diff`, `git status`).

## Check

1. Against `{{STABLE}}/docs/INTEROP.md` (and `capabilities.json`): is every field and value the change writes in the manifest's lists, written at the manifest's schemaVersion,
   with the JSON shape INTEROP.md gives?
2. Does it use a feature only when the manifest lists it (lists are exhaustive; a key that is false or absent is unsupported)?
3. Run the tests: `M21_SECTIONS="1 2" bash pipeline/tests/test-m21.sh`, and the new fixture through `node scripts/cli/run.mjs validate <dir> --json` in `{{STABLE}}`.
4. CAPABILITIES.md lists every manifest key with the right status.
5. Nothing outside the three folders changed; no em dash anywhere.

## Answer

Your whole answer is either the single word `accepted` on its own first line, or `problems:` on the first line followed by a numbered list of concrete problems
(file, what is wrong, what to do). Do not fix anything yourself.
