# پوشش جاری ۵۶ نیازمندی — نسخه۰٫۷

شناسه‌های بسته فاز صفر حفظ شده‌اند؛ جدول تاریخی و manifest آن بازنویسی نشده‌اند. LOCAL_AUTO یعنی شاهد خودکار در دامنه محلی موجود است؛ این برچسب پذیرش انسانی/خارجی یا امضای gate نیست. PARTIAL یعنی اجرای محلی موجود است ولی شاهد اجباری بیرونی/انسانی یا پوشش کامل دستگاه باز است.

| شناسه | الزام | شاهد محلی | وضعیت |
| --- | --- | --- | --- |
| FR-01 | مسیر فارسی Mobile-first | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | PARTIAL |
| FR-02 | OTP شماره خود فرستنده | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | PARTIAL |
| FR-03 | سه موضوع مثبت | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | LOCAL_AUTO |
| FR-04 | چهار موضوع رفتاری محدود | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | LOCAL_AUTO |
| FR-05 | کنترل ورودی و خروجی | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | PARTIAL |
| FR-06 | متن و قیمت ثابت | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | LOCAL_AUTO |
| FR-07 | یک گیرنده | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | LOCAL_AUTO |
| FR-08 | تأیید مالی سمت سرور | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | PARTIAL |
| FR-09 | عدم تکرار | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | LOCAL_AUTO |
| FR-10 | outbox و صف | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | LOCAL_AUTO |
| FR-11 | توقف قبل ارسال | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | LOCAL_AUTO |
| FR-12 | stop/report بی‌حساب | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | LOCAL_AUTO |
| FR-13 | سابقه خصوصی | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | LOCAL_AUTO |
| FR-14 | بدون ارتباط مستقیم | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | LOCAL_AUTO |
| FR-15 | مدیریت قابل رسیدگی | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | PARTIAL |
| FR-16 | مالی و ارسال مستقل | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | PARTIAL |
| FR-17 | متن کامل و قطع دریافت قبل خرید | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | LOCAL_AUTO |
| FR-18 | demo مستقل و آشکار | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | LOCAL_AUTO |
| FR-19 | PWA نسخه اول | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | PARTIAL |
| NFR-01 | معماری یکپارچه | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | LOCAL_AUTO |
| NFR-02 | مرجع داده و صف | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | LOCAL_AUTO |
| NFR-03 | شماره و log | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | PARTIAL |
| NFR-04 | نشست و CSRF | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | LOCAL_AUTO |
| NFR-05 | عدد صحیح و واحد | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | LOCAL_AUTO |
| NFR-06 | بازیابی و تطبیق | [بازیابی](RESTORE.json)، [اتصال‌ها](../release-v0.4/README.fa.md) | PARTIAL |
| NFR-07 | شکست بسته مدل | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | PARTIAL |
| NFR-08 | ظرفیت مشخص | [بار۱۰۰۰حساب](BENCHMARK.json) | LOCAL_AUTO |
| NFR-09 | محیط تکرارپذیر | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | LOCAL_AUTO |
| NFR-10 | مدرک تحویل | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | PARTIAL |
| NFR-11 | polling محدود | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | LOCAL_AUTO |
| NFR-12 | CI و اجرای محلی | [تست‌های backend/frontend](EVIDENCE.json)، [تمرین۱۲سناریو](../release-v0.6/SYNTHETIC-PILOT.json)، [ایمنی](../release-v0.5/README.fa.md) | PARTIAL |
| NFR-13 | تمام MFها | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | PARTIAL |
| NFR-14 | manifest و نصب | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | PARTIAL |
| NFR-15 | SW/cache امن | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | PARTIAL |
| NFR-16 | update و recovery | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | PARTIAL |
| NFR-17 | سازگاری و دسترس‌پذیری | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | PARTIAL |
| MF-01 | شروع از موبایل | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | PARTIAL |
| MF-02 | لمس و keyboard | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | PARTIAL |
| MF-03 | WCAG 2.2 AA | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | PARTIAL |
| MF-04 | RTL و ورودی مختلط | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | LOCAL_AUTO |
| MF-05 | کارکرد و شبکه ضعیف | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | PARTIAL |
| MF-06 | جریان واقعی موبایل | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | PARTIAL |
| PW-01 | HTTPS و scope | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | PARTIAL |
| PW-02 | manifest کامل | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | LOCAL_AUTO |
| PW-03 | نصب واقعی | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | PARTIAL |
| PW-04 | چرخه SW | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | PARTIAL |
| PW-05 | offline صادقانه | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | PARTIAL |
| PW-06 | allowlist cache | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | PARTIAL |
| PW-07 | دستگاه مشترک | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | PARTIAL |
| PW-08 | update امن | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | PARTIAL |
| PW-09 | rollback و asset | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | PARTIAL |
| PW-10 | بدون offline replay | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | LOCAL_AUTO |
| PW-11 | ماتریس پلتفرم | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | PARTIAL |
| PW-12 | پیشرفت تدریجی | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | LOCAL_AUTO |
| PW-13 | deep link و درگاه | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | PARTIAL |
| PW-14 | شواهد جامع | [مرورگر PWA](PWA-BROWSER.json)، [foundation](EVIDENCE.json)، [بررسی انسانی](HUMAN-REVIEW.fa.md) | PARTIAL |

آزمون‌های سیاستی POL نیز زیر همین شواهد قرار دارند: محدودیت‌ها و race در تست PostgreSQL؛ ساعت/انقضای۲۴ساعته و هزینه در safety؛ refund/unknown در provider؛ retention/key rotation در privacy؛ توقف پس از snapshot در restore. حذفِ پس از snapshot در restore نهایی مستقیماً تمرین نشده و در چک‌لیست خارج دستگاه باقی است.

پروفایل ظرفیت، API خواندنی۲RPS به مدت۱۵دقیقه و جهش۱۰RPS به مدت۶۰ثانیه بود؛۳۰ جریان کامل پیام جدا اجرا شد. هیچ ادعای۱۰۰۰ کاربر هم‌زمان یا SLA سرویس‌دهنده وجود ندارد.
