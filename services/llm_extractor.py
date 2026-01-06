"""
LLM Extractor Service
Uses Groq/OpenAI to extract structured syllabus data from raw text
"""
import json
import re
import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)


class LLMExtractor:
    """
    LLM-based structured data extraction from syllabus text
    """
    
    def __init__(self):
        self.groq_client = None
        self.openai_client = None
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize LLM clients"""
        # Try Groq first
        try:
            from groq import Groq
            import os
            api_key = os.getenv("GROQ_API_KEY")
            if api_key:
                self.groq_client = Groq(api_key=api_key)
                logger.info("Groq client initialized")
        except ImportError:
            logger.warning("Groq not installed")
        except Exception as e:
            logger.warning(f"Could not initialize Groq: {e}")
        
        # Try OpenAI as fallback
        try:
            from openai import OpenAI
            if settings.openai_api_key:
                self.openai_client = OpenAI(api_key=settings.openai_api_key)
                logger.info("OpenAI client initialized")
        except ImportError:
            logger.warning("OpenAI not installed")
        except Exception as e:
            logger.warning(f"Could not initialize OpenAI: {e}")
    
    def extract_syllabus_structure(
        self, 
        raw_text: str, 
        semester: int, 
        branch: str,
        chunk_size: int = 8000
    ) -> dict:
        """
        Extract structured syllabus data from raw text using LLM
        
        Args:
            raw_text: Raw text extracted from PDF
            semester: Semester number
            branch: Branch code
            chunk_size: Maximum characters per LLM call
            
        Returns:
            Structured syllabus data as dictionary
        """
        # If text is too long, process in chunks
        if len(raw_text) > chunk_size:
            return self._extract_chunked(raw_text, semester, branch, chunk_size)
        
        prompt = self._build_extraction_prompt(raw_text, semester, branch)
        
        response_text = self._call_llm(prompt)
        
        # Parse JSON from response
        return self._parse_json_response(response_text)
    
    def _build_extraction_prompt(self, text: str, semester: int, branch: str) -> str:
        """Build the extraction prompt"""
        return f"""You are a KTU (Kerala Technological University) syllabus parser. 
Extract structured data from the following syllabus text.

CONTEXT:
- Semester: {semester}
- Branch: {branch}
- University: KTU (Kerala Technological University)

SYLLABUS TEXT:
{text}

INSTRUCTIONS:
1. Extract ALL subjects mentioned in the syllabus
2. For each subject, extract:
   - Subject code (e.g., CS201, MA201)
   - Subject name
   - Credits
   - Category (PCC, BSC, ESC, OEC, etc.)
3. For each module (usually 5 per subject):
   - Module number
   - Module name/title
   - Approximate hours
   - All topics covered
4. Extract keywords for each topic that would help in searching

Return ONLY valid JSON in this exact format (no markdown, no explanation):
{{
    "semester": {semester},
    "branch": "{branch}",
    "subjects": [
        {{
            "code": "CS201",
            "name": "Data Structures",
            "credits": 4,
            "category": "PCC",
            "modules": [
                {{
                    "number": 1,
                    "name": "Introduction to Data Structures",
                    "hours": 9,
                    "topics": [
                        {{
                            "name": "Arrays",
                            "description": "Introduction to arrays, types, operations",
                            "keywords": ["array", "index", "element", "traversal"]
                        }}
                    ]
                }}
            ],
            "textbooks": ["Book Title - Author"],
            "objectives": ["Learning objective 1"]
        }}
    ]
}}

