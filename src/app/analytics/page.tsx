"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { useAnalytics } from "@/hooks/useAnalytics";

const COLORS = ["#10b981", "#f59e0b", "#ef4444"];
const RISK_LABELS: Record<string, string> = {
  low: "Low Risk",
  moderate: "Moderate Risk",
  attention: "High Risk",
};

export default function AnalyticsPage() {
  const [timeRange, setTimeRange] = useState<24 | 168>(24); // 24h or 7d
  const { summary, trends, details, isLoading, error } =
    useAnalytics(timeRange);

  if (error) {
    return (
      <div className="container mx-auto p-6">
        <Card className="p-6 bg-red-50 border-red-200">
          <h2 className="text-lg font-semibold text-red-900 mb-2">
            Error Loading Analytics
          </h2>
          <p className="text-red-700">{error.message}</p>
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
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Analytics Dashboard</h1>
          <p className="text-muted-foreground">
            Real-time insights into document processing and risk analysis
          </p>
        </div>

        {/* Time Range Selector */}
        <div className="flex gap-2">
          <button
            onClick={() => setTimeRange(24)}
            className={`px-4 py-2 rounded-md ${
              timeRange === 24
                ? "bg-primary text-primary-foreground"
                : "bg-secondary"
            }`}
          >
            Last 24 Hours
          </button>
          <button
            onClick={() => setTimeRange(168)}
            className={`px-4 py-2 rounded-md ${
              timeRange === 168
                ? "bg-primary text-primary-foreground"
                : "bg-secondary"
            }`}
          >
            Last 7 Days
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-6">
          <div className="text-sm font-medium text-muted-foreground">
            Documents Processed
          </div>
          <div className="text-3xl font-bold mt-2">
            {isLoading ? "..." : summary?.total_documents || 0}
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            {summary?.total_clauses || 0} clauses analyzed
          </p>
        </Card>

        <Card className="p-6">
          <div className="text-sm font-medium text-muted-foreground">
            Questions Asked
          </div>
          <div className="text-3xl font-bold mt-2">
            {isLoading ? "..." : summary?.total_questions || 0}
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Avg confidence:{" "}
            {summary ? (summary.avg_confidence * 100).toFixed(1) : "0"}%
          </p>
        </Card>

        <Card className="p-6">
          <div className="text-sm font-medium text-muted-foreground">
            High-Risk Clauses
          </div>
          <div className="text-3xl font-bold mt-2 text-red-600">
            {isLoading ? "..." : summary?.total_risks || 0}
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            {summary ? summary.high_risk_percentage.toFixed(1) : "0"}% of total
          </p>
        </Card>

        <Card className="p-6">
          <div className="text-sm font-medium text-muted-foreground">
            Avg Processing Time
          </div>
          <div className="text-3xl font-bold mt-2">
            {isLoading
              ? "..."
              : summary
              ? (summary.avg_processing_time_ms / 1000).toFixed(1)
              : "0"}
            s
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Q&A:{" "}
            {summary ? (summary.avg_response_time_ms / 1000).toFixed(1) : "0"}s
          </p>
        </Card>
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Document Upload Trend */}
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-4">Document Upload Trend</h3>
          {isLoading ? (
            <div className="h-64 flex items-center justify-center text-muted-foreground">
              Loading...
            </div>
          ) : eventTrendData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={eventTrendData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="documents"
                  stroke="#3b82f6"
                  strokeWidth={2}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-64 flex items-center justify-center text-muted-foreground">
              No data available
            </div>
          )}
        </Card>

        {/* Risk Distribution */}
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-4">Risk Distribution</h3>
          {isLoading ? (
            <div className="h-64 flex items-center justify-center text-muted-foreground">
              Loading...
            </div>
          ) : riskData.length > 0 && riskData.some((d) => d.value > 0) ? (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={riskData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={(entry) => `${entry.name}: ${entry.value}`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {riskData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-64 flex items-center justify-center text-muted-foreground">
              No risk data available
            </div>
          )}
        </Card>
      </div>

      {/* Category Breakdown */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Top Clause Categories</h3>
        {isLoading ? (
          <div className="h-80 flex items-center justify-center text-muted-foreground">
            Loading...
          </div>
        ) : categoryData.length > 0 ? (
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={categoryData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" angle={-45} textAnchor="end" height={100} />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="count" fill="#3b82f6" name="Clause Count" />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-80 flex items-center justify-center text-muted-foreground">
            No category data available
          </div>
        )}
      </Card>

      {/* Last Updated */}
      {summary && (
        <p className="text-xs text-muted-foreground text-center">
          Last updated: {new Date(summary.last_updated).toLocaleString()}
        </p>
      )}
    </div>
  );
}
