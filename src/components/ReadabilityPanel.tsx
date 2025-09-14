"use client";

import { useMemo } from "react";
import { BookOpen, TrendingUp, Target, Award, Info, AlertCircle, CheckCircle } from "lucide-react";
import { Card } from "@/components/ui/card";
import { useTranslations } from "next-intl";
import type { ClauseSummary } from "@/lib/api";

interface ReadabilityPanelProps {
  clauses: ClauseSummary[];
  isLoading?: boolean;
  error?: unknown;
}

interface ReadabilityStats {
  averageGrade: number;
  averageFleschScore: number;
  totalClauses: number;
  highlyDifficultClauses: number;
  veryDifficultClauses: number;
  readabilityLevel: 'excellent' | 'good' | 'fair' | 'difficult' | 'very-difficult';
  difficultyDistribution: {
    easy: number;      // grade <= 9
    moderate: number;  // grade 9-13
    difficult: number; // grade 13-16
    veryDifficult: number; // grade > 16
  };
}

// Convert Flesch-Kincaid grade to reading level description
function getReadabilityLevel(grade: number): ReadabilityStats['readabilityLevel'] {
  if (grade <= 6) return 'excellent';
  if (grade <= 9) return 'good'; 
  if (grade <= 13) return 'fair';
  if (grade <= 16) return 'difficult';
  return 'very-difficult';
}

