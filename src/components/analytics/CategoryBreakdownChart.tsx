"use client";

import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { BarChart3 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { AnalyticsSkeleton } from "./AnalyticsSkeleton";
import { EmptyState } from "./EmptyState";
import { ChartErrorBoundary } from "./ChartErrorBoundary";
import type { CategoryBreakdownChartProps } from "@/types/analytics";

export function CategoryBreakdownChart({
  data,
  isLoading,
  height = 400,
}: CategoryBreakdownChartProps) {
  return (
    <ChartErrorBoundary>
      <Card className="p-6 !bg-zinc-900 !border-zinc-800">
        <h3 className="text-lg font-semibold mb-4 text-white">
          Top Clause Categories
        </h3>
        {isLoading ? (
          <AnalyticsSkeleton variant="bar-chart" height={height} />
        ) : data.length > 0 ? (
          <ResponsiveContainer width="100%" height={height}>
            <BarChart data={data as never}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis
                dataKey="name"
                angle={-45}
                textAnchor="end"
                height={100}
                stroke="#888"
              />
              <YAxis stroke="#888" />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#1a1a1a",
                  border: "1px solid #333",
                  borderRadius: "6px",
                }}
              />
              <Legend />
              <Bar dataKey="count" fill="#3b82f6" name="Clause Count" />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <EmptyState
            icon={<BarChart3 size={48} />}
            title="Clause categories will appear after processing"
            description="Upload legal documents and wait for clause analysis to complete. Categories will be extracted automatically."
          />
        )}
      </Card>
    </ChartErrorBoundary>
  );
}
