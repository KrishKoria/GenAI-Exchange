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
  timeout: 120000, // 2 minutes timeout for document processing
  headers: {
    "Content-Type": "application/json",
  },
});

// Response interceptor for consistent error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const status = error.response.status;
      const data = error.response.data;

      // Distinguish between validation errors and actual server errors
      if (status >= 400 && status < 500) {
        // Client errors (validation, authentication, etc.) - log as info/warning
        if (status === 422 || status === 413 || status === 400) {
          // Validation errors - these are expected user feedback, not application errors
          console.info(
            `Validation Response [${status}]:`,
            data?.detail || data
          );
        } else if (status === 401 || status === 403) {
          // Authentication/authorization errors
          console.warn(`Auth Error [${status}]:`, data?.detail || data);
        } else {
          // Other 4xx errors
          console.warn(`Client Error [${status}]:`, data?.detail || data);
        }
      } else if (status >= 500) {
        // Server errors - these are actual application errors
        console.error(`Server Error [${status}]:`, data?.detail || data);
      }
    } else if (error.request) {
      // Request made but no response received - actual network error
      console.error("Network Error:", error.message);
    } else {
      // Something else happened - actual error
      console.error("Request Setup Error:", error.message);
    }

    // Still reject the promise so React Query can handle it properly
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
  readability_metrics: ReadabilityMetrics;
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
  chat_session_id?: string;
  use_conversation_memory?: boolean;
}

export interface SourceCitation {
  clause_id: string;
  clause_number?: number;
  category?: string;
  snippet: string;
  relevance_score: number;
}

export interface AnswerResponse {
  answer: string;
  used_clause_ids: string[];
  used_clause_numbers?: number[];
  sources: SourceCitation[];
  confidence: number;
  response_time_ms?: number;
  token_usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  additional_insights?: string;
}

// Batch Processing Types
export interface BatchUploadResponse {
  uploads: DocumentUploadResponse[];
  successful_count: number;
  failed_count: number;
  total_count: number;
}

export interface QueueItem {
  doc_id: string;
  filename: string;
  file_size: number;
  mime_type: string;
  session_id?: string;
  status: "queued" | "processing" | "completed" | "failed";
  created_at: string;
  started_at?: string;
  completed_at?: string;
  processing_time?: number;
  wait_time: number;
  progress: number;
  error_message?: string;
}

export interface QueueStatus {
  total_items: number;
  queued_items: number;
  processing_items: number;
  completed_items: number;
  failed_items: number;
  max_concurrent: number;
  avg_processing_time?: number;
  estimated_wait_time?: number;
}

export interface QueueStatusResponse {
  queue_status: QueueStatus;
}

export interface QueueItemsResponse {
  queue_items: QueueItem[];
}

export interface QueueItemResponse {
  queue_item: QueueItem;
}

// Q&A Response Extended
export interface AnswerResponseExtended {
  answer: string;
  used_clause_ids: string[];
  used_clause_numbers?: number[];
  confidence: number;
  sources: SourceCitation[];
  timestamp: string;
  additional_insights?: string;
  chat_session_id?: string;
  conversation_context_used?: boolean;
}

export interface QAHistoryItem {
  timestamp: string;
  question: string;
  answer: string;
  clause_ids: string[];
}

// Chat Session Types
export type MessageRole = "user" | "assistant" | "system";

export interface ChatMessage {
  message_id: string;
  role: MessageRole;
  content: string;
  timestamp: string;
  sources?: Array<{
    clause_id?: string;
    clause_number?: number;
    category?: string;
    snippet: string;
    relevance_score: number;
  }>;
  metadata?: Record<string, unknown>;
}

export interface DocumentContext {
  doc_id: string;
  selected_at: string;
  metadata?: Record<string, unknown>;
}

export interface ChatSession {
  session_id: string;
  created_at: string;
  last_activity: string;
  messages: ChatMessage[];
  document_contexts: DocumentContext[];
  total_messages: number;
  metadata?: Record<string, unknown>;
}

export interface CreateChatSessionRequest {
  selected_document_ids?: string[];
  title?: string;
  user_id?: string;
  metadata?: Record<string, unknown>;
}

export interface AddMessageRequest {
  role: MessageRole;
  content: string;
  sources?: Array<{
    clause_id?: string;
    clause_number?: number;
    category?: string;
    snippet: string;
    relevance_score: number;
  }>;
  metadata?: Record<string, unknown>;
}

export interface ChatSessionListResponse {
  sessions: Array<{
    session_id: string;
    created_at: string;
    last_activity: string;
    total_messages: number;
    latest_message_preview?: string;
    document_count: number;
  }>;
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

