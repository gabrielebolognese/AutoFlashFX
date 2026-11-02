# 13-render: Final render (S13)

Built in M12 (the folder, the first schema and dummy.sh date from M2). Spec: BUILD_SPEC.md section 5, S13;
DECISIONS.md (M12).

## Purpose
The approved draft rendered for real: HyperFrames renders the built composition (10-build/project/) at its own size,
1080x1920 at 30 fps, as a silent video (video.mp4); ffmpeg muxes the approved mix (11-sfx/mix.wav, the voice and
the sound effects verified at -14 LUFS) into final.mp4 as AAC 48 kHz with the video copied, so the mix the review
heard is what the reel carries (HyperFrames' own audio path measured 3 LU louder on the golden reel: it duplicates a
mono track to two channels). The hook 2 clip (10-build/hook2/ with 11-sfx/mix_hook2.wav) takes the same path.

## Inputs
- 10-build/project/ (index.html, compositions/, assets/), 10-build/hook2/ (optional: without it the hook 2 file is
  the reel's first 3.5 s, flagged), 10-build/build.json (render_flag: the WebGL flag of the draft), 10-build/plan.json
- 08-voiceover/vo.wav (the duration every check compares with) and vo_hook2.wav
- 11-sfx/mix.wav (the voice alone with a flag when missing) and mix_hook2.wav (vo_hook2.wav with a flag when missing)
- config: render.* (quality, audio_bitrate_k, audio_channels, duration_tolerance_s, loudness_tolerance_lu,
  true_peak_tolerance_db, hook2_max_s), voice.loudness_lufs and true_peak_dbtp, timeouts.render_final_seconds,
  render_hook2_seconds, mux_seconds; node_modules/hyperframes, ffmpeg, ffprobe

## Outputs (in runs/<id>/13-render/)
- render.json is the primary output: the stage is done when it validates against schema.json and the runner has
  written .done (pipeline/lib/state.py stage-done). files {reel, hook2, video}, checks {reel, hook2} (each check with
  want, got, ok: width, height, fps, video_codec, profile, pix_fmt, audio_present, audio_codec, sample_rate,
  duration, loudness; max_seconds for the hook 2 clip), post_pass (what one ffmpeg pass fixed), reel and hook2 (the
  render numbers, the probe, the failing checks), pass.
- final.mp4 (1080x1920, 30 fps, H.264 High, yuv420p, AAC 48 kHz mono, the voice's length within 0.2 s, -14 LUFS
  plus or minus 1, true peak at most -1.5 dBTP plus 0.5 dB of AAC room), hook2.mp4 (3.5 s at most, its own voice and
  sounds), video.mp4 (the silent render, kept for a re-mux by hand).
- stage.log: everything the stage printed (its `say` lines also reach the terminal through fd 3).

## Invariants
- every check passes on final.mp4; an ffmpeg post-pass fixes only the detail that differs (the video is re-encoded
  only for a wrong profile, pixel format, size or rate; the audio is encoded once as AAC; a long file is trimmed to
  the voice; a loudness miss gets one gain plus limiter pass on the mix) and the checks run again
- hook2.mp4 is 3.5 s or shorter, with audio; its loudness is a soft check (a flag, never a failure: the clip is short)
- the voice is the duration reference (words.json, the plan and the mix share its timeline)

## Exit codes
0 done (the primary output must validate against schema.json; the runner then writes .done), anything else is a
code error and goes to the review and fix loop (BUILD_SPEC.md 4.2): a render failure, ffmpeg failing, a missing
input, a check that still fails after the post-pass (exit 3 inside finalrender.py).

## Model and session
No model.

## dummy.sh
`bash pipeline/stages/13-render/dummy.sh <run_dir>` writes fake outputs that validate against schema.json, sleeps
REELS_DUMMY_SECONDS (default 1) and honors the planted REELS_DUMMY_FAIL, REELS_DUMMY_DROP, REELS_DUMMY_BLOCK,
REELS_DUMMY_FLAG and REELS_DUMMY_INVALID lists (see pipeline/lib/dummy.sh). No model calls.
