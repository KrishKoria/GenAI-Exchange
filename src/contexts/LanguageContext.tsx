"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from "react";
import { type Locale } from "@/i18n/config";

interface LanguageContextType {
  viewingLanguage: Locale;
  setViewingLanguage: (lang: Locale) => void;
  availableLanguages: Set<Locale>;
  addAvailableLanguage: (lang: Locale) => void;
  resetAvailableLanguages: () => void;
}

const LanguageContext = createContext<LanguageContextType | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [viewingLanguage, setViewingLanguage] = useState<Locale>("en");
  const [availableLanguages, setAvailableLanguages] = useState<Set<Locale>>(
    new Set(["en"])
  );

  // Reset to English when available languages change
  useEffect(() => {
    if (!availableLanguages.has(viewingLanguage)) {
      setViewingLanguage("en");
    }
  }, [availableLanguages, viewingLanguage]);

  // Memoize to prevent infinite loops in consuming components
  const addAvailableLanguage = useCallback((lang: Locale) => {
    setAvailableLanguages((prev) => {
      if (prev.has(lang)) return prev; // Prevent unnecessary state update
      return new Set(prev).add(lang);
    });
  }, []);

  // Memoize to prevent infinite loops in consuming components
  const resetAvailableLanguages = useCallback(() => {
    setAvailableLanguages(new Set(["en"]));
    setViewingLanguage("en");
  }, []);

  return (
    <LanguageContext.Provider
      value={{
        viewingLanguage,
        setViewingLanguage,
        availableLanguages,
        addAvailableLanguage,
        resetAvailableLanguages,
      }}
    >
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useLanguage must be used within LanguageProvider");
  }
  return context;
}
