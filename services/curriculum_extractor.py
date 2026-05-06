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
            logger.info(f"[EXTRACTOR] Starting extraction from {pdf_path}")
            logger.info(f"[EXTRACTOR] Branch: {branch}, Regulation: {regulation}")
            
            # Step 1: Extract text from PDF
            logger.info("[EXTRACTOR] Step 1: Extracting text from PDF")
            raw_text = pdf_processor.extract_text(pdf_path)
            logger.info(f"[EXTRACTOR] Extracted {len(raw_text)} characters from PDF")
            
            if not raw_text or len(raw_text) < 100:
                logger.error("[EXTRACTOR] PDF text too short or empty")
                result["errors"].append("PDF contains no readable text")
                return result
            
            # Step 2: Use LLM to parse curriculum structure
            logger.info("[EXTRACTOR] Step 2: Parsing with LLM")
            mappings = self._extract_mappings_with_llm(raw_text, branch, regulation)
            logger.info(f"[EXTRACTOR] LLM returned {len(mappings)} mappings")
            
            result["mappings"] = mappings
            result["success"] = len(mappings) > 0
            
            logger.info(f"[EXTRACTOR] Extraction complete: success={result['success']}, mappings={len(mappings)}")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[EXTRACTOR] Extraction failed: {type(e).__name__}: {error_msg}", exc_info=True)
            result["errors"].append(error_msg)
        
        return result
    
    def _extract_mappings_with_llm(self, raw_text: str, branch: str, regulation: str) -> List[Dict[str, Any]]:
        """Use LLM to parse curriculum and extract elective group mappings"""
        
        logger.info(f"[LLM_EXTRACT] Starting LLM extraction (text length: {len(raw_text)} chars)")
        
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
            logger.info("[LLM_EXTRACT] Calling LLM...")
            response = llm_extractor._call_llm(prompt)
            logger.info(f"[LLM_EXTRACT] LLM response received (length: {len(response)} chars)")
            
            mappings = llm_extractor._parse_json_response(response)
            logger.info(f"[LLM_EXTRACT] Parsed JSON: type={type(mappings).__name__}")
            
            if not isinstance(mappings, list):
                logger.warning(f"[LLM_EXTRACT] Response was {type(mappings).__name__}, not list. Wrapping...")
                mappings = [mappings] if isinstance(mappings, dict) else []
            
            logger.info(f"[LLM_EXTRACT] Processing {len(mappings)} mappings for validation")
            
            # Validate and clean mappings
            validated = []
            for i, m in enumerate(mappings):
                if isinstance(m, dict) and m.get("subject_code") and m.get("program_elective"):
                    validated.append({
                        "subject_code": str(m.get("subject_code")).strip().upper(),
                        "subject_name": str(m.get("subject_name", "")).strip(),
                        "program_elective": str(m.get("program_elective")).strip(),
                        "semester": int(m.get("semester", 0)) if m.get("semester") else None,
                        "credits": int(m.get("credits", 0)) if m.get("credits") else None,
                    })
            
            logger.info(f"[LLM_EXTRACT] Validated {len(validated)} mappings from LLM response")
            return validated
            
        except Exception as e:
            logger.error(f"[LLM_EXTRACT] LLM extraction failed: {type(e).__name__}: {str(e)}", exc_info=True)
            return []
    
    def populate_elective_mappings(self, admin_client, mappings: List[Dict[str, Any]], branch: str, regulation: str) -> Dict[str, Any]:
        """
        Insert elective mappings into syllabus_elective_mappings table.
        
        Returns stats on inserted/updated rows.
        """
        logger.info(f"[DB_POPULATE] Starting population: {len(mappings)} mappings, branch={branch}, regulation={regulation}")
        
        stats = {
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "errors": []
        }
        
        if not mappings:
            logger.warning("[DB_POPULATE] No mappings provided")
            return stats
        
        try:
            # Prepare rows for upsert
            logger.info("[DB_POPULATE] Preparing rows for upsert")
            rows = []
            for mapping in mappings:
                if not mapping.get("subject_code"):
                    logger.debug("[DB_POPULATE] Skipping mapping with no subject_code")
                    stats["skipped"] += 1
                    continue
                
                rows.append({
                    "subject_code": mapping["subject_code"],
                    "program_elective": mapping.get("program_elective", ""),
                    "branch": branch,
                    "regulation": regulation,
                })
            
            logger.info(f"[DB_POPULATE] Prepared {len(rows)} rows for upsert (skipped: {stats['skipped']})")
            
            if rows:
                logger.info(f"[DB_POPULATE] Executing upsert for {len(rows)} rows")
                # Upsert all mappings
                result = (
                    admin_client.table("syllabus_elective_mappings")
                    .upsert(rows, on_conflict="subject_code,regulation")
                    .execute()
                )
                
                logger.info(f"[DB_POPULATE] Upsert result: {len(result.data) if result.data else 0} rows affected")
                stats["inserted"] = len(result.data) if result.data else 0
                logger.info(f"[DB_POPULATE] Successfully upserted {stats['inserted']} elective mappings")
            else:
                logger.warning("[DB_POPULATE] No valid rows to upsert after filtering")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[DB_POPULATE] Failed to populate elective mappings: {type(e).__name__}: {error_msg}", exc_info=True)
            stats["errors"].append(error_msg)
        
        return stats


# Global instance
curriculum_extractor = CurriculumExtractor()
