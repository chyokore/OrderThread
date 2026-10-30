"""Synthetic evaluations. Offline checks never call AI; templates contain no observed results."""
import argparse
import base64
import importlib.util
import io
import json
import tempfile
import threading
import urllib.error
import urllib.request
import uuid
import wave
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent


def dataset():
    return json.loads((ROOT / 'evaluation_cases.json').read_text(encoding='utf-8'))


def new_record(mode):
    data = dataset()
    return {'synthetic': True, 'dataset': data['label'], 'mode': mode,
            'created_utc': datetime.now(timezone.utc).isoformat(),
            'provider': None, 'model': None, 'reviewer': None,
            'cases': [{'id': c['id'], 'expected': c, 'observed': None,
                       'raw_proposal': None, 'human_corrections': None,
                       'observed_warning_indexes': None, 'missed_overlap_indexes': None,
                       'false_warning_indexes': None, 'outcome': 'not-run', 'notes': ''}
                      for c in data['cases']]}


def write_record(record):
    parent = ROOT / '.evaluation-runs'
    parent.mkdir(exist_ok=True)
    path = parent / (record['mode'] + '-' + uuid.uuid4().hex + '.json')
    with path.open('x', encoding='utf-8') as output:
        json.dump(record, output, indent=2)
    print('Local synthetic evaluation record: ' + str(path))
    return path


