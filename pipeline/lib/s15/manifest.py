"""manifest.py: the editor's capabilities.json as S15 reads it (BUILD_SPEC.md S15 step 1).

Lists in the manifest are exhaustive: a key that is false or absent is unsupported. `Manifest.has(path)` answers for one
key ("solid.stroke", "captions.wordEmphasis"), `Manifest.lists(path, value)` for a value of a list ("keyframes.eases", "easeOut").
The capability hash covers everything except lastBatch and appVersion (spec step 8).
"""
from __future__ import annotations

import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE = os.path.dirname(os.path.dirname(HERE))
STAGE_DIR = os.path.join(PIPELINE, "stages", "s15-project")
BASELINE = os.path.join(STAGE_DIR, "baseline-capabilities.json")
PLUS = os.path.join(PIPELINE, "tests", "manifest-plus.json")
IGNORED_FOR_HASH = ("lastBatch", "appVersion")


def load_file(path: str) -> dict:
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def baseline() -> dict:
    return load_file(BASELINE)


def find(stable_dir: str | None = None, explicit: str | None = None) -> tuple[dict, str]:
    """(manifest, where it came from): an explicit file, else <stable_dir>/capabilities.json, else the baseline."""
    if explicit:
        return load_file(explicit), explicit
    if stable_dir:
        p = os.path.join(stable_dir, "capabilities.json")
        if os.path.isfile(p):
            try:
                return load_file(p), p
            except (OSError, ValueError):
                pass
    return baseline(), BASELINE


def capability_content(m: dict) -> dict:
    return {k: v for k, v in m.items() if k not in IGNORED_FOR_HASH}


def capability_hash(m: dict) -> str:
    text = json.dumps(capability_content(m), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def flatten(m: dict, prefix: str = "") -> dict:
    """{dotted key: value} for every leaf; a list is a leaf."""
    out = {}
    for k, v in m.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
        else:
            out[key] = v
    return out


def added_keys(old: dict, new: dict) -> list[str]:
    """Dotted keys (and 'list:value' entries) that the new manifest has and the old one lacks or has turned off."""
    a, b = flatten(capability_content(old)), flatten(capability_content(new))
    out = []
    for k, v in sorted(b.items()):
        ov = a.get(k)
        if isinstance(v, list):
            for item in v:
                if not isinstance(ov, list) or item not in ov:
                    out.append(f"{k}:{item}")
        elif v is True and ov is not True:
            out.append(k)
        elif ov != v and not isinstance(v, bool) and k != "schemaVersion":
            out.append(f"{k}={v}")
    if new.get("schemaVersion") != old.get("schemaVersion"):
        out.append(f"schemaVersion={new.get('schemaVersion')}")
    return out


class Manifest:
    def __init__(self, data: dict, source: str = ""):
        self.data = data
        self.source = source

    @property
    def schema_version(self) -> int:
        return int(self.data.get("schemaVersion", 3))

    def get(self, path: str, default=None):
        cur = self.data
        for part in path.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    def has(self, path: str) -> bool:
        v = self.get(path)
        if isinstance(v, bool):
            return v
        if isinstance(v, (list, dict)):
            return len(v) > 0
        return v is not None

    def lists(self, path: str, value) -> bool:
        v = self.get(path)
        return isinstance(v, list) and value in v

    def clip_kind(self, kind: str) -> bool:
        return self.lists("clipKinds", kind)

    def key_prop(self, prop: str) -> bool:
        return self.lists("keyframes.props", prop)

    def ease(self, name: str) -> bool:
        return self.lists("keyframes.eases", name)

    @property
    def hash(self) -> str:
        return capability_hash(self.data)

    # the questions S15's mapping asks; each answer is the list of manifest keys that are missing (for FALLBACKS.md and editor-gaps.md)
    def solid_missing(self, stroke: bool, shadow: bool, radii: bool, gradient: bool) -> list[str]:
        miss = []
        if not self.clip_kind("solid"):
            miss.append("clipKinds:solid")
        if stroke and not self.has("solid.stroke"):
            miss.append("solid.stroke")
        if shadow and not self.has("solid.shadow"):
            miss.append("solid.shadow")
        if radii and not self.has("solid.cornerRadii"):
            miss.append("solid.cornerRadii")
        if gradient and not self.lists("solid.fills", "gradient2"):
            miss.append("solid.fills:gradient2")
        return miss

    def text_missing(self, stroke: bool, shadow: bool, background: str | None, bg_stroke: bool, bg_shadow: bool, gradient: bool) -> list[str]:
        miss = []
        if not self.clip_kind("text"):
            miss.append("clipKinds:text")
        if stroke and not self.has("text.stroke"):
            miss.append("text.stroke")
        if shadow and not self.has("text.shadow"):
            miss.append("text.shadow")
        if background and not self.lists("text.background.modes", background):
            miss.append(f"text.background.modes:{background}")
        if background and bg_stroke and not self.has("text.background.stroke"):
            miss.append("text.background.stroke")
        if background and bg_shadow and not self.has("text.background.shadow"):
            miss.append("text.background.shadow")
        if gradient and not self.lists("text.fills", "gradient2"):
            miss.append("text.fills:gradient2")
        return miss

    def captions_missing(self, progressive: bool, emphasis: bool, box_border: bool, box_shadow: bool, cue_fades: bool) -> list[str]:
        miss = []
        if not self.clip_kind("caption"):
            miss.append("clipKinds:caption")
        if progressive and not self.lists("captions.highlightModes", "progressive"):
            miss.append("captions.highlightModes:progressive")
        if emphasis and not self.has("captions.wordEmphasis"):
            miss.append("captions.wordEmphasis")
        if box_border and not self.has("text.background.stroke"):
            miss.append("text.background.stroke")
        if box_shadow and not self.has("text.background.shadow"):
            miss.append("text.background.shadow")
        if cue_fades and not self.lists("captions.cueAnims", "fade"):
            miss.append("captions.cueAnims:fade")
        return miss


def load(stable_dir: str | None = None, explicit: str | None = None) -> Manifest:
    data, src = find(stable_dir, explicit)
    return Manifest(data, src)
