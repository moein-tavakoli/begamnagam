from django.db import migrations


def seed(apps, schema_editor):
    Package=apps.get_model('core','MessagePackage')
    for index,(name,count,price) in enumerate([('شروع',3,10000),('همراه',9,30000),('دوستانه',30,100000),('ویژه',90,300000)]):
        if not Package.objects.filter(message_count=count,price_toman=price).exists():
            Package.objects.create(name=name,message_count=count,price_toman=price,active=True,sort_order=index*10)


class Migration(migrations.Migration):
    dependencies=[('core','0031_manual_card_payments')]
    operations=[migrations.RunPython(seed,migrations.RunPython.noop)]
