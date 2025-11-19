# app/integrations/dropbox_client.py
import dropbox
from dropbox.files import FileMetadata, FolderMetadata
from dropbox.exceptions import ApiError
from typing import List, Optional, Tuple
from app.utils.helpers import normalize_text, sanitize_filename
from app.utils.logger import logger # <-- IMPORTAR LOGGER
import os

class DropboxIntegrator:
    def __init__(self, token: str):
        self.dbx = dropbox.Dropbox(token)
    
    def get_path_from_link(self, shared_link: str) -> Optional[str]:
        try:
            metadata = self.dbx.sharing_get_shared_link_metadata(shared_link)
            return getattr(metadata, 'path_lower', None)
        except Exception as e:
            logger.error(f"❌ Error resolviendo link Dropbox: {e}") # <-- USO DE LOGGER
            return None

    def list_folder(self, path: str) -> List:
        entries = []
        try:
            res = self.dbx.files_list_folder(path)
            entries.extend(res.entries)
            while res.has_more:
                # logger.debug(f"Paginando carpeta: {path}...") # Opcional para debug
                res = self.dbx.files_list_folder_continue(res.cursor)
                entries.extend(res.entries)
        except ApiError as e:
            logger.warning(f"⚠️ Error listando carpeta {path}: {e}")
        return entries

    def find_folder_fuzzy(self, base_path: str, keywords: List[str]) -> Optional[str]:
        keywords_norm = [normalize_text(k) for k in keywords]
        entries = self.list_folder(base_path)
        
        for entry in entries:
            if isinstance(entry, FolderMetadata):
                name_norm = normalize_text(entry.name)
                if any(kw in name_norm for kw in keywords_norm):
                    logger.info(f"✅ Carpeta encontrada: {entry.name}")
                    return entry.path_lower
        return None

    def validate_vawa_structure(self, root_path: str) -> Tuple[bool, List[str]]:
        logger.info(f"🔍 Validando estructura VAWA en: {root_path}")
        missing = []
        
        # 1. Buscar Exhibit 1 (USCIS)
        uscis = self.find_folder_fuzzy(root_path, ['USCIS', 'UCIS', 'Receipts'])
        if not uscis: missing.append("Carpeta USCIS/Receipts")

        # 2. Buscar Exhibit 3 (VAWA -> Evidence)
        vawa = self.find_folder_fuzzy(root_path, ['VAWA'])
        if vawa:
            evidence = self.find_folder_fuzzy(vawa, ['Evidence'])
            if not evidence: missing.append("Subcarpeta 'Evidence' dentro de VAWA")
        else:
            missing.append("Carpeta VAWA")

        # 3. Buscar Exhibit 4 (Carpeta 7)
        folder_7 = self.find_folder_fuzzy(root_path, ['7', 'Folder7'])
        if not folder_7: missing.append("Carpeta 7 (Filed Copy)")

        is_valid = len(missing) == 0
        if not is_valid:
            logger.warning(f"❌ Validación fallida. Faltan: {missing}")
        
        return is_valid, missing

    def download_file(self, dropbox_path: str, local_dest_folder: str) -> Optional[str]:
        try:
            os.makedirs(local_dest_folder, exist_ok=True)
            file_name = sanitize_filename(os.path.basename(dropbox_path))
            local_path = os.path.join(local_dest_folder, file_name)
            
            logger.info(f"⬇️ Descargando: {file_name}")
            self.dbx.files_download_to_file(local_path, dropbox_path)
            return local_path
        except Exception as e:
            logger.error(f"❌ Error descargando {dropbox_path}: {e}")
            return None
            
    def find_files_recursive_fuzzy(self, folder_path: str, keywords: List[str], stop_on_first: bool = False):
        found = []
        normalized_kws = [normalize_text(k) for k in keywords]
        
        try:
            entries = self.list_folder(folder_path)
            for entry in entries:
                if isinstance(entry, FileMetadata):
                    norm_name = normalize_text(entry.name)
                    # Si keywords es [''], coincide con todo (wildcard)
                    if keywords == [''] or any(kw in norm_name for kw in normalized_kws):
                        found.append(entry)
                        if stop_on_first: return found
                
                elif isinstance(entry, FolderMetadata):
                    sub_found = self.find_files_recursive_fuzzy(entry.path_lower, keywords, stop_on_first)
                    found.extend(sub_found)
                    if stop_on_first and found: return found
                    
        except Exception as e:
            logger.error(f"⚠️ Error en búsqueda recursiva {folder_path}: {e}")
            
        return found