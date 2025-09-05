"""
Readability metrics service using textstat for Flesch-Kincaid analysis
"""
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import re

import textstat

from app.core.logging import get_logger, LogContext

logger = get_logger(__name__)


@dataclass
class ReadabilityMetrics:
    """Comprehensive readability analysis results."""
    flesch_reading_ease: float
    flesch_kincaid_grade: float
    gunning_fog: float
    smog_index: float
    ari: float  # Automated Readability Index
    cli: float  # Coleman-Liau Index
    word_count: int
    sentence_count: int
    syllable_count: int
    avg_sentence_length: float
    avg_syllables_per_word: float
    reading_level: str  # Human-readable description
    complexity_score: float  # 0-1 normalized complexity


class ReadabilityService:
    """Service for calculating readability metrics and improvements."""
    
    def __init__(self):
        # Configure textstat language
        textstat.set_lang("en")
        
        # Reading level mappings
        self.grade_level_descriptions = {
            (0, 5): "Elementary School",
            (6, 8): "Middle School", 
            (9, 12): "High School",
            (13, 16): "College Level",
            (17, 100): "Graduate Level"
        }
        
        # Flesch Reading Ease score descriptions
        self.flesch_descriptions = {
            (90, 100): "Very Easy",
            (80, 90): "Easy",
            (70, 80): "Fairly Easy",
            (60, 70): "Standard",
            (50, 60): "Fairly Difficult",
            (30, 50): "Difficult",
            (0, 30): "Very Difficult"
        }
    
    async def analyze_text_readability(self, text: str) -> ReadabilityMetrics:
        """
        Analyze readability of a text using multiple metrics.
        
        Args:
            text: Input text to analyze
            
        Returns:
            Comprehensive readability analysis
        """
        if not text or not text.strip():
            return self._create_empty_metrics()
        
        with LogContext(logger, text_length=len(text)):
            logger.info("Analyzing text readability")
            
            # Clean and preprocess text
            cleaned_text = self._preprocess_text(text)
            
            if not cleaned_text or len(cleaned_text.split()) < 3:
                logger.warning("Text too short for reliable readability analysis")
                return self._create_empty_metrics()
            
            try:
                # Calculate core metrics using textstat
                flesch_ease = textstat.flesch_reading_ease(cleaned_text)
                flesch_grade = textstat.flesch_kincaid_grade(cleaned_text)
                gunning_fog = textstat.gunning_fog(cleaned_text)
                smog = textstat.smog_index(cleaned_text)
                ari = textstat.automated_readability_index(cleaned_text)
                cli = textstat.coleman_liau_index(cleaned_text)
                
                # Basic text statistics
                word_count = textstat.lexicon_count(cleaned_text)
                sentence_count = textstat.sentence_count(cleaned_text)
                syllable_count = textstat.syllable_count(cleaned_text)
                
                # Derived metrics
                avg_sentence_length = word_count / max(1, sentence_count)
                avg_syllables_per_word = syllable_count / max(1, word_count)
                
                # Determine reading level
                reading_level = self._determine_reading_level(flesch_grade)
                
                # Calculate complexity score (0-1, where 1 is most complex)
                complexity_score = self._calculate_complexity_score(
                    flesch_ease, flesch_grade, gunning_fog, smog
                )
                
                metrics = ReadabilityMetrics(
                    flesch_reading_ease=flesch_ease,
                    flesch_kincaid_grade=flesch_grade,
                    gunning_fog=gunning_fog,
                    smog_index=smog,
                    ari=ari,
                    cli=cli,
                    word_count=word_count,
                    sentence_count=sentence_count,
                    syllable_count=syllable_count,
                    avg_sentence_length=avg_sentence_length,
                    avg_syllables_per_word=avg_syllables_per_word,
                    reading_level=reading_level,
                    complexity_score=complexity_score
                )
                
                logger.info(f"Readability analysis complete: Grade {flesch_grade:.1f}, Ease {flesch_ease:.1f}")
                
                return metrics
                
            except Exception as e:
                logger.error(f"Readability analysis failed: {e}")
                return self._create_fallback_metrics(text)
    
    def _preprocess_text(self, text: str) -> str:
        """
        Clean and preprocess text for readability analysis.
        
        Args:
            text: Raw text
            
        Returns:
            Cleaned text suitable for analysis
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove common legal formatting artifacts
        text = re.sub(r'\([a-z]\)', '', text)  # Remove (a), (b), (c) markers
        text = re.sub(r'\b[IVX]+\.', '', text)  # Remove Roman numerals
        text = re.sub(r'\b\d+\.\s*\d+\.', '', text)  # Remove section numbers like 2.1.
        
        # Fix common punctuation issues
        text = re.sub(r'(?<=[a-z])\.(?=[A-Z])', '. ', text)  # Ensure space after periods
        text = re.sub(r'(?<=[a-z]);(?=[A-Z])', '; ', text)  # Ensure space after semicolons
        
        # Remove excess punctuation that might confuse analysis
        text = re.sub(r'[;:]{2,}', ';', text)  # Multiple punctuation marks
        text = re.sub(r'\.{2,}', '.', text)  # Multiple periods
        
        # Normalize quotes and special characters
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        
        return text.strip()
    
    def _determine_reading_level(self, grade_level: float) -> str:
        """
        Convert grade level to human-readable description.
        
        Args:
            grade_level: Numerical grade level
            
        Returns:
            Reading level description
        """
        grade = max(0, grade_level)  # Ensure non-negative
        
        for (min_grade, max_grade), description in self.grade_level_descriptions.items():
            if min_grade <= grade <= max_grade:
                return description
        
        return "Graduate Level"  # Fallback for very high grades
    
    def _calculate_complexity_score(
        self, 
        flesch_ease: float, 
        flesch_grade: float, 
        gunning_fog: float, 
        smog: float
    ) -> float:
        """
        Calculate normalized complexity score.
        
        Args:
            flesch_ease: Flesch Reading Ease score
            flesch_grade: Flesch-Kincaid Grade Level
            gunning_fog: Gunning Fog Index
            smog: SMOG Index
            
        Returns:
            Complexity score (0-1, where 1 is most complex)
        """
        # Flesch ease score: higher = easier (invert for complexity)
        ease_complexity = max(0, (100 - flesch_ease) / 100)
        
        # Grade level complexity (normalize to 0-1, cap at grade 20)
        grade_complexity = min(1, flesch_grade / 20)
        
        # Fog index complexity (normalize, cap at 20)
        fog_complexity = min(1, gunning_fog / 20)
        
        # SMOG complexity (normalize, cap at 20)
        smog_complexity = min(1, smog / 20)
        
        # Weighted average of complexity measures
        complexity_score = (
            ease_complexity * 0.3 +
            grade_complexity * 0.4 +
            fog_complexity * 0.2 +
            smog_complexity * 0.1
        )
        
        return max(0, min(1, complexity_score))
    
    def _create_empty_metrics(self) -> ReadabilityMetrics:
        """Create empty readability metrics for invalid text."""
        return ReadabilityMetrics(
            flesch_reading_ease=0.0,
            flesch_kincaid_grade=0.0,
            gunning_fog=0.0,
            smog_index=0.0,
            ari=0.0,
            cli=0.0,
            word_count=0,
            sentence_count=0,
            syllable_count=0,
            avg_sentence_length=0.0,
            avg_syllables_per_word=0.0,
            reading_level="N/A",
            complexity_score=0.0
        )
    
    def _create_fallback_metrics(self, text: str) -> ReadabilityMetrics:
        """Create fallback metrics when textstat fails."""
        word_count = len(text.split())
        sentence_count = len(re.findall(r'[.!?]+', text))
        
        return ReadabilityMetrics(
            flesch_reading_ease=50.0,  # Assume average difficulty
            flesch_kincaid_grade=12.0,
            gunning_fog=12.0,
            smog_index=12.0,
            ari=12.0,
            cli=12.0,
            word_count=word_count,
            sentence_count=max(1, sentence_count),
            syllable_count=word_count * 2,  # Rough estimate
            avg_sentence_length=word_count / max(1, sentence_count),
            avg_syllables_per_word=2.0,
            reading_level="High School",
            complexity_score=0.6
        )
    
    async def compare_readability(
        self, 
        original_text: str, 
        simplified_text: str
    ) -> Dict[str, Any]:
        """
        Compare readability between original and simplified text.
        
        Args:
            original_text: Original complex text
            simplified_text: Simplified version
            
        Returns:
            Readability comparison analysis
        """
        with LogContext(logger, original_len=len(original_text), simplified_len=len(simplified_text)):
            logger.info("Comparing text readability")
            
            # Analyze both texts
            original_metrics = await self.analyze_text_readability(original_text)
            simplified_metrics = await self.analyze_text_readability(simplified_text)
            
            # Calculate improvements
            improvements = self._calculate_improvements(original_metrics, simplified_metrics)
            
            return {
                "original": self._metrics_to_dict(original_metrics),
                "simplified": self._metrics_to_dict(simplified_metrics),
                "improvements": improvements,
                "comparison_summary": self._generate_comparison_summary(improvements)
            }
    
    def _calculate_improvements(
        self, 
        original: ReadabilityMetrics, 
        simplified: ReadabilityMetrics
    ) -> Dict[str, Any]:
        """
        Calculate readability improvements between two texts.
        
        Args:
            original: Original text metrics
            simplified: Simplified text metrics
            
        Returns:
            Improvement analysis
        """
        improvements = {
            "grade_level_delta": original.flesch_kincaid_grade - simplified.flesch_kincaid_grade,
            "ease_score_delta": simplified.flesch_reading_ease - original.flesch_reading_ease,
            "complexity_reduction": original.complexity_score - simplified.complexity_score,
            "avg_sentence_length_delta": original.avg_sentence_length - simplified.avg_sentence_length,
            "word_count_change": simplified.word_count - original.word_count,
            "word_count_change_percent": (
                (simplified.word_count - original.word_count) / max(1, original.word_count) * 100
            )
        }
        
        # Determine if improvements were made
        improvements["grade_level_improved"] = improvements["grade_level_delta"] > 0
        improvements["ease_improved"] = improvements["ease_score_delta"] > 0
        improvements["complexity_reduced"] = improvements["complexity_reduction"] > 0
        improvements["sentences_simplified"] = improvements["avg_sentence_length_delta"] > 0
        
        # Overall improvement score (0-1, where 1 is maximum improvement)
        improvement_factors = [
            min(1, max(0, improvements["grade_level_delta"] / 5)),  # Grade level improvement
            min(1, max(0, improvements["ease_score_delta"] / 20)),  # Ease improvement
            min(1, max(0, improvements["complexity_reduction"])),   # Complexity reduction
        ]
        
        improvements["overall_improvement_score"] = sum(improvement_factors) / len(improvement_factors)
        
        return improvements
    
    def _generate_comparison_summary(self, improvements: Dict[str, Any]) -> str:
        """
        Generate human-readable summary of readability improvements.
        
        Args:
            improvements: Improvement metrics
            
        Returns:
            Summary text
        """
        parts = []
        
        # Grade level improvement
        grade_delta = improvements["grade_level_delta"]
        if grade_delta > 1:
            parts.append(f"Reading level reduced by {grade_delta:.1f} grades")
        elif grade_delta > 0:
            parts.append("Reading level slightly improved")
        else:
            parts.append("No significant grade level change")
        
        # Ease score improvement
        ease_delta = improvements["ease_score_delta"]
        if ease_delta > 10:
            parts.append("significantly easier to read")
        elif ease_delta > 5:
            parts.append("moderately easier to read")
        elif ease_delta > 0:
            parts.append("slightly easier to read")
        
        # Word count change
        word_change_pct = improvements["word_count_change_percent"]
        if abs(word_change_pct) > 20:
            direction = "increased" if word_change_pct > 0 else "decreased"
            parts.append(f"text length {direction} by {abs(word_change_pct):.0f}%")
        
        # Overall assessment
        overall_score = improvements["overall_improvement_score"]
        if overall_score > 0.7:
            assessment = "Excellent readability improvement achieved."
        elif overall_score > 0.4:
            assessment = "Good readability improvement achieved."
        elif overall_score > 0.1:
            assessment = "Modest readability improvement achieved."
        else:
            assessment = "Limited readability improvement detected."
        
        summary_text = ". ".join([s for s in parts if s]) + ". " + assessment
        
        return summary_text
    
    def _metrics_to_dict(self, metrics: ReadabilityMetrics) -> Dict[str, Any]:
        """Convert ReadabilityMetrics to dictionary."""
        return {
            "flesch_reading_ease": round(metrics.flesch_reading_ease, 1),
            "flesch_kincaid_grade": round(metrics.flesch_kincaid_grade, 1),
            "gunning_fog": round(metrics.gunning_fog, 1),
            "smog_index": round(metrics.smog_index, 1),
            "ari": round(metrics.ari, 1),
            "cli": round(metrics.cli, 1),
            "word_count": metrics.word_count,
            "sentence_count": metrics.sentence_count,
            "syllable_count": metrics.syllable_count,
            "avg_sentence_length": round(metrics.avg_sentence_length, 1),
            "avg_syllables_per_word": round(metrics.avg_syllables_per_word, 2),
            "reading_level": metrics.reading_level,
            "complexity_score": round(metrics.complexity_score, 3)
        }
    
    async def analyze_document_readability(
        self, 
        clause_comparisons: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze overall document readability from clause comparisons.
        
        Args:
            clause_comparisons: List of clause readability comparisons
            
        Returns:
            Document-level readability analysis
        """
        if not clause_comparisons:
            return {
                "total_clauses": 0,
                "avg_grade_level_reduction": 0.0,
                "avg_ease_improvement": 0.0,
                "clauses_improved": 0,
                "overall_improvement_score": 0.0,
                "reading_level_distribution": {}
            }
        
        # Aggregate improvements
        total_grade_reduction = 0.0
        total_ease_improvement = 0.0
        clauses_improved = 0
        overall_scores = []
        
        reading_levels = {"Elementary School": 0, "Middle School": 0, "High School": 0, 
                         "College Level": 0, "Graduate Level": 0}
        
        for comparison in clause_comparisons:
            improvements = comparison.get("improvements", {})
            simplified = comparison.get("simplified", {})
            
            total_grade_reduction += improvements.get("grade_level_delta", 0)
            total_ease_improvement += improvements.get("ease_score_delta", 0)
            
            if improvements.get("overall_improvement_score", 0) > 0.1:
                clauses_improved += 1
            
            overall_scores.append(improvements.get("overall_improvement_score", 0))
            
            # Count reading levels
            reading_level = simplified.get("reading_level", "High School")
            if reading_level in reading_levels:
                reading_levels[reading_level] += 1
        
        num_clauses = len(clause_comparisons)
        
        return {
            "total_clauses": num_clauses,
            "avg_grade_level_reduction": total_grade_reduction / num_clauses,
            "avg_ease_improvement": total_ease_improvement / num_clauses,
            "clauses_improved": clauses_improved,
            "improvement_rate": clauses_improved / num_clauses,
            "overall_improvement_score": sum(overall_scores) / num_clauses,
            "reading_level_distribution": reading_levels,
            "document_readability_grade": self._calculate_document_grade(clause_comparisons)
        }
    
    def _calculate_document_grade(self, clause_comparisons: List[Dict[str, Any]]) -> str:
        """
        Calculate overall document readability grade.
        
        Args:
            clause_comparisons: Clause comparison data
            
        Returns:
            Document readability grade (A-F)
        """
        if not clause_comparisons:
            return "N/A"
        
        # Calculate weighted average improvement score
        total_improvement = sum(
            comp.get("improvements", {}).get("overall_improvement_score", 0)
            for comp in clause_comparisons
        )
        
        avg_improvement = total_improvement / len(clause_comparisons)
        
        # Grade based on improvement score
        if avg_improvement >= 0.8:
            return "A"
        elif avg_improvement >= 0.6:
            return "B" 
        elif avg_improvement >= 0.4:
            return "C"
        elif avg_improvement >= 0.2:
            return "D"
        else:
            return "F"
    
    async def get_readability_recommendations(
        self, 
        metrics: ReadabilityMetrics
    ) -> List[str]:
        """
        Get recommendations for improving text readability.
        
        Args:
            metrics: Current readability metrics
            
        Returns:
            List of improvement recommendations
        """
        recommendations = []
        
        # Grade level recommendations
        if metrics.flesch_kincaid_grade > 12:
            recommendations.append("Break down complex sentences into shorter, simpler ones")
        if metrics.flesch_kincaid_grade > 16:
            recommendations.append("Replace technical jargon with everyday language")
        
        # Sentence length recommendations
        if metrics.avg_sentence_length > 25:
            recommendations.append("Reduce average sentence length - aim for 15-20 words per sentence")
        elif metrics.avg_sentence_length > 20:
            recommendations.append("Consider shortening some longer sentences")
        
        # Syllable recommendations  
        if metrics.avg_syllables_per_word > 2.0:
            recommendations.append("Use simpler words with fewer syllables where possible")
        
        # Flesch ease recommendations
        if metrics.flesch_reading_ease < 30:
            recommendations.append("Text is very difficult - significant simplification needed")
        elif metrics.flesch_reading_ease < 50:
            recommendations.append("Text is difficult - consider simplifying vocabulary and structure")
        elif metrics.flesch_reading_ease < 60:
            recommendations.append("Text could be clearer - minor simplifications would help")
        
        # Structure recommendations
        if metrics.sentence_count < 3 and metrics.word_count > 100:
            recommendations.append("Break this long paragraph into multiple sentences")
        
        if not recommendations:
            recommendations.append("Text readability is good - no major improvements needed")
        
        return recommendations