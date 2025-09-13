import React, { useState, useMemo } from "react";
import { ClauseSummary, RiskLevel } from "@/lib/api";

interface RiskHeatmapProps {
  clauses: ClauseSummary[];
  className?: string;
  isLoading?: boolean;
  error?: Error | null;
}

interface HeatmapCell {
  category: string;
  riskLevel: RiskLevel;
  count: number;
  percentage: number;
  clauses: ClauseSummary[];
}

interface TooltipData {
  cell: HeatmapCell;
  x: number;
  y: number;
}

const CATEGORY_ORDER = [
  "Termination",
  "Liability",
  "Indemnity",
  "Confidentiality",
  "Payment",
  "IP Ownership",
  "Dispute Resolution",
  "Governing Law",
  "Assignment",
  "Modification",
  "Other",
];

const RISK_LEVELS: RiskLevel[] = ["low", "moderate", "attention"];

const RISK_COLORS = {
  low: "bg-emerald-500",
  moderate: "bg-yellow-500",
  attention: "bg-red-500",
};

const RISK_LABELS = {
  low: "Low Risk",
  moderate: "Moderate Risk",
  attention: "Needs Attention",
};

export const RiskHeatmap: React.FC<RiskHeatmapProps> = ({
  clauses,
  className = "",
  isLoading = false,
  error = null,
}) => {
  const [tooltip, setTooltip] = useState<TooltipData | null>(null);

  // Process clauses into heatmap data
  const heatmapData = useMemo(() => {
    // Group clauses by category and risk level
    const categoryRiskMap = new Map<string, Map<RiskLevel, ClauseSummary[]>>();

    clauses.forEach((clause) => {
      const category = clause.category || "Other";
      if (!categoryRiskMap.has(category)) {
        categoryRiskMap.set(category, new Map());
      }

      const riskMap = categoryRiskMap.get(category)!;
      if (!riskMap.has(clause.risk_level)) {
        riskMap.set(clause.risk_level, []);
      }

      riskMap.get(clause.risk_level)!.push(clause);
    });

    // Get categories that actually have clauses
    const presentCategories = Array.from(categoryRiskMap.keys()).sort(
      (a, b) => {
        const aIndex = CATEGORY_ORDER.indexOf(a);
        const bIndex = CATEGORY_ORDER.indexOf(b);
        if (aIndex === -1 && bIndex === -1) return a.localeCompare(b);
        if (aIndex === -1) return 1;
        if (bIndex === -1) return -1;
        return aIndex - bIndex;
      }
    );

    // Create heatmap cells
    const cells: HeatmapCell[] = [];
    const totalClauses = clauses.length;

    presentCategories.forEach((category) => {
      const riskMap = categoryRiskMap.get(category)!;

      RISK_LEVELS.forEach((riskLevel) => {
        const clausesInCell = riskMap.get(riskLevel) || [];
        const count = clausesInCell.length;
        const percentage = totalClauses > 0 ? (count / totalClauses) * 100 : 0;

        cells.push({
          category,
          riskLevel,
          count,
          percentage,
          clauses: clausesInCell,
        });
      });
    });

    return { cells, categories: presentCategories };
  }, [clauses]);

  const handleCellHover = (cell: HeatmapCell, event: React.MouseEvent) => {
    const rect = event.currentTarget.getBoundingClientRect();
    setTooltip({
      cell,
      x: rect.right + 10,
      y: rect.top,
    });
  };

  const handleCellLeave = () => {
    setTooltip(null);
  };

  const getIntensity = (percentage: number) => {
    if (percentage === 0) return 0;
    if (percentage < 5) return 0.3;
    if (percentage < 15) return 0.5;
    if (percentage < 30) return 0.7;
    return 1.0;
  };

  const getCellColor = (cell: HeatmapCell) => {
    const intensity = getIntensity(cell.percentage);
    if (intensity === 0) return "bg-gray-800 border-gray-700";

    const baseColor = RISK_COLORS[cell.riskLevel];
    return `${baseColor} border-gray-600`;
  };

  const getCellOpacity = (cell: HeatmapCell) => {
    const intensity = getIntensity(cell.percentage);
    return Math.max(0.1, intensity);
  };

  if (isLoading) {
    return (
      <div className={`p-4 ${className}`}>
        <div className="animate-pulse space-y-4">
          {/* Legend skeleton */}
          <div className="space-y-2">
            <div className="h-3 bg-gray-700 rounded w-20"></div>
            <div className="flex gap-3">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-gray-700 rounded-sm"></div>
                  <div className="h-2 bg-gray-700 rounded w-16"></div>
                </div>
              ))}
            </div>
          </div>

          {/* Heatmap skeleton */}
          <div className="space-y-1">
            <div className="flex gap-2">
              <div className="w-24 h-4 bg-gray-700 rounded"></div>
              {[...Array(3)].map((_, i) => (
                <div key={i} className="w-16 h-4 bg-gray-700 rounded"></div>
              ))}
            </div>
            {[...Array(5)].map((_, row) => (
              <div key={row} className="flex gap-2">
                <div className="w-24 h-8 bg-gray-700 rounded"></div>
                {[...Array(3)].map((_, col) => (
                  <div key={col} className="w-16 h-8 bg-gray-700 rounded"></div>
                ))}
              </div>
            ))}
          </div>

          {/* Stats skeleton */}
          <div className="grid grid-cols-3 gap-4 pt-3 border-t border-white/10">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="text-center space-y-1">
                <div className="h-6 bg-gray-700 rounded w-8 mx-auto"></div>
                <div className="h-3 bg-gray-700 rounded w-16 mx-auto"></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`p-4 text-center text-red-400 ${className}`}>
        <div className="text-sm">Failed to load risk analysis</div>
        <div className="text-xs mt-1 text-white/60">
          {error.message || "Please refresh or try again"}
        </div>
      </div>
    );
  }

  if (clauses.length === 0) {
    return (
      <div className={`p-4 text-center text-white/50 ${className}`}>
        <div className="text-sm">No clause data available</div>
        <div className="text-xs mt-1">
          Upload a document to see risk analysis
        </div>
      </div>
    );
  }

  return (
    <div className={`relative ${className}`}>
      {/* Legend */}
      <div className="mb-4">
        <div className="text-xs font-medium text-white/70 mb-2">
          Risk Levels
        </div>
        <div className="flex gap-3">
          {RISK_LEVELS.map((level) => (
            <div key={level} className="flex items-center gap-2">
              <div className={`w-3 h-3 rounded-sm ${RISK_COLORS[level]}`}></div>
              <span className="text-xs text-white/60">
                {RISK_LABELS[level]}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Heatmap */}
      <div className="overflow-x-auto no-scrollbar">
        <div className="min-w-max">
          {/* Column headers (Risk Levels) */}
          <div className="flex mb-2">
            <div className="w-24 flex-shrink-0"></div>{" "}
            {/* Space for row labels */}
            {RISK_LEVELS.map((level) => (
              <div
                key={level}
                className="w-16 text-xs text-white/60 text-center px-1"
              >
                {RISK_LABELS[level]}
              </div>
            ))}
          </div>

          {/* Heatmap rows */}
          {heatmapData.categories.map((category) => (
            <div key={category} className="flex mb-1">
              {/* Row label */}
              <div className="w-24 flex-shrink-0 text-xs text-white/70 py-2 pr-2 text-right truncate">
                {category}
              </div>

              {/* Risk level cells */}
              {RISK_LEVELS.map((riskLevel) => {
                const cell = heatmapData.cells.find(
                  (c) => c.category === category && c.riskLevel === riskLevel
                );

                if (!cell)
                  return <div key={riskLevel} className="w-16 h-8 mx-px"></div>;

                return (
                  <div
                    key={riskLevel}
                    className={`w-16 h-8 mx-px border cursor-pointer transition-all duration-200 hover:scale-105 hover:z-10 relative ${getCellColor(
                      cell
                    )}`}
                    style={{ opacity: getCellOpacity(cell) }}
                    onMouseEnter={(e) => handleCellHover(cell, e)}
                    onMouseLeave={handleCellLeave}
                  >
                    {cell.count > 0 && (
                      <div className="absolute inset-0 flex items-center justify-center">
                        <span className="text-xs font-medium text-white drop-shadow">
                          {cell.count}
                        </span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>

      {/* Summary stats */}
      <div className="mt-4 pt-3 border-t border-white/10">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-lg font-semibold text-white">
              {clauses.length}
            </div>
            <div className="text-xs text-white/60">Total Clauses</div>
          </div>
          <div>
            <div className="text-lg font-semibold text-red-400">
              {clauses.filter((c) => c.risk_level === "attention").length}
            </div>
            <div className="text-xs text-white/60">High Risk</div>
          </div>
          <div>
            <div className="text-lg font-semibold text-yellow-400">
              {clauses.filter((c) => c.risk_level === "moderate").length}
            </div>
            <div className="text-xs text-white/60">Moderate Risk</div>
          </div>
        </div>
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="fixed z-50 bg-gray-900 border border-gray-700 rounded-lg p-3 shadow-lg max-w-xs"
          style={{ left: tooltip.x, top: tooltip.y }}
        >
          <div className="text-sm font-medium text-white mb-1">
            {tooltip.cell.category} - {RISK_LABELS[tooltip.cell.riskLevel]}
          </div>
          <div className="text-xs text-white/80 mb-2">
            {tooltip.cell.count} clause{tooltip.cell.count !== 1 ? "s" : ""} (
            {tooltip.cell.percentage.toFixed(1)}%)
          </div>
          {tooltip.cell.clauses.length > 0 && (
            <div className="text-xs text-white/60">
              <div className="font-medium mb-1">Clauses:</div>
              {tooltip.cell.clauses.slice(0, 3).map((clause) => (
                <div key={clause.clause_id} className="truncate">
                  • {clause.summary}
                </div>
              ))}
              {tooltip.cell.clauses.length > 3 && (
                <div className="text-white/40 mt-1">
                  +{tooltip.cell.clauses.length - 3} more
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
