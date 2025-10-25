"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  ReactNode,
} from "react";
import { NextIntlClientProvider } from "next-intl";
import { type Locale } from "@/i18n/config";
import { getLocaleFromStorage, setLocaleInStorage } from "@/lib/locale";

interface LocaleContextType {
  locale: Locale;
  setLocale: (locale: Locale) => void;
}

const LocaleContext = createContext<LocaleContextType | undefined>(undefined);

interface LocaleProviderProps {
  children: ReactNode;
  initialLocale?: Locale;
  initialMessages?: Record<string, unknown>;
}

export function LocaleProvider({
  children,
  initialLocale = "en",
  initialMessages = {},
}: LocaleProviderProps) {
  const [locale, setLocaleState] = useState<Locale>(initialLocale);
  const [messages, setMessages] = useState(initialMessages);

  useEffect(() => {
    // Get locale from storage on client side
    const storedLocale = getLocaleFromStorage();
    if (storedLocale !== locale) {
      setLocaleState(storedLocale);
      loadMessages(storedLocale);
    }
  }, [locale]);

  const loadMessages = async (newLocale: Locale) => {
    try {
      const newMessages = await import(`../../messages/${newLocale}.json`);
      setMessages(newMessages.default);
    } catch (error) {
      console.error(`Failed to load messages for locale ${newLocale}:`, error);
      // Fallback to English
      if (newLocale !== "en") {
        const fallbackMessages = await import(`../../messages/en.json`);
        setMessages(fallbackMessages.default);
      }
    }
  };

  const setLocale = async (newLocale: Locale) => {
    setLocaleState(newLocale);
    setLocaleInStorage(newLocale);
    await loadMessages(newLocale);
  };

  const contextValue: LocaleContextType = {
    locale,
    setLocale,
  };

  return (
    <LocaleContext.Provider value={contextValue}>
      <NextIntlClientProvider
        messages={messages}
        locale={locale}
        timeZone="Asia/Kolkata"
      >
        {children}
      </NextIntlClientProvider>
    </LocaleContext.Provider>
  );
}

export function useLocale() {
  const context = useContext(LocaleContext);
  if (context === undefined) {
    throw new Error("useLocale must be used within a LocaleProvider");
  }
  return context;
}
