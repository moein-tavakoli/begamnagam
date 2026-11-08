import json
import re
from importlib.resources import files
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings


class PersianCatalogTests(SimpleTestCase):
    def test_packaged_catalog_is_persian_unique_ordered_and_does_not_invent_dates(self):
        data = json.loads(files('core').joinpath('release_notes.fa.json').read_text(encoding='utf-8'))
        entries = data['entries']
        versions = [entry['version'] for entry in entries]
        self.assertEqual(len(versions), len(set(versions)))
        self.assertEqual(versions, sorted(versions, key=lambda v:tuple(map(int,v.split('.'))), reverse=True))
        self.assertEqual(data['catalog_version'], versions[0])
        for entry in entries:
            self.assertRegex(entry['version'], r'^\d+\.\d+\.\d+$')
            self.assertIn(entry['scope'], ('local', 'history'))
            self.assertTrue(entry['date'] is None or re.fullmatch(r'\d{4}-\d{2}-\d{2}', entry['date']))
            self.assertRegex(entry['title'], r'[\u0600-\u06ff]')
            for text in entry['changes']:
                self.assertRegex(text, r'[\u0600-\u06ff]')
                self.assertNotIn('<', text)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ManagementChangelogTests(TestCase):
    path = '/api/v1/manage/changelog'

    def test_private_history_denies_anonymous_members_and_inactive_staff(self):
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 401)
        self.assertNotIn('entries', response.json())
        member = get_user_model().objects.create_user('changelog-member')
        self.client.force_login(member)
        self.assertEqual(self.client.get(self.path).status_code, 403)
        staff = get_user_model().objects.create_user('inactive-history', is_staff=True, is_active=False)
        self.client.force_login(staff, backend='django.contrib.auth.backends.ModelBackend')
        self.assertNotEqual(self.client.get(self.path).status_code, 200)

    def test_active_staff_can_read_persian_notes_without_product_account(self):
        staff = get_user_model().objects.create_user('history-staff', is_staff=True)
        self.client.force_login(staff)
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn('cookie', response['Vary'].lower())
        data = response.json()
        self.assertEqual(data['locale'], 'fa-IR')
        self.assertEqual(data['catalog_version'], data['entries'][0]['version'])
        self.assertGreater(len(data['entries']), 50)
        self.assertEqual(data['entries'][0]['scope'], 'local')
        for entry in data['entries']:
            self.assertRegex(entry['title'], r'[\u0600-\u06ff]')
            self.assertTrue(entry['changes'])
        self.assertEqual(self.client.post(self.path, {}, content_type='application/json').status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.get(self.path).status_code, 401)
