import json
import threading


def runner():
    from scripts.cloud import observe_window
    return observe_window


class Clock:
    def __init__(self):
        self.elapsed = 0
    def now(self):
        return self.elapsed
    def wall(self):
        return 1000 + self.elapsed
    def wait(self, delay):
        self.elapsed += delay


def row(*args, **kwargs):
    return {'schema': 1, 'timestamp': 0, 'units': {}, 'http': {}, 'host': {},
            'private_paths': [], 'collection_mode': 'periodic_operator_declared'}


def test_window_has_289_samples_hard_deadline_and_actual_times(tmp_path):
    clock = Clock()
    log = tmp_path / 'private' / 'samples.jsonl'
    result = runner().run_window(log, 'periodic', clock=clock.now, wall_clock=clock.wall,
                                 wait=clock.wait, collector=row)
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert len(rows) == 289
    assert rows[0]['timestamp'] == 1000
    assert rows[-1]['timestamp'] == 87402
    assert rows[-1]['timestamp'] - rows[0]['timestamp'] >= 86400
    assert result['status'] == 'completed_window'
    assert result['hard_deadline_timestamp'] == 87460
    assert result['collection_mode'] == 'periodic_operator_declared'
    assert result['started_utc'].endswith('+00:00')
    assert result['started_asia_shanghai'].endswith('+08:00')


def test_sample_failure_is_retained_and_window_continues(tmp_path):
    clock = Clock()
    calls = 0
    def collect(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError('SECRET_EXCEPTION_PAYLOAD')
        return row()
    log = tmp_path / 'private' / 'samples.jsonl'
    result = runner().run_window(log, 'periodic', clock=clock.now, wall_clock=clock.wall,
                                 wait=clock.wait, collector=collect)
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert len(rows) == 289
    assert rows[1]['sample_error'] == 'collection_failed'
    assert result['failed_samples'] == 1
    assert 'SECRET' not in log.read_text()


def test_stop_and_log_limit_exit_without_unbounded_retries(tmp_path):
    clock = Clock()
    stopped = threading.Event()
    def collect(*args, **kwargs):
        stopped.set()
        return row()
    log = tmp_path / 'private' / 'samples.jsonl'
    result = runner().run_window(log, 'periodic', clock=clock.now, wall_clock=clock.wall,
                                 wait=clock.wait, collector=collect, stop_event=stopped)
    assert result['status'] == 'stopped_by_signal'
    assert result['sample_count'] == 1
    log2 = tmp_path / 'limited' / 'samples.jsonl'
    result = runner().run_window(log2, 'periodic', clock=clock.now, wall_clock=clock.wall,
                                 wait=clock.wait, collector=row, max_bytes=1)
    assert result['status'] == 'log_limit'
    assert result['sample_count'] == 0


def test_late_wake_stops_at_hard_deadline_without_catching_up(tmp_path):
    clock = Clock()
    def delayed_wait(_delay):
        clock.elapsed += 90000
    log = tmp_path / 'private' / 'samples.jsonl'
    result = runner().run_window(log, 'periodic', clock=clock.now, wall_clock=clock.wall,
                                 wait=delayed_wait, collector=row)
    assert result['status'] == 'deadline_exceeded'
    assert result['sample_count'] == 1
    assert result['summary']['coverage_24h'] is False
