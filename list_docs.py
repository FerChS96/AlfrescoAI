import os
import io
import base64
import requests
from typing import Dict, List, Optional, Literal, Any, Tuple

# Extracción de texto
try:
    from pypdf import PdfReader 
except Exception:
    PdfReader = None
try:
    from docx import Document 
except Exception:
    Document = None
try:
    import chardet  
except Exception:
    chardet = None

ALFRESCO_BASE_URL = os.getenv("ALFRESCO_BASE_URL", "http://localhost:8080").rstrip("/")
ALFRESCO_USERNAME = os.getenv("ALFRESCO_USERNAME", "admin")
ALFRESCO_PASSWORD = os.getenv("ALFRESCO_PASSWORD", "admin")

SEARCH_URL = f"{ALFRESCO_BASE_URL}/alfresco/api/-default-/public/search/versions/1/search"
NODES_BASE = f"{ALFRESCO_BASE_URL}/alfresco/api/-default-/public/alfresco/versions/1/nodes"

DEFAULT_PAGE_SIZE = int(os.getenv("PAGE_SIZE", "50"))
DEFAULT_MAX_DOCS = int(os.getenv("MAX_DOCS", "20"))
DEFAULT_MAX_SIZE_MB = float(os.getenv("MAX_SIZE_MB", "15"))

# Límite de descarga del binario (para extraer texto) y límite de caracteres a devolver
MAX_DOWNLOAD_MB = float(os.getenv("MAX_DOWNLOAD_MB", "10"))
MAX_CHARS_DEFAULT = int(os.getenv("MAX_CHARS_DEFAULT", "50000"))

# Whitelist de tipos MIME textuales
DEFAULT_MIME_WHITELIST = [
    "application/pdf",
    "text/plain",
    "text/markdown",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/html",
    "text/csv",
    "application/json",
    "application/xml",
    "text/xml",
]

class AlfrescoSearchError(Exception):
    pass

def _auth_header() -> Dict[str, str]:
    token = base64.b64encode(f"{ALFRESCO_USERNAME}:{ALFRESCO_PASSWORD}".encode()).decode()
    return {"Authorization": f"Basic {token}"}

def _qname_encode(local: str) -> str:
    # Encodifica un string a QName (cm:my_x002d_site) para PATH en AFTS
    out = []
    for ch in local:
        if ch.isalnum() or ch == "_":
            out.append(ch)
        else:
            out.append(f"_x{ord(ch):04x}_")
    return "cm:" + "".join(out)

def _post_search(body: Dict, timeout: int = 30) -> Dict:
    headers = {**_auth_header(), "Content-Type": "application/json"}
    r = requests.post(SEARCH_URL, json=body, headers=headers, timeout=timeout)
    if r.status_code >= 400:
        raise AlfrescoSearchError(f"Search API error {r.status_code}: {r.text}")
    return r.json()

def _uploaded_only_filters(exclude_system_and_generated: bool = True) -> List[str]:
    filters = ["EXACTTYPE:'cm:content'"]
    if exclude_system_and_generated:
        filters += [
            "-TYPE:'cm:thumbnail'",
            "-TYPE:'cm:failedThumbnail'",
            "-ASPECT:'rn:rendition'",
            "-ASPECT:'cm:workingcopy'",
            'NOT PATH:"/sys:system//*"',
            'NOT PATH:"/app:company_home/app:dictionary//*"',
        ]
    return filters

def _mime_and_size_filters(
    mime_whitelist: Optional[List[str]],
    max_size_mb: Optional[float],
) -> List[str]:
    parts: List[str] = []
    if mime_whitelist:
        mimes_or = " OR ".join([f"=cm:content.mimetype:'{m}'" for m in mime_whitelist])
        parts.append(f"({mimes_or})")
    if max_size_mb and max_size_mb > 0:
        max_bytes = int(max_size_mb * 1024 * 1024)
        parts.append(f"cm:content.size:[1 TO {max_bytes}]")
    return parts

def _fields() -> List[str]:
    return ["id", "name", "nodeType", "content", "path", "properties", "aspectNames", "allowableOperations", "createdAt", "modifiedAt"]

