"""Crea el índice serverless de Pinecone si todavía no existe."""

import logging
import time

from pinecone import Pinecone, ServerlessSpec
from pinecone.exceptions import NotFoundException

from config import Settings, configure_logging, load_settings

logger = logging.getLogger("setup_index")


def pinecone_client(settings: Settings) -> Pinecone:
    return Pinecone(api_key=settings.pinecone_api_key)


def _index_ready(description: object) -> bool:
    status = getattr(description, "status", None)
    if status is None:
        return False
    if isinstance(status, dict):
        return bool(status.get("ready"))
    return bool(getattr(status, "ready", False))


def wait_until_ready(pc: Pinecone, index_name: str, timeout_s: int = 180) -> None:
    """Un índice serverless no acepta upserts hasta que status.ready es verdadero."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        description = pc.describe_index(index_name)
        if _index_ready(description):
            logger.info("Índice '%s' listo.", index_name)
            return
        logger.info("Esperando a que '%s' quede listo...", index_name)
        time.sleep(2)
    raise TimeoutError(
        f"El índice '{index_name}' no quedó listo en {timeout_s} segundos."
    )


def ensure_index(settings: Settings) -> Pinecone:
    """Verifica dimensión y namespace-ready: crea el índice serverless si falta.

    Si el índice ya existe con otra dimensión, corta: subir embeddings de 1536
    a un índice de 512 o 768 falla en el upsert.
    """
    pc = pinecone_client(settings)
    if pc.has_index(settings.index_name):
        description = pc.describe_index(settings.index_name)
        dimension = int(description.dimension)
        if dimension != settings.embedding_dimension:
            raise ValueError(
                f"El índice '{settings.index_name}' tiene dimensión {dimension}, "
                f"pero {settings.embedding_model} exige {settings.embedding_dimension}. "
                "Usá otro INDEX_NAME o borrá el índice en la consola de Pinecone."
            )
        logger.info(
            "El índice '%s' ya existe (dimensión %s, métrica %s).",
            settings.index_name,
            dimension,
            getattr(description, "metric", "cosine"),
        )
        wait_until_ready(pc, settings.index_name)
        return pc

    logger.info(
        "Creando índice serverless '%s' (cloud=%s, region=%s, dimensión=%s).",
        settings.index_name,
        settings.cloud,
        settings.region,
        settings.embedding_dimension,
    )
    pc.create_index(
        name=settings.index_name,
        dimension=settings.embedding_dimension,
        metric="cosine",
        spec=ServerlessSpec(cloud=settings.cloud, region=settings.region),
        deletion_protection="disabled",
    )
    wait_until_ready(pc, settings.index_name)
    return pc


def clear_namespace(pc: Pinecone, settings: Settings) -> None:
    """Borra los vectores del namespace antes de una reingesta."""
    index = pc.Index(settings.index_name)
    try:
        index.delete(delete_all=True, namespace=settings.namespace)
    except NotFoundException:
        logger.info("El namespace '%s' todavía no tenía vectores.", settings.namespace)
        return
    logger.info("Namespace '%s' vaciado.", settings.namespace)


def main() -> None:
    configure_logging()
    settings = load_settings(require_embeddings=False)
    ensure_index(settings)
    print(
        f"Índice '{settings.index_name}' disponible. "
        f"Namespace de trabajo: '{settings.namespace}'."
    )


if __name__ == "__main__":
    main()
