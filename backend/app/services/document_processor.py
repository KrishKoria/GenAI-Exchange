"""
Document processing service with Document AI integration and fallback
"""
import logging
import tempfile
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
import asyncio

from google.cloud import documentai
from google.api_core.exceptions import GoogleAPIError
import PyPDF2
from pdfminer.high_level import extract_text
from pdfminer.pdfparser import PDFSyntaxError

from app.core.config import get_settings
from app.core.logging import get_logger, LogContext, log_execution_time

logger = get_logger(__name__)


class DocumentProcessingError(Exception):
    """Custom exception for document processing errors."""
    pass


class DocumentProcessor:
    """Service for processing legal documents with Document AI and fallbacks."""
    
    def __init__(self):
        self.settings = get_settings()
        self._doc_ai_client: Optional[documentai.DocumentProcessorServiceClient] = None
        self._processor_name: Optional[str] = None
    
    @property
    def doc_ai_client(self) -> documentai.DocumentProcessorServiceClient:
        """Lazy initialization of Document AI client."""
        if self._doc_ai_client is None:
            self._doc_ai_client = documentai.DocumentProcessorServiceClient()
            self._processor_name = self._doc_ai_client.processor_path(
                self.settings.PROJECT_ID,
                self.settings.DOC_AI_LOCATION,
                self.settings.DOC_AI_PROCESSOR_ID
            )
        return self._doc_ai_client
    
    async def process_document(
        self, 
        file_content: bytes, 
        filename: str,
        mime_type: str
    ) -> Dict[str, Any]:
        """
        Process a document to extract text and layout information.
        
        Args:
            file_content: Raw file bytes
            filename: Original filename
            mime_type: MIME type of the file
            
        Returns:
            Dictionary containing extracted text, page info, and metadata
            
        Raises:
            DocumentProcessingError: If processing fails
        """
        start_time = asyncio.get_event_loop().time()
        
        with LogContext(logger, filename=filename, mime_type=mime_type):
            logger.info(f"Starting document processing for {filename}")
            
            # Validate file size and type
            file_size = len(file_content)
            if file_size > self.settings.max_file_size_bytes:
                raise DocumentProcessingError(
                    f"File size {file_size} exceeds limit {self.settings.max_file_size_bytes}"
                )
            
            # Try Document AI first
            try:
                result = await self._process_with_document_ai(
                    file_content, filename, mime_type
                )
                logger.info("Document processed successfully with Document AI")
                
            except Exception as e:
                logger.warning(f"Document AI failed: {e}. Falling back to local processing")
                result = await self._process_with_fallback(
                    file_content, filename, mime_type
                )
            
            # Add processing metadata
            result["processing"] = {
                "filename": filename,
                "file_size": file_size,
                "mime_type": mime_type,
                "processing_time_ms": (asyncio.get_event_loop().time() - start_time) * 1000,
                "method": result.get("method", "unknown")
            }
            
            log_execution_time(logger, "document_processing", result["processing"]["processing_time_ms"])
            
            return result
    
    async def _process_with_document_ai(
        self, 
        file_content: bytes, 
        filename: str,
        mime_type: str
    ) -> Dict[str, Any]:
        """
        Process document using Google Cloud Document AI.
        
        Args:
            file_content: Raw file bytes
            filename: Original filename
            mime_type: MIME type
            
        Returns:
            Processed document data with layout information
        """
        try:
            # Create the request
            request = documentai.ProcessRequest(
                name=self._processor_name,
                raw_document=documentai.RawDocument(
                    content=file_content,
                    mime_type=mime_type
                )
            )
            
            # Process the document
            response = self.doc_ai_client.process_document(request=request)
            document = response.document
            
            # Extract text and layout information
            pages = []
            for i, page in enumerate(document.pages):
                page_info = {
                    "page_number": i + 1,
                    "width": page.dimension.width,
                    "height": page.dimension.height,
                    "blocks": [],
                    "paragraphs": []
                }
                
                # Extract blocks (larger text regions)
                for block in page.blocks:
                    if block.layout.text_anchor:
                        block_text = self._extract_text_from_anchor(
                            document.text, block.layout.text_anchor
                        )
                        page_info["blocks"].append({
                            "text": block_text,
                            "confidence": block.layout.confidence,
                            "bounding_box": self._extract_bounding_box(block.layout.bounding_poly)
                        })
                
                # Extract paragraphs for better clause detection
                for paragraph in page.paragraphs:
                    if paragraph.layout.text_anchor:
                        para_text = self._extract_text_from_anchor(
                            document.text, paragraph.layout.text_anchor
                        )
                        page_info["paragraphs"].append({
                            "text": para_text,
                            "confidence": paragraph.layout.confidence,
                            "bounding_box": self._extract_bounding_box(paragraph.layout.bounding_poly)
                        })
                
                pages.append(page_info)
            
            return {
                "text": document.text,
                "pages": pages,
                "page_count": len(pages),
                "method": "document_ai",
                "confidence": getattr(document, "confidence", None)
            }
            
        except GoogleAPIError as e:
            logger.error(f"Document AI API error: {e}")
            raise DocumentProcessingError(f"Document AI processing failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in Document AI processing: {e}")
            raise DocumentProcessingError(f"Document processing failed: {e}")
    
    async def _process_with_fallback(
        self, 
        file_content: bytes, 
        filename: str,
        mime_type: str
    ) -> Dict[str, Any]:
        """
        Fallback document processing using local libraries.
        
        Args:
            file_content: Raw file bytes
            filename: Original filename
            mime_type: MIME type
            
        Returns:
            Basic document data with extracted text
        """
        if mime_type == "application/pdf":
            return await self._process_pdf_fallback(file_content, filename)
        else:
            raise DocumentProcessingError(f"No fallback available for MIME type: {mime_type}")
    
    async def _process_pdf_fallback(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Process PDF using PyPDF2 and pdfminer as fallbacks.
        
        Args:
            file_content: PDF file bytes
            filename: Original filename
            
        Returns:
            Basic PDF text extraction results
        """
        # Try PyPDF2 first (faster but less reliable)
        try:
            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(file_content)
                temp_file.flush()
                
                with open(temp_file.name, 'rb') as pdf_file:
                    pdf_reader = PyPDF2.PdfReader(pdf_file)
                    
                    if len(pdf_reader.pages) > self.settings.MAX_PAGES:
                        raise DocumentProcessingError(
                            f"PDF has {len(pdf_reader.pages)} pages, exceeds limit of {self.settings.MAX_PAGES}"
                        )
                    
                    text_content = []
                    pages = []
                    
                    for i, page in enumerate(pdf_reader.pages):
                        page_text = page.extract_text()
                        text_content.append(page_text)
                        
                        pages.append({
                            "page_number": i + 1,
                            "text": page_text,
                            "method": "pypdf2"
                        })
                    
                    full_text = "\n".join(text_content)
                    
                    # If PyPDF2 extracted very little text, try pdfminer
                    if len(full_text.strip()) < 100:
                        logger.info("PyPDF2 extracted minimal text, trying pdfminer")
                        return await self._process_pdf_with_pdfminer(file_content, filename)
                    
                    return {
                        "text": full_text,
                        "pages": pages,
                        "page_count": len(pages),
                        "method": "pypdf2_fallback"
                    }
                    
        except Exception as e:
            logger.warning(f"PyPDF2 failed: {e}. Trying pdfminer")
            return await self._process_pdf_with_pdfminer(file_content, filename)
    
    async def _process_pdf_with_pdfminer(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Process PDF using pdfminer (more robust but slower).
        
        Args:
            file_content: PDF file bytes
            filename: Original filename
            
        Returns:
            pdfminer text extraction results
        """
        try:
            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(file_content)
                temp_file.flush()
                
                # Extract text using pdfminer
                text = extract_text(temp_file.name)
                
                # Basic page estimation (pdfminer doesn't easily give page count)
                estimated_pages = max(1, len(text) // 3000)  # Rough estimate
                
                if estimated_pages > self.settings.MAX_PAGES:
                    raise DocumentProcessingError(
                        f"Estimated {estimated_pages} pages, exceeds limit of {self.settings.MAX_PAGES}"
                    )
                
                return {
                    "text": text,
                    "pages": [{"page_number": 1, "text": text, "method": "pdfminer"}],
                    "page_count": estimated_pages,
                    "method": "pdfminer_fallback"
                }
                
        except PDFSyntaxError as e:
            raise DocumentProcessingError(f"PDF syntax error: {e}")
        except Exception as e:
            raise DocumentProcessingError(f"pdfminer processing failed: {e}")
    
    def _extract_text_from_anchor(self, document_text: str, text_anchor) -> str:
        """Extract text using Document AI text anchor."""
        if not text_anchor.text_segments:
            return ""
        
        text_segments = []
        for segment in text_anchor.text_segments:
            start = int(segment.start_index) if segment.start_index else 0
            end = int(segment.end_index) if segment.end_index else len(document_text)
            text_segments.append(document_text[start:end])
        
        return "".join(text_segments)
    
    def _extract_bounding_box(self, bounding_poly) -> Optional[Dict[str, float]]:
        """Extract bounding box coordinates from Document AI bounding poly."""
        if not bounding_poly or not bounding_poly.vertices:
            return None
        
        vertices = bounding_poly.vertices
        if len(vertices) < 4:
            return None
        
        x_coords = [vertex.x for vertex in vertices]
        y_coords = [vertex.y for vertex in vertices]
        
        return {
            "left": min(x_coords),
            "top": min(y_coords),
            "right": max(x_coords),
            "bottom": max(y_coords)
        }
    
    async def validate_document_format(self, file_content: bytes, mime_type: str) -> bool:
        """
        Validate that the document format is supported and readable.
        
        Args:
            file_content: Raw file bytes
            mime_type: MIME type
            
        Returns:
            True if document is valid and readable
        """
        supported_types = [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ]
        
        if mime_type not in supported_types:
            return False
        
        # Basic validation - try to read the first few bytes
        if len(file_content) < 100:
            return False
        
        if mime_type == "application/pdf":
            # PDF files should start with %PDF
            return file_content.startswith(b"%PDF")
        
        return True