"use client";

import Link from "next/link";
import { version } from "../package.json";
import { usePathname } from "next/navigation";
import { Icon } from "./icons";
import { useApp } from "./app-provider";

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
  if (path === "/") return null;
  return (
    <header className="site-header wrap">
      <Brand />
      <nav className="main-nav" aria-label="منوی اصلی">
        <Link href="/help#how-it-works">چطور کار می‌کنه؟</Link>
        <Link href="/help">راهنما و هزینه</Link>
        <Link href="/invitations" prefetch={false}>دعوت دوستان</Link>
        <Link href="/history" prefetch={false} className="nav-account">
          <Icon name="receipt" size={18} /> پیام‌های من
        </Link>
      </nav>
    </header>
  );
}

export function Footer() {
  const { data } = useApp();
  return (
    <footer className="site-footer">
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
          <Link href="/invitations" prefetch={false}>دعوت دوستان</Link>
          <Link href="/preferences" prefetch={false}>قطع دریافت پیام</Link>
          <Link href="/privacy">حریم خصوصی و قوانین</Link>
          <Link href="/help">راهنمای استفاده</Link>
          <a href="/admin/" rel="nofollow">ورود مدیر سیستم</a>
        </nav>
      </div>
      <div className="wrap footer-bottom">
        <span>بگم نگم · نسخه {version}{data?.demo_mode ? " آزمایشی" : ""}</span>
        <span>با احترام، برای بهتر شدن</span>
      </div>
    </footer>
  );
}

export function MobileNav() {
  const path = usePathname();
  if (path === "/") return null;
  const links = [
    {href:"/", label:"خونه", icon:"space" as const},
    {href:"/#compose", label:"نوشتن پیام", icon:"chat" as const},
    {href:"/history", label:"پیام‌های من", icon:"receipt" as const},
    {href:"/invitations", label:"دعوت دوستان", icon:"heart" as const},
    {href:"/preferences", label:"دریافت پیام", icon:"shield" as const},
  ];
  return <nav className="mobile-nav" aria-label="دسترسی سریع موبایل">{links.map(item => <Link key={item.href} href={item.href} prefetch={item.href === "/" ? undefined : false} aria-current={path === item.href ? "page" : undefined}><Icon name={item.icon} size={21}/><span>{item.label}</span></Link>)}</nav>;
}
