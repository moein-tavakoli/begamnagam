# ماتریس نیازمندی، آزمون و پذیرش

شناسه: BN-TRACE-001 | نسخه: ۱٫۰ | وضعیت اجرای همه آزمون‌های این برنامه: **NOT TESTED**

این سند ۵۶ شناسه مبنای ۰٫۲ را حفظ می‌کند. ستون معیار، سناریوی آزمون آینده است؛ تهیه این ماتریس به معنی نوشتن/اجرای تست یا پذیرش قابلیت نیست. آزمون‌های قدیمی فقط در گزارش audit ارجاع شده‌اند.

هر ردیف `T-<شناسه نیازمندی>` شناسه آزمون/گروه پذیرش همان ردیف است. برای پوشش کافی می‌تواند چند case داشته باشد؛ هیچ case اجباری اجرا نشده/ناموفق با میانگین امتیاز جبران نمی‌شود. مسئول تهیه شواهد مجری در فاز مجاز، مسئول پذیرش کارفرماست. معیار G0 مربوط به تصویب سند است، نه اثبات رفتار برنامه.

## نیازمندی‌های کارکردی

| شناسه / آزمون | الزام | معیار پذیرش | gate | مرجع داخل بسته |
| --- | --- | --- | --- | --- |
| FR-01 / T-FR-01 | مسیر فارسی Mobile-first | W-01 تا W-06 روی عرض ۳۲۰ تا دسکتاپ؛ لمس/keyboard/RTL مطابق MFها | G2 | UX-WIREFRAMES |
| FR-02 / T-FR-02 | OTP شماره خود فرستنده | انقضا، پنج تلاش، مصرف یک‌باره، resend، سقف و نشست مدیر؛ demo و واقعی جدا | G2/G3 | PRD / DATA-API |
| FR-03 / T-FR-03 | سه موضوع مثبت | تشکر پیش‌فرض؛ تشویق و تبریک هرکدام تا رسید، با همان فیلتر/سقف | G2 | PRD |
| FR-04 / T-FR-04 | چهار موضوع رفتاری محدود | بدن، دهان، صدای خوردن، فضای مشترک؛ ورودی خارج موضوع/توهین رد شود | G2 | PRD |
| FR-05 / T-FR-05 | کنترل ورودی و خروجی | مجموعه ۱۲۰ مورد مصنوعی؛ خروجی قابل ارسال فقط قالب مصوب؛ timeout/JSON/تزریق رد | G2/G3 | ADR-03 |
| FR-06 / T-FR-06 | متن و قیمت ثابت | تغییر مبلغ/متن client یا تنظیم server سفارش تأییدشده را عوض نکند؛ quote ۱۵ دقیقه | G2 | DATA-API |
| FR-07 / T-FR-07 | یک گیرنده | ارقام فارسی/عربی/+98 یکسان؛ چند شماره، ثابت، خود فرستنده رد؛ خطای خصوصی عمومی | G2 | PRD |
| FR-08 / T-FR-08 | تأیید مالی سمت سرور | callback جعلی/تکراری، واحد اشتباه، مبلغ متفاوت و بازگشت روی نشست دیگر؛ بدون verify ارسال نشود | G2/G3 | DATA-API |
| FR-09 / T-FR-09 | عدم تکرار | درخواست هم‌زمان یک کلید/quote فقط یک order و رویداد بسازد؛ payload متفاوت 409؛ PG واقعی | G2/G3 | DATA-API |
| FR-10 / T-FR-10 | outbox و صف | قطع broker بعد commit، publish تکراری، مرگ worker و recovery؛ بدون گم‌شدن/ارسال دوم | G2/G3 | ADR-02 |
| FR-11 / T-FR-11 | توقف قبل ارسال | توقف میان پرداخت و شروع submission مانع ارسال و محرک refund؛ عدم افشای علت؛ race آزموده شود | G2/G4 | PRD |
| FR-12 / T-FR-12 | stop/report بی‌حساب | لینک معتبر/منقضی/دستکاری‌شده و scanner GET؛ POST محدود، OTP برای فعال‌سازی دوباره | G4 | DATA-API |
| FR-13 / T-FR-13 | سابقه خصوصی | حساب B شناسه A را بخواند/حدس بزند؛ 404؛ pagination و شماره پوشیده؛ نشست admin کافی نیست | G2 | DATA-API |
| FR-14 / T-FR-14 | بدون ارتباط مستقیم | SMS، URL، API، history و صفحه گیرنده فاقد هویت طرف مقابل؛ هیچ reply/contact مستقیم | G2/G4 | PRD |
| FR-15 / T-FR-15 | مدیریت قابل رسیدگی | نقش، پرونده، تعلیق، emergency stop، مشاهده استثنایی و audit؛ پشتیبان مالی را تغییر ندهد | G1/G4 | DECISIONS-G0 |
| FR-16 / T-FR-16 | مالی و ارسال مستقل | accepted/delivered/unknown/refund جدا؛ late success، duplicate callback و late delivery تطبیق شوند | G3 | DATA-API |
| FR-17 / T-FR-17 | متن کامل و قطع دریافت قبل خرید | URL واقعی با طول نهایی، برند و بخش‌ها در quote؛ متن dispatch دقیقاً snapshot؛ بعد خرید AI اجرا نشود | G2/G3 | PRD |
| FR-18 / T-FR-18 | demo مستقل و آشکار | هیچ outbound واقعی در demo؛ pay-demo در live غیرفعال؛ delivered_demo با تحویل واقعی اشتباه نشود | G1/G2 | ADR |
| FR-19 / T-FR-19 | PWA نسخه اول | نصب واقعی Android/iOS، offline عمومی و SW/cache/update پایه در G2؛ همه PWها در gate مربوط | G2/G4/G5/G6 | UX / PW |

