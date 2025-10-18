"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import { Languages, Check, Loader2, Globe, Eye } from "lucide-react";
import { locales, localeNames, type Locale } from "@/i18n/config";
import { documentApi, type ClauseSummary } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { useLanguage } from "@/contexts/LanguageContext";
import { getAvailableLanguages } from "@/lib/translation-utils";

interface TranslationPanelProps {
  docId: string | null;
  isLoading?: boolean;
  clauses?: ClauseSummary[];
}

export function TranslationPanel({
  docId,
  isLoading = false,
  clauses = [],
}: TranslationPanelProps) {
  const [translatedLanguages, setTranslatedLanguages] = useState<Set<string>>(
    new Set()
  );
  const [translatingLanguage, setTranslatingLanguage] = useState<string | null>(
    null
  );
  const { toast } = useToast();
  const {
    viewingLanguage,
    setViewingLanguage,
    availableLanguages,
    addAvailableLanguage,
    resetAvailableLanguages,
  } = useLanguage();

  // Track which document we've already detected translations for
  const detectedDocIdRef = useRef<string | null>(null);
  const previousDocIdRef = useRef<string | null>(null);

  // Compute detected languages without side effects (pure computation)
  const detectedLanguages = useMemo(() => {
    if (!clauses || clauses.length === 0) return new Set<Locale>();

    const languages = new Set<Locale>();
    clauses.forEach((clause) => {
      if (clause.translations) {
        const clauseLanguages = getAvailableLanguages(clause.translations);
        clauseLanguages.forEach((lang) => languages.add(lang));
      }
    });
    return languages;
  }, [clauses]);

  // Single effect to handle document changes and initialization
  useEffect(() => {
    const hasDocChanged = previousDocIdRef.current !== docId;

    if (hasDocChanged) {
      // Reset state when document changes
      setTranslatedLanguages(new Set());
      setTranslatingLanguage(null);
      resetAvailableLanguages();
      detectedDocIdRef.current = null;
      previousDocIdRef.current = docId;
    }

    // Only add detected languages if we haven't already processed this document
    if (
      docId &&
      detectedDocIdRef.current !== docId &&
      detectedLanguages.size > 0
    ) {
      detectedLanguages.forEach((lang) => {
        addAvailableLanguage(lang);
        setTranslatedLanguages((prev) => new Set(prev).add(lang));
      });
      detectedDocIdRef.current = docId;
    }
  }, [docId, detectedLanguages, addAvailableLanguage, resetAvailableLanguages]);

  const handleTranslate = async (targetLanguage: Locale) => {
    if (!docId) return;

    if (targetLanguage === "en") {
      toast({
        type: "info",
        title: "No Translation Needed",
        description: "Document is already in English",
      });
      return;
    }

    setTranslatingLanguage(targetLanguage);

    try {
      const response = await documentApi.translateDocument(
        docId,
        targetLanguage
      );

      setTranslatedLanguages((prev) => new Set(prev).add(targetLanguage));
      addAvailableLanguage(targetLanguage); // Add to available languages for viewing

      toast({
        type: "success",
        title: "Translation Complete",
        description: `Translated to ${localeNames[targetLanguage]} (${response.translations_count} clauses)`,
      });
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
      setTranslatingLanguage(null);
    }
  };

  // Filter out English from translation options
  const translationLanguages = locales.filter((loc) => loc !== "en");

  if (!docId) {
    return (
      <div className="flex flex-col items-center justify-center py-8 px-4 text-center">
        <Globe className="h-12 w-12 text-white/20 mb-3" />
        <p className="text-sm text-white/40">Select a document to translate</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-8 w-8 animate-spin text-purple-400" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Language Selector (only show if translations available) */}
      {availableLanguages.size > 1 && (
        <div className="p-3 bg-purple-500/10 border border-purple-500/30 rounded-lg">
          <label className="text-xs text-white/60 mb-2 block font-medium uppercase tracking-wide">
            View Document In:
          </label>
          <select
            value={viewingLanguage}
            onChange={(e) => setViewingLanguage(e.target.value as Locale)}
            className="w-full px-3 py-2 bg-white/10 border border-white/20 rounded-md text-sm text-white hover:bg-white/15 transition-colors cursor-pointer focus:outline-none focus:ring-2 focus:ring-purple-500"
          >
            {Array.from(availableLanguages)
              .sort((a, b) => {
                // English first, then alphabetically
                if (a === "en") return -1;
                if (b === "en") return 1;
                return localeNames[a].localeCompare(localeNames[b]);
              })
              .map((lang) => (
                <option key={lang} value={lang} className="bg-gray-800">
                  {localeNames[lang]}
                  {lang === "en" && " (Original)"}
                </option>
              ))}
          </select>
          <div className="mt-2 text-xs text-purple-300/80 flex items-center gap-1">
            <Eye className="h-3 w-3" />
            <span>
              Currently viewing in{" "}
              <strong>{localeNames[viewingLanguage]}</strong>
            </span>
          </div>
        </div>
      )}

      {/* Header */}
      <div>
        <h4 className="text-sm font-medium text-white/90 mb-1">
          Translate Document
        </h4>
        <p className="text-xs text-white/50">
          Make this document accessible in multiple languages
        </p>
      </div>

      {/* Language Grid */}
      <div className="grid grid-cols-2 gap-2">
        {translationLanguages.map((loc) => {
          const isTranslated = translatedLanguages.has(loc);
          const isTranslating = translatingLanguage === loc;

          return (
            <button
              key={loc}
              onClick={() => handleTranslate(loc)}
              disabled={isTranslating || translatingLanguage !== null}
              className={`
                relative px-3 py-2.5 rounded-lg border text-left transition-all
                ${
                  isTranslated
                    ? "bg-green-500/20 border-green-500/50 text-white"
                    : "bg-white/5 border-white/10 text-white/70 hover:bg-white/10 hover:border-white/20"
                }
                ${
                  translatingLanguage !== null && !isTranslating
                    ? "opacity-50 cursor-not-allowed"
                    : ""
                }
              `}
            >
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium truncate">
                    {localeNames[loc]}
                  </div>
                  {isTranslating && (
                    <div className="text-[10px] text-white/60 mt-0.5">
                      Translating...
                    </div>
                  )}
                  {isTranslated && !isTranslating && (
                    <div className="text-[10px] text-green-400 mt-0.5">
                      Available
                    </div>
                  )}
                </div>
                <div className="ml-2 shrink-0">
                  {isTranslating ? (
                    <Loader2 className="h-4 w-4 animate-spin text-purple-400" />
                  ) : isTranslated ? (
                    <Check className="h-4 w-4 text-green-400" />
                  ) : (
                    <Languages className="h-4 w-4 text-white/40" />
                  )}
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Stats */}
      {translatedLanguages.size > 0 && (
        <div className="pt-3 border-t border-white/10">
          <div className="flex items-center justify-between text-xs">
            <span className="text-white/60">Available Languages</span>
            <span className="font-semibold text-purple-400">
              {translatedLanguages.size + 1}{" "}
              <span className="text-white/40">/ {locales.length}</span>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
