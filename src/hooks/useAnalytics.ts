import { useQuery } from "@tanstack/react-query";
import {
  fetchMetricsSummary,
  fetchMetricsTrends,
  fetchMetricsDetails,
} from "@/lib/api";
import type { UseAnalyticsHookReturn } from "@/types/analytics";

export function useAnalytics(hours: number = 24): UseAnalyticsHookReturn {
  // Fetch summary metrics
  const {
    data: summary,
    isLoading: summaryLoading,
    isFetching: summaryFetching,
    error: summaryError,
    refetch: refetchSummary,
    dataUpdatedAt: summaryUpdatedAt,
  } = useQuery({
    queryKey: ["analytics", "summary", hours],
    queryFn: () => fetchMetricsSummary(hours),
    // T008: Page Visibility API integration - pause refetch when tab hidden
    refetchInterval: () =>
      typeof window !== "undefined" && document.visibilityState === "visible"
        ? 30000
        : false,
    staleTime: 20000,
  });

  // Fetch trends
  const {
    data: trends,
    isLoading: trendsLoading,
    isFetching: trendsFetching,
    error: trendsError,
    dataUpdatedAt: trendsUpdatedAt,
  } = useQuery({
    queryKey: ["analytics", "trends", hours],
    queryFn: () => fetchMetricsTrends(hours, hours > 48 ? "daily" : "hourly"),
    refetchInterval: () =>
      typeof window !== "undefined" && document.visibilityState === "visible"
        ? 30000
        : false,
    staleTime: 20000,
  });

  // Fetch detailed metrics
  const {
    data: details,
    isLoading: detailsLoading,
    isFetching: detailsFetching,
    error: detailsError,
    dataUpdatedAt: detailsUpdatedAt,
  } = useQuery({
    queryKey: ["analytics", "details", hours],
    queryFn: () => fetchMetricsDetails(hours),
    refetchInterval: () =>
      typeof window !== "undefined" && document.visibilityState === "visible"
        ? 30000
        : false,
    staleTime: 20000,
  });

  const isLoading = summaryLoading || trendsLoading || detailsLoading;
  const isFetching = summaryFetching || trendsFetching || detailsFetching;
  const error = summaryError || trendsError || detailsError;

  // Calculate lastUpdated from the most recent dataUpdatedAt
  const mostRecentUpdate = Math.max(
    summaryUpdatedAt || 0,
    trendsUpdatedAt || 0,
    detailsUpdatedAt || 0
  );
  const lastUpdated = mostRecentUpdate > 0 ? new Date(mostRecentUpdate) : null;

  const refetch = () => {
    refetchSummary();
  };

  return {
    summary: summary || null,
    trends: trends || null,
    details: details || null,
    isLoading,
    isFetching,
    error: error as Error | null,
    refetch,
    lastUpdated,
  };
}
