"use client";

import React from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { TrendingUp } from "lucide-react";
import { Card } from "@/components/ui/card";
import { AnalyticsSkeleton } from "./AnalyticsSkeleton";
import { EmptyState } from "./EmptyState";
import { ChartErrorBoundary } from "./ChartErrorBoundary";
import type { DocumentTrendChartProps } from "@/types/analytics";

export function DocumentTrendChart({
  data,
  isLoading,
  height = 300,
}: DocumentTrendChartProps) {
  return (
    <ChartErrorBoundary>
      <Card className="p-6 !bg-zinc-900 !border-zinc-800">
        <h3 className="text-lg font-semibold mb-4 text-white">
          Document Upload Trend
        </h3>
        {isLoading ? (
          <AnalyticsSkeleton variant="line-chart" height={height} />
        ) : data.length > 0 ? (
          <ResponsiveContainer width="100%" height={height}>
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey="label" stroke="#888" />
              <YAxis stroke="#888" />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1a1a1a",
                  border: "1px solid #333",
                  borderRadius: "6px",
                }}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="documents"
                stroke="#3b82f6"
                strokeWidth={2}
                name="Documents"
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <EmptyState
            icon={<TrendingUp size={48} />}
            title="No uploads during this period"
            description="Try expanding the time range to see historical data, or upload a document to get started."
          />
        )}
      </Card>
    </ChartErrorBoundary>
  );
}
