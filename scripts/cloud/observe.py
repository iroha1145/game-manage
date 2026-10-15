"""One-shot Linux trial observation. No scheduler, credentials or response bodies."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request

try:
    import fcntl
except ImportError:  # Offline report/tests also run on Windows; collection is Linux-only.
    fcntl = None

UNITS = {
    'api': 'game-manage-cloud-trial.service',
    'proxy': 'game-manage-cloud-trial-proxy.service',
    'qq': 'game-manage-cloud-trial-qq.service',
    'lol_dashboard': 'pigeon-dashboard.service',
    'lol_sync': 'pigeon-sync.service',
    'caddy': 'caddy.service',
}
NUMERIC = {'MainPID', 'NRestarts', 'MemoryCurrent', 'MemoryPeak', 'MemoryHigh',
           'MemoryMax', 'CPUUsageNSec', 'TasksCurrent', 'TasksMax'}
PROPERTIES = NUMERIC | {'ActiveState', 'SubState', 'Result', 'UnitFileState', 'User',
                        'NoNewPrivileges', 'PrivateTmp', 'ProtectSystem', 'ProtectHome',
                        'CPUQuotaPerSecUSec'}
MAX_BYTES = 8 * 1024 * 1024
COLLECTION_MODES = ('unverified', 'manual_only', 'periodic')


class ObservationError(Exception):
    pass


def mode_label(mode):
    if mode not in COLLECTION_MODES:
        raise ObservationError('invalid_collection_mode')
    return mode if mode == 'unverified' else mode + '_operator_declared'


def parse_properties(text):
    result = {}
    for line in text.splitlines():
        key, sep, value = line.partition('=')
        if sep and key in PROPERTIES:
            result[key] = (int(value) if value.isdigit() else None) if key in NUMERIC else value
    return result


def unit_state(name):
    try:
        result = subprocess.run(['systemctl', 'show', name, '--no-pager',
                                 '--property=' + ','.join(sorted(PROPERTIES))],
                                capture_output=True, text=True, timeout=5, check=False)
        if result.returncode:
            return {'observation_error': 'systemctl_failed'}
        return parse_properties(result.stdout)
    except (OSError, subprocess.TimeoutExpired):
        return {'observation_error': 'systemctl_unavailable'}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_status(url, host, expected):
    # Fixed loopback probe URLs only; never use the machine's HTTP proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    started = time.monotonic()
    code = None
    error = None
    try:
        with opener.open(urllib.request.Request(url, headers={'Host': host}), timeout=3) as response:
            code = response.status  # Do not read or log the body or headers.
    except urllib.error.HTTPError as exc:
        code = exc.code
        exc.close()
    except (OSError, urllib.error.URLError, TimeoutError):
        error = 'unreachable'
    return {'status': code, 'expected': expected, 'error': error,
            'elapsed_ms': round((time.monotonic() - started) * 1000, 2)}


def private_metadata(path):
    try:
        info = path.lstat()
        return {'mode': oct(stat.S_IMODE(info.st_mode)), 'uid': info.st_uid,
                'symlink': stat.S_ISLNK(info.st_mode),
                'owner_only': not bool(info.st_mode & 0o077), 'exists': True}
    except OSError:
        return {'exists': False, 'owner_only': None}


def collect(private_paths=(), collection_mode='unverified'):
    declared_mode = mode_label(collection_mode)
    if sys.platform != 'linux':
        raise ObservationError('linux_required')
    mem = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, _, value = line.partition(':')
        if key in {'MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree'}:
            mem[key] = int(value.split()[0]) * 1024
    try:
        result = subprocess.run(['ss', '-H', '-ltn'], capture_output=True, text=True,
                                timeout=5, check=False)
        # Only listener addresses for this trial, never process command lines.
        listeners = sorted(line.split()[3] for line in result.stdout.splitlines()
                           if len(line.split()) >= 4 and line.split()[3].rsplit(':', 1)[-1] in {'8020', '8447'})
        listener_error = None if result.returncode == 0 else 'ss_failed'
    except (OSError, subprocess.TimeoutExpired):
        listeners, listener_error = [], 'ss_unavailable'
    return {
        'schema': 1, 'timestamp': time.time(), 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'host': {'total_bytes': mem.get('MemTotal'), 'available_bytes': mem.get('MemAvailable'),
                 'swap_used_bytes': mem['SwapTotal'] - mem['SwapFree'],
                 'root_free_bytes': shutil.disk_usage('/').free, 'loadavg': list(os.getloadavg())},
        'units': {alias: unit_state(name) for alias, name in UNITS.items()},
        'listeners': listeners, 'listener_error': listener_error,
        'private_paths': [private_metadata(path) for path in private_paths],
        'http': {
            'health': http_status('http://127.0.0.1:8020/api/health', 'localhost:8447', 200),
            'anonymous': http_status('http://127.0.0.1:8020/api/identity/me', 'localhost:8447', 401),
            'internal_no_bearer': http_status('http://127.0.0.1:8020/internal/operations/health', 'localhost:8447', 401),
            'wrong_host': http_status('http://127.0.0.1:8020/api/health', 'untrusted.invalid', 403),
            'lol_dashboard_root': http_status('http://127.0.0.1:5000/', 'localhost', 302),
            'lol_sync_root': http_status('http://127.0.0.1:8901/', 'localhost', 404),
        },
        'collection_mode': declared_mode,
        'qq_functional_health': 'not_measured',
    }


def secure_parent(path):
    parent = path.parent
    if not parent.is_absolute():
        raise ObservationError('absolute_log_required')
    for ancestor in [parent, *parent.parents]:
        if ancestor.is_symlink():
            raise ObservationError('unsafe_log_directory')
    # Only create a final directory; a missing ancestor needs operator review.
    parent.mkdir(mode=0o700, exist_ok=True)
    if os.name != 'nt':
        info = parent.stat()
        if info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ObservationError('private_log_directory_required')


def append_sample(path, sample, max_bytes=MAX_BYTES):
    secure_parent(path)
    if path.is_symlink():
        raise ObservationError('unsafe_log')
    payload = (json.dumps(sample, separators=(',', ':'), ensure_ascii=True) + '\n').encode()
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(path, flags, 0o600)
    try:
        if fcntl is not None:
            fcntl.flock(fd, fcntl.LOCK_EX)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ObservationError('unsafe_log')
        if os.name != 'nt' and (info.st_uid != os.getuid() or info.st_mode & 0o077):
            raise ObservationError('private_log_required')
        if info.st_size + len(payload) > max_bytes:
            raise ObservationError('log_limit')
        with os.fdopen(fd, 'ab', closefd=False) as output:
            output.write(payload)
            output.flush()
    finally:
        os.close(fd)


def summarize(samples, max_gap_seconds=600):
    if not samples:
        raise ObservationError('no_samples')
    times = [row['timestamp'] for row in samples]
    ordered = all(a <= b for a, b in zip(times, times[1:]))
    span = times[-1] - times[0]
    gaps = [b - a for a, b in zip(times, times[1:])]
    changes = {}
    http_failures = {}
    unknown_units = 0
    bad_private_paths = 0
    listener_failures = 0
    modes = {}
    collection_errors = 0
    for row in samples:
        label = row.get('collection_mode', 'unverified')
        modes[label] = modes.get(label, 0) + 1
        collection_errors += int(bool(row.get('sample_error')))
        unknown_units += len(UNITS.keys() - row['units'].keys())
        for name, unit in row['units'].items():
            current = changes.setdefault(name, {'pid_changes': 0, 'restart_increments': 0,
                                                'restart_counter_resets': 0, 'non_running_samples': 0,
                                                'memory_max_bytes': None, 'cpu_peak_percent': None,
                                                'oom_samples': 0, 'memory_high_samples': 0})
            if unit.get('ActiveState') != 'active' or unit.get('SubState') != 'running':
                current['non_running_samples'] += 1
            if 'observation_error' in unit:
                unknown_units += 1
            memory = unit.get('MemoryCurrent')
            if memory is not None:
                current['memory_max_bytes'] = max(memory, current['memory_max_bytes'] or 0)
                high = unit.get('MemoryHigh')
                current['memory_high_samples'] += int(high is not None and memory >= high)
            current['oom_samples'] += int(unit.get('Result') == 'oom-kill')
        for name, probe in row['http'].items():
            if probe.get('status') != probe['expected']:
                http_failures[name] = http_failures.get(name, 0) + 1
        bad_private_paths += sum(path.get('owner_only') is not True or path.get('symlink', False)
                                 for path in row['private_paths'])
        # No listener evidence must remain unknown/failed, never count as secure.
        if set(row.get('listeners', [])) != {'127.0.0.1:8020', '127.0.0.1:8447'}:
            listener_failures += 1
    for before, after in zip(samples, samples[1:]):
        for name in before['units'].keys() & after['units'].keys():
            a, b = before['units'][name], after['units'][name]
            if a.get('MainPID') != b.get('MainPID'):
                changes[name]['pid_changes'] += 1
            old, new = a.get('NRestarts'), b.get('NRestarts')
            if old is not None and new is not None:
                changes[name]['restart_increments'] += max(new - old, 0)
                changes[name]['restart_counter_resets'] += int(new < old)
            cpu_a, cpu_b = a.get('CPUUsageNSec'), b.get('CPUUsageNSec')
            elapsed = after['timestamp'] - before['timestamp']
            if (cpu_a is not None and cpu_b is not None and cpu_b >= cpu_a and elapsed > 0
                    and a.get('MainPID') == b.get('MainPID') and before.get('boot_id') == after.get('boot_id')):
                percent = (cpu_b - cpu_a) / 1e9 / elapsed * 100
                changes[name]['cpu_peak_percent'] = round(max(percent, changes[name]['cpu_peak_percent'] or 0), 2)
    available = [row['host'].get('available_bytes') for row in samples]
    return {'schema': 1, 'sample_count': len(samples), 'span_seconds': span,
            'timestamps_ordered': ordered, 'max_gap_seconds': max(gaps, default=0),
            'coverage_24h': ordered and span >= 86400 and bool(gaps) and max(gaps) <= max_gap_seconds,
            'unit_changes': changes, 'http_failures': http_failures,
            'unknown_unit_samples': unknown_units, 'private_path_failures': bad_private_paths,
            'listener_failures': listener_failures,
            'collection_modes': modes, 'collection_mode_changed': len(modes) > 1,
            'collection_error_samples': collection_errors,
            'host_available_min_bytes': min((v for v in available if v is not None), default=None),
            'host_swap_used_max_bytes': max((row['host'].get('swap_used_bytes', 0) for row in samples), default=None),
            'host_root_free_min_bytes': min((row['host']['root_free_bytes'] for row in samples
                                              if row['host'].get('root_free_bytes') is not None), default=None),
            'boot_id_changes': sum(a.get('boot_id') != b.get('boot_id') for a, b in zip(samples, samples[1:])),
            'qq_functional_health': 'not_measured', 'business_e2e': 'not_measured',
            'stability_pass': 'requires_operator_review'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    sample = commands.add_parser('sample')
    sample.add_argument('--log', type=Path, help='Absolute owner-only JSONL, maximum 8 MiB; absent prints one sample')
    sample.add_argument('--private-path', type=Path, action='append', default=[])
    sample.add_argument('--collection-mode', choices=COLLECTION_MODES, default='unverified',
                        help='Operator declaration, not inferred from credentials or configuration')
    report = commands.add_parser('summarize')
    report.add_argument('--log', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'sample':
            data = collect(args.private_path, args.collection_mode)
            if args.log:
                append_sample(args.log, data)
                print(json.dumps({'sample_written': True, 'timestamp': data['timestamp']}))
            else:
                print(json.dumps(data))
        else:
            if args.log.stat().st_size > MAX_BYTES:
                raise ObservationError('log_limit')
            rows = [json.loads(line) for line in args.log.read_text().splitlines() if line]
            print(json.dumps(summarize(rows), indent=2))
    except (ObservationError, OSError, ValueError, KeyError) as exc:
        # Never echo paths, subprocess stderr, payloads or configuration errors.
        code = str(exc) if isinstance(exc, ObservationError) else 'invalid_or_unavailable_observation'
        print(json.dumps({'error': code}), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
