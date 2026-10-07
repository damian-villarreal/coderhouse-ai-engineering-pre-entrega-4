"""Configuración del módulo RAG: claves, índice y rutas locales."""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DOCS_DIR = DATA_DIR / "docs"
CATALOG_PATH = DATA_DIR / "catalog.json"
CHUNKS_PATH = DATA_DIR / "chunks.jsonl"
GOLDEN_SET_PATH = ROOT / "evaluation" / "golden_set.json"

# gemini-embedding-001 admite 768, 1536 o 3072. 1536 coincide con el índice de la consigna.
DEFAULT_EMBEDDING_PROVIDER = "gemini"
DEFAULT_EMBEDDING_MODEL = "gemini-embedding-001"
DEFAULT_EMBEDDING_DIMENSION = 1536
GEMINI_EMBEDDING_DIMENSIONS = {768, 1536, 3072}
DEFAULT_INDEX_NAME = "rag-tecnico"
DEFAULT_NAMESPACE = "tecnico"
DEFAULT_TOP_K = 5

# Punto medio recomendado: chunks de ~500-800 tokens, con solapamiento.
CHUNK_SIZE_TOKENS = 650
CHUNK_OVERLAP_TOKENS = 80


@dataclass(frozen=True)
class Settings:
    pinecone_api_key: str
    gemini_api_key: str
    openai_api_key: str
    index_name: str
    namespace: str
    cloud: str
    region: str
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    top_k: int


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def load_settings(*, require_embeddings: bool = True) -> Settings:
    """Lee `.env` y valida las variables que pide la entrega."""
    load_dotenv(ROOT / ".env")

    pinecone_api_key = os.getenv("PINECONE_API_KEY", "").strip()
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not pinecone_api_key:
        raise ValueError("Falta PINECONE_API_KEY en .env.")

    provider = os.getenv("EMBEDDING_PROVIDER", DEFAULT_EMBEDDING_PROVIDER).strip().lower()
    if provider not in {"gemini", "openai"}:
        raise ValueError("EMBEDDING_PROVIDER tiene que ser 'gemini' u 'openai'.")

    if require_embeddings and provider == "gemini" and not gemini_api_key:
        raise ValueError(
            "Falta GEMINI_API_KEY en .env. "
            "Los embeddings usan gemini-embedding-001."
        )
    if require_embeddings and provider == "openai" and not openai_api_key:
        raise ValueError(
            "Falta OPENAI_API_KEY en .env. "
            "Los embeddings usan text-embedding-3-small."
        )

    index_name = os.getenv("INDEX_NAME", DEFAULT_INDEX_NAME).strip() or DEFAULT_INDEX_NAME
    namespace = os.getenv("PINECONE_NAMESPACE", DEFAULT_NAMESPACE).strip() or DEFAULT_NAMESPACE
    cloud = os.getenv("PINECONE_CLOUD", "aws").strip() or "aws"
    region = os.getenv("PINECONE_REGION", "us-east-1").strip() or "us-east-1"
    default_model = (
        DEFAULT_EMBEDDING_MODEL if provider == "gemini" else "text-embedding-3-small"
    )
    embedding_model = os.getenv("EMBEDDING_MODEL", default_model).strip() or default_model
    embedding_dimension = int(
        os.getenv("EMBEDDING_DIMENSION", str(DEFAULT_EMBEDDING_DIMENSION))
    )
    top_k = int(os.getenv("TOP_K", str(DEFAULT_TOP_K)))

    if embedding_dimension < 1:
        raise ValueError("EMBEDDING_DIMENSION tiene que ser un entero positivo.")
    if top_k < 1:
        raise ValueError("TOP_K tiene que ser un entero positivo.")
    if provider == "gemini" and embedding_dimension not in GEMINI_EMBEDDING_DIMENSIONS:
        raise ValueError(
            "gemini-embedding-001 admite dimensión 768, 1536 o 3072. "
            f"EMBEDDING_DIMENSION está en {embedding_dimension}."
        )
    if (
        provider == "openai"
        and embedding_model == "text-embedding-3-small"
        and embedding_dimension != DEFAULT_EMBEDDING_DIMENSION
    ):
        raise ValueError(
            f"text-embedding-3-small exige dimensión {DEFAULT_EMBEDDING_DIMENSION}. "
            f"EMBEDDING_DIMENSION está en {embedding_dimension}."
        )

    return Settings(
        pinecone_api_key=pinecone_api_key,
        gemini_api_key=gemini_api_key,
        openai_api_key=openai_api_key,
        index_name=index_name,
        namespace=namespace,
        cloud=cloud,
        region=region,
        embedding_provider=provider,
        embedding_model=embedding_model,
        embedding_dimension=embedding_dimension,
        top_k=top_k,
    )
