"""Loopback vendor-contract simulator. No real SMS, bank, credentials or money.

Used by automated integration/pilot/load checks; not a vendor sandbox substitute.
"""
import json
import re
import threading
from contextlib import AbstractContextManager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs


class LocalProviders(AbstractContextManager):
    def __init__(self):
        self.payments, self.messages, self.codes = {}, {}, {}
        self.calls = []
        self.otp_requests = []
        self.modes = {}
        self.lock = threading.Lock()
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                try:
                    raw = self.rfile.read(min(int(self.headers.get('Content-Length', 0)), 8192))
                    payload = json.loads(raw) if self.headers.get('Content-Type') == 'application/json' else {k: v[0] for k, v in parse_qs(raw.decode()).items()}
                except (ValueError, TypeError):
                    self.send_error(400)
                    return
                method = self.path.split('/')[-1].removesuffix('.json')
                with fixture.lock:
                    fixture.calls.append(method)
                    mode = fixture.modes.get(method, '')
                    if mode == 'redirect':
                        self.send_response(302)
                        self.send_header('Location', 'https://example.invalid/never-follow')
                        self.end_headers()
                        return
                    if mode == 'malformed':
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(b'not json')
                        return
                    if mode == 'reject':
                        result = {'errors': {'code': -9}, 'return': {'status': 411}}
                    elif method == 'request':
                        assert type(payload['amount']) is int and payload['currency'] == 'IRR'
                        authority = 'S' + str(len(fixture.payments)+1).zfill(35)
                        fixture.payments[authority] = {'amount': payload['amount'], 'status': 'IN_BANK', 'ref': 100000 + len(fixture.payments)}
                        result = {'data': {'code': 100, 'authority': authority}, 'errors': []}
                    elif method in {'verify', 'inquiry', 'reverse'}:
                        payment = fixture.payments.get(payload.get('authority'))
                        if not payment:
                            result = {'errors': {'code': -54}}
                        elif method == 'inquiry':
                            result = {'data': {'code': 100, 'status': payment['status']}}
                        elif method == 'reverse':
                            payment['status'] = 'REVERSED'
                            result = {'data': {'code': 100}}
                        elif payment['status'] in {'PAID', 'VERIFIED'} and payload['amount'] == payment['amount']:
                            old = payment['status']
                            payment['status'] = 'VERIFIED'
                            result = {'data': {'code': 101 if old == 'VERIFIED' else 100, 'ref_id': payment['ref'], 'amount': payment['amount'] + (1 if mode == 'wrong_amount' else 0)}}
                        else:
                            result = {'errors': {'code': -51}}
                    elif method == 'lookup':
                        fixture.otp_requests.append(payload.copy())
                        fixture.codes[payload['receptor']] = payload['token']
                        result = {'return': {'status': 200}, 'entries': [{'messageid': 700, 'status': 5, 'cost': 100}]}
                    elif method == 'send':
                        if 'localid' not in payload:
                            match = re.fullmatch(r'بگم نگم\nکد ورود: ([0-9]{6})\nاعتبار: ۵ دقیقه\nکد را در اختیار کسی نگذارید\.(?:\n\n@[a-z0-9.-]+ #\1)?', payload['message'])
                            assert match, 'Only the fixed OTP text may use send without localid'
                            fixture.otp_requests.append(payload.copy())
                            fixture.codes[payload['receptor']] = match[1]
                            result = {'return': {'status': 200}, 'entries': [{'messageid': 700, 'status': 1, 'cost': 500}]}
                        else:
                            local_id = str(payload['localid'])
                            if local_id not in fixture.messages:
                                fixture.messages[local_id] = {'messageid': 800 + len(fixture.messages), 'localid': local_id, 'status': 1, 'cost': 500}
                            result = {'return': {'status': 200}, 'entries': [fixture.messages[local_id].copy()]}
                    elif method in {'status', 'statuslocalmessageid'}:
                        msg = fixture.messages.get(str(payload.get('localid'))) if method == 'statuslocalmessageid' else next((m for m in fixture.messages.values() if str(m['messageid']) == str(payload.get('messageid'))), None)
                        result = {'return': {'status': 200}, 'entries': [msg.copy()] if msg else [{'messageid': 1, 'localid': payload.get('localid'), 'status': 100}]}
                        if mode == 'wrong_local_id':
                            result['entries'][0]['localid'] = '0'
                    else:
                        self.send_error(404)
                        return
                    if mode == 'drop_after_accept':
                        self.close_connection = True
                        return
                encoded = json.dumps(result).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