## نیازمندی‌های فنی/کیفی

| شناسه / آزمون | الزام | معیار پذیرش | gate | مرجع داخل بسته |
| --- | --- | --- | --- | --- |
| NFR-01 / T-NFR-01 | معماری یکپارچه | ADR مصوب و مرز frontend/backend/worker؛ میکروسرویس ناخواسته اضافه نشود | G0/G1 | ADR-01 |
| NFR-02 / T-NFR-02 | مرجع داده و صف | پاک‌شدن Redis/قطع broker، سقف/ترجیح/مالی را از بین نبرد؛ outbox قابل بازیابی | G2/G4 | ADR-02 |
| NFR-03 / T-NFR-03 | شماره و log | cipher/HMAC مستقل و key version؛ نشت phone/OTP/text/token در log/queue/analytics بررسی شود | G2/G4 | DATA-API |
| NFR-04 / T-NFR-04 | نشست و CSRF | cross-origin mutation، session rotation، مالکیت، admin-only login، logout/حساب دیگر | G1/G2 | DATA-API |
| NFR-05 / T-NFR-05 | عدد صحیح و واحد | تومان/ریال صریح؛ آزمون تبدیل ×۱۰، rounding ممنوع، مبلغ quote و verify برابر | G2/G3 | DATA-API |
| NFR-06 / T-NFR-06 | بازیابی و تطبیق | unknown/reconcile، broker recovery و restore روی محیط جدا؛ توقف تا تطبیق suppression/مالی | G3/G4 | ADR / DECISIONS-G0 |
| NFR-07 / T-NFR-07 | شکست بسته مدل | timeout/فرمت/شناسه/محدودیت مصرف؛ خروجی آزاد در صف نباشد؛ fallback فقط انتخاب صریح قالب | G2/G3 | ADR-03 |
| NFR-08 / T-NFR-08 | ظرفیت مشخص | بار مصنوعی و منابع ثبت‌شده، اهداف API/صف و نرخ موفق/رد مجزا؛ عدد حساب معادل concurrent نیست | G6 | ECONOMICS-PLAN |
| NFR-09 / T-NFR-09 | محیط تکرارپذیر | Compose محلی روی محیط پاک، نسخه و نصب از lock، health؛ خطای image موفق فرض نشود | G1 | ADR-05 |
| NFR-10 / T-NFR-10 | مدرک تحویل | برای هر تست build/env/date/device/result/evidence/defect؛ بدون سند PASS ثبت نشود | همه gateها | این ماتریس |
| NFR-11 / T-NFR-11 | polling محدود | ۲ ثانیه ×۲۰، توقف روی خروج/نتیجه، استعلام دستی؛ WS و polling بی‌پایان نباشد | G2 | PRD |
| NFR-12 / T-NFR-12 | CI و اجرای محلی | workflow بدون secret، اجرای کنترل‌شده محلی، بدون auto cloud deploy یا SMS/payment واقعی | G1/G6 | ADR-05 |
| NFR-13 / T-NFR-13 | تمام MFها | MF-01 تا MF-06 تک‌تک مدرک داشته باشند؛ نمونه اندازه 375 کافی نیست | G2/G5/G6 | UX |
| NFR-14 / T-NFR-14 | manifest و نصب | PW-01 تا PW-03 روی واقعی Android/iOS و identity پایدار | G2 | PW |
| NFR-15 / T-NFR-15 | SW/cache امن | PW-04 تا PW-07 با inspection در browser و standalone و حساب‌های متفاوت | G2/G4 | PW |
| NFR-16 / T-NFR-16 | update و recovery | PW-08 تا PW-10 با دو tab، form/payment و قطع دانلود، upgrade و rollback | G2/G4 | PW |
| NFR-17 / T-NFR-17 | سازگاری و دسترس‌پذیری | PW-11 تا PW-14 و WCAG2.2AA قابل اعمال؛ ابزار خودکار به‌تنهایی کافی نیست | G2/G5/G6 | UX / PW |

