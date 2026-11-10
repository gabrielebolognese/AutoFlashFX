# s15-project: the editable project (S15, M21)

Built in M21. Spec: BUILD_SPEC.md section 5 (S15) and 14.9; code: pipeline/lib/s15/ (`python pipeline/lib/s15 run --run-dir <run>`).

## Purpose
The last stage of a format. It turns the finished reel into exports/<id>-N/project/, a Shorts Editor project folder that opens as the reel's
layers, each as editable as the editor allows today, and looks like <id>-N.mp4 when nothing is changed. It never changes the MP4, the hook 2
clip or the existing sections of the captions file. The hook 2 clip gets no project.

## Inputs
- timeline/timeline.json (the single input index: layers, captions, audio, markers, sources), the composition and the plans it names
- the stable editor copy's capabilities.json (editor.stable_dir), else baseline-capabilities.json (the editor v1.1.0 manifest, verbatim)
- cues.json (the cache copies of the sounds), the channel's tokens.json and fonts, the sound pack

## Outputs (runs/<run>/s15-project/)
- project/: project.json at the manifest's schemaVersion, media/ (audio/, images/, sprites/, overlays/, plates/), fonts/ (fonts.json version 2), layers.json,
  FALLBACKS.md, OPEN.txt (the runner's export step moves it to exports/<id>-N/project/ and fills in the name and the link)
- layers.json: the capture of every annotated layer, frame by frame (border quads, opacity, look signatures)
- editor.json (primary): the level (full, minimal, failed), the counts (native, sprites, overlays, plates, baked captions), the manifest used (source, hash,
  schemaVersion), every check (validate, layout, duration, mix, parity), needs_review reasons, the gaps (missing manifest keys with the elements they hit)

## Levels of a layer
native (the editor's own clip with keyframes), then sprite (one image, keyframed), then overlay (alpha video, PNG sequence or animated WebP of a layer
that changes continuously), then plate (an opaque video of a scene). Every drop names the manifest key the editor lacks (FALLBACKS.md, logs/editor-gaps.md).

## Invariants
- the project lasts as long as the video within 1 frame; its audio mix is within 0.5 LU of the video's; every sound sits at its time within 1 frame
- the project validates (the editor's CLI when the manifest has cli.validate, else pipeline/lib/s15/validate.py)
- a failure or the editor.cap_minutes cap writes the minimal project (plate, sounds, baked captions, hidden caption track) or project/FAILED.md, a NEEDS REVIEW
  flag, and exit 0: the export goes on in every case

## Exit codes
0 done (including a minimal or failed project, which are flagged), anything else is a code error (the review and fix loop).

## Model and session
No model. The capability upgrade (a builder session and a reviewer session) is run by the runner between ideas, never by this stage.
