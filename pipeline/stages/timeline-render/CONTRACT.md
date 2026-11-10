# timeline-render: render a timeline with ffmpeg (M20)

Built in M20 for the footage family (BUILD_SPEC.md 14.8). A generated format renders its HyperFrames composition in 13-render and has no
stage of this name.

## Inputs
runs/<id>/timeline/timeline.json (written by the format's cut stage; schema pipeline/schemas/timeline.schema.json) and the sources it lists.

## Outputs (in runs/<id>/timeline-render/)
- render.json (primary): pass, files.reel, the frames, the probe of the render
- final.mp4: footage and still layers trimmed and joined, captions burned in at their chunk times, the footage audio, the voice and the
  sounds mixed and normalized to audio.loudness.target_lufs, AAC at the timeline's sample rate, H.264 High yuv420p at its size and rate,
  exactly settings.duration_frames long
- check.json and check.txt: pipeline/lib/timeline/check.py's report, run first

## Invariants
final.mp4 lasts as long as the timeline within 1 frame; the render is one heavy step (the global heavy lock, kind encode).

## Exit codes
0 done, anything else a code error (the review and fix loop).

## Model and session
No model.
