#!/usr/bin/env bash
# dummy.sh for 09a-animations (Visual plan, animations pass, S9a): fake outputs that validate against schema.json, for fast tests of the
# runner. No model calls. Usage: bash pipeline/stages/09a-animations/dummy.sh <run_dir>
set -u
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../lib" && pwd)"
source "$LIB/common.sh"
source "$LIB/log.sh"
source "$LIB/config.sh"
source "$LIB/state.sh"
source "$LIB/status.sh"
source "$LIB/dummy.sh"
dummy_begin "${1:?usage: dummy.sh <run_dir>}" 09a-animations plan.json
cat > "$OUT/plan.json" <<'JSON'
{"pass": "animations", "plan_version": 1, "style": "paper-cards", "idea_id": "dummy", "source": "09a-animations (dummy)", "fps": 30, "duration_ms": 30000,
 "voice": "08-voiceover/vo.wav", "solution": {"type": "none"}, "tracker": {"enabled": false},
 "branding": {"cta_scene": "s3", "dm_avatar": "brand/mark/avatar-dark.png", "lockup": "brand/lockup/lockup-gradient-on-light.png", "brand_slot": null, "flashfx_allowed_outside_cta": false},
 "scenes": [
  {"id": "s1", "beat": "b1", "beat_type": "hook", "start_ms": 0, "end_ms": 1500, "set_piece": true, "hook_set_piece": true, "honesty_label": null,
   "emphasis_hits": [{"word": "fake", "ms": 1110, "effect": "accent-box"}],
   "components": [{"id": "s1-headline-1", "component": "headline", "start_ms": 0, "end_ms": 1500, "props": {"kicker": "AI SITES", "lines_json": ["Your AI site", "*looks fake.*"]}, "role": "hero", "honesty_label": null, "assets": []}]},
  {"id": "s2", "beat": "b2", "beat_type": "stake", "start_ms": 1500, "end_ms": 27000, "set_piece": false, "hook_set_piece": false, "honesty_label": null, "emphasis_hits": [],
   "components": [{"id": "s2-card-1", "component": "card", "start_ms": 1500, "end_ms": 27000, "props": {"x": 90, "y": 560, "w": 900, "title": "Clients spot it"}, "role": "hero", "honesty_label": null, "assets": []}]},
  {"id": "s3", "beat": "b6", "beat_type": "ask", "start_ms": 27000, "end_ms": 30000, "set_piece": false, "hook_set_piece": false, "honesty_label": null, "emphasis_hits": [],
   "components": [{"id": "s3-end-card-1", "component": "end-card", "start_ms": 27000, "end_ms": 30000, "props": {"keyword": "SKILL", "lockup": "brand/lockup/lockup-gradient-on-light.png", "lockup_w": 300}, "role": "cta", "honesty_label": null, "assets": ["brand/lockup/lockup-gradient-on-light.png"]},
                  {"id": "s3-dm-card-2", "component": "dm-card", "start_ms": 27200, "end_ms": 30000, "props": {"avatar": "brand/mark/avatar-dark.png", "sender": "FlashFX", "message": "Comment SKILL and I send it"}, "role": "notification", "honesty_label": null, "assets": ["brand/mark/avatar-dark.png"]}]}
 ],
 "hook2": {"kicker": "AI SITES", "lines": ["Five AI looks", "*to avoid.*"], "set_piece": true},
 "wishlist": [], "notes": "dummy plan"}
JSON
dummy_end
