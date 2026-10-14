#!/bin/bash
# Only call after operator review. No restart, --now or host reboot.
set -euo pipefail
test "$(id -u)" = 0
BASE=/opt/game-manage-cloud-trial/operator/post24
umask 077
test ! -e "$BASE/autostart-previous.json"
python3 - "$BASE/autostart-previous.json" <<'PY'
import json, subprocess, sys
units=['game-manage-cloud-trial','game-manage-cloud-trial-qq','game-manage-cloud-trial-proxy']
previous={unit:subprocess.check_output(['systemctl','is-enabled',unit],text=True).strip()
          for unit in units}
open(sys.argv[1],'x').write(json.dumps(previous)+'\n')
PY
for UNIT in game-manage-cloud-trial game-manage-cloud-trial-qq game-manage-cloud-trial-proxy; do
    test ! -e "/etc/systemd/system/$UNIT.service.d/30-post24-autostart.conf"
done
for UNIT in game-manage-cloud-trial game-manage-cloud-trial-qq game-manage-cloud-trial-proxy; do
    DROP=/etc/systemd/system/$UNIT.service.d
    test ! -e "$DROP/30-post24-autostart.conf"
    install -d -m 755 "$DROP"
    {
        printf '[Unit]\nWants=network-online.target\nAfter=network-online.target\n'
        if test "$UNIT" != game-manage-cloud-trial; then
            printf 'Wants=game-manage-cloud-trial.service\nAfter=game-manage-cloud-trial.service\n'
        fi
        printf '\n[Install]\nWantedBy=multi-user.target\n'
    } > "$DROP/30-post24-autostart.conf"
    chmod 644 "$DROP/30-post24-autostart.conf"
done
# Store diagnostics in the operator directory; do not print unit commands/config.
systemd-analyze verify game-manage-cloud-trial.service game-manage-cloud-trial-qq.service game-manage-cloud-trial-proxy.service > "$BASE/autostart-verify.log" 2>&1
systemctl daemon-reload
systemctl enable game-manage-cloud-trial.service game-manage-cloud-trial-qq.service game-manage-cloud-trial-proxy.service
systemctl show game-manage-cloud-trial game-manage-cloud-trial-qq game-manage-cloud-trial-proxy -p Id -p ActiveState -p UnitFileState -p MainPID -p NRestarts
