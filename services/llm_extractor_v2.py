"""
LLM Extractor Service V2 - KG-RAG Corrected Version
Enforces syllabus-faithful extraction with atomic concepts and canonical naming
"""
import json
import re
import logging
from typing import Optional, List, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)


def to_canonical_id(text: str, prefix: str = "") -> str:
    """
    Convert text to canonical snake_case ID
    
    Rules:
    - snake_case
    - lowercase
    - no special characters
    - singular form
    - optional prefix for domain
    """
    # Remove special characters, keep alphanumeric and spaces
    clean = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    # Convert to lowercase and replace spaces with underscores
    snake = clean.lower().strip().replace(' ', '_')
    # Remove consecutive underscores
    snake = re.sub(r'_+', '_', snake)
    # Remove trailing/leading underscores
    snake = snake.strip('_')
    
    if prefix:
        return f"{prefix}_{snake}"
    return snake


def split_compound_concepts(text: str) -> List[str]:
    """
    Split compound concepts into atomic concepts
    
    Examples:
    - "DFS and BFS" → ["DFS", "BFS"]
    - "Insertion, Deletion, Searching" → ["Insertion", "Deletion", "Searching"]
    - "Stacks & Queues" → ["Stacks", "Queues"]
    """
    # Split by common delimiters
    delimiters = [' and ', ' & ', ', ', ' / ', ' or ']
    
    concepts = [text]
    for delimiter in delimiters:
        new_concepts = []
        for concept in concepts:
            if delimiter.lower() in concept.lower():
                # Case-insensitive split
                parts = re.split(re.escape(delimiter), concept, flags=re.IGNORECASE)
                new_concepts.extend([p.strip() for p in parts if p.strip()])
            else:
                new_concepts.append(concept)
        concepts = new_concepts
    
    return concepts


class LLMExtractorV2:
    """
    KG-RAG Corrected LLM Extractor
    
    Key Improvements:
    1. Enforces verbatim syllabus text extraction
    2. Splits compound concepts into atomic nodes
    3. Uses canonical naming (snake_case IDs)
    4. Extracts semantic relationships (IS_A, PREREQUISITE_OF, USES)
    5. Separates structural data (for KG) from content (for embeddings)
    """
    
    def __init__(self):
        self.openai_client = None
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize LLM clients"""
        try:
            from openai import OpenAI
            import os
            api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
            if api_key:
                self.openai_client = OpenAI(api_key=api_key)
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
        regulation: str = "2019",
        chunk_size: int = 12000
    ) -> dict:
        """
        Extract structured syllabus data with strict fidelity to source
        
        Returns:
        {
            "semester": int,
            "branch": str,
            "regulation": str,
            "subjects": [...],
            "concepts": [...],  # Atomic concepts for KG
            "relationships": [...],  # Semantic relationships
            "content_chunks": [...]  # Rich content for embeddings
        }
        """
        if len(raw_text) > chunk_size:
            return self._extract_chunked(raw_text, semester, branch, regulation, chunk_size)
        
        # Step 1: Extract raw structure (verbatim)
        raw_structure = self._extract_verbatim_structure(raw_text, semester, branch)
        
        # Step 2: Normalize and split into atomic concepts
        normalized = self._normalize_to_atomic_concepts(raw_structure)
        
        # Step 3: Extract semantic relationships
        relationships = self._extract_relationships(normalized)
        
        # Step 4: Generate rich content chunks for embeddings
        content_chunks = self._generate_content_chunks(raw_text, normalized)
        
        return {
            "semester": semester,
            "branch": branch,
            "regulation": regulation,
            "subjects": normalized["subjects"],
            "concepts": normalized["concepts"],
            "relationships": relationships,
            "content_chunks": content_chunks
        }
    
    def _build_verbatim_extraction_prompt(self, text: str, semester: int, branch: str) -> str:
        """Build prompt that enforces verbatim extraction"""
        return f"""You are a KTU syllabus parser. Extract data EXACTLY as written in the syllabus.

CRITICAL RULES:
1. Copy topic names EXACTLY as written - do NOT paraphrase or summarize
2. Include ALL topics mentioned, even if they seem repetitive
3. Keep abbreviations as-is (BST, DFS, BFS, etc.)
4. Do NOT combine or merge topics
5. Extract the EXACT hours/credits mentioned

CONTEXT:
- Semester: {semester}
- Branch: {branch}
- University: KTU (Kerala Technological University)

SYLLABUS TEXT:
{text}

