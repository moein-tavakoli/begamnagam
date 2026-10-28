// Some installed browsers expose these APIs but deny access at runtime.
// Optional installation/session notifications must not prevent the app opening.
export function getServiceWorkerContainer(): ServiceWorkerContainer | null {
  try {
    return typeof navigator !== "undefined" ? navigator.serviceWorker ?? null : null;
  } catch {
    return null;
  }
}

export function openSessionChannel(): BroadcastChannel | null {
  try {
    return typeof BroadcastChannel !== "undefined" ? new BroadcastChannel("begamnagam-session") : null;
  } catch {
    return null;
  }
}
