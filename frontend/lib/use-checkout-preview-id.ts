"use client";

import { useSyncExternalStore } from "react";
import { checkoutPreviewId } from "./credit-purchases";

function subscribe(notify: () => void) {
  window.addEventListener("hashchange", notify);
  window.addEventListener("popstate", notify);
  return () => {
    window.removeEventListener("hashchange", notify);
    window.removeEventListener("popstate", notify);
  };
}

export function useCheckoutPreviewId() {
  return useSyncExternalStore(subscribe, () => checkoutPreviewId(window.location.hash), () => null);
}
