# examples/custom_manifest_example.py
"""
Ejemplos de cómo crear manifests personalizados para diferentes casos de uso.
"""
from app.services.slot_models import (
    PacketManifest,
    Slot,
    SearchStrategy,
    SearchStrategyType,
    SearchMode
)


# =========================================
# EJEMPLO 1: Manifest Simple (2 Slots)
# =========================================

def create_simple_manifest() -> PacketManifest:
    """
    Manifest simple con solo 2 slots:
    1. Cover Letter
    2. Supporting Documents
    """
    return PacketManifest(
        name="Simple Immigration Packet",
        version="1.0.0",
        description="Packet básico con cover letter y documentos de soporte",
        slots=[
            Slot(
                slot_id=1,
                name="Cover Letter",
                description="Carta de presentación del caso",
                required=True,
                cover_page=False,  # No incluir portada para este slot
                search_strategy=SearchStrategy(
                    type=SearchStrategyType.FOLDER_SEARCH,
                    folder_keywords=["Cover", "Letter"],
                    file_keywords=["cover_letter", "letter"],
                    mode=SearchMode.SINGLE
                )
            ),
            Slot(
                slot_id=2,
                name="Supporting Documents",
                description="Documentos de evidencia",
                required=True,
                cover_page=True,
                search_strategy=SearchStrategy(
                    type=SearchStrategyType.RECURSIVE_DOWNLOAD,
                    folder_path=["Documents", "Support"],
                    file_keywords=[""],  # Wildcard: todo
                    mode=SearchMode.MULTIPLE
                )
            )
        ]
    )


# =========================================
# EJEMPLO 2: Manifest con Prioridades
# =========================================

def create_prioritized_manifest() -> PacketManifest:
    """
    Manifest con búsquedas priorizadas.
    Útil cuando hay múltiples nombres posibles para un documento.
    """
    return PacketManifest(
        name="Prioritized Search Packet",
        version="1.0.0",
        description="Usa búsquedas priorizadas para encontrar documentos",
        slots=[
            Slot(
                slot_id=1,
                name="Application Form",
                description="Formulario principal (puede tener varios nombres)",
                required=True,
                cover_page=True,
                search_strategy=SearchStrategy(
                    type=SearchStrategyType.PRIORITIZED_SEARCH,
                    folder_keywords=["Forms", "Applications"],
                    file_keywords_priority=[
                        "I-360",           # Prioridad 1
                        "Application",     # Prioridad 2
                        "Form",            # Prioridad 3
                        "Petition"         # Prioridad 4
                    ],
                    mode=SearchMode.SINGLE
                )
            ),
            Slot(
                slot_id=2,
                name="Signed Declaration",
                description="Declaración firmada",
                required=True,
                cover_page=True,
                search_strategy=SearchStrategy(
                    type=SearchStrategyType.PRIORITIZED_SEARCH,
                    folder_keywords=["Declarations", "Signed"],
                    file_keywords_priority=[
                        "signed",
                        "declaration",
                        "statement"
                    ],
                    mode=SearchMode.SINGLE
                )
            )
        ]
    )


# =========================================
# EJEMPLO 3: Manifest Mixto (Opcional + Required)
# =========================================

