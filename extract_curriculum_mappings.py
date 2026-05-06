"""
One-time script: Extract elective mappings from curriculum PDF and populate the DB.

Usage:
    python extract_curriculum_mappings.py <curriculum_pdf_path> [branch] [regulation]
    
Example:
    python extract_curriculum_mappings.py "CSE Full Curriculum (1).pdf" CSE 2019
"""
import os
import sys
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def extract_and_populate():
    from dotenv import load_dotenv
    load_dotenv()
    
    from utils.supabase_client import supabase_admin_client
    from services.curriculum_extractor import curriculum_extractor
    
    # Parse arguments
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "CSE Full Curriculum (1).pdf"
    branch = sys.argv[2] if len(sys.argv) > 2 else "CSE"
    regulation = sys.argv[3] if len(sys.argv) > 3 else "2019"
    
    if not os.path.exists(pdf_path):
        logger.error(f"PDF not found: {pdf_path}")
        sys.exit(1)
    
    if not supabase_admin_client:
        logger.error("Supabase admin client not configured")
        sys.exit(1)
    
    logger.info(f"Extracting curriculum from {pdf_path}")
    logger.info(f"Branch: {branch}, Regulation: {regulation}")
    
    # Step 1: Extract mappings from PDF
    extract_result = curriculum_extractor.extract_elective_mappings_from_pdf(pdf_path, branch, regulation)
    
    if not extract_result["success"]:
        logger.error("Failed to extract curriculum")
        for error in extract_result["errors"]:
            logger.error(f"  - {error}")
        sys.exit(1)
    
    logger.info(f"✓ Extracted {len(extract_result['mappings'])} mappings from curriculum")
    
    # Display extracted mappings
    logger.info("\nExtracted mappings:")
    for m in extract_result["mappings"][:10]:  # Show first 10
        logger.info(f"  {m['subject_code']:10} {m['subject_name']:40} → {m['program_elective']:8} (S{m.get('semester', '?')})")
    
    if len(extract_result["mappings"]) > 10:
        logger.info(f"  ... and {len(extract_result['mappings']) - 10} more")
    
    # Step 2: Populate database
    logger.info("\nPopulating database...")
    populate_result = curriculum_extractor.populate_elective_mappings(
        supabase_admin_client,
        extract_result["mappings"],
        branch,
        regulation
    )
    
    logger.info(f"✓ Database population complete:")
    logger.info(f"  Inserted: {populate_result['inserted']}")
    logger.info(f"  Updated: {populate_result['updated']}")
    logger.info(f"  Skipped: {populate_result['skipped']}")
    
    if populate_result["errors"]:
        logger.warning("Errors encountered:")
        for error in populate_result["errors"]:
            logger.warning(f"  - {error}")
    
    logger.info("\n✓ Curriculum extraction and mapping complete!")
    logger.info(f"Total mappings in database: {populate_result['inserted']}")


if __name__ == "__main__":
    extract_and_populate()
