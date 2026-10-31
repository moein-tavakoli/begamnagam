import hashlib
import importlib.util
import io
import json
import uuid
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import resolve
from django.utils import timezone

from core.api_v2.contracts import SCHEMAS
from core.api_v2.documentation import ASSETS
from core.api_v2.openapi import specification
from core.models import (Account, CreditPurchase, Invitation, MessageDelivery, MessagePackage,
                         OTPChallenge, Order, Outbox, Preview, RecipientState, SupportMessage)
from core.privacy import digest


@override_settings(DEMO_MODE=True, OTP_BACKEND='demo', SMS_BACKEND='console',
                   PROVIDER_NETWORK_MODE='disabled', PAYMENT_BACKEND='demo', AI_MODE='template',
                   API_DOCUMENTATION_ENABLED=False)
class IntegrationAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client(enforce_csrf_checks=True)
        self.tokens = {}

    def session(self, client=None):
        client = client or self.client
        response = client.get('/api/v2/session')
        self.assertEqual(response.status_code, 200, response.content)
        self.tokens[id(client)] = response.json()['csrf_token']
        return response.json()

    def mutate(self, path, data=None, *, method='POST', client=None, key=None, csrf=True):
        client = client or self.client
        if id(client) not in self.tokens:
            self.session(client)
        headers = {'HTTP_X_CSRFTOKEN': self.tokens[id(client)]} if csrf else {}
        if key is not None:
            headers['HTTP_IDEMPOTENCY_KEY'] = str(key)
        response = client.generic(method, '/api/v2' + path, data=json.dumps({} if data is None else data),
                                  content_type='application/json', **headers)
        if response.status_code < 400 and isinstance(response.json(), dict) and 'csrf_token' in response.json():
            self.tokens[id(client)] = response.json()['csrf_token']
        return response

    def login(self, phone='09123456789', client=None):
        client = client or self.client
        challenge = self.mutate('/auth/otp-challenges', {'phone': phone}, client=client)
        self.assertEqual(challenge.status_code, 201, challenge.content)
        old_token = self.tokens[id(client)]
        verified = self.mutate('/auth/sessions', {'challenge_id': challenge.json()['challenge_id'],
                               'code': challenge.json()['debug_code']}, client=client)
        self.assertEqual(verified.status_code, 201, verified.content)
        self.assertNotEqual(old_token, verified.json()['csrf_token'])
        self.assertTrue(verified.json()['authenticated'])
        return Account.objects.get(phone_hash=digest(phone)).user

    def make_preview(self, phone='09901234567'):
        catalog = self.client.get('/api/v2/catalog').json()
        example = next(item for item in catalog['examples'] if item['topic'] == 'appreciation')
        response = self.mutate('/message-previews', {'recipient_phone': phone, 'source_mode': 'suggestion',
                               'category': example['topic'], 'text': example['text']})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def reserve(self, preview=None, phone='09901234567', key=None):
        preview = preview or self.make_preview(phone)
        return self.mutate('/messages', {'preview_id': preview['preview_id'], 'recipient_phone': phone,
                            'consent': True, 'terms_version': preview['terms_version']}, key=key or uuid.uuid4())

    def test_bootstrap_anonymous_and_verified_credit_summary(self):
        response = self.client.get('/api/v2/bootstrap')
        self.assertEqual(response.status_code, 200)
        self.assertIn('csrftoken', response.cookies)
        self.assertNotIn('me', response.json())
        self.assertNotIn('credits', response.json())
        self.assertFalse(response.json()['session']['authenticated'])
        user = self.login()
        Account.objects.filter(user=user).update(demo_sends_remaining=7, purchased_sends_remaining=99, demo_wallet_balance_toman=321)
        data = self.client.get('/api/v2/bootstrap').json()
        self.assertEqual(data['credits']['gift_remaining'], 3)
        self.assertEqual(data['credits']['purchased_remaining'], 7)
        self.assertEqual(data['credits']['total_remaining'], 10)
        self.assertEqual(data['credits']['wallet_balance_toman'], '321')
        self.assertEqual(data['me'], self.client.get('/api/v2/me').json())
        self.assertNotIn('09123456789', json.dumps(data))
        self.assertNotIn('phone_hash', json.dumps(data))

    def test_complete_review_reserve_submit_poll_and_retry_journey(self):
        user = self.login()
        valid = self.mutate('/recipients/validations', {'phone': '+۹۸۹۹۰۱۲۳۴۵۶۷'})
        self.assertEqual(valid.json()['phone'], '09901234567')
        preview = self.make_preview()
        key = uuid.uuid4()
        response = self.reserve(preview, key=key)
        self.assertEqual(response.status_code, 200, response.content)
        message_id = response.json()['id']
        self.assertEqual(response.json()['status'], 'awaiting_payment')
        self.assertEqual(self.reserve(preview, key=key).json()['id'], message_id)
        self.assertEqual(Account.objects.get(user=user).free_sends_remaining, 2)
        for _ in range(2):
            with self.captureOnCommitCallbacks(execute=True):
                result = self.mutate(f'/messages/{message_id}/submission', method='PUT')
            self.assertEqual(result.status_code, 200, result.content)
        receipt = self.client.get(f'/api/v2/messages/{message_id}').json()
        self.assertEqual(receipt['delivery_status'], 'delivered_demo')
        self.assertEqual(receipt['text'], preview['full_sms'])
        self.assertEqual(self.client.get('/api/v2/messages').json()['results'][0]['id'], message_id)
        self.assertEqual(Outbox.objects.count(), 1)
        self.assertEqual(MessageDelivery.objects.count(), 1)
        self.assertNotIn('09901234567', json.dumps(receipt))
        self.assertNotIn('original_text', receipt)
        self.assertEqual(self.client.get('/api/v1/messages').json()['results'][0]['id'], message_id)

    def test_schema_has_every_route_operation_unique_ids_and_security(self):
        spec = specification()
        identifiers = []
        from core.api_v2.urls import urlpatterns
        actual = sum(len(route.callback.api_operations) for route in urlpatterns if hasattr(route.callback, 'api_operations'))
        for path, methods in spec['paths'].items():
            for method, operation in methods.items():
                identifiers.append(operation['operationId'])
                concrete = path.replace('{category_id}', '1')
                for placeholder in ('message_id', 'preview_id', 'purchase_id', 'topup_id', 'invitation_id'):
                    concrete = concrete.replace('{' + placeholder + '}', str(uuid.uuid4()))
                self.assertTrue(hasattr(resolve('/api/v2' + concrete).func, 'api_operations'))
                if method != 'get':
                    self.assertIn({'CSRFToken': []}, [{k: v for k, v in entry.items() if k == 'CSRFToken'} for entry in operation['security']])
                    self.assertTrue(operation['requestBody']['required'])
                self.assertNotIn('/manage', path)
        self.assertEqual(len(identifiers), actual)
        self.assertEqual(len(set(identifiers)), actual)
        self.assertGreater(actual, 35)
        for name, contract in SCHEMAS.items():
            def walk(value):
                if isinstance(value, dict):
                    if '$ref' in value:
                        self.assertIn(value['$ref'].rsplit('/', 1)[-1], SCHEMAS, name)
                    for item in value.values():
                        walk(item)
                elif isinstance(value, list):
                    for item in value:
                        walk(item)
            walk(contract)

    def test_all_private_resources_require_verified_phone_not_admin_login(self):
        staff = get_user_model().objects.create_user(username='api-staff', is_staff=True)
        self.client.force_login(staff)
        paths = ['/me', '/me/credits', '/me/credit-entries', '/messages', '/wallet', '/wallet/entries',
                 '/wallet/topups', '/credit-purchases', '/invitations', '/support', '/support/messages', '/me/preferences']
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get('/api/v2' + path).status_code, 401)
        self.session()
        self.assertEqual(self.mutate('/message-previews', {}).status_code, 401)

    def test_otp_challenge_is_bound_to_cookie_jar_and_single_use(self):
        challenge = self.mutate('/auth/otp-challenges', {'phone': '09123456789'}).json()
        payload = {'challenge_id': challenge['challenge_id'], 'code': challenge['debug_code']}
        other = Client(enforce_csrf_checks=True)
        self.assertEqual(self.mutate('/auth/sessions', payload, client=other).status_code, 400)
        self.assertEqual(self.mutate('/auth/sessions', payload).status_code, 201)
        self.assertEqual(self.mutate('/auth/sessions', payload).status_code, 400)
        self.assertFalse(self.session(other)['authenticated'])

    def test_csrf_required_for_all_mutating_verbs_including_login_and_recipient_capability(self):
        self.session()
        for method, path, body in [('POST', '/auth/otp-challenges', {'phone': '09123456789'}),
                                   ('PATCH', '/me/preferences', {'blocked': True}), ('DELETE', '/session', {}),
                                   ('PUT', '/recipient-capabilities/preference', {'token': 'not-real'})]:
            with self.subTest(method=method):
                response = self.mutate(path, body, method=method, csrf=False)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()['error']['code'], 'csrf_failed')
        self.assertFalse(OTPChallenge.objects.exists())

    def test_old_csrf_is_rejected_after_login_and_new_token_works(self):
        self.session()
        old = self.tokens[id(self.client)]
        self.login()
        fresh = self.tokens[id(self.client)]
        self.tokens[id(self.client)] = old
        self.assertEqual(self.mutate('/recipients/validations', {'phone': '09901234567'}).status_code, 403)
        self.tokens[id(self.client)] = fresh
        self.assertEqual(self.mutate('/recipients/validations', {'phone': '09901234567'}).status_code, 200)

    def test_invalid_types_unknown_fields_and_oversized_body_are_errors(self):
        self.login()
        for path, data in [('/recipients/validations', {'phone': 9123456789}),
                           ('/recipients/validations', {'phone': '09901234567', 'lookup': True}),
                           ('/message-previews', {'recipient_phone': '09901234567', 'source_mode': 'freeform', 'text': []}),
                           ('/messages', {'preview_id': str(uuid.uuid4()), 'recipient_phone': '09901234567', 'consent': 1, 'terms_version': 'x'})]:
            self.assertEqual(self.mutate(path, data).status_code, 422)
        response = self.client.post('/api/v2/recipients/validations', 'not-json', content_type='text/plain',
                                    HTTP_X_CSRFTOKEN=self.tokens[id(self.client)])
        self.assertEqual(response.status_code, 415)
        response = self.client.post('/api/v2/recipients/validations', '{', content_type='application/json',
                                    HTTP_X_CSRFTOKEN=self.tokens[id(self.client)])
        self.assertEqual(response.status_code, 400)
        response = self.mutate('/recipients/validations', {'phone': 'x' * 9000})
        self.assertEqual(response.status_code, 413)

    def test_catalog_category_ids_and_examples_are_unambiguous(self):
        data = self.client.get('/api/v2/catalog').json()
        groups = self.client.get('/api/v2/categories').json()['results']
        self.assertEqual(groups, data['categories'])
        self.assertEqual(self.client.get('/api/v2/message-packages').json()['results'], data['message_packages'])
        self.assertEqual(len({item['id'] for item in groups}), len(groups))
        for group in groups:
            examples = self.client.get(f'/api/v2/categories/{group["id"]}/examples').json()['results']
            self.assertTrue(examples)
            self.assertTrue(all(item['category_id'] == group['id'] for item in examples))
        self.assertEqual(self.client.get('/api/v2/categories/99999/examples').status_code, 404)

    def test_recipient_validation_cannot_probe_membership_or_opt_out(self):
        self.login()
        before = self.mutate('/recipients/validations', {'phone': '09901234567'}).json()
        RecipientState.objects.create(phone_hash=digest('09901234567'), blocked=True)
        self.assertEqual(self.mutate('/recipients/validations', {'phone': '09901234567'}).json(), before)
        self.assertEqual(self.mutate('/recipients/validations', {'phone': '09123456789'}).status_code, 422)

    def test_recipient_bound_preview_extra_text_and_consent_guards(self):
        self.login()
        preview = self.make_preview()
        result = self.reserve(preview, phone='09901234568')
        self.assertEqual(result.json()['error']['code'], 'quote_recipient_changed')
        for consent in (None, False):
            data = {'preview_id': preview['preview_id'], 'recipient_phone': '09901234567', 'terms_version': preview['terms_version']}
            if consent is not None:
                data['consent'] = consent
            self.assertEqual(self.mutate('/messages', data, key=uuid.uuid4()).status_code, 422)
        response = self.reserve(preview)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.mutate(f'/messages/{response.json()["id"]}/submission', {'text': 'unreviewed'}, method='PUT').status_code, 422)
        self.assertFalse(Outbox.objects.exists())

    def test_message_ownership_and_idempotency_conflict(self):
        self.login()
        key = uuid.uuid4()
        first = self.reserve(key=key).json()
        preview = self.make_preview('09901234568')
        self.assertEqual(self.reserve(preview, phone='09901234568', key=key).json()['error']['code'], 'idempotency_conflict')
        other = Client(enforce_csrf_checks=True)
        self.login('09123456788', other)
        self.assertEqual(other.get(f'/api/v2/messages/{first["id"]}').status_code, 404)
        self.assertEqual(self.mutate(f'/messages/{first["id"]}/submission', method='PUT', client=other).status_code, 404)

    def test_freeform_fails_closed_when_disabled(self):
        self.login()
        result = self.mutate('/message-previews', {'recipient_phone': '09901234567', 'source_mode': 'freeform', 'text': 'متن دلخواه محترمانه'})
        self.assertEqual(result.status_code, 409)
        self.assertEqual(result.json()['error']['code'], 'freeform_unavailable')
        self.assertFalse(Preview.objects.exists())

    def test_missing_idempotency_key_never_reserves_credit(self):
        self.login()
        preview = self.make_preview()
        result = self.mutate('/messages', {'preview_id': preview['preview_id'], 'recipient_phone': '09901234567',
                             'consent': True, 'terms_version': preview['terms_version']})
        self.assertEqual(result.status_code, 422)
        self.assertEqual(result.json()['error']['code'], 'idempotency_key_required')
        self.assertFalse(Order.objects.exists())

    def test_preview_retrieval_preserves_snapshot_and_checks_owner_and_expiry(self):
        self.login()
        created = self.make_preview()
        path = '/api/v2/message-previews/' + created['preview_id']
        self.assertEqual(self.client.get(path).json(), created)
        other = Client(enforce_csrf_checks=True)
        self.login('09123456788', other)
        self.assertEqual(other.get(path).status_code, 404)
        Preview.objects.filter(pk=created['preview_id']).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.get(path).status_code, 409)

    def test_history_batch_serializer_matches_receipts_with_constant_queries(self):
        from core.services import serialize_order, serialize_orders
        self.login()
        for index in range(3):
            self.reserve(phone=f'0990123456{index}')
        orders = list(Order.objects.all())
        Order.objects.filter(pk=orders[0].pk).update(status='unknown')
        orders = list(Order.objects.all())
        expected = [serialize_order(order) for order in orders]
        with self.assertNumQueries(4):
            self.assertEqual(serialize_orders(orders), expected)
        with self.assertNumQueries(4):
            self.assertEqual(serialize_orders(orders[:1]), expected[:1])

    def test_keyset_pagination_ties_tampering_owner_filter_and_new_insertion(self):
        self.login()
        ids = []
        for index in range(3):
            result = self.reserve(phone=f'0990123456{index}')
            self.assertEqual(result.status_code, 200, result.content)
            ids.append(result.json()['id'])
        stamp = timezone.now() - timedelta(seconds=10)
        Order.objects.all().update(created_at=stamp)
        first = self.client.get('/api/v2/messages?limit=2').json()
        self.assertTrue(first['has_more'])
        cursor = first['next_cursor']
        Account.objects.filter(user__username__startswith='phone_').update(demo_sends_remaining=1)
        self.assertEqual(self.reserve(phone='09901234569').status_code, 200)
        second = self.client.get('/api/v2/messages', {'limit': 2, 'cursor': cursor}).json()
        combined = first['results'] + second['results']
        self.assertEqual({item['id'] for item in combined}, set(ids))
        self.assertEqual(len(combined), 3)
        self.assertFalse(second['has_more'])
        for query in ({'cursor': cursor + 'x'}, {'cursor': cursor, 'status': 'queued'}, {'limit': 51},
                      {'limit': -1}, {'status': 'secret'}, {'user_id': '2'}):
            self.assertEqual(self.client.get('/api/v2/messages', query).status_code, 422)
        self.assertEqual(self.client.get('/api/v2/messages?limit=1&limit=2').status_code, 422)
        self.assertEqual(self.client.get('/api/v2/messages?limit=۲').status_code, 200)
        other = Client(enforce_csrf_checks=True)
        self.login('09123456788', other)
        self.assertEqual(other.get('/api/v2/messages', {'cursor': cursor}).status_code, 422)
        self.assertEqual(self.client.get('/api/v2/wallet/entries', {'cursor': cursor}).status_code, 422)
        with patch('django.core.signing.time.time', return_value=timezone.now().timestamp() + 8*86400):
            self.assertEqual(self.client.get('/api/v2/messages', {'cursor': cursor}).status_code, 422)

    def test_preferences_recent_auth_account_deletion_and_logout(self):
        self.login()
        self.assertEqual(self.mutate('/me/preferences', {'blocked': True}, method='PATCH').json(), {'blocked': True})
        session = self.client.session
        session['phone_verified_at'] = timezone.now().timestamp() - 301
        session.save()
        self.assertEqual(self.mutate('/me/preferences', {'blocked': False}, method='PATCH').status_code, 403)
        self.assertEqual(self.mutate('/me/deletion-requests').status_code, 403)
        self.login()
        self.assertEqual(self.mutate('/me/preferences', {'blocked': False}, method='PATCH').json(), {'blocked': False})
        self.assertEqual(self.mutate('/me/deletion-requests').json()['requested'], True)
        self.assertTrue(self.client.get('/api/v2/me').json()['suspended'])
        response = self.mutate('/session', method='DELETE')
        self.assertFalse(response.json()['authenticated'])
        self.assertEqual(self.client.get('/api/v2/me').status_code, 401)

    def test_support_send_retry_read_and_page_validation(self):
        self.login()
        key = uuid.uuid4()
        first = self.mutate('/support/messages', {'text': 'یک پرسش درباره اعتبار دارم'}, key=key)
        self.assertEqual(first.status_code, 200, first.content)
        again = self.mutate('/support/messages', {'text': 'یک پرسش درباره اعتبار دارم'}, key=key)
        self.assertEqual(again.json()['message']['id'], first.json()['message']['id'])
        self.assertEqual(SupportMessage.objects.count(), 1)
        self.assertEqual(self.client.get('/api/v2/support/messages').json()['messages'][0]['text'], 'یک پرسش درباره اعتبار دارم')
        self.assertEqual(self.mutate('/support/read-marker', {'through_sequence': 1}, method='PUT').json(), {'ok': True})
        self.assertEqual(self.mutate('/support/read-marker', {'through_sequence': 2}, method='PUT').status_code, 422)
        self.assertEqual(self.client.get('/api/v2/support/messages?before=۰').status_code, 422)
        self.assertEqual(self.client.get('/api/v2/support/messages?before=۲').status_code, 200)

    def test_purchase_history_ownership_and_environment_separation(self):
        user = self.login()
        package = MessagePackage.objects.create(name='بسته تست', message_count=5, price_toman=10000, active=True)
        payload = {'package_id': package.pk, 'package_revision': package.revision, 'payment_method': 'gateway',
                   'wallet_consent': True, 'wallet_terms_version': 'wallet-credit-v1'}
        key = uuid.uuid4()
        response = self.mutate('/credit-purchases', payload, key=key)
        self.assertEqual(response.status_code, 200, response.content)
        purchase_id = response.json()['id']
        self.assertEqual(self.mutate('/credit-purchases', payload, key=key).json()['id'], purchase_id)
        self.assertEqual(CreditPurchase.objects.filter(owner=user).count(), 1)
        self.assertEqual(self.client.get('/api/v2/me/credits').json()['purchased_remaining'], 5)
        self.assertEqual(len(self.client.get('/api/v2/me/credit-entries').json()['results']), 1)
        CreditPurchase.objects.filter(pk=purchase_id).update(environment='live')
        self.assertEqual(self.client.get(f'/api/v2/credit-purchases/{purchase_id}').status_code, 404)
        self.assertEqual(self.client.get('/api/v2/credit-purchases').json()['results'], [])

    def test_disabled_checkout_and_wallet_topup_stay_disabled(self):
        self.login()
        package = MessagePackage.objects.filter(active=True).first()
        with override_settings(PAYMENT_BACKEND='disabled'):
            result = self.mutate('/credit-purchases', {'package_id': package.pk, 'package_revision': package.revision,
                'payment_method': 'gateway', 'wallet_consent': True, 'wallet_terms_version': 'wallet-credit-v1'}, key=uuid.uuid4())
            self.assertEqual(result.status_code, 409)
            self.assertEqual(result.json()['error']['code'], 'payment_disabled')
            result = self.mutate('/wallet/topups', {'amount_toman': 10000, 'consent': True,
                                  'terms_version': 'wallet-credit-v1'}, key=uuid.uuid4())
            self.assertEqual(result.status_code, 409)
        for path in ('/wallet', '/wallet/entries', '/wallet/topups', '/me/credit-entries'):
            self.assertEqual(self.client.get('/api/v2' + path).status_code, 200)
        self.assertEqual(self.client.get('/api/v2/wallet/topups/' + str(uuid.uuid4())).status_code, 404)
        self.assertFalse(CreditPurchase.objects.exists())

    def test_card_receipt_claim_does_not_credit_and_open_purchase_can_be_cancelled(self):
        from core.models import ManualPaymentSettings
        from core.test_manual_payments import CARD
        self.login()
        ManualPaymentSettings.objects.update_or_create(pk=1, defaults={'enabled': True, 'card_number': CARD,
            'card_holder': 'پشتیبان آزمون', 'bank_name': 'بانک آزمون', 'bale_username': 'test_support'})
        package = MessagePackage.objects.filter(active=True).first()
        data = {'package_id': package.pk, 'package_revision': package.revision, 'payment_method': 'card',
                'wallet_consent': True, 'wallet_terms_version': 'wallet-credit-v1'}
        result = self.mutate('/credit-purchases', data, key=uuid.uuid4())
        self.assertEqual(result.status_code, 200, result.content)
        identifier = result.json()['id']
        self.assertEqual(self.client.get(f'/api/v2/credit-purchases/{identifier}').status_code, 200)
        self.assertEqual(self.mutate(f'/credit-purchases/{identifier}', method='DELETE').json()['status'], 'cancelled')
        result = self.mutate('/credit-purchases', data, key=uuid.uuid4())
        self.assertEqual(result.status_code, 200, result.content)
        identifier = result.json()['id']
        claim = self.mutate(f'/credit-purchases/{identifier}/receipt', {'receipt_sent': True, 'reference': 'BANK123456'}, method='PUT')
        self.assertEqual(claim.status_code, 200, claim.content)
        self.assertEqual(claim.json()['status'], 'awaiting_review')
        self.assertEqual(self.client.get('/api/v2/me/credits').json()['purchased_remaining'], 0)
        self.assertEqual(self.mutate(f'/credit-purchases/{identifier}', method='DELETE').status_code, 409)
        # A pending transfer review prevents another checkout.
        second = self.mutate('/credit-purchases', data, key=uuid.uuid4())
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.json()['error']['code'], 'payment_reconciliation')

    @override_settings(APP_BASE_URL='https://begamnagam.ir')
    def test_received_capability_inspect_stop_and_report_keep_sender_private(self):
        self.login()
        preview = self.make_preview()
        message = self.reserve(preview).json()
        with self.captureOnCommitCallbacks(execute=True):
            result = self.mutate(f'/messages/{message["id"]}/submission', method='PUT')
        self.assertEqual(result.status_code, 200)
        token = preview['full_sms'].rsplit('/r/', 1)[1]
        recipient = Client(enforce_csrf_checks=True)
        inspection = self.mutate('/recipient-capabilities/inspections', {'token': token}, client=recipient)
        self.assertEqual(inspection.json(), {'active': True, 'can_report': True})
        self.assertEqual(self.mutate('/recipient-capabilities/preference', {'token': token}, method='PUT', client=recipient).json(), {'blocked': True})
        report = self.mutate('/recipient-reports', {'token': token, 'reason': 'unwanted', 'details': 'توضیح آزمون'}, client=recipient)
        self.assertEqual(report.status_code, 200, report.content)
        self.assertEqual(set(report.json()), {'receipt', 'blocked'})
        self.assertEqual(self.client.get('/api/v2/me/preferences').json(), {'blocked': False})

    def test_batch_receipts_match_legacy_payment_and_refund_outcomes(self):
        from core.models import PaymentAttempt, Refund
        from core.services import serialize_order, serialize_orders
        self.login()
        identifier = self.reserve().json()['id']
        Order.objects.filter(pk=identifier).update(is_free=False, uses_purchased_credit=False, payment_method='legacy', amount_toman=2000)
        order = Order.objects.get(pk=identifier)
        payment = PaymentAttempt.objects.create(order=order, amount_toman=2000, status='verified', applied_to_order=True)
        refund = Refund.objects.create(payment=payment, amount_toman=2000, status='requested', reason_code='test')
        self.assertEqual(serialize_orders([order]), [serialize_order(order)])
        refund.status = 'refunded'
        refund.save(update_fields=['status'])
        self.assertEqual(serialize_orders([order]), [serialize_order(order)])
        self.assertEqual(serialize_orders([order])[0]['financial_status'], 'refunded')
        payment.return_to_wallet = True
        payment.save(update_fields=['return_to_wallet'])
        self.assertEqual(serialize_orders([order]), [serialize_order(order)])
        self.assertEqual(serialize_orders([order])[0]['financial_status'], 'wallet_returned')

    def test_invitation_flow_detail_and_other_owner(self):
        self.login()
        key = uuid.uuid4()
        data = {'phone': '09901234567', 'consent': True, 'consent_version': 'invitations-v1'}
        result = self.mutate('/invitations', data, key=key)
        self.assertEqual(result.status_code, 200, result.content)
        identifier = result.json()['id']
        self.assertEqual(self.mutate('/invitations', data, key=key).json()['id'], identifier)
        self.assertEqual(Invitation.objects.count(), 1)
        self.assertEqual(self.client.get(f'/api/v2/invitations/{identifier}').status_code, 200)
        self.assertEqual(self.client.get('/api/v2/invitations').json()['results'][0]['id'], identifier)
        summary = self.client.get('/api/v2/invitations/summary').json()
        self.assertEqual(summary['total'], 1)
        self.assertEqual(summary['earned_credits'], 0)
        other = Client(enforce_csrf_checks=True)
        self.login('09123456788', other)
        self.assertEqual(other.get(f'/api/v2/invitations/{identifier}').status_code, 404)
        self.assertEqual(self.mutate(f'/invitations/{identifier}/reminders',
                         {'consent': True, 'consent_version': 'invitations-v1'}, key=uuid.uuid4(), client=other).status_code, 404)

    def test_real_provider_otp_failure_never_falls_back_to_demo(self):
        from core.providers import ProviderDisabled
        with override_settings(OTP_BACKEND='kavenegar', LOCAL_REAL_OTP_ENABLED=True):
            with patch('core.budget.reserve_cost'), patch('core.providers.Kavenegar.otp', side_effect=ProviderDisabled('provider_network_disabled')):
                result = self.mutate('/auth/otp-challenges', {'phone': '09123456789'})
        self.assertEqual(result.status_code, 503)
        self.assertNotIn('debug_code', result.json())
        self.assertIsNotNone(OTPChallenge.objects.get().consumed_at)

    def test_unknown_real_otp_remains_challenge_and_never_exposes_code(self):
        from core.providers import ProviderUnknown
        with override_settings(OTP_BACKEND='kavenegar', LOCAL_REAL_OTP_ENABLED=True):
            with patch('core.budget.reserve_cost'), patch('core.providers.Kavenegar.otp', side_effect=ProviderUnknown('transport_or_format')):
                result = self.mutate('/auth/otp-challenges', {'phone': '09123456789'})
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.json()['delivery_status'], 'unknown')
        self.assertNotIn('debug_code', result.json())
        self.assertIsNone(OTPChallenge.objects.get().consumed_at)

    def test_method_allow_and_private_headers(self):
        self.login()
        response = self.mutate('/me', method='PUT')
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response['Allow'], 'GET')
        for path in ('/me', '/catalog', '/messages'):
            response = self.client.get('/api/v2' + path)
            self.assertEqual(response['Cache-Control'], 'no-store')
            self.assertIn('noindex', response['X-Robots-Tag'])
            self.assertEqual(response['Referrer-Policy'], 'no-referrer')
            self.assertIn('X-Request-ID', response)


