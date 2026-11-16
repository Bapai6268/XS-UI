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
            with self.subTest(addr=addr),self.assertRaisesRegex(RuntimeError,'not loopback'):
                self.check(f'LISTEN 0 128 {addr}:2095 *:*\nLISTEN 0 128 127.0.0.1:2096 *:*')
    def test_reject_missing_subscription(self):
        with self.assertRaisesRegex(RuntimeError,'not ready'):
            self.check('LISTEN 0 128 127.0.0.1:2095 *:*')
    def test_reject_additional_public_binding(self):
        with self.assertRaisesRegex(RuntimeError,'not loopback'):
            self.check('LISTEN 0 128 127.0.0.1:2095 *:*\nLISTEN 0 128 127.0.0.1:2096 *:*\nLISTEN 0 128 [::]:2095 *:*')
    def test_public_panel_keeps_subscription_private(self):
        verify.verify_listeners((2095,2096),lambda *a,**kw:'LISTEN 0 128 0.0.0.0:2095 *:*\nLISTEN 0 128 127.0.0.1:2096 *:*',public_panel=True)
    def test_public_mode_rejects_public_subscription(self):
        with self.assertRaises(RuntimeError):
            verify.verify_listeners((2095,2096),lambda *a,**kw:'LISTEN 0 128 0.0.0.0:2095 *:*\nLISTEN 0 128 0.0.0.0:2096 *:*',public_panel=True)

if __name__=='__main__':unittest.main()
