"""
Chat Service
Handles AI model interaction for chatbot functionality with KG-RAG integration
Supports both Groq API (cloud) and Ollama (local)
"""
import os
import logging
from typing import Optional, AsyncGenerator, Union, List, Dict, Any
import httpx
from openai import AsyncOpenAI

from services.query_router import query_router, QueryType
from services.neo4j_service_v2 import neo4j_service
from services.embedding_service_v2 import embedding_service
from utils.supabase_client import supabase_admin_client

logger = logging.getLogger(__name__)


class ChatService:
    """
    Service for handling chat completions with AI models
    Supports hybrid approach: OpenAI API (primary) and Ollama (fallback)
    """
    
    def __init__(self):
        """Initialize chat service with available AI providers"""
        # Try OpenAI API first
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.use_openai = self.openai_api_key is not None
        
        # Fallback to Ollama (local)
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        
        if self.use_openai:
            self.client = AsyncOpenAI(api_key=self.openai_api_key)
            self.model = "gpt-4o-mini"
            print(f"✅ Chat service initialized with OpenAI API (model: {self.model})")
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
            print(f"   📍 Query routing: {query_type.value}")

            if query_type == QueryType.NO_RAG:
                context["has_context"] = False
                return context
            
            # Prepare tasks for parallel execution
            tasks = []
            
            # KG Search Task
            async def fetch_kg():
                if query_type in [QueryType.KG_ONLY, QueryType.KG_THEN_VECTOR, QueryType.HYBRID, QueryType.VECTOR_THEN_KG]:
                    neo4j_connected = neo4j_service.is_connected()
                    if neo4j_connected:
                        try:
                            # Search for relevant concepts
                            kg_results = neo4j_service.search_concepts(query, limit=5)
                            print(f"   📍 KG search returned: {len(kg_results)} results")
                            
                            # For each concept, get additional context
                            for concept in kg_results[:3]:
                                concept_id = concept.get("id") or concept.get("canonical_id")
                                concept_type = concept.get("type", "Topic")
                                
                                if concept_id:
                                    # Fix: Use correct method names for Neo4jServiceV2
                                    try:
                                        prereqs = neo4j_service.get_prerequisites(concept_id)
                                        concept["prerequisites"] = prereqs[:3] if prereqs else []
                                    except Exception as e:
                                        print(f"   ⚠️ Error fetching prereqs for {concept_id}: {e}")
                                    
                                    try:
                                        # Fix: Use get_related_concepts instead of non-existent get_concept_relationships
                                        related = neo4j_service.get_related_concepts(concept_id)
                                        concept["relationships"] = related[:5] if related else []
                                    except Exception as e:
                                        print(f"   ⚠️ Error fetching relationships for {concept_id}: {e}")
                            
                            return kg_results
                        except Exception as kg_error:
                            print(f"   ❌ KG search error: {kg_error}")
                    else:
                        print("   ⚠️ Neo4j not connected, skipping KG search")
                return []

            # Vector Search Task
            async def fetch_vector():
                should_try_vector = query_type in [QueryType.VECTOR_ONLY, QueryType.VECTOR_THEN_KG, QueryType.HYBRID, QueryType.KG_THEN_VECTOR]
                if should_try_vector:
                    embedding_ready = embedding_service.is_ready()
                    supabase_ready = supabase_admin_client is not None
                    if embedding_ready and supabase_ready:
                        try:
                            vector_results = embedding_service.search_similar(
                                supabase_client=supabase_admin_client,
                                query=query,
                                limit=5,
                                semester=semester,
                                branch=branch,
                                subject_code=subject_code
                            )
                            print(f"   📍 Vector search returned: {len(vector_results) if vector_results else 0} results")
                            return vector_results
                        except Exception as vec_error:
                            print(f"   ❌ Vector search error: {vec_error}")
                    else:
                        print("   ⚠️ Embedding/Supabase not ready, skipping vector search")
                return []

            # Run searches in parallel
            import asyncio
            kg_results, vector_results = await asyncio.gather(fetch_kg(), fetch_vector())
            
            context["kg_results"] = kg_results
            context["vector_results"] = vector_results
            context["has_context"] = bool(kg_results or vector_results)
            
        except Exception as e:
            logger.error(f"Error fetching RAG context: {e}", exc_info=True)
        
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
                concept_type = concept.get('type', concept.get('concept_type', 'Concept'))
                concept_name = concept.get('name', 'Unknown')
                
                # Extract related info from nested dicts if present
                subj = concept.get("subject", {})
                mod = concept.get("module", {})
                
                subj_code = subj.get("code") or concept.get("subject_code")
                mod_num = mod.get("number") or concept.get("module_number")
                mod_name = mod.get("name") or concept.get("module_name")
                
                # Build header with hierarchy info
                header = f"**{concept_type}: {concept_name}**"
                if subj_code:
                    header = f"**{concept_type}: {concept_name}** (Subject: {subj_code})"
                if mod_num:
                    header += f" [Module {mod_num}]"
                    
                parts.append(f"\n{header}")
                
                # Description / Content
                if concept.get("description") or concept.get("original_text"):
                    desc = concept.get("description") or concept.get("original_text")
                    parts.append(f"Content: {desc}")
                
                # Show topics for modules
                if concept_type == 'Module' or 'topics' in concept:
                    topic_list = concept.get("topics", [])
                    if topic_list:
                        parts.append(f"Topics covered: {', '.join(topic_list[:10])}")
                
                # Show modules for subjects
                if concept_type == 'Subject' or 'modules' in concept:
                    module_list = concept.get("modules", [])
                    if module_list:
                        parts.append(f"Modules in this syllabus: {', '.join(module_list[:8])}")
                
                # Show prerequisites if available
                prereqs = concept.get("prerequisites", [])
                if prereqs:
                    prereq_names = [p.get("concept", {}).get("name") for p in prereqs if p.get("concept", {}).get("name")]
                    if prereq_names:
                        parts.append(f"Prerequisites: {', '.join(prereq_names)}")
                
                # Show related concepts
                related = concept.get("relationships", [])
                if related:
                    rel_names = [r.get("concept", {}).get("name") for r in related if r.get("concept", {}).get("name")]
                    if rel_names:
                        parts.append(f"Related Topics: {', '.join(rel_names)}")
        
        # Format Vector Store results
        vector_results = context.get("vector_results", [])
        if vector_results:
            parts.append("\n=== SYLLABUS CONTENT ===")
            for i, result in enumerate(vector_results[:5], 1):
                subject = result.get('subject_name', '') or result.get('subject_code', '')
                module_num = result.get('module_number', '')
                module_name = result.get('module_name', '')
                topic = result.get('topic_name', '')
                
                header = f"**Source {i}:** {subject}"
                if module_num:
                    header += f" - Module {module_num}"
                if module_name:
                    header += f": {module_name}"
                if topic:
                    header += f" - Topic: {topic}"
                    
                parts.append(f"\n{header}")
                content = result.get("content", "")
                # Truncate long content
                if len(content) > 800:
                    content = content[:800] + "..."
                parts.append(content)
        
        return "\n".join(parts)
    
    async def generate_rag_response(
        self,
        query: str,
        conversation_history: List[Dict[str, str]] = None,
        semester: Optional[int] = None,
        branch: Optional[str] = None,
        subject_code: Optional[str] = None,
        system_prompt: Optional[str] = None,
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
            system_prompt: Optional system prompt override for this request
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
        
        # Log RAG context usage for debugging
        kg_count = len(context.get("kg_results", []))
        vector_count = len(context.get("vector_results", []))
        routing_type = context.get("routing", {}).get("type", "unknown")
        print(f"🔍 RAG Context: routing={routing_type}, kg_results={kg_count}, vector_results={vector_count}")
        if kg_count > 0:
            print(f"   📊 KG Topics: {[c.get('name', 'N/A') for c in context['kg_results'][:3]]}")
        if vector_count > 0:
            print(f"   📄 Vector Sources: {[r.get('subject_name', 'N/A') for r in context['vector_results'][:3]]}")
        
        # Format context for prompt
        context_str = self.format_context_for_prompt(context)
        
        # Debug: Show formatted context (first 500 chars)
        if context_str:
            print(f"   📝 Context preview: {context_str[:500]}...")
        
        # Build messages
        if system_prompt and system_prompt.strip():
            system_content = system_prompt.strip()
            if context_str:
                system_content = (
                    f"{system_content}\n\n"
                    "=== RELEVANT CONTEXT FROM KTU SYLLABUS ===\n"
                    f"{context_str}\n"
                    "=== END OF CONTEXT ===\n\n"
                    "Use the above context when answering."
                )
        else:
            system_content = self.get_rag_system_prompt(context_str)

        messages = [{"role": "system", "content": system_content}]
        
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
        if self.use_openai:
            return await self._generate_openai(messages, stream)
        else:
            return await self._generate_ollama(messages, stream)
    
    async def _generate_openai(
        self, 
        messages: list[dict], 
        stream: bool
    ) -> Union[str, AsyncGenerator[str, None]]:
        """Generate response using OpenAI API"""
        if stream:
            return self._stream_openai(messages)
        else:
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=1024,
                    top_p=1,
                    stream=False
                )
                return response.choices[0].message.content
            except Exception as e:
                print(f"❌ OpenAI API error: {str(e)}")
                raise Exception(f"Failed to generate response: {str(e)}")
    
    async def _stream_openai(self, messages: list[dict]) -> AsyncGenerator[str, None]:
        """Stream response from OpenAI API"""
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1024,
                top_p=1,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            print(f"❌ OpenAI streaming error: {str(e)}")
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
        base_prompt = """You are KTUfy AI, the ultimate study companion for KTU (Kerala Technological University) students. 
Your goal is to provide high-quality, accurate, and syllabus-aligned academic assistance, similar to a specialized version of ChatGPT.

You have access to the **official KTU syllabus**, structured via a Knowledge Graph and a vector database.

### 🧠 RESPONSE STRATEGY:
1.  **Detailed Explanations**: Don't just give brief definitions. Explain concepts in depth, covering their "how" and "why", just like ChatGPT would.
2.  **Proactive Examples**: For every major concept, provide a **clear example**. 
    - If it's a programming topic, provide a clean **code snippet**.
    - If it's a theoretical topic, provide a **real-world analogy**.
    - If it's a mathematical topic, provide a **step-by-step calculation example**.
3.  **Syllabus Alignment**: Use the provided context to ensure your examples and explanations match the KTU curriculum standards.
4.  **Module & Topic Structure**: When explaining a module, list all its topics and then deep-dive into the specific one the student asked about.
5.  **Interactive Learning**: End your response by asking if they'd like more examples or a practice question on the topic.

### ✍️ FORMATTING RULES:
- Use **bold** for technical terms.
- Use `###` for section headers.
- Use code blocks (```language) for all technical examples.
- Use bullet points for structured data.
- Always mention: "According to the KTU syllabus for [Subject Code]..."

### 🎓 TONE:
Helpful, expert, and encouraging. You are an elite tutor who makes complex topics easy to understand through great examples."""
        
        if context:
            return f"""{base_prompt}

=== RELEVANT CONTEXT FROM KTU SYLLABUS ===
{context}
=== END OF CONTEXT ===

Use the above context to answer the student's question accurately. Base your response on the provided syllabus information."""
        
        return base_prompt
    
    def get_provider_info(self) -> dict:
        """
        Get information about the current AI provider
        
        Returns:
            Dictionary with provider details
        """
        return {
            "provider": "openai" if self.use_openai else "ollama",
            "model": self.model,
            "base_url": self.ollama_base_url if not self.use_openai else "https://api.openai.com/v1"
        }


# Create singleton instance
chat_service = ChatService()
