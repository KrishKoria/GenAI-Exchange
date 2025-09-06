"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import {
  documentApi,
  qaApi,
  DocumentUploadResponse,
  AnswerResponse,
  QuestionRequest,
} from "@/lib/api";

// Define proper error type for API responses
interface ApiError extends Error {
  response?: {
    status?: number;
    data?: unknown;
  };
}

// Query keys for consistent cache management
export const documentQueryKeys = {
  all: ["documents"] as const,
  status: (docId: string) => ["documents", "status", docId] as const,
  clauses: (docId: string) => ["documents", "clauses", docId] as const,
  clause: (docId: string, clauseId: string) =>
    ["documents", "clause", docId, clauseId] as const,
  qa: (docId: string) => ["qa", docId] as const,
  qaHistory: (docId: string) => ["qa", "history", docId] as const,
};

// ========================================
// DOCUMENT STATUS HOOK
// ========================================

export function useDocumentStatus(
  docId: string | null,
  enabled: boolean = true
) {
  return useQuery({
    queryKey: documentQueryKeys.status(docId || ""),
    queryFn: () => documentApi.getDocumentStatus(docId!),
    enabled: enabled && !!docId,
    staleTime: 15000, // Reduced to 15 seconds for faster status updates
    refetchInterval: (query) => {
      // Poll every 2 seconds if processing, every 10 seconds if completed
      const status = query.state.data?.status;
      if (status === "processing") return 2000;
      if (status === "completed") return 10000; // Still poll occasionally for updated metadata
      return false;
    },
    retry: (failureCount, error: ApiError) => {
      // Don't retry 404 errors (document not found)
      if (error?.response?.status === 404) return false;
      return failureCount < 3;
    },
    refetchOnWindowFocus: true, // Check status when user returns to tab
  });
}

// ========================================
// DOCUMENT CLAUSES HOOK
// ========================================

export function useDocumentClauses(
  docId: string | null,
  enabled: boolean = true
) {
  return useQuery({
    queryKey: documentQueryKeys.clauses(docId || ""),
    queryFn: () => documentApi.getDocumentClauses(docId!),
    enabled: enabled && !!docId,
    staleTime: 1 * 60 * 1000, // Reduced to 1 minute for more responsive updates
    retry: (failureCount, error: ApiError) => {
      if (error?.response?.status === 404) return false;
      return failureCount < 3;
    },
    refetchOnWindowFocus: false, // Prevent unnecessary refetches
    refetchOnMount: true, // Always refetch when component mounts
  });
}

// ========================================
// CLAUSE DETAIL HOOK
// ========================================

export function useClauseDetail(
  docId: string | null,
  clauseId: string | null,
  enabled: boolean = true
) {
  return useQuery({
    queryKey: documentQueryKeys.clause(docId || "", clauseId || ""),
    queryFn: () => documentApi.getClauseDetail(docId!, clauseId!),
    enabled: enabled && !!docId && !!clauseId,
    staleTime: 10 * 60 * 1000, // 10 minutes - clause details rarely change
    retry: (failureCount, error: ApiError) => {
      if (error?.response?.status === 404) return false;
      return failureCount < 3;
    },
  });
}

// ========================================
// DOCUMENT UPLOAD MUTATION
// ========================================

interface UseDocumentUploadOptions {
  onSuccess?: (data: DocumentUploadResponse) => void;
  onError?: (error: ApiError) => void;
}

export function useDocumentUpload(options?: UseDocumentUploadOptions) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      file,
      sessionId,
    }: {
      file: File;
      sessionId?: string;
    }) => {
      return documentApi.uploadDocument(file, sessionId);
    },
    onSuccess: (data) => {
      // Invalidate all document queries to refresh the data
      queryClient.invalidateQueries({ queryKey: documentQueryKeys.all });

      // Immediately start polling the status for this document
      queryClient.setQueryData(documentQueryKeys.status(data.doc_id), data);

      options?.onSuccess?.(data);
    },
    onError: (error: ApiError) => {
      console.error("Document upload failed:", error);
      options?.onError?.(error);
    },
  });
}

// ========================================
// Q&A HOOKS
// ========================================

export function useQAHistory(docId: string | null, enabled: boolean = true) {
  return useQuery({
    queryKey: documentQueryKeys.qaHistory(docId || ""),
    queryFn: () => qaApi.getQAHistory(docId!, 20),
    enabled: enabled && !!docId,
    staleTime: 2 * 60 * 1000, // 2 minutes
    retry: (failureCount, error: ApiError) => {
      if (error?.response?.status === 404) return false;
      return failureCount < 3;
    },
  });
}

interface UseAskQuestionOptions {
  onSuccess?: (data: AnswerResponse) => void;
  onError?: (error: ApiError) => void;
}