  /**
   * Upload multiple documents for batch processing
   */
  async batchUploadDocuments(
    files: File[],
    sessionId?: string
  ): Promise<BatchUploadResponse> {
    const formData = new FormData();

    files.forEach((file) => {
      formData.append("files", file);
    });

    if (sessionId) {
      formData.append("session_id", sessionId);
    }

    const response: AxiosResponse<BatchUploadResponse> = await apiClient.post(
      "/api/v1/documents/ingest/batch",
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
        timeout: 300000, // 5 minutes for batch upload
      }
    );

    return response.data;
  },

  /**
   * Get current queue status
   */
  async getQueueStatus(): Promise<QueueStatusResponse> {
    const response: AxiosResponse<QueueStatusResponse> = await apiClient.get(
      "/api/v1/documents/queue/status"
    );

    return response.data;
  },

  /**
   * Get all items in the queue
   */
  async getQueueItems(): Promise<QueueItemsResponse> {
    const response: AxiosResponse<QueueItemsResponse> = await apiClient.get(
      "/api/v1/documents/queue/items"
    );

    return response.data;
  },

  /**
   * Cancel a queued document processing
   */
  async cancelQueueItem(docId: string): Promise<QueueItemResponse> {
    const response: AxiosResponse<QueueItemResponse> = await apiClient.delete(
      `/api/v1/documents/queue/cancel/${docId}`
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
// CHAT SESSION API
// ========================================

export const chatSessionApi = {
  /**
   * Create a new chat session
   */
  async createSession(
    request?: CreateChatSessionRequest
  ): Promise<ChatSession> {
    const response: AxiosResponse<ChatSession> = await apiClient.post(
      "/api/v1/chat/sessions",
      request || {}
    );

    return response.data;
  },

  /**
   * Get a specific chat session with full conversation history
   */
  async getSession(sessionId: string): Promise<ChatSession> {
    const response: AxiosResponse<ChatSession> = await apiClient.get(
      `/api/v1/chat/sessions/${sessionId}`
    );

    return response.data;
  },

  /**
   * List recent chat sessions
   */
  async listSessions(limit: number = 20): Promise<ChatSessionListResponse> {
    const response: AxiosResponse<ChatSessionListResponse> =
      await apiClient.get(`/api/v1/chat/sessions?limit=${limit}`);

    return response.data;
  },

  /**
   * Add a message to a chat session
   */
  async addMessage(
    sessionId: string,
    message: AddMessageRequest
  ): Promise<ChatMessage> {
    const response: AxiosResponse<ChatMessage> = await apiClient.post(
      `/api/v1/chat/sessions/${sessionId}/messages`,
      message
    );

    return response.data;
  },

  /**
   * Update document context for a chat session
   */
  async updateDocumentContext(
    sessionId: string,
    docIds: string[]
  ): Promise<ChatSession> {
    const response: AxiosResponse<ChatSession> = await apiClient.put(
      `/api/v1/chat/sessions/${sessionId}/documents`,
      { document_ids: docIds }
    );

    return response.data;
  },

  /**
   * Delete a chat session
   */
  async deleteSession(sessionId: string): Promise<void> {
    await apiClient.delete(`/api/v1/chat/sessions/${sessionId}`);
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

  // Convert risk levels to numeric values (0.0 to 1.0)
  const riskValues = clauses.map((clause) => {
    switch (clause.risk_level) {
      case "low":
        return 0.15;
      case "moderate":
        return 0.55;
      case "attention":
        return 0.85;
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
        // For extra cells, use average risk of existing clauses
        const avgRisk =
          riskValues.reduce((sum, val) => sum + val, 0) / riskValues.length;
        rowData.push(Math.min(avgRisk, 0.3)); // Cap at moderate level for filler
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
  limit: number = 5
) {
  if (!clauses || clauses.length === 0) {
    return [];
  }

  // Sort by risk level (attention first, then moderate)
  return clauses
    .filter(
      (clause) =>
        clause.risk_level === "attention" || clause.risk_level === "moderate"
    )
    .sort((a, b) => {
      const riskOrder = { attention: 3, moderate: 2, low: 1 };
      const riskDiff = riskOrder[b.risk_level] - riskOrder[a.risk_level];
      // If same risk level, sort by category name for consistency
      if (riskDiff === 0) {
        return a.category.localeCompare(b.category);
      }
      return riskDiff;
    })
    .slice(0, limit)
    .map((clause) => ({
      k: clause.category,
      risk: clause.risk_level === "attention" ? 0.85 : 0.55,
      clauseId: clause.clause_id,
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

// ========================================
// NEGOTIATION TYPES
// ========================================

export type AlternativeType = "balanced" | "protective" | "simplified";

export interface NegotiationAlternative {
  alternative_id?: string;
  alternative_text: string;
  strategic_benefit: string;
  risk_reduction: string;
  implementation_notes: string;
  confidence: number;
  alternative_type: AlternativeType;
  created_at?: string;
}

export interface RiskAnalysisSummary {
  risk_level: RiskLevel;
  confidence: number;
  risk_score: number;
  detected_keywords: string[];
  risk_factors: string[];
}

export interface NegotiationResponse {
  negotiation_id?: string;
  original_clause: string;
  original_risk_level: RiskLevel;
  alternatives: NegotiationAlternative[];
  risk_analysis?: RiskAnalysisSummary;
  generation_time: number;
  model_used: string;
  context: Record<string, unknown>;
  created_at?: string;
  clause_id?: string;
  doc_id?: string;
}

export interface NegotiationRequest {
  clause_text: string;
  clause_category?: string;
  risk_level?: RiskLevel;
  document_context?: Record<string, unknown>;
  user_preferences?: Record<string, unknown>;
  clause_id?: string;
  doc_id?: string;
}

export interface QuickAlternativeRequest {
  clause_text: string;
  clause_category?: string;
}

export interface QuickAlternativeResponse {
  original_clause: string;
  alternatives: Array<{
    text: string;
    benefit: string;
    type: AlternativeType;
    risk_reduction: string;
  }>;
  generation_time: number;
}

export interface BatchNegotiationRequest {
  clause_ids: string[];
  doc_id: string;
  document_context?: Record<string, unknown>;
  user_preferences?: Record<string, unknown>;
  max_concurrent?: number;
}

export interface BatchNegotiationResponse {
  doc_id: string;
  total_clauses: number;
  successful: number;
  failed: number;
  negotiations: NegotiationResponse[];
  generation_time: number;
  created_at?: string;
}

export interface SaveNegotiationRequest {
  negotiation_id: string;
  doc_id: string;
  clause_id: string;
  selected_alternative_id?: string;
  user_feedback?: string;
  was_helpful?: boolean;
  metadata?: Record<string, unknown>;
}

export interface NegotiationHistory {
  negotiation_id: string;
  doc_id: string;
  clause_id: string;
  original_clause: string;
  alternatives: NegotiationAlternative[];
  selected_alternative_id?: string;
  user_feedback?: string;
  was_helpful?: boolean;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at?: string;
}

export interface NegotiationHistoryResponse {
  doc_id: string;
  total_negotiations: number;
  negotiations: NegotiationHistory[];
  query_time: number;
}

// ========================================
// NEGOTIATION API
// ========================================

export const negotiationApi = {
  /**
   * Generate negotiation alternatives for a single clause
   */
  generateAlternatives: async (
    request: NegotiationRequest
  ): Promise<NegotiationResponse> => {
    const response: AxiosResponse<NegotiationResponse> = await apiClient.post(
      "/api/v1/negotiation/generate",
      request
    );
    return response.data;
  },

  /**
   * Quick alternative generation (simplified for demo)
   */
  generateQuickAlternatives: async (
    request: QuickAlternativeRequest
  ): Promise<QuickAlternativeResponse> => {
    const response: AxiosResponse<QuickAlternativeResponse> =
      await apiClient.post("/api/v1/negotiation/quick", request);
    return response.data;
  },

  /**
   * Generate alternatives for multiple clauses in batch
   */
  generateBatchAlternatives: async (
    request: BatchNegotiationRequest
  ): Promise<BatchNegotiationResponse> => {
    const response: AxiosResponse<BatchNegotiationResponse> =
      await apiClient.post("/api/v1/negotiation/batch", request);
    return response.data;
  },

  /**
   * Save negotiation interaction with user feedback
   */
  saveNegotiation: async (
    request: SaveNegotiationRequest
  ): Promise<{ message: string; negotiation_id: string }> => {
    const response = await apiClient.post("/api/v1/negotiation/save", request);
    return response.data;
  },

  /**
   * Get negotiation history for a document or clause
   */
  getNegotiationHistory: async (
    docId: string,
    clauseId?: string
  ): Promise<NegotiationHistoryResponse> => {
    const params = clauseId ? { clause_id: clauseId } : {};
    const response: AxiosResponse<NegotiationHistoryResponse> =
      await apiClient.get(`/api/v1/negotiation/history/${docId}`, { params });
    return response.data;
  },

  /**
   * Get negotiation statistics for a document
   */
  getNegotiationStats: async (
    docId: string
  ): Promise<{
    doc_id: string;
    total_negotiations: number;
    total_alternatives: number;
    selection_rate: number;
    helpful_rate: number;
    most_common_categories: Array<{ category: string; count: number }>;
  }> => {
    const response = await apiClient.get(`/api/v1/negotiation/stats/${docId}`);
    return response.data;
  },
};

const apiExports = {
  documentApi,
  qaApi,
  chatSessionApi,
  negotiationApi,
  generateRiskHeatmap,
  getTopRiskyClauses,
  formatProcessingMessage,
  isDocumentReady,
  isDocumentFailed,
  getStatusColor,
};

export default apiExports;
