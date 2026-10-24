# مدل مفهومی داده و قرارداد API

شناسه: BN-CONTRACT-001 | نسخه: ۱٫۰ | وضعیت: طرح پیشنهادی؛ بدون schema، migration یا پیاده‌سازی

## ۱. موجودیت‌ها و قواعد داده

| موجودیت | داده ضروری و رابطه | قاعده |
| --- | --- | --- |
| Account / VerifiedPhone | حساب و شماره خود؛ ciphertext، HMAC و نسخه کلید | شماره یکتا؛ فقط تأیید OTP حساب محصول می‌سازد |
| OTPChallenge | digest کد، شماره مقصد رمز، نشست، انقضا، تلاش و مصرف | کد plaintext ذخیره/ثبت نشود؛ مصرف یک‌باره |
| TemplateVersion / PolicyVersion | موضوع، متن مصوب، نسخه فیلتر، لحن و تاریخ اعتبار | سفارش متن را snapshot می‌کند؛ حذف/ویرایش قالب سفارش را عوض نکند |
| PreviewQuote | صاحب، موضوع، متن نهایی، گیرنده رمز/HMAC، قیمت و واحد، نسخه‌ها، تعداد بخش و expires | یک سفارش برای هر quote؛ ۱۵ دقیقه؛ پیش‌نویس خام جزو ذخیره نیست |
| RecipientActionGrant | هش توکن تصادفی، گیرنده/quote، دامنه اقدام، انقضا و زمان فعال‌شدن | token بدون شماره؛ فقط stop/report؛ نه خواندن سابقه یا پول |
| Order | صاحب، quote یکتا، idempotency و payload digest، مبلغ صحیح تومان، محیط | عدم امکان تغییر گیرنده/متن پس از تأیید؛ demo و live جدا |
| PaymentAttempt | سفارش، request key، provider/environment، authority/ref یکتا، مبلغ و واحد ارسال‌شده، وضعیت | فقط یک پرداخت به سفارش تخصیص یابد؛ هر پرداخت اضافی معتبر ثبت و برای استرداد پیگیری شود؛ مرجع بیرونی دوباره مصرف نشود |
| FinancialEvent / Refund | سابقه غیرقابل بازنویسی دریافت/استرداد، مرجع و مبلغ، وضعیت تطبیق | مجموع بازپرداخت از پرداخت معتبر بیشتر نشود؛ حذف حساب سند مالی را پاک نکند |
| MessageDelivery / SendAttempt | سفارش، شناسه منطقی ثابت، تلاش، مرجع provider، status و timestamps | یک پیام منطقی/سفارش؛ timeout موجب ساخت پیام تازه نشود |
| OutboxEvent | نوع/شناسه، مرجع، آماده‌بودن، تلاش و lease | ثبت در تراکنش کسب‌وکار؛ مصرف تکراری بی‌اثر |
| RecipientPreference / Reservation | HMAC گیرنده، blocked، نسخه، رزرو و آخرین پذیرش | مرجع PostgreSQL؛ توقف سراسری؛ بازفعال‌سازی فقط OTP |
| PairLimit | HMAC مستقل جفت و آخرین پذیرش/رزرو | ۳۰ روز؛ HMAC جفت قابلیت تطبیق محدود دارد و بی‌نام مطلق نیست |
| AbuseReport / AdminAudit | پیام مرتبط، دلیل ساختاری، اقدام/نقش/زمان/شناسه پرونده | بدون تماس دو طرف؛ مشاهده شماره استثنایی با دلیل و ممیزی |

ایندکس‌ها و قیود مفهومی لازم: owner+idempotency، quote یک‌به‌یک order، provider+environment+authority/ref، یک delivery برای order، event kind+business id، HMAC شماره و جفت و تاریخ سهمیه. طراحی SQL، انتخاب نوع دقیق و migration به فاز مجاز یک تعلق دارد.

شماره با قالب canonical واحد، تبدیل ارقام فارسی/عربی و کنترل 09/+98 یکسان‌سازی می‌شود. کلید رمزنگاری با کلید HMAC و کلید جفت مستقل و دارای نسخه است؛ کلیدها خارج مخزن نگهداری می‌شوند. چرخش HMAC باید با پنجره تطبیق دو نسخه و حفظ suppression انجام شود؛ حذف ساده کلید نمی‌تواند باعث بازشدن دریافت شود.

