import os
from typing import List, Optional, Literal
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()

from list_docs import (
    list_sites,
    get_document_library_folder,
    list_folder_children,
    search_documents,
    get_node_metadata,
    get_document_with_content,
    DEFAULT_PAGE_SIZE,
    DEFAULT_MAX_DOCS,
    MAX_CHARS_DEFAULT,
)

app = FastAPI(title="Alfresco Search Backend", version="1.2.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static", html=True), name="static")

@app.get("/")
def root():
    return FileResponse("static/index.html")

@app.get("/sites")
def api_list_sites(
    maxItems: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=200),
    skipCount: int = Query(0, ge=0),
    q: str = Query("", description="Filtro por nombre/título del site"),
):
    try:
        return list_sites(max_items=maxItems, skip_count=skipCount, query_text=q)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sites/{siteId}/document-library")
def api_get_document_library(siteId: str):
    try:
        dl = get_document_library_folder(siteId)
        if not dl:
            raise HTTPException(status_code=404, detail="documentLibrary no encontrada para el site")
        return dl
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/folders/{folderId}/children")
def api_list_folder_children(
    folderId: str,
    type: Literal["files", "folders", "all"] = Query("all"),
    maxItems: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=200),
    skipCount: int = Query(0, ge=0),
    excludeSystemAndGenerated: bool = Query(True),
):
    try:
        return list_folder_children(
            folder_id=folderId,
            item_type=type,
            max_items=maxItems,
            skip_count=skipCount,
            exclude_system_and_generated=excludeSystemAndGenerated,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/search/documents")
def api_search_documents(
    q: str = Query("", description="Nombre del archivo o texto libre"),
    siteIds: Optional[str] = Query(None, description="CSV de site IDs"),
    folderId: Optional[str] = Query(None, description="Node ID de carpeta (búsqueda recursiva)"),
    maxItems: int = Query(DEFAULT_MAX_DOCS, ge=1, le=200),
    skipCount: int = Query(0, ge=0),
    includeSnippets: bool = Query(True),
):
    try:
        sites = [s.strip() for s in siteIds.split(",")] if siteIds else None
        return search_documents(
            query_text=q,
            site_ids=sites,
            folder_id=folderId,
            max_items=maxItems,
            skip_count=skipCount,
            include_snippets=includeSnippets,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents/{nodeId}")
def api_get_document_metadata(nodeId: str):
    try:
        return get_node_metadata(nodeId)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents/{nodeId}/full")
def api_get_document_with_content(
    nodeId: str,
    maxChars: int = Query(MAX_CHARS_DEFAULT, ge=5000, le=500000, description="Máx. caracteres del texto a devolver"),
):
    """
    Devuelve metadatos + contenido textual extraído (contentText), con truncamiento controlado.
    Nunca devuelve 500 por problemas de descarga/parseo: el backend empaqueta la nota en contentNote.
    """
    try:
        return get_document_with_content(nodeId, max_chars=maxChars)
    except Exception as e:
        # Último recurso: 500 con detalle (no debería activarse ahora)
        raise HTTPException(status_code=500, detail=str(e))