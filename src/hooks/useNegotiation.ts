/**
 * Custom hook for AI-Powered Negotiation feature
 *
 * Handles:
 * - Generating alternatives for individual clauses
 * - Batch generation for multiple clauses
 * - Saving negotiation interactions
 * - Retrieving history
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  negotiationApi,
  NegotiationRequest,
  NegotiationResponse,
  BatchNegotiationRequest,
  SaveNegotiationRequest,
} from "@/lib/api";

/**
 * Hook to generate negotiation alternatives for a single clause
 */
export function useGenerateAlternatives() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: NegotiationRequest) =>
      negotiationApi.generateAlternatives(request),
    onSuccess: (data, variables) => {
      // Invalidate negotiation history queries
      if (variables.doc_id) {
        queryClient.invalidateQueries({
          queryKey: ["negotiation-history", variables.doc_id],
        });
      }
    },
  });
}

/**
 * Hook to generate quick alternatives (simplified for demos)
 */
export function useQuickAlternatives() {
  return useMutation({
    mutationFn: (request: { clause_text: string; clause_category?: string }) =>
      negotiationApi.generateQuickAlternatives(request),
  });
}

/**
 * Hook to batch generate alternatives for multiple clauses
 */
export function useBatchGenerateAlternatives() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: BatchNegotiationRequest) =>
      negotiationApi.generateBatchAlternatives(request),
    onSuccess: (data) => {
      // Invalidate negotiation history for the document
      queryClient.invalidateQueries({
        queryKey: ["negotiation-history", data.doc_id],
      });
    },
  });
}

/**
 * Hook to save a negotiation interaction with feedback
 */
export function useSaveNegotiation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: SaveNegotiationRequest) =>
      negotiationApi.saveNegotiation(request),
    onSuccess: (_, variables) => {
      // Invalidate history queries
      queryClient.invalidateQueries({
        queryKey: ["negotiation-history", variables.doc_id],
      });
    },
  });
}

/**
 * Hook to retrieve negotiation history for a document
 */
export function useNegotiationHistory(docId: string | null, clauseId?: string) {
  return useQuery({
    queryKey: ["negotiation-history", docId, clauseId],
    queryFn: () => {
      if (!docId) throw new Error("Document ID is required");
      return negotiationApi.getNegotiationHistory(docId, clauseId);
    },
    enabled: !!docId,
  });
}

/**
 * Hook to get negotiation statistics for a document
 */
export function useNegotiationStats(docId: string | null) {
  return useQuery({
    queryKey: ["negotiation-stats", docId],
    queryFn: () => {
      if (!docId) throw new Error("Document ID is required");
      return negotiationApi.getNegotiationStats(docId);
    },
    enabled: !!docId,
  });
}

/**
 * Combined hook for complete negotiation workflow
 * Provides all negotiation operations in one place
 */
export function useNegotiation(docId: string | null = null) {
  const generateAlternatives = useGenerateAlternatives();
  const quickAlternatives = useQuickAlternatives();
  const batchGenerate = useBatchGenerateAlternatives();
  const saveNegotiation = useSaveNegotiation();
  const history = useNegotiationHistory(docId);
  const stats = useNegotiationStats(docId);

  return {
    // Mutations
    generateAlternatives,
    quickAlternatives,
    batchGenerate,
    saveNegotiation,

    // Queries
    history,
    stats,

    // Helper methods
    generateForClause: (
      clauseText: string,
      clauseCategory?: string,
      clauseId?: string
    ) => {
      return generateAlternatives.mutate({
        clause_text: clauseText,
        clause_category: clauseCategory,
        clause_id: clauseId,
        doc_id: docId || undefined,
      });
    },

    generateForClauses: (clauseIds: string[]) => {
      if (!docId)
        throw new Error("Document ID is required for batch generation");
      return batchGenerate.mutate({
        clause_ids: clauseIds,
        doc_id: docId,
      });
    },

    saveFeedback: (
      negotiationId: string,
      clauseId: string,
      selectedAlternativeId?: string,
      wasHelpful?: boolean,
      feedback?: string
    ) => {
      if (!docId)
        throw new Error("Document ID is required to save negotiation");
      return saveNegotiation.mutate({
        negotiation_id: negotiationId,
        doc_id: docId,
        clause_id: clauseId,
        selected_alternative_id: selectedAlternativeId,
        was_helpful: wasHelpful,
        user_feedback: feedback,
      });
    },
  };
}

/**
 * Hook to manage negotiation panel state
 * Tracks which clause is currently being negotiated
 */
export function useNegotiationPanelState() {
  const [selectedClauseId, setSelectedClauseId] = useState<string | null>(null);
  const [negotiationResponse, setNegotiationResponse] =
    useState<NegotiationResponse | null>(null);
  const [isPanelOpen, setIsPanelOpen] = useState(false);

  const openNegotiationFor = (clauseId: string) => {
    setSelectedClauseId(clauseId);
    setIsPanelOpen(true);
  };

  const closeNegotiation = () => {
    setIsPanelOpen(false);
    // Clear state after animation
    setTimeout(() => {
      setSelectedClauseId(null);
      setNegotiationResponse(null);
    }, 300);
  };

  const setResponse = (response: NegotiationResponse | null) => {
    setNegotiationResponse(response);
  };

  return {
    selectedClauseId,
    negotiationResponse,
    isPanelOpen,
    openNegotiationFor,
    closeNegotiation,
    setResponse,
  };
}