def list_sites(
    max_items: int = DEFAULT_PAGE_SIZE,
    skip_count: int = 0,
    query_text: str = "",
) -> Dict[str, Any]:
    filters = ["EXACTTYPE:'st:site'"]
    if query_text.strip():
        q = query_text.replace("'", "\\'")
        filters.append(f"(cm:name:'{q}*' OR cm:title:'{q}*')")
    afts = " AND ".join(filters)

    body = {
        "query": {"query": afts, "language": "afts"},
        "paging": {"maxItems": max_items, "skipCount": skip_count},
        "sort": [{"type": "FIELD", "field": "{http://www.alfresco.org/model/content/1.0}name", "ascending": True}],
        "include": ["path", "properties"],
        "fields": _fields(),
    }
    data = _post_search(body)
    results = []
    for it in data.get("list", {}).get("entries", []):
        e = it["entry"]
        props = e.get("properties") or {}
        results.append({
            "id": e.get("name") or props.get("cm:name"),
            "title": props.get("{http://www.alfresco.org/model/content/1.0}title") or props.get("cm:title"),
            "description": props.get("{http://www.alfresco.org/model/content/1.0}description") or props.get("cm:description"),
            "visibility": props.get("{http://www.alfresco.org/model/site/1.0}siteVisibility") or props.get("st:siteVisibility"),
            "nodeId": e.get("id"),
            "path": (e.get("path") or {}).get("name", ""),
        })
    return {"count": len(results), "entries": results, "pagination": data.get("list", {}).get("pagination", {})}

def get_document_library_folder(site_id: str) -> Optional[Dict[str, Any]]:
    qn_site = _qname_encode(site_id)
    afts = " AND ".join([
        "EXACTTYPE:'cm:folder'",
        f'PATH:"/app:company_home/st:sites/{qn_site}/cm:documentLibrary"',
    ])
    body = {
        "query": {"query": afts, "language": "afts"},
        "paging": {"maxItems": 1, "skipCount": 0},
        "include": ["path", "properties"],
        "fields": _fields(),
    }
    data = _post_search(body)
    entries = data.get("list", {}).get("entries", [])
    if not entries:
        return None
    e = entries[0]["entry"]
    return {"id": e["id"], "name": e["name"], "path": (e.get("path") or {}).get("name", ""), "nodeType": e.get("nodeType")}

def list_folder_children(
    folder_id: str,
    item_type: Literal["files", "folders", "all"] = "all",
    max_items: int = DEFAULT_PAGE_SIZE,
    skip_count: int = 0,
    exclude_system_and_generated: bool = True,
) -> Dict[str, Any]:
    filters: List[str] = [f"PARENT:'workspace://SpacesStore/{folder_id}'"]
    if item_type == "files":
        filters += _uploaded_only_filters(exclude_system_and_generated)
    elif item_type == "folders":
        filters.append("EXACTTYPE:'cm:folder'")
    else:
        filters.append("(EXACTTYPE:'cm:folder' OR EXACTTYPE:'cm:content')")

    afts = " AND ".join(filters)
    body = {
        "query": {"query": afts, "language": "afts"},
        "paging": {"maxItems": max_items, "skipCount": skip_count},
        "sort": [{"type": "FIELD", "field": "{http://www.alfresco.org/model/content/1.0}name", "ascending": True}],
        "include": ["path", "properties", "aspectNames"],
        "fields": _fields(),
    }
    data = _post_search(body)

    results = []
    for it in data.get("list", {}).get("entries", []):
        e = it["entry"]
        is_folder = e.get("nodeType") == "cm:folder"
        content = e.get("content") or {}
        results.append({
            "id": e["id"],
            "name": e["name"],
            "isFolder": is_folder,
            "mimeType": content.get("mimeType") if not is_folder else "",
            "sizeInBytes": content.get("sizeInBytes") if not is_folder else None,
            "path": (e.get("path") or {}).get("name", ""),
        })
    return {"count": len(results), "entries": results, "pagination": data.get("list", {}).get("pagination", {})}

