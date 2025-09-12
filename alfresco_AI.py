import requests
from requests.auth import HTTPBasicAuth
import json
import os

from PyPDF2 import PdfReader
import docx2txt

BASE_URL = "http://localhost:8080/alfresco/api/-default-/public/alfresco/versions/1"
USERNAME = "admin"
PASSWORD = "admin"
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def list_files():
    url = f"{BASE_URL}/nodes/-root-/children"
    response = requests.get(url, auth=HTTPBasicAuth(USERNAME, PASSWORD))
    response.raise_for_status()
    return response.json().get("list", {}).get("entries", [])

def download_file(node_id, file_name):
    url = f"{BASE_URL}/nodes/{node_id}/content?attachment=true"
    response = requests.get(url, auth=HTTPBasicAuth(USERNAME, PASSWORD), stream=True)
    response.raise_for_status()
    file_path = os.path.join(DOWNLOAD_DIR, file_name)
    with open(file_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return file_path

def extract_text(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    try:
        if ext == ".pdf":
            reader = PdfReader(file_path)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        elif ext in [".docx", ".doc"]:
            text = docx2txt.process(file_path)
        elif ext == ".txt":
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        else:
            text = "[Formato no soportado]"
    except Exception as e:
        text = f"[Error extrayendo texto: {e}]"
    return text.strip()

if __name__ == "__main__":
    entries = list_files()
    result_json = []

    for entry in entries:
        node = entry["entry"]
        node_id = node["id"]
        file_name = node["name"]
        is_file = node.get("isFile", False)

        if not is_file:
            print(f"Omitido (no es un archivo): {file_name}")
            continue

        print(f"Procesando: {file_name}")
        try:
            file_path = download_file(node_id, file_name)
            text = extract_text(file_path)
        except Exception as e:
            text = f"[Error descargando o procesando: {e}]"

        result_json.append({
            "nodeId": node_id,
            "nombre": file_name,
            "texto": text
        })

    print(json.dumps(result_json, indent=2, ensure_ascii=False))
6