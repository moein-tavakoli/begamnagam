from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from core.models import Account
from core.privacy import digest, encrypt, mask


class Command(BaseCommand):
    help = 'Create1000 synthetic accounts only in an explicitly isolated demo benchmark database.'

    def handle(self, *args, **options):
        if not settings.DEMO_MODE or not connection.settings_dict['NAME'].startswith('begamnagam_bench_') or not settings.BENCHMARK_RUN_ID:
            raise CommandError('Refusing to seed a normal or live database')
        if Account.objects.exists():
            raise CommandError('Benchmark database is not empty')
        with transaction.atomic():
            User = get_user_model()
            phones = ['099'+str(i).zfill(8) for i in range(1000)]
            users = User.objects.bulk_create([User(username='phone_'+digest(p), password='!benchmark-unusable') for p in phones])
            Account.objects.bulk_create([Account(user=u,phone_hash=digest(p),phone_cipher=encrypt(p),phone_masked=mask(p)) for u,p in zip(users,phones)])
        self.stdout.write('Created1000 synthetic accounts; no provider request or usable password.')
