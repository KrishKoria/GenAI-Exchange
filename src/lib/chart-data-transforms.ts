/**
 * Chart Data Transformation Functions
 *
 * Type-safe functions to transform backend API responses into
 * Recharts-compatible data structures with proper null handling
 * and formatting.
 *
 * @module lib/chart-data-transforms
 */

import {
  MetricsTrends,
  MetricsDetails,
  DocumentTrendChartData,
  RiskDistributionChartData,
  CategoryBreakdownChartData,
  RISK_LABELS,
  RISK_COLORS,
} from "@/types/analytics";

/**
 * Transform document upload trends for LineChart
 *
 * Safely extracts document_uploaded events from trends data and
 * formats them for Recharts LineChart consumption.
 *
 * @param trends - Metrics trends from API (may be null)
 * @returns Array of chart data points (empty array if no data)
 */
export function transformDocumentTrend(
  trends: MetricsTrends | null | undefined
): DocumentTrendChartData {
  if (!trends?.event_trends || !Array.isArray(trends.event_trends)) {
    return [];
  }

  const documentTrend = trends.event_trends.find(
    (t) => t.event_type === "document_uploaded"
  );

  if (
    !documentTrend?.data_points ||
    !Array.isArray(documentTrend.data_points)
  ) {
    return [];
  }

  return documentTrend.data_points.map((dp) => ({
    label: dp.label ?? "N/A",
    documents: Number.isFinite(dp.value) ? dp.value : 0,
    timestamp: dp.timestamp,
  }));
}

/**
 * Transform risk distribution for PieChart
 *
 * Converts risk_distribution object into array format with
 * calculated percentages, colors, and human-readable labels.
 *
 * @param details - Metrics details from API (may be null)
 * @returns Array of risk distribution data points
 */
export function transformRiskDistribution(
  details: MetricsDetails | null | undefined
): RiskDistributionChartData {
  if (!details?.risk_distribution) {
    return [];
  }

  const { low, moderate, attention, total } = details.risk_distribution;

  // Guard against invalid data
  if (total <= 0) {
    return [];
  }

  return [
    {
      name: RISK_LABELS.low,
      value: low ?? 0,
      color: RISK_COLORS.low,
      percentage: total > 0 ? Number(((low / total) * 100).toFixed(1)) : 0,
    },
    {
      name: RISK_LABELS.moderate,
      value: moderate ?? 0,
      color: RISK_COLORS.moderate,
      percentage: total > 0 ? Number(((moderate / total) * 100).toFixed(1)) : 0,
    },
    {
      name: RISK_LABELS.attention,
      value: attention ?? 0,
      color: RISK_COLORS.attention,
      percentage:
        total > 0 ? Number(((attention / total) * 100).toFixed(1)) : 0,
    },
  ].filter((item) => item.value > 0); // Only include non-zero slices
}

/**
 * Transform category breakdown for BarChart
 *
 * Formats top clause categories with counts and risk scores
 * as percentages for bar chart display.
 *
 * @param details - Metrics details from API (may be null)
 * @returns Array of category breakdown data points
 */
export function transformCategoryBreakdown(
  details: MetricsDetails | null | undefined
): CategoryBreakdownChartData {
  if (!details?.top_categories || !Array.isArray(details.top_categories)) {
    return [];
  }

  return details.top_categories.map((cat) => ({
    name: cat.category ?? "Unknown",
    count: cat.count ?? 0,
    avgRisk: `${((cat.avg_risk_score ?? 0) * 100).toFixed(1)}%`,
    avgRiskValue: cat.avg_risk_score ?? 0,
  }));
}

/**
 * Format number with thousand separators
 *
 * @param value - Number to format
 * @returns Formatted string with commas
 */
export function formatNumber(value: number | null | undefined): string {
  if (!Number.isFinite(value)) {
    return "0";
  }
  return value!.toLocaleString();
}

/**
 * Format percentage with 1 decimal place
 *
 * @param value - Number between 0-1 or 0-100
 * @param isDecimal - Whether value is 0-1 (true) or 0-100 (false)
 * @returns Formatted percentage string
 */
export function formatPercentage(
  value: number | null | undefined,
  isDecimal: boolean = true
): string {
  if (!Number.isFinite(value)) {
    return "0.0%";
  }
  const percent = isDecimal ? value! * 100 : value!;
  return `${percent.toFixed(1)}%`;
}

/**
 * Format milliseconds as seconds with 1 decimal place
 *
 * @param ms - Milliseconds value
 * @returns Formatted seconds string
 */
export function formatMillisecondsAsSeconds(
  ms: number | null | undefined
): string {
  if (!Number.isFinite(ms) || ms === null || ms === undefined) {
    return "0.0s";
  }
  return `${(ms / 1000).toFixed(1)}s`;
}

/**
 * Format ISO timestamp for display
 *
 * @param isoString - ISO 8601 timestamp
 * @returns Localized date/time string
 */
export function formatTimestamp(isoString: string | null | undefined): string {
  if (!isoString) {
    return "N/A";
  }

  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) {
      return "Invalid date";
    }
    return date.toLocaleString();
  } catch {
    return "Invalid date";
  }
}

/**
 * Check if chart data is empty
 *
 * @param data - Chart data array
 * @returns True if data is empty or all values are zero
 */
export function isChartDataEmpty(data: unknown[] | null | undefined): boolean {
  if (!Array.isArray(data) || data.length === 0) {
    return true;
  }

  // Check if all values are zero (for pie charts)
  const hasOnlyZeros = data.every((item) => {
    if (typeof item === "object" && item !== null && "value" in item) {
      return (item as { value: unknown }).value === 0;
    }
    return false;
  });

  if (hasOnlyZeros) {
    return true;
  }

  return false;
}

/**
 * Validate and sanitize chart data
 *
 * Ensures chart data meets minimum requirements for rendering.
 *
 * @param data - Raw chart data
 * @param minPoints - Minimum number of data points required
 * @returns Sanitized data or empty array
 */
export function validateChartData<T extends unknown[]>(
  data: T | null | undefined,
  minPoints: number = 1
): T | [] {
  if (!Array.isArray(data)) {
    return [];
  }

  if (data.length < minPoints) {
    return [];
  }

  return data;
}