def search_documents(
    query_text: str = "",
    site_ids: Optional[List[str]] = None,
    folder_id: Optional[str] = None,
    max_items: int = DEFAULT_MAX_DOCS,
    skip_count: int = 0,
    mime_whitelist: Optional[List[str]] = None,
    max_size_mb: Optional[float] = None,
    include_snippets: bool = True,
    exclude_system_and_generated: bool = True,
) -> Dict[str, Any]:
    filters = _uploaded_only_filters(exclude_system_and_generated)
    filters += _mime_and_size_filters(mime_whitelist or DEFAULT_MIME_WHITELIST, max_size_mb or DEFAULT_MAX_SIZE_MB)

    if site_ids:
        site_paths = [f'PATH:"/app:company_home/st:sites/{_qname_encode(sid)}/cm:documentLibrary//*"' for sid in site_ids]
        filters.append(f"({' OR '.join(site_paths)})")

    if folder_id:
        filters.append(f"ANCESTOR:'workspace://SpacesStore/{folder_id}'")

    if query_text.strip():
        q = query_text.replace("'", "\\'")
        relevance = f"(cm:name:'{q}*')^6 OR (cm:title:'{q}*')^4 OR TEXT:'{q}'"
    else:
        relevance = "TEXT:'*'"

    afts = " AND ".join(filters + [f"({relevance})"])

    body: Dict[str, Any] = {
        "query": {"query": afts, "language": "afts"},
        "paging": {"maxItems": max_items, "skipCount": skip_count},
        "sort": [{"type": "SCORE"}],
        "include": ["path"],
        "fields": _fields(),
    }
    if include_snippets:
        body["highlight"] = {
            "prefix": "<em>",
            "postfix": "</em>",
            "mergeContiguous": True,
            "fields": [{"field": "cm:content"}],
            "snippetCount": 3,
        }

    data = _post_search(body)
    results = []
    for it in data.get("list", {}).get("entries", []):
        e = it["entry"]
        s = it.get("search", {}) or {}
        content = e.get("content") or {}
        results.append({
            "id": e.get("id"),
            "name": e.get("name"),
            "path": (e.get("path") or {}).get("name", ""),
            "mimeType": content.get("mimeType", ""),
            "sizeInBytes": content.get("sizeInBytes"),
            "score": s.get("score"),
            "snippets": (s.get("highlight", {}) or {}).get("content", []) if include_snippets else [],
        })
    return {"count": len(results), "entries": results, "pagination": data.get("list", {}).get("pagination", {})}

def get_node_metadata(node_id: str) -> Dict[str, Any]:
    """
    Obtiene el JSON del nodo (documento) directamente desde la API de nodos de Alfresco.
    No descarga contenido, solo metadatos.
    """
    url = f"{NODES_BASE}/{node_id}"
    params = {"include": "path,properties,allowableOperations,aspectNames"}
    headers = {**_auth_header()}
    r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("entry", data)

def _stream_content_bytes(node_id: str, max_bytes: int, expected_size: Optional[int] = None) -> Tuple[bytes, Optional[str]]:
    """
    Descarga el contenido del nodo en memoria, limitado a max_bytes.
    Si expected_size está disponible, ajusta el Range para evitar lecturas incompletas.
    Devuelve (bytes_leidos, mimeType). En errores de streaming, retorna lo ya leído.
    """
    import http.client as httplib

    url = f"{NODES_BASE}/{node_id}/content"
    params = {"attachment": "false"}

    def _read_response(resp: requests.Response, limit: int) -> Tuple[bytes, Optional[str]]:
        mime = resp.headers.get("Content-Type")
        buf = io.BytesIO()
        read = 0
        try:
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    break
                if read + len(chunk) > limit:
                    buf.write(chunk[: limit - read])
                    read = limit
                    break
                buf.write(chunk)
                read += len(chunk)
        except (requests.exceptions.ChunkedEncodingError,
                requests.exceptions.ContentDecodingError,
                requests.exceptions.StreamConsumedError,
                httplib.IncompleteRead,
                Exception):
            # Devolvemos lo que alcanzamos a leer
            return buf.getvalue(), mime
        return buf.getvalue(), mime

    # Primer intento: con Range (ajustado al tamaño esperado si lo sabemos)
    headers = {**_auth_header(), "Accept": "*/*"}
    if max_bytes > 0:
        end = max_bytes - 1
        if expected_size and expected_size > 0:
            end = min(end, expected_size - 1)
        headers["Range"] = f"bytes=0-{end}"

    try:
        with requests.get(url, headers=headers, params=params, stream=True, timeout=60) as r:
            if r.status_code == 416:
                # Range inválido: reintenta sin Range
                with requests.get(url, headers={**_auth_header(), "Accept": "*/*"}, params=params, stream=True, timeout=60) as r2:
                    r2.raise_for_status()
                    return _read_response(r2, max_bytes)
            r.raise_for_status()
            return _read_response(r, max_bytes)
    except requests.RequestException as e:
        # Error de transporte/HTTP a pesar de los intentos
        raise AlfrescoSearchError(f"Content request failed: {e}") from e
    