Return ONLY valid JSON in this exact format:
{{
    "subjects": [
        {{
            "code": "CS201",
            "name": "EXACT subject name from syllabus",
            "credits": 4,
            "category": "PCC",
            "hours_per_week": 3,
            "modules": [
                {{
                    "number": 1,
                    "name": "EXACT module title from syllabus",
                    "hours": 9,
                    "syllabus_text": "Copy the EXACT text from syllabus for this module",
                    "topics_raw": [
                        "EXACT topic 1 as written",
                        "EXACT topic 2 as written"
                    ]
                }}
            ],
            "textbooks": ["EXACT textbook entry from syllabus"],
            "course_outcomes": ["CO1: EXACT outcome text"]
        }}
    ]
}}

IMPORTANT: Return ONLY the JSON. Copy text VERBATIM from syllabus."""
    
    def _extract_verbatim_structure(self, text: str, semester: int, branch: str) -> dict:
        """Extract structure with verbatim text"""
        prompt = self._build_verbatim_extraction_prompt(text, semester, branch)
        response = self._call_llm(prompt)
        try:
            return self._parse_json_response(response)
        except ValueError as e:
            logger.warning("Parse failed, retrying with strict JSON output: %s", e)
            retry_prompt = (
                prompt
                + "\n\nReturn ONLY raw JSON. No code fences, no markdown, no commentary."
            )
            response = self._call_llm(retry_prompt)
            return self._parse_json_response(response)
    
    def _normalize_to_atomic_concepts(self, raw_data: dict) -> dict:
        """
        Convert raw extraction to atomic concepts with canonical IDs
        
        Splits compound topics and generates proper identifiers
        """
        concepts = []
        normalized_subjects = []
        
        for subject in raw_data.get("subjects", []):
            subject_code = str(subject.get("code", "")).strip()
            subject_name = str(subject.get("name", "")).strip()
            if not subject_code or not subject_name:
                logger.warning("Skipping subject with missing code/name: %s", subject)
                continue

            subject_id = to_canonical_id(subject_name, prefix=subject_code.lower())
            
            normalized_modules = []
            
            for module in subject.get("modules", []):
                module_num = module.get("number")
                if isinstance(module_num, str):
                    module_num = module_num.strip()
                    if module_num.isdigit():
                        module_num = int(module_num)
                if not module_num:
                    logger.warning("Skipping module with missing number for subject %s", subject_code)
                    continue
                module_id = f"{subject_code.lower()}_m{module_num}"
                
                atomic_topics = []
                
                for topic_raw in module.get("topics_raw", []):
                    # Split compound concepts
                    atomic_names = split_compound_concepts(topic_raw)
                    
                    for atomic_name in atomic_names:
                        topic_id = to_canonical_id(atomic_name, prefix=module_id)
                        
                        atomic_topic = {
                            "id": topic_id,
                            "name": atomic_name.strip(),
                            "display_name": atomic_name.strip(),
                            "original_text": topic_raw,
                            "module_id": module_id,
                            "subject_code": subject_code
                        }
                        atomic_topics.append(atomic_topic)
                        
                        # Add to global concepts list
                        concepts.append({
                            "id": topic_id,
                            "type": "Topic",
                            "name": atomic_name.strip(),
                            "display_name": atomic_name.strip(),
                            "module_id": module_id,
                            "subject_code": subject_code,
                            "semester": raw_data.get("semester", 0),
                            "branch": raw_data.get("branch", "")
                        })
                
                normalized_module = {
                    "id": module_id,
                    "number": module_num,
                    "name": module.get("name", f"Module {module_num}"),
                    "hours": module.get("hours", 0),
                    "syllabus_text": module.get("syllabus_text", ""),
                    "topics": atomic_topics
                }
                normalized_modules.append(normalized_module)
            
            normalized_subject = {
                **subject,
                "id": subject_id,
                "code": subject_code,
                "name": subject_name,
                "modules": normalized_modules
            }
            normalized_subjects.append(normalized_subject)
        
        return {
            "subjects": normalized_subjects,
            "concepts": concepts
        }
    
    def _extract_relationships(self, normalized_data: dict) -> List[dict]:
        """
        Extract semantic relationships between concepts
        
        Relationship types:
        - IS_A: Type hierarchy (binary_search_tree IS_A tree)
        - PART_OF: Composition (node PART_OF linked_list)
        - PREREQUISITE_OF: Learning dependency
        - USES: Algorithm uses concept (quicksort USES partitioning)
        - RELATED_TO: General association
        """
        concepts = normalized_data.get("concepts", [])
        
        if not concepts:
            return []
        
        # Build concept list for LLM
        concept_list = "\n".join([f"- {c['id']}: {c['display_name']}" for c in concepts[:100]])
        
        prompt = f"""Analyze these academic concepts and identify semantic relationships.

CONCEPTS:
{concept_list}