@override_settings(API_DOCUMENTATION_ENABLED=True)
class PrivateDocumentationTests(TestCase):
    paths = ['/document', '/document/openapi.json', '/document/guide', '/document/client.py',
             '/document/assets/init.js', '/document/assets/swagger-ui-bundle.js',
             '/document/assets/swagger-ui.css', '/document/assets/docs.css', '/document/assets/font.woff2']

    def setUp(self):
        self.client = Client()
        self.staff = get_user_model().objects.create_user(username='docs-staff', is_staff=True)

    def grant(self):
        self.staff.user_permissions.add(Permission.objects.get(codename='view_api_documentation'))
        self.client.force_login(self.staff)

    def test_all_docs_and_assets_are_hidden_for_anonymous_or_unprivileged_staff(self):
        for path in self.paths:
            self.assertEqual(self.client.get('/api/v2' + path).status_code, 404)
        self.client.force_login(self.staff)
        for path in self.paths:
            self.assertEqual(self.client.get('/api/v2' + path).status_code, 404)

    def test_permission_alone_without_staff_status_is_not_sufficient(self):
        self.grant()
        get_user_model().objects.filter(pk=self.staff.pk).update(is_staff=False)
        for path in self.paths:
            self.assertEqual(self.client.get('/api/v2' + path).status_code, 404)

    def test_enabled_scoped_staff_access_and_disabled_gate(self):
        self.grant()
        for path in self.paths:
            response = self.client.get('/api/v2' + path)
            self.assertEqual(response.status_code, 200, path)
            self.assertEqual(response['Cache-Control'], 'no-store')
            self.assertIn('noindex', response['X-Robots-Tag'])
            if response.streaming:
                b''.join(response.streaming_content)
        with override_settings(API_DOCUMENTATION_ENABLED=False):
            for path in self.paths:
                self.assertEqual(self.client.get('/api/v2' + path).status_code, 404)
        self.assertEqual(self.client.get('/api/v2/me').status_code, 401)
        self.assertEqual(self.client.get('/api/v2/catalog').status_code, 200)

    def test_schema_export_works_offline_without_enabling_http_docs(self):
        output = io.StringIO()
        with override_settings(API_DOCUMENTATION_ENABLED=False):
            call_command('export_api_schema', stdout=output)
        self.assertEqual(json.loads(output.getvalue()), specification())
        self.assertEqual(self.client.get('/api/v2/document/openapi.json').status_code, 404)

    def test_schema_and_swagger_have_no_external_validator_or_asset_dependency(self):
        self.grant()
        schema = self.client.get('/api/v2/document/openapi.json').json()
        self.assertEqual(schema['servers'], [{'url': '/api/v2', 'description': 'Same-origin API'}])
        html = self.client.get('/api/v2/document').content.decode()
        self.assertNotIn('https://', html)
        self.assertNotIn('<script>', html)
        init = (ASSETS / 'init.js').read_text()
        self.assertIn('validatorUrl: null', init)
        self.assertIn('persistAuthorization: false', init)
        self.assertEqual(self.client.get('/api/v2/document/assets/source.json').status_code, 404)
        self.assertEqual(self.client.get('/api/v2/document/assets/unknown.js').status_code, 404)
        for name, value in json.loads((ASSETS / 'source.json').read_text())['files'].items():
            self.assertEqual(hashlib.sha256((ASSETS / name).read_bytes()).hexdigest(), value['sha256'])


