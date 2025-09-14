"""
Clause segmentation service for legal documents
"""
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import numpy as np

from app.core.logging import get_logger, LogContext
from app.services.embeddings_service import EmbeddingsService

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
    order: int = 0
    category: str = "Other"


class ClauseSegmenter:
    """Service for segmenting legal documents into individual clauses."""
    
    def __init__(self):
        # Initialize embeddings service for semantic similarity fallback
        try:
            self.embeddings_service = EmbeddingsService()
            self.semantic_enabled = True
        except Exception as e:
            logger.warning(f"Failed to initialize embeddings service: {e}")
            self.embeddings_service = None
            self.semantic_enabled = False

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

        # Representative example clauses for semantic similarity matching
        self.category_examples = {
            "Termination": [
                "This Agreement shall terminate immediately upon material breach.",
                "Either party may terminate this Agreement with thirty (30) days written notice.",
                "This Agreement expires on December 31, 2025 unless renewed.",
                "Upon termination, all obligations and rights shall cease."
            ],
            "Liability": [
                "Company shall not be liable for any indirect or consequential damages.",
                "Customer's liability for damages shall be limited to the amount paid.",
                "Each party shall be responsible for their own negligent acts.",
                "Liability is limited to direct damages not exceeding the contract value."
            ],
            "Indemnity": [
                "Company shall indemnify Customer against third-party claims.",
                "Each party agrees to hold the other harmless from any losses.",
                "Contractor shall defend against all intellectual property claims.",
                "Indemnification includes attorney fees and court costs."
            ],
            "Confidentiality": [
                "All confidential information must remain private and secure.",
                "Neither party shall disclose proprietary information to third parties.",
                "This non-disclosure agreement covers all trade secrets.",
                "Confidential information survives termination for five years."
            ],
            "Payment": [
                "Payment is due within thirty (30) days of invoice receipt.",
                "All fees are non-refundable and payable in advance.",
                "Late payments incur interest at 1.5% per month.",
                "Expenses shall be reimbursed upon submission of receipts."
            ],
            "IP Ownership": [
                "All work product shall be owned exclusively by Company.",
                "Customer retains all rights to their existing intellectual property.",
                "Contractor assigns all invention rights to Company.",
                "Copyrights in deliverables vest immediately in Client."
            ],
            "Dispute Resolution": [
                "Any disputes shall be resolved through binding arbitration.",
                "Parties agree to mediate before pursuing litigation.",
                "All claims must be filed in the courts of California.",
                "Disputes shall be resolved through good faith negotiation first."
            ],
            "Governing Law": [
                "This Agreement is governed by California law.",
                "The laws of New York shall apply to this contract.",
                "Jurisdiction is exclusively in Delaware courts.",
                "This Agreement is construed under federal law."
            ],
            "Assignment": [
                "This Agreement may not be assigned without written consent.",
                "Rights and obligations may be transferred with approval.",
                "No delegation of duties is permitted without permission.",
                "Assignment binds successors and assigns."
            ],
            "Modification": [
                "This Agreement may only be modified in writing.",
                "No oral amendments or changes are permitted.",
                "Changes require signed agreement by both parties.",
                "Waivers must be in writing to be effective."
            ],
            "Warranties": [
                "Company warrants the software will perform as described.",
                "All services are provided 'as is' without warranty.",
                "Contractor guarantees workmanship for twelve months.",
                "Products are warranted against defects in materials."
            ],
            "Force Majeure": [
                "Performance is excused due to acts of God.",
                "Delays caused by uncontrollable circumstances are excused.",
                "Force majeure includes natural disasters and government action.",
                "Performance may be suspended during force majeure events."
            ],
            "Definitions": [
                "Confidential Information means all non-public technical data.",
                "Services shall include all activities described in Exhibit A.",
                "Effective Date means the date this Agreement is signed.",
                "Intellectual Property includes all copyrights and patents."
            ]
        }

        # Cache for embeddings to avoid recomputation
        self._category_embeddings = None
    
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
        # Comprehensive category patterns with expanded legal terminology
        category_patterns = {
            "Termination": [
                # Core termination terms
                r"\bterminate?\b", r"\bterminating\b", r"\btermination\b", r"\bterminated\b",
                r"\bend\s+(?:this|the|such)?\s*(?:agreement|contract)\b", r"\bexpir\w*\b",
                r"\bcancel\w*\b", r"\brescind\b", r"\bvoid\b", r"\bnull\b",
                # Breach and violation
                r"\bbreach\b", r"\bviolat\w*\b", r"\bdefault\b", r"\bnon.?compliance\b",
                r"\bmaterial\s+breach\b", r"\bfundamental\s+breach\b",
                # Notice and dissolution
                r"\bnotice\s+(?:of|to)\s+(?:terminate|termination)\b", r"\bdissol\w*\b",
                r"\bwithdr\w*\b", r"\bquit\b", r"\bexit\b", r"\bceasing?\b", r"\bcease\b",
                # Automatic termination
                r"\bautomatic\w*\s+terminat\w*\b", r"\bimmediate\s+terminat\w*\b",
                # Contract end
                r"\bcontract\s+(?:end|expir)\w*\b", r"\bagreement\s+(?:end|expir)\w*\b",
                r"\beffective\s+date\s+of\s+terminat\w*\b"
            ],
            "Liability": [
                # Core liability terms
                r"\bliabilit\w*\b", r"\bliable\b", r"\bresponsib\w*\b",
                r"\bdamages?\b", r"\bloss(?:es)?\b", r"\bharm\b", r"\binjur\w*\b",
                # Limitation of liability
                r"\blimit\w*\s+(?:of\s+)?liabilit\w*\b", r"\bexclud\w*\s+liabilit\w*\b",
                r"\bno\s+liabilit\w*\b", r"\bdisclaim\w*\s+liabilit\w*\b",
                # Types of damages
                r"\bconsequential\s+damage\w*\b", r"\bincidental\s+damage\w*\b",
                r"\bpunitive\s+damage\w*\b", r"\bindirect\s+damage\w*\b",
                r"\bspecial\s+damage\w*\b", r"\bexemplary\s+damage\w*\b",
                # Causation and fault
                r"\bcaus\w*\s+(?:by|of|from)\b", r"\bfault\b", r"\bnegligen\w*\b",
                r"\bmisconduct\b", r"\bwrongful\b", r"\btort\b",
                # Financial responsibility
                r"\bpay\w*\s+(?:for\s+)?damage\w*\b", r"\bcompensate?\b", r"\bcompensation\b",
                r"\breimburse\w*\b", r"\bmake\s+good\b", r"\bcovering?\s+(?:the\s+)?(?:cost|expense)\w*\b"
            ],
            "Indemnity": [
                # Core indemnification
                r"\bindemnif\w*\b", r"\bindemnity\b", r"\bhold\s+harmless\b",
                r"\bdefend\b", r"\bprotect\b", r"\bsave\s+harmless\b",
                # Defense obligations
                r"\bdefend\s+(?:and\s+)?(?:indemnif\w*|hold\s+harmless)\b",
                r"\bdefense\s+(?:of|against)\b", r"\blegal\s+defense\b",
                # Reimbursement and costs
                r"\breimburse\w*\b", r"\bpay\s+(?:all\s+)?(?:cost|expense)\w*\b",
                r"\battorney\s*(?:'?s)?\s+fee\w*\b", r"\blegal\s+fee\w*\b", r"\bcourt\s+cost\w*\b",
                # Third party claims
                r"\bthird\s+party\s+claim\w*\b", r"\bclaim\w*\s+(?:by|from)\s+third\s+part\w*\b",
                r"\bsuit\w*\s+(?:by|from|against)\b", r"\baction\w*\s+(?:by|from|against)\b",
                # Mutual indemnification
                r"\bmutual\s+indemnif\w*\b", r"\breciprocal\s+indemnit\w*\b",
                # Indemnification scope
                r"\bindemnif\w*\s+(?:against|for|from)\b", r"\bhold\s+\w+\s+harmless\s+(?:against|for|from)\b"
            ],
            "Confidentiality": [
                # Core confidentiality
                r"\bconfidential\w*\b", r"\bnon.?disclosure\b", r"\bNDA\b",
                r"\bproprietary\b", r"\btrade\s+secret\w*\b", r"\bsecret\b", r"\bprivate\b",
                # Information protection
                r"\bprotect\w*\s+information\b", r"\bsensitive\s+information\b",
                r"\bconfidential\s+information\b", r"\bproprietary\s+information\b",
                # Disclosure restrictions
                r"\bnot\s+disclos\w*\b", r"\bprohibit\w*\s+disclos\w*\b", r"\brestrict\w*\s+disclos\w*\b",
                r"\bforbid\w*\s+disclos\w*\b", r"\bkeep\s+(?:confidential|secret)\b",
                # Non-use provisions
                r"\bnon.?use\b", r"\bnot\s+us\w*\s+(?:for|except)\b", r"\bprohibit\w*\s+us\w*\b",
                # Exceptions and carve-outs
                r"\bpublic\s+(?:domain|knowledge)\b", r"\bpublicly\s+available\b",
                r"\bindependent\w*\s+develop\w*\b", r"\bright\w*\s+retain\w*\b",
                # Duration and survival
                r"\bsurviv\w*\s+(?:termination|expir\w*)\b", r"\bperpetual\s+confidentialit\w*\b",
                r"\bconfidentialit\w*\s+(?:period|term)\b"
            ],
            "Payment": [
                # Core payment terms
                r"\bpayment\w*\b", r"\bpay\b", r"\bfee\w*\b", r"\bcost\w*\b", r"\bprice\w*\b",
                r"\bamount\w*\b", r"\bsum\w*\b", r"\bcharg\w*\b", r"\bbill\w*\b",
                # Invoice and billing
                r"\binvoice\w*\b", r"\bbilling\b", r"\bstatement\w*\b", r"\baccount\w*\b",
                # Payment terms
                r"\bdue\s+(?:date|on|within)\b", r"\bnet\s+\d+\b", r"\b(?:30|60|90)\s+day\w*\b",
                r"\bupon\s+(?:receipt|completion|delivery)\b", r"\bin\s+advance\b",
                # Payment methods
                r"\bwire\s+transfer\b", r"\bcheck\b", r"\bcredit\s+card\b", r"\bbank\s+transfer\b",
                r"\bpaypal\b", r"\belectronic\s+payment\b", r"\bACH\b",
                # Late payment
                r"\blate\s+(?:fee|payment|penalty)\b", r"\binterest\s+(?:on|for)\s+late\b",
                r"\bdelinquen\w*\b", r"\boverdue\b", r"\bdefault\s+(?:in\s+)?payment\b",
                # Taxes and expenses
                r"\btax\w*\b", r"\bVAT\b", r"\bsales\s+tax\b", r"\bwithhold\w*\s+tax\b",
                r"\bexpens\w*\b", r"\breimburs\w*\s+expens\w*\b", r"\bout.?of.?pocket\b"
            ],
            "IP Ownership": [
                # Intellectual property
                r"\bintellectual\s+property\b", r"\bIP\s+(?:right|ownership)\w*\b",
                r"\bcopyright\w*\b", r"\btrademark\w*\b", r"\bpatent\w*\b",
                r"\btrade\s+(?:mark|name)\w*\b", r"\bservice\s+mark\w*\b",
                # Ownership and rights
                r"\bownership\b", r"\bown\w*\s+(?:right|title)\w*\b", r"\bproperty\s+right\w*\b",
                r"\btitle\s+(?:to|in)\b", r"\bright\w*\s+(?:to|in)\b", r"\bexclusive\s+right\w*\b",
                # Work product and creations
                r"\bwork\s+product\b", r"\bderivative\s+work\w*\b", r"\boriginal\s+work\w*\b",
                r"\bcreation\w*\b", r"\binvention\w*\b", r"\bdevelopment\w*\b",
                # Assignment and licensing
                r"\bassign\w*\s+(?:right|title|IP|intellectual\s+property)\b",
                r"\blicens\w*\s+(?:right|IP|intellectual\s+property)\b",
                r"\btransfer\s+(?:right|ownership|title)\b",
                # Moral rights and attribution
                r"\bmoral\s+right\w*\b", r"\battribution\b", r"\bcredit\b", r"\bauthor\w*\b"
            ],
            "Dispute Resolution": [
                # Core dispute terms
                r"\bdispute\w*\b", r"\bcontroversy\b", r"\bdisagreement\w*\b",
                r"\bconflict\w*\b", r"\bclaim\w*\b", r"\bgrievance\w*\b",
                # Alternative dispute resolution
                r"\barbitration\b", r"\bmediat\w*\b", r"\bnegotiat\w*\b",
                r"\bconciliat\w*\b", r"\bADR\b", r"\balternative\s+dispute\s+resolution\b",
                # Court and litigation
                r"\blitigation\b", r"\bcourt\w*\b", r"\btribunal\w*\b", r"\bjudg\w*\b",
                r"\bjury\b", r"\btrial\b", r"\blawsuit\w*\b", r"\bsuit\w*\b",
                # Jurisdiction and venue
                r"\bjurisdiction\b", r"\bvenue\b", r"\bcompetent\s+court\w*\b",
                r"\bexclusive\s+jurisdiction\b", r"\bsubmit\s+to\s+jurisdiction\b",
                # Binding decisions
                r"\bbinding\s+(?:arbitration|decision|resolution)\b",
                r"\bfinal\s+(?:and\s+)?binding\b", r"\bnon.?appealable\b",
                # Escalation procedures
                r"\bescalat\w*\b", r"\bfirst\s+(?:attempt|try|discuss)\b",
                r"\bgood\s+faith\s+(?:effort|negotiat\w*)\b"
            ],
            "Governing Law": [
                # Governing law
                r"\bgoverning\s+law\b", r"\bapplicable\s+law\b", r"\bconstrued\s+(?:under|in\s+accordance\s+with)\b",
                r"\binterpreted\s+(?:under|in\s+accordance\s+with)\b",
                # Jurisdiction references
                r"\bjurisdiction\b", r"\bstate\s+(?:of\s+)?\w+\s+law\b", r"\bfederal\s+law\b",
                r"\bcountry\s+(?:of\s+)?\w+\s+law\b", r"\blaw\w*\s+of\s+(?:the\s+)?(?:state|country)\b",
                # Venue
                r"\bvenue\b", r"\bproper\s+venue\b", r"\bexclusive\s+venue\b",
                r"\bsubmit\s+to\s+(?:the\s+)?jurisdiction\b",
                # Choice of law
                r"\bchoice\s+of\s+law\b", r"\bselection\s+of\s+law\b",
                r"\blaw\s+(?:governing|applicable\s+to)\b"
            ],
            "Assignment": [
                # Assignment of rights/obligations
                r"\bassign\w*\b", r"\btransfer\w*\b", r"\bconvey\w*\b",
                r"\bdelegate\w*\b", r"\bsubcontract\w*\b", r"\bnovation\b",
                # Assignment restrictions
                r"\bnot\s+(?:assign|transfer)\b", r"\bprohibit\w*\s+(?:assignment|transfer)\b",
                r"\brestrict\w*\s+(?:assignment|transfer)\b", r"\bforbid\w*\s+(?:assignment|transfer)\b",
                # Consent requirements
                r"\bconsent\s+(?:to\s+)?(?:assign|transfer)\b", r"\bapproval\s+(?:for\s+)?(?:assign|transfer)\b",
                r"\bwritten\s+consent\b", r"\bprior\s+(?:written\s+)?(?:consent|approval)\b",
                # Assignment effects
                r"\bbind\w*\s+(?:successor|assign)\w*\b", r"\bsuccessor\w*\s+(?:and\s+)?assign\w*\b",
                r"\benure\w*\s+(?:to\s+)?(?:benefit|successor)\b"
            ],
            "Modification": [
                # Amendment and modification
                r"\bmodif\w*\b", r"\bamend\w*\b", r"\bchange\w*\b", r"\balter\w*\b",
                r"\bvaried?\b", r"\brevise?\b", r"\bupdate\w*\b", r"\badjust\w*\b",
                # Waiver and supplement
                r"\bwaiv\w*\b", r"\bsupplemented?\b", r"\baddendum\b", r"\baddenda\b",
                # Written requirements
                r"\bwritten\s+(?:amendment|modification|change)\b",
                r"\bin\s+writing\b", r"\bsign\w*\s+(?:amendment|modification)\b",
                # No oral modifications
                r"\bno\s+oral\s+(?:amendment|modification|change)\b",
                r"\bwritten\s+agreement\s+(?:only|required)\b",
                # Entire agreement
                r"\bentire\s+agreement\b", r"\bcomplete\s+agreement\b", r"\bfull\s+agreement\b",
                r"\bintegrat\w*\s+agreement\b", r"\bsupersede\w*\b"
            ],
            "Warranties": [
                # Express warranties
                r"\bwarrant\w*\b", r"\bguarantee\w*\b", r"\brepresent\w*\b",
                r"\bassur\w*\b", r"\bcovenant\w*\b", r"\bundertaking\w*\b",
                # Warranty disclaimers
                r"\bdisclaim\w*\s+warrant\w*\b", r"\bno\s+warrant\w*\b", r"\bas\s+is\b",
                r"\bwithout\s+warrant\w*\b", r"\bexclud\w*\s+warrant\w*\b",
                # Types of warranties
                r"\bmerchantabilit\w*\b", r"\bfitness\s+for\s+(?:a\s+particular\s+)?purpose\b",
                r"\bnon.?infringement\b", r"\btitle\s+warrant\w*\b",
                # Warranty period
                r"\bwarrant\w*\s+period\b", r"\bguarantee\w*\s+period\b",
                r"\bdefect\w*\b", r"\bconform\w*\s+to\s+specification\w*\b"
            ],
            "Force Majeure": [
                # Force majeure events
                r"\bforce\s+majeure\b", r"\bact\w*\s+of\s+god\b", r"\buncontrollable\s+circumstance\w*\b",
                r"\bunavoidable\s+(?:event|circumstance)\w*\b", r"\bbeyond\s+(?:reasonable\s+)?control\b",
                # Natural disasters
                r"\bearthquake\w*\b", r"\bflood\w*\b", r"\bhurricane\w*\b", r"\bfire\w*\b",
                r"\bnatural\s+disaster\w*\b", r"\bcatastroph\w*\b",
                # Human-caused events
                r"\bwar\b", r"\bterrorism\b", r"\bstrike\w*\b", r"\blabor\s+dispute\w*\b",
                r"\bgovernment\w*\s+action\w*\b", r"\bregulatory\s+action\w*\b",
                # Performance excuses
                r"\bexcus\w*\s+(?:performance|delay)\b", r"\bsuspend\w*\s+(?:performance|obligation)\w*\b",
                r"\breliev\w*\s+(?:from|of)\s+(?:performance|obligation)\w*\b"
            ],
            "Definitions": [
                # Definition clauses
                r"\bdefinition\w*\b", r"\bdefin\w*\s+(?:as|to\s+mean)\b", r"\bmean\w*\b",
                r"\binclude\w*\s+(?:but\s+(?:not\s+)?limited\s+to)?\b", r"\brefer\w*\s+to\b",
                # Term definitions
                r"\b(?:shall\s+)?mean\w*\b", r"\b(?:shall\s+)?include\w*\b",
                r"\binterpret\w*\s+(?:to\s+mean|as)\b", r"\bunderstood\s+(?:to\s+mean|as)\b",
                # Capitalized terms
                r"\bcapitalized\s+term\w*\b", r"\bterm\w*\s+(?:used\s+)?(?:herein|in\s+this\s+agreement)\b",
                # Cross-references
                r"\bas\s+defined\s+(?:above|below|herein)\b", r"\bas\s+set\s+forth\s+(?:above|below|herein)\b"
            ]
        }
        
        for clause in clauses:
            text_lower = clause.text.lower()
            clause_length = len(clause.text.split())

            # Calculate weighted scores for each category
            category_scores = {}
            total_patterns_found = 0

            for category, patterns in category_patterns.items():
                score = 0
                patterns_found = 0

                for pattern in patterns:
                    matches = re.findall(pattern, text_lower)
                    if matches:
                        patterns_found += len(matches)
                        # Weight by pattern strength and clause context
                        pattern_weight = 1.0
                        # Longer clauses get slight boost for pattern matches
                        length_factor = min(1.5, 1.0 + (clause_length - 50) / 200) if clause_length > 50 else 1.0
                        score += len(matches) * pattern_weight * length_factor

                if score > 0:
                    # Normalize score by number of patterns in category to prevent bias
                    normalized_score = score / len(patterns) * patterns_found
                    category_scores[category] = normalized_score
                    total_patterns_found += patterns_found

            # Determine best category with confidence scoring
            if category_scores:
                # Find the best match
                best_category = max(category_scores.keys(), key=lambda x: category_scores[x])
                best_score = category_scores[best_category]

                # Calculate confidence based on score separation and total evidence
                confidence = 0.0
                if len(category_scores) > 1:
                    sorted_scores = sorted(category_scores.values(), reverse=True)
                    if len(sorted_scores) >= 2 and sorted_scores[0] > 0:
                        confidence = (sorted_scores[0] - sorted_scores[1]) / sorted_scores[0]
                    else:
                        confidence = 1.0 if sorted_scores[0] > 0 else 0.0
                else:
                    confidence = min(1.0, best_score / 2.0)  # Single category match

                # Apply confidence threshold - require minimum confidence to avoid "Other"
                confidence_threshold = 0.2  # Minimum 20% confidence
                evidence_threshold = 1.5    # Minimum weighted evidence score

                if confidence >= confidence_threshold and best_score >= evidence_threshold:
                    clause.category = best_category
                else:
                    # Try semantic similarity fallback for low confidence cases
                    if self.semantic_enabled and confidence < 0.3:
                        semantic_category = await self._classify_by_semantic_similarity(clause.text)
                        if semantic_category and semantic_category != "Other":
                            clause.category = semantic_category
                        else:
                            clause.category = "Other"
                    else:
                        clause.category = "Other"
            else:
                # Try semantic similarity fallback if no patterns matched
                if self.semantic_enabled:
                    semantic_category = await self._classify_by_semantic_similarity(clause.text)
                    clause.category = semantic_category if semantic_category else "Other"
                else:
                    clause.category = "Other"

        return clauses

    async def _get_category_embeddings(self) -> Dict[str, List[List[float]]]:
        """
        Get or generate embeddings for all category examples.

        Returns:
            Dictionary mapping categories to lists of embeddings for their examples
        """
        if self._category_embeddings is not None:
            return self._category_embeddings

        if not self.semantic_enabled:
            return {}

        category_embeddings = {}

        for category, examples in self.category_examples.items():
            try:
                # Generate embeddings for all examples in this category
                embeddings = await self.embeddings_service.generate_embeddings_batch(examples)
                if embeddings and all(emb is not None for emb in embeddings):
                    category_embeddings[category] = embeddings
                else:
                    logger.warning(f"Failed to generate embeddings for category {category}")

            except Exception as e:
                logger.error(f"Error generating embeddings for category {category}: {e}")

        self._category_embeddings = category_embeddings
        return category_embeddings

    async def _classify_by_semantic_similarity(self, clause_text: str) -> Optional[str]:
        """
        Classify clause using semantic similarity to category examples.

        Args:
            clause_text: The clause text to classify

        Returns:
            Best matching category or None if no good match
        """
        if not self.semantic_enabled or not clause_text.strip():
            return None

        try:
            # Generate embedding for the input clause
            clause_embeddings = await self.embeddings_service.generate_embeddings_batch([clause_text])
            if not clause_embeddings or clause_embeddings[0] is None:
                logger.warning("Failed to generate embedding for clause text")
                return None

            clause_embedding = clause_embeddings[0]

            # Get category embeddings
            category_embeddings = await self._get_category_embeddings()
            if not category_embeddings:
                logger.warning("No category embeddings available")
                return None

            # Calculate similarities for each category
            best_category = None
            best_similarity = 0.0

            for category, example_embeddings in category_embeddings.items():
                # Calculate average similarity to all examples in this category
                similarities = []

                for example_embedding in example_embeddings:
                    similarity = self._cosine_similarity(clause_embedding, example_embedding)
                    similarities.append(similarity)

                if similarities:
                    # Use maximum similarity (best match) rather than average
                    max_similarity = max(similarities)

                    if max_similarity > best_similarity:
                        best_similarity = max_similarity
                        best_category = category

            # Apply semantic similarity threshold
            semantic_threshold = 0.7  # Require 70% similarity for semantic match

            if best_similarity >= semantic_threshold:
                logger.debug(f"Semantic classification: '{clause_text[:100]}...' -> {best_category} (similarity: {best_similarity:.3f})")
                return best_category
            else:
                logger.debug(f"No semantic match found for clause (best: {best_similarity:.3f}, threshold: {semantic_threshold})")
                return None

        except Exception as e:
            logger.error(f"Error in semantic classification: {e}")
            return None

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score between 0 and 1
        """
        try:
            # Convert to numpy arrays for easier calculation
            a = np.array(vec1)
            b = np.array(vec2)

            # Calculate cosine similarity
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)

            if norm_a == 0 or norm_b == 0:
                return 0.0

            similarity = dot_product / (norm_a * norm_b)

            # Ensure result is between 0 and 1
            return max(0.0, min(1.0, similarity))

        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0