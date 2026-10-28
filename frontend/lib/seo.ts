import type { Metadata, MetadataRoute } from "next";
import { isIP } from "node:net";

export const siteName = "بگم نگم";
export const siteAlternateName = "BegamNagam";
export const siteDescription =
  "ارسال پیامک برای تشکر، دلگرمی و یادآوری محترمانه، بدون نمایش نام و شمارهٔ فرستنده به گیرنده؛ با بررسی متن پیش از ارسال و امکان قطع دریافت.";
export const socialImage = {
  url: "/images/social-card.png",
  width: 1200,
  height: 630,
  alt: "بگم نگم؛ تشکر، دلگرمی و یادآوری محترمانه",
  type: "image/png",
};
export const siteLogo = { url: "/icons/icon-512.png", width: 512, height: 512 };

export const publicPages = {
  "/": {
    title: "بگم نگم | ارسال پیامک ناشناس و محترمانه",
    description:
      "با بگم نگم، تشکر، دلگرمی و یادآوری دوستانه را با پیامک و بدون نمایش هویت فرستنده به گیرنده برسان. متن نهایی را بررسی کن؛ ۳ ارسال اول هدیه است.",
  },
  "/help": {
    title: "راهنمای ارسال پیامک ناشناس و پرسش‌های متداول",
    description:
      "راهنمای بگم نگم: نوشتن پیام محترمانه، بررسی متن پیش از ارسال، ۳ ارسال هدیه، محدودیت‌های ناشناس‌بودن، قطع دریافت و پاسخ به سؤال‌های رایج.",
  },
  "/privacy": {
    title: "حریم خصوصی و قوانین استفاده",
    description:
      "حریم خصوصی بگم نگم؛ نحوه پردازش و نگهداری داده‌ها، حفاظت از هویت فرستنده، پیام‌های مجاز، حق قطع دریافت و درخواست حذف اطلاعات.",
  },
  "/links": {
    title: "سایت و شبکه‌های اجتماعی بگم نگم",
    description: "همهٔ لینک‌های بگم نگم در یک صفحه؛ سایت، اینستاگرام، تلگرام، بله، سروش و گپ.",
  },
} as const;

export type PublicPath = keyof typeof publicPages;
export const privatePages = {
  "/wallet": { title: "کیف پول من", description: "موجودی و گردش اعتبار غیرقابل برداشت حساب بگم نگم؛ نیازمند ورود با شمارهٔ تأییدشده." },
  "/credits": { title: "خرید بستهٔ پیام", description: "بسته‌های فعال پیام و اعتبار حساب خودت؛ نیازمند ورود با شمارهٔ تأییدشده." },
  "/manage": {
    title: "مدیریت بگم نگم",
    description: "پنل مدیریت؛ نیازمند حساب مدیر و مجوز دسترسی.",
  },
  "/profile": {
    title: "پروفایل من",
    description: "ورود با شمارهٔ تأییدشده، مشاهدهٔ اطلاعات حساب بگم نگم و مدیریت نشست خودت.",
  },
  "/history": {
    title: "پیام‌های من",
    description: "مشاهدهٔ سابقه، رسید و وضعیت پردازش پیام‌های حساب خودت در بگم نگم؛ نیازمند ورود با شمارهٔ تأییدشده.",
  },
  "/invitations": {
    title: "دعوت دوستان",
    description: "مدیریت دعوت آشنایان، مشاهدهٔ نتیجهٔ دعوت‌های خودت و پیگیری ارسال‌های جایزه در حساب بگم نگم.",
  },
  "/preferences": {
    title: "مدیریت دریافت پیام",
    description: "با تأیید شمارهٔ خودت، دریافت پیام‌های بگم نگم را متوقف یا دوباره فعال کن و درخواست حذف اطلاعات ثبت کن.",
  },
  "/r": {
    title: "مدیریت پیام دریافتی",
    description: "مدیریت دریافت یا گزارش پیام بگم نگم با لینک خصوصی داخل پیامک؛ این لینک را برای دیگران نفرست.",
  },
} as const;
export type PrivatePath = keyof typeof privatePages;
type SeoEnvironment = { [key: string]: string | undefined; APP_BASE_URL?: string; SEO_INDEXABLE?: string };
// Direct references let Next inline the two public, reviewed build settings.
function defaultEnvironment(): SeoEnvironment {
  return { APP_BASE_URL: process.env.APP_BASE_URL, SEO_INDEXABLE: process.env.SEO_INDEXABLE };
}