// Convert Flesch Reading Ease score to description key
function getFleschDescriptionKey(score: number): string {
  if (score >= 90) return 'veryEasy';
  if (score >= 80) return 'easy';
  if (score >= 70) return 'fairlyEasy';
  if (score >= 60) return 'standard';
  if (score >= 50) return 'fairlyDifficult';
  if (score >= 30) return 'difficult';
  return 'veryDifficult';
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

// Convert kebab-case to camelCase for translation keys
function toCamelCase(str: string): string {
  return str.replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
}


export function ReadabilityPanel({ clauses, isLoading, error }: ReadabilityPanelProps) {
  const t = useTranslations();
  const stats = useMemo<ReadabilityStats>(() => {
    if (!clauses || clauses.length === 0) {
      return {
        averageGrade: 0,
        averageFleschScore: 0,
        totalClauses: 0,
        highlyDifficultClauses: 0,
        veryDifficultClauses: 0,
        readabilityLevel: 'fair',
        difficultyDistribution: {
          easy: 0,
          moderate: 0,
          difficult: 0,
          veryDifficult: 0,
        },
      };
    }

    // Calculate aggregate readability statistics
    let totalOriginalGrade = 0;
    let totalFleschScore = 0;
    let validClauses = 0;
    let highlyDifficultCount = 0; // grade > 13
    let veryDifficultCount = 0;   // grade > 16

    const distribution = {
      easy: 0,        // grade <= 9
      moderate: 0,    // grade 9-13
      difficult: 0,   // grade 13-16
      veryDifficult: 0, // grade > 16
    };

    clauses.forEach((clause) => {
      // Check if clause has readability metrics
      if (clause.readability_metrics) {
        const grade = clause.readability_metrics.original_grade || 12;
        const fleschScore = clause.readability_metrics.flesch_score || 50;

        totalOriginalGrade += grade;
        totalFleschScore += fleschScore;
        validClauses++;

        // Count difficulty levels
        if (grade > 16) {
          veryDifficultCount++;
          distribution.veryDifficult++;
        } else if (grade > 13) {
          highlyDifficultCount++;
          distribution.difficult++;
        } else if (grade > 9) {
          distribution.moderate++;
        } else {
          distribution.easy++;
        }
      }
    });

    const averageGrade = validClauses > 0 ? totalOriginalGrade / validClauses : 12;
    const averageFleschScore = validClauses > 0 ? totalFleschScore / validClauses : 50;

    return {
      averageGrade,
      averageFleschScore,
      totalClauses: clauses.length,
      highlyDifficultClauses: highlyDifficultCount,
      veryDifficultClauses: veryDifficultCount,
      readabilityLevel: getReadabilityLevel(averageGrade),
      difficultyDistribution: distribution,
    };
  }, [clauses]);

  if (error) {
    return (
      <Card className="p-4 border-red-500/50 bg-red-500/10">
        <div className="text-sm text-red-400">
          {t('readability.failedToLoad')}
        </div>
      </Card>
    );
  }

  if (isLoading || stats.totalClauses === 0) {
    return (
      <Card className="p-4 border-white/10 bg-[#0F0F0F]">
        <div className="flex items-center gap-2 mb-3">
          <BookOpen className="h-4 w-4 text-blue-400" />
          <h4 className="font-medium text-white">{t('readability.title')}</h4>
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
            {t('readability.uploadForReadability')}
          </div>
        )}
      </Card>
    );
  }

  return (
    <Card className="p-4 border-white/10 bg-[#0F0F0F]">
      <div className="flex items-center gap-2 mb-4">
        <BookOpen className="h-4 w-4 text-blue-400" />
        <h4 className="font-medium text-white">{t('readability.title')}</h4>
      </div>

      {/* Main Metrics Grid */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        {/* Document Grade Level */}
        <div className="text-center p-3 rounded-lg bg-[#121212] border border-white/5">
          <div className={`text-2xl font-bold ${getReadabilityColor(stats.readabilityLevel)}`}>
            {stats.averageGrade.toFixed(1)}
          </div>
          <div className="text-xs text-white/60">{t('readability.averageGrade')}</div>
          <div className="text-xs text-white/40 capitalize">
            {t(`readability.levels.${toCamelCase(stats.readabilityLevel)}`)}
          </div>
        </div>

        {/* Flesch Reading Ease */}
        <div className="text-center p-3 rounded-lg bg-[#121212] border border-white/5">
          <div className="text-2xl font-bold text-purple-400">
            {Math.round(stats.averageFleschScore)}
          </div>
          <div className="text-xs text-white/60">{t('readability.fleschScore')}</div>
          <div className="text-xs text-white/40">
            {t(`readability.fleschDescriptions.${getFleschDescriptionKey(stats.averageFleschScore)}`)}
          </div>
        </div>
      </div>

      {/* Difficulty Stats */}
      <div className="space-y-3 mb-4">
        <div className="flex items-center justify-between p-2 rounded bg-[#121212] border border-white/5">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-red-400" />
            <span className="text-sm text-white/80">{t('readability.difficultyLabels.highlyDifficult')}</span>
          </div>
          <div className="text-sm font-medium text-white">
            {stats.highlyDifficultClauses} / {stats.totalClauses}
          </div>
        </div>

        <div className="flex items-center justify-between p-2 rounded bg-[#121212] border border-white/5">
          <div className="flex items-center gap-2">
            <Target className="h-4 w-4 text-orange-400" />
            <span className="text-sm text-white/80">{t('readability.difficultyLabels.veryDifficult')}</span>
          </div>
          <div className="text-sm font-medium text-white">
            {stats.veryDifficultClauses} / {stats.totalClauses}
          </div>
        </div>
      </div>

      {/* Difficulty Distribution */}
      <div className="mb-4">
        <div className="text-xs text-white/60 mb-2">{t('readability.difficultyDistribution')}</div>
        <div className="grid grid-cols-4 gap-1 text-xs">
          <div className="text-center p-2 rounded bg-green-500/20 text-green-300">
            <div className="font-medium">{stats.difficultyDistribution.easy}</div>
            <div className="text-[10px] opacity-70">{t('readability.difficultyLabels.easy')}</div>
          </div>
          <div className="text-center p-2 rounded bg-blue-500/20 text-blue-300">
            <div className="font-medium">{stats.difficultyDistribution.moderate}</div>
            <div className="text-[10px] opacity-70">{t('readability.difficultyLabels.moderate')}</div>
          </div>
          <div className="text-center p-2 rounded bg-orange-500/20 text-orange-300">
            <div className="font-medium">{stats.difficultyDistribution.difficult}</div>
            <div className="text-[10px] opacity-70">{t('readability.difficultyLabels.difficult')}</div>
          </div>
          <div className="text-center p-2 rounded bg-red-500/20 text-red-300">
            <div className="font-medium">{stats.difficultyDistribution.veryDifficult}</div>
            <div className="text-[10px] opacity-70">{t('readability.difficultyLabels.veryHard')}</div>
          </div>
        </div>
      </div>

      {/* Educational Section: Understanding Metrics */}
      <div className="mb-4 p-3 rounded-lg bg-indigo-500/10 border border-indigo-500/20">
        <div className="flex items-center gap-2 mb-2">
          <Info className="h-4 w-4 text-indigo-400" />
          <span className="text-sm font-medium text-indigo-300">{t('readability.understandingMetrics')}</span>
        </div>
        <div className="space-y-3 text-xs text-white/70">
          <div>
            <div className="font-medium text-indigo-200 mb-1">{t('readability.gradeLevel.title')}</div>
            <div className="text-white/60">{t('readability.gradeLevel.explanation')}</div>
            <div className="mt-1 text-white/50">
              • <strong>6-9:</strong> {t('readability.gradeLevel.elementary')}
              <br />• <strong>9-13:</strong> {t('readability.gradeLevel.highSchool')}
              <br />• <strong>13-16:</strong> {t('readability.gradeLevel.college')}
              <br />• <strong>16+:</strong> {t('readability.gradeLevel.graduate')}
            </div>
          </div>
          <div>
            <div className="font-medium text-indigo-200 mb-1">{t('readability.fleschScale.title')}</div>
            <div className="text-white/60">{t('readability.fleschScale.explanation')}</div>
            <div className="mt-1 text-white/50">
              • <strong>90-100:</strong> {t('readability.fleschScale.veryEasy')}
              <br />• <strong>60-70:</strong> {t('readability.fleschScale.standard')}
              <br />• <strong>30-50:</strong> {t('readability.fleschScale.difficult')}
              <br />• <strong>0-30:</strong> {t('readability.fleschScale.veryDifficult')}
            </div>
          </div>
        </div>
      </div>

      {/* Legal Document Context */}
      <div className="mb-4 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
        <div className="flex items-center gap-2 mb-2">
          <AlertCircle className="h-4 w-4 text-amber-400" />
          <span className="text-sm font-medium text-amber-300">{t('readability.legalContext.title')}</span>
        </div>
        <div className="text-xs text-white/70 space-y-2">
          <div>{t('readability.legalContext.explanation')}</div>
          <div className="space-y-1">
            <div>• <strong>{t('readability.legalContext.averagePerson')}:</strong> {t('readability.legalContext.averagePersonExplanation')}</div>
            <div>• <strong>{t('readability.legalContext.businessProfessional')}:</strong> {t('readability.legalContext.businessProfessionalExplanation')}</div>
            <div>• <strong>{t('readability.legalContext.legalProfessional')}:</strong> {t('readability.legalContext.legalProfessionalExplanation')}</div>
          </div>
        </div>
      </div>

      {/* Dynamic Recommendations */}
      <div className="mb-4 p-3 rounded-lg bg-green-500/10 border border-green-500/20">
        <div className="flex items-center gap-2 mb-2">
          <CheckCircle className="h-4 w-4 text-green-400" />
          <span className="text-sm font-medium text-green-300">{t('readability.recommendations.title')}</span>
        </div>
        <div className="text-xs text-white/70 space-y-1">
          {stats.averageGrade > 16 && (
            <div>• {t('readability.recommendations.graduateLevel')}</div>
          )}
          {stats.averageGrade > 13 && stats.averageGrade <= 16 && (
            <div>• {t('readability.recommendations.collegeLevel')}</div>
          )}
          {stats.averageGrade <= 13 && (
            <div>• {t('readability.recommendations.accessible')}</div>
          )}
          {stats.veryDifficultClauses > 0 && (
            <div>• {t('readability.recommendations.complexClauses', { count: stats.veryDifficultClauses })}</div>
          )}
          {stats.averageFleschScore < 30 && (
            <div>• {t('readability.recommendations.veryDifficult')}</div>
          )}
          {stats.difficultyDistribution.easy > stats.totalClauses * 0.3 && (
            <div>• {t('readability.recommendations.mixedComplexity')}</div>
          )}
        </div>
      </div>

      {/* Readability Insights */}
      <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
        <div className="flex items-center gap-2 mb-2">
          <Award className="h-4 w-4 text-blue-400" />
          <span className="text-sm font-medium text-blue-300">{t('readability.readabilityInsights')}</span>
        </div>
        <div className="text-xs text-white/70 space-y-1">
          {stats.averageGrade > 16 && (
            <div>• {t('readability.insights.graduateLevel')}</div>
          )}
          {stats.averageGrade > 12 && stats.averageGrade <= 16 && (
            <div>• {t('readability.insights.aboveHighSchool')}</div>
          )}
          {stats.veryDifficultClauses > 0 && (
            <div>• {t('readability.insights.graduateClauses', { count: stats.veryDifficultClauses })}</div>
          )}
          {stats.averageFleschScore < 30 && (
            <div>• {t('readability.insights.veryDifficultText')}</div>
          )}
          {stats.averageFleschScore < 50 && stats.averageFleschScore >= 30 && (
            <div>• {t('readability.insights.challengingForGeneral')}</div>
          )}
          {stats.difficultyDistribution.easy > stats.totalClauses * 0.5 && (
            <div>• {t('readability.insights.mostAccessible')}</div>
          )}
        </div>
      </div>
    </Card>
  );
}