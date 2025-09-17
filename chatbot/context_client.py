import os
import requests
from typing import List, Dict, Any

BACKEND_API_BASE = os.getenv("BACKEND_API_BASE", "http://localhost:8000").rstrip("/")

class ContextClientError(Exception):
    pass

def fetch_minimal_doc(node_id: str, max_chars: int = 50000) -> Dict[str, Any]:
    url = f"{BACKEND_API_BASE}/documents/{node_id}/minimal"
    params = {"maxChars": max_chars}
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, dict) or "content" not in data:
            raise ContextClientError(f"Respuesta inesperada para {node_id}: {data}")
        return data
    except requests.RequestException as e:
        raise ContextClientError(f"Error solicitando {url}: {e}") from e

def fetch_minimal_docs(node_ids: List[str], max_chars: int = 50000) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    for nid in node_ids:
        try:
            docs.append(fetch_minimal_doc(nid, max_chars=max_chars))
        except Exception as e:
            docs.append({"name": None, "title": None, "description": None, "content": "", "truncated": False, "_error": str(e)})
    return docs