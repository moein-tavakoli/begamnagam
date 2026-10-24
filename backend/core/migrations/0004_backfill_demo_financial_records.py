from django.db import migrations


def backfill(apps, schema_editor):
    Order = apps.get_model('core', 'Order')
    Payment = apps.get_model('core', 'PaymentAttempt')
    Event = apps.get_model('core', 'FinancialEvent')
    Delivery = apps.get_model('core', 'MessageDelivery')
    db = schema_editor.connection.alias
    for order in Order.objects.using(db).filter(paid_at__isnull=False, payment_mode='demo').iterator():
        payment, _ = Payment.objects.using(db).get_or_create(order_id=order.pk, applied_to_order=True,
            defaults={'amount_toman':order.amount_toman,'status':'verified','provider_reference':f'demo-payment-{order.pk}'})
        Event.objects.using(db).get_or_create(payment_id=payment.pk,kind='payment',defaults={'amount_toman':order.amount_toman})
        status={'delivered_demo':'delivered_demo','queued':'queued','cancelled':'suppressed','failed':'failed'}.get(order.status,'not_ready')
        Delivery.objects.using(db).get_or_create(order_id=order.pk,defaults={'status':status})


class Migration(migrations.Migration):
    dependencies=[('core','0003_phase_two_quote_snapshot')]
    operations=[migrations.RunPython(backfill,migrations.RunPython.noop)]
