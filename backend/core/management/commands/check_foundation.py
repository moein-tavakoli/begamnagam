from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from kombu import Connection
import uuid


class Command(BaseCommand):
    help = 'Readiness check for local demo only; no SMS, model or payment request.'

    def handle(self, *args, **options):
        if not settings.DEMO_MODE or settings.SMS_BACKEND != 'console' or settings.PAYMENT_BACKEND != 'demo' or settings.AI_MODE != 'template':
            raise CommandError('Foundation expects demo/console/template adapters only')
        if connection.vendor != 'postgresql' or not settings.REDIS_URL or not settings.CELERY_BROKER_URL.startswith(('amqp://', 'amqps://')):
            raise CommandError('PostgreSQL, Redis and RabbitMQ configuration required')
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            executor = MigrationExecutor(connection)
            if executor.migration_plan(executor.loader.graph.leaf_nodes()):
                raise CommandError('Unapplied migrations; run migrate before readiness check')
            key = f'foundation-check:{uuid.uuid4()}'
            try:
                cache.set(key, 'ok', timeout=10)
                if cache.get(key) != 'ok': raise CommandError('Redis readiness failed')
            finally:
                cache.delete(key)
            with Connection(settings.CELERY_BROKER_URL, connect_timeout=5) as broker:
                broker.connect()
        except CommandError:
            raise
        except Exception:
            # Never print connection URLs (which can contain credentials).
            raise CommandError('A local infrastructure dependency is unavailable') from None
        self.stdout.write(self.style.SUCCESS('PASS: PostgreSQL / migrations / Redis / RabbitMQ / demo-only adapters'))
