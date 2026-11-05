#!/bin/bash
# Audio Recorder - install / upgrade script
#
# Deploys the application as a systemd service running under a dedicated
# account, with Python dependencies in a private virtual environment:
#
#   /opt/audio-recorder/app        application code (copied from this checkout)
#   /opt/audio-recorder/.venv      virtual environment built from requirements.lock
#   /var/lib/audio-recorder        databases, secret key, backups
#   /var/log/audio-recorder        logs
#
# Usage:  ./install.sh [--fresh | --upgrade] [--yes]
#
#   --fresh     Also (re)install ALSA/udev configuration and run audio device detection
#   --upgrade   Keep existing ALSA/udev configuration (default when already installed)
#   --yes       Answer yes to all prompts (non-interactive)
#
# Requires a 64-bit OS (e.g. Raspberry Pi OS 64-bit, aarch64) and Python 3.9+.
#
# To update an installation:  git pull && ./install.sh --upgrade
#
# Run as your normal user (not root); sudo is used where needed. The script never
# deletes recordings or application data. Installations from before 1.12.0 (code
# and data under your home directory, service running as your user) are migrated.

set -euo pipefail

SERVICE_NAME="audio-recorder"
SERVICE_USER="audio-recorder"
PREFIX="/opt/audio-recorder"
APP_DIR="$PREFIX/app"
VENV_DIR="$PREFIX/.venv"
BACKUP_DIR="$PREFIX/backup"
STATE_DIR="/var/lib/audio-recorder"
LOG_DIR="/var/log/audio-recorder"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"
ASOUND_CONF="/etc/asound.conf"
UDEV_RULE="/etc/udev/rules.d/85-usb-audio.rules"
DEFAULT_STORAGE="/mnt/usb_recorder"
MIN_PYTHON="3.9"
PORT=5000

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_USER="$(id -un)"
CURRENT_HOME="$(getent passwd "$CURRENT_USER" | cut -d: -f6)"
LEGACY_STATE_DIR="$CURRENT_HOME/.audio-recorder"

INSTALL_MODE=""
ASSUME_YES=false
WAS_RUNNING=false
DEPS_NOTE=""
STORAGE_NOTE=""
ANALYSIS_NOTE=""
MIGRATED=false

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

section() { echo ""; echo "== $1"; }
ok()      { echo "  ✓ $1"; }
info()    { echo "  • $1"; }
warn()    { echo "  ⚠ $1"; }
die()     { echo ""; echo "❌ $1" >&2; exit 1; }

confirm() {
    # confirm "question" [default: Y|N]
    local prompt="$1" default="${2:-Y}" reply
    if [ "$ASSUME_YES" = true ]; then return 0; fi
    if [ "$default" = "Y" ]; then prompt="$prompt [Y/n] "; else prompt="$prompt [y/N] "; fi
    read -r -p "  $prompt" reply
    reply="${reply:-$default}"
    [[ "$reply" =~ ^[Yy] ]]
}

ask() {
    # ask "question" default  -> prints the answer (the default with --yes or empty input)
    local prompt="$1" default="$2" reply
    if [ "$ASSUME_YES" = true ]; then echo "$default"; return; fi
    read -r -p "  $prompt [$default]: " reply
    echo "${reply:-$default}"
}

as_service() { sudo -u "$SERVICE_USER" "$@"; }

usage() { sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'; }

rollback_and_die() {
    # Restore the previous code and virtual environment, restart, then exit
    echo ""
    warn "Rolling back to the previous version"
    if [ -d "$PREFIX/app.prev" ]; then
        sudo rm -rf "$APP_DIR" && sudo mv "$PREFIX/app.prev" "$APP_DIR"
    fi
    if [ -d "$VENV_DIR.prev" ]; then
        sudo rm -rf "$VENV_DIR" && sudo mv "$VENV_DIR.prev" "$VENV_DIR"
    fi
    if [ "$WAS_RUNNING" = true ]; then
        sudo systemctl start "$SERVICE_NAME" && ok "Previous version restarted"
    fi
    die "$1"
}

# ----------------------------------------------------------------------------
# Arguments and environment checks
# ----------------------------------------------------------------------------

while [ $# -gt 0 ]; do
    case "$1" in
        --fresh)   INSTALL_MODE="fresh" ;;
        --upgrade) INSTALL_MODE="upgrade" ;;
        --yes|-y)  ASSUME_YES=true ;;
        -h|--help) usage; exit 0 ;;
        *) usage; die "Unknown option: $1" ;;
    esac
    shift
