/**
 * Analytics Dashboard Type Definitions
 *
 * Comprehensive TypeScript interfaces for analytics data structures,
 * API responses, chart data transformations, and component props.
 *
 * @module types/analytics
 */

// ========================================
// API Response Types (from backend)
// ========================================

export interface MetricsSummary {
  total_documents: number;
  total_clauses: number;
  total_questions: number;
  total_risks: number;
  avg_processing_time_ms: number;
  avg_response_time_ms: number;
  avg_confidence: number; // 0.0 - 1.0
  high_risk_percentage: number; // 0.0 - 100.0
  period_start: string; // ISO 8601
  period_end: string; // ISO 8601
  last_updated: string; // ISO 8601
}

export interface TrendDataPoint {
  timestamp: string; // ISO 8601
  value: number;
  label: string; // Human-readable e.g., "10:00 AM", "Mon 10/26"
}

export interface EventTypeTrend {
  event_type:
    | "document_uploaded"
    | "clause_analyzed"
    | "question_asked"
    | "risk_detected";
  data_points: TrendDataPoint[];
  total_count: number;
}

export interface MetricsTrends {
  event_trends: EventTypeTrend[];
  processing_time_trend: TrendDataPoint[];
  response_time_trend: TrendDataPoint[];
  confidence_trend: TrendDataPoint[];
  risk_distribution: Record<string, number>;
  category_distribution: Record<string, number>;
  period_start: string;
  period_end: string;
  granularity: "hourly" | "daily";
}

export interface RiskDistribution {
  low: number;
  moderate: number;
  attention: number;
  total: number;
}

export interface CategoryBreakdown {
  category: string;
  count: number;
  avg_risk_score: number; // 0.0 - 1.0
  high_risk_count: number;
}

export interface MetricsDetails {
  summary: MetricsSummary;
  risk_distribution: RiskDistribution;
  top_categories: CategoryBreakdown[];
  recent_documents: unknown[];
  recent_high_risks: unknown[];
  last_updated: string;
}

// ========================================
// Chart Data Types (transformed for Recharts)
// ========================================

export interface DocumentTrendDataPoint {
  label: string; // X-axis label
  documents: number; // Y-axis value
  timestamp?: string; // Original ISO timestamp for tooltip
}

export type DocumentTrendChartData = DocumentTrendDataPoint[];

export interface RiskDistributionDataPoint {
  name: string; // "Low Risk" | "Moderate Risk" | "High Risk"
  value: number;
  color: string;
  percentage?: number;
}

export type RiskDistributionChartData = RiskDistributionDataPoint[];

export interface CategoryBreakdownDataPoint {
  name: string; // Category name
  count: number;
  avgRisk: string; // Formatted percentage
  avgRiskValue?: number; // Original 0-1 value
}

export type CategoryBreakdownChartData = CategoryBreakdownDataPoint[];

// ========================================
// Component Props
// ========================================

export interface AnalyticsTimeRangeSelectorProps {
  value: 24 | 168;
  onChange: (timeRange: 24 | 168) => void;
  disabled?: boolean;
}

export interface DocumentTrendChartProps {
  data: DocumentTrendChartData;
  isLoading?: boolean;
  height?: number;
  showTooltip?: boolean;
  "aria-label"?: string;
}

export interface RiskDistributionChartProps {
  data: RiskDistributionChartData;
  isLoading?: boolean;
  height?: number;
  showLegend?: boolean;
  showTooltip?: boolean;
  "aria-label"?: string;
}

export interface CategoryBreakdownChartProps {
  data: CategoryBreakdownChartData;
  isLoading?: boolean;
  height?: number;
  showTooltip?: boolean;
  "aria-label"?: string;
}

export interface EmptyStateAction {
  label: string;
  onClick: () => void;
}

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: EmptyStateAction;
}

export type SkeletonVariant =
  | "metric-card"
  | "line-chart"
  | "pie-chart"
  | "bar-chart";

export interface AnalyticsSkeletonProps {
  variant: SkeletonVariant;
  count?: number;
  height?: number | string;
}

// ========================================
// Hook Return Types
// ========================================

export interface UseAnalyticsHookReturn {
  summary: MetricsSummary | null;
  trends: MetricsTrends | null;
  details: MetricsDetails | null;
  isLoading: boolean; // Initial load
  isFetching: boolean; // Background refetch
  error: Error | null;
  refetch: () => void;
  lastUpdated: Date | null;
}

// ========================================
// Page State Types
// ========================================

export interface AnalyticsPageState {
  timeRange: 24 | 168;
  isRefreshing: boolean;
  lastError: Error | null;
  lastUpdated: Date | null;
}

// ========================================
// Constants
// ========================================

export const RISK_LABELS = {
  low: "Low Risk",
  moderate: "Moderate Risk",
  attention: "High Risk",
} as const;

export const RISK_COLORS = {
  low: "#10b981",
  moderate: "#f59e0b",
  attention: "#ef4444",
} as const;

export const TIME_RANGE_OPTIONS = [
  { value: 24, label: "Last 24 Hours" },
  { value: 168, label: "Last 7 Days" },
] as const;
