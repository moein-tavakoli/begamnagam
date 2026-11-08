import json
from unittest.mock import Mock, patch
from django.test import SimpleTestCase, override_settings
from .gapgpt import rewrite_message, GapGPTRejected, GapGPTUnavailable
from .test_gapgpt import _Response, _completion
from .test_ollama_rewrite import response as local_response
from .models import AIConfiguration

COLLOQUIAL = 'از کمکی که کردی خیلی ممنونم.'
FORMAL = 'از کمکی که به من کردید سپاسگزارم.'
CHECKS = dict(
    safe=True,
    intent_preserved=True,
    no_added_claims=True,
    no_private_data=True,
    only_message=True,
    register_preserved=True,
)


@override_settings(
    AI_MODE='gapgpt',
    GAPGPT_API_KEY='synthetic-key',
    GAPGPT_MODEL='synthetic-model',
    GAPGPT_TIMEOUT_SECONDS=5,
    OLLAMA_URL='http://127.0.0.1:11434/api/chat',
)
class ColloquialReviewTests(SimpleTestCase):
    def remote(self, body, verdict):
        opener = Mock()
        opener.open.side_effect = [
            _Response(_completion({'allowed': True, 'message': body})),
            _Response(_completion(verdict)),
        ]
        return opener

    def test_already_suitable_colloquial_text_can_return_unchanged_with_separate_review(
        self,
    ):
        opener = self.remote(COLLOQUIAL, CHECKS)
        with patch('core.gapgpt.urllib.request.build_opener', return_value=opener):
            result = rewrite_message(COLLOQUIAL, max_units=140, message_tone='polite')
        self.assertEqual(result, COLLOQUIAL)
        self.assertEqual(
            json.loads(opener.open.call_args_list[1].args[0].data)['messages'][1][
                'content'
            ],
            json.dumps(
                {'source': COLLOQUIAL, 'candidate': COLLOQUIAL},
                ensure_ascii=False,
                separators=(',', ':'),
            ),
        )
        self.assertEqual(opener.open.call_count, 2)

    def test_forgiveness_and_friendly_wishes_survive_local_checks_and_both_providers(
        self,
    ):
        from .draft_guard import sanitize_draft, validate_polite_body
        from .ollama_rewrite import rewrite_message as local_rewrite

        examples = [
            'حلالم کن داداش',
            'یک اروزی دوستان، امروز روزی پر از ارامش و مهربانی و حال خوب باشه',
        ]
        for source in examples:
            cleaned = sanitize_draft(source)
            self.assertEqual(validate_polite_body(cleaned, max_units=140), cleaned)
            with self.subTest(source=source, provider='gapgpt'):
                opener = self.remote(cleaned, CHECKS)
                with patch(
                    'core.gapgpt.urllib.request.build_opener', return_value=opener
                ):
                    self.assertEqual(
                        rewrite_message(cleaned, max_units=140, message_tone='polite'),
                        cleaned,
                    )
            with self.subTest(source=source, provider='ollama'):
                opener = Mock()
                opener.open.side_effect = [
                    local_response({'allowed': True, 'message': cleaned}),
                    local_response(CHECKS),
                ]
                with patch(
                    'core.ollama_rewrite.urllib.request.build_opener',
                    return_value=opener,
                ):
                    self.assertEqual(
                        local_rewrite(
                            cleaned,
                            max_units=140,
                            message_tone='polite',
                            config=AIConfiguration(provider='ollama'),
                        ),
                        cleaned,
                    )

    def test_unnecessary_formalization_is_rejected_even_when_other_checks_pass(self):
        opener = self.remote(FORMAL, {**CHECKS, 'register_preserved': False})
        with patch(
            'core.gapgpt.urllib.request.build_opener', return_value=opener
        ), self.assertRaises(GapGPTRejected) as error:
            rewrite_message(COLLOQUIAL, max_units=140)
        self.assertEqual(error.exception.reason, 'review_register')

    def test_replacing_forgiveness_with_generic_good_wishes_fails_intent_review(self):
        candidate = 'امروز روزی پر از ارامش و مهربانی و حال خوب باشه'
        opener = self.remote(candidate, {**CHECKS, 'intent_preserved': False})
        with patch(
            'core.gapgpt.urllib.request.build_opener', return_value=opener
        ), self.assertRaises(GapGPTRejected) as error:
            rewrite_message('حلالم کن داداش', max_units=140, message_tone='polite')
        self.assertEqual(error.exception.reason, 'review_intent')

    def test_missing_style_review_does_not_silently_pass(self):
        old_checks = {k: v for k, v in CHECKS.items() if k != 'register_preserved'}
        opener = self.remote(COLLOQUIAL, old_checks)
        with patch(
            'core.gapgpt.urllib.request.build_opener', return_value=opener
        ), self.assertRaises(GapGPTUnavailable):
            rewrite_message(COLLOQUIAL, max_units=140)

    def test_local_provider_requires_style_review_too(self):
        from .ollama_rewrite import rewrite_message as local_rewrite

        for preserved in [True, False]:
            opener = Mock()
            opener.open.side_effect = [
                local_response(
                    {'allowed': True, 'message': COLLOQUIAL if preserved else FORMAL}
                ),
                local_response({**CHECKS, 'register_preserved': preserved}),
            ]
            with self.subTest(preserved=preserved), patch(
                'core.ollama_rewrite.urllib.request.build_opener', return_value=opener
            ):
                if preserved:
                    self.assertEqual(
                        local_rewrite(
                            COLLOQUIAL,
                            max_units=140,
                            message_tone='polite',
                            config=AIConfiguration(provider='ollama'),
                        ),
                        COLLOQUIAL,
                    )
                else:
                    with self.assertRaises(GapGPTRejected):
                        local_rewrite(
                            COLLOQUIAL,
                            max_units=140,
                            message_tone='polite',
                            config=AIConfiguration(provider='ollama'),
                        )
