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
for tool in lb rsvg-convert rsync; do
  command -v "$tool" >/dev/null || { echo "Mangler $tool. Installer: apt install live-build librsvg2-bin rsync python3-pil" >&2; exit 1; }
done
python3 -c "import PIL" 2>/dev/null || { echo "Mangler Pillow. Installer: apt install python3-pil" >&2; exit 1; }

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

# Boot graphics: the boot menu background and the heartbeat start-up animation (Plymouth).
ASSETS=$(mktemp -d)
python3 "$REPO/branding/make_assets.py" "$ASSETS"
cp -a /usr/share/live/build/bootloaders config/
cp "$ASSETS/splash.svg" config/bootloaders/splash.svg
# Our boot menus (Norwegian, centered, auto-start, editing locked) replace live-build's defaults.
cp -r "$REPO/os/bootloaders/." config/bootloaders/
# GRUB: a random admin password nobody keeps, so the start command can't be edited.
GRUB_HASH=$(python3 -c "import hashlib, secrets
salt = secrets.token_bytes(32)
digest = hashlib.pbkdf2_hmac('sha512', secrets.token_bytes(32), salt, 100000, 64)
print(f'grub.pbkdf2.sha512.100000.{salt.hex().upper()}.{digest.hex().upper()}')")
sed -i "s/@GRUB_PASSWORD_HASH@/$GRUB_HASH/" config/bootloaders/grub-pc/grub.cfg
sed -i '/^insmod play$/d; /^play /d' config/bootloaders/grub-pc/config.cfg
mkdir -p config/includes.chroot/usr/share/plymouth/themes
cp -r "$ASSETS/plymouth" config/includes.chroot/usr/share/plymouth/themes/medicus
cp "$ASSETS/avatar.png" config/includes.chroot/etc/skel/.face
rm -rf "$ASSETS"

APP=config/includes.chroot/opt/medicus
mkdir -p "$APP" config/includes.chroot/usr/share/medicus
rsync -rt --chmod=D755,F644 --exclude __pycache__ \
  "$REPO/medicus" "$REPO/kalkulator" "$REPO/helsenett" "$REPO/tilgang" "$REPO/epj" "$REPO/utstyr" "$REPO/wlan" "$REPO/nettleser" "$REPO/tekst" "$REPO/branding" \
  "$REPO/samples" "$REPO/deploy" "$REPO/requirements.txt" "$APP/"
cp "$REPO/branding/medicus-logo.svg" "$REPO/branding/wallpaper.svg" "$REPO/branding/nettleser.svg" "$REPO/branding/post.svg" \
  config/includes.chroot/usr/share/medicus/
cp -r "$REPO/branding/wallpapers" config/includes.chroot/usr/share/medicus/
# Medicus Nettleser's icon, so windows and the taskbar show it.
mkdir -p config/includes.chroot/usr/share/icons/hicolor/scalable/apps
cp "$REPO/branding/nettleser.svg" config/includes.chroot/usr/share/icons/hicolor/scalable/apps/medicus-nettleser.svg
# The IT handbook, opened from IT mode (IT-håndbok).
mkdir -p config/includes.chroot/usr/share/doc/medicus
cp "$REPO/docs/IT-handbok.md" config/includes.chroot/usr/share/doc/medicus/
# Menu: Medicus names and neutral icons, other brands and command tools hidden.
python3 "$REPO/os/menu.py" config/includes.chroot

chmod 755 config/hooks/normal/*.hook.chroot config/includes.chroot/usr/local/bin/* \
  config/includes.chroot/usr/local/lib/medicus/* config/includes.chroot/usr/local/sbin/*

lb build 2>&1 | tee build.log

ISO=$(ls -t "$WORK"/*.iso | head -1)
if [ "$OUT" != "$WORK" ]; then
  cp "$ISO" "$OUT/"
fi
echo "Ferdig: $OUT/$(basename "$ISO")"
