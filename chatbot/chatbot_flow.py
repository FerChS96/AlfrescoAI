import os
import re
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv
load_dotenv(".env")

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from context_client import fetch_minimal_docs

UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b")

def call_llm_model():
    return ChatGroq(
        temperature=0.3,
        model=os.getenv("GROQ_MODEL", "gemma-2b-it"),
        api_key=os.getenv("GROQ_API_KEY"),
    )

def get_last_user_text(state: MessagesState) -> str:
    if not state.get("messages"):
        return ""
    humans = [m for m in state["messages"] if isinstance(m, HumanMessage)]
    if humans:
        return humans[-1].content
    return state["messages"][-1].content

def classify_intent(user_text: str) -> str:
    t = user_text.lower()
    keywords = ["documento", "documentos", "informe", "reporte", "archivo", "pdf", "ecg", "contrato", "expediente", "capítulo"]
    if any(k in t for k in keywords) or UUID_RE.search(user_text):
        return "doc_query"
    return "chit_chat"

def extract_context_ids(user_text: str, config: Optional[Dict[str, Any]]) -> List[str]:
    ids = set(UUID_RE.findall(user_text))
    cfg_ids = (config or {}).get("configurable", {}).get("context_ids")
    if isinstance(cfg_ids, list):
        ids.update([str(x) for x in cfg_ids if isinstance(x, str)])
    return list(ids)

def render_docs_for_prompt(docs: List[Dict[str, Any]], max_chars_per_doc: int = 8000) -> str:
    parts = []
    for i, d in enumerate(docs):
        name = d.get("name") or "(sin nombre)"
        title = d.get("title") or ""
        desc = d.get("description") or ""
        content = (d.get("content") or "")[:max_chars_per_doc]
        truncated = d.get("truncated", False)
        header = f"[DOCUMENTO {i+1} | name={name}{' | title='+title if title else ''}{' | desc='+desc if desc else ''}{' | truncado' if truncated else ''}]"
        parts.append(f"{header}\n{content}\n[FIN DOCUMENTO {i+1}]")
    return "\n-----\n".join(parts)

def answer_from_docs(state: MessagesState, docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    user_text = get_last_user_text(state)
    llm = call_llm_model()
    context_block = render_docs_for_prompt(docs)
    system_instructions = (
        "Eres Hannia. Responde únicamente con base en los documentos proporcionados. "
        "Si la respuesta no está explícita, di: 'No tengo suficiente información en los documentos'. "
        "Responde en español y sé concisa."
    )
    prompt = (
        f"{system_instructions}\n\n"
        f"Pregunta del usuario:\n{user_text}\n\n"
        f"Contexto documental:\n{context_block}\n\n"
        f"Respuesta:"
    )
    resp = llm.invoke(prompt)
    return {"messages": [AIMessage(content=resp.content)]}

def ask_for_document_ids(_: MessagesState) -> Dict[str, Any]:
    text = (
        "¿Quieres que consulte documentos para responder? "
        "Comparte el/los ID(s) del documento (UUID) o escribe: /doc <uuid> (puedes pasar varios separados por espacio)."
    )
    return {"messages": [AIMessage(content=text)]}

def small_talk(state: MessagesState) -> Dict[str, Any]:
    llm = call_llm_model()
    history_text = "\n".join([m.content for m in state.get("messages", [])])
    prompt = (
        "Eres Hannia, una experta en marketing digital que trabaja para VEQSUM.\n"
        "Contesta de forma útil y breve. Si no sabes, di: "
        "\"No estoy segura, pero puedo contactar a un experto para ayudarte\".\n\n"
        f"Historial:\n{history_text}\n\nRespuesta:"
    )
    resp = llm.invoke(prompt)
    return {"messages": [AIMessage(content=resp.content)]}

def node_classify(state: MessagesState) -> Dict[str, Any]:
    user_text = get_last_user_text(state)
    intent = classify_intent(user_text)
    return {"intent": intent}

def node_route_doc_or_chat(state: MessagesState, config: Optional[Dict[str, Any]] = None) -> str:
    intent = state.get("intent") or "chit_chat"
    if intent != "doc_query":
        return "chat"
    user_text = get_last_user_text(state)
    ids = extract_context_ids(user_text, config or {})
    state["context_ids"] = ids
    return "have_ids" if ids else "need_ids"

def node_load_context(state: MessagesState) -> Dict[str, Any]:
    ids: List[str] = state.get("context_ids") or []
    if not ids:
        return {"context_docs": []}
    docs = fetch_minimal_docs(ids, max_chars=50000)
    return {"context_docs": docs}

def node_answer_with_docs(state: MessagesState) -> Dict[str, Any]:
    docs = state.get("context_docs") or []
    if not docs:
        return ask_for_document_ids(state)
    return answer_from_docs(state, docs)

workflow = StateGraph(state_schema=MessagesState)
workflow.add_node("classify", node_classify)
workflow.add_node("load_context", node_load_context)
workflow.add_node("answer_docs", node_answer_with_docs)
workflow.add_node("ask_ids", ask_for_document_ids)
workflow.add_node("chat", small_talk)

workflow.add_edge(START, "classify")

def router(state: MessagesState, config: Optional[Dict[str, Any]] = None) -> str:
    return node_route_doc_or_chat(state, config)

workflow.add_conditional_edges(
    "classify",
    router,
    {
        "have_ids": "load_context",
        "need_ids": "ask_ids",
        "chat": "chat",
    },
)

workflow.add_edge("load_context", "answer_docs")

memory = MemorySaver()
app_graph = workflow.compile(checkpointer=memory)