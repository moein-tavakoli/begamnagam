"""Fixed synthetic abuse/normal-use corpus; never calls a model or live provider."""
import json
from itertools import product
from pathlib import Path
from django.test import SimpleTestCase, override_settings
from .moderation import DIRECT_TEMPLATES, ModerationRejected, TEMPLATES, rewrite


@override_settings(AI_MODE='template')
class ModerationCorpusTests(SimpleTestCase):
    def test_120_synthetic_inputs_reject_abuse_or_return_only_reviewed_template(self):
        cases = json.loads((Path(__file__).parent / 'fixtures/moderation-corpus.json').read_text())
        self.assertEqual(len(cases), 120)
        self.assertEqual(len({c['id'] for c in cases}), 120)
        for case, direct in product(cases, [False, True]):
            with self.subTest(case=case['id'], kind=case['kind'], direct=direct):
                if case['expect'] == 'rejected':
                    with self.assertRaises(ModerationRejected):
                        rewrite(case['category'], case['text'], direct=direct)
                else:
                    output, mode = rewrite(case['category'], case['text'], direct=direct)
                    self.assertIn(output, (DIRECT_TEMPLATES if direct else TEMPLATES)[case['category']])
                    self.assertEqual(mode, 'template')
                    self.assertNotEqual(output, case['text'])