done

echo "=========================================="
echo "Audio Recorder - Installation"
echo "=========================================="

if [ "$(id -u)" -eq 0 ]; then
    die "Run this script as your normal user, not root:  ./install.sh"
fi

[ -f "$SRC_DIR/app.py" ] && [ -f "$SRC_DIR/requirements.lock" ] \
    || die "Run install.sh from the project checkout (app.py and requirements.lock not found in $SRC_DIR)"

VERSION="$(sed -n "s/^__version__ = '\(.*\)'/\1/p" "$SRC_DIR/app.py")"
echo "  Version:   ${VERSION:-unknown}"
echo "  Source:    $SRC_DIR"
echo "  Your user: $CURRENT_USER"

EXISTING_INSTALL=false
if [ -f "$SERVICE_FILE" ] || [ -d "$APP_DIR" ] || [ -d "$LEGACY_STATE_DIR" ]; then
    EXISTING_INSTALL=true
fi

if [ -z "$INSTALL_MODE" ]; then
    if [ "$EXISTING_INSTALL" = true ] && [ "$ASSUME_YES" = true ]; then
        INSTALL_MODE="upgrade"
    elif [ "$EXISTING_INSTALL" = true ]; then
        echo ""
        echo "Existing installation detected. Choose:"
        echo "  1) Upgrade       - update code and dependencies; keep ALSA/udev configuration"
        echo "  2) Fresh install - also reinstall ALSA/udev configuration and re-detect the audio device"
        echo "Recordings, users, schedules and settings are kept either way."
        while true; do
            read -r -p "Enter your choice [1 or 2]: " choice
            case "$choice" in
                1) INSTALL_MODE="upgrade"; break ;;
                2) INSTALL_MODE="fresh"; break ;;
                *) echo "Please enter 1 or 2." ;;
            esac
        done
    else
        INSTALL_MODE="fresh"
    fi
fi
echo "  Mode:      $INSTALL_MODE"

section "Checking prerequisites"

command -v python3 >/dev/null || die "Python 3 not found:  sudo apt install python3"
PY_VERSION="$(python3 -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])')"
python3 -c "import sys; sys.exit(0 if sys.version_info >= tuple(map(int, '$MIN_PYTHON'.split('.'))) else 1)" \
    || die "Python $MIN_PYTHON or newer is required (found $PY_VERSION)"
# 64-bit only. Check the Python build rather than `uname -m`: 32-bit Raspberry Pi
# OS runs a 64-bit kernel on Pi 4/5, so uname reports aarch64 there too.
PY_BITS="$(python3 -c 'import struct; print(struct.calcsize("P") * 8)')"
[ "$PY_BITS" = 64 ] || die "A 64-bit OS is required (found a $PY_BITS-bit Python on $(uname -m)).
   Install Raspberry Pi OS (64-bit) or another 64-bit distribution."
ok "Python $PY_VERSION ($(uname -m), 64-bit)"

python3 -c "import venv, ensurepip" 2>/dev/null \
    || die "Python venv support missing:  sudo apt install python3-venv"
ok "python3-venv"

command -v ffmpeg  >/dev/null || die "FFmpeg not found:  sudo apt install ffmpeg"
ok "FFmpeg"
command -v arecord >/dev/null || die "ALSA tools not found:  sudo apt install alsa-utils"
ok "ALSA tools"
command -v systemctl >/dev/null || die "systemd is required"

echo ""
echo "sudo is needed to install the service. You may be asked for your password."
sudo -v || die "sudo access is required"

# ----------------------------------------------------------------------------
# Stop the running service
# ----------------------------------------------------------------------------

if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    section "Stopping service"
    sudo systemctl stop "$SERVICE_NAME"
    WAS_RUNNING=true
    ok "Service stopped"
fi

# ----------------------------------------------------------------------------
# Service account
# ----------------------------------------------------------------------------

section "Service account"

