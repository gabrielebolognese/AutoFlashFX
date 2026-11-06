"""pipeline/lib/motion/common.py: shared helpers of the motion library tools (M9): paths, the component files and
their declared variables, tokens.json, JSON and text files written with LF.

The library is the HyperFrames project under the channel's motion-lib/ (config paths.motion_lib): compositions/<id>.html are the
approved components, candidates/<id>.html the ones that failed the frame match, assets/ the fonts, the vendored
libraries, the shared CSS and JS, catalog.json the index, gallery/ the human-facing page, stills and frame-match.md.
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
_LIB = os.path.dirname(HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
import paths  # noqa: E402  (the one module that knows the layout: the library and the style are the channel's)
import config as reels_config  # noqa: E402
FPS = 30
CLIP_START_COMPONENTS = ("hero-3d", "icon-3d", "video-card")  # drawn from the hf-seek time: the compiler sets clip_start to the host's data-start (M16: video-card)


def setup_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass


def mixed(path: str) -> str:
    """A path in the C:/... form both Windows programs and Git Bash accept."""
    return os.path.abspath(path).replace("\\", "/")


def motion_lib_dir() -> str:
    if os.environ.get("REELS_MOTION_LIB"):
        return mixed(os.environ["REELS_MOTION_LIB"])
    paths.require_channel()
    return mixed(paths.cfg_path(reels_config.load(), "paths.motion_lib"))


def style_dir() -> str:
    if os.environ.get("REELS_STYLE_DIR"):
        return mixed(os.environ["REELS_STYLE_DIR"])
    paths.require_channel()
    return mixed(paths.cfg_path(reels_config.load(), "paths.style_dir"))


def tokens_path() -> str:
    return os.path.join(style_dir(), "tokens.json")


def read(path: str) -> str:
    with open(path, encoding="utf-8-sig") as f:
        return f.read().replace("\r\n", "\n")


def load_json(path: str):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def write_json(path: str, data, indent: int = 1) -> None:
    write_text(path, json.dumps(data, indent=indent, ensure_ascii=False) + "\n")


def tokens() -> dict:
    return load_json(tokens_path())


# ------------------------------------------------------------------------------------------------ components

DECL_RE = re.compile(r"<html\s+data-composition-variables='(?P<decl>\[.*?\])'\s*>", re.S)
TEMPLATE_RE = re.compile(r"<template>\s*(?P<inner>.*?)\s*</template>", re.S)
ROOT_ID_RE = re.compile(r'<div\s+id="root"[^>]*data-composition-id="(?P<id>[a-z0-9-]+)"')


class ComponentError(Exception):
    pass


def parse_component(path: str) -> dict:
    """The component file: its id, the declared variables (list and defaults), the template's inner HTML."""
    text = read(path)
    m = DECL_RE.search(text)
    if not m:
        raise ComponentError(f"{path}: no <html data-composition-variables='[...]'> declaration")
    try:
        decl = json.loads(m.group("decl"))
    except ValueError as exc:
        raise ComponentError(f"{path}: the variable declaration is not valid JSON: {exc}") from exc
    if "'" in m.group("decl"):
        raise ComponentError(f"{path}: an apostrophe inside the single-quoted declaration cuts the attribute short")
    t = TEMPLATE_RE.search(text)
    if not t:
        raise ComponentError(f"{path}: no <template> block")
    r = ROOT_ID_RE.search(text)
    if not r:
        raise ComponentError(f"{path}: no <div id=\"root\" data-composition-id=\"...\">")
    comp_id = r.group("id")
    file_id = os.path.splitext(os.path.basename(path))[0]
    if comp_id != file_id:
        raise ComponentError(f"{path}: data-composition-id {comp_id} differs from the file name {file_id}")
    defaults = {d["id"]: d.get("default") for d in decl if isinstance(d, dict) and "id" in d}
    return {"id": comp_id, "file": mixed(path), "declaration": decl, "defaults": defaults, "inner": t.group("inner"),
            "no_timeline": "data-no-timeline" in text, "registers": f'window.__timelines["{comp_id}"]' in text}


def component_files(lib: str | None = None) -> dict:
    """{'compositions': [paths], 'candidates': [paths]} of the library."""
    lib = lib or motion_lib_dir()
    out = {}
    for folder in ("compositions", "candidates"):
        d = os.path.join(lib, folder)
        out[folder] = sorted(mixed(os.path.join(d, f)) for f in os.listdir(d) if f.endswith(".html")) if os.path.isdir(d) else []
    return out


def catalog_path(lib: str | None = None) -> str:
    return os.path.join(lib or motion_lib_dir(), "catalog.json")


def load_catalog(lib: str | None = None) -> dict:
    return load_json(catalog_path(lib))


def frames(n: float) -> float:
    return n / FPS
