"""Exercise the pure installer renderer without executing root provisioning."""
import ast
from pathlib import Path
import re


def test_installer_substitution_does_not_expand_inserted_path_prefix_again():
    source=Path(__file__).resolve().parents[1]/'scripts/system-update-install-linux.py'
    module=ast.parse(source.read_text(encoding='utf-8'))
    # The installer intentionally refuses importing outside isolated system
    # Python. Compile only its side-effect-free renderer for this host-neutral test.
    function=next(node for node in module.body if isinstance(node,ast.FunctionDef) and node.name=='render_unit_paths')
    namespace={'re':re}
    exec(compile(ast.Module(body=[function],type_ignores=[]),str(source),'exec'),namespace)
    replacements={
        '/etc/game-manage-cloud/updater.json':'/etc/game-manage-cloud-trial/updater.managed.json',
        '/opt/game-manage-cloud':'/opt/game-manage-cloud-managed',
        '/var/lib/game-manage-updater':'/var/lib/game-manage-cloud-updater-state',
        '/var/lib/game-manage-cloud':'/var/lib/game-manage-cloud-trial/live',
        '/var/lib/game-manage-qq':'/var/lib/game-manage-cloud-trial-qq',
    }
    template='ExecStart=/usr/bin/python3 /opt/game-manage-cloud/.updater/helper/entry.py --config /etc/game-manage-cloud/updater.json\nReadWritePaths=/opt/game-manage-cloud /var/lib/game-manage-updater /var/lib/game-manage-cloud /var/lib/game-manage-qq\n'
    expected='ExecStart=/usr/bin/python3 /opt/game-manage-cloud-managed/.updater/helper/entry.py --config /etc/game-manage-cloud-trial/updater.managed.json\nReadWritePaths=/opt/game-manage-cloud-managed /var/lib/game-manage-cloud-updater-state /var/lib/game-manage-cloud-trial/live /var/lib/game-manage-cloud-trial-qq\n'
    assert namespace['render_unit_paths'](template,replacements)==expected
