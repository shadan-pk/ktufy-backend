"""
Syllabus DB Service
Stores and retrieves structured syllabus data from Supabase (Postgres).
This is for display/browse purposes — Neo4j is used only for KG-RAG.
"""
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class SyllabusDBService:
    """
    CRUD operations for syllabus data in Supabase.
    Uses the admin client (service_role) for writes, regular client for reads.
    """

    # ─── Write Operations (called during syllabus processing) ─────────

    def _coerce_int(self, value) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            if stripped.isdigit():
                return int(stripped)
        return None

    def upsert_subject(self, admin_client, subject_data: dict, semester: int, branch: str, regulation: str = "2019") -> Optional[dict]:
        """
        Upsert a subject into syllabus_subjects.
        Stores category exactly as extracted from the syllabus PDF (PCC, PEC, OEC).
        program_elective is NOT set here — it is resolved by the frontend from
        the syllabus_elective_mappings table.
        Returns the upserted row or None on failure.
        """
        try:
            row = {
                "code": subject_data["code"],
                "name": subject_data["name"],
                "branch": branch,
                "semester": semester,
                "regulation": regulation,
                "credits": self._coerce_int(subject_data.get("credits")),
                "category": subject_data.get("category", ""),
                "hours_per_week": self._coerce_int(subject_data.get("hours_per_week")),
                "course_outcomes": subject_data.get("course_outcomes", []),
                "textbooks": subject_data.get("textbooks", []),
                "references": subject_data.get("references", []),
                "objectives": subject_data.get("objectives", []),
            }

            result = (
                admin_client.table("syllabus_subjects")
                .upsert(row, on_conflict="code,regulation")
                .execute()
            )
            return result.data[0] if result.data else None

        except Exception as e:
            logger.error(f"Failed to upsert subject {subject_data.get('code')}: {e}")
            return None

    def upsert_module(self, admin_client, module_data: dict, subject_code: str, regulation: str = "2019") -> Optional[dict]:
        """
        Upsert a module into syllabus_modules.
        Returns the upserted row (with id) or None on failure.
        """
        try:
            module_number = self._coerce_int(module_data.get("number"))
            if module_number is None:
                logger.warning("Skipping module with invalid number for %s: %s", subject_code, module_data.get("number"))
                return None

            row = {
                "subject_code": subject_code,
                "regulation": regulation,
                "module_number": module_number,
                "name": module_data.get("name", f"Module {module_data['number']}"),
                "hours": self._coerce_int(module_data.get("hours")),
                "syllabus_text": module_data.get("syllabus_text", ""),
            }

            result = (
                admin_client.table("syllabus_modules")
                .upsert(row, on_conflict="subject_code,regulation,module_number")
                .execute()
            )
            return result.data[0] if result.data else None

        except Exception as e:
            logger.error(f"Failed to upsert module {subject_code} M{module_data.get('number')}: {e}")
            return None

    def save_topics(self, admin_client, module_id: str, topics: list) -> int:
        """
        Replace all topics for a module.
        Returns number of topics saved.
        """
        try:
            # Delete existing topics for this module
            admin_client.table("syllabus_topics").delete().eq("module_id", module_id).execute()

            if not topics:
                return 0

            rows = []
            for idx, topic in enumerate(topics):
                if isinstance(topic, dict):
                    name = topic.get("name", topic.get("display_name", str(topic)))
                    description = topic.get("description", "")
                elif isinstance(topic, str):
                    name = topic
                    description = ""
                else:
                    name = str(topic)
                    description = ""

                rows.append({
                    "module_id": module_id,
                    "name": name,
                    "description": description,
                    "sort_order": idx,
                })

            if rows:
                admin_client.table("syllabus_topics").insert(rows).execute()

            return len(rows)

        except Exception as e:
            logger.error(f"Failed to save topics for module {module_id}: {e}")
            return 0

    def store_syllabus(self, admin_client, structured_data: dict, semester: int, branch: str, regulation: str = "2019") -> dict:
        """
        Store the full parsed syllabus into the database.
        Called during syllabus processing after LLM extraction.
        
        Returns stats dict.
        """
        stats = {
            "subjects_stored": 0,
            "modules_stored": 0,
            "topics_stored": 0,
            "errors": [],
        }

        for subject in structured_data.get("subjects", []):
            try:
                logger.info(f"DB store: subject {subject.get('code')} - {subject.get('name')}")
                subj_row = self.upsert_subject(admin_client, subject, semester, branch, regulation)
                if not subj_row:
                    stats["errors"].append(f"Failed to store subject {subject.get('code')}")
                    continue
                stats["subjects_stored"] += 1

                for module in subject.get("modules", []):
                    mod_name = module.get("name", f"Module {module.get('number')}")
                    logger.info(f"  DB store: module {module.get('number')} - '{mod_name}' (keys: {list(module.keys())})")
                    mod_row = self.upsert_module(admin_client, module, subject["code"], regulation)
                    if not mod_row:
                        stats["errors"].append(f"Failed to store module {subject['code']} M{module.get('number')}")
                        continue
                    stats["modules_stored"] += 1

                    # Topics come from module["topics"] (raw list from LLM)
                    topics = module.get("topics", module.get("topics_raw", []))
                    logger.info(f"    DB store: {len(topics)} topics for module {module.get('number')}")
                    count = self.save_topics(admin_client, mod_row["id"], topics)
                    stats["topics_stored"] += count

            except Exception as e:
                stats["errors"].append(f"Subject {subject.get('code')}: {str(e)}")

        logger.info(
            f"Syllabus DB store: {stats['subjects_stored']} subjects, "
            f"{stats['modules_stored']} modules, {stats['topics_stored']} topics"
        )
        return stats

    def delete_subject(self, admin_client, subject_code: str, regulation: str = "2019") -> bool:
        """Delete a subject and all its modules/topics (cascades)."""
        try:
            admin_client.table("syllabus_subjects").delete().eq("code", subject_code).eq("regulation", regulation).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete subject {subject_code}: {e}")
            return False

    # ─── Read Operations (called by syllabus router) ──────────────────

    def get_branches(self, client) -> List[dict]:
        """
        Get all branches that have subjects, with counts.
        Returns: [{"code": "CSE", "count": 5}, ...]
        """
        try:
            result = (
                client.table("syllabus_subjects")
                .select("branch")
                .execute()
            )
            # Count per branch
            branch_counts: Dict[str, int] = {}
            for row in result.data:
                b = row["branch"]
                branch_counts[b] = branch_counts.get(b, 0) + 1

            return [{"code": b, "count": c} for b, c in sorted(branch_counts.items())]

        except Exception as e:
            logger.error(f"Failed to get branches: {e}")
            return []

    def get_subjects(
        self,
        client,
        branch: Optional[str] = None,
        semester: Optional[int] = None,
        regulation: Optional[str] = None,
    ) -> List[dict]:
        """Get subjects list with optional filters."""
        try:
            # Query the VIEW instead of the table for automatic elective resolution
            query = client.table("subjects_with_electives").select("*")

            if branch:
                query = query.eq("branch", branch)
            if semester is not None:
                query = query.eq("semester", semester)
            if regulation:
                query = query.eq("regulation", regulation)

            query = query.order("semester").order("code")
            result = query.execute()

            subjects = []
            for row in result.data:
                # Get module count
                mod_result = client.table("syllabus_modules").select("id", count="exact").eq("subject_code", row["code"]).eq("regulation", row["regulation"]).execute()
                row["module_count"] = mod_result.count if mod_result.count is not None else 0
                
                # Use mapped_elective from view if present
                val = row.get("mapped_elective")
                if val:
                    row["program_elective"] = val
                    row["category"] = val
                else:
                    row["program_elective"] = ""
                        
                subjects.append(row)

            return subjects

        except Exception as e:
            logger.error(f"Failed to get subjects: {e}")
            return []

    def get_subject_detail(self, client, subject_code: str, regulation: str = "2019") -> Optional[dict]:
        """
        Get full subject detail with modules and topics.
        Handles code with/without spaces (e.g. "CST201" vs "CST 201").
        """
        try:
            # Try exact match on the VIEW
            result = (
                client.table("subjects_with_electives")
                .select("*")
                .eq("code", subject_code)
                .eq("regulation", regulation)
                .execute()
            )

            # Try without spaces fallback
            if not result.data:
                code_no_space = subject_code.replace(" ", "")
                result = client.table("subjects_with_electives").select("*").eq("regulation", regulation).execute()
                result.data = [
                    r for r in result.data
                    if r["code"].replace(" ", "").upper() == code_no_space.upper()
                ]

            if not result.data:
                return None

            subject = result.data[0]

            # Use mapped_elective from view
            val = subject.get("mapped_elective")
            if val:
                subject["program_elective"] = val
                subject["category"] = val
            else:
                subject["program_elective"] = ""

            # Fetch modules
            mod_result = (
                client.table("syllabus_modules")
                .select("*")
                .eq("subject_code", subject["code"])
                .eq("regulation", subject["regulation"])
                .order("module_number")
                .execute()
            )

            modules = []
            for mod in mod_result.data:
                # Fetch topics for this module
                topic_result = (
                    client.table("syllabus_topics")
                    .select("*")
                    .eq("module_id", mod["id"])
                    .order("sort_order")
                    .execute()
                )

                modules.append({
                    "module_number": mod["module_number"],
                    "name": mod["name"],
                    "hours": mod.get("hours"),
                    "topics": [t["name"] for t in topic_result.data],
                })

            subject["modules"] = modules
            return subject

        except Exception as e:
            logger.error(f"Failed to get subject detail for {subject_code}: {e}")
            return None


# Global instance
syllabus_db_service = SyllabusDBService()