if id "$SERVICE_USER" >/dev/null 2>&1; then
    ok "Account '$SERVICE_USER' exists"
else
    sudo useradd --system --user-group --home-dir "$STATE_DIR" --no-create-home \
        --shell /usr/sbin/nologin --comment "Audio Recorder service" "$SERVICE_USER"
    ok "Created system account '$SERVICE_USER'"
fi

if getent group audio >/dev/null; then
    sudo usermod -aG audio "$SERVICE_USER"
    ok "'$SERVICE_USER' is in the 'audio' group"
else
    warn "No 'audio' group on this system; ALSA device access may fail"
fi

ADDED_SELF_TO_GROUP=false
if ! id -nG "$CURRENT_USER" | tr ' ' '\n' | grep -qx "$SERVICE_USER"; then
    sudo usermod -aG "$SERVICE_USER" "$CURRENT_USER"
    ADDED_SELF_TO_GROUP=true
    ok "Added '$CURRENT_USER' to the '$SERVICE_USER' group (read logs, manage recordings)"
fi

# ----------------------------------------------------------------------------
# Application code
# ----------------------------------------------------------------------------

section "Application code"

sudo mkdir -p "$PREFIX" "$BACKUP_DIR"
STAGE="$PREFIX/app.new"
sudo rm -rf "$STAGE"
sudo mkdir -p "$STAGE"
tar -C "$SRC_DIR" \
    --exclude=./.git --exclude=./tests --exclude=./.venv --exclude=./venv \
    --exclude=__pycache__ --exclude='*.pyc' --exclude=./.pytest_cache \
    -cf - . | sudo tar -C "$STAGE" --no-same-owner -xf -
sudo chown -R root:root "$STAGE"
sudo chmod -R u=rwX,go=rX "$STAGE"

if [ -d "$APP_DIR" ]; then
    sudo rm -rf "$PREFIX/app.prev"
    sudo mv "$APP_DIR" "$PREFIX/app.prev"
fi
sudo mv "$STAGE" "$APP_DIR"
ok "Installed to $APP_DIR"
[ -d "$PREFIX/app.prev" ] && info "Previous version kept at $PREFIX/app.prev"

# ----------------------------------------------------------------------------
# Python virtual environment
# ----------------------------------------------------------------------------

section "Python dependencies"

LOCK="$APP_DIR/requirements.lock"
LOCK_ID="$(sha256sum "$LOCK" | cut -d' ' -f1) python-$PY_VERSION"
MARKER="$VENV_DIR/.installed-from"

venv_current() {
    # A venv installed without numpy is never "current", so each re-run retries it
    [ -x "$VENV_DIR/bin/python" ] && "$VENV_DIR/bin/python" -c "import flask, numpy" 2>/dev/null \
        && [ -f "$MARKER" ] && [ "$(head -1 "$MARKER")" = "$LOCK_ID" ]
}

# -qq: errors only. pip's warnings here are noise for this use (e.g. deprecation
# notices about decade-old pytz wheel names it sees on the package index).
pip_venv() { sudo "$VENV_DIR/bin/python" -m pip --disable-pip-version-check --no-input -qq "$@"; }

if venv_current; then
    ok "Dependencies unchanged ($(sed -n 2p "$MARKER"))"
else
    if [ -d "$VENV_DIR" ]; then
        sudo rm -rf "$VENV_DIR.prev"
        sudo mv "$VENV_DIR" "$VENV_DIR.prev"
    fi
    sudo python3 -m venv "$VENV_DIR"
    # Exact versions, verified against the lock file's hashes. numpy must be a
    # prebuilt wheel: building it from source on a Pi takes hours.
    if pip_venv install --require-hashes --only-binary=numpy -r "$LOCK" \
            && "$VENV_DIR/bin/python" -c "import numpy" 2>/dev/null; then
        DEPS_NOTE="locked versions, hash-verified"
    else
        # numpy is only needed for audio analysis. Install everything else, still
        # hash-verified, and report that analysis is unavailable.
        warn "numpy could not be installed; installing without it"
        NO_NUMPY_LOCK="$(mktemp)"
        trap 'rm -f "$NO_NUMPY_LOCK"' EXIT
        awk '/^numpy==/ {skip=1; next} skip && /^[[:space:]]+--hash/ {next} {skip=0; print}' \
            "$LOCK" > "$NO_NUMPY_LOCK"
        pip_venv uninstall -y numpy >/dev/null 2>&1 || true
        pip_venv install --require-hashes -r "$NO_NUMPY_LOCK" \
            || rollback_and_die "Dependency install failed. Check the network connection, and that
   requirements.lock was regenerated after any change to pyproject.toml."
        DEPS_NOTE="locked versions, hash-verified, without numpy"
    fi
    printf '%s\n%s\n' "$LOCK_ID" "$DEPS_NOTE" | sudo tee "$MARKER" >/dev/null
    ok "Virtual environment ready: $DEPS_NOTE"
