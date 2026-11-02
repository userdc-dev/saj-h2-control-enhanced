#!/usr/bin/env bash
# One-repo, zero-YAML installer for SAJ H2 Control Enhanced + bundled Safe Monitor.
# Usage: bash scripts/install.sh /path/to/homeassistant/config [--control-only]
set -euo pipefail
if [[ $# -lt 1 || $# -gt 2 || ! -d "$1" ]]; then
  echo "Usage: bash scripts/install.sh /path/to/homeassistant/config [--control-only]" >&2
  exit 2
fi
HA_CONFIG="$(cd "$1" && pwd -P)"
if [[ $# -eq 2 && "$2" != "--control-only" ]]; then
  echo "Unsupported option: $2" >&2
  exit 2
fi
for tool in curl tar mktemp cp; do
  command -v "$tool" >/dev/null || { echo "Missing required tool: $tool" >&2; exit 1; }
done
repo="saj-h2-control-enhanced"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
curl --fail --location --silent --show-error \
  "https://github.com/userdc-dev/$repo/archive/refs/heads/main.tar.gz" \
  --output "$tmp/repo.tar.gz"
mkdir -p "$tmp/download"
tar -xzf "$tmp/repo.tar.gz" -C "$tmp/download"
root="$tmp/download/$repo-main"
control_src="$root/custom_components/saj_h2_control_enhanced"
monitor_src="$root/bundled_components/saj_h2_safe"

# Validate all required files before changing any installation.
for item in "$control_src/manifest.json" "$control_src/__init__.py"; do
  [[ -f "$item" ]] || { echo "Incomplete controller archive: $item" >&2; exit 1; }
done
if [[ "${2:-}" != "--control-only" ]]; then
  for item in "$monitor_src/manifest.json" "$monitor_src/__init__.py" \
              "$monitor_src/const.py" "$monitor_src/sensor.py" \
              "$monitor_src/solar_forecast.py" "$monitor_src/solar_model.py"; do
    [[ -f "$item" ]] || { echo "Incomplete bundled Safe Monitor: $item" >&2; exit 1; }
  done
fi

components="$HA_CONFIG/custom_components"
mkdir -p "$components"
control_dest="$components/saj_h2_control_enhanced"
monitor_dest="$components/saj_h2_safe"

# Never modify an existing independently installed read-only monitor.
if [[ "${2:-}" != "--control-only" ]]; then
  if [[ -e "$monitor_dest" ]]; then
    echo "Existing SAJ H2 Safe Monitor detected; preserving it unchanged."
  else
    cp -a "$monitor_src" "$monitor_dest"
    echo "Installed bundled SAJ H2 Safe Monitor (read-only)."
  fi
else
  echo "Controller-only option selected; Safe Monitor left unchanged."
fi

if [[ -d "$control_dest" ]]; then
  backup="$HA_CONFIG/.saj-h2-backups/$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$backup"
  cp -a "$control_dest" "$backup/saj_h2_control_enhanced"
  echo "Backed up existing controller code: $backup/saj_h2_control_enhanced"
fi
mkdir -p "$control_dest"
cp -a "$control_src/." "$control_dest/"
echo "Installed/updated SAJ H2 Control Enhanced from THIS GitHub repository."
echo
echo "Restart Home Assistant using its normal service/UI."
echo "Open Settings → Devices & services → Add integration."
echo "1. If not already configured, add SAJ H2 Safe Monitor with your inverter IP."
echo "2. Add SAJ H2 Control Enhanced and select your monitor or enter the same IP."
echo "The SAJ TOU Control dashboard is created automatically."
echo "No configuration.yaml, Lovelace YAML or JS resource edits required."
echo "Restoring a code backup does not revert settings already written to the inverter."
