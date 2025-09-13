'use client';

import { useState } from 'react';
import { useLocale } from '@/providers/LocaleProvider';
import { locales, localeNames, type Locale } from '@/i18n/config';
import { ChevronDown, Globe } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function LanguageSelector() {
  const { locale, setLocale } = useLocale();
  const [isOpen, setIsOpen] = useState(false);

  const handleLocaleChange = (newLocale: Locale) => {
    setLocale(newLocale);
    setIsOpen(false);
  };

  return (
    <div className="relative">
      <Button
        variant="outline"
        size="sm"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-2 text-sm bg-white/10 border-white/20 hover:bg-white/20 text-white"
      >
        <Globe className="h-4 w-4" />
        <span className="font-medium">{localeNames[locale]}</span>
        <ChevronDown className={`h-3 w-3 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </Button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />

          {/* Dropdown */}
          <div className="absolute top-full left-0 mt-1 z-20 min-w-[140px] bg-gray-800 border border-white/20 rounded-md shadow-lg overflow-hidden">
            {locales.map((loc) => (
              <button
                key={loc}
                onClick={() => handleLocaleChange(loc)}
                className={`
                  w-full px-4 py-2 text-left text-sm hover:bg-white/10 transition-colors
                  ${locale === loc ? 'bg-white/10 text-white' : 'text-gray-300'}
                  ${loc === 'hi' ? 'font-hindi' : ''}
                  ${loc === 'bn' ? 'font-bengali' : ''}
                `}
              >
                <div className="flex items-center gap-2">
                  <span className="font-medium">{localeNames[loc]}</span>
                  {locale === loc && (
                    <span className="text-xs text-green-400">✓</span>
                  )}
                </div>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// Language display names with proper scripts
export const LanguageDisplay = ({ locale: displayLocale }: { locale?: Locale }) => {
  const currentLocale = displayLocale || 'en';

  return (
    <span className={`
      ${currentLocale === 'hi' ? 'font-hindi' : ''}
      ${currentLocale === 'bn' ? 'font-bengali' : ''}
    `}>
      {localeNames[currentLocale]}
    </span>
  );
};