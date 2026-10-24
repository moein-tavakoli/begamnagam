# مراجع فنی

تاریخ بررسی: ۲۴ اکتبر ۲۰۲۶. ابتدا `resolve-library-id` از Context7 MCP فراخوانی شد؛ سرویس خطای `Monthly quota exceeded` برگرداند. ادامهٔ پیاده‌سازی بر اساس مستندات رسمی و آزمون اجرای محلی انجام شد. نسخه‌های دقیق بسته‌ها در `backend/requirements.lock.txt` و `frontend/package-lock.json` مرجع نصب‌اند.

- [Django 5.2 documentation](https://docs.djangoproject.com/en/5.2/) — تنظیمات، احراز هویت، CSRF، تراکنش و پنل مدیریت.
- [Django transactions](https://docs.djangoproject.com/en/5.2/topics/db/transactions/) — atomic و ثبت کار پس از commit.
- [Django CSRF](https://docs.djangoproject.com/en/5.2/howto/csrf/) — cookie و هدر درخواست‌های تغییردهنده.
- [Next.js installation](https://nextjs.org/docs/app/getting-started/installation) — App Router و نیازمندی Node.
- [Next.js rewrites](https://nextjs.org/docs/app/api-reference/config/next-config-js/rewrites) — اتصال API و پنل مدیریت از دامنهٔ فرانت.
- [Next.js deployment](https://nextjs.org/docs/app/getting-started/deploying) — خروجی standalone و اجرای کانتینری.
- [Celery with Django](https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html) — worker و راه‌اندازی پروژه.
- [Celery periodic tasks](https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html) — بازیابی outbox با beat.
- [RabbitMQ release information](https://www.rabbitmq.com/release-information) — انتخاب شاخهٔ پشتیبانی‌شدهٔ 4.4 به‌جای 4.1 منقضی‌شده.
- [Docker Compose services](https://docs.docker.com/reference/compose-file/services/) — healthcheck، وابستگی سلامت و پایان migration.
- [Docker Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets/) — الگوی موردنیاز برای استقرار واقعی؛ فایل فعلی مخصوص local demo است.
- [GitHub setup-python](https://github.com/actions/setup-python) و [setup-node](https://github.com/actions/setup-node) — نسخهٔ runtime و cache نصب؛ actionها به commit مشخص قفل شده‌اند.
- [Ollama generate API](https://docs.ollama.com/api/generate) — انتخاب اختیاری متن با مدل محلی؛ نصب یا دانلود خودکار مدل انجام نمی‌شود.

کتابخانهٔ ناشناس‌سازی کامل، تضمین درستی مدل یا تضمین تحویل پیامک فرض نشده است. مستندات فازبندی، قابلیت‌های فعلی را از نیازمندی‌های عرضهٔ عمومی جدا می‌کنند.

مراجع اصلاح صف در نسخه۰٫۳٫۱: [تنظیمات Celery5.6](https://docs.celeryq.dev/en/v5.6.3/userguide/configuration.html) و [انواع صف RabbitMQ4.4](https://www.rabbitmq.com/docs/queues). نتیجه عملی در [گزارش زیرساخت](phase-two/INFRASTRUCTURE.md) ثبت است.


مراجع تکمیل تنظیم انتشار۰٫۷ (بررسی۲۴اکتبر۲۰۲۶):

- [Docker Compose production](https://docs.docker.com/compose/how-tos/production/): جداسازی تنظیم محیط و نبود bind کد توسعه در انتشار.
- [Caddy reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy): مسیریابی خصوصی و بازنویسی header بالادست.
- [Django proxy scheme trust](https://docs.djangoproject.com/en/5.2/ref/settings/#secure-proxy-ssl-header): اعتماد به header فقط پشت proxy کنترل‌شده و backend غیرعمومی.

- [Caddy log filter](https://caddyserver.com/docs/caddyfile/directives/log#filter): حذف request و response headers از لاگ runtime proxy.
