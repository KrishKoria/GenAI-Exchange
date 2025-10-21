import { useState, useEffect } from "react";
import { useNegotiation } from "./useNegotiation";
import { useToast, createToast } from "@/components/ui/toast";
import { ClauseSummary, RiskLevel } from "@/lib/api";

export interface SelectedAlternative {
  alternativeId: string;
  alternativeType: string;
  clauseCategory: string;
  strategicBenefit: string;
  selectedAt: Date;
}

export interface ClauseInfo {
  clause_id: string;
  clause_text: string;
  clause_category: string;
  risk_level: string;
}

export interface UseNegotiationStateParams {
  currentDocId: string | null;
  clauses: ClauseSummary[];
  onAddChatMessage: (
    clauseCategory: string,
    alternativeType?: string,
    strategicBenefit?: string,
    messageType?: "generated" | "selected"
  ) => void;
}

export interface UseNegotiationStateReturn {
  negotiationPanelOpen: boolean;
  selectedClauseForNegotiation: ClauseInfo | null;
  selectedAlternatives: { [clauseId: string]: SelectedAlternative };
  setNegotiationPanelOpen: (open: boolean) => void;
  handleGenerateAlternatives: (
    clauseId: string,
    clauseCategory: string,
    riskLevel: string
  ) => Promise<void>;
  handleSelectAlternative: (alternativeId: string) => Promise<void>;
  buildFullNegotiationContext: () => string;
  buildSelectedAlternativesContext: () => string;
  negotiationQuery: ReturnType<typeof useNegotiation>;
}

/**
 * Hook for managing negotiation state and alternative selection
 */
