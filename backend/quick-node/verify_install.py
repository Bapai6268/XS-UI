#!/usr/bin/env python3
"""Check loopback panel login and core readiness without printing credentials."""
import http.cookiejar
import json
import sys
import subprocess
import time
import urllib.parse
import urllib.request

def verify_listeners(ports, execute=subprocess.check_output):
    lines=execute(['ss','-H','-ltn'],text=True).splitlines()
    seen=set()
    for line in lines:
        fields=line.split()
        if len(fields)<4:continue
        address, separator, port=fields[3].rpartition(':')
        if not separator or not port.isdigit() or int(port) not in ports:continue
        if address not in ('127.0.0.1','[::1]','::1'):
            raise RuntimeError('Management/subscription listener is not loopback-only')
        seen.add(int(port))
    if seen!=set(ports):raise RuntimeError('Private listeners are not ready')

def verify(path):
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
    for attempt in range(15):
        try:
            login=request('login',{'user':account['username'],'pass':account['password']})
            if not login.get('success'):raise RuntimeError('Login verification failed')
            result=request('status?r=sbd')
            if result.get('obj',{}).get('sbd',{}).get('running') is True:
                verify_listeners((port,sub_port))
                request('logout')
                print('PASS: private panel login and proxy core readiness. Public nodes/certificates still require tests.')
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError('Readiness failed. Inspect sudo journalctl -u xs-ui; credentials withheld.')

if __name__=='__main__':
    try:verify(sys.argv[1])
    except Exception as error:raise SystemExit(str(error))
