import React from "react";
import type { AnalyticsSkeletonProps } from "@/types/analytics";

// Fixed heights to prevent hydration mismatch (no Math.random())
const LINE_CHART_HEIGHTS = [65, 45, 80, 55, 90, 40, 70, 60];
const BAR_CHART_HEIGHTS = [75, 60, 85, 50, 95, 70];

/**
 * AnalyticsSkeleton Component
 *
 * Provides loading skeleton screens that match final layout dimensions
 * to prevent cumulative layout shift during data fetching.
 */
export function AnalyticsSkeleton({
  variant,
  count = 1,
  height = "auto",
}: AnalyticsSkeletonProps) {
  if (variant === "metric-card") {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: count }).map((_, index) => (
          <div
            key={index}
            className="p-6 rounded-lg border !border-zinc-800 !bg-zinc-900 animate-pulse"
          >
            {/* Label */}
            <div className="h-4 w-32 bg-zinc-800 rounded mb-3"></div>
            {/* Value */}
            <div className="h-8 w-24 bg-zinc-800 rounded mb-2"></div>
            {/* Subtext */}
            <div className="h-3 w-28 bg-zinc-800 rounded"></div>
          </div>
        ))}
      </div>
    );
  }

  if (variant === "line-chart") {
    return (
      <div
        className="animate-pulse flex flex-col items-center justify-center"
        style={{ height: typeof height === "number" ? `${height}px` : height }}
      >
        {/* Chart title skeleton */}
        <div className="h-5 w-40 bg-zinc-800 rounded mb-4"></div>
        {/* Chart area skeleton */}
        <div className="w-full h-[250px] bg-zinc-800/30 rounded-lg flex items-end justify-around px-4 pb-4 gap-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="bg-zinc-700 rounded-t w-full"
              style={{ height: `${LINE_CHART_HEIGHTS[i]}%` }}
            ></div>
          ))}
        </div>
        {/* Axis labels */}
        <div className="flex justify-between w-full mt-2 px-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-3 w-16 bg-zinc-800 rounded"></div>
          ))}
        </div>
      </div>
    );
  }

  if (variant === "pie-chart") {
    return (
      <div
        className="animate-pulse flex flex-col items-center justify-center"
        style={{ height: typeof height === "number" ? `${height}px` : height }}
      >
        {/* Chart title skeleton */}
        <div className="h-5 w-40 bg-zinc-800 rounded mb-4"></div>
        {/* Pie chart circle */}
        <div className="w-40 h-40 rounded-full bg-zinc-800/30 mb-4"></div>
        {/* Legend items */}
        <div className="flex gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-zinc-700"></div>
              <div className="h-3 w-20 bg-zinc-800 rounded"></div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (variant === "bar-chart") {
    return (
      <div
        className="animate-pulse flex flex-col items-center justify-center"
        style={{ height: typeof height === "number" ? `${height}px` : height }}
      >
        {/* Chart title skeleton */}
        <div className="h-5 w-40 bg-zinc-800 rounded mb-4"></div>
        {/* Bar chart area */}
        <div className="w-full h-[300px] bg-zinc-800/30 rounded-lg flex items-end justify-around px-4 pb-8 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="bg-zinc-700 rounded-t w-full"
              style={{ height: `${BAR_CHART_HEIGHTS[i]}%` }}
            ></div>
          ))}
        </div>
        {/* X-axis labels */}
        <div className="flex justify-around w-full mt-2 px-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-3 w-12 bg-zinc-800 rounded"></div>
          ))}
        </div>
      </div>
    );
  }

  return null;
}
