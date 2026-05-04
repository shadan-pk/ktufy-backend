# 🤖 Chatbot Implementation Guide - KTUfy Backend

## 📋 Overview

This guide covers implementing a chatbot system for KTUfy with chat sessions, message history, and AI model integration.

---

## 🎯 Implementation Phases

### **Phase 1: Basic Chat Infrastructure** (Start Here)
1. Database tables for chat sessions and messages
2. API endpoints for CRUD operations
3. Chat history management
4. Session management

### **Phase 2: AI Model Integration**
1. Choose deployment approach (Local vs Cloud)
2. Integrate LLM (Ollama, Groq, or Colab)
3. Streaming responses
4. Context management

### **Phase 3: Advanced Features**
1. RAG (Retrieval Augmented Generation)
2. Knowledge base integration
3. Study material context
4. Multi-modal support

---

## 🏗️ Architecture Decision: Model Deployment

### **Option 1: Local Backend (Ollama)** ⭐ RECOMMENDED
**Pros:**
- ✅ Free and unlimited usage
- ✅ Fast response times (no API calls)
- ✅ Privacy (data stays local)
- ✅ No API costs
- ✅ Works offline
- ✅ Easy to setup with Ollama

**Cons:**
- ❌ Requires good GPU/CPU
- ❌ Model size on disk (2-7GB)
- ❌ Initial setup complexity

**Best for:** Development, testing, and production if you have good hardware

---

### **Option 2: Google Colab**
**Pros:**
- ✅ Free GPU access (with limits)
- ✅ No local resource usage
- ✅ Can use larger models

**Cons:**
- ❌ Session timeouts (90 min idle, 12 hr max)
- ❌ Need to reconnect frequently
- ❌ Unreliable for production
- ❌ Complex tunnel setup (ngrok)
- ❌ Not suitable for 24/7 service

**Best for:** Experimentation only, NOT production

---

### **Option 3: Cloud API (Groq/OpenAI)** 🚀 BEST FOR PRODUCTION
**Pros:**
- ✅ Extremely fast (Groq)
- ✅ No infrastructure needed
- ✅ Always available
- ✅ Scalable
- ✅ Latest models

**Cons:**
- ❌ API costs (but Groq has free tier)
- ❌ Requires internet
- ❌ Data sent to third party

**Best for:** Production deployment with reliability

---

### **Option 4: Hybrid Approach** 🎯 SMARTEST
**Use Case Based:**
- **Development/Testing:** Ollama locally
- **Production:** Groq API (free tier: 14,400 requests/day)
- **Fallback:** Switch between local and API based on availability

**This is what we'll implement!**

---

## 📊 Database Schema

### **Table 1: chat_sessions**
```sql
CREATE TABLE public.chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT DEFAULT 'New Chat',
    model_name TEXT DEFAULT 'llama3',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_chat_sessions_user_id ON public.chat_sessions(user_id);
CREATE INDEX idx_chat_sessions_created_at ON public.chat_sessions(created_at DESC);

-- RLS Policies
ALTER TABLE public.chat_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own chat sessions"
    ON public.chat_sessions FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can create their own chat sessions"
    ON public.chat_sessions FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own chat sessions"
    ON public.chat_sessions FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own chat sessions"
    ON public.chat_sessions FOR DELETE
    USING (auth.uid() = user_id);
```

### **Table 2: chat_messages**
```sql
CREATE TABLE public.chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES public.chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    tokens_used INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_chat_messages_session_id ON public.chat_messages(session_id);
CREATE INDEX idx_chat_messages_created_at ON public.chat_messages(created_at);

-- RLS Policies
ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view messages in their sessions"
    ON public.chat_messages FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.chat_sessions
            WHERE chat_sessions.id = chat_messages.session_id
            AND chat_sessions.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can create messages in their sessions"
    ON public.chat_messages FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.chat_sessions
            WHERE chat_sessions.id = chat_messages.session_id
            AND chat_sessions.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can delete messages in their sessions"
    ON public.chat_messages FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM public.chat_sessions
            WHERE chat_sessions.id = chat_messages.session_id
            AND chat_sessions.user_id = auth.uid()
        )
    );
```

---

## 🛠️ Backend Implementation

### **Step 1: Install Dependencies**

Add to `requirements.txt`:
```txt
# AI/ML Models
ollama>=0.1.0              # Local LLM (Ollama)
groq>=0.4.0                # Cloud LLM (Groq API)
langchain>=0.1.0           # LLM framework
langchain-community>=0.0.10

# Streaming
sse-starlette>=1.8.2       # Server-sent events for streaming
```

### **Step 2: Create Models**

Create `models/chat_session.py`:
```python
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from models.base import Base

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    title = Column(Text, default="New Chat")
    model_name = Column(Text, default="llama3")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata = Column(JSONB, default={})
    
    # Relationship
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(Text, nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    tokens_used = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    metadata = Column(JSONB, default={})
    
    # Relationship
    session = relationship("ChatSession", back_populates="messages")
```

