import io
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.db import transaction
from django.test import Client, TestCase
from django.utils import timezone
from . import test_live_sms as live
from .models import Account, MessageDelivery, OperatorAudit, Order, Outbox, RecipientState
from .provider_delivery import apply_result, reconcile_delivery, submit_delivery
from .providers.kavenegar import SMSResult
from .queue_archive import archive_unknown_outbox
from .safety import refresh_alerts, snapshot
from .services import APIError


class QueueArchiveTests(TestCase):
    setUp = live.LiveGiftSMSTests.setUp
    post, authenticate, preview = live.LiveGiftSMSTests.post, live.LiveGiftSMSTests.authenticate, live.LiveGiftSMSTests.preview
    make_order, confirm = live.LiveGiftSMSTests.make_order, live.LiveGiftSMSTests.confirm

    def unknown(self, days=11):
        result=self.make_order();self.assertEqual(result.status_code,200,result.content)
        self.confirm(result.json());order=Order.objects.get(pk=result.json()['id'])
        age=timezone.now()-timedelta(days=days)
        Order.objects.filter(pk=order.pk).update(status='unknown')
        Outbox.objects.filter(order=order).update(state='unknown',created_at=age)
        MessageDelivery.objects.filter(order=order).update(status='unknown',created_at=age,provider_reference='700')
        return Order.objects.get(pk=order.pk),Outbox.objects.get(order=order),MessageDelivery.objects.get(order=order)

    def test_archive_is_audited_idempotent_and_preserves_history_and_balances(self):
        order,event,delivery=self.unknown()
        balance=Account.objects.get(user=self.user).free_sends_remaining
        before=(order.full_sms,order.recipient_cipher,delivery.provider_reference,delivery.local_id)
        self.assertGreater(snapshot()['oldest_queue_seconds'],48*3600)
        for _ in range(2):archive_unknown_outbox(event.pk,'بایگانی سوابق قدیمی با نتیجه نامعلوم')
        data=refresh_alerts();self.assertEqual(data['oldest_queue_seconds'],0)
        self.assertEqual(data['outbox_pending'],0);self.assertEqual(data['delivery_unknown'],1)
        order.refresh_from_db();delivery.refresh_from_db()
        self.assertEqual((order.status,delivery.status),('unknown','unknown'))
        self.assertEqual(before,(order.full_sms,order.recipient_cipher,delivery.provider_reference,delivery.local_id))
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining,balance)
        self.assertEqual(OperatorAudit.objects.filter(action='archive_unknown_outbox').count(),1)
        self.assertEqual((Order.objects.count(),Outbox.objects.count(),MessageDelivery.objects.count()),(1,1,1))

    def test_archived_item_is_not_sent_or_polled_again(self):
        order,event,delivery=self.unknown();archive_unknown_outbox(event.pk,'خروج صریح از صف فعال')
        with patch('core.provider_delivery.Kavenegar.submit') as send, patch('core.provider_delivery.Kavenegar.status') as status:
            submit_delivery(event.pk);reconcile_delivery(delivery.pk)
            send.assert_not_called();status.assert_not_called()
        with patch('core.provider_delivery.reconcile_delivery') as lookup, patch('core.provider_services.reconcile_payments'):
            from .tasks import reconcile_providers
            reconcile_providers();lookup.assert_not_called()
        event.refresh_from_db();self.assertEqual(event.state,'archived')

    def test_late_unknown_status_response_cannot_reactivate_archive(self):
        order,event,delivery=self.unknown();archive_unknown_outbox(event.pk,'خروج صریح از صف فعال')
        with transaction.atomic():
            order=Order.objects.select_for_update().get(pk=order.pk)
            event=Outbox.objects.select_for_update().get(pk=event.pk)
            delivery=MessageDelivery.objects.select_for_update().get(pk=delivery.pk)
            state=RecipientState.objects.get(phone_hash=order.recipient_hash)
            apply_result(order,state,event,delivery,SMSResult('unknown','700'))
        event.refresh_from_db();self.assertEqual(event.state,'archived')
        self.assertEqual(snapshot()['oldest_queue_seconds'],0)

    def test_recent_or_nonunknown_items_and_missing_reason_are_rejected(self):
        order,event,delivery=self.unknown(days=1)
        with self.assertRaises(APIError):archive_unknown_outbox(event.pk,'نباید بایگانی شود')
        with self.assertRaises(APIError):archive_unknown_outbox(event.pk,'')
        Outbox.objects.filter(pk=event.pk).update(created_at=timezone.now()-timedelta(days=11))
        MessageDelivery.objects.filter(pk=delivery.pk).update(created_at=timezone.now()-timedelta(days=11))
        Order.objects.filter(pk=order.pk).update(status='accepted')
        with self.assertRaises(APIError):archive_unknown_outbox(event.pk,'نباید بایگانی شود')
        self.assertFalse(OperatorAudit.objects.filter(action='archive_unknown_outbox').exists())

    def test_command_defaults_to_readonly_and_apply_preserves_unknown(self):
        order,event,delivery=self.unknown()
        call_command('archive_unknown_outbox',id=event.pk,reason='پاک‌سازی صف فعال',stdout=io.StringIO())
        event.refresh_from_db();self.assertEqual(event.state,'unknown')
        call_command('archive_unknown_outbox',id=event.pk,reason='پاک‌سازی صف فعال',apply=True,stdout=io.StringIO())
        event.refresh_from_db();self.assertEqual(event.state,'archived')
        order.refresh_from_db();self.assertEqual(order.status,'unknown')

    def test_management_lists_and_archives_old_unknown_send_with_operator_permissions(self):
        order, event, delivery = self.unknown()
        actor = get_user_model().objects.create_user('queue-operator', is_staff=True)
        actor.user_permissions.add(Permission.objects.get(content_type__app_label='core', codename='view_outbox'))
        staff = Client(enforce_csrf_checks=True)
        staff.force_login(actor)
        staff.get('/api/v1/manage/session')
        headers = {'content_type': 'application/json', 'HTTP_X_CSRFTOKEN': staff.cookies['csrftoken'].value}
        action = '/api/v1/manage/actions'
        records = '/api/v1/manage/records/outbox'
        payload = {'action': 'archive_unknown_outbox', 'object_id': str(event.pk)}
        self.assertEqual(staff.post(action, payload, **headers).status_code, 403)

        actor.user_permissions.add(Permission.objects.get(content_type__app_label='core', codename='operate_safety'))
        self.assertEqual(staff.post(action, payload, content_type='application/json').status_code, 403)
        rows = staff.post(records, {'status': 'unknown'}, **headers).json()['rows']
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['can_archive'])
        self.assertIn('created_at', rows[0])

        for _ in range(2):
            result = staff.post(action, payload, **headers)
            self.assertEqual(result.status_code, 200, result.content)
        audit = OperatorAudit.objects.get(action='archive_unknown_outbox', object_id=str(event.pk))
        self.assertEqual(audit.actor, actor)
        self.assertEqual(staff.post(records, {'status': 'unknown'}, **headers).json()['rows'], [])
        archive = staff.post(records, {'status': 'archived'}, **headers).json()
        self.assertIn(['archived', 'archived'], archive['statuses'])
        self.assertEqual(archive['rows'][0]['state'], 'archived')
        self.assertFalse(archive['rows'][0]['can_archive'])
        self.assertEqual(snapshot()['oldest_queue_seconds'], 0)
        order.refresh_from_db()
        delivery.refresh_from_db()
        self.assertEqual((order.status, delivery.status), ('unknown', 'unknown'))
