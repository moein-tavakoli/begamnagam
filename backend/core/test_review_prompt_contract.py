"""Review requests must classify, never repeat generation instructions."""

import json
from unittest.mock import Mock, patch
from django.test import SimpleTestCase, override_settings
from . import test_gapgpt as fixtures
from .gapgpt import rewrite_message


@override_settings(
    AI_MODE='gapgpt',
    GAPGPT_API_KEY='synthetic-key',
    GAPGPT_MODEL='synthetic-model',
    GAPGPT_TIMEOUT_SECONDS=5,
)
class ReviewPromptContractTests(SimpleTestCase):
    def test_blunt_review_requests_only_the_exact_classification_schema(self):
        source = 'حلالم کن داداش'
        opener = Mock()
        opener.open.side_effect = [
            fixtures._Response(
                fixtures._completion({'allowed': True, 'message': source})
            ),
            fixtures._Response(
                fixtures._completion({**fixtures.VERDICT, 'tone_matched': True})
            ),
        ]
        with patch('core.gapgpt.urllib.request.build_opener', return_value=opener):
            self.assertEqual(
                rewrite_message(source, max_units=140, message_tone='blunt'), source
            )
        prompt = json.loads(opener.open.call_args_list[1].args[0].data)['messages'][0][
            'content'
        ]
        self.assertNotIn('return it unchanged', prompt)
        self.assertNotIn('Preserve the exact cleaned source whenever', prompt)
        self.assertIn('Do not rewrite', prompt)
        marker = 'Required classification JSON schema: '
        self.assertIn(marker, prompt)
        schema = json.loads(prompt.split(marker)[1])
        expected = set(fixtures.VERDICT) | {'tone_matched'}
        self.assertEqual(set(schema['required']), expected)
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(
            schema['properties'], {key: {'type': 'boolean'} for key in expected}
        )

    def test_generation_shaped_review_stays_rejected_without_logging_its_text(self):
        from .gapgpt import GapGPTUnavailable

        source = 'حلالم کن داداش'
        private_review_text = 'محتوای خصوصی ساختگی بازبین'
        opener = Mock()
        opener.open.side_effect = [
            fixtures._Response(
                fixtures._completion({'allowed': True, 'message': source})
            ),
            fixtures._Response(
                fixtures._completion(
                    {
                        'allowed': True,
                        'message': private_review_text,
                        'tone_matched': True,
                    }
                )
            ),
        ]
        with patch(
            'core.gapgpt.urllib.request.build_opener', return_value=opener
        ), self.assertLogs('core.gapgpt', level='WARNING') as logs:
            with self.assertRaises(GapGPTUnavailable):
                rewrite_message(source, max_units=140, message_tone='blunt')
        output = ' '.join(logs.output)
        self.assertIn('unknown_count=2', output)
        self.assertIn('register_preserved', output)
        self.assertNotIn(private_review_text, output)
        self.assertNotIn(source, output)

    @override_settings(OLLAMA_URL='http://127.0.0.1:11434/api/chat')
    def test_local_provider_uses_same_classifier_without_generation_commands(self):
        from . import test_ollama_rewrite as local_fixtures
        from .ollama_rewrite import rewrite_message as local_rewrite
        from .models import AIConfiguration

        source = 'حلالم کن داداش'
        verdict = {**fixtures.VERDICT, 'tone_matched': True}
        opener = Mock()
        opener.open.side_effect = [
            local_fixtures.response({'allowed': True, 'message': source}),
            local_fixtures.response(verdict),
        ]
        with patch(
            'core.ollama_rewrite.urllib.request.build_opener', return_value=opener
        ):
            self.assertEqual(
                local_rewrite(
                    source,
                    max_units=140,
                    message_tone='blunt',
                    config=AIConfiguration(provider='ollama'),
                ),
                source,
            )
        payload = json.loads(opener.open.call_args_list[1].args[0].data)
        prompt = payload['messages'][0]['content']
        self.assertNotIn('return it unchanged', prompt)
        self.assertNotIn('Preserve the exact cleaned source whenever', prompt)
        schema = json.loads(prompt.split('Required classification JSON schema: ')[1])
        self.assertEqual(set(schema['required']), set(payload['format']['required']))
        self.assertFalse(schema['additionalProperties'])
