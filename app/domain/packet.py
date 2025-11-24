# app/domain/packet.py
from dataclasses import dataclass
from typing import Optional

from app.domain.manifest import Manifest


@dataclass(frozen=True)
class SheetPosition:
    row: int
    col_output: int
    col_status: int


@dataclass(frozen=True)
class SheetOutputConfig:
    spreadsheet_id: str
    sheet_name: Optional[str] = None


@dataclass
class Packet:
    client_name: str
    dropbox_url: str
    manifest: Manifest
    sheet_output_config: Optional[SheetOutputConfig]
    sheet_position: SheetPosition
