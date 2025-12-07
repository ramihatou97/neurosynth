"""
PDF Document Processor

Extracts text, structure, and metadata from PDF documents.
Handles complex medical textbook layouts.
"""

import hashlib
import re
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime

import fitz  # PyMuPDF

from models import (
    ProcessedDocument,
    SourceMetadata,
    Section,
    DocumentType,
    Specialty,
)
from config import settings
from .image_extractor import ImageExtractor


class DocumentProcessor:
    """
    Processes PDF documents into structured, searchable content.
    
    Features:
    - Text extraction with layout preservation
    - Section/header detection
    - Image extraction with context
    - Metadata extraction
    """
    
    # Patterns for detecting section headers
    HEADER_PATTERNS = [
        # Numbered sections: "1. Introduction", "1.1 Background"
        r'^(\d+\.?\d*\.?\d*)\s+([A-Z][^.!?\n]{3,80})$',
        # All caps headers: "INTRODUCTION", "SURGICAL TECHNIQUE"
        r'^([A-Z][A-Z\s]{4,60})$',
        # Title case headers (common in textbooks)
        r'^((?:[A-Z][a-z]+\s?){2,8})$',
    ]
    
    # Keywords for specialty detection
    SPECIALTY_KEYWORDS = {
        Specialty.VASCULAR: ['aneurysm', 'avm', 'arteriovenous', 'carotid', 'bypass', 'stroke', 'hemorrhage'],
        Specialty.TUMOR: ['glioma', 'meningioma', 'tumor', 'oncology', 'resection', 'schwannoma'],
        Specialty.SPINE: ['spine', 'spinal', 'vertebral', 'disc', 'fusion', 'laminectomy', 'cervical', 'lumbar'],
        Specialty.FUNCTIONAL: ['dbs', 'deep brain', 'parkinson', 'epilepsy', 'seizure', 'stimulation'],
        Specialty.PEDIATRIC: ['pediatric', 'child', 'infant', 'congenital', 'hydrocephalus', 'shunt'],
        Specialty.TRAUMA: ['trauma', 'tbi', 'injury', 'fracture', 'hematoma', 'contusion'],
        Specialty.SKULL_BASE: ['skull base', 'pituitary', 'acoustic', 'petroclival', 'clivus', 'cavernous'],
        Specialty.ANATOMY: ['anatomy', 'anatomic', 'rhoton', 'neuroanatomy', 'surgical anatomy'],
    }
    
    def __init__(self):
        self.image_extractor = ImageExtractor()
    
    def process(self, pdf_path: Path) -> ProcessedDocument:
        """
        Process a PDF document and extract all content.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            ProcessedDocument with metadata, sections, images, and raw text
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
        doc = fitz.open(pdf_path)
        
        try:
            # Generate document ID
            doc_id = self._generate_id(pdf_path)
            
            # Extract metadata
            metadata = self._extract_metadata(doc, pdf_path, doc_id)
            
            # Extract raw text (for full-text operations)
            raw_text = self._extract_raw_text(doc)
            
            # Detect specialty from content
            metadata.specialty = self._detect_specialty(raw_text)
            
            # Extract structured sections
            sections = self._extract_sections(doc)
            
            # Extract images with context
            images = self.image_extractor.extract_all(doc, doc_id, pdf_path)
            
            # Associate images with sections
            self._associate_images_with_sections(sections, images)
            
            # Update metadata
            metadata.total_pages = len(doc)
            metadata.processed_at = datetime.now()
            
            return ProcessedDocument(
                metadata=metadata,
                sections=sections,
                images=images,
                raw_text=raw_text
            )
            
        finally:
            doc.close()
    
    def _generate_id(self, pdf_path: Path) -> str:
        """Generate a unique ID for a document"""
        # Use filename + size for uniqueness
        stat = pdf_path.stat()
        hash_input = f"{pdf_path.name}_{stat.st_size}_{stat.st_mtime}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:12]
    
    def _extract_metadata(self, doc: fitz.Document, pdf_path: Path, doc_id: str) -> SourceMetadata:
        """Extract document metadata"""
        meta = doc.metadata
        
        # Try to extract title from metadata or filename
        title = meta.get('title', '') or pdf_path.stem.replace('_', ' ').replace('-', ' ')
        
        # Clean up title
        title = re.sub(r'\s+', ' ', title).strip()
        if len(title) > 200:
            title = title[:200]
        
        # Extract author
        authors = meta.get('author', '')
        
        # Try to extract year from metadata or filename
        year = None
        if meta.get('creationDate'):
            try:
                # PDF date format: D:YYYYMMDDHHmmSS
                date_str = meta['creationDate']
                if date_str.startswith('D:'):
                    year = int(date_str[2:6])
            except (ValueError, IndexError):
                pass
        
        # Detect document type from filename/content
        doc_type = self._detect_document_type(pdf_path, title)
        
        return SourceMetadata(
            id=doc_id,
            title=title,
            doc_type=doc_type,
            file_path=pdf_path,
            authors=authors,
            year=year,
        )
    
    def _detect_document_type(self, pdf_path: Path, title: str) -> DocumentType:
        """Detect the type of document"""
        name_lower = pdf_path.name.lower()
        title_lower = title.lower()
        
        # Check for paper indicators
        paper_indicators = ['et al', 'journal', 'doi', 'abstract', 'pubmed']
        if any(ind in name_lower or ind in title_lower for ind in paper_indicators):
            return DocumentType.PAPER
        
        # Check for guideline indicators
        guideline_indicators = ['guideline', 'recommendation', 'consensus', 'protocol']
        if any(ind in name_lower or ind in title_lower for ind in guideline_indicators):
            return DocumentType.GUIDELINE
        
        # Check for chapter indicators
        chapter_indicators = ['chapter', 'ch.', 'ch_']
        if any(ind in name_lower for ind in chapter_indicators):
            return DocumentType.CHAPTER
        
        # Default to textbook for longer documents
        return DocumentType.TEXTBOOK
    
    def _detect_specialty(self, text: str) -> Specialty:
        """Detect neurosurgical specialty from content"""
        text_lower = text.lower()[:50000]  # Check first 50k chars
        
        # Count keyword matches for each specialty
        scores = {}
        for specialty, keywords in self.SPECIALTY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[specialty] = score
        
        if scores:
            return max(scores, key=scores.get)
        return Specialty.GENERAL
    
    def _extract_raw_text(self, doc: fitz.Document) -> str:
        """Extract all text from document"""
        text_parts = []
        for page in doc:
            text = page.get_text("text")
            text_parts.append(text)
        return "\n\n".join(text_parts)
    
    def _extract_sections(self, doc: fitz.Document) -> List[Section]:
        """
        Extract structured sections from document.
        
        Uses font analysis and pattern matching to detect headers.
        """
        sections = []
        current_section = None
        current_content = []
        
        for page_num, page in enumerate(doc):
            # Get text blocks with font info
            blocks = page.get_text("dict")["blocks"]
            
            for block in blocks:
                if block.get("type") != 0:  # Skip non-text blocks
                    continue
                
                for line in block.get("lines", []):
                    line_text = ""
                    line_size = 0
                    line_flags = 0
                    
                    for span in line.get("spans", []):
                        line_text += span.get("text", "")
                        line_size = max(line_size, span.get("size", 0))
                        line_flags = span.get("flags", 0)
                    
                    line_text = line_text.strip()
                    if not line_text:
                        continue
                    
                    # Detect if this is a header
                    is_header, header_level = self._is_header(line_text, line_size, line_flags)
                    
                    if is_header:
                        # Save previous section
                        if current_section and current_content:
                            current_section.content = "\n".join(current_content)
                            current_section.page_end = page_num
                            sections.append(current_section)
                        
                        # Start new section
                        current_section = Section(
                            title=line_text,
                            level=header_level,
                            page_start=page_num,
                            page_end=page_num,
                            content="",
                            images=[]
                        )
                        current_content = []
                    else:
                        current_content.append(line_text)
        
        # Save last section
        if current_section and current_content:
            current_section.content = "\n".join(current_content)
            current_section.page_end = len(doc) - 1
            sections.append(current_section)
        
        # If no sections detected, create one big section
        if not sections:
            sections.append(Section(
                title="Content",
                level=1,
                page_start=0,
                page_end=len(doc) - 1,
                content=self._extract_raw_text(doc),
                images=[]
            ))
        
        return sections
    
    def _is_header(self, text: str, font_size: float, flags: int) -> Tuple[bool, int]:
        """
        Determine if text is a header and its level.
        
        Returns:
            (is_header, level) where level 1 is main heading
        """
        # Skip very short or very long text
        if len(text) < 3 or len(text) > 100:
            return False, 0
        
        # Check if bold (flag bit 2^4 = 16)
        is_bold = bool(flags & 16)
        
        # Large font suggests header
        if font_size >= 14:
            level = 1 if font_size >= 16 else 2
            return True, level
        
        # Bold with medium font
        if is_bold and font_size >= 11:
            return True, 2
        
        # Pattern matching for headers
        for pattern in self.HEADER_PATTERNS:
            if re.match(pattern, text):
                # Numbered headers get level based on number depth
                if re.match(r'^\d+\.\d+', text):
                    return True, 2
                return True, 1
        
        return False, 0
    
    def _associate_images_with_sections(
        self, 
        sections: List[Section], 
        images: List
    ) -> None:
        """Associate extracted images with their containing sections"""
        for image in images:
            for section in sections:
                if section.page_start <= image.page <= section.page_end:
                    section.images.append(image)
                    break


def process_library(library_path: Path, force: bool = False) -> List[ProcessedDocument]:
    """
    Process all PDFs in a library directory.
    
    Args:
        library_path: Path to library directory
        force: If True, reprocess already processed documents
        
    Returns:
        List of processed documents
    """
    processor = DocumentProcessor()
    documents = []
    
    # Find all PDFs
    pdf_files = list(library_path.rglob("*.pdf"))
    
    for pdf_path in pdf_files:
        try:
            doc = processor.process(pdf_path)
            documents.append(doc)
        except Exception as e:
            print(f"Error processing {pdf_path}: {e}")
            continue
    
    return documents
