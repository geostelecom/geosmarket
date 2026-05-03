@echo off
:: ==============================================================================
:: SCRIPT PRINCIPAL DE ACTUALIZACIÓN DEL BLOG (AgriCien / Bodeguita)
:: ==============================================================================

cd /d "%~dp0"

echo [1/3] Sincronizando imagenes desde Google Drive...
python sync_gdrive.py

echo.
echo [2/3] Descargando y procesando textos desde Google Sheets...
python transform_content.py

echo.
echo [3/3] Subiendo cambios a GitHub...
git add .
git commit -m "Actualizacion automatica: %date% %time%"
git push origin main

echo.
echo Proceso finalizado. Puedes cerrar esta ventana.
pause