## Mobile-first

| شناسه / آزمون | الزام | معیار پذیرش | gate | مرجع داخل بسته |
| --- | --- | --- | --- | --- |
| MF-01 / T-MF-01 | شروع از موبایل | وایرفریم پیش از desktop؛ عرض ۳۲۰/۳۶۰/۳۷۵/۳۹۰/۴۱۲ سپس۷۶۸/۱۲۸۰؛ بدون overflow ناخواسته | G2 | UX W-01..06 |
| MF-02 / T-MF-02 | لمس و keyboard | هدف۴۴×۴۴، label/inputmode و safe-area؛ دکمه/خطا با keyboard و landscape پنهان نباشد | G2/G5 | UX W-02..03 |
| MF-03 / T-MF-03 | WCAG 2.2 AA | تمام معیارهای قابل اعمال با شرح pass یا دلیل عدم اعمال؛ focus/کنتراست/خوانش/zoom/keyboard/reflow | G2/G5 | UX ضوابط |
| MF-04 / T-MF-04 | RTL و ورودی مختلط | اعداد فارسی/عربی/paste/OTP؛ شماره/مبلغ/شناسه در متن فارسی با ترتیب درست و بدون hover dependency | G2 | UX |
| MF-05 / T-MF-05 | کارکرد و شبکه ضعیف | بودجه JS/انتقال و پروفایل شبکه سند اقتصاد؛ بدون انتظار بی‌پایان؛ field CWV فقط با داده کافی | G2/G6 | ECONOMICS-PLAN |
| MF-06 / T-MF-06 | جریان واقعی موبایل | ورود تا درگاه و برگشت، foreground/background، چرخش، history و stop در browser و standalone | G2/G3/G5 | UX / DATA-API |

## PWA اجباری

