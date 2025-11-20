#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de verificación del refactor.
Verifica que todos los componentes estén correctamente instalados.
"""
import os
import sys
import io

# Configurar encoding para Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def check_file_exists(filepath, description):
    """Verifica que un archivo exista."""
    if os.path.exists(filepath):
        print(f"✅ {description}")
        return True
    else:
        print(f"❌ {description} - FALTA: {filepath}")
        return False


def check_imports():
    """Verifica que los módulos se puedan importar."""
    print("\n🔍 Verificando imports...")

    try:
        from app.services.pdf_assembler import PDFAssembler
        print("✅ PDFAssembler importado correctamente")
    except Exception as e:
        print(f"❌ Error importando PDFAssembler: {e}")
        return False

    try:
        from app.services.slot_models import PacketManifest, Slot, SearchStrategy
        print("✅ Modelos de slots importados correctamente")
    except Exception as e:
        print(f"❌ Error importando modelos: {e}")
        return False

    try:
        from app.services.slot_resolver import SlotResolver
        print("✅ SlotResolver importado correctamente")
    except Exception as e:
        print(f"❌ Error importando SlotResolver: {e}")
        return False

    try:
        from app.services.slot_orchestrator import SlotBasedOrchestrator
        print("✅ SlotBasedOrchestrator importado correctamente")
    except Exception as e:
        print(f"❌ Error importando SlotBasedOrchestrator: {e}")
        return False

    try:
        from app.services.vawa_default_manifest import get_vawa_default_manifest
        print("✅ VAWA manifest importado correctamente")
    except Exception as e:
        print(f"❌ Error importando manifest: {e}")
        return False

    return True


def check_manifest():
    """Verifica que el manifest default esté bien configurado."""
    print("\n📋 Verificando manifest default...")

    try:
        from app.services.vawa_default_manifest import get_vawa_default_manifest

        manifest = get_vawa_default_manifest()

        assert manifest.name == "VAWA Standard Packet"
        assert manifest.version == "1.0.0"
        assert len(manifest.slots) == 4
        print(f"✅ Manifest VAWA: {manifest.name} v{manifest.version}")
        print(f"✅ Total slots: {len(manifest.slots)}")

        for slot in manifest.get_ordered_slots():
            print(f"   • Slot {slot.slot_id}: {slot.name} (required={slot.required})")

        return True

    except Exception as e:
        print(f"❌ Error verificando manifest: {e}")
        return False


def main():
    """Función principal."""
    print("=" * 60)
    print("🔍 VERIFICACIÓN DEL REFACTOR - Sistema de Slots")
    print("=" * 60)

    all_ok = True

    # Verificar archivos de código
    print("\n📂 Verificando archivos de código...")
    files_code = [
        ("app/services/pdf_assembler.py", "PDFAssembler"),
        ("app/services/slot_models.py", "Modelos de datos"),
        ("app/services/slot_resolver.py", "SlotResolver"),
        ("app/services/slot_orchestrator.py", "SlotBasedOrchestrator"),
        ("app/services/vawa_default_manifest.py", "Manifest VAWA default"),
        ("app/api/v1/packet.py", "Endpoint modificado"),
    ]

    for filepath, desc in files_code:
        if not check_file_exists(filepath, desc):
            all_ok = False

    # Verificar archivos de documentación
    print("\n📚 Verificando documentación...")
    files_docs = [
        ("docs/REFACTOR_PDF_ASSEMBLER.md", "Doc técnica del refactor"),
        ("docs/SLOT_SYSTEM_GUIDE.md", "Guía de uso"),
        ("docs/MIGRATION_CHECKLIST.md", "Checklist de migración"),
        ("docs/ARCHITECTURE_DIAGRAM.md", "Diagramas de arquitectura"),
        ("REFACTOR_SUMMARY.md", "Resumen del refactor"),
    ]

    for filepath, desc in files_docs:
        if not check_file_exists(filepath, desc):
            all_ok = False

    # Verificar testing y ejemplos
    print("\n🧪 Verificando tests y ejemplos...")
    files_test = [
        ("tests/test_slot_system.py", "Tests unitarios"),
        ("examples/custom_manifest_example.py", "Ejemplos de manifests"),
    ]

    for filepath, desc in files_test:
        if not check_file_exists(filepath, desc):
            all_ok = False

    # Verificar imports
    if not check_imports():
        all_ok = False

    # Verificar manifest
    if not check_manifest():
        all_ok = False

    # Resultado final
    print("\n" + "=" * 60)
    if all_ok:
        print("✅ VERIFICACIÓN EXITOSA")
        print("=" * 60)
        print("\nEl refactor está completo y listo para usar.")
        print("\nPróximos pasos:")
        print("1. Revisar la documentación en docs/")
        print("2. Ejecutar tests: pytest tests/test_slot_system.py -v")
        print("3. Probar en local: uvicorn app.main:app --reload")
        print("4. Consultar REFACTOR_SUMMARY.md para más detalles")
        return 0
    else:
        print("❌ VERIFICACIÓN FALLÓ")
        print("=" * 60)
        print("\nAlgunos componentes faltan o tienen errores.")
        print("Revisa los mensajes de error arriba.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
