"""
Legal chunk data models.

This module defines the dataclasses for legal document chunks:
- LegalParentChunk: Full sections with metadata
- LegalChildChunk: Search fragments with parent links
- LegalTableChunk: Tables extracted from legal documents
- LegalFormChunk: Forms extracted from legal documents
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Optional



@dataclass
class LegalParentChunk:
    """Represents a full legal section (parent chunk)."""
    text: str
    metadata: Dict[str, any]
  # Contains: parent_id, act_name, section_number, section_title, category, page_numbers, table_numbers, form_numbers
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class LegalChildChunk:
    """Represents a search fragment (child chunk)."""
    text: str
    footnotes: List[str]
    metadata: Dict[str, any]
 # Contains: child_id, parent_id, section_name, act_name, section_number, category, page_numbers, start_pos_raw, end_pos_raw
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class LegalTableChunk:
    """Represents a table extracted from a legal document."""
    text: str              # full markdown table as extracted
    summary: str           # short natural-language summary (may be empty)
    metadata: Dict[str, any]
         # table_id, parent_id, act_name, section_number, section_title, category, page_numbers, page, table_index_in_section, pdf_path
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class LegalFormChunk:
    """Represents a form extracted from a legal document."""
    text: str              # full form block as extracted (markdown or plain text)
    summary: str           # short natural-language summary for embeddings
    metadata: Dict[str, any]
         # form_id, parent_id, act_name, section_number, section_title, category, page_numbers, page, form_index_in_section, pdf_path
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

