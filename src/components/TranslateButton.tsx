"use client";

import { useState } from "react";
import { Languages, Check, Loader2, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { locales, localeNames, type Locale } from "@/i18n/config";
import { documentApi } from "@/lib/api";
import { useToast } from "@/components/ui/toast";

interface TranslateButtonProps {
  docId: string;
  docName: string;
  disabled?: boolean;
  onTranslationComplete?: () => void;
}

export function TranslateButton({
  docId,
  docName,
  disabled = false,
  onTranslationComplete,
}: TranslateButtonProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isTranslating, setIsTranslating] = useState(false);
  const [translatedLanguages, setTranslatedLanguages] = useState<Set<string>>(
    new Set()
  );
  const { toast } = useToast();

  const handleTranslate = async (targetLanguage: Locale) => {
    if (targetLanguage === "en") {
      toast({
        type: "info",
        title: "No Translation Needed",
        description: "Document is already in English",
      });
      setIsOpen(false);
      return;
    }

    setIsTranslating(true);
    setIsOpen(false);

    try {
      const response = await documentApi.translateDocument(
        docId,
        targetLanguage
      );

      setTranslatedLanguages((prev) => new Set(prev).add(targetLanguage));

      toast({
        type: "success",
        title: "Translation Complete",
        description: `${docName} translated to ${localeNames[targetLanguage]} (${response.translations_count} clauses in ${response.duration_ms}ms)`,
      });

      onTranslationComplete?.();
    } catch (error: unknown) {
      console.error("Translation failed:", error);

      const errorMessage =
        (error as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ||
        (error as Error)?.message ||
        "Failed to translate document";

      toast({
        type: "error",
        title: "Translation Failed",
        description: errorMessage,
      });
    } finally {
      setIsTranslating(false);
    }
  };

  // Filter out English from translation options
  const translationLanguages = locales.filter((loc) => loc !== "en");

  // Debug: Log when component renders
  console.log(
    `[TranslateButton Render] Doc: ${docName}, DocId: ${docId}, IsOpen: ${isOpen}, TranslatedCount: ${translatedLanguages.size}`
  );

  return (
    <div className="relative">
      <Button
        variant="ghost"
        size="sm"
        onClick={(e) => {
          e.stopPropagation();
          console.log(
            `[TranslateButton Click] Opening dropdown for ${docName}`
          );
          setIsOpen(!isOpen);
        }}
        disabled={disabled || isTranslating}
        className="h-8 px-3 text-xs font-medium text-purple-400 hover:text-purple-100 hover:bg-purple-500/30 border border-purple-400/30 hover:border-purple-400/60 transition-all"
        title="Translate document"
      >
        {isTranslating ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <>
            <Languages className="h-4 w-4 mr-1.5" />
            {translatedLanguages.size > 0 && (
              <span className="text-[10px] font-bold bg-purple-500/50 px-1.5 py-0.5 rounded-full">
                {translatedLanguages.size}
              </span>
            )}
            <ChevronDown
              className={`h-3 w-3 ml-1 transition-transform ${
                isOpen ? "rotate-180" : ""
              }`}
            />
          </>
        )}
      </Button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-30"
            onClick={() => setIsOpen(false)}
          />

          {/* Dropdown */}
          <div className="absolute top-full right-0 mt-1 z-40 min-w-[180px] bg-gray-800/95 backdrop-blur-sm border border-white/20 rounded-md shadow-lg overflow-hidden max-h-[300px] overflow-y-auto">
            <div className="px-3 py-2 text-xs text-white/60 border-b border-white/10">
              Translate to:
            </div>
            {translationLanguages.map((loc) => (
              <button
                key={loc}
                onClick={() => handleTranslate(loc)}
                disabled={isTranslating}
                className={`
                  w-full px-3 py-2 text-left text-sm hover:bg-white/10 transition-colors
                  flex items-center justify-between gap-2
                  ${isTranslating ? "opacity-50 cursor-not-allowed" : ""}
                  text-gray-200
                `}
              >
                <span>{localeNames[loc]}</span>
                {translatedLanguages.has(loc) && (
                  <Check className="h-3 w-3 text-green-400" />
                )}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
