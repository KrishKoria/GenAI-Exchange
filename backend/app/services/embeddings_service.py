"""
Embeddings service for vector similarity search using Google's text-embedding-004 model
"""
import logging
import numpy as np
import time
from typing import List, Dict, Any, Optional, Tuple
import asyncio

import google.generativeai as genai

from app.core.config import get_settings
from app.core.logging import get_logger, log_execution_time

logger = get_logger(__name__)


class EmbeddingsError(Exception):
    """Custom exception for embeddings operations."""
    pass


class EmbeddingsService:
    """Service for generating and searching embeddings using Google's text-embedding-004 model."""
    
    def __init__(self):
        self.settings = get_settings()
        genai.configure(api_key=self.settings.GOOGLE_GENAI_API_KEY)
        self.model_name = "models/text-embedding-004"
        
    def _log_execution_time(self, operation: str, start_time: float) -> None:
        """Helper method to log execution time."""
        duration_ms = (time.time() - start_time) * 1000
        log_execution_time(logger, operation, duration_ms)
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to generate embedding for
            
        Returns:
            List of float values representing the embedding
            
        Raises:
            EmbeddingsError: If embedding generation fails
        """
        start_time = time.time()
        
        try:
            # Clean and validate input
            if not text or not text.strip():
                raise EmbeddingsError("Text cannot be empty")
            
            text = text.strip()
            
            # Use asyncio.to_thread to make the synchronous API call async
            result = await asyncio.to_thread(
                genai.embed_content,
                model=self.model_name,
                content=text,
                task_type="retrieval_document"
            )
            
            if not result or 'embedding' not in result:
                raise EmbeddingsError("Failed to generate embedding")
            
            embedding = result['embedding']
            
            self._log_execution_time("generate_embedding", start_time)
            logger.debug(f"Generated embedding for text of length {len(text)}")
            
            return embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise EmbeddingsError(f"Embedding generation failed: {e}")
    
    async def generate_embeddings_batch(
        self, 
        texts: List[str], 
        max_concurrent: int = 5,
        batch_size: int = 20
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts with parallel processing.
        
        Args:
            texts: List of texts to generate embeddings for
            max_concurrent: Maximum number of concurrent requests (default: 5)
            batch_size: Number of texts to process in parallel batches (default: 20)
            
        Returns:
            List of embeddings corresponding to input texts (None for failed embeddings)
            
        Raises:
            EmbeddingsError: If all embeddings fail or critical error occurs
        """
        start_time = time.time()
        
        try:
            if not texts:
                return []
            
            logger.info(f"Generating embeddings for {len(texts)} texts with max {max_concurrent} concurrent requests")
            
            # Create semaphore to limit concurrent requests
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def generate_with_semaphore(text: str, index: int) -> Tuple[int, Optional[List[float]]]:
                """Generate embedding with concurrency control and error handling."""
                async with semaphore:
                    try:
                        embedding = await self.generate_embedding(text)
                        return index, embedding
                    except Exception as e:
                        logger.warning(f"Failed to generate embedding for text {index}: {e}")
                        return index, None
            
            # Process all texts in parallel with controlled concurrency
            tasks = [
                generate_with_semaphore(text, i) 
                for i, text in enumerate(texts)
            ]
            
            # Use gather with return_exceptions=True to handle individual failures
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results and maintain order
            embeddings = [None] * len(texts)
            successful_count = 0
            failed_count = 0
            
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Task failed with exception: {result}")
                    failed_count += 1
                    continue
                
                index, embedding = result
                embeddings[index] = embedding
                
                if embedding is not None:
                    successful_count += 1
                else:
                    failed_count += 1
            
            self._log_execution_time("generate_embeddings_batch", start_time)
            logger.info(f"Batch embedding generation completed: {successful_count} successful, {failed_count} failed")
            
            if successful_count == 0:
                raise EmbeddingsError("All embedding generation requests failed")
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Critical error in batch embedding generation: {e}")
            raise EmbeddingsError(f"Batch embedding generation failed: {e}")
    
    def cosine_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score between -1 and 1
        """
        try:
            # Convert to numpy arrays
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            # Calculate cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0
    
    async def find_similar_chunks(
        self, 
        query_embedding: List[float], 
        chunk_embeddings: List[Dict[str, Any]], 
        top_k: int = 5,
        similarity_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Find the most similar chunks to a query embedding.
        
        Args:
            query_embedding: Embedding vector for the query
            chunk_embeddings: List of dictionaries containing chunk data and embeddings
            top_k: Number of top similar chunks to return
            similarity_threshold: Minimum similarity score to include
            
        Returns:
            List of chunks sorted by similarity (highest first)
        """
        start_time = time.time()
        
        try:
            if not chunk_embeddings:
                return []
            
            # Calculate similarities for all chunks
            similarities = []
            
            for chunk_data in chunk_embeddings:
                if 'embedding' not in chunk_data:
                    continue
                
                similarity = self.cosine_similarity(query_embedding, chunk_data['embedding'])
                
                if similarity >= similarity_threshold:
                    chunk_with_similarity = chunk_data.copy()
                    chunk_with_similarity['similarity'] = similarity
                    similarities.append(chunk_with_similarity)
            
            # Sort by similarity (highest first) and take top_k
            similarities.sort(key=lambda x: x['similarity'], reverse=True)
            top_chunks = similarities[:top_k]
            
            self._log_execution_time("find_similar_chunks", start_time)
            logger.info(f"Found {len(top_chunks)} similar chunks above threshold {similarity_threshold}")
            
            return top_chunks
            
        except Exception as e:
            logger.error(f"Error finding similar chunks: {e}")
            raise EmbeddingsError(f"Similarity search failed: {e}")
    
    async def search_similar_content(
        self, 
        query: str, 
        document_chunks: List[Dict[str, Any]], 
        top_k: int = 5,
        similarity_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Search for similar content using semantic similarity.
        
        Args:
            query: Search query text
            document_chunks: List of document chunks with embeddings
            top_k: Number of top results to return
            similarity_threshold: Minimum similarity score
            
        Returns:
            List of similar chunks with similarity scores
        """
        start_time = time.time()
        
        try:
            # Generate embedding for the query
            query_embedding = await self.generate_embedding(query)
            
            # Find similar chunks
            similar_chunks = await self.find_similar_chunks(
                query_embedding=query_embedding,
                chunk_embeddings=document_chunks,
                top_k=top_k,
                similarity_threshold=similarity_threshold
            )
            
            self._log_execution_time("search_similar_content", start_time)
            
            return similar_chunks
            
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            raise EmbeddingsError(f"Semantic search failed: {e}")

    async def search_similar_clauses(
        self, 
        question: str, 
        clause_embeddings: List[Dict[str, Any]], 
        top_k: int = 5,
        min_similarity: float = 0.2
    ) -> List[Dict[str, Any]]:
        """
        Search for similar clauses using semantic similarity.
        
        Args:
            question: Question text
            clause_embeddings: List of clause data with embeddings
            top_k: Number of top results to return
            min_similarity: Minimum similarity score
            
        Returns:
            List of similar clauses with similarity scores
        """
        return await self.search_similar_content(
            query=question,
            document_chunks=clause_embeddings,
            top_k=top_k,
            similarity_threshold=min_similarity
        )


# Global instance
embeddings_service = EmbeddingsService()
