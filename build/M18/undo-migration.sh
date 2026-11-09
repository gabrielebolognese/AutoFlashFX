#!/usr/bin/env bash
# undo-migration.sh: the exact reverse of M18's moves (written by pipeline/lib/migrate.py before the first move).
# Safe to run twice: every step checks what is where. Restores the rewritten files from premigrate/ last.
cd "C:/Users/there/OneDrive/Desktop/instagramReels" || exit 1
[ -e "channels/flashfx/logs/voice-profile" ] && [ ! -e "logs/voice-profile" ] && mv "channels/flashfx/logs/voice-profile" "logs/voice-profile"
[ -e "channels/flashfx/logs/status.txt" ] && [ ! -e "logs/status.txt" ] && mv "channels/flashfx/logs/status.txt" "logs/status.txt"
[ -e "channels/flashfx/logs/runner.log" ] && [ ! -e "logs/runner.log" ] && mv "channels/flashfx/logs/runner.log" "logs/runner.log"
[ -e "channels/flashfx/logs/index-hooks" ] && [ ! -e "logs/index-hooks" ] && mv "channels/flashfx/logs/index-hooks" "logs/index-hooks"
[ -e "channels/flashfx/logs/build-sfx-map" ] && [ ! -e "logs/build-sfx-map" ] && mv "channels/flashfx/logs/build-sfx-map" "logs/build-sfx-map"
[ -e "channels/flashfx/golden" ] && [ ! -e "golden" ] && git mv "channels/flashfx/golden" "golden"
[ -e "channels/flashfx/motion-lib" ] && [ ! -e "motion-lib" ] && git mv "channels/flashfx/motion-lib" "motion-lib"
[ -e "channels/flashfx/styles" ] && [ ! -e "styles" ] && git mv "channels/flashfx/styles" "styles"
[ -e "channels/flashfx/library" ] && [ ! -e "library" ] && git mv "channels/flashfx/library" "library"
[ -e "channels/flashfx/ideas.txt" ] && [ ! -e "ideas.txt" ] && git mv "channels/flashfx/ideas.txt" "ideas.txt"
[ -d "C:/Users/there/OneDrive/Desktop/instagramReels/build/M18/premigrate" ] && cp -R "C:/Users/there/OneDrive/Desktop/instagramReels/build/M18/premigrate/." . && echo "restored the rewritten files from premigrate/"
