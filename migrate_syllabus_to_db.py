"""
One-time migration script: Copy existing syllabus data from Neo4j → Supabase tables.
Run this once so the new DB-based syllabus endpoints work for already-imported subjects.

Usage:
    python migrate_syllabus_to_db.py
"""
import os
import sys
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def migrate():
    from dotenv import load_dotenv
    load_dotenv()

    from services.neo4j_service_v2 import neo4j_service as neo4j_v2
    from services.neo4j_service import neo4j_service as neo4j_v1
    from utils.supabase_client import supabase_admin_client
    from services.syllabus_db_service import syllabus_db_service

    # Pick whichever Neo4j service is connected
    if neo4j_v2.is_connected():
        svc = neo4j_v2
        version = "v2"
    elif neo4j_v1.is_connected():
        svc = neo4j_v1
        version = "v1"
    else:
        logger.error("Neither Neo4j V1 nor V2 is connected. Aborting.")
        sys.exit(1)

    logger.info(f"Using Neo4j {version}")

    # Get all subjects from Neo4j
    subjects = svc.get_all_subjects()
    logger.info(f"Found {len(subjects)} subjects in Neo4j")

    if not subjects:
        logger.warning("No subjects found. Nothing to migrate.")
        return

    total_subjects = 0
    total_modules = 0
    total_topics = 0

    for subj_summary in subjects:
        code = subj_summary.get("code", "")
        regulation = subj_summary.get("regulation", "2019")

        # Fetch full subject detail
        if version == "v2":
            detail = svc.get_subject(code, regulation)
        else:
            detail = svc.get_subject(code)

        if not detail:
            logger.warning(f"  Could not fetch detail for {code}, skipping")
            continue

        semester = detail.get("semester", 0)
        branch = detail.get("branch", "")

        # Upsert subject
        subj_row = syllabus_db_service.upsert_subject(
            admin_client=supabase_admin_client,
            subject_data={
                "code": code,
                "name": detail.get("name", ""),
                "credits": detail.get("credits"),
                "category": detail.get("category", ""),
                "hours_per_week": detail.get("hours_per_week"),
                "course_outcomes": detail.get("course_outcomes", detail.get("objectives", [])),
                "textbooks": detail.get("textbooks", []),
                "references": detail.get("references", []),
                "objectives": detail.get("objectives", []),
            },
            semester=semester,
            branch=branch,
            regulation=regulation,
        )

        if not subj_row:
            logger.error(f"  Failed to upsert subject {code}")
            continue

        total_subjects += 1
        logger.info(f"  Subject: {code} - {detail.get('name', '')}")

        # Upsert modules & topics
        for mod in detail.get("modules", []):
            mod_number = mod.get("number", 0)
            mod_name = mod.get("name", mod.get("display_name", f"Module {mod_number}"))
            hours = mod.get("hours")

            mod_row = syllabus_db_service.upsert_module(
                admin_client=supabase_admin_client,
                module_data={
                    "number": mod_number,
                    "name": mod_name,
                    "hours": hours,
                    "syllabus_text": mod.get("syllabus_text", ""),
                },
                subject_code=code,
                regulation=regulation,
            )

            if not mod_row:
                logger.warning(f"    Failed to upsert module {code} M{mod_number}")
                continue

            total_modules += 1

            # Topics: V2 uses "concepts", V1 uses "topics"
            topics = mod.get("concepts", mod.get("topics", []))
            count = syllabus_db_service.save_topics(
                admin_client=supabase_admin_client,
                module_id=mod_row["id"],
                topics=topics,
            )
            total_topics += count
            logger.info(f"    Module {mod_number}: {mod_name} ({count} topics)")

    logger.info(f"\nMigration complete: {total_subjects} subjects, {total_modules} modules, {total_topics} topics")


if __name__ == "__main__":
    migrate()