export function useAskQuestion(options?: UseAskQuestionOptions) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: QuestionRequest) => {
      return qaApi.askQuestion(request);
    },
    onSuccess: (data, variables) => {
      // Invalidate Q&A history to show the new question/answer
      queryClient.invalidateQueries({
        queryKey: documentQueryKeys.qaHistory(variables.doc_id),
      });

      options?.onSuccess?.(data);
    },
    onError: (error: ApiError) => {
      console.error("Question failed:", error);
      options?.onError?.(error);
    },
  });
}

// ========================================
// COMPOSITE HOOKS FOR COMPLEX WORKFLOWS
// ========================================

/**
 * Combined hook for document upload and status tracking
 * Automatically starts polling status after upload
 */
export function useDocumentWorkflow() {
  const queryClient = useQueryClient();

  const uploadMutation = useDocumentUpload({
    onSuccess: (data) => {
      // Start polling immediately after upload
      queryClient.invalidateQueries({
        queryKey: documentQueryKeys.status(data.doc_id),
      });
      // Also invalidate clauses to prepare for fresh data
      queryClient.invalidateQueries({
        queryKey: documentQueryKeys.clauses(data.doc_id),
      });
    },
  });

  return {
    upload: uploadMutation,
  };
}

/**
 * Hook to get document status and clauses together
 */
export function useDocumentWithClauses(docId: string | null) {
  const queryClient = useQueryClient();
  const statusQuery = useDocumentStatus(docId);
  const clausesQuery = useDocumentClauses(
    docId,
    true // Always enable clauses query - let it handle empty results gracefully
  );

  // When status changes to completed, invalidate clauses cache to ensure fresh data
  useEffect(() => {
    if (statusQuery.data?.status === "completed" && docId) {
      // Invalidate clauses cache immediately
      queryClient.invalidateQueries({
        queryKey: documentQueryKeys.clauses(docId),
      });

      // Force a refetch after a short delay to ensure backend is ready
      setTimeout(() => {
        queryClient.invalidateQueries({
          queryKey: documentQueryKeys.clauses(docId),
        });
      }, 1000);
    }
  }, [statusQuery.data?.status, docId, queryClient]);

  // Additional effect to check if we have stale clause data
  useEffect(() => {
    if (
      statusQuery.data?.status === "completed" &&
      statusQuery.data?.clause_count &&
      statusQuery.data.clause_count > 0 &&
      clausesQuery.data?.length === 0 &&
      !clausesQuery.isLoading &&
      docId
    ) {
      // We have a completed document with clauses but frontend shows 0
      // This indicates a stale cache issue - force refresh
      console.warn("Detected clause count mismatch, forcing refresh...", {
        backend_count: statusQuery.data.clause_count,
        frontend_count: clausesQuery.data?.length,
        doc_id: docId,
      });

      queryClient.invalidateQueries({
        queryKey: documentQueryKeys.clauses(docId),
      });
      queryClient.refetchQueries({
        queryKey: documentQueryKeys.clauses(docId),
      });
    }
  }, [
    statusQuery.data,
    clausesQuery.data,
    clausesQuery.isLoading,
    docId,
    queryClient,
  ]);

  return {
    status: statusQuery,
    clauses: clausesQuery,
    isReady: statusQuery.data?.status === "completed",
    isFailed: statusQuery.data?.status === "failed",
    isProcessing: statusQuery.data?.status === "processing",
  };
}

// ========================================
// UTILITY FUNCTIONS
// ========================================

/**
 * Prefetch document data for improved UX
 */
export function usePrefetchDocument() {
  const queryClient = useQueryClient();

  return {
    prefetchStatus: (docId: string) => {
      queryClient.prefetchQuery({
        queryKey: documentQueryKeys.status(docId),
        queryFn: () => documentApi.getDocumentStatus(docId),
        staleTime: 30000,
      });
    },
    prefetchClauses: (docId: string) => {
      queryClient.prefetchQuery({
        queryKey: documentQueryKeys.clauses(docId),
        queryFn: () => documentApi.getDocumentClauses(docId),
        staleTime: 5 * 60 * 1000,
      });
    },
  };
}

/**
 * Manually refresh document data
 */
export function useRefreshDocument() {
  const queryClient = useQueryClient();

  return {
    refreshStatus: (docId: string) => {
      queryClient.invalidateQueries({
        queryKey: documentQueryKeys.status(docId),
      });
    },
    refreshClauses: (docId: string) => {
      queryClient.invalidateQueries({
        queryKey: documentQueryKeys.clauses(docId),
      });
    },
    refreshAll: (docId: string) => {
      queryClient.invalidateQueries({
        queryKey: ["documents"],
      });
      queryClient.invalidateQueries({
        queryKey: ["qa", docId],
      });
    },
  };
}
