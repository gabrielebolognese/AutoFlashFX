# 13-render: Final render (S13)

First version written in M2: the folder set, this contract, schema.json and dummy.sh are fixed here; M12
builds the real stage (run.sh and prompt.md) and refines the schema. Spec: BUILD_SPEC.md section 5, S13.

## Purpose
Render with HyperFrames at 1080x1920, 30 fps, H.264 high profile, yuv420p, AAC 48 kHz, with the approved mix; check with ffprobe (duration equal to the voice within 0.2 s, resolution, fps, codecs, audio, loudness); the same for the hook 2 clip.

## Inputs
- 10-build/project/ and hook2/, 08-voiceover/vo.wav and vo_hook2.wav, 11-sfx/sfx_stem.wav

## Outputs (in runs/<id>/13-render/)
- render.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done (pipeline/lib/state.py stage-done). An invalid output gets one retry with the validation errors
  inside the stage; after that it counts as a code error.
- final.mp4, hook2.mp4
- render.json: files, the ffprobe checks, pass
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).
- result.json with a `reason` when the stage exits 10 (drop) or 20 (block).

## Invariants
- every ffprobe check passes; an ffmpeg post-pass only fixes a container detail
- hook2.mp4 is 3.5 s or shorter

## Exit codes
0 done (the primary output must validate against schema.json; the runner then writes .done), 10 drop the idea (reason in result.json), 20 block the idea (reason in result.json), anything else is a code error and goes to the review and fix loop (BUILD_SPEC.md 4.2, built in M3).

## Model and session
No model.

## dummy.sh
`bash pipeline/stages/13-render/dummy.sh <run_dir>` writes fake outputs that validate against schema.json, sleeps
REELS_DUMMY_SECONDS (default 1) and honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK,
REELS_DUMMY_FLAG and REELS_DUMMY_INVALID lists (see pipeline/lib/dummy.sh). No model calls.
