"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Icon } from "./icons";
import { LetterFlight } from "./letter-flight";
import { HomeTrustMarks } from "./home-trust-marks";
import { ThemeToggle } from "./theme-toggle";
import { changeHomeView, useComposeView } from "@/lib/use-compose-view";
import { HomeLogout } from "./home-logout";
import { AppVersion } from "./app-version";
import styles from "./home-intro.module.css";

type HomeComposerProps = { active: boolean; focusOnActivate: boolean; onExit: () => void };

function ComposerUnavailable({ active, onExit }: HomeComposerProps) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (active) heading.current?.focus({ preventScroll: true });
  }, [active]);
  return <div className="account-card">
    <h2 ref={heading} tabIndex={-1}>فرم پیام بارگیری نشد.</h2>
    <button type="button" className="button primary" onClick={() => window.location.reload()}>تلاش دوباره</button>
    <button type="button" className="button secondary" onClick={onExit}>بازگشت</button>
  </div>;
}

const Composer = dynamic<HomeComposerProps>(() => import("./composer").then(
  module => module.Composer,
  () => ComposerUnavailable,
), {
  loading: () => <p role="status">در حال آماده کردن فرم پیام…</p>,
});

export function HomeFlow() {
  const composing = useComposeView();
  const [composerOpened, setComposerOpened] = useState(false);
  const touch = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    const resize = () => {
      const viewport = window.visualViewport;
      if (viewport && Math.abs(viewport.scale - 1) > 0.01) return;
      document.documentElement.style.setProperty("--app-height", `${viewport?.height || window.innerHeight}px`);
      const keyboardInset = viewport ? Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop) : 0;
      document.documentElement.style.setProperty("--composer-keyboard-inset", `${keyboardInset}px`);
    };
    resize();
    window.addEventListener("resize", resize);
    window.visualViewport?.addEventListener("resize", resize);
    window.visualViewport?.addEventListener("scroll", resize);
    return () => {
      window.removeEventListener("resize", resize);
      window.visualViewport?.removeEventListener("resize", resize);
      window.visualViewport?.removeEventListener("scroll", resize);
      document.documentElement.style.removeProperty("--app-height");
      document.documentElement.style.removeProperty("--composer-keyboard-inset");
    };
  }, []);

  useEffect(() => {
    if (composing) setComposerOpened(true);
    else document.getElementById("welcome-title")?.focus({ preventScroll: true });
  }, [composing]);

  function showComposer(value: boolean) {
    changeHomeView(value);
  }

  return (
    <div className="home-flow" data-view={composing ? "compose" : "welcome"} aria-label="شروع و نوشتن پیام">
      <section
        className="home-slide hero wrap"
        aria-roledescription="اسلاید"
        aria-label="معرفی؛ صفحه اول"
        aria-labelledby="welcome-title"
        hidden={composing}
        onPointerDown={event => {
          touch.current = null;
          if (event.pointerType !== "touch" || !event.isPrimary || event.clientX < 24 ||
              event.clientX > window.innerWidth - 24 ||
              (event.target as HTMLElement).closest("a,button")) return;
          touch.current = { x: event.clientX, y: event.clientY };
        }}
        onPointerCancel={() => { touch.current = null; }}
        onPointerUp={event => {
          const start = touch.current;
          touch.current = null;
          if (start && event.clientX - start.x > 64 && Math.abs(event.clientY - start.y) < 40)
            showComposer(true);
        }}
      >
        <Link href="/pricing" className="home-credit-link" data-home-enter="pricing"><Icon name="receipt" size={17} /> تعرفه‌ها و خرید اعتبار</Link>
        <div className="home-account-actions">
          <Link href="/profile" prefetch={false} className="home-profile-link" data-home-enter="profile">
            <Icon name="user" size={19} /> پروفایل
          </Link>
          <span className="home-theme-control" data-home-enter="theme"><ThemeToggle /></span>
        </div>
        <div className="hero-copy">
          <h1 id="welcome-title" tabIndex={-1}>
            <span className="hero-text-line" data-home-enter="title-first">یه حرف خوب،</span>
            <span className="hero-text-line" data-home-enter="title-last">یه <span className="highlight-text">حال خوب‌تر.</span></span>
          </h1>
          <p className="hero-description">
            <span className="hero-text-line" data-home-enter="description-first">پیامک بفرست یا لینک شخصی‌ات رو بده تا برات بنویسن.</span>
            <span className="hero-text-line" data-home-enter="description-last">شمارهٔ حساب فرستنده توی پیامک نمیاد.</span>
          </p>
          <div className={styles.paths} data-home-enter="primary">
            <button type="button" className="button primary" onClick={() => showComposer(true)}>
              <Icon name="send" size={18} /> پیامک بفرستم
            </button>
            <Link href="/profile/share" prefetch={false} className="button secondary">
              <Icon name="chat" size={18} /> لینک دریافت پیام بگیرم
            </Link>
          </div>
          <nav className={styles.audiences} aria-label="معرفی برای گروه‌ها" data-home-enter="help">
            <Link href="/about#family-friends">برای خانواده و دوستان</Link>
            <Link href="/about#neighbors">برای همسایه‌ها</Link>
          </nav>
          <div className={styles.more} data-home-enter="invite">
            <Link href="/help">راهنمای استفاده</Link>
            <Link href="/invitations" prefetch={false}>دعوت دوستان</Link>
          </div>
        </div>
        <div className="hero-art"><LetterFlight active={!composing} /><HomeTrustMarks /></div>
        <HomeLogout />
        <AppVersion />
      </section>
      <div className="home-slide compose-slide" hidden={!composing} aria-roledescription="اسلاید" aria-label="نوشتن پیام؛ صفحه دوم">
        {(composing || composerOpened) && <Composer active={composing} focusOnActivate onExit={() => showComposer(false)} />}
      </div>
    </div>
  );
}
