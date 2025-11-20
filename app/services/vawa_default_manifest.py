# app/services/vawa_default_manifest.py
"""
Manifest por defecto para expedientes VAWA.
Define la estructura estándar de slots para el ensamblado de paquetes VAWA.
"""
from app.services.slot_models import (
    PacketManifest,
    Slot,
    SearchStrategy,
    SearchStrategyType,
    SearchMode
)


def get_vawa_default_manifest() -> PacketManifest:
    """
    Retorna el manifest por defecto para paquetes VAWA.

    Este manifest define 4 exhibits estándar:
    1. USCIS Documents (Prima Facie, Transfer Notices, etc.)
    2. Missing Documents Report (Generado automáticamente)
    3. VAWA Evidence (Todo el contenido de VAWA/Evidence)
    4. Filed Copy (Documento maestro de carpeta 7)

    Returns:
        PacketManifest configurado para VAWA
    """
    return PacketManifest(
        name="VAWA Standard Packet",
        version="1.0.0",
        description="Manifest estándar para ensamblado de expedientes VAWA",
        slots=[
            # --- SLOT 1: USCIS DOCUMENTS ---
            Slot(
                slot_id=1,
                name="Exhibit A – USCIS Documents",
                description="Documentos de USCIS: Prima Facie, Transfer Notices, Receipts",
                required=True,
                cover_page=True,
                search_strategy=SearchStrategy(
                    type=SearchStrategyType.FOLDER_SEARCH,
                    folder_keywords=["USCIS", "UCIS", "Receipts"],
                    file_keywords=["Prima", "Transfer", "I-360", "I-485", "Receipt"],
                    mode=SearchMode.MULTIPLE
                )
            ),

            # --- SLOT 2: MISSING DOCUMENTS REPORT ---
            Slot(
                slot_id=2,
                name="Exhibit B – Missing Documents Report",
                description="Reporte generado automáticamente de documentos faltantes",
                required=True,
                cover_page=True,
                search_strategy=SearchStrategy(
                    type=SearchStrategyType.GENERATED,
                    generator="missing_report"
                )
            ),

            # --- SLOT 3: VAWA EVIDENCE ---
            Slot(
                slot_id=3,
                name="Exhibit C – VAWA Evidence",
                description="Todo el contenido de la carpeta VAWA/Evidence",
                required=False,  # Puede no existir en algunos casos
                cover_page=True,
                search_strategy=SearchStrategy(
                    type=SearchStrategyType.RECURSIVE_DOWNLOAD,
                    folder_path=["VAWA", "Evidence"],
                    file_keywords=[""],  # Wildcard: traer todo
                    mode=SearchMode.MULTIPLE
                )
            ),

            # --- SLOT 4: FILED COPY ---
            Slot(
                slot_id=4,
                name="Exhibit D – Filed Copy",
                description="Documento maestro (Filed Copy, Ready to Print, etc.)",
                required=True,
                cover_page=True,
                search_strategy=SearchStrategy(
                    type=SearchStrategyType.PRIORITIZED_SEARCH,
                    folder_keywords=["7", "Folder7", "Filed"],
                    file_keywords_priority=[
                        "Filed Copy",
                        "FILED_COPY",
                        "FILED-COPY",
                        "FC",
                        "Ready to print",
                        "Ready-to-print",
                        "READYTOPRINT",
                        "RTP",
                        "Signed"
                    ],
                    mode=SearchMode.SINGLE
                )
            )
        ]
    )


def get_custom_manifest_example() -> PacketManifest:
    """
    Ejemplo de un manifest customizado.
    Muestra cómo crear un manifest diferente para otros casos de uso.

    Returns:
        PacketManifest con configuración diferente
    """
    return PacketManifest(
        name="Custom Immigration Packet",
        version="1.0.0",
        description="Ejemplo de manifest personalizado",
        slots=[
            Slot(
                slot_id=1,
                name="Cover Letter",
                required=True,
                cover_page=False,
                search_strategy=SearchStrategy(
                    type=SearchStrategyType.FOLDER_SEARCH,
                    folder_keywords=["Cover"],
                    file_keywords=["letter", "cover"],
                    mode=SearchMode.SINGLE
                )
            ),
            Slot(
                slot_id=2,
                name="Supporting Evidence",
                required=False,
                cover_page=True,
                search_strategy=SearchStrategy(
                    type=SearchStrategyType.RECURSIVE_DOWNLOAD,
                    folder_path=["Evidence", "Support"],
                    file_keywords=[""],
                    mode=SearchMode.MULTIPLE
                )
            )
        ]
    )