| شناسه / آزمون | الزام | معیار پذیرش | gate | مرجع داخل بسته |
| --- | --- | --- | --- | --- |
| PW-01 / T-PW-01 | HTTPS و scope | TLS معتبر/no mixed-content در تست دستگاه؛ localhost فقط همان دستگاه؛ مبدأ و scope محدود ثبت شود | G2 | ADR-04 |
| PW-02 / T-PW-02 | manifest کامل | name/short/id/start/scope/display/lang/dir/theme/background؛ PNG192/512، maskable و apple icon؛ بدون داده خصوصی | G2 | ADR-04 |
| PW-03 / T-PW-03 | نصب واقعی | Chrome Android و Safari iOS Home Screen؛ آیکون/name/launch درست؛ prompt ساختگی یا تکراری در standalone نباشد | G2/G5 | UX W-06 |
| PW-04 / T-PW-04 | چرخه SW | install/activate/fetch/scope، شکست نسخه تازه نسخه سالم را خراب نکند؛ update فایل worker قفل نشود | G2/G4 | ADR-04 |
| PW-05 / T-PW-05 | offline صادقانه | پس از بازدید آنلاین عمومی/fallback باز شود؛ cache خالی هم راهنما؛ هیچ ادعای ورود/پرداخت/ارسال آفلاین | G2 | UX W-06 |
| PW-06 / T-PW-06 | allowlist cache | در CacheStorage/IDB/localStorage و cache چارچوب، phone/OTP/token/session/private text/history/admin/callback/error نباشد | G2/G4 | ADR-04 |
| PW-07 / T-PW-07 | دستگاه مشترک | A logout و B login؛ Back/bfcache/reopen/offline بدون متن و سابقه A؛ حافظه خصوصی پاک شود | G2/G4 | UX W-06 |
| PW-08 / T-PW-08 | update امن | فرم نیمه‌تمام/OTP/درگاه در دو tab، نسخه تازه معرفی و تعویق‌پذیر؛ reload/activation اجباری ممنوع | G2/G4 | UX W-06 |
| PW-09 / T-PW-09 | rollback و asset | upgrade خراب/نیمه‌کاره و rollback؛ نسخه صحیح JS/CSS و cache نسخه‌دار، بدون loop؛ asset قدیم به‌موقع حذف | G4/G6 | ADR-04 |
| PW-10 / T-PW-10 | بدون offline replay | قطع هر mutation و اتصال دوباره؛ هیچ Background Sync/صف OTP/order/payment/SMS/preference؛ فقط استعلام همان سفارش | G2/G3/G4 | DATA-API |
| PW-11 / T-PW-11 | ماتریس پلتفرم | Android/iOS واقعی در دو حالت و دو نسخه عمده آخر هنگام gate؛ desktop Chrome/Edge/Safari/Firefox برای وب؛ مشخصات ثبت | G2/G5/G6 | UX ضوابط |
| PW-12 / T-PW-12 | پیشرفت تدریجی | وب بدون نصب قابل استفاده؛ push/camera/location/contacts خودکار درخواست نشود؛ قابلیت ناموجود fallback روشن | G2/G5 | ADR-04 |
| PW-13 / T-PW-13 | deep link و درگاه | SMS link، Back، reopen standalone، خروج scope و بازگشت پرداخت با نشست عوض‌شده؛ URL بدون شماره/OTP/متن خصوصی | G3/G4/G5 | DATA-API |
| PW-14 / T-PW-14 | شواهد جامع | manifest/SW/cache/manual+device/network/update/QA؛ صرف Lighthouse یا manifest PASS پذیرش نیست | G2/G4/G5/G6 | همه اسناد |

## آزمون‌های سیاست‌های دقیق‌شده فاز صفر

