"""Finite 24h observation only. No game refresh, QQ message, cron or timer."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import signal
import sys
import threading
import time

if __package__:
    from . import observe
else:
    import observe

DURATION_SECONDS = 86400
INTERVAL_SECONDS = 300
FINAL_MARGIN_SECONDS = 2
DEADLINE_MARGIN_SECONDS = 60
MAX_SAMPLES = 289


def times(timestamp):
    utc = datetime.fromtimestamp(timestamp, timezone.utc)
    return {'utc': utc.isoformat(),
            'asia_shanghai': utc.astimezone(timezone(timedelta(hours=8))).isoformat()}


def write_once(path, data):
    observe.secure_parent(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=True, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def plan(collection_mode):
    label = observe.mode_label(collection_mode)
    if collection_mode == 'unverified':
        raise observe.ObservationError('explicit_window_mode_required')
    return {'duration_seconds': DURATION_SECONDS, 'interval_seconds': INTERVAL_SECONDS,
            'max_samples': MAX_SAMPLES, 'final_offset_seconds': DURATION_SECONDS + FINAL_MARGIN_SECONDS,
            'hard_deadline_offset_seconds': DURATION_SECONDS + DEADLINE_MARGIN_SECONDS,
            'max_log_bytes': observe.MAX_BYTES, 'collection_mode': label,
            'restart': False, 'stability_pass': 'requires_operator_review'}


def run_window(log, collection_mode, private_paths=(), *, clock=time.monotonic,
               wall_clock=time.time, wait=None, collector=observe.collect,
               stop_event=None, max_bytes=observe.MAX_BYTES):
    configuration = plan(collection_mode)
    observe.secure_parent(log)
    if log.exists() or log.is_symlink():
        raise observe.ObservationError('observation_log_already_exists')
    stopped = stop_event if stop_event is not None else threading.Event()
    wait = wait if wait is not None else stopped.wait
    started = clock()
    started_wall = wall_clock()
    begin = times(started_wall)
    hard_deadline = started + configuration['hard_deadline_offset_seconds']
    configuration.update({'started_timestamp': started_wall, 'started_utc': begin['utc'],
                          'started_asia_shanghai': begin['asia_shanghai'],
                          'hard_deadline_timestamp': started_wall + configuration['hard_deadline_offset_seconds']})
    write_once(log.parent / 'window-plan.json', configuration)
    status = 'completed_window'
    count = failures = attempts = 0
    error = None
    for index in range(MAX_SAMPLES):
        target = started + index * INTERVAL_SECONDS
        if index == MAX_SAMPLES - 1:
            target += FINAL_MARGIN_SECONDS
        if stopped.is_set():
            status = 'stopped_by_signal'
            break
        delay = target - clock()
        if delay > 0:
            wait(delay)
        if stopped.is_set():
            status = 'stopped_by_signal'
            break
        if clock() >= hard_deadline:
            status = 'deadline_exceeded'
            break
        sample_started = started_wall if index == 0 else wall_clock()
        attempts += 1
        try:
            row = collector(private_paths, collection_mode)
        except Exception:
            # Retain failed attempts; never persist exception text or partial payloads.
            failures += 1
            row = {'schema': 1, 'host': {}, 'units': {}, 'http': {}, 'private_paths': [],
                   'listeners': [], 'sample_error': 'collection_failed',
                   'qq_functional_health': 'not_measured'}
        row.update({'timestamp': sample_started, 'sample_finished_timestamp': wall_clock(),
                    'window_sample_index': index, 'collection_mode': configuration['collection_mode']})
        try:
            observe.append_sample(log, row, max_bytes=max_bytes)
            count += 1
        except (observe.ObservationError, OSError) as exc:
            error = str(exc) if isinstance(exc, observe.ObservationError) else 'log_write_failed'
            status = 'log_limit' if error == 'log_limit' else 'log_write_failed'
            break
        if clock() >= hard_deadline:
            status = 'deadline_exceeded'
            break
    end_wall = wall_clock()
    end = times(end_wall)
    result = {'status': status, 'collection_mode': configuration['collection_mode'],
              'sample_count': count, 'attempted_samples': attempts, 'failed_samples': failures,
              'started_timestamp': started_wall, 'started_utc': begin['utc'],
              'started_asia_shanghai': begin['asia_shanghai'],
              'finished_timestamp': end_wall, 'finished_utc': end['utc'],
              'finished_asia_shanghai': end['asia_shanghai'],
              'hard_deadline_timestamp': configuration['hard_deadline_timestamp'],
              'elapsed_monotonic_seconds': clock() - started, 'last_error': error,
              'stability_pass': 'requires_operator_review'}
    if count:
        rows = [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines() if line]
        result['summary'] = observe.summarize(rows)
    write_once(log.parent / 'window-result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    preview = commands.add_parser('plan', help='Print bounded schedule without sampling or writes')
    preview.add_argument('--collection-mode', choices=('manual_only', 'periodic'), required=True)
    run = commands.add_parser('run')
    run.add_argument('--log', type=Path, required=True)
    run.add_argument('--collection-mode', choices=('manual_only', 'periodic'), required=True)
    run.add_argument('--private-path', type=Path, action='append', default=[])
    args = parser.parse_args()
    try:
        if args.command == 'plan':
            print(json.dumps(plan(args.collection_mode)))
            return 0
        if sys.platform != 'linux':
            raise observe.ObservationError('linux_required')
        stopped = threading.Event()
        for signum in (signal.SIGTERM, signal.SIGINT):
            signal.signal(signum, lambda *_: stopped.set())
        result = run_window(args.log, args.collection_mode, args.private_path, stop_event=stopped)
        print(json.dumps({key: result[key] for key in ('status', 'sample_count', 'failed_samples',
                                                      'started_utc', 'finished_utc', 'collection_mode')}))
        return 0 if result['status'] in ('completed_window', 'stopped_by_signal') else 1
    except (observe.ObservationError, OSError, ValueError, KeyError) as exc:
        code = str(exc) if isinstance(exc, observe.ObservationError) else 'window_unavailable'
        print(json.dumps({'error': code}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