class BotClientTests(SimpleTestCase):
    def setUp(self):
        path = Path(__file__).parent / 'api_v2/integration/client.py'
        spec = importlib.util.spec_from_file_location('begamnagam_sample_client', path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_client_does_not_contact_network_at_import_or_construction(self):
        with patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('network')):
            client = self.module.BotAPI('https://begamnagam.ir/api/v2')
        self.assertTrue(client.require_real_otp)
        self.assertTrue(client.require_real_delivery)
        self.assertEqual(len(client.jar), 0)

    def test_client_enforces_https_except_loopback_and_has_separate_cookie_jars(self):
        for url in ('http://example.com/api/v2', 'https://a.test/api/v1', 'https://x:secret@a.test/api/v2',
                    'https://a.test/api/v2?x=1', 'https://a.test/api/v2#token'):
            with self.assertRaises(ValueError):
                self.module.BotAPI(url)
        first = self.module.BotAPI('http://127.0.0.1:8000/api/v2')
        second = self.module.BotAPI('http://127.0.0.1:8000/api/v2')
        self.assertIsNot(first.jar, second.jar)

    def test_client_rotates_csrf_and_preserves_idempotency_without_automatic_retry(self):
        client = self.module.BotAPI('https://begamnagam.ir/api/v2')
        old, new = 'old-csrf', 'new-csrf'
        results = [{'csrf_token': old, 'authenticated': False}, {'csrf_token': new, 'authenticated': True}, {'id': 'message'}]
        requests = []
        def respond(request, **kwargs):
            requests.append(request)
            return io.BytesIO(json.dumps(results.pop(0)).encode())
        with patch.object(client.opener, 'open', side_effect=respond):
            client.refresh_session()
            client.verify_otp(str(uuid.uuid4()), '0123')
            client.call('POST', '/messages', {'x': 1}, key='stored-key')
        self.assertEqual(requests[1].get_header('X-csrftoken'), old)
        self.assertEqual(requests[2].get_header('X-csrftoken'), new)
        self.assertEqual(requests[2].get_header('Idempotency-key'), 'stored-key')
        self.assertEqual(len(requests), 3)

    def test_real_execution_rejects_demo_and_requires_explicit_consent(self):
        client = self.module.BotAPI('https://begamnagam.ir/api/v2')
        with patch.object(client, 'refresh_session', return_value={'otp_is_real': False, 'demo_mode': True}):
            with self.assertRaises(RuntimeError):
                client.request_otp('09123456789')
            with self.assertRaises(RuntimeError):
                client.submit_message(str(uuid.uuid4()))
        with self.assertRaises(ValueError):
            client.reserve_message({}, '09901234567', key=uuid.uuid4(), consent=False)
