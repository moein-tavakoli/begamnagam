import json
import uuid
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings

from . import tests as fixture
from .limit_services import editable_values
from .limits import defaults
from .models import Account, OperatorAudit, Order, Preview, SafetyControl, SiteLimits


class BundlePricingCompatibilityTests(TestCase):
    post, authenticate, preview = fixture.APITestCase.post, fixture.APITestCase.authenticate, fixture.APITestCase.preview

    def setUp(self):
        fixture.APITestCase.setUp(self)
        self.user = self.authenticate(free_sends=0)
        self.manager = get_user_model().objects.create_user(username='tariff-manager', is_staff=True)
        self.manager.user_permissions.add(Permission.objects.get(codename='manage_site_limits'))
        self.staff = Client(); self.staff.force_login(self.manager)

    def test_legacy_tariff_is_not_editable_and_public_quotes_stay_zero(self):
        response = self.staff.get('/api/v1/manage/limits')
        self.assertNotIn('price_toman', response.json()['values'])
        result = self.staff.post('/api/v1/manage/limits', {'values': {'price_toman': 7350}, 'revision': response.json()['revision'], 'reason': 'Set wallet send price'}, content_type='application/json')
        self.assertEqual(result.status_code, 422)
        with override_settings(PRICE_TOMAN=9990):
            self.assertEqual(self.client.get('/api/v1/bootstrap').json()['price_toman'], 0)
            self.assertEqual(self.preview()['price_toman'], 0)

    def test_historical_single_quote_requires_a_new_preview(self):
        quote = self.preview()
        Preview.objects.filter(pk=quote['preview_id']).update(price_toman=2000)
        response = self.post('/orders', {'preview_id': quote['preview_id'], 'recipient_phone': '09901234567'}, HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(response.json()['error']['code'], 'preview_expired')
        self.assertFalse(Order.objects.exists())


class PriceMigrationTests(TransactionTestCase):
    def test_existing_installation_preserves_its_configured_price(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        old = [('core', '0020_private_original_message_text')]
        try:
            executor.migrate(old)
            apps = executor.loader.project_state(old).apps
            apps.get_model('core', 'SiteLimits').objects.create(pk=1)
            with override_settings(PRICE_TOMAN=9150):
                executor = MigrationExecutor(connection)
                executor.migrate(latest)
            self.assertEqual(SiteLimits.objects.get(pk=1).price_toman, 9150)
        finally:
            MigrationExecutor(connection).migrate(latest)