## ۲. ماشین وضعیت‌های مستقل

```text
PaymentAttempt:
created → pending → verified | failed | unknown
unknown → verified | failed    (فقط با مدرک)
Refund:
requested → processing → refunded | failed | unknown

Delivery:
not_ready → queued → submitting → accepted → delivered | undeliverable
                        ↘ unknown → accepted | definitive_failure
queued → suppressed | expired | definitive_failure
Demo:
queued_demo → delivered_demo | failed_demo
```

state کلی سفارش از این محورهای مستقل مشتق می‌شود. `accepted` به معنی پذیرش provider است؛ `delivered` فقط رسید تحویل معتبر، نه خوانده‌شدن. وضعیت ناشناخته با موفق/ناموفق حدس‌زده جایگزین نمی‌شود. callback قدیمی یا تکراری state جدیدتر را بدون قاعده اصلاح/تطبیق عقب نمی‌برد؛ رسید دیررس با timestamp و رویداد ممیزی ثبت می‌شود.

## ۳. قرارداد HTTP پیشنهادی

همه مسیرها زیر `/api/v1`؛ مبدأ عمومی واحد، JSON، نشست cookie امن و CSRF برای عملیات تغییردهنده. پاسخ خصوصی `no-store`؛ server/client/SW هر سه این مرز را رعایت کنند. نام‌ها در این سند قرارداد هدف‌اند و تماماً در نمونه موجود نیستند.

| متد/مسیر | ورودی اصلی | خروجی و کنترل |
| --- | --- | --- |
| GET /bootstrap | بدون داده خصوصی در URL | موضوع‌ها/قواعد/محیط demo، تنظیمات عمومی و CSRF؛ قیمت cacheشده قابل خرید نیست |
| POST /auth/request-otp | phone | 202 چالش/زمان retry؛ پاسخ عمومی بدون کشف وجود حساب |
| POST /auth/verify-otp | challenge_id، code | نشست چرخیده؛ خطای کد/انقضا عمومی؛ تلاش محدود |
| POST /auth/logout | CSRF | 204؛ پاک‌کردن state خصوصی مرورگر |
| POST /messages/preview | category، input اختیاری، recipient؛ نیازمند حساب | 201 quote_id، full_sms، masked_recipient، amount_toman، segments، processing_mode، versions، expires_at |
| POST /orders | quote_id + Idempotency-Key | 201 اولین و 200 تکرار همان payload؛ یک سفارش؛ payload متفاوت با همان کلید 409 |
| POST /orders/{id}/payments | شناسه سفارش، کلید تلاش پرداخت | مرجع تلاش/redirect فقط به دامنه درگاه مصوب؛ amount از سرور |
| GET /orders/{id} | فقط صاحب | وضعیت عملیاتی/مالی عمومی، قیمت و متن خود، timestamps؛ بدون علت خصوصی گیرنده |
| GET /messages?cursor=… | فقط صاحب | pagination، شماره پوشیده، متن snapshot و وضعیت؛ بدون جست‌وجوی شماره دلخواه |
| GET /payments/return/{provider} | authority/status اعلامی | هیچ نتیجه مالی صرفاً از query پذیرفته نشود؛ به تلاش موجود نگاشت و verify مستقل زمان‌بندی شود |
| POST /webhooks/{provider} | payload حداقلی | احراز اصالت طبق قرارداد؛ محدودیت replay/سایز؛ در نبود امضای معتبر، فقط محرک استعلام مستقل |
| GET /recipient/action/{token} | token محدود | صفحه عمومی و بدون داده طرفین؛ GET بی‌اثر، no-store، no-referrer و بدون analytics |
| POST /recipient/action/{token}/stop | تأیید صریح + CSRF/کنترل origin مناسب | توقف همان گیرنده؛ idempotent؛ بدون حساب؛ موفقیت فقط پس از commit |
| POST /recipient/action/{token}/reports | reason ساختاری، توضیح اختیاری حداکثر ۵۰۰ | 202 کد پیگیری؛ محدودیت نرخ؛ متن گزارش در log نیست |
| GET/PATCH /preferences | حساب OTP تأییدشده | فقط شماره خود؛ تغییر با CSRF؛ فعال‌سازی مجدد نیازمند OTP تازه حداکثر ۵ دقیقه |
| POST /orders/{id}/pay-demo | فقط محیط demo | جدا و آشکار؛ در live موجود/فعال نباشد |

