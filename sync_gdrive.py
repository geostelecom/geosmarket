import requests
import re
import os
import sys
from datetime import datetime
import config

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================
# FOLDER_ID: El identificador de la carpeta compartida en Google Drive.
# OUTPUT_DIR: Carpeta local (o relativa) donde se descargarán las imágenes/videos.
FOLDER_ID = config.GDRIVE_FOLDER_ID
OUTPUT_DIR = "imagenes"

def get_file_list(folder_id):
    """
    Escanea la vista pública de una carpeta de Google Drive para extraer los IDs
    y nombres de los archivos disponibles. 
    Utiliza una expresión regular para parsear el HTML de la vista embebida.
    """
    url = f"https://drive.google.com/embeddedfolderview?id={folder_id}"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        # Patrón para encontrar el ID del archivo y su nombre en el HTML.
        # Formato esperado: id="entry-ID" ... flip-entry-title">Nombre</div>
        matches = re.findall(r'id="entry-([\w-]+)".*?class="flip-entry-title">([^<]+)</div>', response.text, re.DOTALL)
        
        files = []
        seen = set()
        for fid, name in matches:
            if fid not in seen:
                name = name.strip()
                ext = os.path.splitext(name)[1].lower()
                # Filtrar solo archivos multimedia permitidos
                if ext in ['.jpg', '.jpeg', '.jfif', '.png', '.webp', '.gif', '.mp4', '.mov', '.avi', '.webm']:
                    files.append((fid, name))
                    seen.add(fid)
        return files
    except Exception as e:
        print(f"Error al listar archivos: {e}")
        return []


def download_file(file_id, name, output_path):
    """
    Descarga un archivo individual usando el ID de descarga directa de Google Drive.
    """
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return True
    except Exception as e:
        print(f"Error descargando {name}: {e}")
        return False

def sync():
    """
    Función principal de sincronización:
    1. Obtiene la lista de archivos en Drive.
    2. Descarga los nuevos archivos que no existen localmente.
    3. Elimina los archivos locales que ya no están en la carpeta de Drive.
    """
    print(f"Iniciando sincronizacion de Google Drive (ID: {FOLDER_ID})...")
    
    files = get_file_list(FOLDER_ID)
    if not files:
        print("No se encontraron archivos o la carpeta no es publica.")
        return

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # Obtener lista de archivos locales actuales (ignorando archivos de sistema de Git)
    local_files = set(os.listdir(OUTPUT_DIR))
    if ".git" in local_files: local_files.remove(".git")
    if "README.md" in local_files: local_files.remove("README.md")
    
    remote_names = set()

    for fid, name in files:
        remote_names.add(name)
        file_path = os.path.join(OUTPUT_DIR, name)
        
        # Solo descargar si el archivo no existe localmente
        if not os.path.exists(file_path):
            print(f"Descargando: {name}")
            download_file(fid, name, file_path)
        else:
            print(f"Ya existe: {name}")

    # Espejo (Mirroring): Borrar archivos locales que ya no existen en el origen (Drive)
    for local_name in local_files:
        if local_name not in remote_names:
            file_to_remove = os.path.join(OUTPUT_DIR, local_name)
            if os.path.isfile(file_to_remove):
                print(f"Borrando archivo eliminado en Drive: {local_name}")
                os.remove(file_to_remove)

    print("Sincronizacion completada.")

if __name__ == "__main__":
    sync()
