#!/bin/sh
# Build the Medicus OS live ISO (Debian 13 "trixie" + XFCE desktop).
#
# Run inside Debian (WSL or a real machine) as root:
#   sudo sh os/build.sh [output-folder]
#
# The download cache is kept in /var/tmp/medicus-os, so rebuilds are much faster.
set -eu

REPO=$(cd "$(dirname "$0")/.." && pwd)
WORK=/var/tmp/medicus-os
OUT=${1:-$WORK}

if [ "$(id -u)" -ne 0 ]; then
  echo "Må kjøres som root: sudo sh os/build.sh" >&2
  exit 1
fi
command -v lb >/dev/null || { echo "Installer live-build først: apt install live-build" >&2; exit 1; }

mkdir -p "$WORK" "$OUT"
cd "$WORK"
lb clean >/dev/null 2>&1 || true
rm -rf config auto

lb config \
  --distribution trixie \
  --archive-areas "main contrib non-free-firmware" \
  --mirror-bootstrap http://deb.debian.org/debian/ \
  --mirror-binary http://deb.debian.org/debian/ \
  --security true \
  --updates true \
  --debian-installer none \
  --memtest none \
  --image-name medicus-os \
  --iso-application "Medicus OS" \
  --iso-publisher "Medicus" \
  --iso-volume "MEDICUS_OS" \
  --bootappend-live "boot=live components quiet splash \
live-config.username=bruker live-config.user-fullname=Bruker live-config.hostname=medicus \
live-config.locales=nb_NO.UTF-8 live-config.keyboard-layouts=no live-config.timezone=Europe/Oslo"

# Our files: package list, hooks, desktop settings, firewall. Files on a Windows
# drive look world-writable, so reset permissions to sane values while copying.
rsync -rt --chmod=D755,F644 "$REPO/os/config/" config/

APP=config/includes.chroot/opt/medicus
mkdir -p "$APP"
rsync -rt --chmod=D755,F644 --exclude __pycache__ \
  "$REPO/medicus" "$REPO/kalkulator" "$REPO/samples" "$REPO/deploy" "$REPO/requirements.txt" "$APP/"

chmod 755 config/hooks/normal/*.hook.chroot config/includes.chroot/usr/local/bin/*

lb build 2>&1 | tee build.log

ISO=$(ls -t "$WORK"/*.iso | head -1)
if [ "$OUT" != "$WORK" ]; then
  cp "$ISO" "$OUT/"
fi
echo "Ferdig: $OUT/$(basename "$ISO")"
