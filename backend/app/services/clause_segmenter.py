"""
Clause segmentation service for legal documents
"""
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from app.core.logging import get_logger, LogContext

logger = get_logger(__name__)


@dataclass
class ClauseCandidate:
    """Represents a potential clause in the document."""
    text: str
    start_position: int
    end_position: int
    heading: Optional[str] = None
    heading_level: int = 0
    confidence: float = 0.0
    page_number: Optional[int] = None
    bounding_box: Optional[Dict[str, float]] = None


class ClauseSegmenter:
    """Service for segmenting legal documents into individual clauses."""
    
    def __init__(self):
        # Common legal document heading patterns
        self.heading_patterns = [
            # Numbered sections (1., 2., 3. or 1.1, 1.2, etc.)
            r'^(\d+\.(?:\d+\.)*)\s+(.+?)(?:\n|$)',
            # Roman numerals (I., II., III., IV.)
            r'^([IVX]+\.)\s+(.+?)(?:\n|$)',
            # Letters (a), (b), (c) or A., B., C.
            r'^(\([a-z]\)|\(?[A-Z]\.)\s+(.+?)(?:\n|$)',
            # Article/Section keywords
            r'^((?:ARTICLE|SECTION|CLAUSE)\s+\d+(?:\.\d+)*)\s*[:\-]?\s*(.+?)(?:\n|$)',
            # All caps headings
            r'^([A-Z\s]{3,}?)(?:\n|$)',
        ]
        
        # Compile regex patterns for performance
        self.compiled_patterns = [re.compile(pattern, re.MULTILINE | re.IGNORECASE) 
                                for pattern in self.heading_patterns]
        
        # Common legal clause keywords for validation
        self.legal_keywords = {
            'termination', 'liability', 'indemnity', 'confidentiality', 'payment',
            'intellectual property', 'dispute resolution', 'governing law',
            'assignment', 'modification', 'severability', 'entire agreement',
            'force majeure', 'warranties', 'representations', 'damages',
            'breach', 'notice', 'jurisdiction', 'venue', 'arbitration'
        }
    
    async def segment_document(
        self, 
        document_data: Dict[str, Any]
    ) -> List[ClauseCandidate]:
        """
        Segment a processed document into clause candidates.
        
        Args:
            document_data: Processed document from DocumentProcessor
            
        Returns:
            List of clause candidates with metadata
        """
        text = document_data.get("text", "")
        pages = document_data.get("pages", [])
        method = document_data.get("method", "unknown")
        
        with LogContext(logger, method=method, page_count=len(pages)):
            logger.info("Starting clause segmentation")
            
            if method == "document_ai":
                # Use layout information from Document AI
                clauses = await self._segment_with_layout(text, pages)
            else:
                # Use text-based heuristics for fallback methods
                clauses = await self._segment_with_text_analysis(text)
            
            # Post-process and validate clauses
            validated_clauses = await self._validate_and_merge_clauses(clauses)
            
            logger.info(f"Segmentation complete: {len(validated_clauses)} clauses identified")
            
            return validated_clauses
    
    async def _segment_with_layout(
        self, 
        text: str, 
        pages: List[Dict[str, Any]]
    ) -> List[ClauseCandidate]:
        """
        Segment document using Document AI layout information.
        
        Args:
            text: Full document text
            pages: Page layout information from Document AI
            
        Returns:
            List of clause candidates
        """
        clauses = []
        
        for page_info in pages:
            page_num = page_info.get("page_number", 1)
            
            # Use blocks for major sections
            blocks = page_info.get("blocks", [])
            for block in blocks:
                block_text = block.get("text", "").strip()
                if len(block_text) < 50:  # Skip very short blocks
                    continue
                
                # Check if this looks like a clause heading
                heading = self._extract_heading_from_text(block_text)
                if heading:
                    # This block starts with a heading
                    clause = ClauseCandidate(
                        text=block_text,
                        start_position=text.find(block_text),
                        end_position=text.find(block_text) + len(block_text),
                        heading=heading,
                        confidence=block.get("confidence", 0.8),
                        page_number=page_num,
                        bounding_box=block.get("bounding_box")
                    )
                    clauses.append(clause)
                else:
                    # Check if this continues a previous clause
                    if clauses and self._should_merge_with_previous(block_text, clauses[-1]):
                        clauses[-1].text += "\n" + block_text
                        clauses[-1].end_position = text.find(block_text) + len(block_text)
                    else:
                        # This might be a clause without a clear heading
                        clause = ClauseCandidate(
                            text=block_text,
                            start_position=text.find(block_text),
                            end_position=text.find(block_text) + len(block_text),
                            confidence=block.get("confidence", 0.5),
                            page_number=page_num,
                            bounding_box=block.get("bounding_box")
                        )
                        clauses.append(clause)
        
        return clauses
    
    async def _segment_with_text_analysis(self, text: str) -> List[ClauseCandidate]:
        """
        Segment document using text analysis and pattern matching.
        
        Args:
            text: Full document text
            
        Returns:
            List of clause candidates
        """
        clauses = []
        lines = text.split('\n')
        
        current_clause_lines = []
        current_heading = None
        current_start = 0
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Check if this line is a heading
            heading_match = self._extract_heading_from_text(line)
            
            if heading_match:
                # Save previous clause if we have one
                if current_clause_lines:
                    clause_text = '\n'.join(current_clause_lines)
                    clause = ClauseCandidate(
                        text=clause_text,
                        start_position=current_start,
                        end_position=current_start + len(clause_text),
                        heading=current_heading,
                        confidence=self._calculate_clause_confidence(clause_text)
                    )
                    clauses.append(clause)
                
                # Start new clause
                current_clause_lines = [line]
                current_heading = heading_match
                current_start = text.find(line)
            else:
                # Add to current clause
                if current_clause_lines:
                    current_clause_lines.append(line)
                else:
                    # This might be the beginning of the document
                    current_clause_lines = [line]
                    current_start = text.find(line)
        
        # Don't forget the last clause
        if current_clause_lines:
            clause_text = '\n'.join(current_clause_lines)
            clause = ClauseCandidate(
                text=clause_text,
                start_position=current_start,
                end_position=current_start + len(clause_text),
                heading=current_heading,
                confidence=self._calculate_clause_confidence(clause_text)
            )
            clauses.append(clause)
        
        return clauses
    
    def _extract_heading_from_text(self, text: str) -> Optional[str]:
        """
        Extract heading from text line if it matches known patterns.
        
        Args:
            text: Text line to analyze
            
        Returns:
            Heading text if found, None otherwise
        """
        text = text.strip()
        
        # Try each compiled pattern
        for pattern in self.compiled_patterns:
            match = pattern.match(text)
            if match:
                if len(match.groups()) >= 2:
                    # Pattern with heading number and title
                    return f"{match.group(1).strip()} {match.group(2).strip()}"
                else:
                    # Pattern with just heading text
                    return match.group(1).strip()
        
        # Check for all-caps lines (potential headings)
        if len(text) > 5 and text.isupper() and not any(char.isdigit() for char in text):
            return text
        
        return None
    
    def _should_merge_with_previous(
        self, 
        current_text: str, 
        previous_clause: ClauseCandidate
    ) -> bool:
        """
        Determine if current text should be merged with the previous clause.
        
        Args:
            current_text: Current text block
            previous_clause: Previous clause candidate
            
        Returns:
            True if texts should be merged
        """
        # Don't merge if current text looks like a new heading
        if self._extract_heading_from_text(current_text):
            return False
        
        # Merge if previous clause doesn't have much content yet
        if len(previous_clause.text.split()) < 20:
            return True
        
        # Merge if current text starts with lowercase (continuation)
        first_word = current_text.split()[0] if current_text.split() else ""
        if first_word and first_word[0].islower():
            return True
        
        # Don't merge very long blocks
        if len(current_text) > 1000:
            return False
        
        return False
    
    def _calculate_clause_confidence(self, text: str) -> float:
        """
        Calculate confidence score for a clause candidate.
        
        Args:
            text: Clause text
            
        Returns:
            Confidence score between 0 and 1
        """
        confidence = 0.5  # Base confidence
        
        # Length-based confidence
        word_count = len(text.split())
        if 20 <= word_count <= 500:
            confidence += 0.2
        elif word_count < 10:
            confidence -= 0.3
        
        # Legal keyword presence
        text_lower = text.lower()
        keyword_matches = sum(1 for keyword in self.legal_keywords 
                            if keyword in text_lower)
        
        if keyword_matches > 0:
            confidence += min(0.3, keyword_matches * 0.1)
        
        # Sentence structure
        sentence_count = len([s for s in text.split('.') if s.strip()])
        if sentence_count >= 2:
            confidence += 0.1
        
        return min(1.0, max(0.1, confidence))
    
    async def _validate_and_merge_clauses(
        self, 
        clauses: List[ClauseCandidate]
    ) -> List[ClauseCandidate]:
        """
        Validate and merge clause candidates to improve quality.
        
        Args:
            clauses: List of raw clause candidates
            
        Returns:
            List of validated and merged clauses
        """
        if not clauses:
            return []
        
        validated = []
        
        for i, clause in enumerate(clauses):
            # Skip very short clauses unless they have high confidence
            if len(clause.text.split()) < 5 and clause.confidence < 0.8:
                # Try to merge with next clause
                if i < len(clauses) - 1:
                    clauses[i + 1].text = clause.text + "\n" + clauses[i + 1].text
                    clauses[i + 1].start_position = clause.start_position
                continue
            
            # Clean up clause text
            clause.text = self._clean_clause_text(clause.text)
            
            # Assign order
            clause.order = len(validated) + 1
            
            validated.append(clause)
        
        return validated
    
    def _clean_clause_text(self, text: str) -> str:
        """
        Clean and normalize clause text.
        
        Args:
            text: Raw clause text
            
        Returns:
            Cleaned clause text
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove page breaks and similar artifacts
        text = re.sub(r'Page \d+.*?\n', '', text)
        text = re.sub(r'\f', '', text)  # Form feed characters
        
        # Normalize quotes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        
        return text.strip()
    
    async def identify_clause_types(
        self, 
        clauses: List[ClauseCandidate]
    ) -> List[ClauseCandidate]:
        """
        Identify the type/category of each clause based on content.
        
        Args:
            clauses: List of clause candidates
            
        Returns:
            Clauses with identified types
        """
        # Category patterns
        category_patterns = {
            "Termination": [
                r"terminat\w*", r"end\s+this\s+agreement", r"expir\w*",
                r"breach", r"cancel\w*"
            ],
            "Liability": [
                r"liabilit\w*", r"damages", r"liable", r"responsible",
                r"loss\w*", r"harm"
            ],
            "Indemnity": [
                r"indemnif\w*", r"hold\s+harmless", r"defend",
                r"reimburse"
            ],
            "Confidentiality": [
                r"confidential\w*", r"non.?disclosure", r"proprietary",
                r"trade\s+secret"
            ],
            "Payment": [
                r"payment", r"fee\w*", r"cost\w*", r"invoice",
                r"billing", r"price", r"amount"
            ],
            "Intellectual Property": [
                r"intellectual\s+property", r"copyright", r"trademark",
                r"patent", r"ip\s+rights"
            ],
            "Dispute Resolution": [
                r"dispute", r"arbitration", r"mediation", r"litigation",
                r"court", r"jurisdiction"
            ],
            "Governing Law": [
                r"governing\s+law", r"applicable\s+law", r"jurisdiction",
                r"venue"
            ],
            "Assignment": [
                r"assign\w*", r"transfer", r"delegate"
            ],
            "Modification": [
                r"modif\w*", r"amend\w*", r"chang\w*", r"alter\w*"
            ]
        }
        
        for clause in clauses:
            text_lower = clause.text.lower()
            
            # Check each category
            best_match = ("Other", 0)
            
            for category, patterns in category_patterns.items():
                match_count = sum(1 for pattern in patterns 
                                if re.search(pattern, text_lower))
                
                if match_count > best_match[1]:
                    best_match = (category, match_count)
            
            clause.category = best_match[0]
        
        return clauses