RELATIONSHIP TYPES:
1. IS_A: Type/inheritance (e.g., binary_search_tree IS_A binary_tree)
2. PART_OF: Composition (e.g., node PART_OF linked_list)  
3. PREREQUISITE_OF: Must learn A before B (e.g., arrays PREREQUISITE_OF stacks)
4. USES: A uses/applies B (e.g., quicksort USES partitioning)
5. IMPLEMENTS: A implements B (e.g., adjacency_list IMPLEMENTS graph)

Return JSON array of relationships:
[
    {{"from_id": "concept_id_1", "to_id": "concept_id_2", "type": "IS_A", "confidence": 0.9}},
    {{"from_id": "concept_id_1", "to_id": "concept_id_3", "type": "PREREQUISITE_OF", "confidence": 0.8}}
]

Rules:
- Use EXACT concept IDs from the list above
- Only include high-confidence relationships (>0.7)
- IS_A goes from specific to general
- PREREQUISITE_OF goes from simpler to complex

Return ONLY the JSON array."""

        try:
            response = self._call_llm(prompt)
            relationships = self._parse_json_response(response)
            
            # Validate relationship IDs exist
            concept_ids = {c['id'] for c in concepts}
            valid_relationships = []
            
            for rel in relationships:
                if rel.get('from_id') in concept_ids and rel.get('to_id') in concept_ids:
                    valid_relationships.append(rel)
            
            return valid_relationships
        except Exception as e:
            logger.warning(f"Could not extract relationships: {e}")
            return []
    
    def _generate_content_chunks(
        self, 
        raw_text: str, 
        normalized_data: dict,
        max_chunk_tokens: int = 400,
        overlap_tokens: int = 50
    ) -> List[dict]:
        """
        Generate rich content chunks for embedding
        
        Each chunk contains:
        - Actual educational content (not just titles)
        - Clear metadata for filtering
        - chunk_type for query routing
        """
        chunks = []
        
        for subject in normalized_data.get("subjects", []):
            subject_code = subject["code"]
            subject_name = subject["name"]
            
            for module in subject.get("modules", []):
                module_id = module["id"]
                module_name = module.get("name", f"Module {module['number']}")
                syllabus_text = module.get("syllabus_text", "")
                
                # Chunk 1: Module overview (definition type)
                if syllabus_text:
                    overview_chunk = {
                        "chunk_id": f"{module_id}_overview",
                        "chunk_type": "syllabus_content",
                        "content": f"""Subject: {subject_name} ({subject_code})
Module {module['number']}: {module_name}

Syllabus Content:
{syllabus_text}""",
                        "metadata": {
                            "subject_code": subject_code,
                            "subject_name": subject_name,
                            "module_id": module_id,
                            "module_number": module["number"],
                            "module_name": module_name,
                            "chunk_type": "syllabus_content",
                            "hours": module.get("hours", 0)
                        }
                    }
                    chunks.append(overview_chunk)
                
                # Chunk 2: Topics list (for topic-based search)
                topics = module.get("topics", [])
                if topics:
                    topic_names = [t["display_name"] for t in topics]
                    topics_chunk = {
                        "chunk_id": f"{module_id}_topics",
                        "chunk_type": "topic_list",
                        "content": f"""Subject: {subject_name} ({subject_code})
Module {module['number']}: {module_name}

Topics covered in this module:
{chr(10).join(f'- {name}' for name in topic_names)}

These topics are part of the {subject_name} curriculum for KTU students.""",
                        "metadata": {
                            "subject_code": subject_code,
                            "subject_name": subject_name,
                            "module_id": module_id,
                            "module_number": module["number"],
                            "module_name": module_name,
                            "chunk_type": "topic_list",
                            "topic_count": len(topics),
                            "topic_ids": [t["id"] for t in topics]
                        }
                    }
                    chunks.append(topics_chunk)
                
                # Chunk 3: Individual topic chunks (for specific queries)
                for topic in topics:
                    topic_chunk = {
                        "chunk_id": f"{topic['id']}_detail",
                        "chunk_type": "topic_detail",
                        "content": f"""Subject: {subject_name} ({subject_code})
Module: {module_name}
Topic: {topic['display_name']}

This topic covers {topic['display_name']} as part of the {module_name} module in {subject_name}.
Original syllabus reference: {topic.get('original_text', topic['display_name'])}""",
                        "metadata": {
                            "subject_code": subject_code,
                            "subject_name": subject_name,
                            "module_id": module_id,
                            "module_number": module["number"],
                            "module_name": module_name,
                            "topic_id": topic["id"],
                            "topic_name": topic["display_name"],
                            "chunk_type": "topic_detail"
                        }
                    }
                    chunks.append(topic_chunk)
            
            # Subject-level chunks
            if subject.get("course_outcomes"):
                co_chunk = {
                    "chunk_id": f"{subject_code.lower()}_outcomes",
                    "chunk_type": "course_outcomes",
                    "content": f"""Subject: {subject_name} ({subject_code})