| آزمون | سناریو/نتیجه لازم | gate |
| --- | --- | --- |
| T-POL-01 | سه سفارش در۲۴ساعت شامل لغو/رهاشده؛ retry سهم جدید ندارد؛ چندفرستنده/یک‌گیرنده و جفت۳۰روز با PG واقعی و پاک‌شدن Redis | G2/G4 |
| T-POL-02 | مرز ساعات۹/۲۱ تهران، رزرو/expiry، صف بیش از۲۴ساعت؛ هیچ ارسال خارج زمان یا پس از انقضا، وجه به مسیر مصوب برود | G2/G3 |
| T-POL-03 | قیمت شامل متن کامل و link، max۳بخش؛ emoji/نیم‌فاصله؛ tampering مبلغ/واحد/گیرنده رد | G2/G3 |
| T-POL-04 | شکست/توقف/undeliverable و unknown۲۴ساعته، refund کامل بدون duplicate و مدرک؛ late result بدون SMS تازه | G3/G4 |
| T-POL-05 | pruning با زمان مصنوعی برای هر ردیف retention، حذف حساب، suppression و گزارش باز؛ restore درخواست حذف را برنگرداند | G4 |
| T-POL-06 | permission role، emergency stop، پوشش پشتیبان، هشدار۸۰٪/توقف۱۰۰٪ بودجه؛ نشت secret/token در log/API/browser بررسی | G4/G5 |
| T-POL-07 | crash بعد پذیرش provider، تحویل مجدد صف و خروج از پنجره استعلام localid؛ unknown بدون retry کور و رسیدگی انسانی | G3 |
| T-POL-08 | تمام هفت موضوع با stop، quota و گزارش یکسان؛ مثبت مجوز ارسال گروهی یا دورزدن منع دریافت نباشد | G2/G4/G5 |

## شواهد لازم و قواعد gate

برای هر case: نسخه/build/commit یا hash، نسخه معیار، محیط و dependencyها، دستگاه/OS/browser/mode، ورودی مصنوعی/شماره مجاز، وضعیت شبکه/clock، انتظار، نتیجه PASS/FAIL/NOT_TESTED/BLOCKED، فایل مدرک و defect، مجری و زمان. عدم اعمال یک معیار فقط با دلیل روشن و تأیید کارفرما ثبت می‌شود؛ حذف بی‌صدا پذیرفته نیست.

G1 پایه محلی؛ G2 مسیر demo + PWA نصب/آفلاین/cache/update پایه؛ G3 قراردادهای واقعی و مالی؛ G4 privacy/stop/ops و سخت‌سازی PWA؛ G5 جریان روی دستگاه واقعی و پایلوت مجاز؛ G6 بار/rollback و ممیزی نهایی. آزمون‌های G2 با پرداخت واقعی درگاه اجرا نمی‌شوند؛ سناریوی واقعی همان نیازمندی در G3 تکرار می‌شود. نصب واقعی دستگاه در G2 با محیط HTTPS و demo ممکن است و تا G5 عقب نمی‌افتد.

هیچ نقص بحرانی/شدید یا معیار اجباریِ آزموده‌نشده در gate مربوط، با عنوان «پذیرش کامل» بسته نمی‌شود. نتیجه ناموفق به اصلاح در همان فاز مجاز یا درخواست تصمیم منجر می‌شود. پذیرش gate و مجوز شروع فاز بعد فیلدهای جدا دارند.

## ماتریس آفلاین هنجاری

| مسیر | رفتار لازم |
| --- | --- |
| عمومی/فونت/آیکون نسخه‌دار | allowlist و fallback پس از بازدید؛ قیمت cached مبنای خرید نیست |
| فرم/متن/quote | متن فقط حافظه، بدون persistence خصوصی؛ quote تازه نیازمند سرور |
| OTP/session/history/admin | network-only، بدون cache ماندگار، نتیجه ورود cached نباشد |
| order/payment/SMS | عملیات آفلاین/خرید/ارسال تازه و replay ممنوع؛ بعد اتصال استعلام همان مرجع |
| stop/report | guide عمومی ممکن، ثبت موفق تنها پاسخ سرور؛ reconnect اقدام خودکار نکند |
| update/logout | نسخه تازه در نقطه امن، private state پاک؛ account قبل با Back/standalone/offline برنگردد |

منابع معیارها: [نصب PWA در MDN](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable)، [چرخه SW](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers)، [WCAG 2.2](https://www.w3.org/WAI/WCAG22/quickref/) و [Web Vitals](https://web.dev/articles/vitals). اعداد/قواعد cache و gateها الزام پیشنهادی پروژه‌اند؛ حداقل نصب یک مرورگر جای کل تعهد PWA پروژه نیست.
