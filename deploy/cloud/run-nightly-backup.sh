#!/bin/bash
# Install beside nightly_backup.py in root-only operator directory.
set -euo pipefail
umask 077
RELEASE=$(systemctl show game-manage-cloud-trial.service -p WorkingDirectory --value)
case "$RELEASE" in /opt/game-manage-cloud-trial/releases/*) ;; *) exit 2 ;; esac
test -d "$RELEASE"
test ! -L "$RELEASE"
test -x "$RELEASE/.venv/bin/python"
cd "$RELEASE"
export PYTHONPATH="$RELEASE"
exec "$RELEASE/.venv/bin/python" /opt/game-manage-cloud-trial/operator/post24/nightly_backup.py
