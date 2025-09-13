'use client';

import { type Locale, locales } from '@/i18n/config';

const LOCALE_COOKIE_NAME = 'NEXT_LOCALE';

export function getLocaleFromStorage(): Locale {
  if (typeof window === 'undefined') return 'en';

  try {
    // Try localStorage first
    const stored = localStorage.getItem(LOCALE_COOKIE_NAME);
    if (stored && locales.includes(stored as Locale)) {
      return stored as Locale;
    }

    // Fallback to browser language detection
    const browserLang = navigator.language.split('-')[0];
    if (locales.includes(browserLang as Locale)) {
      return browserLang as Locale;
    }
  } catch (error) {
    console.warn('Failed to get locale from storage:', error);
  }

  return 'en';
}

export function setLocaleInStorage(locale: Locale): void {
  if (typeof window === 'undefined') return;

  try {
    localStorage.setItem(LOCALE_COOKIE_NAME, locale);
    // Also set a cookie for SSR
    document.cookie = `${LOCALE_COOKIE_NAME}=${locale}; path=/; max-age=31536000; SameSite=Lax`;
  } catch (error) {
    console.warn('Failed to set locale in storage:', error);
  }
}

export function getLocaleFromCookie(cookieString?: string): Locale {
  // Server-safe version - can be called from server or client
  if (typeof window !== 'undefined' && !cookieString) {
    cookieString = document.cookie;
  }

  if (!cookieString) return 'en';

  try {
    const cookies = cookieString.split(';').reduce((acc, cookie) => {
      const [key, value] = cookie.trim().split('=');
      acc[key] = value;
      return acc;
    }, {} as Record<string, string>);

    const locale = cookies[LOCALE_COOKIE_NAME];
    if (locale && locales.includes(locale as Locale)) {
      return locale as Locale;
    }
  } catch (error) {
    console.warn('Failed to parse locale from cookie:', error);
  }

  return 'en';
}

// Server-safe function for getting locale from cookie string
export function getServerLocaleFromCookie(cookieString: string): Locale {
  if (!cookieString) return 'en';

  try {
    const cookies = cookieString.split(';').reduce((acc, cookie) => {
      const [key, value] = cookie.trim().split('=');
      acc[key] = value;
      return acc;
    }, {} as Record<string, string>);

    const locale = cookies[LOCALE_COOKIE_NAME];
    if (locale && locales.includes(locale as Locale)) {
      return locale as Locale;
    }
  } catch (error) {
    console.warn('Failed to parse locale from cookie:', error);
  }

  return 'en';
}