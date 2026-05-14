import os
from dotenv import load_dotenv

# Cargar variables desde .env
load_dotenv()

# Parámetros del sitio
SITE_NAME = os.getenv("SITE_NAME", "geosmarket")
GIT_REPO = os.getenv("GIT_REPO", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# Google Drive (Extraer ID si es una URL completa)
GDRIVE_IMAGES_URL = os.getenv("GDRIVE_IMAGES_FOLDER", "")
def extract_gdrive_id(url):
    if "folders/" in url:
        return url.split("folders/")[1].split("?")[0]
    return url
GDRIVE_FOLDER_ID = extract_gdrive_id(GDRIVE_IMAGES_URL)

# Google Sheets (Asegurar formato de exportación)
CONTENT_SHEET_URL = os.getenv("CONTENT_SHEET_URL", "")
def get_export_url(url):
    if not url: return ""
    # Eliminar parámetros de consulta existentes
    base_url = url.split("?")[0]
    if "/edit" in base_url:
        return base_url.replace("/edit", "/export?format=xlsx")
    if not base_url.endswith("/export"):
        return base_url.rstrip("/") + "/export?format=xlsx"
    return base_url
GOOGLE_SHEETS_EXPORT_URL = get_export_url(CONTENT_SHEET_URL)

# Google Form
CONTACT_FORM_URL = os.getenv("CONTACT_FORM_URL", "")
