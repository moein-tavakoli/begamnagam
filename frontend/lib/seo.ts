import type { Metadata, MetadataRoute } from "next";
import { isIP } from "node:net";

export const siteName = "بگم نگم";
export const socialImage = {
  url: "/images/social-card.png",
  width: 1200,
  height: 630,
  alt: "بگم نگم؛ تشکر، دلگرمی و یادآوری محترمانه",
};

export const publicPages = {
  "/": {
    title: "بگم نگم | پیام محترمانه بدون نمایش هویت فرستنده",
    description:
      "با بگم نگم، تشکر، دلگرمی و یادآوری دوستانه را با پیامک و بدون نمایش هویت فرستنده به گیرنده برسان. متن نهایی را بررسی کن؛ ۳ ارسال اول هدیه است.",
  },
  "/help": {
    title: "راهنمای ارسال پیام محترمانه و هزینه‌ها",
    description:
      "راهنمای بگم نگم: نوشتن پیام محترمانه، بررسی متن پیش از ارسال، ۳ ارسال هدیه، محدودیت‌های ناشناس‌بودن، قطع دریافت و پاسخ به سؤال‌های رایج.",
  },
  "/privacy": {
    title: "حریم خصوصی و قوانین استفاده",
    description:
      "حریم خصوصی بگم نگم؛ نحوه پردازش و نگهداری داده‌ها، حفاظت از هویت فرستنده، پیام‌های مجاز، حق قطع دریافت و درخواست حذف اطلاعات.",
  },
} as const;

export type PublicPath = keyof typeof publicPages;
type SeoEnvironment = { [key: string]: string | undefined; APP_BASE_URL?: string; SEO_INDEXABLE?: string };

// Use trusted configuration, never the request Host or a recipient's token URL.
export function getSeoConfig(env: SeoEnvironment = process.env) {
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

export function publicMetadata(path: PublicPath, env: SeoEnvironment = process.env): Metadata {
  const { baseUrl, indexable } = getSeoConfig(env);
  const page = publicPages[path];
  const title = path === "/" ? page.title : `${page.title} | ${siteName}`;
  return {
    title: { absolute: title },
    description: page.description,
    alternates: { canonical: new URL(path, baseUrl).href },
    robots: indexable
      ? { index: true, follow: true, googleBot: { index: true, follow: true, "max-image-preview": "large", "max-snippet": -1, "max-video-preview": -1 } }
      : { index: false, follow: false },
    openGraph: {
      type: "website", locale: "fa_IR", siteName,
      url: new URL(path, baseUrl).href, title, description: page.description,
      images: [{ ...socialImage, url: new URL(socialImage.url, baseUrl).href }],
    },
    twitter: {
      card: "summary_large_image", title, description: page.description,
      images: [{ url: new URL(socialImage.url, baseUrl).href, alt: socialImage.alt }],
    },
  };
}

export function privateMetadata(title: string): Metadata {
  return {
    title,
    robots: { index: false, follow: false, noarchive: true, nosnippet: true },
    referrer: "no-referrer",
  };
}

export function sitemapEntries(env: SeoEnvironment = process.env): MetadataRoute.Sitemap {
  const { baseUrl, indexable } = getSeoConfig(env);
  if (!indexable) return [];
  // No invented lastModified dates, query parameters, fragments or account URLs.
  return (Object.keys(publicPages) as PublicPath[]).map(path => ({
    url: new URL(path, baseUrl).href,
  }));
}

export function robotsRules(env: SeoEnvironment = process.env): MetadataRoute.Robots {
  const { baseUrl, indexable } = getSeoConfig(env);
  return {
    // Allow HTML crawling so crawlers can read noindex, including on private pages.
    rules: { userAgent: "*", allow: "/", disallow: ["/api/", "/admin/", "/static/admin/"] },
    ...(indexable ? { sitemap: new URL("/sitemap.xml", baseUrl).href } : {}),
  };
}

export function serializeJsonLd(data: unknown) {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}

type Question = { question: string; answer: string };

export function pageJsonLd(path: PublicPath, questions: readonly Question[] = [], env: SeoEnvironment = process.env) {
  const { baseUrl } = getSeoConfig(env);
  const page = publicPages[path];
  const url = new URL(path, baseUrl).href;
  const websiteId = new URL("/#website", baseUrl).href;
  const pageId = `${url}#webpage`;
  const breadcrumbId = `${url}#breadcrumb`;
  const applicationId = new URL("/#application", baseUrl).href;
  const graph: Record<string, unknown>[] = [
    {
      "@type": "WebSite", "@id": websiteId, url: baseUrl.href,
      name: siteName, alternateName: "BegamNagam", inLanguage: "fa-IR",
    },
    {
      "@type": questions.length ? "FAQPage" : "WebPage", "@id": pageId,
      url, name: page.title, description: page.description, inLanguage: "fa-IR",
      isPartOf: { "@id": websiteId },
      ...(path !== "/" ? { breadcrumb: { "@id": breadcrumbId } } : {}),
      ...(path === "/" ? { mainEntity: { "@id": applicationId } } : {}),
      ...(questions.length ? {
        mainEntity: questions.map(({ question, answer }) => ({
          "@type": "Question", name: question,
          acceptedAnswer: { "@type": "Answer", text: answer },
        })),
      } : {}),
    },
  ];
  if (path === "/") {
    graph.push({
      "@type": "WebApplication", "@id": applicationId,
      name: siteName, url, description: page.description, inLanguage: "fa-IR",
      applicationCategory: "LifestyleApplication", operatingSystem: "Web",
      browserRequirements: "Requires JavaScript and an internet connection",
      image: new URL(socialImage.url, baseUrl).href,
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
