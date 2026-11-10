"""writer.py: the project folder (BUILD_SPEC.md S15 steps 3 to 5, M21).

Builds project.json at the manifest's schemaVersion from the finalized items, the audio, the captions and the markers, copies the
media and the fonts, and writes layers.json, FALLBACKS.md and OPEN.txt. Tracks from the bottom: the layers in z-order (tracks reused
across scenes), the baked captions, the caption track, then the audio tracks. Names a person can read ("S03 card: <text>"), label
colors (violet sprites, orange overlays, red plates), bins (Audio, Images, Sprites, Overlays, Plates), a marker at each scene start
and at the comment keyword.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import uuid

from . import audio as saudio
from . import mapper

BINS = [("bin-audio", "Audio"), ("bin-images", "Images"), ("bin-sprites", "Sprites"), ("bin-overlays", "Overlays"), ("bin-plates", "Plates")]
FONT_EXT = (".ttf", ".otf", ".woff", ".woff2")


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def rgba(c: dict | None, default=(0, 0, 0, 1)) -> dict:
    if not c:
        return {"r": default[0], "g": default[1], "b": default[2], "a": default[3]}
    return {"r": c["r"], "g": c["g"], "b": c["b"], "a": c.get("a", 1)}


# ---------------------------------------------------------------------------------------------------- fonts


class Fonts:
    """The fonts the project's texts use: the editor's library (public/fonts/library/catalog.json of the stable copy, copied into fonts/) and
    the composition's own font files (source user)."""

    def __init__(self, stable_dir: str | None, own_dir: str | None, tokens: dict | None):
        self.stable_dir = stable_dir
        self.index: dict[str, dict] = {}     # family lower -> entry
        self.used: dict[tuple, dict] = {}    # (family, weight, italic) -> face record + source path
        cat = os.path.join(stable_dir, "public", "fonts", "library", "catalog.json") if stable_dir else None
        if cat and os.path.isfile(cat):
            try:
                data = json.load(open(cat, encoding="utf-8"))
                for fam in data.get("families", []):
                    self.index[fam["family"].lower()] = {"family": fam["family"], "source": "library", "files": fam.get("files", []), "root": os.path.join(stable_dir, "public", "fonts", "library")}
            except (OSError, ValueError):
                pass
        for spec in ((tokens or {}).get("fonts") or {}).values():
            fam, f = spec.get("family"), spec.get("file")
            if fam and f and own_dir and os.path.isfile(os.path.join(own_dir, f)) and fam.lower() not in self.index:
                self.index[fam.lower()] = {"family": fam, "source": "user", "files": [{"path": f, "weight": int(spec.get("weight", 400)), "style": spec.get("style", "normal")}], "root": own_dir}

    def lookup(self) -> dict:
        return self.index

    def face(self, family: str, weight: int, italic: bool) -> dict | None:
        e = self.index.get(family.lower())
        if not e:
            return None
        files = [f for f in e["files"] if f.get("subset", "latin") == "latin" or e["source"] == "user"]
        want_style = "italic" if italic else "normal"
        cands = [f for f in files if f.get("style", "normal") == want_style] or files
        best = min(cands, key=lambda f: abs(int(f.get("weight", 400)) - weight))
        key = (e["family"], int(best.get("weight", 400)), best.get("style", "normal"))
        if key not in self.used:
            name = os.path.basename(best["path"])
            self.used[key] = {"family": e["family"], "style": "Italic" if best.get("style") == "italic" else "Regular", "weight": int(best.get("weight", 400)),
                              "italic": best.get("style") == "italic", "postscriptName": os.path.splitext(name)[0], "file": name,
                              "source": e["source"], "origin": best["path"] if e["source"] == "library" else None, "_src": os.path.join(e["root"], best["path"])}
        return self.used[key]

    def write(self, project_dir: str) -> int:
        fonts_dir = os.path.join(project_dir, "fonts")
        os.makedirs(fonts_dir, exist_ok=True)
        faces = []
        for face in self.used.values():
            src = face["_src"]
            if os.path.isfile(src):
                shutil.copyfile(src, os.path.join(fonts_dir, face["file"]))
            rec = {k: v for k, v in face.items() if not k.startswith("_") and v is not None}
            faces.append(rec)
        with open(os.path.join(fonts_dir, "fonts.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump({"version": 2, "faces": faces}, f, indent=2)
        return len(faces)


# ---------------------------------------------------------------------------------------------------- project builder


class Builder:
    def __init__(self, ctx, manifest, project_dir: str, name: str, fonts: Fonts, background: str, total_frames: int):
        self.ctx = ctx
        self.m = manifest
        self.dir = project_dir
        self.name = name
        self.fonts = fonts
        self.total = total_frames
        self.bg = background
        self.media: dict[str, dict] = {}
        self.clips: dict[str, dict] = {}
        self.video_tracks: list[list[str]] = []          # clip ids per video track, bottom first
        self.video_ends: list[list[tuple[int, int, int]]] = []   # per track: (start, end, z)
        self.markers: list[dict] = []
        self.caption_tracks: dict[str, dict] = {}
        self.audio_clips: list[dict] = []
        self.baked_caption_clips: list[str] = []
        self.hidden_cc: str | None = None
        self.n = 0
        self.fallbacks: list[dict] = []
        self.counts = {"native": 0, "sprite": 0, "overlay": 0, "plate": 0, "baked_captions": 0}
        self.image_media: dict[str, str] = {}
        self.meta_generator = None
        self.audio_clip_ids: dict[int, list[str]] = {}
        self.cc_clips: list[str] = []
        self.cc_hidden = True
        self.audio_notes: list[str] = []

    def cid(self, prefix: str) -> str:
        self.n += 1
        return f"{prefix}-{self.n:04d}"

    # ------------------------------------------------------------------------------------ media
    def add_media(self, mid: str, rec: dict) -> str:
        rec.setdefault("analysis", {"thumbs": "none", "peaks": "none"})
        rec.setdefault("addedAt", now_iso())
        rec.setdefault("hasAudio", False)
        self.media[mid] = rec
        return mid

    def file_media(self, rel: str, kind: str, name: str, **extra) -> str:
        if rel in self.image_media:
            return self.image_media[rel]
        mid = f"m-{len(self.media) + 1:04d}"
        rec = {"id": mid, "kind": kind, "name": name, "file": {"relPath": rel}, "durationUs": 0 if kind == "image" else extra.pop("durationUs", 0),
               "size": os.path.getsize(os.path.join(self.dir, rel)) if os.path.isfile(os.path.join(self.dir, rel)) else 0}
        rec.update(extra)
        bins = {"image": "bin-sprites" if "/sprites/" in rel else "bin-images", "video": "bin-overlays"}
        if "/plates/" in rel:
            rec["binId"] = "bin-plates"
        elif kind in bins:
            rec["binId"] = bins[kind]
        if "/overlays/" in rel:
            rec["binId"] = "bin-overlays"
        self.add_media(mid, rec)
        self.image_media[rel] = mid
        return mid

    # ------------------------------------------------------------------------------------ tracks
    def place(self, clip: dict, z: int) -> None:
        """Put a video-track clip on the lowest track that keeps z-order: above every earlier clip it overlaps in time, on a track with no overlap."""
        start, end = clip["start"], clip["start"] + clip["duration"]
        lowest = 0
        for ti, spans in enumerate(self.video_ends):
            for s, e, _z in spans:
                if s < end and start < e:
                    lowest = max(lowest, ti + 1)
        ti = lowest
        while ti < len(self.video_tracks) and any(s < end and start < e for s, e, _z in self.video_ends[ti]):
            ti += 1
        while ti >= len(self.video_tracks):
            self.video_tracks.append([])
            self.video_ends.append([])
        clip["trackId"] = f"v{ti + 1}"
        self.video_tracks[ti].append(clip["id"])
        self.video_ends[ti].append((start, end, z))
        self.clips[clip["id"]] = clip

    # ------------------------------------------------------------------------------------ clips from items
    def base_clip(self, prefix: str, kind: str, name: str, start: int, dur: int, label: str | None = None) -> dict:
        c = {"id": self.cid(prefix), "trackId": "", "kind": kind, "name": name, "start": int(start), "duration": int(max(1, dur)), "enabled": True}
        if label:
            c["color"] = label
        return c

    def keys(self, clip: dict, res: dict) -> None:
        clip["transform"] = res["transform"]
        clip["opacity"] = res["opacity"]
        if res["keyframes"]:
            clip["keyframes"] = res["keyframes"]

    def add_native(self, item: dict, scene_label: str) -> dict:
        ctx = self.ctx
        n = item["native"]
        dur = item["end"] - item["start"]
        if item["kind"] == "solid":
            c = self.base_clip("solid", "solid", f"{scene_label} {item['layer_name']}", item["start"], dur)
            for k in ("fill", "shape", "size", "cornerRadius", "cornerRadii", "stroke", "shadow"):
                if k in n:
                    c[k] = n[k]
            c["fill"] = n["fill"]
            self.keys(c, mapper.native_motion(ctx, item))
        elif item["kind"] == "text":
            c = self.base_clip("text", "text", f"{scene_label} {item['name']}", item["start"], dur)
            c["text"] = n["text"]
            c["style"] = n["style"]
            c["fades"] = {"in": 0, "out": 0}
            self.keys(c, mapper.native_motion(ctx, item))
            self.fonts.face(n["style"]["fontFamily"], int(n["style"]["fontWeight"]), bool(n["style"]["italic"]))
        else:
            c = self.base_clip("image", "image", f"{scene_label} {item['layer_name']}", item["start"], dur)
            rel = self.copy_source(n["source"], item)
            c["mediaId"] = self.file_media(rel, "image", os.path.basename(rel), width=int(n["nw"]), height=int(n["nh"]), codec=os.path.splitext(rel)[1][1:].lower())
            c.update({"in": 0, "out": int(round(dur * 1_000_000 / ctx.fps)), "speed": 1, "crop": n["crop"], "volume": {"gainDb": 0, "muted": True}, "fades": {"in": 0, "out": 0}})
            for k in ("cornerRadius", "stroke", "shadow"):
                if k in n:
                    c[k] = n[k]
            sref = (1.0 / n["scale_x"], 1.0 / n["scale_y"])
            res, _ = mapper.key_tracks(ctx, item, lambda p: (p[0], p[1]), scale_ref=sref)
            self.keys(c, res)
        self.place(c, item["z"])
        item["clip_id"] = c["id"]
        self.counts["native"] += 1
        return c

    def copy_source(self, src: str, item: dict) -> str:
        """An image of the composition (currentSrc, a file:// URL inside the host's project) copied into media/images/."""
        path = src
        if path.startswith("file:///"):
            path = path[8:]
        path = path.split("?")[0].replace("%20", " ")
        base = re.sub(r"[^A-Za-z0-9._-]+", "-", os.path.basename(path)) or "image.png"
        rel = f"media/images/{base}"
        dst = os.path.join(self.dir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.isfile(path) and not os.path.isfile(dst):
            shutil.copyfile(path, dst)
        elif not os.path.isfile(dst):
            # not a file we can reach: the item cannot be native (the caller catches the missing file in validation)
            with open(dst, "wb") as f:
                f.write(b"")
        return rel

    def add_sprite(self, item: dict, rr: dict, scene_label: str) -> dict:
        ctx = self.ctx
        dur = item["end"] - item["start"]
        c = self.base_clip("sprite", "image", f"{scene_label} {item['layer_name']} (sprite)", item["start"], dur, "violet")
        mid = self.file_media(rr["file"], "image", os.path.basename(rr["file"]), width=rr["w"], height=rr["h"], codec="png")
        c.update({"mediaId": mid, "in": 0, "out": int(round(dur * 1_000_000 / ctx.fps)), "speed": 1, "crop": {"left": 0, "top": 0, "right": 0, "bottom": 0},
                  "volume": {"gainDb": 0, "muted": True}, "fades": {"in": 0, "out": 0}})
        self.keys(c, mapper.sprite_motion(ctx, item, rr))
        self.stand_in(c, item, "sprite")
        self.place(c, item["z"])
        item["clip_id"] = c["id"]
        self.counts["sprite"] += 1
        return c

    def add_overlay(self, item: dict, pieces: list[dict], scene_label: str, to_captions: bool = False) -> list[dict]:
        ctx = self.ctx
        out = []
        for pi, piece in enumerate(pieces):
            media = piece["media"]
            dur = piece["end"] - piece["start"]
            x0, y0, x1, y1 = piece["box"]
            name = f"{scene_label} {item['layer_name']} (overlay)" + (f" {pi + 1}" if len(pieces) > 1 else "")
            if media["type"] == "video-alpha":
                kind = "video"
                mid = self.file_media(media["file"], "video", os.path.basename(media["file"]), width=media["width"], height=media["height"], codec="vp9", alpha=True,
                                      fps={"num": int(ctx.fps), "den": 1}, durationUs=int(round(media["frames"] * 1_000_000 / ctx.fps)))
            elif media["type"] == "sequence":
                kind = "image"
                mid = self.file_media(media["file"], "image", os.path.basename(media["dir"]), width=media["width"], height=media["height"], codec="png",
                                      durationUs=int(round(media["frames"] * 1_000_000 / ctx.fps)),
                                      sequence={"dir": media["dir"], "pattern": media["pattern"], "first": media["first"], "count": media["frames"], "fps": {"num": int(ctx.fps), "den": 1}})
            else:
                kind = "image"
                mid = self.file_media(media["file"], "image", os.path.basename(media["file"]), width=media["width"], height=media["height"], codec="webp")
            c = self.base_clip("overlay", kind, name, piece["start"], dur, "orange")
            c.update({"mediaId": mid, "in": 0, "out": int(round(dur * 1_000_000 / ctx.fps)), "speed": 1, "crop": {"left": 0, "top": 0, "right": 0, "bottom": 0},
                      "volume": {"gainDb": 0, "muted": True}, "fades": {"in": 0, "out": 0},
                      "transform": {"x": round((x0 + x1) / 2.0 - ctx.W / 2.0, 3), "y": round((y0 + y1) / 2.0 - ctx.H / 2.0, 3), "scale": 1, "rotation": 0,
                                    "anchor": {"x": 0.5, "y": 0.5}, "flipH": False, "flipV": False}, "opacity": 1})
            if media["type"] == "webp":
                c["in"], c["out"] = 0, int(round(dur * 1_000_000 / ctx.fps))
            if to_captions:   # the baked captions as one alpha video on the "Captions (baked)" track
                c["name"] = f"Captions (baked) {pi + 1}" if len(pieces) > 1 else "Captions (baked)"
                self.baked_caption_clips.append(c["id"])
                self.clips[c["id"]] = c
                self.counts["baked_captions"] += 1
                self.fallbacks.append({"scene": "", "from": piece["start"], "to": piece["end"], "layer": "captions", "name": "captions", "level": "overlay", "missing": list(item.get("missing") or []),
                                       "why": ["the caption words move every frame: baked as one alpha video"]})
            else:
                self.stand_in(c, item, "overlay")
                self.place(c, item["z"])
                self.counts["overlay"] += 1
            out.append(c)
        return out

    def stand_in(self, clip: dict, item: dict, level: str) -> None:
        """fallbackOf on a sprite or an overlay that has a native equivalent in the editor's JSON, when the manifest allows it."""
        self.fallbacks.append({"scene": item["scene"], "from": item["start"], "to": item["end"], "layer": f"{item['host']}/{item['layer']}", "name": item["layer_name"],
                               "level": level, "missing": list(item.get("missing") or []), "why": list(item.get("why") or [])})
        if not self.m.has("interop.fallbackOf"):
            return
        native = item.get("stand_in")
        if native:
            clip["fallbackOf"] = {"kind": native["kind"], "reason": "; ".join(item.get("why") or ["baked"])[:200], "schemaVersion": self.m.schema_version, "data": native}

    # ------------------------------------------------------------------------------------ plates
    def add_plate(self, rel: str, start: int, end: int, name: str, in_frame: int = 0) -> dict:
        ctx = self.ctx
        dur = end - start
        mid = self.file_media(rel, "video", os.path.basename(rel), width=ctx.W, height=ctx.H, codec="h264", fps={"num": int(ctx.fps), "den": 1},
                              durationUs=int(round(((end - start) + in_frame) * 1_000_000 / ctx.fps)) + 200000)
        c = self.base_clip("plate", "video", name, start, dur, "red")
        c.update({"mediaId": mid, "in": int(round(in_frame * 1_000_000 / ctx.fps)), "out": int(round((in_frame + dur) * 1_000_000 / ctx.fps)), "speed": 1,
                  "crop": {"left": 0, "top": 0, "right": 0, "bottom": 0}, "volume": {"gainDb": 0, "muted": True}, "fades": {"in": 0, "out": 0},
                  "transform": {"x": 0, "y": 0, "scale": 1, "rotation": 0, "anchor": {"x": 0.5, "y": 0.5}, "flipH": False, "flipV": False}, "opacity": 1})
        self.place(c, 0)
        self.counts["plate"] += 1
        self.fallbacks.append({"scene": "", "from": start, "to": end, "layer": "composition", "name": name, "level": "plate", "missing": [], "why": ["the whole frame baked"]})
        return c

    # ------------------------------------------------------------------------------------ captions
    def add_baked_captions(self, states: list[dict]) -> None:
        ctx = self.ctx
        for i, s in enumerate(states):
            dur = s["end"] - s["start"]
            c = self.base_clip("cap", "image", f"Caption state {i + 1}", s["start"], dur, "violet")
            mid = self.file_media(s["file"], "image", os.path.basename(s["file"]), width=s["w"], height=s["h"], codec="png")
            c.update({"mediaId": mid, "in": 0, "out": int(round(dur * 1_000_000 / ctx.fps)), "speed": 1, "crop": {"left": 0, "top": 0, "right": 0, "bottom": 0},
                      "volume": {"gainDb": 0, "muted": True}, "fades": {"in": 0, "out": 0},
                      "transform": {"x": round((s["x0"] + s["x1"]) / 2.0 - ctx.W / 2.0, 3), "y": round((s["y0"] + s["y1"]) / 2.0 - ctx.H / 2.0, 3), "scale": 1, "rotation": 0,
                                    "anchor": {"x": 0.5, "y": 0.5}, "flipH": False, "flipV": False}, "opacity": 1})
            self.baked_caption_clips.append(c["id"])
            self.clips[c["id"]] = c
            self.counts["baked_captions"] += 1

    def add_caption_track(self, cues: list[dict], style: dict, hidden: bool, name: str = "CC") -> str:
        tid = "cc1"
        cids = []
        for cue in cues:
            c = self.base_clip("q", "caption", cue.get("name") or f"Cue {len(cids) + 1}", cue["start"], cue["duration"])
            c["text"] = cue["text"]
            if cue.get("words"):
                c["words"] = cue["words"]
            if cue.get("styleOverride"):
                c["styleOverride"] = cue["styleOverride"]
            c["trackId"] = tid
            self.clips[c["id"]] = c
            cids.append(c["id"])
        self.caption_tracks[tid] = {"style": style}
        self.hidden_cc = tid
        self.cc_clips = cids
        self.cc_hidden = hidden
        return tid

    # ------------------------------------------------------------------------------------ audio
    def add_audio(self, aud: dict) -> None:
        for mid, rec in aud["media"].items():
            rec["binId"] = "bin-audio"
            self.add_media(mid, rec)
        lanes = saudio.pack_lanes(aud["clips"])
        self.audio_lanes = lanes + 1
        self.audio_clip_ids: dict[int, list[str]] = {}
        for ac in sorted(aud["clips"], key=lambda c: (c["lane"], c["start"])):
            c = {"id": ac["id"], "trackId": f"a{ac['lane'] + 1}", "kind": "audio", "name": ac["name"], "start": ac["start"], "duration": ac["duration"], "enabled": True,
                 "color": ac.get("label", "green"), "mediaId": ac["mediaId"], "in": ac["in"], "out": ac["out"], "speed": 1,
                 "transform": {"x": 0, "y": 0, "scale": 1, "rotation": 0, "anchor": {"x": 0.5, "y": 0.5}, "flipH": False, "flipV": False}, "opacity": 1,
                 "crop": {"left": 0, "top": 0, "right": 0, "bottom": 0}, "volume": {"gainDb": ac["gain_db"], "muted": False}, "fades": {"in": 0, "out": ac.get("fade_out", 0)}}
            self.clips[c["id"]] = c
            self.audio_clip_ids.setdefault(ac["lane"], []).append(c["id"])

    # ------------------------------------------------------------------------------------ the document
    def project(self, settings_extra: dict | None = None, generator: dict | None = None) -> dict:
        ctx = self.ctx
        bgc = tuple(int(self.bg.lstrip("#")[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
        tracks = []
        for ti, ids in enumerate(self.video_tracks):
            ids = sorted(ids, key=lambda i: self.clips[i]["start"])
            tracks.append({"id": f"v{ti + 1}", "kind": "video", "name": f"V{ti + 1}", "clipIds": ids, "locked": False, "muted": False, "solo": False, "hidden": False,
                           "targeted": True, "height": "M"})
        if self.baked_caption_clips:
            ti = len(tracks)
            for cid in self.baked_caption_clips:
                self.clips[cid]["trackId"] = f"v{ti + 1}"
            tracks.append({"id": f"v{ti + 1}", "kind": "video", "name": "Captions (baked)", "clipIds": sorted(self.baked_caption_clips, key=lambda i: self.clips[i]["start"]),
                           "locked": False, "muted": False, "solo": False, "hidden": False, "targeted": False, "height": "S"})
        if self.hidden_cc:
            tracks.append({"id": self.hidden_cc, "kind": "caption", "name": "Captions", "clipIds": sorted(self.cc_clips, key=lambda i: self.clips[i]["start"]), "locked": False,
                           "muted": False, "solo": False, "hidden": bool(self.cc_hidden), "targeted": False, "height": "S"})
        for lane in sorted(self.audio_clip_ids):
            ids = sorted(self.audio_clip_ids[lane], key=lambda i: self.clips[i]["start"])
            nm = "Voice" if lane == 0 else f"SFX {lane}"
            tracks.append({"id": f"a{lane + 1}", "kind": "audio", "name": nm, "clipIds": ids, "locked": False, "muted": False, "solo": False, "hidden": False,
                           "targeted": True, "height": "M"})
        used_bins = {m.get("binId") for m in self.media.values()}
        settings = {"width": ctx.W, "height": ctx.H, "fps": {"num": int(ctx.fps), "den": 1}, "background": {"r": round(bgc[0], 4), "g": round(bgc[1], 4), "b": round(bgc[2], 4), "a": 1},
                    "sampleRate": 48000}
        if self.m.has("audio.loudness"):
            settings["loudness"] = {"enabled": True, "targetLufs": -14, "truePeakDb": -1.5}
        if settings_extra:
            settings.update(settings_extra)
        meta = {"createdAt": now_iso(), "modifiedAt": now_iso(), "appVersion": str(self.m.get("appVersion", "1.1.0"))}
        if generator and self.m.has("interop.generatorMeta"):
            meta["generator"] = generator
        doc = {"schemaVersion": self.m.schema_version, "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "instagramreels/" + self.name)), "name": self.name, "settings": settings,
               "media": self.media, "bins": [{"id": i, "name": n} for i, n in BINS if i in used_bins], "tracks": tracks, "clips": self.clips,
               "markers": sorted(self.markers, key=lambda m: m["frame"]), "captionTracks": self.caption_tracks, "textPresetsLocal": [], "meta": meta}
        return doc


def fallbacks_md(fallbacks: list[dict], counts: dict, manifest_source: str, schema_version: int) -> str:
    lines = ["# Fallbacks", "",
             f"Written by S15 against the editor manifest {manifest_source} (schemaVersion {schema_version}).",
             f"Native layers: {counts.get('native', 0)}. Baked: {counts.get('sprite', 0)} sprites, {counts.get('overlay', 0)} overlays, {counts.get('plate', 0)} plates, "
             f"{counts.get('baked_captions', 0)} baked caption images.", "",
             "Every baked layer with the manifest key the editor lacks (a layer that is baked only because its look changes continuously has no missing key).", "",
             "| scene | frames | layer | level | missing manifest key | why |", "| --- | --- | --- | --- | --- | --- |"]
    for f in fallbacks:
        lines.append(f"| {f['scene'] or '-'} | {f['from']}-{f['to']} | {f['name']} | {f['level']} | {', '.join(f['missing']) or '-'} | {'; '.join(f['why'])[:120] or '-'} |")
    return "\n".join(lines) + "\n"


def open_txt(editor_url: str, rel_project: str, folder_abs: str) -> str:
    return (f"Open this project in the Shorts Editor.\n\nLink: {editor_url.rstrip('/')}/?open={rel_project}\n"
            "(first choose this instagramReels folder as the editor's projects folder; then the link opens the project)\n\n"
            f"Or use Open project in the editor and pick this folder: {folder_abs}\n")
