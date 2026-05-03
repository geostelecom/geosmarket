import pandas as pd
import json
import os
import requests
import io
import urllib.parse
from datetime import datetime

# ==============================================================================
# CONFIGURACIÓN Y DEPENDENCIAS
# ==============================================================================
# GOOGLE_SHEETS_URL: Enlace de exportación a Excel del Google Sheet Público.
# LOCAL_EXCEL: Nombre del archivo local que se usa como respaldo si falla la descarga.
GOOGLE_SHEETS_URL = "https://docs.google.com/spreadsheets/d/113Cg8-t31cXcg5_brGk2H5buyT3evXzF/export?format=xlsx"
LOCAL_EXCEL = "contenidos.xlsx"

def detect_language(url):
    """
    Heurística simple para detectar si la fuente de una noticia es en Inglés o Español
    basándose en la extensión del dominio o palabras clave en la URL.
    """
    if not url or pd.isna(url):
        return "Español"
    
    url = str(url).lower()
    spanish_indicators = [
        '.cr', '.es', 'latam', 'mund', 'noticias', 'agroclima', 
        'español', 'spanish', 'el-pais', 'abril', 'mayo'
    ]
    
    # Dominios conocidos que son mayoritariamente en inglés
    english_only = ['usda.gov', 'croplife.com', 'agribusinessglobal', 'topconpositioning.com', 'github.com']
    
    for indicator in spanish_indicators:
        if indicator in url:
            return "Español"
            
    for domain in english_only:
        if domain in url:
            return "English"
            
    return "English" # Por defecto a Inglés para fuentes internacionales

def get_excel_data(url, local_path):
    """
    Intenta descargar el archivo Excel más reciente desde la nube (Google Sheets).
    Si la descarga falla, intenta cargar el archivo local 'contenidos.xlsx'.
    """
    try:
        print(f"Intentando descargar Excel desde la nube (Google Sheets)...")
        # El cache-buster (t=TIMESTAMP) previene cacheos de proxy
        url_with_cache_buster = f"{url}&t={datetime.now().timestamp()}"
        response = requests.get(url_with_cache_buster, timeout=15)
        response.raise_for_status()
        
        # Validar que no hayamos descargado una página de error HTML (común si no es público)
        if b"<!DOCTYPE html>" in response.content[:100].lower() or b"<html" in response.content[:100].lower():
             raise ValueError("El archivo descargado es HTML, probablemente el Google Sheet no es público o el enlace es incorrecto.")
             
        print("Éxito: Datos obtenidos desde Google Sheets.")
        return io.BytesIO(response.content)
    except Exception as e:
        print(f"Aviso: No se pudo obtener el Excel desde la nube ({e}).")
        if os.path.exists(local_path):
            print(f"Usando archivo local de respaldo: {local_path}")
            return local_path
        else:
            print("Error: No existe el archivo local de respaldo.")
            return None

