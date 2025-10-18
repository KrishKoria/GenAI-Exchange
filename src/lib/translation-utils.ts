import { type Locale } from "@/i18n/config";

/**
 * Get the appropriate text based on the selected viewing language.
 *
 * @param originalText - The original English text
 * @param translations - Record of translations { hi: "...", bn: "...", etc. }
 * @param targetLanguage - The language to display
 * @returns The translated text if available, otherwise the original text
 */
export function getTranslatedText(
  originalText: string,
  translations: Record<string, string> | undefined | null,
  targetLanguage: Locale
): string {
  // If viewing in English or no translations available, return original
  if (targetLanguage === "en" || !translations) {
    return originalText;
  }

  // Return translation if available, otherwise fall back to original
  return translations[targetLanguage] || originalText;
}

/**
 * Check if translations are available for a specific language.
 *
 * @param translations - Record of translations
 * @param language - The language to check
 * @returns True if translation exists for the language
 */
export function hasTranslation(
  translations: Record<string, string> | undefined | null,
  language: Locale
): boolean {
  if (!translations || language === "en") {
    return language === "en"; // English is always "available" (original text)
  }
  return !!translations[language];
}

/**
 * Get all available languages from translations.
 *
 * @param translations - Record of translations
 * @returns Set of available language codes (always includes "en")
 */
export function getAvailableLanguages(
  translations: Record<string, string> | undefined | null
): Set<Locale> {
  const languages = new Set<Locale>(["en"]);

  if (translations) {
    Object.keys(translations).forEach((lang) => {
      languages.add(lang as Locale);
    });
  }

  return languages;
}
