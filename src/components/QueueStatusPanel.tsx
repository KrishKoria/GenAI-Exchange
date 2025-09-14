"use client";

import React from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Clock,
  FileText,
  AlertCircle,
  CheckCircle,
  X,
  Loader2,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { documentApi, QueueItem } from "@/lib/api";

interface QueueStatusPanelProps {
  isVisible: boolean;
  onClose: () => void;
}

export function QueueStatusPanel({
  isVisible,
  onClose,
}: QueueStatusPanelProps) {
  // Query for queue status
  const { data: queueStatusData, isLoading: statusLoading } = useQuery({
    queryKey: ["queue", "status"],
    queryFn: () => documentApi.getQueueStatus(),
    refetchInterval: 2000, // Refresh every 2 seconds
    enabled: isVisible,
  });

  // Query for queue items
  const { data: queueItemsData, isLoading: itemsLoading } = useQuery({
    queryKey: ["queue", "items"],
    queryFn: () => documentApi.getQueueItems(),
    refetchInterval: 2000, // Refresh every 2 seconds
    enabled: isVisible,
  });

  const queueStatus = queueStatusData?.queue_status;
  const queueItems = queueItemsData?.queue_items || [];

  if (!isVisible) return null;

  const getStatusIcon = (status: QueueItem["status"]) => {
    switch (status) {
      case "queued":
        return <Clock className="h-4 w-4 text-yellow-500" />;
      case "processing":
        return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
      case "completed":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case "failed":
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      default:
        return <FileText className="h-4 w-4 text-gray-500" />;
    }
  };

  const getStatusColor = (status: QueueItem["status"]) => {
    switch (status) {
      case "queued":
        return "text-yellow-600 bg-yellow-50 border-yellow-200";
      case "processing":
        return "text-blue-600 bg-blue-50 border-blue-200";
      case "completed":
        return "text-green-600 bg-green-50 border-green-200";
      case "failed":
        return "text-red-600 bg-red-50 border-red-200";
      default:
        return "text-gray-600 bg-gray-50 border-gray-200";
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  };

  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <Card className="w-full max-w-2xl max-h-[80vh] m-4 flex flex-col">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Document Processing Queue
            </h2>
            <Button variant="ghost" size="sm" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Queue Status Summary */}
          {queueStatus && !statusLoading && (
            <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">
                  {queueStatus.total_items}
                </div>
                <div className="text-gray-600">Total</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-yellow-600">
                  {queueStatus.queued_items}
                </div>
                <div className="text-gray-600">Queued</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">
                  {queueStatus.processing_items}
                </div>
                <div className="text-gray-600">Processing</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-green-600">
                  {queueStatus.completed_items}
                </div>
                <div className="text-gray-600">Completed</div>
              </div>
            </div>
          )}
        </div>

        {/* Queue Items List */}
        <div className="flex-1 overflow-y-auto p-6">
          {statusLoading || itemsLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
              <span className="ml-2 text-gray-600">Loading queue...</span>
            </div>
          ) : queueItems.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <FileText className="h-12 w-12 mx-auto mb-2 text-gray-300" />
              <div>No documents in queue</div>
            </div>
          ) : (
            <div className="space-y-3">
              {queueItems.map((item) => (
                <div
                  key={item.doc_id}
                  className={`p-4 rounded-lg border ${getStatusColor(
                    item.status
                  )}`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3 flex-1">
                      {getStatusIcon(item.status)}
                      <div className="flex-1 min-w-0">
                        <div className="font-medium truncate">
                          {item.filename}
                        </div>
                        <div className="text-sm text-gray-600">
                          {formatFileSize(item.file_size)} •{" "}
                          {formatTimeAgo(item.created_at)}
                        </div>

                        {/* Progress Bar for Processing Items */}
                        {item.status === "processing" && (
                          <div className="mt-2">
                            <Progress
                              value={item.progress * 100}
                              className="h-2"
                            />
                            <div className="text-xs text-gray-500 mt-1">
                              {Math.round(item.progress * 100)}% complete
                            </div>
                          </div>
                        )}

                        {/* Error Message for Failed Items */}
                        {item.status === "failed" && item.error_message && (
                          <div className="mt-2 text-sm text-red-600">
                            Error: {item.error_message}
                          </div>
                        )}

                        {/* Wait Time for Queued Items */}
                        {item.status === "queued" && (
                          <div className="mt-2 text-sm text-gray-600">
                            Estimated wait: {Math.round(item.wait_time / 60)}{" "}
                            minutes
                          </div>
                        )}

                        {/* Processing Time for Completed Items */}
                        {item.status === "completed" &&
                          item.processing_time && (
                            <div className="mt-2 text-sm text-gray-600">
                              Processed in {Math.round(item.processing_time)}{" "}
                              seconds
                            </div>
                          )}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 ml-4">
                      <span
                        className={`px-2 py-1 text-xs font-medium rounded-full border ${getStatusColor(
                          item.status
                        )}`}
                      >
                        {item.status}
                      </span>

                      {/* Cancel Button for Queued Items */}
                      {item.status === "queued" && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={async () => {
                            try {
                              await documentApi.cancelQueueItem(item.doc_id);
                            } catch (error) {
                              console.error(
                                "Failed to cancel queue item:",
                                error
                              );
                            }
                          }}
                          className="text-red-600 hover:text-red-700"
                        >
                          Cancel
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer with Refresh Info */}
        <div className="p-4 border-t border-gray-200 text-center text-sm text-gray-600">
          Updates automatically every 2 seconds
        </div>
      </Card>
    </div>
  );
}
