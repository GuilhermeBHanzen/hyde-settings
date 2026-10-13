#!/bin/sh
# Installs hyde-settings for the current user (no root).
set -eu
here=$(dirname "$(readlink -f "$0")")
lib="$HOME/.local/lib/hyde-settings"
bin="$HOME/.local/bin/hyde-settings"
layout="$HOME/.config/waybar/layouts/hyprdots/gladius.jsonc"

mkdir -p "$lib" "$HOME/.local/bin" "$HOME/.local/share/applications" "$HOME/.local/share/waybar/modules"
rm -rf "$lib/hyde_settings"
cp -r "$here/hyde_settings" "$lib/hyde_settings"
find "$lib" -name __pycache__ -type d -prune -exec rm -rf {} +
install -m 0755 "$here/data/hyde-settings" "$bin"
sed "s|@BIN@|$bin|g" "$here/data/hyde-settings.desktop.in" > "$HOME/.local/share/applications/hyde-settings.desktop"
sed "s|@BIN@|$bin|g" "$here/data/custom-hyde-settings.jsonc.in" > "$HOME/.local/share/waybar/modules/custom-hyde-settings.jsonc"
if [ -f "$layout" ]; then
    python3 "$here/tools/wire_waybar.py" "$layout"
    hyde-shell waybar --set hyprdots/gladius >/dev/null 2>&1 || pkill -SIGUSR2 waybar || true
fi
echo "hyde-settings installed: app launcher, waybar icon, or $bin"
