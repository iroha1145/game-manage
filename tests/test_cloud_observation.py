import json
import os

import pytest


def module():
    from scripts.cloud import observe
    return observe


def sample(timestamp, pid=10, restarts=0):
    return {'schema': 1, 'timestamp': timestamp, 'host': {'available_bytes': 100},
            'units': {'api': {'ActiveState': 'active', 'SubState': 'running',
                              'MainPID': pid, 'NRestarts': restarts}},
            'http': {'health': {'status': 200, 'expected': 200}}, 'private_paths': []}


def test_summary_does_not_claim_24h_from_sparse_or_failed_samples():
    result = module().summarize([sample(0), sample(86400)], max_gap_seconds=600)
    assert result['coverage_24h'] is False
    assert result['max_gap_seconds'] == 86400
    bad = sample(100)
    bad['http']['health']['status'] = None
    result = module().summarize([sample(0), bad])
    assert result['http_failures'] == {'health': 1}


def test_summary_detects_manual_restart_and_counter_reset():
    result = module().summarize([sample(0, 10, 2), sample(300, 20, 0)])
    assert result['unit_changes']['api']['pid_changes'] == 1
    assert result['unit_changes']['api']['restart_counter_resets'] == 1
    assert result['qq_functional_health'] == 'not_measured'


def test_24h_coverage_is_only_time_coverage_and_cpu_delta_is_bounded_by_pid():
    rows = [sample(index * 300) for index in range(289)]
    rows[0]['units']['api']['CPUUsageNSec'] = 0
    rows[1]['units']['api']['CPUUsageNSec'] = 300_000_000_000
    result = module().summarize(rows)
    assert result['coverage_24h'] is True
    assert result['unknown_unit_samples'] > 0
    assert result['stability_pass'] == 'requires_operator_review'
    assert result['unit_changes']['api']['cpu_peak_percent'] == 100
    rows[1]['units']['api']['MainPID'] = 20
    result = module().summarize(rows[:2])
    assert result['unit_changes']['api']['cpu_peak_percent'] is None


def test_log_is_bounded_and_does_not_follow_symlinks(tmp_path):
    observe = module()
    log = tmp_path / 'private' / 'samples.jsonl'
    observe.append_sample(log, sample(0), max_bytes=1000)
    assert len(log.read_text().splitlines()) == 1
    before = log.read_bytes()
    with pytest.raises(observe.ObservationError, match='log_limit'):
        observe.append_sample(log, sample(300), max_bytes=len(before))
    assert log.read_bytes() == before
    if os.name != 'nt':
        assert log.stat().st_mode & 0o777 == 0o600
        assert log.parent.stat().st_mode & 0o777 == 0o700
        link = log.parent / 'linked.jsonl'
        link.symlink_to(log)
        with pytest.raises(observe.ObservationError, match='unsafe_log'):
            observe.append_sample(link, sample(600))


def test_http_probe_does_not_follow_redirects_or_read_payload():
    import http.server
    import threading
    class Handler(http.server.BaseHTTPRequestHandler):
        calls = []
        def do_GET(self):
            self.calls.append(self.path)
            self.send_response(302)
            self.send_header('Location', '/secret')
            self.end_headers()
            self.wfile.write(b'sensitive-payload')
        def log_message(self, *args):
            pass
    server = http.server.HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = module().http_status(f'http://127.0.0.1:{server.server_port}/', 'localhost', 302)
        assert result['status'] == 302
        assert Handler.calls == ['/']
        assert 'sensitive' not in json.dumps(result)
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_systemctl_properties_are_an_allowlist():
    observe = module()
    parsed = observe.parse_properties('MainPID=2\nNRestarts=0\nEnvironment=SECRET\nExecStart=SECRET\nMemoryCurrent=[not set]\n')
    assert parsed['MainPID'] == 2
    assert parsed['MemoryCurrent'] is None
    assert 'SECRET' not in json.dumps(parsed)


def test_collection_mode_is_explicit_and_summary_preserves_mode_changes():
    observe = module()
    assert observe.mode_label('periodic') == 'periodic_operator_declared'
    assert observe.mode_label('unverified') == 'unverified'
    with pytest.raises(observe.ObservationError, match='invalid_collection_mode'):
        observe.mode_label('anything')
    rows = [sample(0), sample(300)]
    rows[0]['collection_mode'] = 'manual_only_operator_declared'
    rows[1]['collection_mode'] = 'periodic_operator_declared'
    result = observe.summarize(rows)
    assert result['collection_mode_changed'] is True
    assert result['collection_modes'] == {'manual_only_operator_declared': 1, 'periodic_operator_declared': 1}
