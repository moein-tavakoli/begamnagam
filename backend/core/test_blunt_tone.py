"""Blunt is minimal editing with the same independently enforced safety boundary."""

from unittest.mock import patch
from django.test import TestCase, override_settings
from . import test_message_tones as fixtures
from .models import AIConfiguration, Preview
from .message_tones import choices, resolve


class BluntToneTests(TestCase):
    def setUp(self):
        fixtures.TonePolicyTests.setUp(self)
        self.config.tone_firm_enabled = True
        self.config.tone_blunt_enabled = True
        self.config.save()

    post = fixtures.TonePolicyTests.post
    authenticate = fixtures.TonePolicyTests.authenticate
    quote = fixtures.TonePolicyTests.quote

    def test_three_choices_and_default_are_shared_by_web_and_v2(self):
        expected = [('polite', 'مودبانه'), ('firm', 'کمی مودبانه'), ('blunt', 'رُک')]
        for url in ['/api/v1/bootstrap', '/api/v2/catalog']:
            data = self.client.get(url).json()
            self.assertEqual(
                [(row['id'], row['label']) for row in data['message_tones']], expected
            )
            self.assertEqual(data['default_message_tone'], 'firm')
        self.assertEqual(self.quote().json()['message_tone'], 'firm')

    def test_legacy_angry_is_not_a_fourth_public_option(self):
        self.config.tone_angry_enabled = True
        self.assertEqual(
            [row['id'] for row in choices(self.config)], ['polite', 'firm', 'blunt']
        )
        self.assertEqual(resolve('angry', self.config), 'angry')

    @override_settings(
        AI_MODE='gapgpt',
        GAPGPT_API_KEY='synthetic-key',
        GAPGPT_MODEL='synthetic-model',
        GAPGPT_DAILY_REQUEST_LIMIT=20,
        GAPGPT_USER_DAILY_LIMIT=10,
    )
    def test_blunt_keeps_clean_colloquial_source_and_rejects_unsafe_output(self):
        AIConfiguration.objects.update(provider='gapgpt')
        with patch(
            'core.gapgpt.rewrite_message', return_value='حلالم کن داداش'
        ) as model:
            result = self.quote('blunt', text='حلالم کن داداش')
            self.assertEqual(result.status_code, 200, result.content)
            self.assertEqual(result.json()['rewritten_text'], 'حلالم کن داداش')
            self.assertEqual(model.call_args.args[0], 'حلالم کن داداش')
            self.assertEqual(model.call_args.kwargs['message_tone'], 'blunt')
        Preview.objects.all().delete()
        with patch('core.gapgpt.rewrite_message') as model:
            for text in ['می کشمت', 'احمق بیشعور', 'به 09123456789 زنگ بزن']:
                self.assertEqual(self.quote('blunt', text=text).status_code, 422)
            model.assert_not_called()
        with patch(
            'core.gapgpt.rewrite_message', return_value='احمق، وسایلم را برندار.'
        ):
            self.assertEqual(self.quote('blunt').status_code, 422)
        self.assertFalse(Preview.objects.exists())

    def test_enable_migration_preserves_provider_and_non_tone_settings(self):
        import importlib
        from types import SimpleNamespace
        from django.apps import apps
        from django.db import connection
        from .models import OperatorAudit

        AIConfiguration.objects.filter(pk=1).update(
            tone_polite_enabled=False,
            tone_firm_enabled=False,
            tone_blunt_enabled=False,
            revision=17,
        )
        config = AIConfiguration.objects.get(pk=1)
        unchanged = {
            field.name: getattr(config, field.name)
            for field in config._meta.fields
            if field.name
            not in {
                'tone_polite_enabled',
                'tone_firm_enabled',
                'tone_blunt_enabled',
                'revision',
                'updated_at',
            }
        }
        migration = importlib.import_module(
            'core.migrations.0040_enable_requested_tones'
        )
        migration.enable_requested_tones(apps, SimpleNamespace(connection=connection))
        config.refresh_from_db()
        self.assertEqual(config.revision, 18)
        self.assertEqual(resolve(None, config), 'firm')
        self.assertEqual(
            [row['id'] for row in choices(config)], ['polite', 'firm', 'blunt']
        )
        self.assertEqual({name: getattr(config, name) for name in unchanged}, unchanged)
        audit = OperatorAudit.objects.get(action='enable_requested_tones')
        self.assertEqual(audit.before['revision'], 17)
        self.assertEqual(audit.after['revision'], 18)
