# problem-solution-reel: the template of a new channel

`bash pipeline/bin/new-channel <id> --format problem-solution-reel --platform instagram-reels --name "..."` copies this folder into
channels/<id>/ and writes channel.json (enabled false) from channel.config.json and the platform's defaults. Every file here that
still says [FILL IN] must be written by you; `bash pipeline/bin/preflight --channel <id>` lists what is missing or unfilled.

Not copied from here, because they are made by tools: styles/paper-cards/tokens.json (`bash pipeline/bin/build-tokens`),
styles/sfx/sfx-map.json (`bash pipeline/bin/build-sfx-map`), motion-lib/catalog.json (the approved components: copy or build them),
library/voice/engine.txt (BUILD_SPEC.md 2.5), library/.hooks.index.json (`bash pipeline/bin/index-hooks`).
