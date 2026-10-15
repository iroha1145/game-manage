"""Pull only the latest completed cloud set; no key export or automatic pruning."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import threading
import uuid

from scripts.cloud import local_pull_remote as remote

TIMEOUT_SECONDS = 900
MAX_ARCHIVE_BYTES = remote.MAX_BYTES + 16 * 1024**2
DEFAULT_ROOT = 'C:/Zcode/game-manage-cloud-backups/data'
DEFAULT_KEY = 'C:/GPT/LOLhelper/reki2.pem'
DEFAULT_HOST = 'ubuntu@111.229.64.119'


# This read-only predicate is shared by the real NTFS walk and synthetic ACL
# tests. An elevated creator can have Administrators as its token default owner;
# that principal already has exact FullControl in the protected root policy.
CHILD_ACL_POLICY = r'''
function Test-TrustedChildAcl {
    param($Acl, [string]$UserSid, [string]$TokenOwnerSid, [bool]$AdminEnabled)
    $admin='S-1-5-32-544'
    $allowed=@($UserSid,'S-1-5-18',$admin)
    $childOwner=$Acl.GetOwner([System.Security.Principal.SecurityIdentifier]).Value
    $verifiedAdminOwner=($TokenOwnerSid -eq $admin -and $AdminEnabled -and $childOwner -eq $TokenOwnerSid)
    if($childOwner -ne $UserSid -and !$verifiedAdminOwner){return $false}
    $seen=@()
    foreach($rule in $Acl.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier])){
        $identity=$rule.IdentityReference.Value
        # OWNER RIGHTS is the descriptor's actual owner, never an invented User ACE.
        if($identity -eq 'S-1-3-4'){$identity=$childOwner}
        if($identity -notin $allowed -or $rule.AccessControlType -ne 'Allow' -or $rule.FileSystemRights -ne 'FullControl' -or $rule.PropagationFlags -ne 'None'){return $false}
        $seen+=$identity
    }
    if($UserSid -in $seen){return $true}
    return ($verifiedAdminOwner -and $TokenOwnerSid -in $seen)
}
'''


def safe_path(value):
    path = Path(value).absolute()
    for part in (path, *path.parents):
        try:
            remote.plain(part)
        except FileNotFoundError:
            pass
    return path


def prepare_root(value, *, allowed_files=()):
    """Create empty dedicated NTFS root, or fail closed on an unsafe existing ACL."""
    if os.name != 'nt':
        raise ValueError('windows_ntfs_required')
    path = safe_path(value)
    quoted = "'" + str(path).replace("'", "''") + "'"
    script = CHILD_ACL_POLICY + r'''
$ErrorActionPreference='Stop'
$p=PATH_LITERAL
$current=[System.Security.Principal.WindowsIdentity]::GetCurrent()
$sid=$current.User
$tokenOwner=$current.Owner.Value
$adminEnabled=(New-Object System.Security.Principal.WindowsPrincipal($current)).IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)
$volume=New-Object System.IO.DriveInfo([System.IO.Path]::GetPathRoot($p))
if($volume.DriveFormat -ne 'NTFS'){throw 'ntfs_required'}
$allowed=@($sid.Value,'S-1-5-18','S-1-5-32-544')
if(!(Test-Path -LiteralPath $p)){
    [System.IO.Directory]::CreateDirectory($p) | Out-Null
    $acl=New-Object System.Security.AccessControl.DirectorySecurity
    $acl.SetOwner($sid)
    $acl.SetAccessRuleProtection($true,$false)
    foreach($identity in $allowed){
        $rule=New-Object System.Security.AccessControl.FileSystemAccessRule(
            (New-Object System.Security.Principal.SecurityIdentifier($identity)),
            'FullControl','ContainerInherit,ObjectInherit','None','Allow')
        $acl.AddAccessRule($rule)
    }
    (New-Object System.IO.DirectoryInfo($p)).SetAccessControl($acl)
}
$acl=(New-Object System.IO.DirectoryInfo($p)).GetAccessControl()
if(!$acl.AreAccessRulesProtected -or $acl.GetOwner([System.Security.Principal.SecurityIdentifier]).Value -ne $sid.Value){throw 'owner_required'}
$seen=@()
foreach($rule in $acl.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier])){
    if($rule.IdentityReference.Value -notin $allowed -or $rule.AccessControlType -ne 'Allow' -or $rule.IsInherited -or $rule.FileSystemRights -ne 'FullControl' -or $rule.InheritanceFlags -ne 'ContainerInherit, ObjectInherit' -or $rule.PropagationFlags -ne 'None'){throw 'unsafe_acl'}
    $seen+=$rule.IdentityReference.Value
}
if(($seen | Select-Object -Unique).Count -ne 3){throw 'incomplete_acl'}
$queue=New-Object 'System.Collections.Generic.Queue[System.IO.DirectoryInfo]'
$queue.Enqueue((New-Object System.IO.DirectoryInfo($p)))
$count=0
while($queue.Count -gt 0){
    foreach($entry in $queue.Dequeue().GetFileSystemInfos()){
        $count++
        if($count -gt 65536 -or ($entry.Attributes -band [System.IO.FileAttributes]::ReparsePoint)){throw 'unsafe_tree'}
        $child=$entry.GetAccessControl()
        if(!(Test-TrustedChildAcl $child $sid.Value $tokenOwner $adminEnabled)){throw 'unsafe_child_acl'}
        if($entry -is [System.IO.DirectoryInfo]){$queue.Enqueue($entry)}
    }
}
'''.replace('PATH_LITERAL', quoted)
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                            capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode != 0:
        raise ValueError('secure_root_failed')
    safe_path(path)
    if not path.is_dir():
        raise ValueError('invalid_root')
    # Existing data is never chmodded or deleted. Only this dedicated tree is accepted.
    for entry in path.iterdir():
        remote.plain(entry)
        if not (remote.NAME.fullmatch(entry.name) and entry.is_dir() or
                entry.name.startswith('.pending-') and entry.is_dir() or entry.name == '.pull.lock' or
                entry.name in allowed_files and entry.is_file()):
            raise ValueError('unmanaged_local_root')
    return path


class SSHTransport:
    def __init__(self, key=DEFAULT_KEY, host=DEFAULT_HOST):
        if host != DEFAULT_HOST:
            raise ValueError('fixed_host_required')
        key = safe_path(key)
        if not key.is_file():
            raise ValueError('ssh_key_missing')
        # Windows' bundled OpenSSH avoids PATH helpers. Known-host checks are mandatory.
        executable = str(Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/OpenSSH/ssh.exe')
        self.base = [executable, '-T', '-i', str(key), '-o', 'BatchMode=yes',
                     '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=15',
                     '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=2',
                     '-o', 'IdentitiesOnly=yes', '-o', 'ForwardAgent=no', host]
        self.program = Path(remote.__file__).read_text(encoding='utf-8').encode('utf-8')

    def command(self, *args):
        return self.base + ['sudo -n /usr/bin/python3 - ' + ' '.join(shlex.quote(arg) for arg in args)]

    def latest(self):
        # Listing reads bounded metadata and stat values, never tar or database bytes.
        result = subprocess.run(self.command('list'), input=self.program, capture_output=True,
                                timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode != 0 or len(result.stdout) > remote.MAX_METADATA_BYTES:
            raise ValueError('remote_metadata_failed')
        return validate_listing(json.loads(result.stdout))

    def download(self, name, destination):
        if not remote.NAME.fullmatch(name):
            raise ValueError('invalid_set_name')
        process = subprocess.Popen(self.command('archive', name), stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        timer = threading.Timer(TIMEOUT_SECONDS, process.kill)
        timer.start()
        try:
            process.stdin.write(self.program)
            process.stdin.close()
            size = 0
            with destination.open('xb') as output:
                while chunk := process.stdout.read(1024**2):
                    size += len(chunk)
                    if size > MAX_ARCHIVE_BYTES:
                        raise ValueError('archive_size_limit')
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            if process.wait(timeout=5) != 0:
                raise ValueError('download_failed')
        finally:
            timer.cancel()
            if process.poll() is None:
                process.kill()
            process.wait()
            process.stdout.close()


def validate_listing(value):
    if value is None:
        return None
    if (not isinstance(value, dict) or not isinstance(value.get('name'), str) or
            not remote.NAME.fullmatch(value['name']) or
            type(value.get('files')) is not int or not 3 <= value['files'] <= remote.MAX_FILES or
            type(value.get('bytes')) is not int or not 0 <= value['bytes'] <= remote.MAX_BYTES):
        raise ValueError('invalid_listing')
    return {field: value[field] for field in ('name', 'files', 'bytes')}


def extract(archive, stage):
    """Never use extractall: links, special files, aliases and large archives fail closed."""
    seen, total = set(), 0
    with tarfile.open(archive, 'r:') as tar:
        for member in tar:
            relative = remote.safe_relative(member.name)
            if (not member.isfile() or member.name.casefold() in seen or len(seen) >= remote.MAX_FILES or
                    member.size < 0 or member.sparse is not None):
                raise ValueError('unsafe_archive_member')
            seen.add(member.name.casefold())
            total += member.size
            if total > remote.MAX_BYTES:
                raise ValueError('archive_size_limit')
            target = safe_path(stage / str(relative))
            target.parent.mkdir(parents=True, exist_ok=True)
            safe_path(target)
            with tar.extractfile(member) as source, target.open('xb') as output:
                left = member.size
                while left:
                    chunk = source.read(min(left, 1024**2))
                    if not chunk:
                        raise ValueError('truncated_archive')
                    output.write(chunk)
                    left -= len(chunk)
                output.flush()
                os.fsync(output.fileno())


def pull_latest(root, transport):
    root = safe_path(root)
    latest = validate_listing(transport.latest())
    if latest is None:
        return {'status': 'no_complete_set', 'key_included': False}
    destination = safe_path(root / latest['name'])
    if destination.exists():
        remote.inspect_set(destination, verify_hashes=True)
        return {'status': 'already_present', **latest, 'key_included': False}
    lock = root / '.pull.lock'
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        stage = root / ('.pending-' + uuid.uuid4().hex[:12])
        stage.mkdir(mode=0o700)
        payload = stage / 'set'
        payload.mkdir(mode=0o700)
        download = stage / 'download.tar'
        transport.download(latest['name'], download)
        if download.stat().st_size > MAX_ARCHIVE_BYTES:
            raise ValueError('archive_size_limit')
        extract(download, payload)
        report = remote.inspect_set(payload, verify_hashes=True)
        if any(report[field] != latest[field] for field in ('files', 'bytes')):
            raise ValueError('set_changed_since_listing')
        # Atomic no-overwrite rename on Windows; never delete or replace existing data.
        if os.name != 'nt':
            raise ValueError('windows_publish_required')
        safe_path(destination)
        os.rename(payload, destination)
        # Only exact, owned scratch files from this invocation are removed.
        download.unlink()
        stage.rmdir()
        return {'status': 'downloaded', 'name': latest['name'], 'files': report['files'],
                'bytes': report['bytes'], 'key_included': False}
    finally:
        os.close(descriptor)
        lock.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', default=DEFAULT_ROOT)
    parser.add_argument('--ssh-key', default=DEFAULT_KEY)
    parser.add_argument('--execute', action='store_true', help='Download latest; default is metadata only')
    args = parser.parse_args(argv)
    try:
        transport = SSHTransport(args.ssh_key)
        result = pull_latest(prepare_root(args.destination), transport) if args.execute else {
            'status': 'metadata_only', 'latest': transport.latest(), 'key_included': False}
        print(json.dumps(result))
        return 0
    except Exception:
        print('local_pull_failed', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
