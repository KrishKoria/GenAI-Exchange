/**
 * API service layer for GenAI Exchange legal document analysis
 * Handles all communication with the FastAPI backend
 */
import axios, { AxiosResponse } from "axios";

// Get API base URL from environment with fallback to localhost
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Create axios instance with default configuration
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 second timeout
  headers: {
    "Content-Type": "application/json",
  },
});

// Response interceptor for consistent error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      // Server responded with error status
      console.error("API Error:", error.response.status, error.response.data);
    } else if (error.request) {
      // Request made but no response received
      console.error("Network Error:", error.message);
    } else {
      // Something else happened
      console.error("Request Error:", error.message);
    }
    return Promise.reject(error);
  }
);

// ========================================
// TYPE DEFINITIONS (matching backend models)
// ========================================

export type DocumentStatus = "uploaded" | "processing" | "completed" | "failed";
export type RiskLevel = "low" | "moderate" | "attention";

export interface DocumentUploadResponse {
  doc_id: string;
  status: DocumentStatus;
  filename: string;
  message: string;
  created_at: string;
}

export interface ClauseSummary {
  clause_id: string;
  order: number;
  category: string;
  risk_level: RiskLevel;
  summary: string;
  readability_delta: number;
  needs_review: boolean;
}

export interface ReadabilityMetrics {
  original_grade: number;
  summary_grade: number;
  delta: number;
  flesch_score: number;
}

export interface ClauseDetail {
  clause_id: string;
  doc_id: string;
  order: number;
  category: string;
  risk_level: RiskLevel;
  original_text: string;
  summary: string;
  readability_metrics: ReadabilityMetrics;
  needs_review: boolean;
  negotiation_tip?: string;
}

export interface ProcessingProgress {
  doc_id: string;
  stage: string;
  progress: number; // 0.0 to 1.0
  message: string;
  estimated_completion?: string;
  error_message?: string;
}

export interface DocumentStatusResponse {
  doc_id: string;
  status: DocumentStatus;
  progress?: ProcessingProgress;
  filename?: string;
  created_at?: string;
  processed_at?: string;
  error_message?: string;
  clause_count?: number;
  page_count?: number;
  masked?: boolean;
  pii_summary?: Record<string, unknown>;
  processing_statistics?: Record<string, unknown>;
  message?: string;
}

// Q&A Types
export interface QuestionRequest {
  doc_id: string;
  question: string;
  session_id?: string;
}

export interface SourceCitation {
  clause_id: string;
  snippet: string;
  relevance_score: number;
}

export interface AnswerResponse {
  answer: string;
  used_clause_ids: string[];
  confidence: number;
  sources: SourceCitation[];
  timestamp: string;
}

export interface QAHistoryItem {
  timestamp: string;
  question: string;
  answer: string;
  clause_ids: string[];
}

// ========================================
// DOCUMENT API
// ========================================

export const documentApi = {
  /**
   * Upload a document for processing
   */
  async uploadDocument(
    file: File,
    sessionId?: string
  ): Promise<DocumentUploadResponse> {
    const formData = new FormData();
    formData.append("file", file);
    if (sessionId) {
      formData.append("session_id", sessionId);
    }

    const response: AxiosResponse<DocumentUploadResponse> =
      await apiClient.post("/api/v1/documents/ingest", formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
        timeout: 60000, // 60 seconds for file upload
      });

    return response.data;
  },

  /**
   * Get document processing status
   */
  async getDocumentStatus(docId: string): Promise<DocumentStatusResponse> {
    const response: AxiosResponse<DocumentStatusResponse> = await apiClient.get(
      `/api/v1/documents/status/${docId}`
    );

    return response.data;
  },

  /**
   * Get clause summaries for a document
   */
  async getDocumentClauses(docId: string): Promise<ClauseSummary[]> {
    const response: AxiosResponse<ClauseSummary[]> = await apiClient.get(
      `/api/v1/documents/clauses?doc_id=${docId}`
    );

    return response.data;
  },

  /**
   * Get detailed information about a specific clause
   */
  async getClauseDetail(
    docId: string,
    clauseId: string
  ): Promise<ClauseDetail> {
    const response: AxiosResponse<ClauseDetail> = await apiClient.get(
      `/api/v1/documents/clause/${clauseId}?doc_id=${docId}`
    );

    return response.data;
  },
};

