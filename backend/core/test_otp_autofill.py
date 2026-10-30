from django.test import SimpleTestCase
from datetime import datetime, timezone
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
    def test_bank_style_code_line_jalali_tehran_time_and_final_domain_binding(self):
        text = otp_sms('0123', sent_at=datetime(2026, 9, 15, 10, 30, 28, tzinfo=timezone.utc))
        self.assertEqual(text, 'بگم نگم\nکد تأیید ورود به سامانه:\nCode: 0123\n1405/06/24 14:00:28\n\n@begamnagam.ir #0123')
        self.assertLessEqual(len(text.encode('utf-16-le')) // 2, 134)

    def test_date_rolls_at_tehran_midnight_and_nowruz(self):
        for utc, stamp in [
            ((2026, 9, 14, 20, 29, 59), '1405/06/23 23:59:59'),
            ((2026, 9, 14, 20, 30, 0), '1405/06/24 00:00:00'),
            ((2026, 3, 20, 20, 30, 0), '1405/01/01 00:00:00'),
        ]:
            with self.subTest(stamp=stamp):
                self.assertEqual(otp_sms('0000', sent_at=datetime(*utc, tzinfo=timezone.utc)).splitlines()[3], stamp)

    @override_settings(APP_BASE_URL='https://localhost:3000')
    def test_local_sms_keeps_keyboard_code_hint_without_an_invalid_domain_binding(self):
        text = otp_sms('9999')
        self.assertEqual(len(text.splitlines()), 4)
        self.assertEqual(text.splitlines()[2], 'Code: 9999')

    def test_invalid_code_never_becomes_message_content(self):
        for code in ('123', '12345', '123456', '۱۲۳۴', '12a4', '1234\nExtra', None, 1234):
            with self.subTest(code=code), self.assertRaises(ValueError):
                otp_sms(code)
