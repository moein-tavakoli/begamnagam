import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";
import "@fontsource/vazirmatn/400.css";
import "@fontsource/vazirmatn/500.css";
import "@fontsource/vazirmatn/600.css";
import "@fontsource/vazirmatn/700.css";
import "./globals.css";
import { AppProvider } from "@/components/app-provider";
import { Header, Footer, MobileNav } from "@/components/chrome";

import { PWAFoundation } from "@/components/pwa-foundation";
import { rootMetadata } from "@/lib/seo";

export const metadata: Metadata = rootMetadata();
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#f2eeff",
  viewportFit: "cover",
};

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  // Reading request headers opts every HTML page into dynamic rendering, so
  // Next applies the current CSP nonce instead of reusing a cached document.
  await headers();
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
