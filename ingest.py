"""Pipeline de ingesta: chunking, embeddings e inserción en Pinecone."""

import argparse
import json
import logging
from collections import Counter
from pathlib import Path

from langchain_core.documents import Document
from langchain_pinecone import PineconeVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import (
    CATALOG_PATH,
    CHUNK_OVERLAP_TOKENS,
    CHUNK_SIZE_TOKENS,
    CHUNKS_PATH,
    DATA_DIR,
    Settings,
    configure_logging,
    load_settings,
)
from embeddings import build_embeddings
from setup_index import clear_namespace, ensure_index

logger = logging.getLogger("ingest")


def load_catalog(path: Path = CATALOG_PATH) -> list[dict]:
    catalog = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(catalog, list) or not catalog:
        raise ValueError(f"El catálogo {path} tiene que ser una lista con documentos.")
    return catalog


def load_source_documents(catalog: list[dict] | None = None) -> list[Document]:
    """Carga los Markdown técnicos declarados en data/catalog.json."""
    items = catalog if catalog is not None else load_catalog()
    documents: list[Document] = []
    for item in items:
        document_id = item["document_id"]
        relative_path = item["path"]
        categories = list(item["categories"])
        source_path = DATA_DIR / relative_path
        if not source_path.is_file():
            raise FileNotFoundError(f"No existe el documento {source_path}.")
        text = source_path.read_text(encoding="utf-8").strip()
        if not text:
            raise ValueError(f"El documento {source_path} está vacío.")
        documents.append(
            Document(
                page_content=text,
                metadata={
                    "document_id": document_id,
                    "source": relative_path,
                    "categories": categories,
                },
            )
        )
    return documents


def build_chunks(documents: list[Document] | None = None) -> list[Document]:
    """Parte cada fuente en chunks de ~650 tokens y numera la página dentro del archivo.

    Los Markdown no tienen número de página: `page` es el índice del chunk
    (1, 2, 3...) dentro de ese documento. El texto queda en page_content;
    PineconeVectorStore lo copia a la metadata `text` en el upsert.
    """
    sources = documents if documents is not None else load_source_documents()
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=CHUNK_SIZE_TOKENS,
        chunk_overlap=CHUNK_OVERLAP_TOKENS,
    )
    chunks = splitter.split_documents(sources)
    page_by_document: Counter[str] = Counter()
    prepared: list[Document] = []
    for chunk in chunks:
        document_id = str(chunk.metadata["document_id"])
        page_by_document[document_id] += 1
        page = page_by_document[document_id]
        chunk_id = f"{document_id}::p{page}"
        metadata = {
            "document_id": document_id,
            "source": str(chunk.metadata["source"]),
            "page": page,
            "categories": list(chunk.metadata["categories"]),
            "chunk_id": chunk_id,
        }
        prepared.append(
            Document(page_content=chunk.page_content, metadata=metadata, id=chunk_id)
        )
    return prepared


def save_chunks(chunks: list[Document], path: Path = CHUNKS_PATH) -> None:
    """Persiste el corpus léxico que BM25 necesita en el proceso local.

    No reemplaza a Pinecone: el texto también viaja en la metadata del vector
    para no consultar una base relacional en cada búsqueda semántica.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            record = {"page_content": chunk.page_content, "metadata": chunk.metadata}
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    logger.info("Corpus léxico escrito en %s (%s chunks).", path, len(chunks))


def load_chunks(path: Path = CHUNKS_PATH) -> list[Document]:
    if not path.is_file():
        raise FileNotFoundError(
            f"No está {path}. Ejecutá `python ingest.py` para generar el corpus."
        )
    documents: list[Document] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            metadata = record["metadata"]
            documents.append(
                Document(
                    page_content=record["page_content"],
                    metadata=metadata,
                    id=metadata.get("chunk_id"),
                )
            )
    if not documents:
        raise ValueError(f"{path} no tiene chunks.")
    return documents


def _log_chunk_stats(chunks: list[Document]) -> None:
    counts = Counter(str(chunk.metadata["document_id"]) for chunk in chunks)
    for document_id, count in sorted(counts.items()):
        logger.info("  %s: %s chunks", document_id, count)


def upsert_chunks(chunks: list[Document], settings: Settings) -> None:
    pc = ensure_index(settings)
    embeddings = build_embeddings(settings)
    index = pc.Index(settings.index_name)
    vector_store = PineconeVectorStore(
        index=index,
        embedding=embeddings,
        namespace=settings.namespace,
        text_key="text",
    )
    ids = [str(chunk.metadata["chunk_id"]) for chunk in chunks]
    logger.info(
        "Subiendo %s chunks al índice '%s', namespace '%s'.",
        len(chunks),
        settings.index_name,
        settings.namespace,
    )
    vector_store.add_documents(documents=chunks, ids=ids)
    logger.info("Upsert terminado. El texto quedó en la metadata 'text'.")


def ingest(*, reset: bool = False) -> list[Document]:
    settings = load_settings(require_embeddings=True)
    chunks = build_chunks()
    logger.info(
        "Chunking: %s fragmentos (tamaño %s tokens, overlap %s).",
        len(chunks),
        CHUNK_SIZE_TOKENS,
        CHUNK_OVERLAP_TOKENS,
    )
    _log_chunk_stats(chunks)
    save_chunks(chunks)
    if reset:
        pc = ensure_index(settings)
        clear_namespace(pc, settings)
    upsert_chunks(chunks, settings)
    return chunks


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(
        description="Ingesta de documentos técnicos en un índice Pinecone serverless."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Borra el namespace antes de volver a insertar.",
    )
    args = parser.parse_args()
    chunks = ingest(reset=args.reset)
    print(f"Ingesta lista: {len(chunks)} chunks en Pinecone y en {CHUNKS_PATH.name}.")


if __name__ == "__main__":
    main()
