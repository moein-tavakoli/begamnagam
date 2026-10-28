# طرح اولیهٔ بهینه‌سازی ظرفیت و مانع تاریخی Storage

**به‌روزرسانی:** پس از رفع مشکل دیسک توسط کارفرما، تنظیمات روی CT/Nginx فعال و آزمون۳۰دقیقه‌ای کامل شد. [گزارش نهایی](optimized.fa.md) و [پیکربندی فعال](../release-v0.11.2-capacity/README.fa.md) مرجع جاری‌اند؛ شرح مانع و طرح سه‌فرانت زیر تاریخی است.

**وضعیت۲۸اکتبر۲۰۲۶: روی سرور اعمال نشده و تست بار تازه اجرا نشده است.** مجوز کارفرما برای بهینه‌سازی، اعمال و تکرار تست وجود دارد؛ مانع فعلی دسترسی/سلامت Storage میزبان Proxmox است. اعداد این سند تنظیم پیشنهادی‌اند و ظرفیت اثبات‌شده نیستند.

## مشاهدهٔ پیش از تغییر

در بررسی نهایی ساعت۰۸:۲۵تهران، فایل‌سیستم ریشهٔ CT115، دستگاه `/dev/mapper/pve-vm--115--disk--0`، وضعیت `ext4 rw,relatime,stripe=32,emergency_ro` داشت. ظاهرشدن `rw` به معنی امکان نوشتن نیست؛ ساخت یک فایل موقت با `EROFS` رد شد. Healthcheckهای Docker به خطای `OCI runtime exec failed: open /tmp/runc-process…: read-only file system` می‌رسند.

از مسیر HTTPS واقعی دامنه با گواهی معتبر و اتصال به Nginx مرکزی، صفحهٔ اصلی۲۰۰، `/healthz` و `/api/v1/bootstrap` هر دو۵۰۳بودند. شش سرویس دارای healthcheck، unhealthy بودند؛ worker و beat healthcheck مستقل ندارند. restart قبلی worker برابر۱و سایر سرویس‌ها۰بود؛ OOM مشاهده نشد. بکاپ زمان‌بندی‌شده نیز شکست خورده است. این وضعیت پیش از هر تغییر یا بار جدید مشاهده شد و نباید به تست جدید نسبت داده شود.

حدود۱۳GiB فضای آزاد داخل CT گزارش می‌شود؛ پرشدن معمول این فایل‌سیستم اثبات نشده است. ظرفیت thin pool/metadata، خطاهای I/O، سلامت دیسک و لاگ kernel میزبان باید در Proxmox بررسی شوند. علت اصلی از داخل CT قابل تعیین نبود. `fsck` روی فایل‌سیستم mountشده یا remount اجباری اجرا نشده است؛ هیچ DB یا volume بازیابی/حذف نشده است. شواهد بدون اسرار در [server-preflight.json](server-preflight.json) ثبت شده‌اند.

## تغییر آماده‌شده

[compose.performance.yaml](../../compose.performance.yaml) یک overlay اختیاری پس از `compose.internal.yaml` و `compose.hardened.yaml` است. پیش‌فرض فعلی را فعال نمی‌کند.

| بخش | قبلی | پیشنهادی |
| --- | --- | --- |
| Traefik |۶۴MiB|۵۱۲MiB؛ `GOMEMLIMIT=384MiB` نرم، با حاشیه برای حافظهٔ خارج runtime |
| frontend |یک Node،۲۵۶MiB،heap۱۶۰MiB|سه کانتینر از **همان image**، هرکدام۷۶۸MiB،heap۳۸۴MiB |
| backend |یک Gunicorn worker،دو thread،۱۹۲MiB|سه worker،هرکدام دو thread،۷۶۸MiB |
| worker |۱۲۸MiB،solo۱|۲۵۶MiB؛ همان concurrency و کنترل‌های ارسال |
| beat |۹۶MiB|۱۹۲MiB |

سقف مجموع۱۰سرویس۴٬۴۴۸MiB است. PostgreSQL/Redis/RabbitMQ در این مرحله نیاز به تغییر تنظیم ندارند؛ شش thread وب به‌اضافهٔ worker/beat برای سقف۲۰اتصال PostgreSQL حاشیه می‌گذارند. مصرف واقعی باید پس از فعال‌سازی پایش شود. heap یا `GOMEMLIMIT` با سقف کل حافظه یکسان نیست.

فرانت‌ها فقط روی loopback پورت‌های۳۰۰۰/۳۰۰۱/۳۰۰۲هستند. Traefik در حالت `FRONTEND_REPLICAS=3` بار را میان سه سرور تقسیم و سلامت آن‌ها را کنترل می‌کند؛ حالت تک‌نمونهٔ قبلی حفظ شده است. nonce/CSP، عدم کش پاسخ شخصی، هویت کلاینت، CSRF، ACL، env جدا، provider واقعی و نسخهٔ برنامه تغییر نمی‌کنند. همهٔ فرانت‌ها باید image/build یکسان داشته باشند تا static assets و کلیدهای build سازگار باشند. بازگشت به یک فرانت با برداشتن overlay و متغیر replica، بدون تغییر DB، انجام می‌شود؛ حذف کانتینر اضافی باید پس از خارج‌کردن آن از routing باشد.

## کنترل‌های محلی انجام‌شده

