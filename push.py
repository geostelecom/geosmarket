import os
import subprocess
from dotenv import load_dotenv

# Cargar variables
load_dotenv()

SITE_NAME = os.getenv("SITE_NAME", "geosmarket")
GIT_REPO = os.getenv("GIT_REPO", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

if not GITHUB_TOKEN or not GIT_REPO:
    print("Error: GITHUB_TOKEN o GIT_REPO no configurados en .env")
    exit(1)

# Construir URL con token
# https://TOKEN@github.com/USER/REPO.git
auth_repo = GIT_REPO.replace("https://", f"https://{GITHUB_TOKEN}@")

def run(cmd):
    print(f"Ejecutando: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
    else:
        print(result.stdout)

print(f"--- Desplegando {SITE_NAME} ---")

# Comandos de Git
run("git add .")
run('git commit -m "Update from parameter sheet"')
run(f"git remote set-url origin {auth_repo}")
run("git branch -M main")
run("git push -u origin main --force")

print("--- Proceso completado ---")
