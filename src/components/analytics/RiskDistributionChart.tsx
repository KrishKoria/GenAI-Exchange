"use client";

import React from "react";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { PieChart as PieChartIcon } from "lucide-react";
import { Card } from "@/components/ui/card";
import { AnalyticsSkeleton } from "./AnalyticsSkeleton";
import { EmptyState } from "./EmptyState";
import { ChartErrorBoundary } from "./ChartErrorBoundary";
import type { RiskDistributionChartProps } from "@/types/analytics";

export function RiskDistributionChart({
  data,
  isLoading,
  height = 300,
}: RiskDistributionChartProps) {
  const hasData = data.length > 0 && data.some((d) => d.value > 0);

  return (
    <ChartErrorBoundary>
      <Card className="p-6 !bg-zinc-900 !border-zinc-800">
        <h3 className="text-lg font-semibold mb-4 text-white">
          Risk Distribution
        </h3>
        {isLoading ? (
          <AnalyticsSkeleton variant="pie-chart" height={height} />
        ) : hasData ? (
          <ResponsiveContainer width="100%" height={height}>
            <PieChart>
              <Pie
                data={data as never}
                cx="50%"
                cy="50%"
                labelLine={false}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1a1a1a",
                  border: "1px solid #333",
                  borderRadius: "6px",
                }}
              />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        ) : (
          <EmptyState
            icon={<PieChartIcon size={48} />}
            title="No clauses analyzed yet"
            description="Upload legal documents to see risk analysis and clause distribution."
          />
        )}
      </Card>
    </ChartErrorBoundary>
  );
}