def create_mixed_requirements_manifest() -> PacketManifest:
    """
    Manifest con slots opcionales y requeridos.
    Útil cuando algunos documentos pueden no estar disponibles.
    """
    return PacketManifest(
        name="Flexible Packet",
        version="1.0.0",
        description="Permite slots opcionales que pueden faltar",
        slots=[
            # SLOT REQUERIDO
            Slot(
                slot_id=1,
                name="Main Petition",
                description="Petición principal (REQUERIDO)",
                required=True,  # ✅ Este DEBE existir
                cover_page=True,
                search_strategy=SearchStrategy(
                    type=SearchStrategyType.FOLDER_SEARCH,
                    folder_keywords=["Petition"],
                    file_keywords=["petition", "main"],
                    mode=SearchMode.SINGLE
                )
            ),

            # SLOT OPCIONAL 1
            Slot(
                slot_id=2,
                name="Police Reports",
                description="Reportes policiales (OPCIONAL)",
                required=False,  # ⚠️ Puede faltar sin problema
                cover_page=True,
                search_strategy=SearchStrategy(
                    type=SearchStrategyType.RECURSIVE_DOWNLOAD,
                    folder_path=["Evidence", "Police"],
                    file_keywords=[""],
                    mode=SearchMode.MULTIPLE
                )
            ),

            # SLOT OPCIONAL 2
            Slot(
                slot_id=3,
                name="Medical Records",
                description="Registros médicos (OPCIONAL)",
                required=False,
                cover_page=True,
                search_strategy=SearchStrategy(
                    type=SearchStrategyType.RECURSIVE_DOWNLOAD,
                    folder_path=["Evidence", "Medical"],
                    file_keywords=[""],
                    mode=SearchMode.MULTIPLE
                )
            ),

            # SLOT REQUERIDO
            Slot(
                slot_id=4,
                name="Summary Report",
                description="Reporte generado (REQUERIDO)",
                required=True,  # ✅ Este se genera automáticamente
                cover_page=True,
                search_strategy=SearchStrategy(
                    type=SearchStrategyType.GENERATED,
                    generator="missing_report"
                )
            )
        ]
    )


# =========================================
# EJEMPLO 4: Manifest Complejo (Múltiples Niveles)
# =========================================

def create_complex_manifest() -> PacketManifest:
    """
    Manifest complejo con múltiples niveles de carpetas
    y diferentes estrategias de búsqueda.
    """
    return PacketManifest(
        name="Complex Immigration Packet",
        version="2.0.0",
        description="Packet complejo con jerarquía profunda de carpetas",
        slots=[
            # SLOT 1: Cover con title custom
            Slot(
                slot_id=1,
                name="Client Cover Page",
                description="Portada del cliente",
                required=True,
                cover_page=True,
                cover_title="Immigration Petition Package",  # Título custom
                search_strategy=SearchStrategy(
                    type=SearchStrategyType.GENERATED,
                    generator="cover_page",
                    metadata={"include_client_name": True}
                )
            ),

            # SLOT 2: USCIS con múltiples keywords
            Slot(
                slot_id=2,
                name="USCIS Receipts and Notices",
                description="Todos los documentos de USCIS",
                required=True,
                cover_page=True,
                search_strategy=SearchStrategy(
                    type=SearchStrategyType.FOLDER_SEARCH,
                    folder_keywords=["USCIS", "UCIS", "Immigration", "Receipts"],
                    file_keywords=[
                        "Prima Facie",
                        "Transfer Notice",
                        "Receipt",
                        "I-360",
                        "I-485",
                        "Notice"
                    ],
                    mode=SearchMode.MULTIPLE
                )
            ),

            # SLOT 3: Evidence multinivel
            Slot(
                slot_id=3,
                name="Supporting Evidence - Level 1",
                description="Evidencia de primer nivel",
                required=True,
                cover_page=True,
                search_strategy=SearchStrategy(
                    type=SearchStrategyType.RECURSIVE_DOWNLOAD,
                    folder_path=["Evidence", "Primary"],
                    file_keywords=[""],
                    mode=SearchMode.MULTIPLE,
                    metadata={"max_depth": 2}
                )
            ),

            # SLOT 4: Evidence adicional
            Slot(
                slot_id=4,
                name="Supporting Evidence - Level 2",
                description="Evidencia adicional",
                required=False,
                cover_page=True,
                search_strategy=SearchStrategy(
                    type=SearchStrategyType.RECURSIVE_DOWNLOAD,
                    folder_path=["Evidence", "Secondary"],
                    file_keywords=[""],
                    mode=SearchMode.MULTIPLE
                )
            ),

            # SLOT 5: Documento específico con prioridad
            Slot(
                slot_id=5,
                name="Filed Copy or Signed Petition",
                description="Documento maestro firmado",
                required=True,
                cover_page=True,
                search_strategy=SearchStrategy(
                    type=SearchStrategyType.PRIORITIZED_SEARCH,
                    folder_keywords=["7", "Filed", "Signed", "Final"],
                    file_keywords_priority=[
                        "filed copy",
                        "FILED_COPY",
                        "ready to print",
                        "signed petition",
                        "final version"
                    ],
                    mode=SearchMode.SINGLE
                )
            ),

            # SLOT 6: Reporte de faltantes
            Slot(
                slot_id=6,
                name="Missing Documents Report",
                description="Reporte generado de documentos faltantes",
                required=True,
                cover_page=True,
                search_strategy=SearchStrategy(
                    type=SearchStrategyType.GENERATED,
                    generator="missing_report"
                )
            )
        ]
    )


