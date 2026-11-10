# S15 capability upgrade: the builder session

You maintain S15, the stage of the instagramReels pipeline that writes a Shorts Editor project folder for each finished reel (BUILD_SPEC.md section 5, S15, and 14.9).
The editor's stable copy (`{{STABLE}}`) now announces capabilities S15 has not been written for. The keys that are new since the manifest S15 last accepted:

{{KEYS}}

## What to do

1. Read `{{STABLE}}/capabilities.json` and `{{STABLE}}/docs/INTEROP.md` (the exact JSON of each supported feature; section 21 of `docs/PLAN_V1_2.md` for planned ones).
   Also check any mapping S15 wrote earlier from the plan against INTEROP.md.
2. Extend S15 for the new keys, in `pipeline/lib/s15/` (manifest.py asks the questions, mapper.py decides the level of each layer, writer.py writes the clips,
   validate.py is the fallback validator, run.py orders the work) and `pipeline/stages/s15-project/CAPABILITIES.md` (regenerate it with
   `python pipeline/lib/s15/capdoc.py`: every manifest key, mapped or not, and which reel elements use it). Use a clip kind, field, ease, transition, effect or value only
   when the manifest lists it: lists are exhaustive. A key that is false or absent is unsupported. Write the project at exactly the manifest's schemaVersion.
3. Add tests: a fixture project that the editor's CLI validates (`node scripts/cli/run.mjs validate <dir> --json` in `{{STABLE}}`), and, when the manifest has `cli.render`,
   rendered and compared with `compare`. Put them in `pipeline/tests/` (extend `pipeline/tests/m21-helpers.py` or add a file next to it) and run them.
4. Run `bash pipeline/tests/test-m21.sh` sections 1 and 2 (`M21_SECTIONS="1 2"`) and fix what you broke.

## Rules

- Edit only `pipeline/lib/s15/`, `pipeline/stages/s15-project/` and `pipeline/tests/`. Never touch `channels/`, `exports/`, the editor repo or its stable copy.
- The project must look like the exported MP4 when nothing is changed: a native clip replaces a sprite or overlay only when the look is the same.
- Never write an em dash in any file.
- Problems the last review found (empty on the first round):

{{PROBLEMS}}

When you are done, say in one short paragraph what you changed.
