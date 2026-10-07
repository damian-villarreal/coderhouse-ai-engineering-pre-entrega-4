"""Recuperador híbrido: similitud en Pinecone + BM25, fusionados por rango."""

import re
import unicodedata
import warnings

# BM25 vive en langchain-community. El paquete avisa que está en sunset;
# el import que pide la versión actual sigue siendo este.
warnings.filterwarnings(
    "ignore",
    message=r"`langchain-community` is being sunset.*",
    category=DeprecationWarning,
)

from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_pinecone import PineconeVectorStore

from config import Settings, load_settings
from embeddings import build_embeddings
from ingest import load_chunks
from setup_index import ensure_index, pinecone_client

# Peso parejo: el léxico rescata nombres propios y el vectorial, paráfrasis.
BM25_WEIGHT = 0.5
VECTOR_WEIGHT = 0.5


def tokenize(text: str) -> list[str]:
    """Minúsculas y sin acentos, para que BM25 matchee términos técnicos en español."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.findall(r"[a-z0-9_]+", ascii_text.lower())


class RAGSystem:
    """Encapsula un EnsembleRetriever (BM25 local + Pinecone en el namespace)."""

    def __init__(self, retriever: EnsembleRetriever, k: int) -> None:
        self.retriever = retriever
        self.k = k

    @classmethod
    def from_settings(cls, settings: Settings) -> "RAGSystem":
        chunks = load_chunks()
        ensure_index(settings)
        embeddings = build_embeddings(settings)
        index = pinecone_client(settings).Index(settings.index_name)
        vector_store = PineconeVectorStore(
            index=index,
            embedding=embeddings,
            namespace=settings.namespace,
            text_key="text",
        )
        bm25 = BM25Retriever.from_documents(
            chunks,
            preprocess_func=tokenize,
            k=settings.top_k,
        )
        vector_retriever = vector_store.as_retriever(search_kwargs={"k": settings.top_k})
        ensemble = EnsembleRetriever(
            retrievers=[bm25, vector_retriever],
            weights=[BM25_WEIGHT, VECTOR_WEIGHT],
            id_key="chunk_id",
        )
        return cls(retriever=ensemble, k=settings.top_k)

    @classmethod
    def from_env(cls) -> "RAGSystem":
        return cls.from_settings(load_settings(require_embeddings=True))

    def retrieve(self, query: str) -> list[Document]:
        """Devuelve los top-k documentos combinando búsqueda léxica y semántica."""
        cleaned = query.strip()
        if not cleaned:
            raise ValueError("La consulta está vacía.")
        documents = self.retriever.invoke(cleaned)
        return list(documents)[: self.k]
