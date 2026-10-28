from django.test import SimpleTestCase
from config.origins import web_otp_sms_host


class WebOTPSMSOriginTests(SimpleTestCase):
    def test_https_site_host_is_used_without_scheme_or_port(self):
        for origin in ('https://begamnagam.ir', 'https://begamnagam.ir/', 'https://BEGAMNAGAM.IR:443'):
            self.assertEqual(web_otp_sms_host(origin), 'begamnagam.ir')

    def test_local_insecure_or_malformed_origins_do_not_add_an_sms_binding(self):
        for origin in ('http://begamnagam.ir', 'https://localhost:3000', 'https://192.168.1.123',
                       'https://user:pass@begamnagam.ir', 'https://@begamnagam.ir',
                       'https://begamnagam.ir\n', 'https://begamnagam.ir/path',
                       'https://begamnagam.ir?other=1', 'https://begamnagam.ir#other',
                       'https://begamnagam.ir:bad', '', None):
            with self.subTest(origin=origin):
                self.assertIsNone(web_otp_sms_host(origin))
