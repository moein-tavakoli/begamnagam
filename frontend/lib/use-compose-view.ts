"use client";

import { useSyncExternalStore } from "react";
import { usePathname } from "next/navigation";

const VIEW_EVENT = "compose-view-change";
function subscribe(notify: () => void) {
  window.addEventListener("hashchange", notify);
  window.addEventListener("popstate", notify);
  window.addEventListener(VIEW_EVENT, notify);
  return () => {
    window.removeEventListener("hashchange", notify);
    window.removeEventListener("popstate", notify);
    window.removeEventListener(VIEW_EVENT, notify);
  };
}
export function useComposeView() {
  const path = usePathname();
  const compose = useSyncExternalStore(subscribe, () => window.location.hash === "#compose", () => false);
  return path === "/" && compose;
}

export function changeHomeView(compose: boolean) {
  const hash = compose ? "#compose" : "";
  if (window.location.hash !== hash)
    window.history.pushState(null, "", `${window.location.pathname}${window.location.search}${hash}`);
  window.dispatchEvent(new Event(VIEW_EVENT));
}
