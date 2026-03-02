"""
Embedding Service V2 - KG-RAG Corrected Version
Proper chunking with rich content and metadata
"""
import os
import re
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class EmbeddingServiceV2:
    """
    KG-RAG Corrected Embedding Service
    
    Key Improvements:
    1. Proper chunking (not just titles)
    2. chunk_type for query routing
    3. Rich content for actual retrieval
    4. Overlap between chunks
    5. Clear separation from KG data
    """
    
    def __init__(self):
        self.model = None
        self.model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")
        self.embedding_dimension = 768
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize the embedding model"""
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name)
            
            test_embedding = self.model.encode("test")
            self.embedding_dimension = len(test_embedding)
            
            logger.info(f"Embedding model '{self.model_name}' loaded. Dimension: {self.embedding_dimension}")
        except ImportError:
            logger.warning("sentence-transformers not installed")
        except Exception as e:
            logger.error(f"Error loading embedding model: {e}")
    
    def is_ready(self) -> bool:
        """Check if embedding service is ready"""
        return self.model is not None
    
    def generate_embedding(self, text: str, is_query: bool = False) -> List[float]:
        """
        Generate embedding for text
        
        Args:
            text: Text to embed
            is_query: If True, adds instruction prefix for BGE models
        """
        if not self.model:
            raise RuntimeError("Embedding model not loaded")
        
        # BGE models work better with instruction prefix for queries
        if is_query and "bge" in self.model_name.lower():
            text = f"Represent this sentence for searching relevant passages: {text}"
        
        embedding = self.model.encode(text)
        return embedding.tolist()
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        if not self.model:
            raise RuntimeError("Embedding model not loaded")
        
        embeddings = self.model.encode(texts)
        return [emb.tolist() for emb in embeddings]
    
    # ═══════════════════════════════════════════════════════════════════════
    # Store Content Chunks (V2 Format)
    # ═══════════════════════════════════════════════════════════════════════
    
    def store_content_chunks(
        self,
        supabase_client,
        content_chunks: List[dict],
        semester: int,
        branch: str,
        regulation: str = "2019"
    ) -> dict:
        """
        Store content chunks from V2 extractor
        
        Args:
            supabase_client: Supabase client
            content_chunks: List of chunk dicts from LLMExtractorV2
            semester: Semester number
            branch: Branch code
            regulation: Regulation year
        """
        stats = {
            "chunks_stored": 0,
            "by_type": {},
            "errors": []
        }
        
        for chunk in content_chunks:
            try:
                chunk_type = chunk.get("chunk_type", "unknown")
                
                # Generate embedding for the content
                content = chunk.get("content", "")
                if not content:
                    continue
                
                embedding = self.generate_embedding(content)
                
                # Merge metadata
                metadata = chunk.get("metadata", {})
                
                # Store in Supabase
                data = {
                    "chunk_id": chunk.get("chunk_id", ""),
                    "chunk_type": chunk_type,
                    "content": content,
                    "embedding": embedding,
                    "subject_code": metadata.get("subject_code"),
                    "subject_name": metadata.get("subject_name"),
                    "module_number": metadata.get("module_number"),
                    "module_name": metadata.get("module_name"),
                    "module_id": metadata.get("module_id"),
                    "topic_id": metadata.get("topic_id"),
                    "topic_name": metadata.get("topic_name"),
                    "semester": semester,
                    "branch": branch,
                    "regulation": regulation
                }
                
                result = supabase_client.table("syllabus_embeddings").upsert(data, on_conflict="chunk_id").execute()
                
                if result.data:
                    stats["chunks_stored"] += 1
                    stats["by_type"][chunk_type] = stats["by_type"].get(chunk_type, 0) + 1
                    
            except Exception as e:
                error_msg = f"Error storing chunk '{chunk.get('chunk_id', 'unknown')}': {str(e)}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)
        
        return stats
    
    # ═══════════════════════════════════════════════════════════════════════
    # Search Operations (V2)
    # ═══════════════════════════════════════════════════════════════════════
    
    def search(
        self,
        supabase_client,
        query: str,
        limit: int = 5,
        chunk_types: List[str] = None,
        semester: Optional[int] = None,
        branch: Optional[str] = None,
        subject_code: Optional[str] = None,
        regulation: Optional[str] = None
    ) -> List[dict]:
        """
        Search for relevant content with filtering
        
        Args:
            query: Search query
            limit: Max results
            chunk_types: Filter by chunk types (syllabus_content, topic_list, topic_detail, etc.)
            semester: Filter by semester
            branch: Filter by branch
            subject_code: Filter by subject
            regulation: Filter by regulation
        """
        query_embedding = self.generate_embedding(query, is_query=True)
        
        # Try RPC function first
        params = {
            "query_embedding": query_embedding,
            "match_count": limit
        }
        
        if semester:
            params["filter_semester"] = semester
        if branch:
            params["filter_branch"] = branch
        if subject_code:
            params["filter_subject"] = subject_code
        if regulation:
            params["filter_regulation"] = regulation
        if chunk_types:
            params["filter_chunk_types"] = chunk_types
        
        try:
            result = supabase_client.rpc("search_syllabus_v2", params).execute()
            return result.data if result.data else []
        except Exception as e:
            logger.warning(f"RPC search failed, using fallback: {e}")
            return self._fallback_search(
                supabase_client, query, limit, chunk_types,
                semester, branch, subject_code, regulation
            )
    
    def _fallback_search(
        self,
        supabase_client,
        query: str,
        limit: int,
        chunk_types: List[str],
        semester: Optional[int],
        branch: Optional[str],
        subject_code: Optional[str],
        regulation: Optional[str]
    ) -> List[dict]:
        """Fallback text-based search"""
        query_builder = supabase_client.table("syllabus_embeddings").select("*")
        
        if semester:
            query_builder = query_builder.eq("semester", semester)
        if branch:
            query_builder = query_builder.eq("branch", branch)
        if subject_code:
            query_builder = query_builder.eq("subject_code", subject_code)
        if regulation:
            query_builder = query_builder.eq("regulation", regulation)
        if chunk_types:
            query_builder = query_builder.in_("chunk_type", chunk_types)
        
        # Text search
        query_builder = query_builder.ilike("content", f"%{query}%")
        
        result = query_builder.limit(limit).execute()
        return result.data if result.data else []
    
    def search_by_concept(
        self,
        supabase_client,
        concept_id: str,
        chunk_types: List[str] = None,
        limit: int = 10
    ) -> List[dict]:
        """
        Get all content chunks for a specific concept
        
        Args:
            concept_id: The canonical concept ID
            chunk_types: Filter by chunk types
            limit: Max results
        """
        query_builder = supabase_client.table("syllabus_embeddings").select("*")
        query_builder = query_builder.eq("topic_id", concept_id)
        
        if chunk_types:
            query_builder = query_builder.in_("chunk_type", chunk_types)
        
        result = query_builder.limit(limit).execute()
        return result.data if result.data else []
    
    def search_by_module(
        self,
        supabase_client,
        module_id: str,
        chunk_types: List[str] = None
    ) -> List[dict]:
        """Get all content chunks for a module"""
        query_builder = supabase_client.table("syllabus_embeddings").select("*")
        query_builder = query_builder.eq("module_id", module_id)
        
        if chunk_types:
            query_builder = query_builder.in_("chunk_type", chunk_types)
        
        result = query_builder.execute()
        return result.data if result.data else []
    
    # ═══════════════════════════════════════════════════════════════════════
    # Statistics
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_statistics(self, supabase_client) -> dict:
        """Get embedding statistics"""
        try:
            # Total count
            count_result = supabase_client.table("syllabus_embeddings").select("id", count="exact").execute()
            total = count_result.count or 0
            
            # Count by chunk type
            all_data = supabase_client.table("syllabus_embeddings").select("chunk_type, subject_code, topic_id").execute()
            
            by_type = {}
            subjects = set()
            topics = set()
            
            for row in all_data.data or []:
                chunk_type = row.get("chunk_type", "unknown")
                by_type[chunk_type] = by_type.get(chunk_type, 0) + 1
                
                if row.get("subject_code"):
                    subjects.add(row["subject_code"])
                if row.get("topic_id"):
                    topics.add(row["topic_id"])
            
            return {
                "total_chunks": total,
                "total_embeddings": total,
                "chunks_by_type": by_type,
                "subjects_covered": len(subjects),
                "topics_covered": len(topics),
                "model": self.model_name,
                "dimension": self.embedding_dimension
            }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {
                "total_chunks": 0,
                "chunks_by_type": {},
                "subjects_covered": 0,
                "topics_covered": 0,
                "model": self.model_name,
                "dimension": self.embedding_dimension,
                "error": str(e)
            }
    
    # ═══════════════════════════════════════════════════════════════════════
    # Cleanup
    # ═══════════════════════════════════════════════════════════════════════
    
    def delete_by_subject(self, supabase_client, subject_code: str) -> int:
        """Delete all embeddings for a subject"""
        result = supabase_client.table("syllabus_embeddings").delete().eq(
            "subject_code", subject_code
        ).execute()
        return len(result.data) if result.data else 0
    
    def delete_by_regulation(
        self, 
        supabase_client, 
        regulation: str,
        semester: Optional[int] = None,
        branch: Optional[str] = None
    ) -> int:
        """Delete embeddings by regulation with optional filters"""
        query = supabase_client.table("syllabus_embeddings").delete().eq("regulation", regulation)
        
        if semester:
            query = query.eq("semester", semester)
        if branch:
            query = query.eq("branch", branch)
        
        result = query.execute()
        return len(result.data) if result.data else 0

    # ═══════════════════════════════════════════════════════════════════════
    # V1 Compatibility Shims
    # ═══════════════════════════════════════════════════════════════════════

    def search_similar(
        self,
        supabase_client,
        query: str,
        limit: int = 5,
        semester: Optional[int] = None,
        branch: Optional[str] = None,
        subject_code: Optional[str] = None,
        chunk_types: List[str] = None,
    ) -> List[dict]:
        """V1 compat → calls search()"""
        return self.search(
            supabase_client=supabase_client,
            query=query,
            limit=limit,
            chunk_types=chunk_types,
            semester=semester,
            branch=branch,
            subject_code=subject_code,
        )

    def delete_embeddings(
        self,
        supabase_client,
        semester: Optional[int] = None,
        branch: Optional[str] = None,
        subject_code: Optional[str] = None,
    ) -> int:
        """V1 compat → deletes embeddings with optional filters"""
        if subject_code:
            return self.delete_by_subject(supabase_client, subject_code)
        # Fallback: delete by fields
        q = supabase_client.table("syllabus_embeddings").delete()
        if semester:
            q = q.eq("semester", semester)
        if branch:
            q = q.eq("branch", branch)
        result = q.execute()
        return len(result.data) if result.data else 0


# Global instance
embedding_service = EmbeddingServiceV2()
