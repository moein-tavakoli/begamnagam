from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings

from .message_examples import is_current_suggestion, public_catalog, write_record
from .models import ExampleCategory, MessageExample, OperatorAudit
from .services import APIError
from . import tests as fixture


class MessageExampleTests(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user('example-editor', is_staff=True)
        self.manager.user_permissions.add(Permission.objects.get(codename='manage_message_examples'))
        self.staff = Client(); self.staff.force_login(self.manager)
        self.group = ExampleCategory.objects.create(name='دستهٔ آزمون', sort_order=900)
        self.values = dict(group_id=self.group.pk, label='عنوان ۱۲', description='', text='سپاس از کمک ۱۲ بار شما', topic='appreciation', active=True, sort_order=0)

    def post(self, path='', data=None):
        return self.staff.post('/api/v1/manage/message-examples' + path, data, content_type='application/json')

    def test_seed_preserves_all_eighteen_examples_and_five_groups(self):
        self.assertEqual(MessageExample.objects.count(), 18)
        catalog = public_catalog()
        self.assertEqual(len(catalog['categories']), 18)
        self.assertEqual(len(catalog['category_groups']), 5)

    def test_reapplying_seed_preserves_existing_edits_without_duplicates(self):
        from importlib import import_module
        from django.apps import apps
        from django.db import connection
        item = MessageExample.objects.first()
        item.text = 'متن ویرایش‌شده'; item.active = False; item.save()
        import_module('core.migrations.0035_seed_message_examples').seed(apps, connection.schema_editor())
        item.refresh_from_db()
        self.assertEqual(MessageExample.objects.count(), 18)
        self.assertEqual(item.text, 'متن ویرایش‌شده')
        self.assertFalse(item.active)

    def test_create_edit_move_and_delete_with_canonical_storage_and_audit(self):
        response = self.post('/examples', {'values': self.values, 'revision': 0, 'reason': 'نمونه ۱۲'})
        self.assertEqual(response.status_code, 200, response.content)
        item = response.json()
        self.assertEqual(item['text'], 'سپاس از کمک 12 بار شما')
        self.assertEqual(item['label'], 'عنوان 12')
        self.assertTrue(is_current_suggestion('appreciation', item['text']))
        next_group = ExampleCategory.objects.exclude(pk=self.group.pk).first()
        changed = {**self.values, 'group_id': next_group.pk, 'text': 'از همراهی همیشگی تو ممنونم', 'active': False}
        response = self.post(f"/examples/{item['id']}", {'values': changed, 'revision': 1, 'reason': 'ویرایش نمونه'})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(is_current_suggestion('appreciation', changed['text']))
        self.assertEqual(MessageExample.objects.get(pk=item['id']).group_id, next_group.pk)
        response = self.post(f"/examples/{item['id']}/delete", {'revision': 2, 'reason': 'حذف نمونه'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(MessageExample.objects.filter(pk=item['id']).exists())
        self.assertEqual(OperatorAudit.objects.filter(actor=self.manager).count(), 3)

    def test_hidden_groups_custom_only_examples_and_positive_pilot(self):
        item = MessageExample.objects.create(**self.values)
        self.group.active = False; self.group.save()
        self.assertFalse(is_current_suggestion(item.topic, item.text))
        self.assertNotIn(self.group.pk, [g['id'] for g in public_catalog()['category_groups']])
        self.group.active = True; self.group.save()
        item.topic = ''; item.save()
        self.assertNotIn(str(item.pk), [c['key'] for c in public_catalog()['categories']])
        self.assertIn(str(item.pk), [c['key'] for c in public_catalog(freeform=True)['categories']])
        with override_settings(PILOT_POSITIVE_ONLY=True):
            self.assertEqual({c['id'] for c in public_catalog(freeform=True)['categories']}, {'appreciation','encouragement','congratulations'})

    def test_stale_update_and_nonempty_category_delete_are_rejected(self):
        item = MessageExample.objects.create(**self.values)
        response = self.post(f'/groups/{self.group.pk}/delete', {'revision': 0, 'reason': 'حذف دسته'})
        self.assertEqual(response.status_code, 409)
        self.assertTrue(MessageExample.objects.filter(pk=item.pk).exists())
        response = self.post(f'/examples/{item.pk}', {'values': self.values, 'revision': 99, 'reason': 'ویرایش قدیمی'})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(OperatorAudit.objects.filter(actor=self.manager).count(), 0)

    def test_category_add_rename_order_and_empty_delete(self):
        response = self.post('/groups', {'values': {'name': 'جدید ۲', 'active': True, 'sort_order': 2}, 'revision': 0, 'reason': 'افزودن دسته'})
        self.assertEqual(response.status_code, 200, response.content)
        group = response.json()
        self.assertEqual(group['name'], 'جدید 2')
        response = self.post(f"/groups/{group['id']}", {'values': {'name': 'نام تازه', 'active': False, 'sort_order': 0}, 'revision': 1, 'reason': 'ویرایش دسته'})
        self.assertEqual(response.status_code, 200)
        response = self.post(f"/groups/{group['id']}/delete", {'revision': 2, 'reason': 'حذف دسته'})
        self.assertEqual(response.status_code, 200)

    def test_validation_and_permissions_fail_without_changes(self):
        for change in ({'text': 'الف' * 281}, {'text': '  '}, {'sort_order': -1}, {'sort_order': True}, {'group_id': 99999}, {'topic': 'unreviewed'}):
            response = self.post('/examples', {'values': {**self.values, **change}, 'revision': 0, 'reason': 'آزمون اعتبارسنجی'})
            self.assertEqual(response.status_code, 422, (change, response.content))
        self.assertEqual(OperatorAudit.objects.filter(actor=self.manager).count(), 0)
        plain = get_user_model().objects.create_user('unprivileged-staff', is_staff=True)
        self.staff.force_login(plain)
        self.assertEqual(self.staff.get('/api/v1/manage/message-examples').status_code, 403)
        self.assertEqual(self.post('/groups', {}).status_code, 403)
        with self.assertRaises(APIError):
            write_record(plain, 'examples', {'values': self.values, 'revision': 0, 'reason': 'نامعتبر'})
        self.assertEqual(Client().get('/api/v1/manage/message-examples').status_code, 401)

    def test_write_requires_csrf(self):
        client = Client(enforce_csrf_checks=True); client.force_login(self.manager)
        response = client.post('/api/v1/manage/message-examples/groups', {'values': {'name': 'جدید'}, 'revision': 0, 'reason': 'دسته'}, content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_django_admin_shares_permissions_normalization_and_audit(self):
        response = self.staff.get('/admin/core/messageexample/')
        self.assertEqual(response.status_code, 200)
        response = self.staff.post('/admin/core/messageexample/add/', {
            **self.values, 'group': self.group.pk, 'text': 'سپاس از کمک ۱۲ بار شما', 'sort_order': '۱۲',
            'active': 'on', 'source_revision': '۰', 'reason': 'افزودن نمونه', '_save': 'ثبت'})
        self.assertEqual(response.status_code, 302, response.content[:100])
        self.assertTrue(MessageExample.objects.filter(group=self.group, text='سپاس از کمک 12 بار شما', sort_order=12).exists())
        self.assertEqual(OperatorAudit.objects.filter(actor=self.manager).count(), 1)


class SuggestionPreviewTests(TestCase):
    post, authenticate = fixture.APITestCase.post, fixture.APITestCase.authenticate

    def setUp(self):
        fixture.APITestCase.setUp(self)
        self.authenticate()

    def test_removed_changed_and_disabled_prompts_cannot_bypass_current_catalog(self):
        item = MessageExample.objects.get(topic='appreciation')
        data = {'category': item.topic, 'text': item.text, 'source_mode': 'suggestion'}
        item.active = False; item.save()
        response = self.post('/messages/preview', data)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['error']['code'], 'freeform_unavailable')
        item.delete()
        self.assertEqual(self.post('/messages/preview', data).status_code, 409)
