# tests/test_slot_system.py
"""
Tests básicos para el sistema de slots.
Estos tests verifican que los componentes principales funcionen correctamente.
"""
import pytest
from app.services.slot_models import (
    PacketManifest,
    Slot,
    SearchStrategy,
    SearchStrategyType,
    SearchMode,
    SlotResult,
    AssemblyReport
)
from app.services.vawa_default_manifest import get_vawa_default_manifest


class TestSlotModels:
    """Tests para los modelos de datos."""

    def test_search_strategy_creation(self):
        """Test: Crear una estrategia de búsqueda."""
        strategy = SearchStrategy(
            type=SearchStrategyType.FOLDER_SEARCH,
            folder_keywords=["USCIS"],
            file_keywords=["Prima"],
            mode=SearchMode.SINGLE
        )

        assert strategy.type == SearchStrategyType.FOLDER_SEARCH
        assert "USCIS" in strategy.folder_keywords
        assert strategy.mode == SearchMode.SINGLE

    def test_slot_creation(self):
        """Test: Crear un slot con configuración válida."""
        slot = Slot(
            slot_id=1,
            name="Test Slot",
            required=True,
            cover_page=True,
            search_strategy=SearchStrategy(
                type=SearchStrategyType.FOLDER_SEARCH,
                folder_keywords=["Test"],
                mode=SearchMode.MULTIPLE
            )
        )

        assert slot.slot_id == 1
        assert slot.name == "Test Slot"
        assert slot.required is True
        assert slot.cover_page is True

    def test_slot_result_is_complete(self):
        """Test: Verificar lógica de completitud de SlotResult."""
        # Caso 1: Slot requerido con archivos = completo
        result1 = SlotResult(
            slot_id=1,
            name="Test",
            files_found=["file1.pdf"],
            status="success",
            required=True
        )
        assert result1.is_complete is True
        assert result1.has_files is True

        # Caso 2: Slot requerido sin archivos = incompleto
        result2 = SlotResult(
            slot_id=2,
            name="Test",
            files_found=[],
            status="missing",
            required=True
        )
        assert result2.is_complete is False
        assert result2.has_files is False

        # Caso 3: Slot opcional sin archivos = completo (no es crítico)
        result3 = SlotResult(
            slot_id=3,
            name="Test",
            files_found=[],
            status="missing",
            required=False
        )
        assert result3.is_complete is True  # Opcional, puede faltar
        assert result3.has_files is False

    def test_packet_manifest_creation(self):
        """Test: Crear un manifest con múltiples slots."""
        manifest = PacketManifest(
            name="Test Manifest",
            version="1.0.0",
            slots=[
                Slot(
                    slot_id=1,
                    name="Slot 1",
                    required=True,
                    search_strategy=SearchStrategy(
                        type=SearchStrategyType.GENERATED,
                        generator="test"
                    )
                ),
                Slot(
                    slot_id=2,
                    name="Slot 2",
                    required=False,
                    search_strategy=SearchStrategy(
                        type=SearchStrategyType.FOLDER_SEARCH,
                        folder_keywords=["Test"],
                        mode=SearchMode.SINGLE
                    )
                )
            ]
        )

        assert manifest.name == "Test Manifest"
        assert len(manifest.slots) == 2
        assert manifest.get_slot_by_id(1).name == "Slot 1"
        assert manifest.get_slot_by_id(2).name == "Slot 2"
        assert manifest.get_slot_by_id(999) is None

    def test_manifest_ordering(self):
        """Test: Los slots se ordenan por slot_id."""
        manifest = PacketManifest(
            name="Test",
            version="1.0.0",
            slots=[
                Slot(
                    slot_id=3,
                    name="Third",
                    required=True,
                    search_strategy=SearchStrategy(
                        type=SearchStrategyType.GENERATED
                    )
                ),
                Slot(
                    slot_id=1,
                    name="First",
                    required=True,
                    search_strategy=SearchStrategy(
                        type=SearchStrategyType.GENERATED
                    )
                ),
                Slot(
                    slot_id=2,
                    name="Second",
                    required=True,
                    search_strategy=SearchStrategy(
                        type=SearchStrategyType.GENERATED
                    )
                )
            ]
        )

        ordered = manifest.get_ordered_slots()
        assert ordered[0].name == "First"
        assert ordered[1].name == "Second"
        assert ordered[2].name == "Third"


