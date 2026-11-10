# Editor capabilities S15 knows

Every manifest key of the manifests below, whether S15 maps it, what it does and which reel elements use it. Written by
`python pipeline/lib/s15/capdoc.py`; a key no row covers is listed as not mapped yet: the capability upgrade (BUILD_SPEC.md S15 step 8) works from that.

Manifests read: baseline (schemaVersion 3), plus (schemaVersion 6)

| manifest key | status | what S15 does | reel elements |
| --- | --- | --- | --- |
| `app` | mapped | read | - |
| `audio.clipGainDb` | mapped | the sound gains plus the master gain, clamped to the range | voice, sfx |
| `audio.fades` | mapped | the fade-out of each sound | sfx |
| `audio.loudness` | mapped | the project loudness target -14 LUFS, true peak -1.5 dBTP | every project |
| `audio.pan` | not mapped yet | the mix is mono | - |
| `audio.trackGain` | not mapped yet | - | - |
| `captions.boxModes` | not mapped yet | - | - |
| `captions.cueAnims` | mapped | fade in 4 frames and out 2 frames | word captions |
| `captions.cueAnims:fade` | mapped | fade in 4 frames and out 2 frames | word captions |
| `captions.cueAnims:pop` | mapped | fade in 4 frames and out 2 frames | word captions |
| `captions.cueAnims:slideDown` | mapped | fade in 4 frames and out 2 frames | word captions |
| `captions.cueAnims:slideUp` | mapped | fade in 4 frames and out 2 frames | word captions |
| `captions.highlightModes` | mapped | none (word mode, one word at a time); progressive and reveal are known but not needed | word captions |
| `captions.highlightModes:background` | mapped | none (word mode, one word at a time); progressive and reveal are known but not needed | word captions |
| `captions.highlightModes:color` | mapped | none (word mode, one word at a time); progressive and reveal are known but not needed | word captions |
| `captions.highlightModes:colorAndScale` | mapped | none (word mode, one word at a time); progressive and reveal are known but not needed | word captions |
| `captions.highlightModes:none` | mapped | none (word mode, one word at a time); progressive and reveal are known but not needed | word captions |
| `captions.highlightModes:progressive` | mapped | none (word mode, one word at a time); progressive and reveal are known but not needed | word captions |
| `captions.highlightModes:reveal` | mapped | none (word mode, one word at a time); progressive and reveal are known but not needed | word captions |
| `captions.highlightModes:scale` | mapped | none (word mode, one word at a time); progressive and reveal are known but not needed | word captions |
| `captions.perCueStyle` | mapped | emphasis words restyle their cue (serif italic, larger, accent box) | word captions |
| `captions.wordEmphasis` | mapped | required for native word captions with emphasis words | word captions |
| `captions.wordsImport` | not mapped yet | - | - |
| `cli.compare` | mapped | the parity check's frame compare | every project |
| `cli.info` | not mapped yet | - | - |
| `cli.normalize` | mapped | the project is normalized after writing | every project |
| `cli.render` | mapped | parity check: the editor renders the project and the render is compared with the video | every project |
| `cli.validate` | mapped | the project is validated with the editor's CLI in the stable copy | every project |
| `clipKinds` | not mapped yet | compound, shape, null, lottie, adjustment: not written (groups are flattened) | - |
| `clipKinds:audio` | mapped | voice and sound effects | voice, sfx |
| `clipKinds:caption` | mapped | the caption track, native or hidden next to baked captions | captions |
| `clipKinds:image` | mapped | sprites, baked captions, native images | images, sprites |
| `clipKinds:solid` | mapped | native boxes (cards, chips, bars) when the style is supported | cards, chips, tracker |
| `clipKinds:text` | mapped | native text when the font is in the editor's library or a composition font | titles, labels, chips |
| `clipKinds:video` | mapped | plates, overlays (alpha), footage | overlays, footage |
| `compositing.adjustment` | not mapped yet | blend modes, mattes, masks, compound and adjustment clips are not written | - |
| `compositing.blendModes` | not mapped yet | blend modes, mattes, masks, compound and adjustment clips are not written | - |
| `compositing.compound` | not mapped yet | blend modes, mattes, masks, compound and adjustment clips are not written | - |
| `compositing.masks` | not mapped yet | blend modes, mattes, masks, compound and adjustment clips are not written | - |
| `compositing.trackMatte` | not mapped yet | blend modes, mattes, masks, compound and adjustment clips are not written | - |
| `effects` | not mapped yet | blur and glow are baked into overlays | fade-blur exits |
| `export.alpha` | not mapped yet | exporting is the editor's own | - |
| `export.containers` | not mapped yet | exporting is the editor's own | - |
| `export.gif` | not mapped yet | exporting is the editor's own | - |
| `export.imageSequence` | not mapped yet | exporting is the editor's own | - |
| `export.stems` | not mapped yet | exporting is the editor's own | - |
| `export.videoCodecs` | not mapped yet | exporting is the editor's own | - |
| `interop.externalReload` | mapped | rebuild-project.sh may rewrite a project the editor has open | - |
| `interop.fallbackOf` | mapped | sprites and overlays carry the native clip they stand in for when S15 can describe it (boxes) | sprites |
| `interop.generatorMeta` | mapped | meta.generator: instagramReels, git hash, runs/<id> | every project |
| `interop.openLink` | mapped | OPEN.txt and the EDITOR section carry the open link | every project |
| `interop.repairOnOpen` | mapped | - | - |
| `keyframes.bezier` | not mapped yet | the fit uses named eases | - |
| `keyframes.eases` | partly | linear and the Penner eases (sine to bounce) fitted to the captured motion; the editor's v1 eases are never guessed | entrances, exits |
| `keyframes.eases:easeIn` | partly | linear and the Penner eases (sine to bounce) fitted to the captured motion; the editor's v1 eases are never guessed | entrances, exits |
| `keyframes.eases:easeInOut` | partly | linear and the Penner eases (sine to bounce) fitted to the captured motion; the editor's v1 eases are never guessed | entrances, exits |
| `keyframes.eases:easeOut` | partly | linear and the Penner eases (sine to bounce) fitted to the captured motion; the editor's v1 eases are never guessed | entrances, exits |
| `keyframes.eases:hold` | partly | linear and the Penner eases (sine to bounce) fitted to the captured motion; the editor's v1 eases are never guessed | entrances, exits |
| `keyframes.eases:linear` | partly | linear and the Penner eases (sine to bounce) fitted to the captured motion; the editor's v1 eases are never guessed | entrances, exits |
| `keyframes.eases:overshoot` | partly | linear and the Penner eases (sine to bounce) fitted to the captured motion; the editor's v1 eases are never guessed | entrances, exits |
| `keyframes.eases:smooth` | partly | linear and the Penner eases (sine to bounce) fitted to the captured motion; the editor's v1 eases are never guessed | entrances, exits |
| `keyframes.eases:snap` | partly | linear and the Penner eases (sine to bounce) fitted to the captured motion; the editor's v1 eases are never guessed | entrances, exits |
| `keyframes.props` | mapped | transform.x, transform.y, transform.scale, transform.scaleY, transform.rotation, opacity | every moving layer |
| `keyframes.spring` | not mapped yet | the fit uses named eases | - |
| `keyframes.vectorValues` | not mapped yet | color changes of a layer make it an overlay | - |
| `manifestVersion` | mapped | read, never written | - |
| `media.animatedImage.alpha` | mapped | animated WebP overlays within textureBudgetBytes and maxSide, 33/33/34 ms frame rule | overlays when no alpha video |
| `media.animatedImage.formats` | mapped | animated WebP overlays within textureBudgetBytes and maxSide, 33/33/34 ms frame rule | overlays when no alpha video |
| `media.animatedImage.maxSide` | mapped | animated WebP overlays within textureBudgetBytes and maxSide, 33/33/34 ms frame rule | overlays when no alpha video |
| `media.animatedImage.textureBudgetBytes` | mapped | animated WebP overlays within textureBudgetBytes and maxSide, 33/33/34 ms frame rule | overlays when no alpha video |
| `media.audio` | mapped | the voice and sound effects as 48 kHz WAV | voice, sound effects |
| `media.image` | mapped | PNG sprites, baked caption images, composition images | cards' images, logos, sprites |
| `media.imageSequence` | mapped | PNG sequence overlays (second choice) | same as above |
| `media.lottie` | not mapped yet | Lottie files are not produced by the compositions | - |
| `media.video` | mapped | plates and footage clips (mp4) | plates, footage-dummy clips |
| `media.videoAlpha` | mapped | VP9 alpha WebM overlays (first choice) | counters, 3D, mascots, confetti |
| `mediaFrame.cornerRadius` | mapped | a picture's cornerRadius, stroke and shadow | card images |
| `mediaFrame.shadow` | mapped | a picture's cornerRadius, stroke and shadow | card images |
| `mediaFrame.stroke` | mapped | a picture's cornerRadius, stroke and shadow | card images |
| `project.file` | mapped | project.json, fonts/fonts.json (version 2), sample rate 48000 | every project |
| `project.fontsManifest` | mapped | project.json, fonts/fonts.json (version 2), sample rate 48000 | every project |
| `project.fontsManifestVersion` | mapped | project.json, fonts/fonts.json (version 2), sample rate 48000 | every project |
| `project.sampleRate` | mapped | project.json, fonts/fonts.json (version 2), sample rate 48000 | every project |
| `schemaVersion` | mapped | the project is written at exactly this version | every project |
| `solid.cornerRadii` | mapped | four different border radii | - |
| `solid.fills` | mapped | color, gradient2 (a vertical two-stop CSS gradient), linear (stops) | cards, glow |
| `solid.fills:color` | mapped | color, gradient2 (a vertical two-stop CSS gradient), linear (stops) | cards, glow |
| `solid.fills:gradient2` | mapped | color, gradient2 (a vertical two-stop CSS gradient), linear (stops) | cards, glow |
| `solid.fills:linear` | mapped | color, gradient2 (a vertical two-stop CSS gradient), linear (stops) | cards, glow |
| `solid.fills:radial` | mapped | color, gradient2 (a vertical two-stop CSS gradient), linear (stops) | cards, glow |
| `solid.shadow` | mapped | one outer box-shadow becomes the editor's shadow | paper cards |
| `solid.shapes` | mapped | rect, roundedRect, ellipse | cards, chips, dots |
| `solid.stroke` | mapped | a uniform solid CSS border becomes a stroke aligned inside | paper cards |
| `templates` | not mapped yet | - | - |
| `text.animUnits` | not mapped yet | - | - |
| `text.animators` | not mapped yet | - | - |
| `text.anims` | not mapped yet | text motion is captured as keyframes or an overlay | - |
| `text.anims:blurIn` | not mapped yet | text motion is captured as keyframes or an overlay | - |
| `text.anims:fade` | not mapped yet | text motion is captured as keyframes or an overlay | - |
| `text.anims:lineReveal` | not mapped yet | text motion is captured as keyframes or an overlay | - |
| `text.anims:pop` | not mapped yet | text motion is captured as keyframes or an overlay | - |
| `text.anims:scaleBounce` | not mapped yet | text motion is captured as keyframes or an overlay | - |
| `text.anims:slideDown` | not mapped yet | text motion is captured as keyframes or an overlay | - |
| `text.anims:slideLeft` | not mapped yet | text motion is captured as keyframes or an overlay | - |
| `text.anims:slideRight` | not mapped yet | text motion is captured as keyframes or an overlay | - |
| `text.anims:slideUp` | not mapped yet | text motion is captured as keyframes or an overlay | - |
| `text.anims:typewriter` | not mapped yet | text motion is captured as keyframes or an overlay | - |
| `text.anims:wordFade` | not mapped yet | text motion is captured as keyframes or an overlay | - |
| `text.anims:wordPop` | not mapped yet | text motion is captured as keyframes or an overlay | - |
| `text.background.modes` | not mapped yet | a chip's box is its own solid layer, the text a text layer | chips |
| `text.background.shadow` | not mapped yet | a chip's box is its own solid layer, the text a text layer | chips |
| `text.background.stroke` | not mapped yet | a chip's box is its own solid layer, the text a text layer | chips |
| `text.counter` | not mapped yet | a counting number is an overlay | stat numbers |
| `text.fills` | partly | color only; gradient text becomes a sprite | titles |
| `text.fills:color` | partly | color only; gradient text becomes a sprite | titles |
| `text.fills:gradient2` | partly | color only; gradient text becomes a sprite | titles |
| `text.fills:linear` | partly | color only; gradient text becomes a sprite | titles |
| `text.fills:radial` | partly | color only; gradient text becomes a sprite | titles |
| `text.shadow` | mapped | one text-shadow | - |
| `text.spans` | not mapped yet | - | - |
| `text.stroke` | mapped | -webkit-text-stroke | - |
| `time.frameBlend` | not mapped yet | no speed change, freeze, reverse or remap | - |
| `time.freeze` | not mapped yet | no speed change, freeze, reverse or remap | - |
| `time.remap` | not mapped yet | no speed change, freeze, reverse or remap | - |
| `time.reverse` | not mapped yet | no speed change, freeze, reverse or remap | - |
| `time.speedRange` | not mapped yet | no speed change, freeze, reverse or remap | - |
| `trackKinds` | mapped | video, audio and caption tracks | every project |
| `transform.autoOrient` | not mapped yet | rotation is keyed | - |
| `transform.motionPaths` | not mapped yet | positions are keyed per axis | - |
| `transform.parenting` | not mapped yet | groups are flattened (world-space keyframes) | - |
| `transform.rotation3d` | not mapped yet | a 3D parallax tilt is fitted by a flat affine map; a stronger tilt becomes an overlay | cards during fly-in |
| `transitions` | not mapped yet | scene transitions are inside the scenes' layers (keyframes or overlays) | - |
| `transitions:crossDissolve` | not mapped yet | scene transitions are inside the scenes' layers (keyframes or overlays) | - |
| `transitions:dipToBlack` | not mapped yet | scene transitions are inside the scenes' layers (keyframes or overlays) | - |
| `transitions:dipToWhite` | not mapped yet | scene transitions are inside the scenes' layers (keyframes or overlays) | - |
| `vector.shapes` | not mapped yet | svg artwork is baked as a sprite | icons, strike lines |
| `vector.svgImport` | not mapped yet | svg artwork is baked as a sprite | icons, strike lines |
| `vector.trimPaths` | not mapped yet | svg artwork is baked as a sprite | icons, strike lines |
