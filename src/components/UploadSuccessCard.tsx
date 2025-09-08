"use client";

import { useState, useEffect } from "react";
import { Check, FileText, AlertTriangle, Clock, Loader2, X } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export interface UploadSuccessCardProps {
  filename: string;
  fileSize: number;
  pageCount?: number;
  processingStatus: 'uploading' | 'processing' | 'completed' | 'failed';
  error?: string;
  uploadProgress?: number;
  onRetry?: () => void;
  onDismiss?: () => void;
  estimatedTime?: number; // in seconds
  clauseCount?: number;
}

export const UploadSuccessCard = ({
  filename,
  fileSize,
  pageCount,
  processingStatus,
  error,
  uploadProgress = 0,
  onRetry,
  onDismiss,
  estimatedTime,
  clauseCount,
}: UploadSuccessCardProps) => {
  const [progress, setProgress] = useState(uploadProgress);
  const [timeElapsed, setTimeElapsed] = useState(0);

  // Animate progress bar
  useEffect(() => {
    if (processingStatus === 'uploading') {
      setProgress(uploadProgress);
    } else if (processingStatus === 'processing') {
      // Simulate processing progress
      const interval = setInterval(() => {
        setProgress((prev) => {
          if (prev >= 95) return prev;
          return prev + Math.random() * 2;
        });
      }, 500);
      return () => clearInterval(interval);
    } else if (processingStatus === 'completed') {
      setProgress(100);
    }
  }, [processingStatus, uploadProgress]);

  // Track time elapsed
  useEffect(() => {
    if (processingStatus === 'processing') {
      const interval = setInterval(() => {
        setTimeElapsed((prev) => prev + 1);
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [processingStatus]);

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatTime = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  };

  const getStatusIcon = () => {
    switch (processingStatus) {
      case 'uploading':
        return <Loader2 className="h-5 w-5 animate-spin text-blue-500" />;
      case 'processing':
        return <Clock className="h-5 w-5 animate-pulse text-yellow-500" />;
      case 'completed':
        return <Check className="h-5 w-5 text-green-500" />;
      case 'failed':
        return <AlertTriangle className="h-5 w-5 text-red-500" />;
    }
  };

  const getStatusMessage = () => {
    switch (processingStatus) {
      case 'uploading':
        return 'Uploading document...';
      case 'processing':
        return 'Analyzing document structure and content...';
      case 'completed':
        return `Document processed successfully! Found ${clauseCount} clauses.`;
      case 'failed':
        return error || 'Processing failed. Please try again.';
    }
  };

  const getStatusColor = () => {
    switch (processingStatus) {
      case 'uploading':
        return 'border-blue-500/50 bg-blue-500/10';
      case 'processing':
        return 'border-yellow-500/50 bg-yellow-500/10';
      case 'completed':
        return 'border-green-500/50 bg-green-500/10';
      case 'failed':
        return 'border-red-500/50 bg-red-500/10';
    }
  };

  // Determine if card should use compact layout
  const isCompactMode = processingStatus === 'completed' || processingStatus === 'failed';
  const cardPadding = isCompactMode ? 'p-3' : 'p-4';
  const iconSize = isCompactMode ? 'w-8 h-8' : 'w-12 h-12';
  const statusIconSize = isCompactMode ? 'w-4 h-4' : 'w-6 h-6';

  return (
    <Card className={`w-full ${cardPadding} border-2 transition-all duration-300 relative ${getStatusColor()}`}>
      {/* Top-right dismiss button - always visible for non-processing states */}
      {onDismiss && processingStatus !== 'processing' && (
        <Button
          variant="ghost"
          size="icon"
          onClick={onDismiss}
          className="absolute top-1 right-1 h-6 w-6 hover:bg-white/10 z-10 bg-black/20 backdrop-blur-sm border border-white/20"
          title="Dismiss notification"
        >
          <X className="h-3 w-3 text-white/80" />
        </Button>
      )}
      
      <div className={`flex items-start justify-between ${isCompactMode ? 'mb-1' : 'mb-3'}`}>
        <div className="flex items-start gap-2 flex-1 pr-8">
          <div className="relative">
            <div className={`${iconSize} bg-gradient-to-br from-purple-500 to-pink-500 rounded-lg flex items-center justify-center`}>
              <FileText className={`${isCompactMode ? 'h-4 w-4' : 'h-6 w-6'} text-white`} />
            </div>
            <div className={`absolute -top-1 -right-1 ${statusIconSize} bg-[#0B0B0B] rounded-full flex items-center justify-center`}>
              {getStatusIcon()}
            </div>
          </div>
          
          <div className="flex-1 min-w-0">
            <div className="mb-1">
              <h4 className="font-medium text-white truncate">{filename}</h4>
            </div>
            
            <div className="text-sm text-white/60 space-y-1">
              <div className="flex items-center gap-4">
                <span>{formatFileSize(fileSize)}</span>
                {pageCount && <span>{pageCount} pages</span>}
                {processingStatus === 'processing' && timeElapsed > 0 && (
                  <span>⏱️ {formatTime(timeElapsed)}</span>
                )}
              </div>
            </div>
            
            <p className="text-sm text-white/80 mt-2">
              {getStatusMessage()}
            </p>
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      {(processingStatus === 'uploading' || processingStatus === 'processing') && (
        <div className="mb-3">
          <div className="flex justify-between items-center mb-1">
            <span className="text-xs text-white/60">
              {processingStatus === 'uploading' ? 'Upload Progress' : 'Processing Progress'}
            </span>
            <span className="text-xs text-white/60">{Math.round(progress)}%</span>
          </div>
          <div className="w-full bg-white/10 rounded-full h-2 overflow-hidden">
            <div 
              className="h-full bg-gradient-to-r from-purple-500 to-pink-500 rounded-full transition-all duration-300 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
          {estimatedTime && processingStatus === 'processing' && (
            <div className="text-xs text-white/50 mt-1">
              Estimated time: {formatTime(estimatedTime)}
            </div>
          )}
        </div>
      )}

      {/* Success Details - Compact for completed cards */}
      {processingStatus === 'completed' && clauseCount && (
        <div className="flex items-center gap-4 pt-2 border-t border-white/10 text-xs">
          <div className="flex items-center gap-1">
            <span className="font-semibold text-green-400">{clauseCount}</span>
            <span className="text-white/60">clauses</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="font-semibold text-blue-400">{formatTime(timeElapsed)}</span>
            <span className="text-white/60">processing time</span>
          </div>
        </div>
      )}

      {/* Error Actions */}
      {processingStatus === 'failed' && (
        <div className="pt-3 border-t border-white/10 flex gap-2">
          {onRetry && (
            <Button 
              variant="secondary" 
              size="sm" 
              onClick={onRetry}
              className="flex-1"
            >
              Try Again
            </Button>
          )}
          {onDismiss && (
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={onDismiss}
              className="flex-1"
            >
              Dismiss
            </Button>
          )}
        </div>
      )}

      {/* Additional Processing Info */}
      {processingStatus === 'processing' && (
        <div className="pt-3 border-t border-white/10">
          <div className="flex items-center gap-2 text-xs text-white/60">
            <div className="flex gap-1">
              <div className="w-1 h-1 bg-purple-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <div className="w-1 h-1 bg-purple-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <div className="w-1 h-1 bg-purple-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
            <span>Extracting clauses, analyzing risks, and calculating readability scores...</span>
          </div>
        </div>
      )}
    </Card>
  );
};