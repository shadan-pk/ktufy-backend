"""
Chat Service
Handles AI model interaction for chatbot functionality
Supports both Groq API (cloud) and Ollama (local)
"""
import os
from typing import Optional, AsyncGenerator, Union
import httpx
from groq import Groq


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
