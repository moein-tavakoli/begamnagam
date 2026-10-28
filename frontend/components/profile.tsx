"use client";

import Link from "next/link";
import { useState } from "react";
import { api, errorMessage } from "@/lib/api";
import { useApp } from "./app-provider";
import { AuthGate } from "./auth-gate";
import { BusyButton, ErrorBox, ServiceState } from "./feedback";
import { Icon } from "./icons";

export function Profile() {
  const { data, reload } = useApp();
  const [loggingOut, setLoggingOut] = useState(false);
  const [error, setError] = useState("");
  const number = new Intl.NumberFormat("fa-IR");

  async function logout() {
    setLoggingOut(true);
    setError("");
    try {
      await api("/auth/logout", { method: "POST", body: {} });
      await reload();
      window.location.assign("/");
    } catch (error) {
      setError(errorMessage(error));
      setLoggingOut(false);
    }
  }

  return (
    <div className="account-page profile-page wrap">
      <div className="account-heading">
        <h1>پروفایل من</h1>
        <p>اطلاعات حسابت و ارسال‌های باقی‌مانده رو اینجا ببین.</p>
      </div>
      <div className="account-card profile-card">
        <ServiceState />
        {!data?.authenticated ? (
          <AuthGate purpose="برای دیدن پروفایلت، شمارهٔ خودت رو تأیید کن." />
        ) : (
          <>
            <div className="profile-identity">
              <span className="profile-avatar"><Icon name="user" size={32} /></span>
              <div>
                <h2>شمارهٔ تأییدشده</h2>
                <bdi className="profile-phone">{data.phone_masked}</bdi>
                <span className="profile-verified"><Icon name="shield" size={15} /> حساب تأییدشده</span>
              </div>
            </div>
            <dl className="profile-stats">
              <div><dt>اعتبار بسته‌ها</dt><dd>{number.format(data.purchased_sends_remaining ?? 0)} <small>پیام{data.demo_mode ? " آزمایشی" : ""}</small></dd></div>
              <div><dt>ارسال باقی‌مانده</dt><dd>{number.format(data.free_sends_remaining ?? 0)} <small>از {number.format(data.free_sends_total ?? 3)}</small></dd></div>
              <div><dt>جایزهٔ دعوت‌ها</dt><dd>{number.format(data.free_sends_earned_total ?? 0)} <small>ارسال</small></dd></div>
            </dl>
            <nav className="profile-links" aria-label="بخش‌های حساب">
              <Link href="/wallet" prefetch={false}><Icon name="receipt" size={21} /><span>کیف پول من<small>موجودی، شارژ و گردش اعتبار</small></span><Icon name="arrow" size={18} /></Link>
              <Link href="/credits" prefetch={false}><Icon name="receipt" size={21} /><span>خرید بستهٔ پیام<small>بسته‌های فعال و اعتبار حساب</small></span><Icon name="arrow" size={18} /></Link>
              <Link href="/history" prefetch={false}><Icon name="receipt" size={21} /><span>پیام‌های من<small>سابقه و وضعیت ارسال‌ها</small></span><Icon name="arrow" size={18} /></Link>
              <Link href="/invitations" prefetch={false}><Icon name="heart" size={21} /><span>دعوت دوستان<small>دعوت‌ها و پاداش‌ها</small></span><Icon name="arrow" size={18} /></Link>
              <Link href="/preferences" prefetch={false}><Icon name="shield" size={21} /><span>مدیریت دریافت پیام<small>تنظیم دریافت و اطلاعات حساب</small></span><Icon name="arrow" size={18} /></Link>
            </nav>
            <ErrorBox message={error} />
            <BusyButton type="button" className="button ghost full-width profile-logout" busy={loggingOut} onClick={() => void logout()}>
              خروج از حساب
            </BusyButton>
          </>
        )}
      </div>
    </div>
  );
}