fi

if "$VENV_DIR/bin/python" -c "import numpy" 2>/dev/null; then
    ok "Clipping/discontinuity detection available (numpy $("$VENV_DIR/bin/python" -c 'import numpy; print(numpy.__version__)'))"
else
    ANALYSIS_NOTE="Clipping and discontinuity detection is not available on this system: numpy has no prebuilt package for Python $PY_VERSION on $(uname -m), or its download failed. Recording, scheduling and level/silence analysis work normally. Re-running ./install.sh --upgrade retries the numpy install."
    warn "Clipping/discontinuity detection not available (numpy could not be installed)"
fi

sudo "$VENV_DIR/bin/python" -m compileall -q "$APP_DIR" >/dev/null || true

# ----------------------------------------------------------------------------
# State and log directories (and migration from pre-1.12 installs)
# ----------------------------------------------------------------------------

section "Data and logs"

sudo install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0750 "$STATE_DIR" "$LOG_DIR"

# Tests on the state, log and storage directories run as root: they are not
# readable by the installing user, and a failed test would look like "missing".
if [ -d "$LEGACY_STATE_DIR" ] && ! sudo test -e "$STATE_DIR/auth.db" && ! sudo test -e "$STATE_DIR/schedule.db"; then
    info "Migrating data from $LEGACY_STATE_DIR"
    sudo cp -a "$LEGACY_STATE_DIR/." "$STATE_DIR/"
    sudo find "$STATE_DIR" -maxdepth 1 -type f -name '*.log' -exec mv -f -t "$LOG_DIR" {} +
    MIGRATED=true
    ok "Copied users, schedules, settings and backups to $STATE_DIR"
    info "The original $LEGACY_STATE_DIR was left in place; delete it once everything checks out"
elif [ -d "$LEGACY_STATE_DIR" ]; then
    info "$STATE_DIR already has data; ignoring $LEGACY_STATE_DIR"
fi

sudo chown -R "$SERVICE_USER:$SERVICE_USER" "$STATE_DIR" "$LOG_DIR"
if sudo test -e "$STATE_DIR/secret_key"; then sudo chmod 600 "$STATE_DIR/secret_key"; fi
ok "$STATE_DIR"
ok "$LOG_DIR"

# ----------------------------------------------------------------------------
# Recordings directory access
# ----------------------------------------------------------------------------

section "Recordings directory"

STORAGE="$(sudo "$VENV_DIR/bin/python" - "$STATE_DIR/schedule.db" <<'PY' 2>/dev/null || true
import sqlite3, sys
try:
    con = sqlite3.connect("file:%s?mode=ro" % sys.argv[1], uri=True)
    row = con.execute("SELECT value FROM system_config WHERE key = 'storage_path'").fetchone()
    print(row[0] if row and row[0] else "")
except Exception:
    print("")
PY
)"
STORAGE="${STORAGE:-$DEFAULT_STORAGE}"
info "Configured path: $STORAGE"

first_blocking_parent() {
    # Print the top-most existing ancestor the service account cannot traverse, if any
    local dir
    dir="$(dirname "$1")"
    while [ "$dir" != "/" ]; do
        if sudo test -d "$dir" && ! as_service test -x "$dir" 2>/dev/null; then echo "$dir"; fi
        dir="$(dirname "$dir")"
    done | tail -1
}

storage_writable() { as_service test -d "$1" -a -w "$1" -a -x "$1" 2>/dev/null; }