### **Step 3: Create Schemas**

Create `schemas/chat.py`:
```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class ChatMessageBase(BaseModel):
    role: str = Field(..., description="Message role: user, assistant, or system")
    content: str = Field(..., description="Message content")

class ChatMessageCreate(ChatMessageBase):
    pass

class ChatMessageResponse(ChatMessageBase):
    id: UUID
    session_id: UUID
    tokens_used: int = 0
    created_at: datetime
    metadata: dict = {}
    
    class Config:
        from_attributes = True

class ChatSessionCreate(BaseModel):
    title: Optional[str] = Field("New Chat", description="Session title")
    model_name: Optional[str] = Field("llama3", description="Model to use")

class ChatSessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    model_name: str
    created_at: datetime
    updated_at: datetime
    metadata: dict = {}
    message_count: Optional[int] = 0
    
    class Config:
        from_attributes = True

class ChatSessionWithMessages(ChatSessionResponse):
    messages: List[ChatMessageResponse] = []

class ChatRequest(BaseModel):
    message: str = Field(..., description="User message")
    session_id: Optional[UUID] = Field(None, description="Session ID (creates new if not provided)")
    stream: bool = Field(False, description="Stream response")

class ChatResponse(BaseModel):
    session_id: UUID
    message: ChatMessageResponse
    assistant_message: ChatMessageResponse
```

### **Step 4: Create Chat Service**

Create `services/chat_service.py`:
```python
import os
from typing import Optional, AsyncGenerator
import httpx
from groq import Groq

class ChatService:
    def __init__(self):
        # Try Groq API first (free tier)
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.use_groq = self.groq_api_key is not None
        
        # Fallback to Ollama (local)
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        
        if self.use_groq:
            self.client = Groq(api_key=self.groq_api_key)
            self.model = "llama-3.1-8b-instant"  # Fast and free
        else:
            self.model = "llama3"
    
    async def generate_response(
        self, 
        messages: list[dict],
        stream: bool = False
    ) -> str | AsyncGenerator[str, None]:
        """
        Generate AI response
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            stream: Whether to stream the response
        """
        if self.use_groq:
            return await self._generate_groq(messages, stream)
        else:
            return await self._generate_ollama(messages, stream)
    
    async def _generate_groq(self, messages: list[dict], stream: bool):
        """Generate using Groq API"""
        if stream:
            return self._stream_groq(messages)
        else:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1024
            )
            return response.choices[0].message.content
    
    async def _stream_groq(self, messages: list[dict]):
        """Stream response from Groq"""
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
            stream=True
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    async def _generate_ollama(self, messages: list[dict], stream: bool):
        """Generate using local Ollama"""
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
    
    async def _stream_ollama_response(self, response):
        """Stream response from Ollama"""
        async for line in response.aiter_lines():
            if line:
                import json
                data = json.loads(line)
                if "message" in data:
                    yield data["message"]["content"]
    
    def get_system_prompt(self) -> str:
        """Get system prompt for the chatbot"""
        return """You are KTUfy AI, an intelligent study assistant for KTU (Kerala Technological University) students.

Your role:
- Help students understand their course materials
- Answer questions about syllabus topics
- Generate study questions and explanations
- Provide guidance on exam preparation
- Be encouraging and supportive

Guidelines:
- Keep responses clear and concise
- Use examples when explaining concepts
- Ask clarifying questions when needed
- Stay focused on educational topics
- Be friendly and approachable"""
```

### **Step 5: Create Chat Router**

