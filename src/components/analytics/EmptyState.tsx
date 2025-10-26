import React from "react";
import type { EmptyStateProps } from "@/types/analytics";

/**
 * EmptyState Component
 *
 * Displays helpful empty state with icon, message, and optional action button
 * when no data is available in charts or sections.
 */
export function EmptyState({
  icon,
  title,
  description,
  action,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[300px] text-center px-4">
      {/* Icon */}
      {icon && <div className="mb-4 text-gray-500 opacity-50">{icon}</div>}

      {/* Title */}
      <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>

      {/* Description */}
      {description && (
        <p className="text-sm text-gray-400 max-w-md mb-4">{description}</p>
      )}

      {/* Action Button */}
      {action && (
        <button
          onClick={action.onClick}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