class TestVAWADefaultManifest:
    """Tests para el manifest default de VAWA."""

    def test_vawa_manifest_structure(self):
        """Test: El manifest VAWA tiene la estructura correcta."""
        manifest = get_vawa_default_manifest()

        assert manifest.name == "VAWA Standard Packet"
        assert manifest.version == "1.0.0"
        assert len(manifest.slots) == 4

    def test_vawa_slot_1_uscis(self):
        """Test: Slot 1 (USCIS) está configurado correctamente."""
        manifest = get_vawa_default_manifest()
        slot1 = manifest.get_slot_by_id(1)

        assert slot1 is not None
        assert "USCIS" in slot1.name
        assert slot1.required is True
        assert slot1.search_strategy.type == SearchStrategyType.FOLDER_SEARCH
        assert "USCIS" in slot1.search_strategy.folder_keywords

    def test_vawa_slot_2_missing_report(self):
        """Test: Slot 2 (Missing Report) está configurado correctamente."""
        manifest = get_vawa_default_manifest()
        slot2 = manifest.get_slot_by_id(2)

        assert slot2 is not None
        assert "Missing" in slot2.name
        assert slot2.required is True
        assert slot2.search_strategy.type == SearchStrategyType.GENERATED
        assert slot2.search_strategy.generator == "missing_report"

    def test_vawa_slot_3_evidence(self):
        """Test: Slot 3 (Evidence) está configurado correctamente."""
        manifest = get_vawa_default_manifest()
        slot3 = manifest.get_slot_by_id(3)

        assert slot3 is not None
        assert "Evidence" in slot3.name
        assert slot3.required is False  # Opcional
        assert slot3.search_strategy.type == SearchStrategyType.RECURSIVE_DOWNLOAD
        assert slot3.search_strategy.folder_path == ["VAWA", "Evidence"]

    def test_vawa_slot_4_filed_copy(self):
        """Test: Slot 4 (Filed Copy) está configurado correctamente."""
        manifest = get_vawa_default_manifest()
        slot4 = manifest.get_slot_by_id(4)

        assert slot4 is not None
        assert "Filed Copy" in slot4.name
        assert slot4.required is True
        assert slot4.search_strategy.type == SearchStrategyType.PRIORITIZED_SEARCH
        assert "Filed Copy" in slot4.search_strategy.file_keywords_priority


class TestAssemblyReport:
    """Tests para el reporte de ensamblado."""

    def test_assembly_report_success(self):
        """Test: Reporte con todos los slots exitosos."""
        slot_results = [
            SlotResult(
                slot_id=1,
                name="Slot 1",
                files_found=["file1.pdf"],
                status="success",
                required=True
            ),
            SlotResult(
                slot_id=2,
                name="Slot 2",
                files_found=["file2.pdf"],
                status="success",
                required=True
            )
        ]

        report = AssemblyReport(
            success=True,
            total_slots=2,
            completed_slots=2,
            slot_results=slot_results,
            final_pdf_path="/tmp/final.pdf"
        )

        assert report.success is True
        assert report.completed_slots == 2
        assert len(report.missing_required_slots) == 0
        assert len(report.get_missing_items()) == 0

    def test_assembly_report_with_missing(self):
        """Test: Reporte con slots faltantes."""
        slot_results = [
            SlotResult(
                slot_id=1,
                name="Slot 1",
                files_found=[],
                status="missing",
                required=True
            ),
            SlotResult(
                slot_id=2,
                name="Slot 2",
                files_found=["file2.pdf"],
                status="success",
                required=False
            )
        ]

        report = AssemblyReport(
            success=False,
            total_slots=2,
            completed_slots=1,
            missing_required_slots=["Slot 1"],
            slot_results=slot_results
        )

        assert report.success is False
        assert report.completed_slots == 1
        assert "Slot 1" in report.missing_required_slots
        missing_items = report.get_missing_items()
        assert len(missing_items) > 0
        assert "Slot 1 (required)" in missing_items


# Ejecutar tests:
# pytest tests/test_slot_system.py -v