Create `routers/chat.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from typing import List
from uuid import UUID

from app.auth import get_current_user, AuthenticatedUser
from schemas.chat import (
    ChatSessionCreate,
    ChatSessionResponse,
    ChatSessionWithMessages,
    ChatRequest,
    ChatResponse,
    ChatMessageResponse
)
from services.chat_service import ChatService
from utils.supabase_client import supabase_client

router = APIRouter(
    prefix="/api/v1/chat",
    tags=["Chat"]
)

chat_service = ChatService()

@router.post("/sessions", response_model=ChatSessionResponse)
async def create_chat_session(
    session_data: ChatSessionCreate,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """Create a new chat session"""
    try:
        response = supabase_client.table("chat_sessions").insert({
            "user_id": current_user.user_id,
            "title": session_data.title,
            "model_name": session_data.model_name
        }).execute()
        
        return response.data[0]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating session: {str(e)}"
        )

@router.get("/sessions", response_model=List[ChatSessionResponse])
async def get_user_sessions(
    current_user: AuthenticatedUser = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0
):
    """Get all chat sessions for current user"""
    try:
        response = supabase_client.table("chat_sessions")\
            .select("*, messages:chat_messages(count)")\
            .eq("user_id", current_user.user_id)\
            .order("updated_at", desc=True)\
            .range(offset, offset + limit - 1)\
            .execute()
        
        return response.data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching sessions: {str(e)}"
        )

@router.get("/sessions/{session_id}", response_model=ChatSessionWithMessages)
async def get_chat_session(
    session_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """Get a specific chat session with messages"""
    try:
        # Get session
        session_response = supabase_client.table("chat_sessions")\
            .select("*")\
            .eq("id", str(session_id))\
            .eq("user_id", current_user.user_id)\
            .execute()
        
        if not session_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Get messages
        messages_response = supabase_client.table("chat_messages")\
            .select("*")\
            .eq("session_id", str(session_id))\
            .order("created_at")\
            .execute()
        
        session = session_response.data[0]
        session["messages"] = messages_response.data
        
        return session
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching session: {str(e)}"
        )

@router.post("/message", response_model=ChatResponse)
async def send_message(
    chat_request: ChatRequest,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """Send a message and get AI response"""
    try:
        # Create session if needed
        if not chat_request.session_id:
            session_response = supabase_client.table("chat_sessions").insert({
                "user_id": current_user.user_id,
                "title": chat_request.message[:50]  # First 50 chars as title
            }).execute()
            session_id = session_response.data[0]["id"]
        else:
            session_id = str(chat_request.session_id)
        
        # Save user message
        user_message_response = supabase_client.table("chat_messages").insert({
            "session_id": session_id,
            "role": "user",
            "content": chat_request.message
        }).execute()
        
        # Get conversation history
        history_response = supabase_client.table("chat_messages")\
            .select("role, content")\
            .eq("session_id", session_id)\
            .order("created_at")\
            .execute()
        
        # Build messages for AI
        messages = [{"role": "system", "content": chat_service.get_system_prompt()}]
        messages.extend([
            {"role": msg["role"], "content": msg["content"]}
            for msg in history_response.data
        ])
        
        # Generate AI response
        ai_response = await chat_service.generate_response(messages, stream=False)
        
        # Save assistant message
        assistant_message_response = supabase_client.table("chat_messages").insert({
            "session_id": session_id,
            "role": "assistant",
            "content": ai_response
        }).execute()
        
        # Update session timestamp
        supabase_client.table("chat_sessions")\
            .update({"updated_at": "now()"})\
            .eq("id", session_id)\
            .execute()
        
        return {
            "session_id": session_id,
            "message": user_message_response.data[0],
            "assistant_message": assistant_message_response.data[0]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing message: {str(e)}"
        )

@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user)
):
    """Delete a chat session"""
    try:
        response = supabase_client.table("chat_sessions")\
            .delete()\
            .eq("id", str(session_id))\
            .eq("user_id", current_user.user_id)\
            .execute()
        
        return {"message": "Session deleted successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting session: {str(e)}"
        )
```

---

## 🚀 Setup Instructions

### **Option A: Using Groq API (Recommended for Start)**

1. **Get Free API Key:**
   ```
   Visit: https://console.groq.com
   Sign up → Get API Key
   Free tier: 14,400 requests/day
   ```

2. **Add to .env:**
   ```env
   GROQ_API_KEY=gsk_your_api_key_here
   ```

3. **Install:**
   ```bash
   pip install groq
   ```

### **Option B: Using Ollama (Local)**

1. **Install Ollama:**
   ```bash
   # Windows
   Download from: https://ollama.com/download
   
   # Or use winget
   winget install Ollama.Ollama
   ```

2. **Pull Model:**
   ```bash
   ollama pull llama3
   # or smaller model
   ollama pull phi3
   ```

3. **Start Ollama:**
   ```bash
   ollama serve
   ```

4. **Add to .env (optional):**
   ```env
   OLLAMA_BASE_URL=http://localhost:11434
   ```

---

## 📡 API Endpoints Summary

```
POST   /api/v1/chat/sessions              - Create new chat session
GET    /api/v1/chat/sessions              - Get all user sessions
GET    /api/v1/chat/sessions/{id}         - Get session with messages
POST   /api/v1/chat/message               - Send message & get response
DELETE /api/v1/chat/sessions/{id}         - Delete session
```

---

## 🎯 Next Steps

1. **Phase 1:** Implement basic endpoints (2-3 days)
2. **Phase 2:** Add AI integration (1-2 days)
3. **Phase 3:** Add streaming support (1 day)
4. **Phase 4:** Add RAG with study materials (3-4 days)

---

## 💡 Recommendations

**For Your Use Case:**

1. **Start with Groq API:**
   - Free tier is generous
   - Extremely fast responses
   - No infrastructure needed
   - Easy to implement

2. **Later Add Ollama:**
   - For offline capability
   - As fallback when Groq quota reached
   - For testing without API costs

3. **Avoid Google Colab:**
   - Not suitable for production
   - Session timeouts are problematic
   - Complex tunnel setup

**Architecture:**
```
Frontend → Backend API → Groq API (primary)
                      ↘ Ollama (fallback/offline)
```

---

**Ready to start? Let's implement Phase 1!** 🚀
