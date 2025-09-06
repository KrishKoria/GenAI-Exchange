"""
Document processing service using direct Document AI REST API calls
"""
import json
import base64
import requests
import asyncio
import tempfile
import os
from typing import Optional, Dict, Any
from google.auth.transport.requests import Request
from google.oauth2 import service_account
import PyPDF2
from pdfminer.high_level import extract_text
from pdfminer.pdfparser import PDFSyntaxError

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class DocumentProcessingError(Exception):
    """Custom exception for document processing errors."""
    pass


class DocumentProcessor:
    """Document processor using direct Document AI REST API calls."""
    
    def __init__(self):
        self.settings = get_settings()
        self.project_number = "672053308745"  # Use PROJECT_NUMBER directly
        self.location = "us"
        self.processor_id = "cad714d3e55fe636"
        self.endpoint_url = f"https://us-documentai.googleapis.com/v1/projects/{self.project_number}/locations/{self.location}/processors/{self.processor_id}:process"
        self._access_token = None
        logger.info(f"Initialized DocumentProcessor with direct REST API")
        logger.info(f"Endpoint URL: {self.endpoint_url}")
    
    def _get_access_token(self) -> str:
        """Get OAuth2 access token using service account credentials."""
        try:
            # Load service account credentials
            credentials_path = "./credentials.json"
            
            logger.info(f"Loading service account credentials from {credentials_path}")
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            
            # Refresh the token
            auth_req = Request()
            credentials.refresh(auth_req)
            
            access_token = credentials.token
            logger.info("Successfully obtained OAuth2 access token")
            return access_token
            
        except Exception as e:
            logger.error(f"Failed to get access token: {str(e)}")
            raise
    
    def clear_cache(self):
        """Clear any cached access tokens."""
        self._access_token = None
        logger.info("Cleared access token cache")
    
    async def _process_with_document_ai_api(self, pdf_content: bytes) -> Optional[str]:
        """
        Process a document using Document AI REST API.
        
        Args:
            pdf_content: PDF file content as bytes
            
        Returns:
            Extracted text or None if processing fails
        """
        try:
            logger.info("Starting Document AI REST API processing...")
            
            # Get access token
            access_token = self._get_access_token()
            
            # Encode PDF content to base64
            pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
            
            # Prepare request payload using correct Document AI REST API format
            payload = {
                "rawDocument": {
                    "content": pdf_base64,
                    "mimeType": "application/pdf"
                }
            }
            
            # Prepare headers
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "User-Agent": "ClauseCompass/1.0"
            }
            
            logger.info(f"Making POST request to {self.endpoint_url}")
            logger.info(f"PDF content size: {len(pdf_content)} bytes")
            
            # Make the API request
            response = requests.post(
                self.endpoint_url,
                headers=headers,
                json=payload,
                timeout=60
            )
            
            logger.info(f"Document AI API response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                
                # Extract text from the response
                document = result.get("document", {})
                text = document.get("text", "")
                
                if text.strip():
                    logger.info(f"Successfully extracted {len(text)} characters of text")
                    return text
                else:
                    logger.warning("Document AI returned empty text")
                    return None
            else:
                logger.error(f"Document AI API error: {response.status_code}")
                logger.error(f"Response body: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Document AI API call: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during Document AI processing: {str(e)}")
            return None
    
    async def _fallback_extract_text(self, file_content: bytes) -> Optional[str]:
        """
        Fallback text extraction using pdfminer and PyPDF2.
        
        Args:
            file_content: PDF file content as bytes
            
        Returns:
            Extracted text or None if extraction fails
        """
        logger.info("Attempting fallback text extraction...")
        
        # Create a temporary file for fallback processing
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name
            
            logger.info(f"Created temporary file: {temp_file_path}")
            
            # Try pdfminer first
            try:
                logger.info("Attempting text extraction with pdfminer...")
                text = extract_text(temp_file_path)
                if text and text.strip():
                    logger.info(f"pdfminer extracted {len(text)} characters")
                    return text
            except PDFSyntaxError as e:
                logger.warning(f"pdfminer failed with syntax error: {str(e)}")
            except Exception as e:
                logger.warning(f"pdfminer failed: {str(e)}")
            
            # Try PyPDF2 as backup
            try:
                logger.info("Attempting text extraction with PyPDF2...")
                with open(temp_file_path, 'rb') as pdf_file:
                    pdf_reader = PyPDF2.PdfReader(pdf_file)
                    text_parts = []
                    
                    for page_num, page in enumerate(pdf_reader.pages):
                        try:
                            page_text = page.extract_text()
                            if page_text:
                                text_parts.append(page_text)
                                logger.debug(f"Extracted text from page {page_num + 1}")
                        except Exception as e:
                            logger.warning(f"Failed to extract text from page {page_num + 1}: {str(e)}")
                    
                    combined_text = "\n".join(text_parts)
                    if combined_text.strip():
                        logger.info(f"PyPDF2 extracted {len(combined_text)} characters")
                        return combined_text
                        
            except Exception as e:
                logger.warning(f"PyPDF2 failed: {str(e)}")
            
            logger.error("All fallback text extraction methods failed")
            return None
            
        except Exception as e:
            logger.error(f"Failed to create temporary file for fallback processing: {str(e)}")
            return None
        finally:
            # Clean up temporary file
            try:
                if 'temp_file_path' in locals():
                    os.unlink(temp_file_path)
                    logger.debug(f"Cleaned up temporary file: {temp_file_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file: {str(e)}")
    
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
        logger.info(f"Starting document processing for {filename}")
        
        # Validate file size (10MB limit)
        max_size = 10 * 1024 * 1024
        if len(file_content) > max_size:
            raise DocumentProcessingError(f"File size {len(file_content)} bytes exceeds maximum {max_size} bytes")
        
        # Validate MIME type
        if mime_type not in ["application/pdf"]:
            raise DocumentProcessingError(f"Unsupported MIME type: {mime_type}")
        
        extracted_text = None
        processing_method = "none"
        
        # Try Document AI first
        try:
            extracted_text = await self._process_with_document_ai_api(file_content)
            if extracted_text:
                processing_method = "document_ai_api"
                logger.info("Successfully processed document with Document AI REST API")
        except Exception as e:
            logger.warning(f"Document AI API processing failed: {str(e)}")
        
        # Fallback to local text extraction if Document AI failed
        if not extracted_text:
            logger.info("Document AI failed, attempting fallback text extraction...")
            extracted_text = await self._fallback_extract_text(file_content)
            if extracted_text:
                processing_method = "fallback"
                logger.info("Successfully processed document with fallback methods")
        
        if not extracted_text:
            raise DocumentProcessingError("Failed to extract text from document using all available methods")
        
        # Basic text cleaning
        cleaned_text = extracted_text.strip()
        
        # Estimate page count (rough approximation)
        estimated_pages = max(1, len(cleaned_text) // 3000)
        
        result = {
            "text": cleaned_text,
            "page_count": estimated_pages,
            "processing_method": processing_method,
            "character_count": len(cleaned_text),
            "file_size_bytes": len(file_content)
        }
        
        logger.info(f"Document processing complete: {len(cleaned_text)} characters, {estimated_pages} pages, method: {processing_method}")
        return result
