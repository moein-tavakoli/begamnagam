"use client";
import { useEffect, useState } from "react";

export function PWAFoundation() {
  const [offline, setOffline] = useState(false);
  useEffect(() => {
    const update = () => setOffline(!navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    // Development HMR and a production worker must not share cached builds.
    if (process.env.NODE_ENV === "production" && "serviceWorker" in navigator && window.isSecureContext) {
      void navigator.serviceWorker.register("/sw.js", { scope: "/", updateViaCache: "none" }).catch(() => {
        // The web flow remains available when registration is unsupported/blocked.
        // Do not log request data or repeatedly reload to try to repair it.
      });
    }
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  return offline ? <div className="pwa-connection" role="status">اینترنت قطع شده؛ ورود، پرداخت و ارسال به اتصال نیاز دارند. درخواست‌ها خودکار تکرار نمی‌شوند.</div> : null;
}
