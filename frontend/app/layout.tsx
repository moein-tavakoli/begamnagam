import type { Metadata, Viewport } from "next";
import "@fontsource/vazirmatn/400.css";
import "@fontsource/vazirmatn/500.css";
import "@fontsource/vazirmatn/600.css";
import "@fontsource/vazirmatn/700.css";
import "./globals.css";
import { AppProvider } from "@/components/app-provider";
import { Header, Footer, MobileNav } from "@/components/chrome";

import { PWAFoundation } from "@/components/pwa-foundation";

export const metadata: Metadata = {
  title: {
    default: "بگم نگم | حرفت رو مهربون‌تر برسون",
    template: "%s | بگم نگم",
  },
  description:
    "بازخورد محترمانه با پیامک، بدون نمایش هویت فرستنده به گیرنده. متن نهایی را قبل از ارسال ببین و حق قطع دریافت را به گیرنده بده.",
  applicationName: "بگم نگم",
  manifest: "/manifest.webmanifest",
  icons: { icon: [{ url: "/icon.svg", type: "image/svg+xml" }, { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" }], apple: "/icons/apple-touch-icon.png" },
  appleWebApp: { capable: true, statusBarStyle: "default", title: "بگم نگم" },
  robots: { index: false, follow: false },
};
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#f2eeff",
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fa" dir="rtl">
      <body>
        <a className="skip-link" href="#main-content">
          رفتن به محتوای اصلی
        </a>
        <AppProvider>
          <PWAFoundation />
          <Header />
          <main id="main-content">{children}</main>
          <Footer />
          <MobileNav />
        </AppProvider>
      </body>
    </html>
  );
}
