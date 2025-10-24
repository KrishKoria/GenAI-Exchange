import { useQuery } from "@tanstack/react-query";
import {
  fetchMetricsSummary,
  fetchMetricsTrends,
  fetchMetricsDetails,
} from "@/lib/api";

interface MetricsSummary {
  total_documents: number;
  total_clauses: number;
  total_questions: number;
  total_risks: number;
  avg_processing_time_ms: number;
  avg_response_time_ms: number;
  avg_confidence: number;
  high_risk_percentage: number;
  period_start: string;
  period_end: string;
  last_updated: string;
}

interface TrendDataPoint {
  timestamp: string;
  value: number;
  label: string;
}

interface EventTypeTrend {
  event_type: string;
  data_points: TrendDataPoint[];
  total_count: number;
}

interface MetricsTrends {
  event_trends: EventTypeTrend[];
  processing_time_trend: TrendDataPoint[];
  response_time_trend: TrendDataPoint[];
  confidence_trend: TrendDataPoint[];
  risk_distribution: Record<string, number>;
  category_distribution: Record<string, number>;
  period_start: string;
  period_end: string;
  granularity: string;
}

interface CategoryBreakdown {
  category: string;
  count: number;
  avg_risk_score: number;
  high_risk_count: number;
}

interface RiskDistribution {
  low: number;
  moderate: number;
  attention: number;
  total: number;
}

interface MetricsDetails {
  summary: MetricsSummary;
  risk_distribution: RiskDistribution;
  top_categories: CategoryBreakdown[];
  recent_documents: unknown[];
  recent_high_risks: unknown[];
  last_updated: string;
}

interface AnalyticsData {
  summary: MetricsSummary | null;
  trends: MetricsTrends | null;
  details: MetricsDetails | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useAnalytics(hours: number = 24): AnalyticsData {
  // Fetch summary metrics
  const {
    data: summary,
    isLoading: summaryLoading,
    error: summaryError,
    refetch: refetchSummary,
  } = useQuery({
    queryKey: ["analytics", "summary", hours],
    queryFn: () => fetchMetricsSummary(hours),
    refetchInterval: 30000, // Auto-refresh every 30 seconds
    staleTime: 20000,
  });

  // Fetch trends
  const {
    data: trends,
    isLoading: trendsLoading,
    error: trendsError,
  } = useQuery({
    queryKey: ["analytics", "trends", hours],
    queryFn: () => fetchMetricsTrends(hours, hours > 48 ? "daily" : "hourly"),
    refetchInterval: 30000,
    staleTime: 20000,
  });

  // Fetch detailed metrics
  const {
    data: details,
    isLoading: detailsLoading,
    error: detailsError,
  } = useQuery({
    queryKey: ["analytics", "details", hours],
    queryFn: () => fetchMetricsDetails(hours),
    refetchInterval: 30000,
    staleTime: 20000,
  });

  const isLoading = summaryLoading || trendsLoading || detailsLoading;
  const error = summaryError || trendsError || detailsError;

  const refetch = () => {
    refetchSummary();
  };

  return {
    summary: summary || null,
    trends: trends || null,
    details: details || null,
    isLoading,
    error: error as Error | null,
    refetch,
  };
}
