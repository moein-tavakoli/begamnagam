"use client";

import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { gsap } from "gsap";
import styles from "./letter-flight.module.css";

/** Original artwork, with separate entrance and idle transforms for each piece. */
export function LetterFlight({ active = true }: { active?: boolean }) {
  const stage = useRef<HTMLDivElement>(null);
  const syncPlayback = useRef<() => void>(() => {});
  const pausedRef = useRef(false);
  const [paused, setPaused] = useState(false);
  const uid = useId().replace(/:/g, "");
  const paint = (name: string) => `url(#${uid}-${name})`;

  useLayoutEffect(() => {
    const root = stage.current;
    if (!root || !active) return;
    const media = gsap.matchMedia();
    media.add("(prefers-reduced-motion: no-preference)", () => {
      const select = gsap.utils.selector(root);
      gsap.set(select("[data-enter], [data-idle], [data-eyes]"), { transformOrigin: "50% 50%" });
      const master = gsap.timeline({ paused: true });
      // A small anticipation, then the envelope banks into place; its companions follow.
      master.from(select('[data-enter="shadow"]'), { scale: .35, opacity: 0, duration: .8, ease: "power2.out" }, 0)
        .from(select('[data-enter="cloud"]'), { x: i => i ? 34 : -34, opacity: 0, duration: 1, stagger: .14, ease: "power3.out" }, .08)
        .from(select('[data-enter="envelope"]'), { x: 70, y: 80, rotation: 24, scale: .65, opacity: 0, duration: 1.15, ease: "back.out(1.15)" }, .16)
        .from(select('[data-enter="heart"]'), { y: 65, rotation: -22, scale: .2, opacity: 0, duration: .95, ease: "back.out(1.9)" }, .55)
        .from(select('[data-enter="friend"]'), { x: -65, y: 48, rotation: -28, scaleX: .7, scaleY: 1.18, opacity: 0, duration: 1, ease: "elastic.out(1,.65)" }, .77)
        .from(select('[data-enter="spark"]'), { scale: 0, rotation: -65, opacity: 0, duration: .65, stagger: .09, ease: "back.out(2.2)" }, .95);

      // Independent phases keep the scene alive without moving everything in unison.
      const idle = gsap.timeline({ repeat: -1, defaults: { ease: "sine.inOut" } });
      idle.to(select('[data-idle="envelope"]'), { y: -9, x: -3, rotation: -2.5, duration: 2.4 }, 0)
        .to(select('[data-idle="envelope"]'), { y: 3, x: 3, rotation: 1.8, duration: 2.2 }, 2.4)
        .to(select('[data-idle="envelope"]'), { y: 0, x: 0, rotation: 0, duration: 1.8 }, 4.6)
        .to(select('[data-idle="shadow"]'), { scaleX: .88, opacity: .65, duration: 2.4 }, 0)
        .to(select('[data-idle="shadow"]'), { scaleX: 1, opacity: 1, duration: 4 }, 2.4)
        .to(select('[data-idle="heart"]'), { y: -13, x: 4, rotation: 5, duration: 2.7 }, 0)
        .to(select('[data-idle="heart"]'), { y: 0, x: 0, rotation: 0, duration: 3.7 }, 2.7)
        .to(select('[data-pulse]'), { scale: 1.07, duration: .22, ease: "power2.out" }, 1.2)
        .to(select('[data-pulse]'), { scale: 1, duration: .24 }, 1.42)
        .to(select('[data-pulse]'), { scale: 1.04, duration: .2 }, 1.66)
        .to(select('[data-pulse]'), { scale: 1, duration: .38 }, 1.86)
        .to(select('[data-idle="friend"]'), { y: 5, rotation: -3, scaleX: 1.04, scaleY: .95, duration: .4 }, .5)
        .to(select('[data-idle="friend"]'), { y: -11, rotation: 4, scaleX: .98, scaleY: 1.02, duration: .65, ease: "power2.out" }, .9)
        .to(select('[data-idle="friend"]'), { y: 0, rotation: 0, scaleX: 1, scaleY: 1, duration: 1.4, ease: "elastic.out(1,.8)" }, 1.55)
        .to(select('[data-eyes]'), { scaleY: .12, duration: .08, repeat: 1, yoyo: true }, 3.2)
        .to(select('[data-idle="cloud"]'), { x: i => i ? -7 : 6, y: -3, duration: 3.2 }, 0)
        .to(select('[data-idle="cloud"]'), { x: 0, y: 0, duration: 3.2 }, 3.2)
        .to(select('[data-idle="spark"]'), { y: i => i % 2 ? 5 : -6, rotation: i => i % 2 ? -12 : 14, scale: 1.08, duration: 2.5, stagger: .12 }, 0)
        .to(select('[data-idle="spark"]'), { y: 0, rotation: 0, scale: 1, duration: 2.9, stagger: .12 }, 2.9);
      gsap.set(select('[data-pulse]'), { transformOrigin: "50% 65%" });
      master.add(idle, 2.15);
      let visible = false;
      const sync = () => {
        const playing = visible && !document.hidden && !pausedRef.current;
        master.paused(!playing);
        root.dataset.motion = playing ? "running" : "paused";
      };
      syncPlayback.current = sync;
      const observer = new IntersectionObserver(entries => { visible = entries[0].isIntersecting; sync(); }, { threshold: .1 });
      observer.observe(root);
      document.addEventListener("visibilitychange", sync);
      return () => {
        observer.disconnect(); document.removeEventListener("visibilitychange", sync);
        syncPlayback.current = () => {}; root.dataset.motion = "static";
      };
    }, root);
    return () => { media.revert(); root.dataset.motion = "static"; };
  }, [active]);

  useEffect(() => { pausedRef.current = paused; syncPlayback.current(); }, [paused]);

  return <div className={styles.stage} ref={stage} data-motion="static">
    <svg className="letter-flight" viewBox="0 0 460 380" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id={`${uid}-body`} x1="150" y1="100" x2="340" y2="280" gradientUnits="userSpaceOnUse"><stop stopColor="#fff"/><stop offset="1" stopColor="#e5ddff"/></linearGradient>
        <linearGradient id={`${uid}-flap`} x1="150" y1="130" x2="290" y2="220" gradientUnits="userSpaceOnUse"><stop stopColor="#fff"/><stop offset="1" stopColor="#f2eefe"/></linearGradient>
        <linearGradient id={`${uid}-heart`} x1="210" y1="80" x2="260" y2="165" gradientUnits="userSpaceOnUse"><stop stopColor="#ffacae"/><stop offset="1" stopColor="#f36479"/></linearGradient>
        <linearGradient id={`${uid}-friend`} x1="90" y1="180" x2="180" y2="290" gradientUnits="userSpaceOnUse"><stop stopColor="#bba6ff"/><stop offset="1" stopColor="#8e6ce2"/></linearGradient>
        <filter id={`${uid}-shadow`} x="-50%" y="-50%" width="200%" height="220%"><feDropShadow dx="0" dy="15" stdDeviation="10" floodColor="#8a4b33" floodOpacity=".16"/></filter>
      </defs>
      <g data-enter="shadow"><g data-idle="shadow"><ellipse cx="237" cy="327" rx="111" ry="15" fill="#dca334" opacity=".3"/></g></g>
      <g data-enter="cloud"><g data-idle="cloud"><path d="M68 245c-40-16-25-57 8-53-2-32 50-45 61-13 27-4 39 35 10 47" fill="#fff8ee"/></g></g>
      <g data-enter="cloud"><g data-idle="cloud"><path d="M333 120c-19 0-25-26-5-33 0-25 35-33 42-8 27-5 36 31 11 38" fill="#fff8ee"/></g></g>
      <g filter={paint("shadow")}>
        <g data-enter="envelope"><g data-idle="envelope"><g transform="rotate(-12 239 215)">
          <rect x="130" y="128" width="218" height="160" rx="28" fill={paint("body")}/>
          <path d="m142 272 83-74c9-8 20-8 29 0l82 74" stroke="#c5b5ef" strokeWidth="3"/>
          <path d="m131 151 89 68c11 9 24 9 36 0l90-68c-3-14-12-23-25-23H157c-13 0-23 9-26 23Z" fill={paint("flap")}/>
          <path d="m143 144 86 65c6 5 13 5 20 0l85-65" stroke="white" strokeWidth="5" strokeLinecap="round"/>
        </g></g></g>
        <g data-enter="heart"><g data-idle="heart"><g data-pulse="true">
          <path d="M234 153s-48-24-48-54c0-25 33-33 48-12 16-21 48-13 48 12 0 30-48 54-48 54Z" fill={paint("heart")}/>
          <path d="M204 98c2-6 8-8 12-6" stroke="#ffd0d3" strokeWidth="6" strokeLinecap="round"/>
        </g></g></g>
        <g data-enter="friend"><g data-idle="friend">
          <rect x="84" y="225" width="112" height="77" rx="27" fill={paint("friend")} transform="rotate(8 140 264)"/>
          <path d="m112 294 2 24 27-17" fill="#9c80ea"/>
          <g data-eyes="true"><circle cx="121" cy="260" r="4" fill="#34254e"/><circle cx="161" cy="265" r="4" fill="#34254e"/></g>
          <path d="M134 276c5 6 12 7 18 2" stroke="#34254e" strokeWidth="4" strokeLinecap="round"/>
        </g></g>
      </g>
      <g data-enter="spark"><g data-idle="spark"><path d="m349 224 8 16 17 3-13 12 2 18-15-9-16 7 4-17-11-14 18-1 6-15Z" fill="#ff8d9c"/></g></g>
      <g data-enter="spark"><g data-idle="spark"><path d="m113 107 5 12 13 2-10 9 2 13-11-6-12 6 3-13-9-10 13-1 6-12Z" fill="#fff"/></g></g>
      <g data-enter="spark"><g data-idle="spark"><circle cx="318" cy="307" r="6" fill="#fff"/></g></g>
      <g data-enter="spark"><g data-idle="spark"><circle cx="72" cy="145" r="5" fill="#a58aef"/></g></g>
      <g data-enter="spark"><g data-idle="spark"><path d="m373 180 12-5m-17-9 4-12M91 315l-12 7" stroke="#684da1" strokeWidth="3" strokeLinecap="round"/></g></g>
    </svg>
    <button className={styles.pause} data-home-enter="pause" type="button" aria-label="توقف حرکت تصویر" aria-pressed={paused} title={paused ? "ادامهٔ حرکت تصویر" : "توقف حرکت تصویر"} onClick={() => setPaused(value => !value)}>
      <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" fill="currentColor">{paused ? <path d="m5 3 8 5-8 5Z"/> : <><rect x="4" y="3" width="3" height="10" rx="1"/><rect x="10" y="3" width="3" height="10" rx="1"/></>}</svg>
    </button>
  </div>;
}
