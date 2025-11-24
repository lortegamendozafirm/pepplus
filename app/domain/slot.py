# app/domain/slot.py
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class SlotMeta:
    folder_hint: Optional[str] = None
    file_hint: Optional[str] = None
    filename_patterns: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    allow_docx: bool = False


@dataclass(frozen=True)
class Slot:
    slot: int
    name: str
    required: bool = True
    meta: SlotMeta = field(default_factory=SlotMeta)
