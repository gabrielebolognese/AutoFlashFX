# timeline: the final video as layers in time (M20)

Built in M20. Spec: BUILD_SPEC.md 14.8; schema pipeline/schemas/timeline.schema.json (version 1; schema.json here is the same file).

## Purpose
Every run of every format ends its production stages with runs/<run>/timeline/timeline.json: the final video as layers in time.
For a generated format (problem-solution-reel) the HyperFrames composition stays the render source and the timeline describes it;
for a footage format the cut stage writes it and pipeline/lib/timeline/render_ffmpeg.py renders it. The exporters read the length and
times from it, and S15 (M21) builds the editor project from it. The timeline is a record, not a new decision.

## Inputs (generated formats)
- 13-render/final.mp4 (the duration the timeline must match within 1 frame; size, fps, sample rate)
- 09c-transitions/merged.json (scenes, components, caption chunks, transitions, branding), 08-voiceover/words.json (every spoken word
  and the beats), 11-sfx/cues.json (every sound), 07-script/script.json (the comment keyword), 10-build/project/index.html and
  instances.json (the composition and its hosts), 08-voiceover/vo.wav and 11-sfx/mix.wav, the sound files of the channel's pack
- config: paths.sfx_dir (REELS_SFX_DIR overrides); format.json timeline.builder

## Outputs (in runs/<id>/timeline/)
- timeline.json (primary): settings (size, fps, duration in frames, sample rate, background), sources (path, base run | channel | abs,
  kind, duration, size, sha256), layers bottom to top (one per host of the composition: the paper canvas, every component instance
  with its selector and its component id in the channel's motion library, the caption host as caption-burn), captions (chunks and
  words with start, end, emphasis; the style id), audio (the voice with its words, every sound with start, trim, fades, gain and cue
  type; footage audio; music reserved), transitions, markers (scene and beat starts, the hook end, the end card, the comment keyword),
  provenance
- check.json and check.txt: pipeline/lib/timeline/check.py's report (schema, sources, duration, layers, composition, words, captions,
  cues, footage, markers)

## Invariants
- the duration is within 1 frame of final.mp4; every word of words.json and every sound of cues.json is in the timeline at its time;
  every host of the composition has a layer and every layer's selector is a host
- nothing in the timeline contradicts the plans, words.json, cues.json or the composition: every value comes from a file a stage wrote

## Exit codes
0 done (timeline.json validates and every check passes), anything else is a code error (the review and fix loop).

## Model and session
No model.

## dummy.sh
Writes a minimal timeline.json that validates against schema.json; honors the planted REELS_DUMMY_* lists (pipeline/lib/dummy.sh).