is_mount_permission_fs() {
    case "$(findmnt -n -o FSTYPE --target "$1" 2>/dev/null)" in
        vfat|msdos|exfat|ntfs|ntfs3|fuseblk) return 0 ;;
        *) return 1 ;;
    esac
}

fstab_note() {
    # Instructions for a FAT/exFAT/NTFS drive, whose permissions come from mount options
    local mnt fstype
    mnt="$(findmnt -n -o TARGET --target "$1")"
    fstype="$(findmnt -n -o FSTYPE --target "$1")"
    echo "Recordings drive ($fstype, mounted at $mnt) is not writable by '$SERVICE_USER'. In /etc/fstab, set the options for $mnt to include  uid=$(id -u "$SERVICE_USER"),gid=$(id -g "$SERVICE_USER"),umask=0002  (replacing any uid=/gid=/umask=), then:  sudo umount $mnt && sudo mount $mnt && sudo systemctl restart $SERVICE_NAME"
}

grant_group_access() {
    # Let the service group read and write $1 and everything in it; new files inherit the group
    sudo chgrp -R "$SERVICE_USER" "$1"
    sudo chmod -R g+rwX "$1"
    sudo find "$1" -type d -exec chmod g+s {} +
}

save_storage_setting() {
    # Store the recordings directory in the app's settings (the service is stopped here)
    as_service "$VENV_DIR/bin/python" - "$STATE_DIR/schedule.db" "$1" <<'PY' 2>/dev/null
import sqlite3, sys
con = sqlite3.connect(sys.argv[1])
con.execute("INSERT OR REPLACE INTO system_config (key, value, updated_at) "
            "VALUES ('storage_path', ?, datetime('now'))", (sys.argv[2],))
con.commit()
PY
}

