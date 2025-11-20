from domain.packet import SheetOutputConfig, SheetPosition
from integrations.sheets_client import SheetsClient


class ProgressReporter:
    """
    Sends coarse-grained progress updates to Sheets to keep users informed.
    """

    def __init__(self, sheets_client: SheetsClient) -> None:
        self.sheets_client = sheets_client

    def report(self, config: SheetOutputConfig, position: SheetPosition, label: str) -> None:
        self.sheets_client.update_status(config, position, label)
