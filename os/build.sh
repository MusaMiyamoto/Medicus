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

# Kernel hardening (Kernel Self Protection Project recommendations that Debian supports).
HARDENING="slab_nomerge init_on_alloc=1 init_on_free=1 page_alloc.shuffle=1 randomize_kstack_offset=on \
vsyscall=none debugfs=off lockdown=integrity"

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
  --bootappend-live "boot=live components quiet splash $HARDENING \
live-config.noautologin live-config.noroot \
live-config.username=bruker live-config.hostname=medicus \
live-config.locales=nb_NO.UTF-8 live-config.keyboard-layouts=no live-config.timezone=Europe/Oslo"

# Our files: package list, hooks, desktop settings, firewall. Files on a Windows
# drive look world-writable, so reset permissions to sane values while copying.
rsync -rt --chmod=D755,F644 "$REPO/os/config/" config/

# Boot menu with Medicus branding.
cp -a /usr/share/live/build/bootloaders config/
cp "$REPO/branding/boot-splash.svg" config/bootloaders/splash.svg
sed -i 's/#76a1d0ff/#ff1a7f4b/g' config/bootloaders/syslinux_common/stdmenu.cfg

APP=config/includes.chroot/opt/medicus
mkdir -p "$APP" config/includes.chroot/usr/share/medicus
rsync -rt --chmod=D755,F644 --exclude __pycache__ \
  "$REPO/medicus" "$REPO/kalkulator" "$REPO/helsenett" "$REPO/tilgang" "$REPO/branding" \
  "$REPO/samples" "$REPO/deploy" "$REPO/requirements.txt" "$APP/"
cp "$REPO/branding/medicus-logo.svg" "$REPO/branding/wallpaper.svg" "$REPO/branding/nettleser.svg" \
  config/includes.chroot/usr/share/medicus/
cp -r "$REPO/branding/wallpapers" config/includes.chroot/usr/share/medicus/

chmod 755 config/hooks/normal/*.hook.chroot config/includes.chroot/usr/local/bin/* \
  config/includes.chroot/usr/local/lib/medicus/* config/includes.chroot/usr/local/sbin/*

lb build 2>&1 | tee build.log

ISO=$(ls -t "$WORK"/*.iso | head -1)
if [ "$OUT" != "$WORK" ]; then
  cp "$ISO" "$OUT/"
fi
echo "Ferdig: $OUT/$(basename "$ISO")"
