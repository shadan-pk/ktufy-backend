"""
Query Router for KG-RAG
Determines whether to use Knowledge Graph, Vector Store, or both
"""
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Types of queries for routing"""
    KG_ONLY = "kg_only"  # Structural queries (prerequisites, relationships)
    VECTOR_ONLY = "vector_only"  # Content retrieval (definitions, explanations)
    KG_THEN_VECTOR = "kg_then_vector"  # Get context from KG, then retrieve content
    VECTOR_THEN_KG = "vector_then_kg"  # Find topic via vector, enrich with KG
    HYBRID = "hybrid"  # Use both in parallel


class QueryRouter:
    """
    Routes queries to appropriate data sources
    
    Query Patterns:
    1. STRUCTURAL (KG_ONLY):
       - "What are the prerequisites for X?"
       - "What should I study before X?"
       - "What topics are in Module 1?"
       - "Show me the syllabus structure for CS201"
    
    2. CONTENT (VECTOR_ONLY):
       - "Explain quick sort"
       - "What is a binary tree?"
       - "Give me an example of recursion"
    
    3. CONTEXT + CONTENT (KG_THEN_VECTOR):
       - "Explain all topics in Module 3"
       - "What is covered in Data Structures?"
    
    4. SEARCH + ENRICH (VECTOR_THEN_KG):
       - "Tell me about sorting algorithms"
       - "What does the syllabus say about trees?"
    
    5. COMPARISON (HYBRID):
       - "Difference between DFS and BFS"
       - "Compare stacks and queues"
    """
    
    # Keywords that indicate structural/KG queries
    STRUCTURAL_KEYWORDS = [
        "prerequisite", "prerequisites", "before", "after",
        "order", "sequence", "path", "learning path",
        "what topics", "list topics", "topics in",
        "modules in", "structure", "syllabus structure",
        "what comes", "what should i study",
        "how many modules", "how many topics"
    ]
    
    # Keywords that indicate content/Vector queries
    CONTENT_KEYWORDS = [
        "explain", "what is", "what are", "define", "definition",
        "how does", "how do", "how to",
        "example", "examples", "give me an example",
        "describe", "description",
        "tell me about", "teach me",
        "algorithm", "implementation", "code"
    ]
    
    # Keywords that indicate comparison (hybrid)
    COMPARISON_KEYWORDS = [
        "difference", "different", "compare", "comparison",
        "vs", "versus", "or", "better",
        "similarities", "similar", "same"
    ]
    
    # Keywords that indicate module/subject context needed first
    CONTEXT_KEYWORDS = [
        "all topics in", "everything in", "covered in",
        "module", "subject", "chapter"
    ]
    
    def __init__(self):
        pass
    
    def route(self, query: str) -> Tuple[QueryType, Dict[str, Any]]:
        """
        Analyze query and determine routing
        
        Args:
            query: User's question
            
        Returns:
            Tuple of (QueryType, metadata)
        """
        query_lower = query.lower()
        metadata = {
            "original_query": query,
            "detected_patterns": [],
            "extracted_entities": []
        }
        
        # Check for structural keywords
        has_structural = any(kw in query_lower for kw in self.STRUCTURAL_KEYWORDS)
        
        # Check for content keywords
        has_content = any(kw in query_lower for kw in self.CONTENT_KEYWORDS)
        
        # Check for comparison keywords
        has_comparison = any(kw in query_lower for kw in self.COMPARISON_KEYWORDS)
        
        # Check for context keywords
        has_context = any(kw in query_lower for kw in self.CONTEXT_KEYWORDS)
        
        # Extract potential entities (subject codes, topic names)
        metadata["extracted_entities"] = self._extract_entities(query)
        
        # Routing logic
        if has_comparison:
            metadata["detected_patterns"].append("comparison")
            return QueryType.HYBRID, metadata
        
        if has_structural and not has_content:
            metadata["detected_patterns"].append("structural")
            return QueryType.KG_ONLY, metadata
        
        if has_context:
            metadata["detected_patterns"].append("context_required")
            return QueryType.KG_THEN_VECTOR, metadata
        
        if has_content and not has_structural:
            metadata["detected_patterns"].append("content")
            # If we have specific entity, use vector then enrich with KG
            if metadata["extracted_entities"]:
                return QueryType.VECTOR_THEN_KG, metadata
            return QueryType.VECTOR_ONLY, metadata
        
        # Default: hybrid approach
        return QueryType.HYBRID, metadata
    
    def _extract_entities(self, query: str) -> List[Dict[str, str]]:
        """Extract potential entities from query"""
        entities = []
        
        # Subject codes (e.g., CS201, MA301)
        code_pattern = r'\b([A-Z]{2,4}\d{3}[A-Z]?)\b'
        codes = re.findall(code_pattern, query.upper())
        for code in codes:
            entities.append({"type": "subject_code", "value": code})
        
        # Module references (e.g., "Module 1", "M1")
        module_pattern = r'[Mm]odule\s*(\d+)|M(\d+)\b'
        modules = re.findall(module_pattern, query)
        for match in modules:
            module_num = match[0] or match[1]
            if module_num:
                entities.append({"type": "module_number", "value": int(module_num)})
        
        # Semester references
        semester_pattern = r'[Ss]emester\s*(\d+)|S(\d+)\b'
        semesters = re.findall(semester_pattern, query)
        for match in semesters:
            sem_num = match[0] or match[1]
            if sem_num:
                entities.append({"type": "semester", "value": int(sem_num)})
        
        return entities
    
    def get_kg_query_type(self, query: str) -> str:
        """
        Determine specific KG query type for optimization
        
        Returns:
            - "prerequisites": Get prerequisite chain
            - "hierarchy": Get IS_A hierarchy
            - "related": Get related concepts
            - "structure": Get subject/module structure
            - "path": Find learning path between concepts
        """
        query_lower = query.lower()
        
        if any(kw in query_lower for kw in ["prerequisite", "before", "need to know", "should study"]):
            return "prerequisites"
        
        if any(kw in query_lower for kw in ["type of", "kind of", "is a", "hierarchy"]):
            return "hierarchy"
        
        if any(kw in query_lower for kw in ["related", "similar", "like"]):
            return "related"
        
        if any(kw in query_lower for kw in ["path", "from", "to", "reach", "get to"]):
            return "path"
        
        return "structure"
    
    def get_vector_chunk_types(self, query: str) -> List[str]:
        """
        Determine which chunk types to search based on query
        
        Chunk types:
        - syllabus_content: Original syllabus text
        - topic_list: List of topics in a module
        - topic_detail: Individual topic details
        - course_outcomes: Course outcomes
        - references: Textbooks and references
        """
        query_lower = query.lower()
        
        if any(kw in query_lower for kw in ["textbook", "reference", "book", "read"]):
            return ["references"]
        
        if any(kw in query_lower for kw in ["outcome", "objective", "co", "po", "learn"]):
            return ["course_outcomes"]
        
        if any(kw in query_lower for kw in ["list", "all topics", "topics in", "what topics"]):
            return ["topic_list", "syllabus_content"]
        
        if any(kw in query_lower for kw in ["explain", "what is", "define", "describe"]):
            return ["topic_detail", "syllabus_content"]
        
        # Default: search all content types
        return ["syllabus_content", "topic_detail", "topic_list"]


# Global instance
query_router = QueryRouter()
