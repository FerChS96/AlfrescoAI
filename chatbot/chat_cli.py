import os
import sys
import argparse
from typing import List
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from chatbot_flow import app_graph

load_dotenv(".env")

HELP_TEXT = """Comandos:
  /doc <uuid1> [uuid2 uuid3]   Fija uno o varios documentos como contexto.
  /show                        Muestra los IDs de documentos fijados.
  /clear                       Limpia el historial del hilo y documentos.
  /exit                        Sale.
Escribe cualquier otra cosa para conversar.
"""

def main():
    parser = argparse.ArgumentParser(description="Chat CLI (Groq + contexto Alfresco mínimo)")
    parser.add_argument("--thread", default="cli-thread", help="Thread ID para memoria conversacional")
    parser.add_argument("--ids", nargs="*", default=[], help="UUIDs iniciales de documentos para contexto")
    args = parser.parse_args()

    thread_id = args.thread
    context_ids: List[str] = list(args.ids)

    print("Chat CLI iniciado. Usa /exit para salir.")
    print(HELP_TEXT)
    while True:
        try:
            user = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSaliendo...")
            break

        if not user:
            continue

        if user.startswith("/exit"):
            print("Saliendo...")
            break

        if user.startswith("/clear"):
            # Reinicia el hilo (nuevo id) y limpia ids
            context_ids = []
            print("Historial e IDs de documentos limpiados.")
            # Cambiar thread id para forzar memoria nueva
            thread_id = f"cli-thread-{os.urandom(3).hex()}"
            continue

        if user.startswith("/doc"):
            parts = user.split()
            if len(parts) < 2:
                print("Uso: /doc <uuid1> [uuid2 uuid3]")
                continue
            context_ids = parts[1:]
            print(f"Context IDs = {', '.join(context_ids)}")
            continue

        if user.startswith("/show"):
            if context_ids:
                print(f"Context IDs actuales: {', '.join(context_ids)}")
            else:
                print("No hay IDs de documentos configurados. Usa /doc <uuid>.")
            continue

        # Mensaje normal → invocar grafo
        state = {"messages": [HumanMessage(content=user)]}
        config = {"configurable": {"thread_id": thread_id, "context_ids": context_ids}}
        out = app_graph.invoke(state, config=config)
        print("Bot:", out["messages"][-1].content)

if __name__ == "__main__":
    sys.exit(main())