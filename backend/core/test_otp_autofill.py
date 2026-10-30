from django.test import SimpleTestCase
from config.origins import web_otp_sms_host
from core.otp import otp_sms
from django.test import override_settings


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


@override_settings(APP_BASE_URL='https://begamnagam.ir')
class OTPMessageTests(SimpleTestCase):
    def test_compact_code_and_final_domain_binding_without_extra_text(self):
        text = otp_sms('0123')
        self.assertEqual(text, 'بگم نگم\nCode: 0123\n\n@begamnagam.ir #0123')
        self.assertNotIn('سامانه', text)
        self.assertNotRegex(text, r'[0-9]{4}/[0-9]{2}/[0-9]{2}|[0-9]{2}:[0-9]{2}')
        self.assertLessEqual(len(text.encode('utf-16-le')) // 2, 70)

    @override_settings(APP_BASE_URL='https://localhost:3000')
    def test_local_sms_keeps_keyboard_code_hint_without_an_invalid_domain_binding(self):
        text = otp_sms('9999')
        self.assertEqual(len(text.splitlines()), 2)
        self.assertEqual(text.splitlines()[1], 'Code: 9999')

    def test_invalid_code_never_becomes_message_content(self):
        for code in ('123', '12345', '123456', '۱۲۳۴', '12a4', '1234\nExtra', None, 1234):
            with self.subTest(code=code), self.assertRaises(ValueError):
                otp_sms(code)
