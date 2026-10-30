"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { Composer } from "./composer";
import { Icon } from "./icons";
import { LetterFlight } from "./letter-flight";
import { HomeTrustMarks } from "./home-trust-marks";
import { ThemeToggle } from "./theme-toggle";
import { changeHomeView, useComposeView } from "@/lib/use-compose-view";
import { HomeLogout } from "./home-logout";

export function HomeFlow() {
  const composing = useComposeView();
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
    document.getElementById(composing ? "compose-title" : "welcome-title")?.focus({ preventScroll: true });
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
            <span className="hero-text-line" data-home-enter="description-first">تشکر، دلگرمی یا یه یادآوری دوستانه؛</span>
            <span className="hero-text-line" data-home-enter="description-last">حرفت رو با احترام برسون، بدون نمایش اسمت به گیرنده.</span>
          </p>
          <button type="button" className="button primary hero-cta" data-home-enter="primary" onClick={() => showComposer(true)}>
            بعدی؛ حرفم رو بگم <Icon name="arrow" size={20} />
          </button>
          <Link href="/help" className="hero-help" data-home-enter="help">اول ببینم چطوری کار می‌کنه</Link>
          <Link href="/invitations" prefetch={false} className="hero-help" data-home-enter="invite">دعوت دوستان <Icon name="heart" size={16} /></Link>
        </div>
        <div className="hero-art"><LetterFlight active={!composing} /><HomeTrustMarks /></div>
        <HomeLogout />
      </section>
      <div className="home-slide compose-slide" hidden={!composing} aria-roledescription="اسلاید" aria-label="نوشتن پیام؛ صفحه دوم">
        <Composer onExit={() => showComposer(false)} />
      </div>
    </div>
  );
}