// ========================================
// Q&A API
// ========================================

export const qaApi = {
  /**
   * Ask a question about a document
   */
  async askQuestion(request: QuestionRequest): Promise<AnswerResponse> {
    const response: AxiosResponse<AnswerResponse> = await apiClient.post(
      "/api/v1/qa/ask",
      request
    );

    return response.data;
  },

  /**
   * Get Q&A history for a document
   */
  async getQAHistory(
    docId: string,
    limit: number = 10
  ): Promise<QAHistoryItem[]> {
    const response: AxiosResponse<QAHistoryItem[]> = await apiClient.get(
      `/api/v1/qa/history/${docId}?limit=${limit}`
    );

    return response.data;
  },
};

// ========================================
// UTILITY FUNCTIONS
// ========================================

/**
 * Generate risk heatmap data from clauses
 */
export function generateRiskHeatmap(clauses: ClauseSummary[]): number[][] {
  if (clauses.length === 0) {
    // Return default placeholder heatmap
    return [
      [0.2, 0.4, 0.1, 0.6, 0.8, 0.3],
      [0.1, 0.5, 0.7, 0.2, 0.4, 0.9],
      [0.3, 0.2, 0.6, 0.5, 0.7, 0.4],
      [0.6, 0.8, 0.2, 0.3, 0.5, 0.7],
    ];
  }

  // Convert risk levels to numeric values
  const riskValues = clauses.map((clause) => {
    switch (clause.risk_level) {
      case "low":
        return 0.2;
      case "moderate":
        return 0.5;
      case "attention":
        return 0.8;
      default:
        return 0.4;
    }
  });

  // Create 4x6 grid (24 cells) from clause risk data
  const heatmap: number[][] = [];
  for (let row = 0; row < 4; row++) {
    const rowData: number[] = [];
    for (let col = 0; col < 6; col++) {
      const index = row * 6 + col;
      if (index < riskValues.length) {
        rowData.push(riskValues[index]);
      } else {
        // Fill remaining cells with average risk of existing clauses
        const avgRisk =
          riskValues.reduce((sum, val) => sum + val, 0) / riskValues.length;
        rowData.push(avgRisk);
      }
    }
    heatmap.push(rowData);
  }

  return heatmap;
}

/**
 * Get top risky clauses from clauses array
 */
export function getTopRiskyClauses(
  clauses: ClauseSummary[],
  limit: number = 3
) {
  return clauses
    .filter((clause) => clause.risk_level !== "low")
    .sort((a, b) => {
      const riskOrder = { attention: 3, moderate: 2, low: 1 };
      return riskOrder[b.risk_level] - riskOrder[a.risk_level];
    })
    .slice(0, limit)
    .map((clause) => ({
      k: clause.category,
      risk: clause.risk_level === "attention" ? 0.85 : 0.65,
    }));
}

/**
 * Format processing progress message
 */
export function formatProcessingMessage(progress: ProcessingProgress): string {
  const percentage = Math.round(progress.progress * 100);
  return `${progress.message} (${percentage}%)`;
}

/**
 * Check if document processing is complete
 */
export function isDocumentReady(status: DocumentStatusResponse): boolean {
  return status.status === "completed";
}

/**
 * Check if document processing failed
 */
export function isDocumentFailed(status: DocumentStatusResponse): boolean {
  return status.status === "failed";
}

/**
 * Get processing status color for UI
 */
export function getStatusColor(status: DocumentStatus): string {
  switch (status) {
    case "uploaded":
      return "blue";
    case "processing":
      return "yellow";
    case "completed":
      return "green";
    case "failed":
      return "red";
    default:
      return "gray";
  }
}

const apiExports = {
  documentApi,
  qaApi,
  generateRiskHeatmap,
  getTopRiskyClauses,
  formatProcessingMessage,
  isDocumentReady,
  isDocumentFailed,
  getStatusColor,
};

export default apiExports;
