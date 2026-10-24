import json
from pathlib import Path
from tempfile import TemporaryDirectory
from django.test import TestCase
from core.management.commands.release_readiness import HUMAN_CHECKS, human_results, collect


class ReleaseGateTests(TestCase):
    def test_missing_or_empty_human_file_cannot_approve(self):
        self.assertEqual(set(human_results().values()), {'PENDING'})
        with TemporaryDirectory() as folder:
            path = Path(folder)/'checks.json'
            path.write_text('{"checks": []}')
            self.assertEqual(set(human_results(path).values()), {'PENDING'})

    def test_pass_requires_reviewer_date_and_evidence_for_every_check(self):
        with TemporaryDirectory() as folder:
            path = Path(folder)/'checks.json'
            items = [{'id': key, 'status': 'PASS'} for key in HUMAN_CHECKS]
            path.write_text(json.dumps({'checks': items}))
            self.assertEqual(set(human_results(path).values()), {'PENDING'})
            for item in items:
                item.update(reviewer=None, reviewed_at='2026-10-24T10:00:00Z', evidence=None)
            path.write_text(json.dumps({'checks': items}))
            self.assertEqual(set(human_results(path).values()), {'PENDING'})
            for item in items:
                item.update(reviewer='Synthetic unit-test reviewer', reviewed_at='2026-10-24T10:00:00Z', evidence='synthetic-unit-test-only')
            path.write_text(json.dumps({'checks': items}))
            self.assertEqual(set(human_results(path).values()), {'RECORDED_PASS'})

    def test_demo_and_unreviewed_human_gates_prevent_live_readiness(self):
        result = collect()
        self.assertFalse(result['live_ready'])
        self.assertFalse(result['publication_authorized'])
        self.assertIn('non_demo', result['blockers'])
        self.assertIn('human:volunteer_pilot', result['blockers'])
