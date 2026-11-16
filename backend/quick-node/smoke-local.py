#!/usr/bin/env python3
"""Real backend + frontend plan + SOCKS authentication; loopback only.
Never invokes the root installer, changes a firewall, or contacts an ACME CA.
"""
import argparse
import http.cookiejar
import http.server
import json
import os
import pathlib
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('--binary', required=True)
parser.add_argument('--frontend', required=True)
parser.add_argument('--api-only', action='store_true', help='Explicitly skip live proxy tests; validate disabled-node API operations only')
args = parser.parse_args()
binary = str(pathlib.Path(args.binary).resolve())
plan_module = pathlib.Path(args.frontend).resolve() / 'src/plugins/quickNode.ts'

def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

def recv_exact(s, n):
    data = b''
    while len(data) < n:
        part = s.recv(n-len(data))
        if not part:
            raise AssertionError('Unexpected socket close')
        data += part
    return data

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'quick-node-loopback-ok')
    def log_message(self, *_args):
        pass

with tempfile.TemporaryDirectory(prefix='sui-quick-smoke-') as folder:
    panel, subscription, socks_port = free_port(), free_port(), free_port()
    assert len({panel, subscription, socks_port}) == 3
    origin = f'http://127.0.0.1:{panel}'
    api = origin + '/app/api/'
    credentials = {'username': 'test-'+secrets.token_hex(4), 'password': secrets.token_hex(24), 'port': panel, 'sub_port': subscription}
    env = dict(os.environ, SUI_DB_FOLDER=folder+'/db')
    subprocess.run([binary, 'quick-init'], input=json.dumps(credentials).encode(), env=env, cwd=folder, check=True, stdout=subprocess.DEVNULL)
    jar = http.cookiejar.CookieJar()
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(jar))
    def request(action, data=None, request_origin=None):
        body = None if data is None else urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(api+action, data=body, headers={'X-Requested-With':'XMLHttpRequest', 'Origin':request_origin or origin})
        try:
            with client.open(req, timeout=20) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, {}
    def save(kind, action, value, **extra):
        code, result = request('save', {'object':kind, 'action':action, 'data':json.dumps(value), **extra})
        if code != 200 or not result.get('success'):
            raise AssertionError(f'{kind}/{action} failed (details withheld to avoid exposing credentials)')
        return result['obj']
    fixture = http.server.ThreadingHTTPServer(('127.0.0.1',0), Handler)
    threading.Thread(target=fixture.serve_forever, daemon=True).start()
    with open(folder+'/server.log', 'wb') as log:
        process = subprocess.Popen([binary], cwd=folder, env=env, stdout=log, stderr=log)
        try:
            for _ in range(100):
                if process.poll() is not None:
                    raise AssertionError('Backend exited before readiness')
                try:
                    code, response = request('load')
                    break
                except (urllib.error.URLError, ConnectionError):
                    time.sleep(.1)
            else:
                raise AssertionError('Backend readiness timeout')
            assert code in (401,403) or response.get('success') is False, 'Unauthenticated API access'
            code, response = request('login', {'user':credentials['username'], 'pass':credentials['password']})
            assert code == 200 and response['success'], 'Login failed'
            code, _ = request('save', {'object':'clients','action':'new','data':'{}'}, 'https://cross-site.invalid')
            assert code == 403, 'Cross-origin write was not rejected'
            _, status = request('status?r=sbd')
            if not args.api_only:
                assert status['obj']['sbd']['running'] is True, 'Core cannot run in this environment; full proxy test is blocked'
            script = "const {buildQuickPlan}=await import(process.argv[1]);process.stdout.write(JSON.stringify(buildQuickPlan(JSON.parse(process.argv[2]))));"
            options = {'protocol':'socks','host':'127.0.0.1','port':socks_port,'tag':'quick-smoke'}
            output = subprocess.check_output(['node','--experimental-strip-types','--input-type=module','-e',script,plan_module.as_uri(),json.dumps(options)],stderr=subprocess.DEVNULL)
            plan = json.loads(output)
            result = save('clients','new',plan['client'])
            client_id = next(c['id'] for c in result['clients'] if c['name']==plan['client']['name'])
            result = save('inbounds','new',plan['inbound'],initUsers=str(client_id))
            inbound_id = next(i['id'] for i in result['inbounds'] if i['tag']=='quick-smoke')
            saved_inbound = next(i for i in result['inbounds'] if i['id']==inbound_id)
            assert saved_inbound.get('enable') is False, 'Backend did not persist disabled state'
            _, core_config = request('singbox-config')
            config_value = core_config
            if isinstance(config_value, str): config_value = json.loads(config_value)
            assert not any(i.get('tag')=='quick-smoke' for i in (config_value.get('inbounds') or [])), 'Disabled inbound leaked into generated core config'
            with socket.socket() as s:
                assert s.connect_ex(('127.0.0.1',socks_port)) != 0, 'Staged listener became active'
            _, response = request('clients?id='+str(client_id))
            saved_client = response['obj']['clients'][0]
            assert inbound_id in saved_client['inbounds']
            assert saved_client['config']['socks']['password'] == plan['password']
            if args.api_only:
                # Exercise the real TLS save format for both other protocols,
                # keeping every inbound disabled and never requesting a cert.
                _, keys_response = request('keypairs?k=reality')
                assert keys_response['success']
                keys = dict(line.split(': ', 1) for line in keys_response['obj'])
                assert all(re.fullmatch(r'[A-Za-z0-9_-]{43}', keys[k]) for k in ('PrivateKey','PublicKey'))
                for protocol in ('reality','hysteria2'):
                    options = {'protocol':protocol,'host':'127.0.0.1','port':free_port(),'tag':'quick-'+protocol}
                    if protocol == 'reality':
                        options.update(target='target.example.com', privateKey=keys['PrivateKey'], publicKey=keys['PublicKey'])
                    else:
                        options['acme'] = {'domain':'proxy.example.com','email':'operator@example.com'}
                    candidate = json.loads(subprocess.check_output(['node','--experimental-strip-types','--input-type=module','-e',script,plan_module.as_uri(),json.dumps(options)],stderr=subprocess.DEVNULL))
                    rows = save('tls','new',candidate['tls'])['tls']
                    candidate['inbound']['tls_id'] = next(t['id'] for t in rows if t['name']==candidate['tls']['name'])
                    rows = save('clients','new',candidate['client'])['clients']
                    candidate_id = next(c['id'] for c in rows if c['name']==candidate['username'])
                    rows = save('inbounds','new',candidate['inbound'],initUsers=str(candidate_id))['inbounds']
                    created = next(i for i in rows if i['tag']==options['tag'])
                    assert created['enable'] is False
                    _, check = request('clients?id='+str(candidate_id))
                    bound = check['obj']['clients'][0]
                    assert created['id'] in bound['inbounds']
                    config_key, secret_key = ('vless','uuid') if protocol=='reality' else ('hysteria2','password')
                    assert bound['config'][config_key][secret_key] == candidate['password']
                _, config_value = request('singbox-config')
                assert not any(i.get('tag','').startswith('quick-') for i in (config_value.get('inbounds') or []))
                print('PASS (API only): private bootstrap, login enforcement, cross-origin rejection, Reality key generation, all three protocols staged with correct credentials/TLS, and disabled nodes excluded from core config. Live proxy testing explicitly skipped.')
                sys.exit(0)
            save('inbounds','edit',{**plan['inbound'],'id':inbound_id,'enable':True})
            with socket.create_connection(('127.0.0.1',socks_port),timeout=5) as s:
                s.sendall(b'\x05\x01\x00')
                assert recv_exact(s,2) == b'\x05\xff', 'SOCKS accepted no authentication'
            for password, success in [('wrong-password',False),(plan['password'],True)]:
                with socket.create_connection(('127.0.0.1',socks_port),timeout=5) as s:
                    s.sendall(b'\x05\x01\x02')
                    assert recv_exact(s,2) == b'\x05\x02'
                    user, password_bytes = plan['username'].encode(), password.encode()
                    s.sendall(b'\x01'+bytes([len(user)])+user+bytes([len(password_bytes)])+password_bytes)
                    auth = recv_exact(s,2)
                    assert (auth[1] == 0) == success, 'SOCKS credential enforcement failed'
                    if success:
                        s.sendall(b'\x05\x01\x00\x01'+socket.inet_aton('127.0.0.1')+fixture.server_port.to_bytes(2,'big'))
                        reply = recv_exact(s,4)
                        assert reply[1] == 0
                        recv_exact(s, (4 if reply[3] == 1 else 16)+2)
                        s.sendall(b'GET / HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n')
                        data = b''
                        while chunk := s.recv(4096): data += chunk
                        assert b'quick-node-loopback-ok' in data, 'Proxy request failed'
            print('PASS: private bootstrap, API login enforcement, cross-origin protection, staged creation, credential binding, SOCKS no-auth/wrong-password rejection and authenticated proxy request.')
        except Exception:
            log.flush()
            diagnostic = pathlib.Path(folder+'/server.log').read_text(errors='replace')[-2500:]
            for secret in [credentials['password'], credentials['username']] + ([plan['password'], plan['username']] if 'plan' in locals() else []):
                diagnostic = diagnostic.replace(secret, '[redacted]')
            print(diagnostic)
            raise
        finally:
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
            fixture.shutdown(); fixture.server_close()
