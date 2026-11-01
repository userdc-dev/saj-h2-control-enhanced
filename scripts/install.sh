#!/usr/bin/env bash
# SAJ H2 Control Enhanced: code-only installation, no configuration.yaml edits.
# Usage: bash scripts/install.sh /path/to/homeassistant/config [--with-safe-monitor]
set -euo pipefail
if [[ $# -lt 1 || $# -gt 2 || ! -d "$1" ]]; then
  echo "Usage: bash scripts/install.sh /path/to/homeassistant/config [--with-safe-monitor]" >&2
  exit 2
fi
HA_CONFIG="$(cd "$1" && pwd -P)"
if [[ $# -eq 2 && "$2" != "--with-safe-monitor" ]]; then
  echo "Unsupported option: $2" >&2
  exit 2
fi
for program in curl tar mktemp cp; do
  command -v "$program" >/dev/null || { echo "Missing required tool: $program" >&2; exit 1; }
done
mkdir -p "$HA_CONFIG/custom_components"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

install_component() {
  local repo="$1" domain="$2" update_existing="$3"
  local dest="$HA_CONFIG/custom_components/$domain"
  if [[ -d "$dest" && "$update_existing" == "no" ]]; then
    echo "Preserving existing independent $domain integration (no overwrite)."
    return
  fi
  local archive="$tmp/$domain.tar.gz" unpack="$tmp/$domain-unpack"
  mkdir -p "$unpack"
  curl --fail --location --silent --show-error \
    "https://github.com/userdc-dev/$repo/archive/refs/heads/main.tar.gz" \
    --output "$archive"
  tar -xzf "$archive" -C "$unpack"
  local source="$unpack/$repo-main/custom_components/$domain"
  if [[ ! -f "$source/manifest.json" || ! -f "$source/__init__.py" ]]; then
    echo "Invalid download: $domain is missing manifest.json or __init__.py" >&2
    exit 1
  fi
  if [[ -d "$dest" ]]; then
    local backup_dir="$HA_CONFIG/.saj-h2-backups/$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$backup_dir"
    cp -a "$dest" "$backup_dir/$domain"
    echo "Backed up installed $domain code to $backup_dir/$domain"
  fi
  mkdir -p "$dest"
  cp -a "$source/." "$dest/"
  echo "Installed $domain from $repo."
}

install_component "saj-h2-control-enhanced" "saj_h2_control_enhanced" "yes"
if [[ "${2:-}" == "--with-safe-monitor" ]]; then
  # The separate safe monitor is read-only and must not be overwritten;
  # this option installs it ONLY if it does not already exist.
  install_component "saj-h2-safe-enhanced" "saj_h2_safe" "no"
fi
echo
echo "Installation files copied. Restart Home Assistant using its normal service/UI."
echo "Next: Settings → Devices & services → Add integration → SAJ H2 Control Enhanced."
echo "Choose an existing SAJ Safe Monitor source, or enter the inverter's Modbus IP/port."
echo "The integration itself registers its card and SAJ H2 Control dashboard."
echo "NO configuration.yaml, Lovelace YAML, or manual JS resource editing is required."
echo "The Live energy section needs the separate SAJ H2 Safe Enhanced integration."
echo "If you used --with-safe-monitor and it was newly installed, also add it via the HA UI."
echo "Backed-up code cannot roll back settings already written to the inverter."