درگاه ممکن است GET به callback بفرستد؛ آن مسیر CSRF مرورگر لازم ندارد اما نتیجه ارسالی را معتبر فرض نمی‌کند، به نشست جاری وابسته نیست و بدون verify وجه/ارسال ثبت نمی‌کند. عملیات عمومی گیرنده محافظت origin و token دارد؛ GET اسکنرهای لینک نباید تغییر ایجاد کند.

قالب خطا: `code` ماشینی عمومی، `message` فارسی، `request_id` تصادفی و در صورت محدودیت `retry_after`. کدهای اصلی: 400 ورودی، 401 نشست، 403 CSRF/مجوز، 404 سفارش ناموجود یا متعلق به دیگری، 409 کلید متعارض/quote مصرف‌شده، 410 انقضای quote، 422 محتوای نامجاز یا recipient_unavailable عمومی، 429 سقف درخواست، 503 وابستگی موقت. خطای private block/account/recipient quota در پاسخ قابل تفکیک نیست؛ timing و مسیر پیش/پس پرداخت هم بررسی می‌شود. پاسخ شامل stacktrace، phone کامل یا raw provider payload نیست.

## ۴. تکرار، قطع شبکه و تراکنش

- retry ساخت سفارش با همان کلید و quote همان سفارش را برمی‌گرداند، حتی اگر quote اکنون مصرف‌شده باشد؛ بررسی کلید مقدم است. payload متفاوت رد می‌شود.
- reservation و سفارش داخل تراکنش، با ترتیب قفل ثابت sender/recipient/pair و قید یکتا ساخته می‌شوند. race دو فرستنده به یک گیرنده باید فقط یک رزرو بسازد.
- PaymentAttempt جدید وقتی تلاش قبلی pending/unknown است ساخته نمی‌شود؛ ابتدا استعلام همان تلاش. اگر برخلاف انتظار چند دریافت معتبر رخ دهد، همه ثبت و فقط یکی به سفارش تخصیص داده می‌شود؛ اضافه‌دریافت به استرداد می‌رود. موفقیت دیررس پس از بسته‌شدن quote/order به refund می‌رود و SMS تازه نمی‌سازد.
- commit پرداخت معتبر، رویداد مالی و outbox ارسال را یکجا ثبت می‌کند. خرابی broker با reconciler جبران می‌شود؛ رویداد پرداخت دوباره outbox تازه نمی‌سازد.
- تماس بیرونی شناسه منطقی ثابت دارد. worker مرده بعد از submission به بررسی unknown می‌رود؛ تکرار خودکار بدون احراز عدم پذیرش ممنوع است.
- توقف دریافت پیش از submission، ارسال را suppress و refund را ثبت می‌کند. توقف پس از پذیرش، ارسال‌های بعدی را می‌بندد؛ تضمین پس‌گرفتن SMS در شبکه وجود ندارد.

## ۵. توکن و privacy

پیشنهاد: توکن ۳۲ بایت تصادفی، ذخیره فقط digest، دامنه stop/report، بدون امکان کشف فرستنده/شماره. quote نسخه کامل متن و URL نهایی را پیش از خرید نگه می‌دارد؛ grant تا پذیرش ارسال غیرفعال و برای quote مصرف‌نشده حذف می‌شود. گزارش ۳۰ روز و توقف ۳۶۵ روز پس از ارسال اعتبار دارد؛ مسیر OTP برای توقف بدون لینک همیشه باقی می‌ماند. کنترل فعال‌شدن و انقضای دو قابلیت جداست.

مسیر حاوی token از access log، ابزار تحلیل، cache، referrer و خطا حذف/پوشیده می‌شود. لینک بیرونی از صفحه گیرنده نباید token را منتقل کند. توکن دوبار stop می‌تواند همان نتیجه عمومی را بدهد؛ گزارش‌های تکراری یک پرونده واحد را تقویت می‌کنند و داده تازه به مشاهده‌کننده نمی‌دهند. تست حدس و دستکاری، انقضا، نشت و browser link scanner در فاز چهار لازم است.
