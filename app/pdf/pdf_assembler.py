from pathlib import Path
from typing import Iterable

from pypdf import PdfMerger


def merge_pdfs_in_order(input_paths: Iterable[str], output_path: str) -> None:
    """
    Merge the provided PDFs in the received order into a final PDF.
    The function assumes paths exist; callers should validate upstream.
    """
    merger = PdfMerger(strict=False)
    for pdf_path in input_paths:
        merger.append(str(pdf_path))
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("wb") as fh:
        merger.write(fh)