def transform_excel_to_json(source, output_json):
    """
    Función principal que lee el Excel, extrae la información de todas las hojas
    y genera un archivo JSON estructurado para que la web lo consuma.
    """
    if source is None:
        print("Error: No hay fuente de datos disponible.")
        return

    try:
        # Leer todas las hojas del Excel. 'sheet_name=None' devuelve un diccionario.
        sheets = pd.read_excel(source, sheet_name=None)
        
        # Hojas especiales que definen la estructura del sitio y no son temas de noticias.
        system_sheets = ['Encabezado', 'Pie de Página', 'Imagen Empresa', 'Banner', 'Hoja1', 'Logos']
        
        # Columnas que deben existir en cada hoja de tema para que el sistema funcione.
        required_cols = ['SubTema', 'Sub titulo', 'Titulo', 'Spanish', 'Original', 'Foto', 'Boton', 'Resumen']
        
        news_list = []
        today = datetime.now().strftime("%Y-%m-%d")

        # 1. PROCESAR LOGOS DE SUBTEMAS
        # Mapea qué logo debe aparecer en cada tarjeta de subtema (mosaico).
        logos_data = {}
        logos_df = sheets.get('Logos', pd.DataFrame())
        if not logos_df.empty:
            logos_df = logos_df.fillna("")
            for _, row in logos_df.iterrows():
                t = str(row.get('Tema', '')).strip()
                s = str(row.get('SubTema', '')).strip()
                logo_val = str(row.get('Logo', '')).strip()
                if logo_val and t and s:
                    # Si es solo un nombre de archivo, completar con la URL de GitHub
                    if logo_val == "" or logo_val == "nan":
                        logo_url = ""
                    elif logo_val.startswith("http"):
                        logo_url = logo_val
                    else:
                        logo_url = "./imagenes/" + urllib.parse.quote(logo_val)
                    
                    if t not in logos_data: logos_data[t] = {}
                    logos_data[t][s] = logo_url
            print(f"Éxito: Leídos {len(logos_df)} registros de Logos.")

        # 2. PROCESAR BANNER
        # Carrusel o imagen destacada en la parte superior del sitio.
        banner_data = []
        banner_df = sheets.get('Banner', pd.DataFrame())
        if not banner_df.empty:
            banner_df = banner_df.fillna("")
            for _, row in banner_df.iterrows():
                if pd.isna(row.get('Titulo')) or str(row.get('Titulo')).strip() == "":
                    continue
                # Auto-completado de URL para la imagen del Banner
                banner_photo = str(row.get('Foto', '')).strip()
                if banner_photo == "" or banner_photo == "nan":
                    banner_img_url = "https://picsum.photos/1200/600"
                elif banner_photo.startswith("http"):
                    banner_img_url = banner_photo
                else:
                    banner_img_url = "./imagenes/" + urllib.parse.quote(banner_photo)

                banner_data.append({
                    "title": str(row.get('Titulo', '')).strip(),
                    "subtitle": str(row.get('Sub titulo', '')).strip(),
                    "image": banner_img_url,
                    "link": str(row.get('Original', '')).strip(),
                    "button_text": str(row.get('Boton', 'Saber Más')).strip()
                })
            print(f"Éxito: Leídos {len(banner_data)} elementos para el Banner.")

        # 3. PROCESAR TEMAS (CATEGORÍAS)
        # Cada hoja extra que no esté en 'system_sheets' se considera una categoría del blog.
        theme_sheets = [s for s in sheets.keys() if s not in system_sheets]
        
        # Mantener compatibilidad con nombres antiguos
        if 'Noticias' in sheets and 'Noticias' not in theme_sheets:
            theme_sheets.append('Noticias')

        # El orden de las pestañas en Excel define el orden en la botonera de la web.
        categories_order = theme_sheets.copy()

        for sheet_name in theme_sheets:
            df = sheets[sheet_name]
            if df.empty: continue
            
            # Normalizar nombres de columnas (quitar espacios accidentales)
            cols = [str(c).strip() for c in df.columns]
            if 'SubTema' not in cols and 'Tema' in cols:
                df = df.rename(columns={'Tema': 'SubTema'})
            
            # Asegurar que todas las columnas requeridas existan, aunque estén vacías
            for col in required_cols:
                if col not in df.columns:
                    df[col] = ""

            for _, row in df.iterrows():
                if pd.isna(row['Titulo']) or str(row['Titulo']).strip() == "":
                    continue

                # Lógica del botón: Si está vacío, detecta idioma y pone texto sugerido
                btn_text = str(row['Boton']).strip()
                if btn_text == "" or btn_text == "nan":
                    lang = detect_language(row['Original'])
                    btn_text = f"Ver Original [{lang}]"

                # Lógica de Foto/Miniatura: Auto-completa URL si es solo el nombre del archivo
                photo_val = str(row['Foto']).strip()
                if photo_val == "" or photo_val == "nan":
                    photo_url = "https://picsum.photos/600/400"
                elif photo_val.startswith("http"):
                    photo_url = photo_val
                else:
                    # Enlace a la carpeta de imágenes local
                    base_url = "./imagenes/"
                    photo_url = base_url + urllib.parse.quote(photo_val)

                # Detección de 'Resumen': Decide si el item aparece en la pantalla de inicio
                resumen_val = str(row['Resumen']).strip().lower()
                is_resumen = resumen_val == "1" or resumen_val == "1.0" or resumen_val == "true"

                # Lógica de Desactivación de Tarjeta y Botón
                disable_card_val = str(row.get('Desactivar Tarjeta', '')).strip().lower()
                disable_card = disable_card_val == "1" or disable_card_val == "1.0" or disable_card_val == "true"
                
                disable_btn_val = str(row.get('Desactivar Botón', '')).strip().lower()
                disable_btn = disable_btn_val == "1" or disable_btn_val == "1.0" or disable_btn_val == "true"

                item = {
                    "category": sheet_name,
                    "sub_category": str(row['SubTema']).strip(),
                    "title": str(row['Titulo']).strip(),
                    "summary": str(row['Sub titulo']).strip(),
                    "content": str(row['Spanish']).strip(),
                    "link": str(row['Original']).strip(),
                    "thumbnail": photo_url,
                    "button_text": btn_text,
                    "published": today,
                    "lang": detect_language(row['Original']),
                    "is_resumen": is_resumen,
                    "disable_card": disable_card,
                    "disable_btn": disable_btn
                }
                
                if item['link'] == "nan": item['link'] = "#"
                news_list.append(item)
            print(f"Éxito: Procesada hoja de tema: {sheet_name} ({len(df)} filas)")

        # 4. PROCESAR ENCABEZADO, PIE DE PÁGINA E IMAGEN DE EMPRESA
        header_df = sheets.get('Encabezado', pd.DataFrame())
        header_data = {}
        if not header_df.empty:
            row = header_df.iloc[0]
            header_data = {
                "title": str(row.get('Titulo', '')).strip(),
                "subtitle": str(row.get('Subtitulo', '')).strip(),
                "brand_black": str(row.get('Primera Linea Negra', '')).strip(),
                "brand_blue": str(row.get('Primera Linea Azul', '')).strip()
            }
        
        footer_df = sheets.get('Pie de Página', pd.DataFrame())
        footer_data = {}
        if not footer_df.empty:
            row = footer_df.iloc[0]
            footer_data = {
                "line1": str(row.get('Primera Linea', '')).strip(),
                "line2": str(row.get('Segunda Linea', '')).strip()
            }

        company_df = sheets.get('Imagen Empresa', pd.DataFrame())
        company_data = {"logo": "", "main_theme": "Resumen"}
        if not company_df.empty:
            row = company_df.iloc[0]
            logo_val = str(row.get('Logo', '')).strip()
            
            # Formatear la URL del logo de la empresa
            if logo_val == "" or logo_val == "nan":
                final_logo_url = ""
            elif logo_val.startswith("http"):
                final_logo_url = logo_val
            else:
                final_logo_url = "./imagenes/" + urllib.parse.quote(logo_val)
                
            company_data = {
                "logo": final_logo_url,
                "main_theme": str(row.get('Tema Principal', 'Resumen')).strip()
            }

        # 5. GENERACIÓN DEL JSON FINAL
        final_data = {
            "header": header_data,
            "footer": footer_data,
            "company": company_data,
            "banner": banner_data,
            "categories_order": categories_order,
            "subtheme_logos": logos_data,
            "news": news_list
        }

        os.makedirs(os.path.dirname(output_json), exist_ok=True)
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(final_data, f, ensure_ascii=False, indent=2)
            
        print(f"Éxito: Se procesaron {len(news_list)} items, {len(categories_order)} categorías y {len(banner_data)} banners.")

    except Exception as e:
        print(f"Error durante la transformación: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 1. Obtener datos (Excel) de Google Sheets
    data_source = get_excel_data(GOOGLE_SHEETS_URL, LOCAL_EXCEL)
    # 2. Transformar y guardar como JSON para la web
    transform_excel_to_json(data_source, "data/news.json")