# =========================================
# EJEMPLO 5: Manifest para Testing
# =========================================

def create_test_manifest() -> PacketManifest:
    """
    Manifest simplificado para testing.
    Usa solo contenido generado para evitar dependencias de Dropbox.
    """
    return PacketManifest(
        name="Test Packet",
        version="1.0.0-test",
        description="Manifest para tests sin dependencias externas",
        slots=[
            Slot(
                slot_id=1,
                name="Test Cover",
                required=True,
                cover_page=True,
                search_strategy=SearchStrategy(
                    type=SearchStrategyType.GENERATED,
                    generator="test_cover"
                )
            ),
            Slot(
                slot_id=2,
                name="Test Content",
                required=True,
                cover_page=True,
                search_strategy=SearchStrategy(
                    type=SearchStrategyType.GENERATED,
                    generator="test_content"
                )
            )
        ]
    )


# =========================================
# USO DE LOS EJEMPLOS
# =========================================

if __name__ == "__main__":
    # Ejemplo 1: Mostrar estructura de manifest simple
    print("=" * 50)
    print("EJEMPLO 1: Manifest Simple")
    print("=" * 50)

    simple = create_simple_manifest()
    print(f"Nombre: {simple.name}")
    print(f"Versión: {simple.version}")
    print(f"Total slots: {len(simple.slots)}")

    for slot in simple.get_ordered_slots():
        print(f"\n  Slot {slot.slot_id}: {slot.name}")
        print(f"    Required: {slot.required}")
        print(f"    Cover page: {slot.cover_page}")
        print(f"    Strategy: {slot.search_strategy.type}")

    # Ejemplo 2: Comparar manifests
    print("\n" + "=" * 50)
    print("EJEMPLO 2: Comparar Manifests")
    print("=" * 50)

    manifests = [
        create_simple_manifest(),
        create_prioritized_manifest(),
        create_mixed_requirements_manifest(),
        create_complex_manifest(),
        create_test_manifest()
    ]

    for manifest in manifests:
        required_slots = sum(1 for s in manifest.slots if s.required)
        optional_slots = sum(1 for s in manifest.slots if not s.required)

        print(f"\n{manifest.name}:")
        print(f"  Total slots: {len(manifest.slots)}")
        print(f"  Required: {required_slots}")
        print(f"  Optional: {optional_slots}")

    # Ejemplo 3: Usar manifest custom con orquestador
    print("\n" + "=" * 50)
    print("EJEMPLO 3: Uso con Orquestador")
    print("=" * 50)

    print("""
    # Para usar un manifest custom:
    from app.services.slot_orchestrator import SlotBasedOrchestrator
    from examples.custom_manifest_example import create_simple_manifest

    # Crear manifest
    my_manifest = create_simple_manifest()

    # Crear orquestador con el manifest
    orchestrator = SlotBasedOrchestrator(manifest=my_manifest)

    # Procesar request
    result = await orchestrator.process_request(request)
    """)
