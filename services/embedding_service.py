"""
Embedding Service
Generates and manages vector embeddings for RAG in Supabase pgvector
"""
import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Vector embedding service for RAG using Supabase pgvector
    """
    
    def __init__(self):
        self.model = None
        self.model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self.embedding_dimension = 384  # Default for MiniLM
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize the embedding model"""
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name)
            
            # Get actual embedding dimension
            test_embedding = self.model.encode("test")
            self.embedding_dimension = len(test_embedding)
            
            logger.info(f"Embedding model '{self.model_name}' loaded. Dimension: {self.embedding_dimension}")
        except ImportError:
            logger.warning("sentence-transformers not installed. Install with: pip install sentence-transformers")
        except Exception as e:
            logger.error(f"Error loading embedding model: {e}")
    
    def is_ready(self) -> bool:
        """Check if embedding service is ready"""
        return self.model is not None
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        if not self.model:
            raise RuntimeError("Embedding model not loaded")
        
        embedding = self.model.encode(text)
        return embedding.tolist()
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        if not self.model:
            raise RuntimeError("Embedding model not loaded")
        
        embeddings = self.model.encode(texts)
        return [emb.tolist() for emb in embeddings]
    
    def create_topic_embedding_text(
        self,
        topic_name: str,
        topic_description: str,
        keywords: List[str],
        module_name: str,
        subject_name: str,
        subject_code: str
    ) -> str:
        """
        Create rich text for embedding a topic
        
        Args:
            topic_name: Name of the topic
            topic_description: Description of the topic
            keywords: Keywords for the topic
            module_name: Name of the module
            subject_name: Name of the subject
            subject_code: Subject code
            
        Returns:
            Rich text suitable for embedding
        """
        return f"""Subject: {subject_name} ({subject_code})
Module: {module_name}
Topic: {topic_name}
Description: {topic_description}
Keywords: {', '.join(keywords)}"""
    
    # ═══════════════════════════════════════════════════════════════════════
    # Supabase pgvector Operations
    # ═══════════════════════════════════════════════════════════════════════
    
    def store_embedding(
        self,
        supabase_client,
        content: str,
        embedding: List[float],
        metadata: Dict[str, Any]
    ) -> dict:
        """
        Store an embedding in Supabase pgvector
        
        Args:
            supabase_client: Supabase client instance
            content: Original text content
            embedding: Embedding vector
            metadata: Additional metadata
            
        Returns:
            Created record
        """
        data = {
            "content": content,
            "embedding": embedding,
            **metadata
        }
        
        result = supabase_client.table("syllabus_embeddings").insert(data).execute()
        return result.data[0] if result.data else None
    
    def store_topic_embedding(
        self,
        supabase_client,
        topic: dict,
        module: dict,
        subject: dict,
        semester: int,
        branch: str,
        regulation: str = "2019"
    ) -> dict:
        """
        Store embedding for a topic
        
        Args:
            supabase_client: Supabase client
            topic: Topic data
            module: Module data
            subject: Subject data
            semester: Semester number
            branch: Branch code
            regulation: KTU regulation year
            
        Returns:
            Created record
        """
        # Create rich text
        content = self.create_topic_embedding_text(
            topic_name=topic["name"],
            topic_description=topic.get("description", ""),
            keywords=topic.get("keywords", []),
            module_name=module.get("name", f"Module {module.get('number', '')}"),
            subject_name=subject["name"],
            subject_code=subject["code"]
        )
        
        # Generate embedding
        embedding = self.generate_embedding(content)
        
        # Store with metadata
        return self.store_embedding(
            supabase_client=supabase_client,
            content=content,
            embedding=embedding,
            metadata={
                "subject_code": subject["code"],
                "subject_name": subject["name"],
                "module_number": module.get("number"),
                "module_name": module.get("name"),
                "topic_name": topic["name"],
                "keywords": topic.get("keywords", []),
                "semester": semester,
                "branch": branch,
                "regulation": regulation
            }
        )
    
    def search_similar(
        self,
        supabase_client,
        query: str,
        limit: int = 5,
        semester: Optional[int] = None,
        branch: Optional[str] = None,
        subject_code: Optional[str] = None
    ) -> List[dict]:
        """
        Search for similar content using vector similarity
        
        Args:
            supabase_client: Supabase client
            query: Search query
            limit: Maximum results
            semester: Filter by semester
            branch: Filter by branch
            subject_code: Filter by subject
            
        Returns:
            List of similar content with scores
        """
        # Generate query embedding
        query_embedding = self.generate_embedding(query)
        
        # Build the RPC call for similarity search
        # This requires a function in Supabase - see setup SQL
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
        
        try:
            result = supabase_client.rpc("search_syllabus", params).execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Similarity search error: {e}")
            # Fallback to basic search if RPC not available
            return self._fallback_search(supabase_client, query, limit, semester, branch, subject_code)
    
    def _fallback_search(
        self,
        supabase_client,
        query: str,
        limit: int,
        semester: Optional[int],
        branch: Optional[str],
        subject_code: Optional[str]
    ) -> List[dict]:
        """Fallback text-based search if vector search fails"""
        query_builder = supabase_client.table("syllabus_embeddings").select("*")
        
        if semester:
            query_builder = query_builder.eq("semester", semester)
        if branch:
            query_builder = query_builder.eq("branch", branch)
        if subject_code:
            query_builder = query_builder.eq("subject_code", subject_code)
        
        # Text search on content
        query_builder = query_builder.ilike("content", f"%{query}%")
        
        result = query_builder.limit(limit).execute()
        return result.data if result.data else []
    
    # ═══════════════════════════════════════════════════════════════════════
    # Bulk Operations
    # ═══════════════════════════════════════════════════════════════════════
    
    def store_syllabus_embeddings(
        self,
        supabase_client,
        syllabus_data: dict
    ) -> dict:
        """
        Store embeddings for all topics in syllabus data
        
        Args:
            supabase_client: Supabase client
            syllabus_data: Structured syllabus data
            
        Returns:
            Statistics about stored embeddings
        """
        stats = {
            "embeddings_created": 0,
            "errors": []
        }
        
        semester = syllabus_data.get("semester", 0)
        branch = syllabus_data.get("branch", "")
        regulation = syllabus_data.get("regulation", "2019")
        
        for subject in syllabus_data.get("subjects", []):
            for module in subject.get("modules", []):
                for topic in module.get("topics", []):
                    try:
                        self.store_topic_embedding(
                            supabase_client=supabase_client,
                            topic=topic,
                            module=module,
                            subject=subject,
                            semester=semester,
                            branch=branch,
                            regulation=regulation
                        )
                        stats["embeddings_created"] += 1
                    except Exception as e:
                        error_msg = f"Error embedding topic '{topic.get('name', 'unknown')}': {str(e)}"
                        logger.error(error_msg)
                        stats["errors"].append(error_msg)
        
        return stats
    
    def get_statistics(self, supabase_client) -> dict:
        """Get embedding statistics from Supabase"""
        try:
            # Count total embeddings
            count_result = supabase_client.table("syllabus_embeddings").select("id", count="exact").execute()
            total = count_result.count or 0
            
            # Get unique subjects
            subjects_result = supabase_client.table("syllabus_embeddings").select("subject_code").execute()
            unique_subjects = len(set(r["subject_code"] for r in subjects_result.data)) if subjects_result.data else 0
            
            # Get unique topics
            topics_result = supabase_client.table("syllabus_embeddings").select("topic_name").execute()
            unique_topics = len(set(r["topic_name"] for r in topics_result.data)) if topics_result.data else 0
            
            return {
                "total_embeddings": total,
                "subjects_covered": unique_subjects,
                "topics_covered": unique_topics,
                "model": self.model_name,
                "dimension": self.embedding_dimension
            }
        except Exception as e:
            logger.error(f"Error getting embedding stats: {e}")
            return {
                "total_embeddings": 0,
                "subjects_covered": 0,
                "topics_covered": 0,
                "model": self.model_name,
                "dimension": self.embedding_dimension,
                "error": str(e)
            }
    
    def delete_embeddings(
        self,
        supabase_client,
        semester: Optional[int] = None,
        branch: Optional[str] = None,
        subject_code: Optional[str] = None
    ) -> int:
        """
        Delete embeddings with optional filters
        
        Args:
            supabase_client: Supabase client
            semester: Filter by semester
            branch: Filter by branch
            subject_code: Filter by subject
            
        Returns:
            Number of deleted records
        """
        query = supabase_client.table("syllabus_embeddings").delete()
        
        if subject_code:
            query = query.eq("subject_code", subject_code)
        elif branch and semester:
            query = query.eq("branch", branch).eq("semester", semester)
        elif branch:
            query = query.eq("branch", branch)
        elif semester:
            query = query.eq("semester", semester)
        else:
            # Safety: require at least one filter for delete all
            raise ValueError("At least one filter required for bulk delete")
        
        result = query.execute()
        return len(result.data) if result.data else 0


# Global instance
embedding_service = EmbeddingService()
