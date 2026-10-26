"use client";
import { useApp } from "./app-provider";
import { toman } from "@/lib/format";
import { Icon } from "./icons";
import { ServiceState } from "./feedback";
import { FreeSendsBalance } from "./free-sends";

export function Pricing() {
  const { data } = useApp();
  return (
    <div className="pricing-card">
      <div>
        <span className="eyebrow">روشن و ساده</span>
        <h2>هزینه هر پیام</h2>
        <p>۳ ارسال اول هدیهٔ ماست؛ یک‌بار برای هر شمارهٔ تأییدشده. {data && !data.demo_mode && data.payment_backend === "disabled" ? "ارسال پولی فعلاً بسته است؛ قیمت زیر برای زمان فعال‌شدن پرداخت است." : "بعدش هر پیام با هزینهٔ زیره."}</p>
        <FreeSendsBalance />
      </div>
      <div className="price-amount">
        {data ? (
          <>
            <strong>
              {new Intl.NumberFormat("fa-IR").format(data.price_toman)}
            </strong>
            <span>تومان / هر درخواست</span>
          </>
        ) : (
          <ServiceState />
        )}
      </div>
      <div className="pricing-footnote">
        <Icon name="info" size={19} />
        <p>
          {data?.demo_mode
            ? `مبلغ ${toman(data.price_toman)} در این نسخه صرفاً برای تست ثبت سفارش است؛ پرداخت و ارسال پیام به گیرنده آزمایشی‌اند.`
            : data?.payment_backend === "disabled"
              ? "ارسال‌های هدیه پیامک واقعی‌اند. بعد از مصرف ۳ هدیه، تا فعال‌شدن پرداخت امکان ارسال تازه وجود نداره؛ وجهی دریافت نمی‌شه."
              : "متن نهایی و هزینه را پیش از تأیید بررسی کن. ثبت در صف به معنی تحویل قطعی یا خوانده‌شدن پیام نیست."}
        </p>
      </div>
    </div>
  );
}