IMPORTANT: Return ONLY the JSON object, no other text before or after."""
    
    def _call_llm(self, prompt: str, model: Optional[str] = None) -> str:
        """
        Call LLM (Groq or OpenAI) with the prompt
        
        Args:
            prompt: The prompt to send
            model: Optional model override
            
        Returns:
            LLM response text
        """
        # Try Groq first
        if self.groq_client:
            try:
                response = self.groq_client.chat.completions.create(
                    model=model or "llama-3.3-70b-versatile",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a precise data extraction assistant. Always return valid JSON."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=4096
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.error(f"Groq API error: {e}")
                if not self.openai_client:
                    raise
        
        # Fallback to OpenAI
        if self.openai_client:
            try:
                response = self.openai_client.chat.completions.create(
                    model=model or "gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a precise data extraction assistant. Always return valid JSON."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=4096
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.error(f"OpenAI API error: {e}")
                raise
        
        raise RuntimeError("No LLM client available. Configure GROQ_API_KEY or OPENAI_API_KEY")
    
    def _parse_json_response(self, response_text: str) -> dict:
        """
        Parse JSON from LLM response
        
        Args:
            response_text: Raw response from LLM
            
        Returns:
            Parsed JSON as dictionary
        """
        # Try direct JSON parsing first
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from markdown code blocks
        json_patterns = [
            r'```json\s*([\s\S]*?)\s*```',
            r'```\s*([\s\S]*?)\s*```',
            r'\{[\s\S]*\}'
        ]
        
        for pattern in json_patterns:
            match = re.search(pattern, response_text)
            if match:
                try:
                    json_str = match.group(1) if '```' in pattern else match.group(0)
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    continue
        
        logger.error(f"Could not parse JSON from response: {response_text[:500]}...")
        raise ValueError("Could not parse JSON from LLM response")
    
    def _extract_chunked(
        self, 
        raw_text: str, 
        semester: int, 
        branch: str, 
        chunk_size: int
    ) -> dict:
        """
        Process large text in chunks and merge results
        
        Args:
            raw_text: Full text
            semester: Semester number
            branch: Branch code
            chunk_size: Size of each chunk
            
        Returns:
            Merged structured data
        """
        # Split text into chunks
        chunks = [raw_text[i:i + chunk_size] for i in range(0, len(raw_text), chunk_size - 500)]
        
        all_subjects = []
        seen_codes = set()
        
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i + 1}/{len(chunks)}")
            try:
                prompt = self._build_extraction_prompt(chunk, semester, branch)
                response = self._call_llm(prompt)
                data = self._parse_json_response(response)
                
                # Merge subjects (avoid duplicates)
                for subject in data.get("subjects", []):
                    if subject["code"] not in seen_codes:
                        all_subjects.append(subject)
                        seen_codes.add(subject["code"])
                    else:
                        # Merge modules if subject already exists
                        existing = next(s for s in all_subjects if s["code"] == subject["code"])
                        existing_modules = {m["number"] for m in existing.get("modules", [])}
                        for module in subject.get("modules", []):
                            if module["number"] not in existing_modules:
                                existing.setdefault("modules", []).append(module)
            except Exception as e:
                logger.warning(f"Error processing chunk {i + 1}: {e}")
                continue
        
        return {
            "semester": semester,
            "branch": branch,
            "subjects": all_subjects
        }
    
    def generate_topic_description(self, topic_name: str, subject_name: str, module_name: str) -> str:
        """
        Generate a detailed description for a topic
        
        Args:
            topic_name: Name of the topic
            subject_name: Name of the subject
            module_name: Name of the module
            
        Returns:
            Generated description
        """
        prompt = f"""Generate a concise educational description (2-3 sentences) for this topic:
        
Topic: {topic_name}
Subject: {subject_name}
Module: {module_name}
University: KTU (Kerala Technological University)

Provide only the description, no other text."""
        
        return self._call_llm(prompt)
    
    def extract_prerequisites(self, subjects: list) -> list:
        """
        Identify prerequisite relationships between subjects
        
        Args:
            subjects: List of subject data
            
        Returns:
            List of prerequisite relationships
        """
        subject_names = [f"{s['code']}: {s['name']}" for s in subjects]
        
        prompt = f"""Given these KTU subjects, identify prerequisite relationships:

Subjects:
{chr(10).join(subject_names)}

Return JSON array of prerequisites:
[
    {{"from_code": "CS201", "to_code": "CS301", "reason": "Data structures needed for algorithms"}}
]

Return only valid JSON array, no other text."""
        
        response = self._call_llm(prompt)
        return self._parse_json_response(response)


# Global instance
llm_extractor = LLMExtractor()
