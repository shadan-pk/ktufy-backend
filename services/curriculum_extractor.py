"""
Curriculum Extractor Service
Extracts elective mappings from KTU curriculum PDFs using LLM.
"""
import logging
import re
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
            
            # Step 1.5: Preprocess to extract only PROGRAM ELECTIVE sections if text is very large
            # This focuses the LLM on the relevant sections
            processed_text = self._preprocess_curriculum_text(raw_text)
            logger.info(f"[EXTRACTOR] Preprocessed text: {len(processed_text)} characters (from {len(raw_text)})")
            
            # Step 2: Use LLM to parse curriculum structure
            logger.info("[EXTRACTOR] Step 2: Parsing with LLM")
            mappings = self._extract_mappings_with_llm(processed_text, branch, regulation, pdf_path)
            logger.info(f"[EXTRACTOR] LLM returned {len(mappings)} mappings")
            
            result["mappings"] = mappings
            result["success"] = len(mappings) > 0
            
            logger.info(f"[EXTRACTOR] Extraction complete: success={result['success']}, mappings={len(mappings)}")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[EXTRACTOR] Extraction failed: {type(e).__name__}: {error_msg}", exc_info=True)
            result["errors"].append(error_msg)
        
        return result
    
    def _preprocess_curriculum_text(self, raw_text: str) -> str:
        """
        Preprocess curriculum text to keep the most relevant parts.
        If text is very large (>50KB), extract sections around PROGRAM ELECTIVE
        and OPEN ELECTIVE to help the LLM focus on the right content.
        Otherwise, return the full text.
        """
        if len(raw_text) < 50000:
            # Text is manageable size, use full text
            return raw_text
        
        logger.info(f"[PREPROCESS] PDF is large ({len(raw_text)} chars), extracting relevant sections")
        
        # Extract sections containing elective headings.
        lines = raw_text.split('\n')
        relevant_lines = []
        context_window = 100  # Keep 100 lines before/after each PROGRAM ELECTIVE
        
        pec_indices = []
        for i, line in enumerate(lines):
            upper_line = line.upper()
            if "PROGRAM ELECTIVE" in upper_line or "OPEN ELECTIVE" in upper_line or upper_line.startswith("OEC"):
                pec_indices.append(i)
        
        logger.info(f"[PREPROCESS] Found {len(pec_indices)} elective sections")
        
        # Include context around each PROGRAM ELECTIVE section
        indices_to_include = set()
        for idx in pec_indices:
            start = max(0, idx - context_window)
            end = min(len(lines), idx + context_window)
            indices_to_include.update(range(start, end))
        
        # Also include SEMESTER headers
        for i, line in enumerate(lines):
            if line.strip().startswith("SEMESTER"):
                start = max(0, i - 5)
                end = min(len(lines), i + context_window)
                indices_to_include.update(range(start, end))
        
        # Sort and extract
        relevant_lines = [lines[i] for i in sorted(indices_to_include)]
        processed = '\n'.join(relevant_lines)
        
        logger.info(f"[PREPROCESS] Extracted {len(processed)} chars ({len(relevant_lines)} lines) from {len(lines)} total lines")
        
        return processed
    
    def _extract_mappings_with_llm(self, raw_text: str, branch: str, regulation: str, pdf_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Use LLM to parse curriculum and extract elective group mappings
        
        The curriculum PDF structure:
        - Each SEMESTER X table contains courses with SLOT (A, B, C, D, E, F, S, T, R/M, H)
        - SLOT courses = PCC (core courses) - SKIP THESE
        - Below each semester, there are PROGRAM ELECTIVE I/II/III/IV/V sections
        - Some semesters also contain OPEN ELECTIVE sections, usually labeled OPEN ELECTIVE or OEC
        - PROGRAM ELECTIVE I under Semester 6 = PEC1 for Semester 6
        - PROGRAM ELECTIVE II under Semester 7 = PEC2 for Semester 7
        - OPEN ELECTIVE sections should be mapped to OEC
        - Extract only the PROGRAM ELECTIVE courses, not the SLOT courses
        """
        
        logger.info(f"[LLM_EXTRACT] Starting LLM extraction (text length: {len(raw_text)} chars)")
        
        prompt = f"""You are a KTU curriculum parser. Extract ALL program elective course mappings from the provided curriculum.

CRITICAL STRUCTURE UNDERSTANDING:
Each semester has two parts:
1. REGULAR COURSES TABLE with columns: SLOT | COURSE NO. | COURSES | ... 
   - These have SLOT values (A, B, C, D, E, F, S, T, R/M, H)
   - These are PCC (core) courses - IGNORE THESE
2. PROGRAM ELECTIVE I/II/III/IV/V sections below the semester table
   - These are the ELECTIVE OPTIONS for that semester
   - PROGRAM ELECTIVE I in Sem 6 = PEC1 for Sem 6
   - PROGRAM ELECTIVE II in Sem 7 = PEC2 for Sem 7
   - PROGRAM ELECTIVE III in Sem 7 = PEC3 for Sem 7
   - PROGRAM ELECTIVE IV in Sem 8 = PEC4 for Sem 8
   - PROGRAM ELECTIVE V in Sem 8 = PEC5 for Sem 8
3. OPEN ELECTIVE sections
    - These may be labeled OPEN ELECTIVE, OEC, or OPEN ELECTIVE-I/II
    - Extract all courses listed there and set program_elective to OEC

EXTRACTION INSTRUCTIONS:
1. Find each SEMESTER (1-8) section
2. For each semester, find PROGRAM ELECTIVE I/II/III/IV/V subsections
3. For OPEN ELECTIVE sections, extract ALL courses listed as options and mark them as OEC
4. For each program elective section, extract ALL courses listed as options
5. Map to PEC group based on:
   - If under "PROGRAM ELECTIVE I" → PEC1
   - If under "PROGRAM ELECTIVE II" → PEC2
   - If under "PROGRAM ELECTIVE III" → PEC3
   - If under "PROGRAM ELECTIVE IV" → PEC4
   - If under "PROGRAM ELECTIVE V" → PEC5
6. DO NOT extract courses from the regular SEMESTER table (those have SLOT letters)

BRANCH: {branch}
REGULATION: {regulation}

FULL CURRICULUM TEXT:
{raw_text}

Return ONLY a valid JSON array with NO markdown or code fences:
[
    {{
        "subject_code": "CST312",
        "subject_name": "FOUNDATIONS OF MACHINE LEARNING",
        "program_elective": "PEC1",
        "semester": 6,
        "credits": 3
    }},
    {{
        "subject_code": "CST322",
        "subject_name": "DATA ANALYTICS",
        "program_elective": "PEC1",
        "semester": 6,
        "credits": 3
    }},
    {{
        "subject_code": "CST342",
        "subject_name": "AUTOMATED VERIFICATION",
        "program_elective": "PEC1",
        "semester": 6,
        "credits": 3
    }}
]

VALIDATION RULES:
1. Subject code must NOT be empty
2. Program elective must be one of: PEC1, PEC2, PEC3, PEC4, PEC5, OEC, MINOR, HONOURS
3. Semester must be 1-8
4. Do NOT include any PCC courses (those are in the main SEMESTER table with SLOT)
5. Only include courses from PROGRAM ELECTIVE sections or OPEN ELECTIVE sections

IMPORTANT: Extract courses from ALL PROGRAM ELECTIVE sections across all semesters. Be thorough."""

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
            
            # Valid program elective values (skip PCC courses)
            valid_pec_values = {"PEC1", "PEC2", "PEC3", "PEC4", "PEC5", "OEC", "MINOR", "HONOURS"}
            
            # Validate and clean mappings
            validated = []
            skipped_count = 0
            
            for i, m in enumerate(mappings):
                if not isinstance(m, dict):
                    skipped_count += 1
                    continue
                
                subject_code = str(m.get("subject_code", "")).strip().upper()
                program_elective = str(m.get("program_elective", "")).strip().upper()
                if program_elective in {"OPEN ELECTIVE", "OPEN_ELECTIVE", "OPEN-ELECTIVE", "OEC", "OE"}:
                    program_elective = "OEC"
                
                # Skip if missing required fields
                if not subject_code or not program_elective:
                    logger.debug(f"[LLM_EXTRACT] Skipping {i}: missing code or elective")
                    skipped_count += 1
                    continue
                
                # Skip if not a valid elective (i.e., it's PCC)
                if program_elective not in valid_pec_values:
                    logger.debug(f"[LLM_EXTRACT] Skipping {subject_code}: invalid program_elective '{program_elective}' (appears to be PCC)")
                    skipped_count += 1
                    continue
                
                # Valid elective - add to validated list
                validated.append({
                    "subject_code": subject_code,
                    "subject_name": str(m.get("subject_name", "")).strip(),
                    "program_elective": program_elective,
                    "semester": int(m.get("semester", 0)) if m.get("semester") else None,
                    "credits": int(m.get("credits", 0)) if m.get("credits") else None,
                })
            
            logger.info(f"[LLM_EXTRACT] Validated {len(validated)} mappings (skipped {skipped_count} PCC or invalid courses)")
            
            if validated:
                logger.info(f"[LLM_EXTRACT] Sample validated courses: {[v['subject_code'] + '→' + v['program_elective'] for v in validated[:5]]}")

            # Fallback: supplement with table-based extraction ONLY if LLM found nothing
            # or very few results, as the table extractor can be noisy.
            try:
                if pdf_path and len(validated) < 10:
                    logger.info(f"[LLM_EXTRACT] LLM found only {len(validated)} mappings. Running table fallback...")
                    table_mappings = self._extract_from_tables(pdf_path)
                    logger.info(f"[TABLE_EXTRACT] Found {len(table_mappings)} mappings from tables")

                    # Merge table mappings if they are not already present
                    existing_codes = {m['subject_code'] for m in validated}
                    for tm in table_mappings:
                        if tm['subject_code'] not in existing_codes and tm['program_elective'] in valid_pec_values:
                            validated.append(tm)
                            existing_codes.add(tm['subject_code'])

                    if table_mappings:
                        logger.info(f"[LLM_EXTRACT] After table supplement validated count: {len(validated)}")
                else:
                    logger.info(f"[LLM_EXTRACT] LLM found {len(validated)} mappings. Skipping table fallback to avoid duplicates.")
            except Exception as e:
                logger.warning(f"[TABLE_EXTRACT] Table extraction failed: {e}")

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
                logger.info(f"[DB_POPULATE] Executing safe upsert for {len(rows)} rows (per-row checks)")
                for r in rows:
                    try:
                        # Check existing mapping
                        existing = (
                            admin_client.table("syllabus_elective_mappings")
                            .select("id,program_elective")
                            .eq("subject_code", r["subject_code"]) 
                            .eq("regulation", r["regulation"]) 
                            .execute()
                        )
                        existing_row = existing.data[0] if existing and existing.data else None

                        if existing_row:
                            # If program_elective is same, skip
                            if str(existing_row.get("program_elective", "")).upper() == str(r.get("program_elective", "")).upper():
                                logger.debug(f"[DB_POPULATE] Skipping upsert for {r['subject_code']} — no change")
                                stats["skipped"] += 1
                                continue
                            # Otherwise update
                            admin_client.table("syllabus_elective_mappings").update({
                                "program_elective": r.get("program_elective", "")
                            }).eq("id", existing_row["id"]).execute()
                            stats["updated"] += 1
                            logger.debug(f"[DB_POPULATE] Updated {r['subject_code']} -> {r.get('program_elective')}")
                        else:
                            # Insert new row
                            admin_client.table("syllabus_elective_mappings").insert(r).execute()
                            stats["inserted"] += 1
                            logger.debug(f"[DB_POPULATE] Inserted {r['subject_code']} -> {r.get('program_elective')}")
                    except Exception as e:
                        logger.warning(f"[DB_POPULATE] Failed to upsert {r.get('subject_code')}: {e}")
                        stats["errors"].append(str(e))
            else:
                logger.warning("[DB_POPULATE] No valid rows to upsert after filtering")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[DB_POPULATE] Failed to populate elective mappings: {type(e).__name__}: {error_msg}", exc_info=True)
            stats["errors"].append(error_msg)
        
        return stats

    def _extract_from_tables(self, pdf_path: str) -> List[Dict[str, Any]]:
        """Extract mappings from PDF tables near PROGRAM ELECTIVE or OPEN ELECTIVE headings.

        Returns list of mapping dicts: subject_code, subject_name, program_elective, semester, credits
        """
        results: List[Dict[str, Any]] = []
        # KTU Core Course Slots
        PCC_SLOTS = {"A", "B", "C", "D", "E", "F", "S", "T", "R", "M", "H", "R/M"}
        
        try:
            tables = pdf_processor.extract_tables_with_pages(pdf_path)
            for page_num, table in tables:
                # Get the page text to check context
                page_text = pdf_processor.extract_text_by_pages(pdf_path, start_page=page_num-1, end_page=page_num)
                up = page_text.upper() if page_text else ""
                
                # If page doesn't mention electives, skip all tables on it
                if "PROGRAM ELECTIVE" not in up and "OPEN ELECTIVE" not in up and "OEC" not in up:
                    continue

                # table is a list of rows; try to pull course codes from each row
                for row in table:
                    if not row or len(row) < 2:
                        continue
                        
                    # 1. Skip rows that look like PCC (Core) courses.
                    # Core tables always have a SLOT (A, B, C, D, etc.)
                    is_pcc = False
                    for cell in row:
                        if cell and str(cell).strip().upper() in PCC_SLOTS:
                            is_pcc = True
                            break
                    if is_pcc:
                        continue

                    # 2. Find subject code
                    subject_code = None
                    subject_name = None
                    for cell in row:
                        if not cell:
                            continue
                        cell_str = str(cell).strip()
                        m = re.search(r"\b([A-Z]{2,4})\s*(\d{3,4})\b", cell_str)
                        if m:
                            subject_code = (m.group(1) + m.group(2)).upper()
                            break
                    
                    if not subject_code:
                        continue

                    # 3. Find subject name (usually the next significant string)
                    names = []
                    for cell in row:
                        if not cell:
                            continue
                        s = str(cell).strip()
                        # Skip if it's the code itself or another code
                        if subject_code in s.replace(' ', ''):
                            continue
                        if re.search(r"\b([A-Z]{2,4})\s*(\d{3,4})\b", s):
                            continue
                        # Skip if it's a credit or number
                        if s.isdigit() or (s.replace('.', '').isdigit()):
                            continue
                        if len(s) > 1:
                            names.append(s)
                    subject_name = names[0] if names else ""

                    # 4. Determine elective type (much more carefully)
                    # We look for the heading most likely to be ABOVE this specific table
                    # For now, we use a simple heuristic: if PEC1 is on page, assume PEC1
                    # but we already filtered PCC courses above which was the main issue.
                    pe = None
                    if "PROGRAM ELECTIVE I" in up: pe = "PEC1"
                    elif "PROGRAM ELECTIVE II" in up: pe = "PEC2"
                    elif "PROGRAM ELECTIVE III" in up: pe = "PEC3"
                    elif "PROGRAM ELECTIVE IV" in up: pe = "PEC4"
                    elif "PROGRAM ELECTIVE V" in up: pe = "PEC5"
                    elif "OPEN ELECTIVE" in up or "OEC" in up: pe = "OEC"

                    # 5. Semester
                    sem = None
                    m2 = re.search(r"SEMESTER\s*(\d)", up)
                    if m2:
                        sem = int(m2.group(1))

                    results.append({
                        "subject_code": subject_code,
                        "subject_name": subject_name,
                        "program_elective": pe or "",
                        "semester": sem,
                        "credits": None,
                    })
        except Exception as e:
            logger.warning(f"[TABLE_EXTRACT] Error extracting tables: {e}")

        return results


# Global instance
curriculum_extractor = CurriculumExtractor()