relocate_storage() {
    # Move the contents of $1 into $2, make $2 usable by the service and select it
    # in Settings. Existing files in $2 are never overwritten. Returns non-zero, with
    # the reason in RELOCATE_ERROR, if nothing was moved.
    local src="$1" tgt="$2" blocker needed avail moved=0 skipped=0 entry name
    RELOCATE_ERROR=""
    tgt="${tgt%/}"
    if [[ "$tgt" != /* ]]; then
        RELOCATE_ERROR="'$tgt' is not an absolute path"; return 1
    fi
    if [ "$tgt" = "$src" ] || [[ "$tgt/" == "$src/"* ]]; then
        RELOCATE_ERROR="'$tgt' is inside the current recordings directory"; return 1
    fi
    blocker="$(first_blocking_parent "$tgt/x")"
    if [ -n "$blocker" ]; then
        RELOCATE_ERROR="'$SERVICE_USER' cannot enter $blocker either"; return 1
    fi
    if ! sudo test -e "$tgt"; then
        sudo install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 2775 "$tgt"
        ok "Created $tgt"
        if ! mountpoint -q "$tgt" && [[ "$tgt" == /mnt/* || "$tgt" == /media/* ]]; then
            info "Note: $tgt is a plain directory on the system disk, not a mounted drive"
        fi
    elif ! sudo test -d "$tgt"; then
        RELOCATE_ERROR="'$tgt' exists and is not a directory"; return 1
    fi
    if ! storage_writable "$tgt"; then
        if is_mount_permission_fs "$tgt"; then
            RELOCATE_ERROR="$(fstab_note "$tgt")"; return 1
        fi
        sudo chgrp "$SERVICE_USER" "$tgt"
        sudo chmod g+rwxs "$tgt"
        storage_writable "$tgt" || { RELOCATE_ERROR="could not make $tgt writable"; return 1; }
    fi

    if sudo test -d "$src"; then
        # Moving within one filesystem is a rename; across filesystems it copies, so check space
        if [ "$(sudo stat -c %d "$src")" != "$(sudo stat -c %d "$tgt")" ]; then
            needed="$(sudo du -sb "$src" | cut -f1)"
            avail="$(df --output=avail -B1 "$tgt" | tail -1 | tr -d ' ')"
            if [ "$needed" -gt "$avail" ]; then
                RELOCATE_ERROR="$tgt has $((avail / 1048576)) MB free, recordings need $((needed / 1048576)) MB"
                return 1
            fi
        fi
        while IFS= read -r -d '' entry; do
            name="$(basename "$entry")"
            if sudo test -e "$tgt/$name"; then
                skipped=$((skipped + 1))
                warn "Not moved (already exists in $tgt): $name"
            elif sudo mv "$entry" "$tgt/"; then
                moved=$((moved + 1))
            else
                skipped=$((skipped + 1))
            fi
        done < <(sudo find "$src" -mindepth 1 -maxdepth 1 -print0)
    fi
    grant_group_access "$tgt"
    ok "Moved $moved item(s) from $src to $tgt"

    if save_storage_setting "$tgt"; then
        ok "Settings → Storage Location is now $tgt"
    else
        warn "Could not update the storage setting; set Settings → Storage Location to $tgt"
    fi
    if [ "$skipped" -gt 0 ]; then
        STORAGE_NOTE="$skipped item(s) were left in $src because they could not be moved (see above)."
    elif sudo test -d "$src"; then
        info "$src is now empty; you can remove it:  rmdir $src"
    fi
    return 0
}

BLOCKER="$(first_blocking_parent "$STORAGE")"
if [ -n "$BLOCKER" ]; then
    warn "'$SERVICE_USER' cannot reach $STORAGE: no access to $BLOCKER"
    if confirm "Move the recordings to a directory the service can use?"; then
        TARGET="$(ask "New recordings directory" "$DEFAULT_STORAGE")"
        if relocate_storage "$STORAGE" "$TARGET"; then
            STORAGE="${TARGET%/}"
        else
            warn "Recordings not moved: $RELOCATE_ERROR"
        fi
    fi
    if [ -n "$(first_blocking_parent "$STORAGE")" ]; then
        STORAGE_NOTE="Recordings directory $STORAGE is inside $BLOCKER, which the service cannot enter. Re-run ./install.sh --upgrade to move it, or move it yourself and update Settings → Storage Location."
    fi
fi

if [ -z "$(first_blocking_parent "$STORAGE")" ]; then
    if ! sudo test -e "$STORAGE"; then
        sudo install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 2775 "$STORAGE"
        ok "Created $STORAGE"
        if ! mountpoint -q "$STORAGE" && [[ "$STORAGE" == /mnt/* || "$STORAGE" == /media/* ]]; then
            info "Note: $STORAGE is a plain directory on the system disk, not a mounted drive"
        fi
    fi

    if storage_writable "$STORAGE"; then
        ok "'$SERVICE_USER' can write to $STORAGE"
    elif is_mount_permission_fs "$STORAGE"; then
        warn "$STORAGE is on a $(findmnt -n -o FSTYPE --target "$STORAGE") drive; its permissions come from mount options"
        STORAGE_NOTE="$(fstab_note "$STORAGE")"
    else
        warn "'$SERVICE_USER' cannot write to $STORAGE"
        if confirm "Give the '$SERVICE_USER' group write access to $STORAGE and its contents?"; then
            grant_group_access "$STORAGE"
            if storage_writable "$STORAGE"; then
                ok "'$SERVICE_USER' can write to $STORAGE"
            else
                STORAGE_NOTE="Recordings directory $STORAGE is still not writable by '$SERVICE_USER'; check its permissions."
            fi
        else
            STORAGE_NOTE="Recordings directory $STORAGE is not writable by '$SERVICE_USER'. Recording will fail until it is."
        fi
    fi
fi

# ----------------------------------------------------------------------------
# ALSA, udev and device detection
# ----------------------------------------------------------------------------

section "Audio configuration"

if [ "$INSTALL_MODE" = "upgrade" ] && [ -f "$ASOUND_CONF" ]; then
    ok "Kept existing $ASOUND_CONF"
else
    sudo cp "$SRC_DIR/configs/asound.conf" "$ASOUND_CONF"
    ok "Installed $ASOUND_CONF"
fi

if [ "$INSTALL_MODE" = "upgrade" ] && [ -f "$UDEV_RULE" ]; then
    ok "Kept existing udev rule"
elif confirm "Install udev rule for consistent USB audio device numbering? (recommended)"; then
    sudo cp "$SRC_DIR/configs/85-usb-audio.rules" "$UDEV_RULE"
    if sudo udevadm control --reload-rules && sudo udevadm trigger; then
        ok "Installed udev rule"
    else
        warn "Installed udev rule; reloading udev failed (it applies after a reboot)"
    fi
else
    info "Skipped udev rule"
fi

if [ "$INSTALL_MODE" = "fresh" ]; then
    "$SRC_DIR/configure_audio.sh" || warn "Audio device detection reported a problem (see above)"
fi

# ----------------------------------------------------------------------------
# systemd service
# ----------------------------------------------------------------------------

section "systemd service"

if [ -f "$SERVICE_FILE" ] && ! cmp -s "$APP_DIR/audio-recorder.service" "$SERVICE_FILE"; then
    BACKUP="$BACKUP_DIR/audio-recorder.service.$(date +%Y%m%d-%H%M%S)"
    sudo cp "$SERVICE_FILE" "$BACKUP"
    info "Previous unit file saved to $BACKUP"
fi
sudo install -m 0644 "$APP_DIR/audio-recorder.service" "$SERVICE_FILE"
sudo systemctl daemon-reload
sudo systemctl enable --quiet "$SERVICE_NAME"
sudo systemctl start "$SERVICE_NAME"
ok "Service installed and started"

# ----------------------------------------------------------------------------
# Verify
# ----------------------------------------------------------------------------

section "Verifying"

HEALTHY=false
for _ in $(seq 1 45); do
    if "$VENV_DIR/bin/python" -c "
import sys, urllib.error, urllib.request
try:
    urllib.request.urlopen('http://127.0.0.1:$PORT/login', timeout=2)
except urllib.error.HTTPError:
    pass
except Exception:
    sys.exit(1)
" 2>/dev/null; then
        HEALTHY=true
        break
    fi
    sleep 1
done

if [ "$HEALTHY" = true ]; then
    ok "Web interface responding on port $PORT (running as '$(systemctl show -p User --value "$SERVICE_NAME")')"
else
    warn "Web interface did not respond on port $PORT"
    sudo systemctl status "$SERVICE_NAME" --no-pager -l | head -20 || true
    echo ""
    echo "  Startup output:  sudo journalctl -u $SERVICE_NAME -n 50 --no-pager"
    echo "  Errors:          sudo tail -50 $LOG_DIR/error.log"
    echo "  To roll back the code: sudo mv $APP_DIR $APP_DIR.failed && sudo mv $PREFIX/app.prev $APP_DIR && sudo systemctl restart $SERVICE_NAME"
fi

# ----------------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------------

IP_ADDR="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo ""
echo "=========================================="
if [ "$HEALTHY" = true ]; then echo "✓ Installation complete (${VERSION:-unknown})"; else echo "⚠ Installed with problems (${VERSION:-unknown})"; fi
echo "=========================================="
echo ""
echo "Web interface:  http://${IP_ADDR:-<this-host>}:$PORT   or   http://$(hostname).local:$PORT"
echo ""
echo "Locations:"
echo "  Code           $APP_DIR"
echo "  Python env     $VENV_DIR  (${DEPS_NOTE:-unchanged})"
echo "  Data           $STATE_DIR"
echo "  Logs           $LOG_DIR"
echo "  Recordings     $STORAGE"
echo ""
echo "Manage:   sudo systemctl status|restart|stop $SERVICE_NAME"
echo "Update:   cd $SRC_DIR && git pull && ./install.sh --upgrade"
echo "Customize the service with a drop-in (kept across upgrades):  sudo systemctl edit $SERVICE_NAME"

if [ "$MIGRATED" = true ]; then
    echo ""
    echo "Migrated from the previous layout. After confirming users, schedules and"
    echo "settings look right, you can remove the old copy:  rm -rf $LEGACY_STATE_DIR"
fi
if [ "$ADDED_SELF_TO_GROUP" = true ]; then
    echo ""
    echo "You were added to the '$SERVICE_USER' group. Log out and back in to read"
    echo "logs in $LOG_DIR without sudo."
fi
if [ -n "$STORAGE_NOTE" ]; then
    echo ""
    echo "⚠ ACTION NEEDED: $STORAGE_NOTE"
fi
if [ -n "$ANALYSIS_NOTE" ]; then
    echo ""
    echo "⚠ NOTICE: $ANALYSIS_NOTE"
fi
echo ""
