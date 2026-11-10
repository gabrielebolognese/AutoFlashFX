"""capdoc.py: writes pipeline/stages/s15-project/CAPABILITIES.md (BUILD_SPEC.md S15 step 8, M21).

The file lists every manifest key S15 knows: mapped or not, and which reel elements use it. KNOWN maps a key prefix (or an exact key) to
(status, what S15 does with it, the reel elements). A key of a manifest that no prefix covers is listed as "not mapped yet": that is what the
capability upgrade works on (the builder session extends KNOWN and the mappings).

  python pipeline/lib/s15/capdoc.py [--manifest FILE] [--out FILE]      (default: the baseline, the plus manifest and the editor repo's manifest if present)
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from s15 import manifest as sm  # noqa: E402

MAPPED, PARTLY, NOT = "mapped", "partly", "not mapped yet"

KNOWN: list[tuple[str, str, str, str]] = [
    ("manifestVersion", MAPPED, "read, never written", "-"),
    ("app", MAPPED, "read", "-"),
    ("appVersion", MAPPED, "written as meta.appVersion", "-"),
    ("lastBatch", MAPPED, "read (not part of the capability hash)", "-"),
    ("schemaVersion", MAPPED, "the project is written at exactly this version", "every project"),
    ("project.", MAPPED, "project.json, fonts/fonts.json (version 2), sample rate 48000", "every project"),
    ("media.video", MAPPED, "plates and footage clips (mp4)", "plates, footage-dummy clips"),
    ("media.audio", MAPPED, "the voice and sound effects as 48 kHz WAV", "voice, sound effects"),
    ("media.image", MAPPED, "PNG sprites, baked caption images, composition images", "cards' images, logos, sprites"),
    ("media.animatedImage", MAPPED, "animated WebP overlays within textureBudgetBytes and maxSide, 33/33/34 ms frame rule", "overlays when no alpha video"),
    ("media.videoAlpha", MAPPED, "VP9 alpha WebM overlays (first choice)", "counters, 3D, mascots, confetti"),
    ("media.imageSequence", MAPPED, "PNG sequence overlays (second choice)", "same as above"),
    ("media.lottie", NOT, "Lottie files are not produced by the compositions", "-"),
    ("trackKinds", MAPPED, "video, audio and caption tracks", "every project"),
    ("clipKinds:video", MAPPED, "plates, overlays (alpha), footage", "overlays, footage"),
    ("clipKinds:audio", MAPPED, "voice and sound effects", "voice, sfx"),
    ("clipKinds:image", MAPPED, "sprites, baked captions, native images", "images, sprites"),
    ("clipKinds:text", MAPPED, "native text when the font is in the editor's library or a composition font", "titles, labels, chips"),
    ("clipKinds:solid", MAPPED, "native boxes (cards, chips, bars) when the style is supported", "cards, chips, tracker"),
    ("clipKinds:caption", MAPPED, "the caption track, native or hidden next to baked captions", "captions"),
    ("clipKinds", NOT, "compound, shape, null, lottie, adjustment: not written (groups are flattened)", "-"),
    ("transform.rotation3d", NOT, "a 3D parallax tilt is fitted by a flat affine map; a stronger tilt becomes an overlay", "cards during fly-in"),
    ("transform.parenting", NOT, "groups are flattened (world-space keyframes)", "-"),
    ("transform.motionPaths", NOT, "positions are keyed per axis", "-"),
    ("transform.autoOrient", NOT, "rotation is keyed", "-"),
    ("keyframes.props", MAPPED, "transform.x, transform.y, transform.scale, transform.scaleY, transform.rotation, opacity", "every moving layer"),
    ("keyframes.eases", PARTLY, "linear and the Penner eases (sine to bounce) fitted to the captured motion; the editor's v1 eases are never guessed", "entrances, exits"),
    ("keyframes.bezier", NOT, "the fit uses named eases", "-"),
    ("keyframes.spring", NOT, "the fit uses named eases", "-"),
    ("keyframes.vectorValues", NOT, "color changes of a layer make it an overlay", "-"),
    ("keyframes.effectProps", NOT, "no effects are written", "-"),
    ("solid.shapes", MAPPED, "rect, roundedRect, ellipse", "cards, chips, dots"),
    ("solid.fills", MAPPED, "color, gradient2 (a vertical two-stop CSS gradient), linear (stops)", "cards, glow"),
    ("solid.stroke", MAPPED, "a uniform solid CSS border becomes a stroke aligned inside", "paper cards"),
    ("solid.shadow", MAPPED, "one outer box-shadow becomes the editor's shadow", "paper cards"),
    ("solid.cornerRadii", MAPPED, "four different border radii", "-"),
    ("mediaFrame.", MAPPED, "a picture's cornerRadius, stroke and shadow", "card images"),
    ("text.fills", PARTLY, "color only; gradient text becomes a sprite", "titles"),
    ("text.stroke", MAPPED, "-webkit-text-stroke", "-"),
    ("text.shadow", MAPPED, "one text-shadow", "-"),
    ("text.background", NOT, "a chip's box is its own solid layer, the text a text layer", "chips"),
    ("text.anims", NOT, "text motion is captured as keyframes or an overlay", "-"),
    ("text.animUnits", NOT, "-", "-"),
    ("text.spans", NOT, "-", "-"),
    ("text.counter", NOT, "a counting number is an overlay", "stat numbers"),
    ("text.animators", NOT, "-", "-"),
    ("text.animatorKeyframeProps", NOT, "-", "-"),
    ("captions.highlightModes", MAPPED, "none (word mode, one word at a time); progressive and reveal are known but not needed", "word captions"),
    ("captions.perCueStyle", MAPPED, "emphasis words restyle their cue (serif italic, larger, accent box)", "word captions"),
    ("captions.wordEmphasis", MAPPED, "required for native word captions with emphasis words", "word captions"),
    ("captions.cueAnims", MAPPED, "fade in 4 frames and out 2 frames", "word captions"),
    ("captions.boxModes", NOT, "-", "-"),
    ("captions.wordsImport", NOT, "-", "-"),
    ("transitions", NOT, "scene transitions are inside the scenes' layers (keyframes or overlays)", "-"),
    ("compositing.", NOT, "blend modes, mattes, masks, compound and adjustment clips are not written", "-"),
    ("vector.", NOT, "svg artwork is baked as a sprite", "icons, strike lines"),
    ("effects", NOT, "blur and glow are baked into overlays", "fade-blur exits"),
    ("audio.clipGainDb", MAPPED, "the sound gains plus the master gain, clamped to the range", "voice, sfx"),
    ("audio.fades", MAPPED, "the fade-out of each sound", "sfx"),
    ("audio.loudness", MAPPED, "the project loudness target -14 LUFS, true peak -1.5 dBTP", "every project"),
    ("audio.trackGain", NOT, "-", "-"),
    ("audio.trackGainDb", NOT, "-", "-"),
    ("audio.pan", NOT, "the mix is mono", "-"),
    ("audio.panRange", NOT, "-", "-"),
    ("audio.fadeCurves", NOT, "linear fades only", "-"),
    ("audio.beatMarkers", NOT, "-", "-"),
    ("time.", NOT, "no speed change, freeze, reverse or remap", "-"),
    ("templates", NOT, "-", "-"),
    ("export.", NOT, "exporting is the editor's own", "-"),
    ("cli.validate", MAPPED, "the project is validated with the editor's CLI in the stable copy", "every project"),
    ("cli.normalize", MAPPED, "the project is normalized after writing", "every project"),
    ("cli.info", NOT, "-", "-"),
    ("cli.render", MAPPED, "parity check: the editor renders the project and the render is compared with the video", "every project"),
    ("cli.compare", MAPPED, "the parity check's frame compare", "every project"),
    ("cli.fill", NOT, "-", "-"),
    ("interop.openLink", MAPPED, "OPEN.txt and the EDITOR section carry the open link", "every project"),
    ("interop.externalReload", MAPPED, "rebuild-project.sh may rewrite a project the editor has open", "-"),
    ("interop.repairOnOpen", MAPPED, "-", "-"),
    ("interop.fallbackOf", MAPPED, "sprites and overlays carry the native clip they stand in for when S15 can describe it (boxes)", "sprites"),
    ("interop.generatorMeta", MAPPED, "meta.generator: instagramReels, git hash, runs/<id>", "every project"),
]


def lookup(key: str) -> tuple[str, str, str]:
    base = key.split(":", 1)[0].split("=", 1)[0]
    best = None
    for k, status, what, who in KNOWN:
        if base == k or base.startswith(k) or key == k or key.startswith(k):
            if best is None or len(k) > len(best[0]):
                best = (k, status, what, who)
    if best is None:
        return NOT, "not mapped yet (new key: the capability upgrade reads the editor's INTEROP.md and extends S15)", "-"
    return best[1], best[2], best[3]


def keys_of(m: dict) -> list[str]:
    out = []
    for k, v in sorted(sm.flatten(sm.capability_content(m)).items()):
        if isinstance(v, list):
            out.append(k)
            out += [f"{k}:{x}" for x in v if isinstance(x, (str, int, float))] if k in ("clipKinds", "text.anims", "captions.highlightModes", "captions.cueAnims", "solid.fills", "text.fills",
                                                                                    "transitions", "effects", "keyframes.eases") else []
        else:
            out.append(k)
    return out


def render(manifests: list[tuple[str, dict]]) -> str:
    seen: dict[str, tuple[str, str, str]] = {}
    for _name, m in manifests:
        for k in keys_of(m):
            seen.setdefault(k, lookup(k))
    lines = ["# Editor capabilities S15 knows", "",
             "Every manifest key of the manifests below, whether S15 maps it, what it does and which reel elements use it. Written by",
             "`python pipeline/lib/s15/capdoc.py`; a key no row covers is listed as not mapped yet: the capability upgrade (BUILD_SPEC.md S15 step 8) works from that.", "",
             "Manifests read: " + ", ".join(f"{n} (schemaVersion {m.get('schemaVersion')})" for n, m in manifests), "",
             "| manifest key | status | what S15 does | reel elements |", "| --- | --- | --- | --- |"]
    for k in sorted(seen):
        st, what, who = seen[k]
        lines.append(f"| `{k}` | {st} | {what} | {who} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", action="append", default=[])
    ap.add_argument("--out", default=os.path.join(sm.STAGE_DIR, "CAPABILITIES.md"))
    a = ap.parse_args(argv)
    ms = [("baseline", sm.baseline())]
    if os.path.isfile(sm.PLUS):
        ms.append(("plus", sm.load_file(sm.PLUS)))
    editor = os.environ.get("EDITOR_REPO") or "/c/Users/there/OneDrive/Desktop/editor"
    real = os.path.join(editor, "capabilities.json")
    if os.path.isfile(real):
        ms.append(("editor " + str(sm.load_file(real).get("appVersion")), sm.load_file(real)))
    for f in a.manifest:
        ms.append((os.path.basename(f), sm.load_file(f)))
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(render(ms))
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
