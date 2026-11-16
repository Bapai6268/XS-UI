#!/usr/bin/env python3
"""Check API/core/listeners; unrelated log levels never determine readiness."""
import http.cookiejar
import json
import sys
import subprocess
import time
import urllib.parse
import urllib.request

def verify_listeners(ports, execute=subprocess.check_output, public_panel=False):
    lines=execute(['ss','-H','-ltn'],text=True).splitlines()
    seen=set()
    for line in lines:
        fields=line.split()
        if len(fields)<4:continue
        address, separator, port=fields[3].rpartition(':')
        if not separator or not port.isdigit() or int(port) not in ports:continue
        allowed=('0.0.0.0','[::]','::','*') if public_panel and int(port)==ports[0] else ('127.0.0.1','[::1]','::1')
        if address not in allowed:
            raise RuntimeError(f'Unexpected listener binding on port {port}: {address}')
        seen.add(int(port))
    if seen!=set(ports):raise RuntimeError('Listeners are not ready; missing ports: '+','.join(map(str,sorted(set(ports)-seen))))

def verify(path,public_panel=False):
    with open(path) as stream:
        account=json.load(stream)
    port=account['port']
    sub_port=account['sub_port']
    if any(type(value) is not int or not 1024 <= value <= 65535 for value in (port,sub_port)) or port==sub_port:
        raise RuntimeError('Invalid local panel port')
    origin=f'http://127.0.0.1:{port}'
    client=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def request(action,data=None):
        body=None if data is None else urllib.parse.urlencode(data).encode()
        req=urllib.request.Request(origin+'/app/api/'+action,data=body,headers={'Origin':origin,'X-Requested-With':'XMLHttpRequest'})
        with client.open(req,timeout=3) as response:return json.load(response)
    # Do not scan journal ERROR lines: the optional Naive outbound build warning
    # is unrelated to whether the panel and sing-box are operational.
    last_reason='No successful readiness response'
    for attempt in range(30):
        try:
            login=request('login',{'user':account['username'],'pass':account['password']})
            if not login.get('success'):raise RuntimeError('Login verification failed')
            result=request('status?r=sbd')
            if result.get('obj',{}).get('sbd',{}).get('running') is not True:
                raise RuntimeError('Proxy core API does not report running=true')
            verify_listeners((port,sub_port),public_panel=public_panel)
            # Logout cleanup must not turn a healthy service into installation failure.
            try:request('logout')
            except Exception:pass
            print('PASS: panel login, expected listener bindings and proxy core readiness. Public nodes/certificates still require tests.')
            return
        except RuntimeError as error:
            last_reason=str(error)
        except Exception as error:
            # Do not echo HTTP bodies, submitted credentials or raw exception text.
            last_reason='Readiness request/check failed: '+type(error).__name__
        if attempt<29:time.sleep(1)
    raise RuntimeError('Readiness failed: '+last_reason+'. Inspect sudo journalctl -u xs-ui; initial credentials saved in /root/xs-ui-access.json (root only).')

if __name__=='__main__':
    try:verify(sys.argv[1],public_panel='--public-panel' in sys.argv[2:])
    except Exception as error:raise SystemExit(str(error))
