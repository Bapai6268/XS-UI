import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('verify',Path(__file__).with_name('verify_install.py'))
verify=importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)

class ListenerTests(unittest.TestCase):
    def check(self,text):
        verify.verify_listeners((2095,2096),lambda *a,**kw:text)
    def test_loopback_with_other_public_services(self):
        self.check('LISTEN 0 128 127.0.0.1:2095 0.0.0.0:*\nLISTEN 0 128 [::1]:2096 [::]:*\nLISTEN 0 128 *:22 *:*')
    def test_reject_public_management_on_ipv4_and_ipv6(self):
        for addr in ('0.0.0.0','[::]','*','192.0.2.1'):
            with self.subTest(addr=addr),self.assertRaisesRegex(RuntimeError,'Unexpected listener'):
                self.check(f'LISTEN 0 128 {addr}:2095 *:*\nLISTEN 0 128 127.0.0.1:2096 *:*')
    def test_reject_missing_subscription(self):
        with self.assertRaisesRegex(RuntimeError,'not ready'):
            self.check('LISTEN 0 128 127.0.0.1:2095 *:*')
    def test_reject_additional_public_binding(self):
        with self.assertRaisesRegex(RuntimeError,'Unexpected listener'):
            self.check('LISTEN 0 128 127.0.0.1:2095 *:*\nLISTEN 0 128 127.0.0.1:2096 *:*\nLISTEN 0 128 [::]:2095 *:*')
    def test_public_panel_keeps_subscription_private(self):
        verify.verify_listeners((2095,2096),lambda *a,**kw:'LISTEN 0 128 0.0.0.0:2095 *:*\nLISTEN 0 128 127.0.0.1:2096 *:*',public_panel=True)
    def test_public_mode_rejects_public_subscription(self):
        with self.assertRaises(RuntimeError):
            verify.verify_listeners((2095,2096),lambda *a,**kw:'LISTEN 0 128 0.0.0.0:2095 *:*\nLISTEN 0 128 0.0.0.0:2096 *:*',public_panel=True)

class ReadinessTests(unittest.TestCase):
    def run_check(self, running=True, login=True, listener_error=None, logout_error=False):
        from unittest.mock import patch, mock_open, MagicMock
        import io
        import contextlib
        account='{"port":2095,"sub_port":2096,"username":"test","password":"secret-test"}'
        def response(req, **kwargs):
            if req.full_url.endswith('login'): value={'success':login}
            elif req.full_url.endswith('logout'):
                if logout_error: raise OSError('logout failed')
                value={'success':True}
            else: value={'obj':{'sbd':{'running':running},'log':'ERROR - naive outbound is disabled when built without with_naive_outbound tag'}}
            return contextlib.closing(io.StringIO(verify.json.dumps(value)))
        client=MagicMock()
        client.open.side_effect=response
        with patch('builtins.open',mock_open(read_data=account)), patch.object(verify.urllib.request,'build_opener',return_value=client), patch.object(verify,'verify_listeners',side_effect=listener_error), patch.object(verify.time,'sleep'), contextlib.redirect_stdout(io.StringIO()):
            verify.verify('unused',public_panel=True)
    def test_naive_warning_does_not_fail_healthy_core(self):
        self.run_check()
    def test_stopped_core_still_fails(self):
        with self.assertRaisesRegex(RuntimeError,'running=true'):self.run_check(running=False)
    def test_bad_credentials_still_fail(self):
        with self.assertRaisesRegex(RuntimeError,'Login verification failed'):self.run_check(login=False)
    def test_missing_listener_reports_reason(self):
        with self.assertRaisesRegex(RuntimeError,'missing ports: 2096'):self.run_check(listener_error=RuntimeError('missing ports: 2096'))
    def test_logout_failure_is_not_readiness_failure(self):
        self.run_check(logout_error=True)
    def test_public_wildcard_formats(self):
        for addr in ('0.0.0.0','*','[::]','::'):
            with self.subTest(addr=addr):
                verify.verify_listeners((2095,2096),lambda *a,**k:f'LISTEN 0 128 {addr}:2095 *:*\nLISTEN 0 128 127.0.0.1:2096 *:*',public_panel=True)
    def test_embedded_checker_matches_source(self):
        script=Path(__file__).resolve().parents[2].joinpath('install.sh').read_text()
        embedded=script.split("<<'XS_UI_READINESS_HOTFIX'\n",1)[1].split('XS_UI_READINESS_HOTFIX\n',1)[0]
        self.assertEqual(embedded,Path(__file__).with_name('verify_install.py').read_text())

if __name__=='__main__':unittest.main()
