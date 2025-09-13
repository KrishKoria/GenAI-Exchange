import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { QueryProvider } from "@/providers/QueryProvider";
import { LocaleProvider } from "@/providers/LocaleProvider";
import { cookies } from "next/headers";
import { type Locale, locales } from "@/i18n/config";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "LegalEase AI - Legal Document Analysis",
  description: "AI-powered legal document analysis with risk assessment and plain-language summaries",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Get locale from cookies using Next.js 15 approach
  const cookieStore = await cookies();
  const localeCookie = cookieStore.get('NEXT_LOCALE');
  const initialLocale: Locale = (localeCookie?.value && locales.includes(localeCookie.value as Locale))
    ? localeCookie.value as Locale
    : 'en';

  // Load initial messages for SSR
  let initialMessages = {};
  try {
    initialMessages = (await import(`../../messages/${initialLocale}.json`)).default;
  } catch (error) {
    console.warn(`Failed to load messages for ${initialLocale}, falling back to English`);
    initialMessages = (await import(`../../messages/en.json`)).default;
  }

  return (
    <html lang={initialLocale}>
      <head>
        {/* Google Fonts for Indian Languages */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Noto+Sans+Devanagari:wght@400;500;600;700&family=Noto+Sans+Bengali:wght@400;500;600;700&family=Noto+Sans+Tamil:wght@400;500;600;700&family=Noto+Sans+Telugu:wght@400;500;600;700&family=Noto+Sans+Gujarati:wght@400;500;600;700&family=Noto+Sans+Kannada:wght@400;500;600;700&family=Noto+Sans+Malayalam:wght@400;500;600;700&family=Noto+Sans+Gurmukhi:wght@400;500;600;700&family=Noto+Nastaliq+Urdu:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <LocaleProvider initialLocale={initialLocale} initialMessages={initialMessages}>
          <QueryProvider>{children}</QueryProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}
