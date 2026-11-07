

# ------------------------------------------------------------------------------------------------ text on screen (E4, M15)

# The size in px of the text each library component draws, as its own file sets it (motion-lib/compositions/*.html and
# assets/paper-cards.css): E4 wants every graphic text at the caption size (67 px) or more. These sizes are baked into
# the components; terminal-card's and strike-through's font_px props are the plan's own choice ("explicit").
BAKED_TEXT_PX = {
    ("card", "title"): 44, ("card", "body"): 34, ("fly-in", "title"): 44, ("fly-in", "body"): 34,
    ("window-card", "title"): 30, ("window-card", "lines_json"): 32, ("terminal-card", "lines_json"): 30,
    ("chat-card", "prompt"): 30, ("chat-card", "reply"): 30, ("chart-card", "title"): 36, ("chart-card", "values_json"): 28,
    ("table-card", "title"): 36, ("table-card", "rows_json"): 30, ("check-badge", "items_json"): 34,
    ("dark-chip", "text"): 28, ("light-chip", "text"): 30, ("progress-bar", "label"): 30,
    ("stat-number", "unit"): 44, ("stat-number", "sub_label"): 28, ("strike-through", "text"): 30, ("strike-through", "replacement"): 30,
    ("handwritten-callout", "text"): 58, ("speech-bubble", "text"): 44, ("speech-bubble", "keyword"): 56,
    ("dm-card", "message"): 32, ("dm-card", "sender"): 36, ("thumb-grid", "items_json"): 26,
    ("hero-3d", "label"): 34, ("icon-3d", "label"): 34, ("pop", "text"): 48,
    ("headline", "lines_json"): 102, ("headline", "kicker"): 21, ("end-card", "verb"): 97, ("end-card", "keyword"): 98,
    ("end-card", "line1"): 58, ("end-card", "line2"): 58,
}
HONESTY_TEXT = {"mock": "illustrative", "sourced": "real"}
NO_TEXT_COMPONENTS = ("paper-canvas", "caption-line", "caption-word", "caption-group", "camera-move", "exit-move", "mascot", "logo-tile")


def _strs(v) -> list[str]:
    """The texts inside a structured prop: a list of strings, or of {text|label|name|value|title} dicts."""
    out: list[str] = []
    for item in _lines(v):
        if isinstance(item, dict):
            for k in ("text", "label", "name", "value", "title"):
                if isinstance(item.get(k), str) and item[k].strip():
                    out.append(item[k])
        elif isinstance(item, str) and item.strip():
            out.append(item)
    return out


def text_items(component: str, props: dict, toks: dict | None = None) -> list[dict]:
    """The non-caption text a component instance shows: [{prop, text, chars, px, explicit}], px the font size the component
    draws it at (BAKED_TEXT_PX, or the plan's own font_px) and `explicit` when the plan chose that size. A number (the
    stat's digits) is a graphic and does not count; honesty labels do (they are chips)."""
    if component in NO_TEXT_COMPONENTS:
        return []
    out: list[dict] = []

    def add(prop: str, text: str, px=None, explicit=False):
        t = str(text).replace("*", "").strip()
        if t:
            out.append({"prop": prop, "text": t, "chars": len(t), "px": px, "explicit": explicit})

    for k, v in props.items():
        if isinstance(v, str) and v.strip() and (k in TITLE_PROPS or k in BODY_PROPS):
            if component == "terminal-card" and k == "prompt":
                continue
            if component == "dm-card" and k in ("app_label", "time_label"):
                continue
            px = BAKED_TEXT_PX.get((component, k))
            explicit = False
            if component == "strike-through" and k in ("text", "replacement") and not props.get("chip", True) and props.get("font_px"):
                px, explicit = _num(props, "font_px", 48), True
            add(k, v, px, explicit)
    for k in ("lines_json", "items_json", "rows_json", "values_json"):
        if k not in props:
            continue
        if component == "headline" and k == "lines_json":
            texts = [str(ln) for ln in _lines(props.get(k))]
        elif component == "table-card" and k == "rows_json":
            texts = [str(val) for r in _lines(props.get(k)) if isinstance(r, dict) for val in r.values() if isinstance(val, str)]
        elif component in ("chart-card", "thumb-grid") and k in ("values_json", "items_json"):
            texts = [str(d.get("label")) for d in _lines(props.get(k)) if isinstance(d, dict) and d.get("label")]
        else:
            texts = _strs(props.get(k))
        px = BAKED_TEXT_PX.get((component, k))
        explicit = False
        if component == "terminal-card" and k == "lines_json":
            px, explicit = _num(props, "font_px", 30), "font_px" in props
        for t in texts:
            add(k, t, px, explicit)
    h = props.get("honesty")
    if h in HONESTY_TEXT:
        label = ((toks or {}).get("honesty_labels") or {}).get("texts", {}).get(h, HONESTY_TEXT[h])
        add("honesty", label, 28)
    return out


def text_chars_at(plan: dict, toks: dict | None = None, exempt_scenes: set | None = None) -> list[dict]:
    """The non-caption characters on screen over time, from the plan's instances (each visible from its start to its end):
    [{from_ms, to_ms, chars, items: [(instance, prop, chars)]}] for every stretch between two changes; the scenes in
    exempt_scenes (the CTA, whose text is the ask) are left out."""
    rows = []
    for s in plan.get("scenes", []):
        if exempt_scenes and s["id"] in exempt_scenes:
            continue
        for c in s.get("components", []):
            items = text_items(c["component"], c.get("props", {}), toks)
            if items:
                rows.append((int(c["start_ms"]), int(c["end_ms"]), c["id"], items))
    cuts = sorted({r[0] for r in rows} | {r[1] for r in rows})
    out = []
    for a, b in zip(cuts, cuts[1:]):
        live = [r for r in rows if r[0] <= a and r[1] >= b]
        if live:
            out.append({"from_ms": a, "to_ms": b, "chars": sum(i["chars"] for r in live for i in r[3]),
                        "items": [(r[2], i["prop"], i["chars"]) for r in live for i in r[3]]})
    return out


def text_windows(plan: dict, toks: dict | None = None) -> list[tuple[int, int, str]]:
    """(start_ms, end_ms, instance) of every instance that shows non-caption text: where captions must be in word mode."""
    out = []
    for s in plan.get("scenes", []):
        for c in s.get("components", []):
            if text_items(c["component"], c.get("props", {}), toks):
                out.append((int(c["start_ms"]), int(c["end_ms"]), c["id"]))
    return out
