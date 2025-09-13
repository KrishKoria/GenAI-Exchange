// For now, we'll use CSS custom properties and web fonts loaded via link tags
// This is more compatible with Tailwind CSS v4 and avoids build issues

export const fontConfig = {
  // Font families for different scripts - loaded via HTML link tags
  devanagari: '"Noto Sans Devanagari", system-ui, -apple-system, sans-serif',
  bengali: '"Noto Sans Bengali", system-ui, -apple-system, sans-serif',
  tamil: '"Noto Sans Tamil", system-ui, -apple-system, sans-serif',
  telugu: '"Noto Sans Telugu", system-ui, -apple-system, sans-serif',
  gujarati: '"Noto Sans Gujarati", system-ui, -apple-system, sans-serif',
  kannada: '"Noto Sans Kannada", system-ui, -apple-system, sans-serif',
  malayalam: '"Noto Sans Malayalam", system-ui, -apple-system, sans-serif',
  punjabi: '"Noto Sans Gurmukhi", system-ui, -apple-system, sans-serif',
  urdu: '"Noto Nastaliq Urdu", system-ui, -apple-system, sans-serif',
  fallback: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
};

// Helper function to get appropriate font family for locale
export function getFontFamily(locale: string): string {
  switch (locale) {
    case 'hi':
    case 'mr': // Marathi also uses Devanagari
      return fontConfig.devanagari;
    case 'bn':
      return fontConfig.bengali;
    case 'ta':
      return fontConfig.tamil;
    case 'te':
      return fontConfig.telugu;
    case 'gu':
      return fontConfig.gujarati;
    case 'kn':
      return fontConfig.kannada;
    case 'ml':
      return fontConfig.malayalam;
    case 'pa':
      return fontConfig.punjabi;
    case 'ur':
      return fontConfig.urdu;
    default:
      return fontConfig.fallback;
  }
}

// Google Fonts URLs for dynamic loading
export const fontUrls = {
  devanagari: 'https://fonts.googleapis.com/css2?family=Noto+Sans+Devanagari:wght@400;500;600;700&display=swap',
  bengali: 'https://fonts.googleapis.com/css2?family=Noto+Sans+Bengali:wght@400;500;600;700&display=swap',
  tamil: 'https://fonts.googleapis.com/css2?family=Noto+Sans+Tamil:wght@400;500;600;700&display=swap',
  telugu: 'https://fonts.googleapis.com/css2?family=Noto+Sans+Telugu:wght@400;500;600;700&display=swap',
  gujarati: 'https://fonts.googleapis.com/css2?family=Noto+Sans+Gujarati:wght@400;500;600;700&display=swap',
  kannada: 'https://fonts.googleapis.com/css2?family=Noto+Sans+Kannada:wght@400;500;600;700&display=swap',
  malayalam: 'https://fonts.googleapis.com/css2?family=Noto+Sans+Malayalam:wght@400;500;600;700&display=swap',
  punjabi: 'https://fonts.googleapis.com/css2?family=Noto+Sans+Gurmukhi:wght@400;500;600;700&display=swap',
  urdu: 'https://fonts.googleapis.com/css2?family=Noto+Nastaliq+Urdu:wght@400;500;600;700&display=swap',
};