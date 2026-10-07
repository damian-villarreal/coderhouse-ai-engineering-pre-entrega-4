"""Consulta de prueba: top-5 del recuperador híbrido."""

import sys

from config import configure_logging, load_settings
from retriever import RAGSystem

DEFAULT_QUESTION = "¿Para qué sirve un namespace en un índice Serverless de Pinecone?"


def main() -> None:
    configure_logging()
    settings = load_settings(require_embeddings=True)
    question = " ".join(sys.argv[1:]).strip() or DEFAULT_QUESTION
    system = RAGSystem.from_settings(settings)
    documents = system.retrieve(question)
    print(f"Consulta: {question}\n")
    if not documents:
        print("Sin resultados.")
        return
    for rank, document in enumerate(documents, start=1):
        metadata = document.metadata
        categories = ", ".join(metadata.get("categories", []))
        print(
            f"{rank}. {metadata.get('document_id')} "
            f"(página {metadata.get('page')}, fuente {metadata.get('source')})"
        )
        print(f"   categorías: {categories}")
        preview = " ".join(document.page_content.split())
        print(f"   {preview[:280]}")
        print()


if __name__ == "__main__":
    main()
