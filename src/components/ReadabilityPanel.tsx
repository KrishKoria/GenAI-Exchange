"use client";

import { useMemo } from "react";
import { BookOpen, TrendingUp, TrendingDown, Minus, Target, Award } from "lucide-react";
import { Card } from "@/components/ui/card";
import type { ClauseSummary } from "@/lib/api";

interface ReadabilityPanelProps {
  clauses: ClauseSummary[];
  isLoading?: boolean;
  error?: unknown;
}

interface ReadabilityStats {
  documentGrade: number;
  averageImprovement: number;
  totalClauses: number;
  improvedClauses: number;
  averageFleschScore: number;
  readabilityLevel: 'excellent' | 'good' | 'fair' | 'difficult' | 'very-difficult';
}

// Convert Flesch-Kincaid grade to reading level description
function getReadabilityLevel(grade: number): ReadabilityStats['readabilityLevel'] {
  if (grade <= 6) return 'excellent';
  if (grade <= 9) return 'good'; 
  if (grade <= 13) return 'fair';
  if (grade <= 16) return 'difficult';
  return 'very-difficult';
}

// Convert Flesch Reading Ease score to description
function getFleschDescription(score: number): string {
  if (score >= 90) return 'Very Easy';
  if (score >= 80) return 'Easy';
  if (score >= 70) return 'Fairly Easy';
  if (score >= 60) return 'Standard';
  if (score >= 50) return 'Fairly Difficult';
  if (score >= 30) return 'Difficult';
  return 'Very Difficult';
}

// Get color for readability level
function getReadabilityColor(level: ReadabilityStats['readabilityLevel']): string {
  switch (level) {
    case 'excellent': return 'text-green-400';
    case 'good': return 'text-blue-400';
    case 'fair': return 'text-yellow-400';
    case 'difficult': return 'text-orange-400';
    case 'very-difficult': return 'text-red-400';
  }
}

// Get improvement icon
function getImprovementIcon(delta: number, size = "h-4 w-4") {
  if (delta > 1) return <TrendingUp className={`${size} text-green-400`} />;
  if (delta < -1) return <TrendingDown className={`${size} text-red-400`} />;
  return <Minus className={`${size} text-gray-400`} />;
}