- Compose سه‌لایه با env مصنوعی validate شد؛۱۰سرویس، image یکسان فرانت، loopback، read-only، cap-drop و env مستقل runtime/migration تأیید شدند؛ ACL Redis حفظ شده است.
- فایل routing با **Traefik3.7.13 واقعی** در دو کانتینر موقتِ شبکه‌بسته و بدون پورت منتشرشده اجرا شد؛ API داخلی آزمایش، تعریف یک و سه upstream را تأیید کرد. گواهی مصنوعی فقط برای این آزمایش محلی بود؛ هیچ healthcheck سرور واقعی دور زده نشد.
- ابزار تست compile شد؛ plan بار مرحله‌ای و اجرای۱۸۰۰ثانیه‌ای، ورودی‌های نامعتبر و `git diff --check` بررسی شدند. کانتینرهای موقت پاک شدند. تست کامل برنامه اجرا نشد، چون کد برنامه در این تغییر دست نخورده است.

## ادامهٔ اجرا پس از تعمیر Storage

ابتدا تعمیر آفلاین/بررسی Storage با اپراتور Proxmox، تأیید نوشتن و fsync، سلامت DB/Redis/RabbitMQ، backup تازه و restore-check لازم است. نسخهٔ فعال آخرین مشاهده۰٫۱۱٫۰است؛ قبل از rollout باید دوباره خوانده شود، چون کاندیدا و تغییرات دیگر در مخزن وجود دارند. فقط این overlay، routing و ابزار تست باید روی همان release بررسی‌شده اعمال شوند؛ تغییرات نامرتبط محیط کار وارد انتشار نشوند. مجوز اجرای این کار موجود است؛ مجوز تازه صرفاً برای همان مراحل لازم نیست.

با env خصوصی فعلی، ابتدا config سه‌لایه اعتبارسنجی و نسخهٔ قبلی ذخیره شود. فرانت‌های اضافی با `--no-deps` بالا بیایند و health هر سه روی loopback تأیید شود؛ سپس فرانت اصلی/بک‌اند و پراکسی با همان imageهای فعال recreate شوند. برای worker/beat، افزایش سقف حافظه می‌تواند بدون restart از طریق `docker update` اعمال شود؛ overlay باید برای اجرای بعدی حفظ شود. DB/Redis/RabbitMQ recreate نشوند. TLS، CSP nonce، مجوزها و smoke قبل از بار دوباره بررسی شوند.

[scripts/live-read-load.py](../../scripts/live-read-load.py) اکنون۸یا۱۰سرویس اصلی را می‌پاید و `--rates`، `--stage-seconds` و بودجهٔ اتصال تا۲۵۶دارد. در `emergency_ro` یا root فقط‌خواندنی از شروع بار خودداری می‌کند. همهٔ مسیرها همچنان GET مشخص‌اند؛ provider، OTP، سفارش، پرداخت و AI فراخوانی نمی‌شوند. نشست بی‌نام خود ابزار پس از کنترل عدم احراز هویت پاک می‌شود.

نمونهٔ برنامهٔ مرحله‌ای روی سرور، **فقط پس از بازیابی سلامت**:

```sh
python3 /opt/begamnagam/benchmarks/live-read-load.py \
  --ack-live-get-only --transport public-edge --max-inflight 128 \
  --rates 60,150,225,325,450,600 --stage-seconds 60 --skip-api \
  --output /opt/begamnagam/benchmarks/NEW_UNIQUE_STEP_RUN
```

بالاترین مرحلهٔ کامل با خطا/افت صفر، p95≤۵۰۰ms و p95 عقب‌افتادگی مولد≤۱۰ms، نامزد آزمون طولانی است؛ گام‌های کوچک‌تر حوالی مرز فشار برای تعیین بازه تکرار شوند. سپس یک نرخ پایین‌تر از مرز، حداقل۳۰دقیقه اجرا و smoke/recovery و counters داده/هزینه دوباره بررسی شوند. برای soak از یک نرخ در `--rates` و `--stage-seconds 1800` استفاده شود. عدد۳۰۰در plan آزمایش محلی صرفاً نمونه است و ظرفیت تأییدشده نیست.

حدود توقف قبلیِ خطا، p95>۲ثانیه، حافظه>۹۰٪، restart/OOM، سلامت و افت>۵٪ حفظ‌اند. مصرف CPU/RAM مولد هم‌میزبان باید در کنار سرویس‌ها گزارش شود؛ اگر مولد عقب بماند، نتیجه سقف سایت نیست. HTTP واقعی از LAN edge سنجیده می‌شود؛ محدودیت WAN و هزینه/تأخیر providerها جدا هستند. ظرفیت معتبر فقط برای همین ترکیب خواندن و مدت ثبت‌شده اعلام شود، نه تعداد کاربران یا ظرفیت SMS/AI.

مراجع تنظیم: [Docker production overlay](https://docs.docker.com/compose/how-tos/production/)، [Traefik services/healthcheck](https://doc.traefik.io/traefik/reference/routing-configuration/http/load-balancing/service/)، [Go memory limit](https://tip.golang.org/doc/gc-guide)، [Next.js self-hosting](https://nextjs.org/docs/app/guides/self-hosting) و [رفتار خطاهای ext4](https://www.kernel.org/doc/html/latest/admin-guide/ext4.html). Context7 این جلسه در دسترس نبود؛ مستندات اصلی و runtime نصب‌شده مبنا بودند.
