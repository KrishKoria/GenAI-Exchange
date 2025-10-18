import { notFound } from "next/navigation";
import { getRequestConfig } from "next-intl/server";

// All supported languages matching backend SupportedLanguage enum
export const locales = [
  "en",
  "hi",
  "bn",
  "ta",
  "te",
  "mr",
  "gu",
  "kn",
  "ml",
  "pa",
  "ur",
] as const;
export type Locale = (typeof locales)[number];

export const localeNames: Record<Locale, string> = {
  en: "English",
  hi: "हिन्दी",
  bn: "বাংলা",
  ta: "தமிழ்",
  te: "తెలుగు",
  mr: "मराठी",
  gu: "ગુજરાતી",
  kn: "ಕನ್ನಡ",
  ml: "മലയാളം",
  pa: "ਪੰਜਾਬੀ",
  ur: "اردو",
};

export const localeDirection: Record<Locale, "ltr" | "rtl"> = {
  en: "ltr",
  hi: "ltr",
  bn: "ltr",
  ta: "ltr",
  te: "ltr",
  mr: "ltr",
  gu: "ltr",
  kn: "ltr",
  ml: "ltr",
  pa: "ltr",
  ur: "rtl", // Urdu is RTL
};

export default getRequestConfig(async ({ locale }) => {
  // Validate that the incoming `locale` parameter is valid
  if (!locales.includes(locale as Locale)) notFound();

  return {
    locale: locale as string,
    messages: (await import(`../../messages/${locale}.json`)).default,
    timeZone: "Asia/Kolkata", // Default to Indian Standard Time for Indian language support
    now: new Date(),
  };
});
