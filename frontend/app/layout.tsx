import type { Metadata, Viewport } from "next";
import { headers } from "next/headers";
import "@fontsource/vazirmatn/400.css";
import "@fontsource/vazirmatn/500.css";
import "@fontsource/vazirmatn/600.css";
import "@fontsource/vazirmatn/700.css";
import "./globals.css";
import "./theme.css";
import { ThemeProvider } from "@/components/theme-provider";
import { THEME_INIT_SCRIPT } from "@/lib/theme";
import { AppProvider } from "@/components/app-provider";
import { Header, Footer, MobileNav, SkipToContent } from "@/components/chrome";

import { SupportWidget } from "@/components/support-widget";
import { PWAFoundation } from "@/components/pwa-foundation";
import { rootMetadata } from "@/lib/seo";
import { monitoringTvRenderHeader } from "@/lib/security";

export const metadata: Metadata = rootMetadata();
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  // Reading request headers opts every HTML page into dynamic rendering, so
  // Next applies the current CSP nonce instead of reusing a cached document.
  const requestHeaders = await headers();
  if (requestHeaders.get(monitoringTvRenderHeader) === "1") {
    return <html lang="fa" dir="rtl" data-theme="dark"><body>{children}</body></html>;
  }
  const nonce = requestHeaders.get("x-nonce") ?? undefined;
  return (
    <html lang="fa" dir="rtl" data-theme="light" suppressHydrationWarning>
      <head>
        <script id="theme-init" nonce={nonce} dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body>
        <SkipToContent />
        <ThemeProvider>
          <AppProvider>
            <PWAFoundation />
            <Header />
            <main id="main-content" tabIndex={-1}>{children}</main>
            <Footer />
            <MobileNav />
            <SupportWidget />
          </AppProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
