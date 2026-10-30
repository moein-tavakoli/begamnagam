from types import SimpleNamespace
import uuid

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, SimpleTestCase, TestCase

from .input_digits import ascii_digits, canonical_input
from .middleware import CanonicalAdminInput
from .models import MessagePackage, SupportMessage
from .privacy import digest
from .tests import APITestCase
from .views import body


class CanonicalInputTests(SimpleTestCase):
    def test_all_decimal_digits_become_ascii_without_losing_zero_or_other_text(self):
        self.assertEqual(ascii_digits('پیگیری ۰۰١۲３ ४५'), 'پیگیری 00123 45')
        self.assertEqual(canonical_input({'phone': '۰۹۱۲', 'values': ['۰۱۲۳', {'reason': 'آزمون ۴'}], 'amount': 123, 'enabled': True, 'optional': None}),
                         {'phone': '0912', 'values': ['0123', {'reason': 'آزمون 4'}], 'amount': 123, 'enabled': True, 'optional': None})

    def test_input_keeps_json_types_and_original_object(self):
        original = {'amount_toman': '۱۲۳', 'name': 'بسته ۱'}
        self.assertEqual(canonical_input(original), {'amount_toman': '123', 'name': 'بسته 1'})
        self.assertEqual(original['name'], 'بسته ۱')

    def test_credentials_capabilities_versions_and_identifiers_are_byte_exact(self):
        original = {key: 'Ab۰۱۲٣' for key in ('username', 'password', 'csrfmiddlewaretoken', 'alternative_token', 'preview_id', 'client_key', 'terms_version', 'signature', 'authority')}
        self.assertEqual(canonical_input(original), original)

    def test_json_ingress_normalizes_escaped_and_literal_input_before_use(self):
        request = RequestFactory().post('/api/v1/support/messages', {'text': 'رسید ۰۰۱۲', 'values': {'name': 'بسته ۴'}}, content_type='application/json')
        self.assertEqual(body(request), {'text': 'رسید 0012', 'values': {'name': 'بسته 4'}})

    def test_admin_preserves_repeated_fields_csrf_and_password(self):
        request = RequestFactory().post('/admin/core/account/', {'reason': 'آزمون ۱۲', '_selected_action': ['۱', '۲'], 'password': 'رمز۱۲', 'csrfmiddlewaretoken': 'Ab۱۲'})
        request.resolver_match = SimpleNamespace(app_names=['admin'])
        CanonicalAdminInput(lambda r: None).process_view(request, None, (), {})
        self.assertEqual(request.POST['reason'], 'آزمون 12')
        self.assertEqual(request.POST.getlist('_selected_action'), ['1', '2'])
        self.assertEqual(request.POST['password'], 'رمز۱۲')
        self.assertEqual(request.POST['csrfmiddlewaretoken'], 'Ab۱۲')


class CanonicalStorageTests(TestCase):
    post, authenticate = APITestCase.post, APITestCase.authenticate

    def setUp(self):
        APITestCase.setUp(self)
        self.manager = get_user_model().objects.create_superuser('digits-manager', password='Secret۱۲۳!')
        self.staff = Client()
        self.staff.force_login(self.manager)

    def test_api_converts_user_text_before_database_write_and_sealing(self):
        self.authenticate()
        response = self.post('/support/messages', {'text': 'پیگیری ۰۰۱۲۳ و سفارش ٤٥'}, HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(response.status_code, 200, response.content)
        message = SupportMessage.objects.get()
        self.assertEqual(message.text, 'پیگیری 00123 و سفارش 45')
        self.assertEqual(message.text_digest, digest('support-text-v1:' + message.text))

    def test_api_package_name_is_canonical_before_persistence(self):
        response = self.staff.post('/api/v1/manage/packages', {'values': {'name': 'بسته ۱۲', 'message_count': 12, 'price_toman': 10000, 'active': True, 'sort_order': 0}, 'revision': 0, 'reason': 'ثبت بسته ۱۲'}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(MessagePackage.objects.filter(name='بسته 12', message_count=12).exists())

    def test_admin_form_converts_persian_and_arabic_fields_before_save(self):
        response = self.staff.post('/admin/core/messagepackage/add/', {'name': 'بسته ۳۴', 'message_count': '٣٤', 'price_toman': '۱۰۰۰۰', 'active': 'on', 'sort_order': '۲', 'source_revision': '۰', 'reason': 'ثبت بسته ۳۴', '_save': 'ذخیره'})
        self.assertEqual(response.status_code, 302, response.content[:200])
        self.assertTrue(MessagePackage.objects.filter(name='بسته 34', message_count=34, price_toman=10000, sort_order=2).exists())

    def test_login_keeps_password_digits_exact(self):
        client = Client()
        response = client.post('/api/v1/manage/login', {'username': 'digits-manager', 'password': 'Secret۱۲۳!'}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
