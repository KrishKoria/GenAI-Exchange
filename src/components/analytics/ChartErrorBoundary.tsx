"use client";

import React, { ReactNode } from "react";
import { ErrorBoundary as ReactErrorBoundary } from "react-error-boundary";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface ChartErrorFallbackProps {
  error: Error;
  resetErrorBoundary: () => void;
}

function ChartErrorFallback({
  error,
  resetErrorBoundary,
}: ChartErrorFallbackProps) {
  return (
    <Card className="p-6 !bg-zinc-900 !border-zinc-800">
      <div className="flex flex-col items-center justify-center h-64 space-y-4">
        <div className="text-red-500">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="48"
            height="48"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>
        <div className="text-center space-y-2">
          <h3 className="font-semibold text-white">Chart Error</h3>
          <p className="text-sm text-gray-400">
            {error.message || "An error occurred while rendering this chart"}
          </p>
        </div>
        <Button onClick={resetErrorBoundary} variant="outline" size="sm">
          Retry
        </Button>
      </div>
    </Card>
  );
}

interface ChartErrorBoundaryProps {
  children: ReactNode;
  onReset?: () => void;
}

export function ChartErrorBoundary({
  children,
  onReset,
}: ChartErrorBoundaryProps) {
  return (
    <ReactErrorBoundary
      FallbackComponent={ChartErrorFallback}
      onReset={onReset}
      onError={(error, errorInfo) => {
        console.error("Chart error:", error, errorInfo);
      }}
    >
      {children}
    </ReactErrorBoundary>
  );
}
