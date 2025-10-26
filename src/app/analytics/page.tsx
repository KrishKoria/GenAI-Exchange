"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAnalytics } from "@/hooks/useAnalytics";
import { formatTimestamp } from "@/lib/chart-data-transforms";
import { DocumentTrendChart } from "@/components/analytics/DocumentTrendChart";
import { RiskDistributionChart } from "@/components/analytics/RiskDistributionChart";
import { CategoryBreakdownChart } from "@/components/analytics/CategoryBreakdownChart";
import { AnalyticsSkeleton } from "@/components/analytics/AnalyticsSkeleton";
import { RISK_COLORS } from "@/types/analytics";

const COLORS = [RISK_COLORS.low, RISK_COLORS.moderate, RISK_COLORS.attention];
const RISK_LABELS: Record<string, string> = {
  low: "Low Risk",
  moderate: "Moderate Risk",
  attention: "High Risk",
};

export default function AnalyticsPage() {
  const [timeRange, setTimeRange] = useState<24 | 168>(24); // 24h or 7d
  const {
    summary,
    trends,
    details,
    isLoading,
    isFetching,
    error,
    lastUpdated,
  } = useAnalytics(timeRange);

  if (error) {
    return (
      <div className="container mx-auto p-6 bg-[#0B0B0B] min-h-screen">
        <Card className="p-6 bg-red-950 border-red-900">
          <h2 className="text-lg font-semibold text-red-200 mb-2">
            Error Loading Analytics
          </h2>
          <p className="text-red-300">{error.message}</p>
        </Card>
      </div>
    );
  }

  // Transform risk distribution for pie chart
  const riskData = details?.risk_distribution
    ? [
        {
          name: RISK_LABELS.low,
          value: details.risk_distribution.low,
          color: COLORS[0],
        },
        {
          name: RISK_LABELS.moderate,
          value: details.risk_distribution.moderate,
          color: COLORS[1],
        },
        {
          name: RISK_LABELS.attention,
          value: details.risk_distribution.attention,
          color: COLORS[2],
        },
      ]
    : [];

  // Transform category distribution for bar chart
  const categoryData =
    details?.top_categories.map(
      (cat: { category: string; count: number; avg_risk_score: number }) => ({
        name: cat.category,
        count: cat.count,
        avgRisk: (cat.avg_risk_score * 100).toFixed(1),
      })
    ) || [];

  // Transform event trends for line chart
  const eventTrendData =
    trends?.event_trends
      .find((t: { event_type: string }) => t.event_type === "document_uploaded")
      ?.data_points.map((dp: { label: string; value: number }) => ({
        label: dp.label,
        documents: dp.value,
      })) || [];

  return (
    <div className="container mx-auto p-6 space-y-6 relative bg-[#0B0B0B] text-white min-h-screen">
      {/* Loading Overlay - shows during background refetch */}
      {isFetching && !isLoading && (
        <div className="absolute top-6 right-6 z-10">
          <div className="bg-primary text-primary-foreground px-4 py-2 rounded-md shadow-lg flex items-center gap-2">
            <div className="animate-spin h-4 w-4 border-2 border-current border-t-transparent rounded-full"></div>
            <span className="text-sm font-medium">Updating...</span>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold text-white">Analytics Dashboard</h1>
          <p className="text-gray-400">
            Real-time insights into document processing and risk analysis
          </p>
        </div>

        {/* Time Range Selector */}
        <div className="flex gap-2">
          <Button
            onClick={() => setTimeRange(24)}
            variant={timeRange === 24 ? "default" : "outline"}
            className={
              timeRange === 24
                ? "bg-white text-black hover:bg-gray-100"
                : "border-zinc-700 text-gray-300 hover:bg-zinc-800 hover:text-white"
            }
          >
            Last 24 Hours
          </Button>
          <Button
            onClick={() => setTimeRange(168)}
            variant={timeRange === 168 ? "default" : "outline"}
            className={
              timeRange === 168
                ? "bg-white text-black hover:bg-gray-100"
                : "border-zinc-700 text-gray-300 hover:bg-zinc-800 hover:text-white"
            }
          >
            Last 7 Days
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      {isLoading ? (
        <AnalyticsSkeleton variant="metric-card" count={4} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="p-6 !bg-zinc-900 !border-zinc-800">
            <div className="text-sm font-medium text-gray-400">
              Documents Processed
            </div>
            <div className="text-3xl font-bold mt-2 text-white">
              {summary?.total_documents || 0}
            </div>
            <p className="text-xs text-gray-500 mt-1">
              {summary?.total_clauses || 0} clauses analyzed
            </p>
          </Card>

          <Card className="p-6 !bg-zinc-900 !border-zinc-800">
            <div className="text-sm font-medium text-gray-400">
              Questions Asked
            </div>
            <div className="text-3xl font-bold mt-2 text-white">
              {summary?.total_questions || 0}
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Avg confidence:{" "}
              {summary ? (summary.avg_confidence * 100).toFixed(1) : "0"}%
            </p>
          </Card>

          <Card className="p-6 !bg-zinc-900 !border-zinc-800">
            <div className="text-sm font-medium text-gray-400">
              High-Risk Clauses
            </div>
            <div className="text-3xl font-bold mt-2 text-red-500">
              {summary?.total_risks || 0}
            </div>
            <p className="text-xs text-gray-500 mt-1">
              {summary ? summary.high_risk_percentage.toFixed(1) : "0"}% of
              total
            </p>
          </Card>

          <Card className="p-6 !bg-zinc-900 !border-zinc-800">
            <div className="text-sm font-medium text-gray-400">
              Avg Processing Time
            </div>
            <div className="text-3xl font-bold mt-2 text-white">
              {summary
                ? (summary.avg_processing_time_ms / 1000).toFixed(1)
                : "0"}
              s
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Q&A:{" "}
              {summary ? (summary.avg_response_time_ms / 1000).toFixed(1) : "0"}
              s
            </p>
          </Card>
        </div>
      )}

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <DocumentTrendChart data={eventTrendData} isLoading={isLoading} />
        <RiskDistributionChart data={riskData} isLoading={isLoading} />
      </div>

      {/* Category Breakdown */}
      <CategoryBreakdownChart data={categoryData} isLoading={isLoading} />

      {/* Last Updated */}
      {lastUpdated && (
        <p className="text-xs text-gray-500 text-center">
          Last updated: {formatTimestamp(lastUpdated.toISOString())}
        </p>
      )}
    </div>
  );
}