// Use trusted configuration, never the request Host or a recipient's token URL.
export function getSeoConfig(env: SeoEnvironment = defaultEnvironment()) {
  const url = new URL(env.APP_BASE_URL || "http://localhost:3000");
  if (
    !["http:", "https:"].includes(url.protocol) || url.username || url.password ||
    url.pathname !== "/" || url.search || url.hash
  ) {
    throw new Error("APP_BASE_URL must be an HTTP(S) origin without credentials, path, query or fragment.");
  }
  // A terminal DNS dot is equivalent to the bare hostname, including localhost.
  url.hostname = url.hostname.replace(/\.$/, "");
  const hostname = url.hostname.replace(/^\[|\]$/g, "");
  const publicHost = hostname.includes(".") && !isIP(hostname) &&
    !/(^|\.)(localhost|local|internal|test|example|invalid)$/.test(hostname);
  const indexable = env.SEO_INDEXABLE === "1";
  if (indexable && (url.protocol !== "https:" || !publicHost)) {
    throw new Error("SEO_INDEXABLE=1 requires a public HTTPS domain in APP_BASE_URL.");
  }
  return { baseUrl: url, indexable };
}

// Keep public canonical/social metadata out of the root: private and error
// routes inherit it too. Public pages opt in explicitly below.
export function rootMetadata(env: SeoEnvironment = defaultEnvironment()): Metadata {
  return {
    metadataBase: getSeoConfig(env).baseUrl,
    title: { default: publicPages["/"].title, template: `%s | ${siteName}` },
    description: siteDescription,
    applicationName: siteName,
    manifest: "/manifest.webmanifest",
    icons: {
      icon: [
        { url: "/icon.svg", type: "image/svg+xml", sizes: "any" },
        { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
        { url: siteLogo.url, sizes: "512x512", type: "image/png" },
      ],
      apple: [{ url: "/icons/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
    },
    appleWebApp: { capable: true, statusBarStyle: "default", title: siteName },
    referrer: "no-referrer",
    formatDetection: { telephone: false, email: false, address: false },
    robots: { index: false, follow: false },
  };
}

export function publicMetadata(path: PublicPath, env: SeoEnvironment = defaultEnvironment()): Metadata {
  const { baseUrl, indexable } = getSeoConfig(env);
  const page = publicPages[path];
  const title = path === "/" ? page.title : `${page.title} | ${siteName}`;
  const imageUrl = new URL(socialImage.url, baseUrl).href;
  return {
    title: { absolute: title },
    description: page.description,
    authors: [{ name: siteName, url: baseUrl.href }],
    creator: siteName,
    publisher: siteName,
    category: "ارتباطات و پیامک",
    alternates: { canonical: new URL(path, baseUrl).href },
    robots: indexable
      ? { index: true, follow: true, googleBot: { index: true, follow: true, "max-image-preview": "large", "max-snippet": -1, "max-video-preview": -1 } }
      : { index: false, follow: false },
    openGraph: {
      type: "website", locale: "fa_IR", siteName,
      url: new URL(path, baseUrl).href, title, description: page.description,
      images: [{
        ...socialImage, url: imageUrl,
        ...(baseUrl.protocol === "https:" ? { secureUrl: imageUrl } : {}),
      }],
    },
    twitter: {
      card: "summary_large_image", title, description: page.description,
      images: [{ url: imageUrl, alt: socialImage.alt }],
    },
  };
}

export function privateMetadata(path: PrivatePath): Metadata {
  const { title, description } = privatePages[path];
  return {
    title,
    description,
    robots: {
      index: false, follow: false, noarchive: true, nosnippet: true,
      googleBot: { index: false, follow: false, noimageindex: true, nosnippet: true },
    },
    // Explicitly clear these if a parent ever adds public defaults.
    alternates: null,
    openGraph: null,
    twitter: null,
    referrer: "no-referrer",
  };
}

export function sitemapEntries(env: SeoEnvironment = defaultEnvironment()): MetadataRoute.Sitemap {
  const { baseUrl, indexable } = getSeoConfig(env);
  if (!indexable) return [];
  // No invented lastModified dates, query parameters, fragments or account URLs.
  return (Object.keys(publicPages) as PublicPath[]).map(path => ({
    url: new URL(path, baseUrl).href,
  }));
}

export function robotsRules(env: SeoEnvironment = defaultEnvironment()): MetadataRoute.Robots {
  const { baseUrl, indexable } = getSeoConfig(env);
  return {
    // Allow HTML crawling so crawlers can read noindex, including on private pages.
    rules: { userAgent: "*", allow: "/", disallow: ["/api/", "/admin/", "/manage", "/static/admin/"] },
    ...(indexable ? { sitemap: new URL("/sitemap.xml", baseUrl).href } : {}),
  };
}

export function serializeJsonLd(data: unknown) {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}

type Question = { id: string; question: string; answer: string };

export function pageJsonLd(path: PublicPath, questions: readonly Question[] = [], env: SeoEnvironment = defaultEnvironment()) {
  const { baseUrl } = getSeoConfig(env);
  const page = publicPages[path];
  const url = new URL(path, baseUrl).href;
  const websiteId = new URL("/#website", baseUrl).href;
  const pageId = `${url}#webpage`;
  const breadcrumbId = `${url}#breadcrumb`;
  const applicationId = new URL("/#application", baseUrl).href;
  const organizationId = new URL("/#organization", baseUrl).href;
  const logoId = new URL("/#logo", baseUrl).href;
  const imageId = new URL("/#primaryimage", baseUrl).href;
  const serviceId = new URL("/#service", baseUrl).href;
  const faq = path === "/help" ? questions : [];
  const graph: Record<string, unknown>[] = [
    {
      // This names the service brand, not a legal company or physical business.
      "@type": "Organization", "@id": organizationId,
      name: siteName, alternateName: siteAlternateName, url: baseUrl.href,
      description: siteDescription,
      logo: { "@id": logoId }, image: { "@id": imageId },
    },
    {
      "@type": "ImageObject", "@id": logoId,
      url: new URL(siteLogo.url, baseUrl).href,
      contentUrl: new URL(siteLogo.url, baseUrl).href,
      width: siteLogo.width, height: siteLogo.height,
      encodingFormat: "image/png", caption: `نشان ${siteName}`,
    },
    {
      "@type": "ImageObject", "@id": imageId,
      url: new URL(socialImage.url, baseUrl).href,
      contentUrl: new URL(socialImage.url, baseUrl).href,
      width: socialImage.width, height: socialImage.height,
      encodingFormat: socialImage.type, caption: socialImage.alt, inLanguage: "fa-IR",
    },
    {
      "@type": "WebSite", "@id": websiteId, url: baseUrl.href,
      name: siteName, alternateName: siteAlternateName, inLanguage: "fa-IR",
      description: siteDescription, publisher: { "@id": organizationId },
      image: { "@id": imageId },
    },
    {
      "@type": faq.length ? "FAQPage" : "WebPage", "@id": pageId,
      url, name: page.title, description: page.description, inLanguage: "fa-IR",
      isPartOf: { "@id": websiteId },
      publisher: { "@id": organizationId },
      primaryImageOfPage: { "@id": imageId },
      image: { "@id": imageId },
      about: { "@id": path === "/" ? serviceId : organizationId },
      relatedLink: (Object.keys(publicPages) as PublicPath[])
        .filter(otherPath => otherPath !== path).map(otherPath => new URL(otherPath, baseUrl).href),
      ...(path !== "/" ? { breadcrumb: { "@id": breadcrumbId } } : {}),
      ...(path === "/" ? { mainEntity: { "@id": applicationId } } : {}),
      ...(faq.length ? {
        mainEntity: faq.map(({ id, question, answer }) => ({
          "@type": "Question", "@id": `${url}#${id}`, name: question,
          acceptedAnswer: { "@type": "Answer", "@id": `${url}#${id}-answer`, text: answer },
        })),
      } : {}),
    },
  ];
  if (path === "/") {
    graph.push({
      "@type": "WebApplication", "@id": applicationId,
      name: siteName, url, description: page.description, inLanguage: "fa-IR",
      alternateName: siteAlternateName,
      applicationCategory: "LifestyleApplication", operatingSystem: "Web",
      applicationSubCategory: "ارسال پیامک محترمانه",
      browserRequirements: "مرورگر به‌روز، جاوااسکریپت فعال و اتصال به اینترنت",
      countriesSupported: "IR",
      publisher: { "@id": organizationId },
      mainEntityOfPage: { "@id": pageId },
      image: { "@id": imageId },
      softwareHelp: { "@type": "WebPage", "@id": new URL("/help#webpage", baseUrl).href },
      featureList: [
        "ارسال پیامک بدون نمایش نام و شمارهٔ فرستنده به گیرنده",
        "بررسی متن نهایی پیش از تأیید ارسال",
        "ورود با کد تأیید شمارهٔ همراه",
        "امکان قطع دریافت و گزارش پیام توسط گیرنده",
        "پیگیری وضعیت پیام در حساب فرستنده",
      ],
    });
    graph.push({
      "@type": "Service", "@id": serviceId,
      name: "ارسال پیامک محترمانه بگم نگم", url,
      description: siteDescription, serviceType: "ارسال پیامک تشکر، دلگرمی و یادآوری محترمانه",
      provider: { "@id": organizationId },
      areaServed: { "@type": "Country", name: "ایران", identifier: "IR" },
      image: { "@id": imageId },
      availableChannel: {
        "@type": "ServiceChannel", serviceUrl: new URL("/#compose", baseUrl).href,
        availableLanguage: "fa-IR",
      },
    });
  } else {
    graph.push({
      "@type": "BreadcrumbList", "@id": breadcrumbId,
      itemListElement: [
        { "@type": "ListItem", position: 1, name: siteName, item: baseUrl.href },
        { "@type": "ListItem", position: 2, name: page.title, item: url },
      ],
    });
  }
  return { "@context": "https://schema.org", "@graph": graph };
}
