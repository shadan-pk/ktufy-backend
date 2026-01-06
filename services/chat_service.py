"""
Chat Service
Handles AI model interaction for chatbot functionality with KG-RAG integration
Supports both Groq API (cloud) and Ollama (local)
"""
import os
import logging
from typing import Optional, AsyncGenerator, Union, List, Dict, Any
import httpx
from groq import Groq

from services.query_router import query_router, QueryType
from services.neo4j_service import neo4j_service
from services.embedding_service import embedding_service
from utils.supabase_client import supabase_admin_client

logger = logging.getLogger(__name__)


class ChatService:
    """
    Service for handling chat completions with AI models
    Supports hybrid approach: Groq API (primary) and Ollama (fallback)
    """
    
    def __init__(self):
        """Initialize chat service with available AI providers"""
        # Try Groq API first (free tier: 14,400 requests/day)
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.use_groq = self.groq_api_key is not None
        
        # Fallback to Ollama (local)
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        
        if self.use_groq:
            self.client = Groq(api_key=self.groq_api_key)
            self.model = "llama-3.1-8b-instant"  # Fast and free on Groq
            print(f"✅ Chat service initialized with Groq API (model: {self.model})")
        else:
            self.model = "llama3"
            print(f"✅ Chat service initialized with Ollama (model: {self.model})")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # KG-RAG Integration Methods
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_rag_context(
        self,
        query: str,
        semester: Optional[int] = None,
        branch: Optional[str] = None,
        subject_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get relevant context from Knowledge Graph and Vector Store using intelligent routing
        
        Args:
            query: User's question
            semester: Optional filter by semester
            branch: Optional filter by branch
            subject_code: Optional filter by subject
            
        Returns:
            Dictionary with kg_context, vector_context, and routing info
        """
        context = {
            "kg_results": [],
            "vector_results": [],
            "routing": None,
            "has_context": False
        }
        
        try:
            # Route the query to determine best data source
            query_type, metadata = query_router.route(query)
            context["routing"] = {
                "type": query_type.value,
                "metadata": metadata
            }
            
            # Fetch from Knowledge Graph
            if query_type in [QueryType.KG_ONLY, QueryType.KG_THEN_VECTOR, QueryType.HYBRID]:
                if neo4j_service.is_connected():
                    # Search for relevant concepts
                    kg_results = neo4j_service.search_concepts(query, limit=5)
                    
                    # For each concept, get additional context
                    for concept in kg_results[:3]:
                        concept_id = concept.get("canonical_id")
                        concept_type = concept.get("type", "Topic")
                        
                        if concept_id:
                            # Get prerequisites based on concept type
                            if concept_type == "Topic":
                                prereqs = neo4j_service.get_topic_prerequisites(concept_id)
                            elif concept_type == "Subject":
                                prereqs = neo4j_service.get_prerequisites(concept_id)
                            else:
                                prereqs = []
                            concept["prerequisites"] = prereqs[:3] if prereqs else []
                            
                            # Get related concepts
                            relationships = neo4j_service.get_concept_relationships(concept_id)
                            concept["relationships"] = relationships[:5] if relationships else []
                    
                    context["kg_results"] = kg_results
            
            # Fetch from Vector Store
            if query_type in [QueryType.VECTOR_ONLY, QueryType.VECTOR_THEN_KG, QueryType.HYBRID]:
                if embedding_service.is_ready() and supabase_admin_client:
                    vector_results = embedding_service.search_similar(
                        supabase_client=supabase_admin_client,
                        query=query,
                        limit=5,
                        semester=semester,
                        branch=branch,
                        subject_code=subject_code
                    )
                    context["vector_results"] = vector_results
            
            context["has_context"] = bool(context["kg_results"] or context["vector_results"])
            
        except Exception as e:
            logger.error(f"Error fetching RAG context: {e}")
        
        return context
    
    def format_context_for_prompt(self, context: Dict[str, Any]) -> str:
        """
        Format the RAG context into a string for the LLM prompt
        
        Args:
            context: Dictionary with kg_results and vector_results
            
        Returns:
            Formatted context string
        """
        if not context.get("has_context"):
            return ""
        
        parts = []
        
        # Format Knowledge Graph results
        kg_results = context.get("kg_results", [])
        if kg_results:
            parts.append("=== KNOWLEDGE GRAPH CONTEXT ===")
            for i, concept in enumerate(kg_results[:3], 1):
                parts.append(f"\n**Concept {i}: {concept.get('name', 'Unknown')}**")
                if concept.get("subject_name"):
                    parts.append(f"Subject: {concept.get('subject_name')}")
                if concept.get("module_name"):
                    parts.append(f"Module: {concept.get('module_name')}")
                if concept.get("description"):
                    parts.append(f"Description: {concept.get('description')}")
                
                # Prerequisites
                prereqs = concept.get("prerequisites", [])
                if prereqs:
                    prereq_names = [p.get("name", "") for p in prereqs if p.get("name")]
                    if prereq_names:
                        parts.append(f"Prerequisites: {', '.join(prereq_names)}")
                
                # Related concepts
                rels = concept.get("relationships", [])
                if rels:
                    for rel in rels[:3]:
                        parts.append(f"  - {rel.get('type', 'RELATED')}: {rel.get('target_name', '')}")
        
        # Format Vector Store results
        vector_results = context.get("vector_results", [])
        if vector_results:
            parts.append("\n=== SYLLABUS CONTENT ===")
            for i, result in enumerate(vector_results[:3], 1):
                parts.append(f"\n**Source {i}:** {result.get('subject_name', '')} - {result.get('module_name', '')}")
                content = result.get("content", "")
                # Truncate long content
                if len(content) > 500:
                    content = content[:500] + "..."
                parts.append(content)
        
        return "\n".join(parts)
    
    async def generate_rag_response(
        self,
        query: str,
        conversation_history: List[Dict[str, str]] = None,
        semester: Optional[int] = None,
        branch: Optional[str] = None,
        subject_code: Optional[str] = None,
        stream: bool = False
    ) -> Union[str, AsyncGenerator[str, None]]:
        """
        Generate AI response with KG-RAG context
        
        Args:
            query: User's question
            conversation_history: Previous messages in the conversation
            semester: Optional filter
            branch: Optional filter
            subject_code: Optional filter
            stream: Whether to stream response
            
        Returns:
            AI response string or async generator for streaming
        """
        # Get RAG context
        context = await self.get_rag_context(
            query=query,
            semester=semester,
            branch=branch,
            subject_code=subject_code
        )
        
        # Format context for prompt
        context_str = self.format_context_for_prompt(context)
        
        # Build messages
        messages = [{"role": "system", "content": self.get_rag_system_prompt(context_str)}]
        
        # Add conversation history
        if conversation_history:
            messages.extend(conversation_history)
        
        # Add current query
        messages.append({"role": "user", "content": query})
        
        # Generate response
        return await self.generate_response(messages, stream=stream)
    
    async def generate_response(
        self, 
        messages: list[dict],
        stream: bool = False
    ) -> Union[str, AsyncGenerator[str, None]]:
        """
        Generate AI response from chat messages
        
        Args:
            messages: List of message dicts with 'role' and 'content'
                     Example: [{"role": "user", "content": "Hello"}]
            stream: Whether to stream the response (for real-time display)
        
        Returns:
            String response or async generator for streaming
        """
        if self.use_groq:
            return await self._generate_groq(messages, stream)
        else:
            return await self._generate_ollama(messages, stream)
    
    async def _generate_groq(
        self, 
        messages: list[dict], 
        stream: bool
    ) -> Union[str, AsyncGenerator[str, None]]:
        """Generate response using Groq API"""
        if stream:
            return self._stream_groq(messages)
        else:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=1024,
                    top_p=1,
                    stream=False
                )
                return response.choices[0].message.content
            except Exception as e:
                print(f"❌ Groq API error: {str(e)}")
                raise Exception(f"Failed to generate response: {str(e)}")
    
    async def _stream_groq(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        """Stream response from Groq API"""
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1024,
                top_p=1,
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            print(f"❌ Groq streaming error: {str(e)}")
            yield f"Error: {str(e)}"
    
    async def _generate_ollama(
        self, 
        messages: list[dict], 
        stream: bool
    ) -> Union[str, AsyncGenerator[str, None]]:
        """Generate response using local Ollama"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.ollama_base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": stream
                    },
                    timeout=60.0
                )
                
                if stream:
                    return self._stream_ollama_response(response)
                else:
                    data = response.json()
                    return data["message"]["content"]
        except httpx.ConnectError:
            raise Exception(
                "Could not connect to Ollama. Make sure Ollama is running: ollama serve"
            )
        except Exception as e:
            print(f"❌ Ollama error: {str(e)}")
            raise Exception(f"Failed to generate response: {str(e)}")
    
    async def _stream_ollama_response(self, response) -> AsyncGenerator[str, None]:
        """Stream response from Ollama"""
        try:
            async for line in response.aiter_lines():
                if line:
                    import json
                    data = json.loads(line)
                    if "message" in data and "content" in data["message"]:
                        yield data["message"]["content"]
        except Exception as e:
            print(f"❌ Ollama streaming error: {str(e)}")
            yield f"Error: {str(e)}"
    
    def get_system_prompt(self) -> str:
        """
        Get the system prompt that defines the chatbot's personality and role
        
        Returns:
            System prompt string
        """
        return """You are KTUfy AI, an intelligent study assistant for KTU (Kerala Technological University) students.

Your role:
- Help students understand their course materials and syllabus topics
- Answer questions about computer science, engineering, and academic subjects
- Generate study questions, explanations, and examples
- Provide guidance on exam preparation and study strategies
- Be encouraging, supportive, and motivational
- Break down complex topics into simple, understandable explanations

Guidelines:
- Keep responses clear, concise, and well-structured
- Use examples and analogies when explaining concepts
- Ask clarifying questions when the student's query is unclear
- Stay focused on educational topics
- Be friendly, approachable, and patient
- If you don't know something, admit it honestly
- Encourage active learning and critical thinking

Remember: You're here to help students learn and succeed in their studies!"""
    
    def get_rag_system_prompt(self, context: str = "") -> str:
        """
        Get the system prompt with RAG context for KG-RAG responses
        
        Args:
            context: Formatted context from Knowledge Graph and Vector Store
            
        Returns:
            System prompt with context
        """
        base_prompt = """You are KTUfy AI, an intelligent study assistant for KTU (Kerala Technological University) students.

You have access to the official KTU syllabus and course materials through a Knowledge Graph and document database.

Your role:
- Answer questions using the provided syllabus context when available
- Help students understand their course materials and topics
- Explain concepts clearly based on what's in their actual syllabus
- Identify prerequisites and related topics to guide learning
- Be accurate and cite the syllabus when relevant

Guidelines:
- ALWAYS use the provided context to answer syllabus-related questions
- If context is provided, base your answer primarily on that information
- Mention which subject/module the information comes from when relevant
- If the context doesn't contain the answer, say so and provide general knowledge
- Keep responses clear, structured, and educational
- Use examples to explain complex concepts"""
        
        if context:
            return f"""{base_prompt}

=== RELEVANT CONTEXT FROM KTU SYLLABUS ===
{context}
=== END OF CONTEXT ===

Use the above context to answer the student's question. If the context is relevant, incorporate it into your response."""
        
        return base_prompt
    
    def get_provider_info(self) -> dict:
        """
        Get information about the current AI provider
        
        Returns:
            Dictionary with provider details
        """
        return {
            "provider": "groq" if self.use_groq else "ollama",
            "model": self.model,
            "base_url": self.ollama_base_url if not self.use_groq else "https://api.groq.com"
        }


# Create singleton instance
chat_service = ChatService()