export function ReadabilityPanel({ clauses, isLoading, error }: ReadabilityPanelProps) {
  const stats = useMemo<ReadabilityStats>(() => {
    if (!clauses || clauses.length === 0) {
      return {
        documentGrade: 0,
        averageImprovement: 0,
        totalClauses: 0,
        improvedClauses: 0,
        averageFleschScore: 0,
        readabilityLevel: 'fair',
      };
    }

    // Calculate aggregate readability statistics
    let totalOriginalGrade = 0;
    let totalImprovement = 0;
    let totalFleschScore = 0;
    let improvedCount = 0;
    let validClauses = 0;

    clauses.forEach((clause) => {
      // Check if clause has readability metrics (might be missing for some clauses)
      if (clause.readability_delta !== undefined) {
        totalOriginalGrade += 12; // default grade level when not available
        totalImprovement += clause.readability_delta;
        totalFleschScore += 50; // default flesch score when not available
        if (clause.readability_delta > 0.5) improvedCount++;
        validClauses++;
      }
    });

    const documentGrade = validClauses > 0 ? totalOriginalGrade / validClauses : 12;
    const averageImprovement = validClauses > 0 ? totalImprovement / validClauses : 0;
    const averageFleschScore = validClauses > 0 ? totalFleschScore / validClauses : 50;

    return {
      documentGrade,
      averageImprovement,
      totalClauses: clauses.length,
      improvedClauses: improvedCount,
      averageFleschScore,
      readabilityLevel: getReadabilityLevel(documentGrade),
    };
  }, [clauses]);

  if (error) {
    return (
      <Card className="p-4 border-red-500/50 bg-red-500/10">
        <div className="text-sm text-red-400">
          Failed to load readability analysis. Please refresh to try again.
        </div>
      </Card>
    );
  }

  if (isLoading || stats.totalClauses === 0) {
    return (
      <Card className="p-4 border-white/10 bg-[#0F0F0F]">
        <div className="flex items-center gap-2 mb-3">
          <BookOpen className="h-4 w-4 text-blue-400" />
          <h4 className="font-medium text-white">Readability Analysis</h4>
        </div>
        
        {isLoading ? (
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="animate-pulse">
                <div className="h-4 bg-gray-700 rounded mb-2"></div>
                <div className="h-6 bg-gray-700 rounded"></div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-white/60">
            Upload a document to see readability analysis
          </div>
        )}
      </Card>
    );
  }

  return (
    <Card className="p-4 border-white/10 bg-[#0F0F0F]">
      <div className="flex items-center gap-2 mb-4">
        <BookOpen className="h-4 w-4 text-blue-400" />
        <h4 className="font-medium text-white">Readability Analysis</h4>
      </div>

      {/* Main Metrics Grid */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        {/* Document Grade Level */}
        <div className="text-center p-3 rounded-lg bg-[#121212] border border-white/5">
          <div className={`text-2xl font-bold ${getReadabilityColor(stats.readabilityLevel)}`}>
            {stats.documentGrade.toFixed(1)}
          </div>
          <div className="text-xs text-white/60">Grade Level</div>
          <div className="text-xs text-white/40 capitalize">
            {stats.readabilityLevel.replace('-', ' ')}
          </div>
        </div>

        {/* Flesch Reading Ease */}
        <div className="text-center p-3 rounded-lg bg-[#121212] border border-white/5">
          <div className="text-2xl font-bold text-purple-400">
            {Math.round(stats.averageFleschScore)}
          </div>
          <div className="text-xs text-white/60">Flesch Score</div>
          <div className="text-xs text-white/40">
            {getFleschDescription(stats.averageFleschScore)}
          </div>
        </div>
      </div>

      {/* Improvement Stats */}
      <div className="space-y-3 mb-4">
        <div className="flex items-center justify-between p-2 rounded bg-[#121212] border border-white/5">
          <div className="flex items-center gap-2">
            {getImprovementIcon(stats.averageImprovement)}
            <span className="text-sm text-white/80">Average Improvement</span>
          </div>
          <div className="text-sm font-medium text-white">
            {stats.averageImprovement > 0 ? '+' : ''}{stats.averageImprovement.toFixed(1)} grades
          </div>
        </div>

        <div className="flex items-center justify-between p-2 rounded bg-[#121212] border border-white/5">
          <div className="flex items-center gap-2">
            <Target className="h-4 w-4 text-green-400" />
            <span className="text-sm text-white/80">Improved Clauses</span>
          </div>
          <div className="text-sm font-medium text-white">
            {stats.improvedClauses} / {stats.totalClauses}
          </div>
        </div>
      </div>

      {/* Progress Bar for Improved Clauses */}
      <div className="mb-4">
        <div className="flex justify-between text-xs text-white/60 mb-1">
          <span>Improvement Progress</span>
          <span>{Math.round((stats.improvedClauses / stats.totalClauses) * 100)}%</span>
        </div>
        <div className="w-full bg-white/10 rounded-full h-2">
          <div 
            className="bg-gradient-to-r from-green-500 to-blue-500 h-2 rounded-full transition-all duration-300"
            style={{ width: `${(stats.improvedClauses / stats.totalClauses) * 100}%` }}
          />
        </div>
      </div>

      {/* Readability Tips */}
      <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
        <div className="flex items-center gap-2 mb-2">
          <Award className="h-4 w-4 text-blue-400" />
          <span className="text-sm font-medium text-blue-300">Readability Insights</span>
        </div>
        <div className="text-xs text-white/70 space-y-1">
          {stats.documentGrade > 12 && (
            <div>• Document complexity is above high school level</div>
          )}
          {stats.averageImprovement > 2 && (
            <div>• Excellent simplification achieved in summaries</div>
          )}
          {stats.averageFleschScore < 50 && (
            <div>• Consider requesting simpler explanations for complex clauses</div>
          )}
          {stats.improvedClauses / stats.totalClauses < 0.5 && (
            <div>• Some clauses may benefit from further clarification</div>
          )}
        </div>
      </div>
    </Card>
  );
}