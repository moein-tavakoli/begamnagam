"""Evaluate only fixed synthetic fixtures against the real local model; no SMS."""
import json
import time
from pathlib import Path
from django.core.management.base import BaseCommand
from core.ai_config import current
from core.draft_guard import sanitize_draft, validate_polite_body
from core.gapgpt import GapGPTRejected, GapGPTUnavailable
from core.moderation import ModerationRejected
from core.ollama_rewrite import rewrite_message, slot


class Command(BaseCommand):
    help = 'Measure real local AI on synthetic Persian cases, without sending or storing user messages.'

    def add_arguments(self, parser):
        parser.add_argument('--model', default='')
        parser.add_argument('--case', default='')

    def handle(self, *args, **options):
        config = current(); config.provider = 'ollama'
        if options['model']: config.ollama_model = options['model']
        config.clean()
        cases = json.loads((Path(__file__).resolve().parents[2]/'fixtures/ollama-evaluation.json').read_text())
        rows = []
        for case in cases:
            if options['case'] and case['id'] != options['case']: continue
            started = time.monotonic(); result = ''; status = 'rejected'; stage = 'local_guard'
            try:
                cleaned = sanitize_draft(case['text']); stage = 'model'
                with slot(config.parallel_requests):
                    result = rewrite_message(cleaned, max_units=140, config=config)
                validate_polite_body(result, max_units=140); status = 'accepted'
            except (ModerationRejected, GapGPTRejected):
                pass
            except GapGPTUnavailable as error:
                status = str(error)
            row = {'id': case['id'], 'source': case['text'], 'expected_allowed': case['allow'],
                'status': status, 'stage': stage, 'message': result,
                'elapsed_seconds': round(time.monotonic()-started, 3),
                'classification_matches': (status == 'accepted') == case['allow'] and status in {'accepted', 'rejected'}}
            rows.append(row)
            self.stdout.write(json.dumps(row, ensure_ascii=False)); self.stdout.flush()
        self.stdout.write(json.dumps({'model': config.ollama_model, 'cases': len(rows),
            'classification_matches': sum(row['classification_matches'] for row in rows),
            'requires_human_intent_review': True, 'sms_sent': 0}, ensure_ascii=False))
