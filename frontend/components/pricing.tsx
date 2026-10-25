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
        <p>۳ ارسال اول هدیهٔ ماست؛ یک‌بار برای هر شمارهٔ تأییدشده. بعدش هر پیام با هزینهٔ زیره.</p>
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
            : "پرداخت واقعی و فعال‌سازی ارسال، نیازمند آماده‌بودن درگاه و سرویس پیامکی است. وضعیت فعال سرویس را قبل از ادامه بررسی کن."}
        </p>
      </div>
    </div>
  );
}