Credits: {subject.get('credits', 0)}

Course Outcomes:
{chr(10).join(subject['course_outcomes'])}""",
                    "metadata": {
                        "subject_code": subject_code,
                        "subject_name": subject_name,
                        "chunk_type": "course_outcomes"
                    }
                }
                chunks.append(co_chunk)
            
            if subject.get("textbooks"):
                textbook_chunk = {
                    "chunk_id": f"{subject_code.lower()}_textbooks",
                    "chunk_type": "references",
                    "content": f"""Subject: {subject_name} ({subject_code})

Recommended Textbooks and References:
{chr(10).join(f'- {tb}' for tb in subject['textbooks'])}""",
                    "metadata": {
                        "subject_code": subject_code,
                        "subject_name": subject_name,
                        "chunk_type": "references"
                    }
                }
                chunks.append(textbook_chunk)
        
        return chunks
    
    def _call_llm(self, prompt: str, model: Optional[str] = None) -> str:
        """Call LLM with the prompt"""
        if self.openai_client:
            try:
                response = self.openai_client.chat.completions.create(
                    model=model or "gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a precise academic data extraction assistant. Extract information EXACTLY as written in source documents. Always return valid JSON."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.05,
                    max_tokens=8000
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.error(f"OpenAI API error: {e}")
                raise
        
        raise RuntimeError("No LLM client available")
    
    def _parse_json_response(self, response_text: str) -> Any:
        """Parse JSON from LLM response"""
        cleaned = response_text.strip()
        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*```$', '', cleaned)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        
        patterns = [
            r'```json\s*([\s\S]*?)\s*```',
            r'```\s*([\s\S]*?)\s*```',
            r'\[[\s\S]*\]',
            r'\{[\s\S]*\}'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, response_text)
            if match:
                try:
                    json_str = match.group(1) if '```' in pattern else match.group(0)
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    continue

        # Fallback: best-effort slice from first opener to last closer
        start_obj = cleaned.find("{")
        start_arr = cleaned.find("[")
        if start_obj != -1 or start_arr != -1:
            if start_obj == -1 or (start_arr != -1 and start_arr < start_obj):
                end = cleaned.rfind("]")
                start = start_arr
            else:
                end = cleaned.rfind("}")
                start = start_obj
            if end > start:
                try:
                    return json.loads(cleaned[start:end + 1])
                except json.JSONDecodeError:
                    pass
        
        raise ValueError(f"Could not parse JSON from response: {response_text[:500]}...")
    
    def _extract_chunked(
        self, 
        raw_text: str, 
        semester: int, 
        branch: str,
        regulation: str,
        chunk_size: int
    ) -> dict:
        """Process large text in chunks"""
        chunks = [raw_text[i:i + chunk_size] for i in range(0, len(raw_text), chunk_size - 1000)]
        
        all_subjects = []
        all_concepts = []
        all_relationships = []
        all_content_chunks = []
        seen_codes = set()
        
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i + 1}/{len(chunks)}")
            try:
                raw_structure = self._extract_verbatim_structure(chunk, semester, branch)
                normalized = self._normalize_to_atomic_concepts(raw_structure)
                
                for subject in normalized.get("subjects", []):
                    if subject["code"] not in seen_codes:
                        all_subjects.append(subject)
                        seen_codes.add(subject["code"])
                    else:
                        # Merge modules
                        existing = next(s for s in all_subjects if s["code"] == subject["code"])
                        existing_modules = {m["number"] for m in existing.get("modules", [])}
                        for module in subject.get("modules", []):
                            if module["number"] not in existing_modules:
                                existing.setdefault("modules", []).append(module)
                
                all_concepts.extend(normalized.get("concepts", []))
                
            except Exception as e:
                logger.warning(f"Error processing chunk {i + 1}: {e}")
                continue
        
        # Extract relationships from all concepts
        if all_concepts:
            all_relationships = self._extract_relationships({"concepts": all_concepts})
        
        # Generate content chunks
        all_content_chunks = self._generate_content_chunks(
            raw_text, 
            {"subjects": all_subjects, "concepts": all_concepts}
        )
        
        return {
            "semester": semester,
            "branch": branch,
            "regulation": regulation,
            "subjects": all_subjects,
            "concepts": all_concepts,
            "relationships": all_relationships,
            "content_chunks": all_content_chunks
        }


# Global instance
llm_extractor = LLMExtractorV2()
