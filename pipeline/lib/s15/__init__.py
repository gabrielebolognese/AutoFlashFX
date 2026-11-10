"""pipeline/lib/s15: the editable project (S15, BUILD_SPEC.md section 5 and 14.9, M21).

manifest.py (the editor's capabilities.json: baseline, plus, the stable copy's), geom.py (quads, affine fits, keyframe reduction),
capture.py (the layers of the composition, frame by frame), mapper.py (layers to native, sprite, overlay or plate clips),
render.py (sprites, overlays and plates), audio.py, writer.py (project.json, media, fonts, FALLBACKS.md, OPEN.txt), validate.py
(the S15 validator), checks.py (the layout, duration and mix checks), gaps.py (editor-gaps.md), run.py (the stage).

  python pipeline/lib/s15 <command>     (see __main__.py)
"""
