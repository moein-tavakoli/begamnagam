"use client";

import Link from "next/link";
import { version } from "../package.json";
import { usePathname } from "next/navigation";
import { Icon } from "./icons";
import { useApp } from "./app-provider";
import { CrestNavigation } from "./crest-navigation";
import navigationStyles from "./crest-navigation.module.css";
import { ThemeToggle } from "./theme-toggle";
import { useComposeView } from "@/lib/use-compose-view";

export function Brand() {
  return (
    <Link href="/" className="brand" aria-label="بگم نگم، صفحه اصلی">
      <span className="brand-mark">
        <Icon name="chat" size={24} />
      </span>
      <span>
        بگم<span className="brand-space"> </span>نگم
        <span className="brand-period">.</span>
      </span>
    </Link>
  );
}

export function Header() {
  const path = usePathname();
  const composing = useComposeView();
  const { data } = useApp();
  const hidden = (path === "/" && !composing) || path === "/links" || path.startsWith("/manage");
  return (
    <header className="site-header wrap" hidden={hidden}>
      <div className="header-brand-actions"><Brand /><ThemeToggle /></div>
      <CrestNavigation mode="desktop" />
      <nav className={navigationStyles.utilities} aria-label="راهنما و اعتبار">
        <Link href="/pricing">خرید اعتبار</Link>
        <Link href="/help#how-it-works">راهنمای استفاده</Link>
      </nav>
      {data?.authenticated && <div className="header-account">
        <bdi className="header-phone" dir="ltr" tabIndex={-1} aria-label="شمارهٔ حساب واردشده">{data.phone_masked}</bdi>
        <span className="header-balance" role="status">اعتبار: {new Intl.NumberFormat("fa-IR").format(data.purchased_sends_remaining ?? 0)} و {new Intl.NumberFormat("fa-IR").format(data.free_sends_remaining ?? 0)} هدیه</span>
      </div>}
    </header>
  );
}

export function Footer() {
  const { data } = useApp();
  const path = usePathname();
  if (path === "/links" || path.startsWith("/manage")) return null;
  return (
    <footer className={`site-footer${path === "/pricing" ? " pricing-footer" : ""}`}>
      <div className="wrap footer-top">
        <div>
          <Brand />
          <p>حرف‌های کوچک، حالِ بهتر.</p>
        </div>
        <div className="footer-note">
          کلمه‌ها می‌تونن مراقبت کنن.
          <br />
          بیایید با هم مهربون‌تر حرف بزنیم.
        </div>
        <nav aria-label="پیوندهای پایین صفحه">
          <Link href="/about">دربارهٔ بگم نگم</Link>
          <Link href="/pricing">تعرفه‌ها و خرید اعتبار</Link>
          <Link href="/invitations" prefetch={false}>دعوت دوستان</Link>
          <Link href="/preferences" prefetch={false}>قطع دریافت پیام</Link>
          <Link href="/privacy">حریم خصوصی و قوانین</Link>
          <Link href="/help">راهنمای استفاده</Link>
          <Link href="/links">شبکه‌های اجتماعی</Link>
          <Link href="/manage" prefetch={false} rel="nofollow">ورود مدیر سیستم</Link>
        </nav>
      </div>
      <div className="wrap footer-bottom">
        <span>بگم نگم{data?.demo_mode ? " · آزمایشی" : ""}</span>
        <span>با احترام، برای بهتر شدن</span>
      </div>
    </footer>
  );
}

export function MobileNav() {
  const path = usePathname();
  const composing = useComposeView();
  const hidden = (path === "/" && !composing) || path === "/links" || path.startsWith("/manage");
  return <CrestNavigation mode="mobile" hidden={hidden} />;
}

export function AppVersion() {
  const path = usePathname();
  if (path.startsWith("/manage") || path.startsWith("/admin")) return null;
  return <small className="app-version" aria-label="نسخهٔ نرم‌افزار">
    نسخه <bdi dir="ltr">{version}</bdi>{process.env.NODE_ENV === "development" ? " · توسعه" : ""}
  </small>;
}
