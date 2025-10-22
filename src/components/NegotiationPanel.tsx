import React, { useState } from "react";
import { useTranslations } from "next-intl";
import {
  Loader2,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  Sparkles,
} from "lucide-react";
import { NegotiationResponse, AlternativeType } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

interface NegotiationPanelProps {
  negotiationResponse: NegotiationResponse | null;
  isLoading?: boolean;
  error?: Error | null;
  onSelectAlternative?: (alternativeId: string) => void;
  onCopyAlternative?: (alternativeText: string) => void;
  className?: string;
}

const ALTERNATIVE_TYPE_COLORS: Record<AlternativeType, string> = {
  balanced: "bg-blue-100 text-blue-800 border-blue-300",
  protective: "bg-green-100 text-green-800 border-green-300",
  simplified: "bg-purple-100 text-purple-800 border-purple-300",
};

const ALTERNATIVE_TYPE_ICONS: Record<AlternativeType, string> = {
  balanced: "⚖️",
  protective: "🛡️",
  simplified: "✨",
};

export const NegotiationPanel: React.FC<NegotiationPanelProps> = ({
  negotiationResponse,
  isLoading = false,
  error = null,
  onSelectAlternative,
  onCopyAlternative,
  className = "",
}) => {
  const t = useTranslations();
  const [expandedAlternativeIds, setExpandedAlternativeIds] = useState<
    Set<string>
  >(new Set());
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Initialize all alternatives as expanded by default
  React.useEffect(() => {
    if (negotiationResponse?.alternatives) {
      const allIds = new Set(
        negotiationResponse.alternatives
          .map((alt) => alt.alternative_id)
          .filter((id): id is string => id !== null && id !== undefined)
      );
      setExpandedAlternativeIds(allIds);
    }
  }, [negotiationResponse]);

  const toggleExpanded = (alternativeId: string) => {
    setExpandedAlternativeIds((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(alternativeId)) {
        newSet.delete(alternativeId);
      } else {
        newSet.add(alternativeId);
      }
      return newSet;
    });
  };

  const handleCopy = async (alternativeId: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(alternativeId);
      onCopyAlternative?.(text);

      // Reset copied state after 2 seconds
      setTimeout(() => {
        setCopiedId(null);
      }, 2000);
    } catch (err) {
      console.error("Failed to copy text:", err);
    }
  };

  const getAlternativeTypeLabel = (type: AlternativeType): string => {
    return t(`negotiation.alternativeTypes.${type}`);
  };

  // Loading state
  if (isLoading) {
    return (
      <Card className={`p-6 ${className}`}>
        <div className="flex flex-col items-center justify-center space-y-4 py-8">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
          <p className="text-sm text-gray-600">{t("negotiation.generating")}</p>
          <p className="text-xs text-gray-500">
            {t("negotiation.generatingMessage")}
          </p>
        </div>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card className={`p-6 border-red-200 bg-red-50 ${className}`}>
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-red-900">
            {t("negotiation.errorTitle")}
          </h3>
          <p className="text-sm text-red-700">{error.message}</p>
          <p className="text-xs text-red-600">
            Please try again or contact support if the issue persists.
          </p>
        </div>
      </Card>
    );
  }

  // No data state
  if (!negotiationResponse) {
    return (
      <Card className={`p-6 bg-gray-50 ${className}`}>
        <div className="text-center space-y-2 py-4">
          <Sparkles className="h-8 w-8 mx-auto text-gray-400" />
          <p className="text-sm text-gray-600">
            {t("negotiation.selectDocument")}
          </p>
          <p className="text-xs text-gray-500">
            {t("negotiation.alternativeDescriptions.balanced")}
          </p>
        </div>
      </Card>
    );
  }

  const {
    alternatives,
    original_clause,
    original_risk_level,
    generation_time,
  } = negotiationResponse;

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Header */}
      <Card className="p-4 bg-gradient-to-r from-blue-50 to-indigo-50 border-blue-200">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-blue-600" />
              {t("negotiation.title")}
            </h3>
            <p className="text-sm text-gray-600">
              {alternatives.length}{" "}
              {t("negotiation.alternatives").toLowerCase()}
            </p>
          </div>
          <div className="text-right">
            <div className="text-xs text-gray-500">Generation Time</div>
            <div className="text-sm font-medium text-gray-700">
              {generation_time.toFixed(2)}s
            </div>
          </div>
        </div>
      </Card>

      {/* Original Clause */}
      <Card className="p-4 bg-gray-50 border-gray-200">
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-gray-700">
              {t("negotiation.originalClause")}
            </h4>
            <span
              className={`px-2 py-1 text-xs font-medium rounded-full ${
                original_risk_level === "attention"
                  ? "bg-red-100 text-red-800"
                  : original_risk_level === "moderate"
                  ? "bg-yellow-100 text-yellow-800"
                  : "bg-green-100 text-green-800"
              }`}
            >
              {original_risk_level.charAt(0).toUpperCase() +
                original_risk_level.slice(1)}{" "}
              Risk
            </span>
          </div>
          <p className="text-sm text-gray-700 leading-relaxed">
            {original_clause}
          </p>
        </div>
      </Card>

      {/* Alternatives */}
      <div className="space-y-3">
        {alternatives.map((alternative, index) => {
          const isExpanded = alternative.alternative_id
            ? expandedAlternativeIds.has(alternative.alternative_id)
            : false;
          const isCopied = alternative.alternative_id === copiedId;

          return (
            <Card
              key={alternative.alternative_id || index}
              className={`overflow-hidden transition-all duration-200 border-2 ${
                ALTERNATIVE_TYPE_COLORS[alternative.alternative_type]
              }`}
            >
              {/* Alternative Header */}
              <div className="p-4 space-y-3">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-lg">
                        {ALTERNATIVE_TYPE_ICONS[alternative.alternative_type]}
                      </span>
                      <h4 className="text-sm font-semibold text-gray-900">
                        {getAlternativeTypeLabel(alternative.alternative_type)}
                      </h4>
                      <span className="text-xs text-gray-500">
                        ({Math.round(alternative.confidence * 100)}% confidence)
                      </span>
                    </div>

                    {/* Strategic Benefit */}
                    <div className="mt-2 p-3 bg-white/60 rounded-lg border border-gray-200">
                      <div className="text-xs font-medium text-gray-600 mb-1">
                        ✨ Strategic Benefit
                      </div>
                      <p className="text-sm text-gray-800">
                        {alternative.strategic_benefit}
                      </p>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 ml-4">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        alternative.alternative_id &&
                        handleCopy(
                          alternative.alternative_id,
                          alternative.alternative_text
                        )
                      }
                      className="h-8 w-8 p-0"
                      title={t("negotiation.copyAlternative")}
                    >
                      {isCopied ? (
                        <Check className="h-4 w-4 text-green-600" />
                      ) : (
                        <Copy className="h-4 w-4" />
                      )}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        alternative.alternative_id &&
                        toggleExpanded(alternative.alternative_id)
                      }
                      className="h-8 w-8 p-0"
                      title={isExpanded ? t("common.close") : t("common.view")}
                    >
                      {isExpanded ? (
                        <ChevronUp className="h-4 w-4" />
                      ) : (
                        <ChevronDown className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                </div>

                {/* Alternative Text (Always Visible) */}
                <div className="mt-3 p-3 bg-white rounded-lg border border-gray-200">
                  <div className="text-xs font-medium text-gray-600 mb-2">
                    📄 Alternative Clause Text
                  </div>
                  <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
                    {alternative.alternative_text}
                  </p>
                </div>

                {/* Expanded Details */}
                {isExpanded && (
                  <div className="mt-3 space-y-3 animate-in slide-in-from-top-2">
                    {/* Strategic Benefit */}
                    <div className="p-3 bg-white rounded-lg border border-gray-200">
                      <div className="text-xs font-medium text-gray-600 mb-1">
                        ✨ {t("negotiation.strategicBenefit")}
                      </div>
                      <p className="text-sm text-gray-700">
                        {alternative.strategic_benefit}
                      </p>
                    </div>

                    {/* Risk Reduction */}
                    <div className="p-3 bg-white rounded-lg border border-gray-200">
                      <div className="text-xs font-medium text-gray-600 mb-1">
                        🛡️ {t("negotiation.riskReduction")}
                      </div>
                      <p className="text-sm text-gray-700">
                        {alternative.risk_reduction}
                      </p>
                    </div>

                    {/* Implementation Notes */}
                    <div className="p-3 bg-white rounded-lg border border-gray-200">
                      <div className="text-xs font-medium text-gray-600 mb-1">
                        💡 {t("negotiation.implementationNotes")}
                      </div>
                      <p className="text-sm text-gray-700">
                        {alternative.implementation_notes}
                      </p>
                    </div>

                    {/* Select Button */}
                    {onSelectAlternative && alternative.alternative_id && (
                      <Button
                        onClick={() =>
                          alternative.alternative_id &&
                          onSelectAlternative(alternative.alternative_id)
                        }
                        className="w-full"
                        variant="default"
                      >
                        {t("negotiation.selectAlternative")}
                      </Button>
                    )}
                  </div>
                )}
              </div>
            </Card>
          );
        })}
      </div>

      {/* Footer Note */}
      <Card className="p-3 bg-blue-50 border-blue-200">
        <p className="text-xs text-blue-900">
          <strong>💡 Pro Tip:</strong> These alternatives are generated by AI
          and should be reviewed by a legal professional before use in actual
          contract negotiations.
        </p>
      </Card>
    </div>
  );
};

export default NegotiationPanel;