class Fixture:
    def __enter__(self):
        spec = importlib.util.spec_from_file_location('orderthread_evaluation', ROOT / 'OrderThread' / 'app.py')
        self.app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.app)
        self.folder = tempfile.TemporaryDirectory(prefix='orderthread-evaluation-')
        self.app.DB = Path(self.folder.name) / 'synthetic.db'
        # Fail closed if an offline evaluation accidentally attempts a provider call.
        self.guard = patch.object(self.app, 'ai_completion', side_effect=AssertionError('Offline evaluation cannot call live AI'))
        self.guard.start()
        self.server = self.app.ThreadingHTTPServer(('127.0.0.1', 0), self.app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.guard.stop(); self.folder.cleanup()

    def request(self, path, data=None):
        req = urllib.request.Request(f'http://127.0.0.1:{self.server.server_port}' + path,
                                     data=None if data is None else json.dumps(data).encode(),
                                     headers={'Content-Type': 'application/json'})
        try:
            response = urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def ok(self, path, data=None):
        status, result = self.request(path, data)
        if status != 200:
            raise AssertionError(f'{path}: expected HTTP 200, got {status}')
        return result

    def review(self, items):
        # Hand-authored text proposals test confirmation/ledger rules, not extraction.
        message = 'SYNTHETIC evaluation source'
        return self.request('/api/confirm', {'message': message,
            'proposal': {'items': [dict(i, evidence=message) for i in items]},
            'decisions': ['new'] * len(items)})

    def seed(self):
        status, review = self.review(dataset()['baseline'])
        assert status == 200
        result = self.ok('/api/apply', {'event_id': review['event_id'], 'order_id': '__new__',
                         'order_name': 'SYNTHETIC isolated evaluation', 'targets': [None], 'confirmed': True})
        return result['order_id']


def check_case(case, row):
    with Fixture() as f:
        order_id = f.seed()
        if case['kind'] == 'overlap':
            status, review = f.review(case['incoming'])
            assert status == 200
            preview = f.ok('/api/apply-preview', {'event_id': review['event_id'], 'order_id': order_id})
            observed = [m['index'] for m in preview['overlaps']]
            expected = case['expected_warning_indexes']
            row['observed_warning_indexes'] = observed
            row['missed_overlap_indexes'] = sorted(set(expected) - set(observed))
            row['false_warning_indexes'] = sorted(set(observed) - set(expected))
            assert observed == expected, 'Overlap warnings differ from labels'
            line = preview['lines'][0]['id']
            targets = [line if i in observed and case.get('resolution') in ('add', 'replace') else None
                       for i in range(len(case['incoming']))]
            payload = {'event_id': review['event_id'], 'order_id': order_id, 'targets': targets,
                       'confirmed': True, 'order_state': preview['state_token']}
            if observed:
                blocked, _ = f.request('/api/apply', payload)
                assert blocked == 400, 'Missing overlap decision must block application'
            payload['overlap_resolutions'] = {str(i): case['resolution'] for i in observed}
            f.ok('/api/apply', payload)
            actual = [i['quantity'] for i in f.ok('/api/orders')[0]['items']]
            row['observed'] = {'quantities': actual}
            assert actual == case['expected_quantities'], 'Final quantities differ'
        elif case['kind'] == 'unclear':
            status, _ = f.review(case['incoming'])
            quantity = f.ok('/api/orders')[0]['items'][0]['quantity']
            row['observed'] = {'confirmation_status': status, 'baseline_quantity': quantity}
            assert status == 400 and quantity == 10
        elif case['kind'] == 'pickup':
            # Explicit mock: one second of silence is not speech or a transcription test.
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as audio:
                audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(16000)
                audio.writeframes(b'\0\0' * 16000)
            proposal = {'transcript': case['source'], 'items': [], 'intent': 'unclear',
                        'fulfillment_note': 'Pick up tomorrow', 'clarification': ''}
            response = {'choices': [{'message': {'content': json.dumps(proposal)}}]}
            with patch.object(f.app, 'ai_completion', return_value=(response, {'provider': 'baseten', 'model': 'MOCKED-evaluation-only'})):
                p = f.ok('/api/propose-audio', {'provider': 'baseten', 'audio': {
                    'mime': 'audio/wav', 'base64': base64.b64encode(buffer.getvalue()).decode()}})
            review = f.ok('/api/confirm', {'proposal': p, 'audio_draft_id': p['audio_draft_id'],
                         'audio_reviewed': True, 'decisions': [], 'submission_id': 'synthetic-pickup'})
            attachment = {'event_id': review['event_id'], 'order_id': order_id, 'submission_id': 'synthetic-attach'}
            assert f.request('/api/attach-review', attachment)[0] == 400
            f.ok('/api/attach-review', dict(attachment, confirmed=True))
            order = f.ok('/api/orders')[0]
            row['observed'] = {'quantity': order['items'][0]['quantity'],
                               'pickup': order['reviews'][-1]['review']['fulfillment_note'],
                               'items': p['items'], 'dispatched': order['items'][0]['dispatched'],
                               'received': order['items'][0]['received']}
            assert row['observed'] == {'quantity': 10, 'pickup': 'Pick up tomorrow', 'items': [], 'dispatched': 0, 'received': 0}
            row['notes'] = 'MOCKED audio AI; synthetic silence. Tests review/attachment behaviour only.'
        elif case['kind'] == 'dispatch':
            line = f.ok('/api/orders')[0]['items'][0]['id']
            payload = {'order_id': order_id, 'submission_id': 'synthetic-dispatch', 'kind': 'dispatch',
                       'items': [{'line_id': line, 'quantity': 4}]}
            assert f.request('/api/fulfillment', payload)[0] == 400
            f.ok('/api/fulfillment', dict(payload, confirmed=True))
            f.ok('/api/fulfillment', dict(payload, confirmed=True))  # retry must not double-dispatch
            line = f.ok('/api/orders')[0]['items'][0]
            row['observed'] = {k: line[k] for k in case['expected']}
            assert row['observed'] == case['expected']
        else:
            raise AssertionError('Unknown case kind')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    template = commands.add_parser('template', help='Create blank observations, never run AI.')
    template.add_argument('--mode', choices=['live-ai', 'mocked-ai', 'manual'], required=True)
    commands.add_parser('offline', help='Run deterministic ledger checks plus one explicitly mocked audio workflow.')
    args = parser.parse_args()
    if args.command == 'template':
        write_record(new_record(args.mode)); return
    record = new_record('offline')
    failures = 0
    for case, row in zip(dataset()['cases'], record['cases']):
        try:
            check_case(case, row)
            row['outcome'] = 'pass'
        except Exception as error:
            failures += 1
            row['outcome'] = 'fail'
            row['notes'] = 'Offline check failed: ' + type(error).__name__
        print(case['id'] + ': ' + row['outcome'])
    write_record(record)
    print('Offline only: deterministic rules plus mocked audio; no AI accuracy measurement.')
    raise SystemExit(bool(failures))


if __name__ == '__main__':
    main()
