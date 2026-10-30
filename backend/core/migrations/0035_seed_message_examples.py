from django.db import migrations

# Frozen writing prompts, independent of the reviewed outbound SMS template pool.
EXAMPLES = [{'id': 'appreciation',
  'label': 'تشکر و قدردانی',
  'description': 'دیدن خوبی\u200cها و تشکر از همراهی یک نفر',
  'example': 'از مهربانی و کمکی که به من کردی ممنونم'},
 {'id': 'encouragement',
  'label': 'دلگرمی و تشویق',
  'description': 'یک پیام مثبت برای ارزش\u200cدادن به تلاش دیگران',
  'example': 'تلاشت دیده می\u200cشود؛ با قدم\u200cهای کوچک ادامه بده'},
 {'id': 'congratulations',
  'label': 'تبریک و شادی',
  'description': 'شریک\u200cشدن در خوشحالی و موفقیت یک نفر',
  'example': 'موفقیتت را تبریک می\u200cگویم و برایت روزهای خوبی آرزو می\u200cکنم'},
 {'id': 'body',
  'label': 'بهداشت فردی',
  'description': 'یادآوری محترمانه درباره بهداشت و بوی بدن',
  'example': 'یک یادآوری دوستانه درباره بهداشت روزانه'},
 {'id': 'breath',
  'label': 'بهداشت دهان',
  'description': 'یادآوری آرام درباره تازگی نفس',
  'example': 'توجه بیشتر به بهداشت دهان'},
 {'id': 'noise',
  'label': 'آرامش و صدا',
  'description': 'رعایت آرامش هنگام غذا خوردن یا در جمع',
  'example': 'کمی آرام\u200cتر غذا بخوریم'},
 {'id': 'shared_space',
  'label': 'فضای مشترک',
  'description': 'رعایت نظافت و آسایش دیگران',
  'example': 'با هم فضای مشترک را تمیز نگه داریم'},
 {'id': 'punctuality',
  'label': 'خوش\u200cقولی',
  'description': 'احترام به زمان و قرارهای مشترک',
  'example': 'لطفاً برای قرارها به\u200cموقع برسیم و تأخیر را خبر بدهیم'},
 {'id': 'listening',
  'label': 'خوب گوش\u200cدادن',
  'description': 'فرصت دادن به دیگران برای کامل\u200cکردن حرفشان',
  'example': 'دوست دارم به حرف هم کامل گوش بدهیم و وسط صحبت نپریم'},
 {'id': 'conversation',
  'label': 'ادب در گفت\u200cوگو',
  'description': 'گفتن اختلاف\u200cنظر با آرامش و احترام',
  'example': 'حتی وقتی اختلاف\u200cنظر داریم، آرام و محترمانه صحبت کنیم'},
 {'id': 'personal_space',
  'label': 'حریم شخصی',
  'description': 'احترام به فضای شخصی و وسایل دیگران',
  'example': 'لطفاً پیش از استفاده از وسایل دیگران اجازه بگیریم'},
 {'id': 'phone_etiquette',
  'label': 'استفاده از تلفن',
  'description': 'توجه به جمع هنگام استفاده از تلفن همراه',
  'example': 'در جمع صدای تلفن را کم کنیم و برای گفت\u200cوگو به هم توجه کنیم'},
 {'id': 'neighbor',
  'label': 'حقوق همسایه',
  'description': 'رعایت آرامش و مسیرهای مشترک ساختمان',
  'example': 'برای آرامش همسایه\u200cها، ساعت استراحت و مسیر رفت\u200cوآمد را رعایت کنیم'},
 {'id': 'parking',
  'label': 'پارک خودرو',
  'description': 'بازگذاشتن مسیر پیاده\u200cرو و ورودی\u200cها',
  'example': 'لطفاً خودرو را طوری پارک کنیم که مسیر رفت\u200cوآمد بسته نشود'},
 {'id': 'teamwork',
  'label': 'همکاری گروهی',
  'description': 'تقسیم مسئولیت و همراهی در کار مشترک',
  'example': 'برای انجام بهتر کار گروهی، سهم خودمان را به\u200cموقع انجام بدهیم'},
 {'id': 'apology',
  'label': 'عذرخواهی',
  'description': 'پذیرفتن اشتباه و ابراز تأسف محترمانه',
  'example': 'می\u200cخواهم بابت رفتارم عذرخواهی کنم و برای بهترشدنش تلاش کنم'},
 {'id': 'good_wishes',
  'label': 'آرزوی روز خوب',
  'description': 'فرستادن یک آرزوی ساده و مهربانانه',
  'example': 'برایت روزی آرام و پر از اتفاق\u200cهای خوب آرزو می\u200cکنم'},
 {'id': 'environment',
  'label': 'مراقبت از محیط',
  'description': 'کم\u200cکردن زباله و مراقبت از فضای اطراف',
  'example': 'زباله را در جای مناسب بگذاریم و در مصرف آب و برق دقت کنیم'}]
GROUPS = [('حال خوب', ['appreciation', 'encouragement', 'congratulations', 'apology', 'good_wishes']), ('گفت\u200cوگو و رابطه', ['punctuality', 'listening', 'conversation', 'personal_space', 'phone_etiquette']), ('خانه و همسایه', ['noise', 'shared_space', 'neighbor', 'parking']), ('بهداشت فردی', ['body', 'breath']), ('کار و محیط', ['teamwork', 'environment'])]


def seed(apps, schema_editor):
    Group = apps.get_model('core', 'ExampleCategory')
    Example = apps.get_model('core', 'MessageExample')
    db = schema_editor.connection.alias
    for index, (name, topics) in enumerate(GROUPS):
        group, _ = Group.objects.using(db).get_or_create(name=name, defaults={'active': True, 'sort_order': index * 10})
        for position, topic in enumerate(topics):
            if Example.objects.using(db).filter(group=group, topic=topic).exists():
                continue
            item = next(example for example in EXAMPLES if example['id'] == topic)
            Example.objects.using(db).create(group=group, topic=topic, label=item['label'],
                description=item['description'], text=item['example'], active=True, sort_order=position * 10)


class Migration(migrations.Migration):
    dependencies = [('core', '0034_message_examples')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
