"""
PDF Processing Service
Extracts text from KTU syllabus PDFs
"""
import os
import re
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class PDFProcessor:
    """
    PDF text extraction service for KTU syllabus documents
    """
    
    def __init__(self):
        self.pdfplumber = None
        self._load_library()
    
    def _load_library(self):
        """Load pdfplumber library"""
        try:
            import pdfplumber
            self.pdfplumber = pdfplumber
            logger.info("pdfplumber loaded successfully")
        except ImportError:
            logger.warning("pdfplumber not installed. Install with: pip install pdfplumber")
            self.pdfplumber = None
    
    def extract_text(self, pdf_path: str) -> str:
        """
        Extract all text from a PDF file
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Extracted text as string
        """
        if not self.pdfplumber:
            raise ImportError("pdfplumber is required. Install with: pip install pdfplumber")
        
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        full_text = ""
        
        try:
            with self.pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                logger.info(f"Processing PDF with {total_pages} pages")
                
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text:
                        # Clean up the text
                        text = self._clean_text(text)
                        full_text += f"\n--- Page {i + 1} ---\n{text}\n"
                    
                    # Log progress for large PDFs
                    if (i + 1) % 10 == 0:
                        logger.info(f"Processed {i + 1}/{total_pages} pages")
            
            logger.info(f"Successfully extracted {len(full_text)} characters from PDF")
            return full_text
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            raise
    
    def extract_text_by_pages(self, pdf_path: str, start_page: int = 0, end_page: Optional[int] = None) -> str:
        """
        Extract text from specific pages of a PDF
        
        Args:
            pdf_path: Path to the PDF file
            start_page: Starting page (0-indexed)
            end_page: Ending page (exclusive, None for all remaining)
            
        Returns:
            Extracted text as string
        """
        if not self.pdfplumber:
            raise ImportError("pdfplumber is required")
        
        full_text = ""
        
        with self.pdfplumber.open(pdf_path) as pdf:
            pages = pdf.pages[start_page:end_page]
            
            for i, page in enumerate(pages):
                text = page.extract_text()
                if text:
                    text = self._clean_text(text)
                    full_text += f"\n{text}\n"
        
        return full_text
    
    def _clean_text(self, text: str) -> str:
        """
        Clean extracted text
        
        Args:
            text: Raw extracted text
            
        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters that might cause issues
        text = text.replace('\x00', '')
        
        # Fix common OCR issues
        text = text.replace('|', 'I')  # Common OCR mistake
        
        # Normalize line breaks
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Remove excessive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()
    
    def extract_tables(self, pdf_path: str) -> list:
        """
        Extract tables from PDF (useful for syllabus structure)
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            List of extracted tables (as lists of lists)
        """
        if not self.pdfplumber:
            raise ImportError("pdfplumber is required")
        
        all_tables = []
        
        with self.pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                if tables:
                    all_tables.extend(tables)
        
        return all_tables
    
    def get_pdf_info(self, pdf_path: str) -> dict:
        """
        Get metadata about a PDF file
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Dictionary with PDF metadata
        """
        if not self.pdfplumber:
            raise ImportError("pdfplumber is required")
        
        with self.pdfplumber.open(pdf_path) as pdf:
            return {
                "total_pages": len(pdf.pages),
                "metadata": pdf.metadata or {},
                "file_size": os.path.getsize(pdf_path)
            }


# Global instance
pdf_processor = PDFProcessor()
