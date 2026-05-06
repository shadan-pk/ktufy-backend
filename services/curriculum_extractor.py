"""
Curriculum Extractor Service
Extracts elective mappings from KTU curriculum PDFs using LLM.
"""
import logging
from typing import List, Dict, Any, Optional
from services.pdf_processor import pdf_processor
from services.llm_extractor_v2 import llm_extractor

logger = logging.getLogger(__name__)


class CurriculumExtractor:
    """Extract elective mappings from curriculum PDF"""
    
    def extract_elective_mappings_from_pdf(self, pdf_path: str, branch: str = "CSE", regulation: str = "2019") -> Dict[str, Any]:
        """
        Extract subject → elective group mappings from a curriculum PDF.
        
        Returns:
        {
            "branch": "CSE",
            "regulation": "2019",
            "success": True,
            "mappings": [
                {"subject_code": "CST3E1", "subject_name": "Deep Learning", "program_elective": "PEC1", "semester": 6},
                {"subject_code": "CST3E2", "subject_name": "NLP", "program_elective": "PEC1", "semester": 6},
                ...
            ],
            "errors": []
        }
        """
        result = {
            "branch": branch,
            "regulation": regulation,
            "success": False,
            "mappings": [],
            "errors": []
        }
        
        try:
            logger.info(f"Extracting curriculum from {pdf_path} for {branch} regulation {regulation}")
            
            # Step 1: Extract text from PDF
            raw_text = pdf_processor.extract_text(pdf_path)
            logger.info(f"Extracted {len(raw_text)} characters from PDF")
            
            # Step 2: Use LLM to parse curriculum structure
            mappings = self._extract_mappings_with_llm(raw_text, branch, regulation)
            
            result["mappings"] = mappings
            result["success"] = len(mappings) > 0
            
            logger.info(f"Extracted {len(mappings)} elective mappings from curriculum")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to extract curriculum: {error_msg}")
            result["errors"].append(error_msg)
        
        return result
    
    def _extract_mappings_with_llm(self, raw_text: str, branch: str, regulation: str) -> List[Dict[str, Any]]:
        """Use LLM to parse curriculum and extract elective group mappings"""
        
        prompt = f"""You are a KTU curriculum parser. Extract all subject → elective group mappings from the provided curriculum text.

BRANCH: {branch}
REGULATION: {regulation}

CURRICULUM TEXT:
{raw_text[:8000]}

Extract every subject and which program elective group it belongs to:
- PEC1, PEC2, PEC3, PEC4, PEC5 (Program Electives - 5 categories)
- OEC (Open Electives)
- MINOR (Minor courses)
- HONOURS (Honours courses)
- Other specialty groups

Return ONLY valid JSON array:
[
    {{
        "subject_code": "CST3E1",
        "subject_name": "Deep Learning Applications",
        "program_elective": "PEC1",
        "semester": 6,
        "credits": 3
    }},
    {{
        "subject_code": "CST3E2",
        "subject_name": "Natural Language Processing",
        "program_elective": "PEC1",
        "semester": 6,
        "credits": 3
    }},
    ...
]

CRITICAL RULES:
1. Include ALL subjects with their subject codes and elective categories
2. Extract semester information if available
3. For each subject, determine which elective group (PEC1-5, OEC, etc.) it belongs to
4. Use consistent subject codes (match the exact code from curriculum)
5. If a subject belongs to multiple groups, create separate entries

Return ONLY the JSON array. No explanation, no markdown."""

        try:
            response = llm_extractor._call_llm(prompt)
            mappings = llm_extractor._parse_json_response(response)
            
            if not isinstance(mappings, list):
                logger.warning("LLM response was not a list, wrapping")
                mappings = [mappings] if isinstance(mappings, dict) else []
            
            # Validate and clean mappings
            validated = []
            for m in mappings:
                if isinstance(m, dict) and m.get("subject_code") and m.get("program_elective"):
                    validated.append({
                        "subject_code": str(m.get("subject_code")).strip().upper(),
                        "subject_name": str(m.get("subject_name", "")).strip(),
                        "program_elective": str(m.get("program_elective")).strip(),
                        "semester": int(m.get("semester", 0)) if m.get("semester") else None,
                        "credits": int(m.get("credits", 0)) if m.get("credits") else None,
                    })
            
            logger.info(f"Validated {len(validated)} mappings from LLM response")
            return validated
            
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return []
    
    def populate_elective_mappings(self, admin_client, mappings: List[Dict[str, Any]], branch: str, regulation: str) -> Dict[str, Any]:
        """
        Insert elective mappings into syllabus_elective_mappings table.
        
        Returns stats on inserted/updated rows.
        """
        stats = {
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "errors": []
        }
        
        if not mappings:
            return stats
        
        try:
            # Prepare rows for upsert
            rows = []
            for mapping in mappings:
                if not mapping.get("subject_code"):
                    stats["skipped"] += 1
                    continue
                
                rows.append({
                    "subject_code": mapping["subject_code"],
                    "program_elective": mapping.get("program_elective", ""),
                    "branch": branch,
                    "regulation": regulation,
                })
            
            if rows:
                # Upsert all mappings
                result = (
                    admin_client.table("syllabus_elective_mappings")
                    .upsert(rows, on_conflict="subject_code,regulation")
                    .execute()
                )
                
                stats["inserted"] = len(result.data) if result.data else 0
                logger.info(f"Upserted {len(result.data)} elective mappings")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to populate elective mappings: {error_msg}")
            stats["errors"].append(error_msg)
        
        return stats


# Global instance
curriculum_extractor = CurriculumExtractor()