export const useNegotiationState = ({
  currentDocId,
  clauses,
  onAddChatMessage,
}: UseNegotiationStateParams): UseNegotiationStateReturn => {
  const { toast } = useToast();
  const negotiation = useNegotiation(currentDocId);

  const [negotiationPanelOpen, setNegotiationPanelOpen] = useState(false);
  const [selectedClauseForNegotiation, setSelectedClauseForNegotiation] =
    useState<ClauseInfo | null>(null);
  const [selectedAlternatives, setSelectedAlternatives] = useState<{
    [clauseId: string]: SelectedAlternative;
  }>({});

  // Clear negotiation state when selected clause is no longer in the current document(s)
  useEffect(() => {
    if (selectedClauseForNegotiation) {
      // Check if the selected clause still exists in the current clauses
      const clauseExists = clauses.some(
        (c) => c.clause_id === selectedClauseForNegotiation.clause_id
      );

      // If clause doesn't exist in current selection, clear negotiation state
      if (!clauseExists) {
        setSelectedClauseForNegotiation(null);
        setNegotiationPanelOpen(false);
      }
    }
  }, [clauses, selectedClauseForNegotiation]);

  // Handle generating negotiation alternatives
  const handleGenerateAlternatives = async (
    clauseId: string,
    clauseCategory: string,
    riskLevel: string
  ) => {
    if (!currentDocId) {
      toast(
        createToast.error(
          "No Document Selected",
          "Please select a document first."
        )
      );
      return;
    }

    try {
      // Find the clause in our local data first for quick display
      const clause = clauses.find((c) => c.clause_id === clauseId);
      if (!clause) {
        throw new Error("Clause not found");
      }

      // Store the clause details and open the panel
      setSelectedClauseForNegotiation({
        clause_id: clauseId,
        clause_text: clause.summary, // Use summary as placeholder until we get full text
        clause_category: clauseCategory,
        risk_level: riskLevel,
      });
      setNegotiationPanelOpen(true);

      // Generate alternatives - the backend will fetch the original_text
      await negotiation.generateAlternatives.mutateAsync({
        clause_text: clause.summary, // Backend can use clause_id to fetch original_text
        clause_category: clauseCategory,
        clause_id: clauseId,
        doc_id: currentDocId,
        risk_level: riskLevel as RiskLevel,
      });

      // Add automated message to chat about the generated alternatives
      onAddChatMessage(clauseCategory, undefined, undefined, "generated");

      toast(
        createToast.success(
          "Alternatives Generated",
          "AI has generated 3 strategic alternatives for your clause."
        )
      );
    } catch (error: unknown) {
      console.error("Failed to generate alternatives:", error);
      toast(
        createToast.error(
          "Generation Failed",
          (error as Error)?.message ||
            "Failed to generate alternatives. Please try again."
        )
      );
    }
  };

  // Handle selecting an alternative
  const handleSelectAlternative = async (alternativeId: string) => {
    if (
      !negotiation.generateAlternatives.data?.negotiation_id ||
      !selectedClauseForNegotiation
    ) {
      return;
    }

    try {
      await negotiation.saveFeedback(
        negotiation.generateAlternatives.data.negotiation_id,
        selectedClauseForNegotiation.clause_id,
        alternativeId,
        true
      );

      // Find the selected alternative details
      const selectedAlt =
        negotiation.generateAlternatives.data.alternatives.find(
          (alt) => alt.alternative_id === alternativeId
        );

      if (selectedAlt) {
        // Track the selection in state
        setSelectedAlternatives((prev) => ({
          ...prev,
          [selectedClauseForNegotiation.clause_id]: {
            alternativeId: alternativeId,
            alternativeType:
              selectedAlt.alternative_type.charAt(0).toUpperCase() +
              selectedAlt.alternative_type.slice(1),
            clauseCategory: selectedClauseForNegotiation.clause_category,
            strategicBenefit: selectedAlt.strategic_benefit,
            selectedAt: new Date(),
          },
        }));

        // Add automated message to chat about the selection
        onAddChatMessage(
          selectedClauseForNegotiation.clause_category,
          selectedAlt.alternative_type.charAt(0).toUpperCase() +
            selectedAlt.alternative_type.slice(1),
          selectedAlt.strategic_benefit,
          "selected"
        );
      }

      toast(
        createToast.success(
          "Alternative Saved",
          "Your selection has been recorded and added to the chat."
        )
      );
    } catch (error) {
      console.error("Failed to save alternative:", error);
    }
  };

  // Build comprehensive negotiation context for chatbot (when panel is open)
  const buildFullNegotiationContext = (): string => {
    if (
      !negotiation.generateAlternatives.data ||
      !selectedClauseForNegotiation
    ) {
      return "";
    }

    const data = negotiation.generateAlternatives.data;
    const selectedId = Object.values(selectedAlternatives).find(
      (alt) =>
        alt.clauseCategory === selectedClauseForNegotiation.clause_category
    )?.alternativeId;

    let context = `\n\n[NEGOTIATION CONTEXT for ${selectedClauseForNegotiation.clause_category} Clause:\n\n`;
    context += `ORIGINAL CLAUSE:\n"${data.original_clause}"\n\n`;
    context += `GENERATED ALTERNATIVES:\n\n`;

    data.alternatives.forEach((alt, index) => {
      const altType =
        alt.alternative_type.charAt(0).toUpperCase() +
        alt.alternative_type.slice(1);
      const isSelected = alt.alternative_id === selectedId;

      context += `${index + 1}. ${altType.toUpperCase()} Alternative${
        isSelected ? " (SELECTED)" : ""
      }:\n`;
      context += `"${alt.alternative_text}"\n`;
      context += `Strategic Benefit: ${alt.strategic_benefit}\n`;
      context += `Risk Reduction: ${alt.risk_reduction}\n\n`;
    });

    context += `]`;
    return context;
  };

  // Build brief context for selected alternatives (when panel is closed)
  const buildSelectedAlternativesContext = (): string => {
    const recentSelections = Object.entries(selectedAlternatives).filter(
      ([, alt]) => {
        const minutesAgo =
          (new Date().getTime() - alt.selectedAt.getTime()) / (1000 * 60);
        return minutesAgo < 30; // Only include selections from last 30 minutes
      }
    );

    if (recentSelections.length === 0) {
      return "";
    }

    let context = `\n\n[RECENT NEGOTIATION DECISIONS:\n\n`;
    recentSelections.forEach(([, alt]) => {
      context += `• Selected "${alt.alternativeType}" alternative for ${alt.clauseCategory} clause\n`;
      context += `  Strategic Benefit: ${alt.strategicBenefit}\n\n`;
    });
    context += `]`;

    return context;
  };

  return {
    negotiationPanelOpen,
    selectedClauseForNegotiation,
    selectedAlternatives,
    setNegotiationPanelOpen,
    handleGenerateAlternatives,
    handleSelectAlternative,
    buildFullNegotiationContext,
    buildSelectedAlternativesContext,
    negotiationQuery: negotiation,
  };
};