def _decode_text(data: bytes, fallback_encoding: str = "utf-8") -> str:
    if not data:
        return ""
    enc = fallback_encoding
    if chardet:
        try:
            det = chardet.detect(data)
            if det and det.get("encoding"):
                enc = det["encoding"]
        except Exception:
            pass
    try:
        return data.decode(enc, errors="replace")
    except Exception:
        return data.decode("utf-8", errors="replace")

def _extract_text_from_pdf(data: bytes) -> str:
    if not PdfReader:
        return "[PDF: pypdf no instalado]"
    try:
        reader = PdfReader(io.BytesIO(data))
        parts = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                parts.append("")
        return "\n".join(parts).strip()
    except Exception as e:
        return f"[PDF: error al extraer texto: {e}]"

def _extract_text_from_docx(data: bytes) -> str:
    if not Document:
        return "[DOCX: python-docx no instalado]"
    try:
        doc = Document(io.BytesIO(data))
        parts = [p.text for p in doc.paragraphs]
        return "\n".join(parts).strip()
    except Exception as e:
        return f"[DOCX: error al extraer texto: {e}]"

def get_document_with_content(node_id: str, max_chars: int = MAX_CHARS_DEFAULT) -> Dict[str, Any]:
    """
    Retorna el JSON del nodo + el campo contentText (texto extraído) y banderas de truncamiento.
    Nunca lanza 500: si algo falla, devuelve metadatos y una nota en contentNote.
    """
    meta = get_node_metadata(node_id)
    content_info = meta.get("content") or {}
    declared_mime = content_info.get("mimeType") or ""
    size_bytes = int(content_info.get("sizeInBytes") or 0)

    combined = dict(meta)
    combined.setdefault("contentNote", "")
    combined["contentText"] = ""
    combined["contentTextTruncated"] = False
    combined["contentBytesRead"] = 0
    combined["contentMaxDownloadMB"] = MAX_DOWNLOAD_MB
    combined["contentMaxChars"] = max_chars
    combined["contentMimeDetected"] = declared_mime
    combined["contentTotalSizeInBytes"] = size_bytes
    combined["contentDownloadTruncated"] = False

    if not declared_mime and size_bytes == 0:
        combined["contentNote"] = "El nodo no contiene binario o no expone mimeType/size."
        return combined

    max_download_bytes = int(MAX_DOWNLOAD_MB * 1024 * 1024)

    # Descargar binario (limitado), ajustando Range al tamaño esperado
    try:
        raw, resp_mime = _stream_content_bytes(node_id, max_download_bytes, expected_size=size_bytes if size_bytes > 0 else None)
    except AlfrescoSearchError as e:
        combined["contentNote"] = f"No se pudo descargar el contenido: {e}"
        return combined

    eff_mime = declared_mime or resp_mime or ""
    combined["contentMimeDetected"] = eff_mime
    combined["contentBytesRead"] = len(raw)
    combined["contentDownloadTruncated"] = bool(size_bytes and len(raw) < size_bytes)

    if combined["contentDownloadTruncated"] and eff_mime in (
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ):
        combined["contentNote"] = (
            f"Archivo más grande que el límite de descarga ({MAX_DOWNLOAD_MB} MB). "
            f"No se intentó extraer texto para evitar errores. Aumenta MAX_DOWNLOAD_MB o descarga completo."
        )
        return combined

    # Extraer texto según tipo
    text = ""
    note = combined["contentNote"] or ""
    if eff_mime.startswith("text/") or eff_mime in ("application/json", "application/xml", "text/xml", "text/csv", "text/html"):
        text = _decode_text(raw)
    elif eff_mime == "application/pdf":
        text = _extract_text_from_pdf(raw)
    elif eff_mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        text = _extract_text_from_docx(raw)
    elif eff_mime == "application/msword":
        note = (note + " " if note else "") + "El formato .doc clásico no está soportado para extracción en este demo."
    else:
        note = (note + " " if note else "") + f"Tipo MIME no soportado para extracción de texto: {eff_mime or 'desconocido'}"

    # Truncar por caracteres
    truncated = False
    if text and len(text) > max_chars:
        text = text[:max_chars]
        truncated = True

    combined["contentText"] = text
    combined["contentTextTruncated"] = bool(truncated)
    combined["contentNote"] = note
    return combined