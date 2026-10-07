"""Precision@k y Recall@k sobre chunks recuperados.

Recall@k responde si el documento fuente esperado aparece en el top-k.
Precision@k mide qué fracción del top-k proviene de ese documento.
"""

from langchain_core.documents import Document


def is_useful(document: Document, expected_document_id: str) -> bool:
    return document.metadata.get("document_id") == expected_document_id


def precision_at_k(
    documents: list[Document],
    expected_document_id: str,
    k: int,
) -> float:
    """Porcentaje (0-1) de los k recuperados que pertenecen al documento esperado.

    El denominador es k, no la cantidad devuelta: un hueco cuenta como no útil.
    """
    if k < 1:
        raise ValueError("k tiene que ser >= 1.")
    top = documents[:k]
    hits = sum(1 for document in top if is_useful(document, expected_document_id))
    return hits / k


def recall_at_k(
    documents: list[Document],
    expected_document_id: str,
    k: int,
) -> float:
    """1.0 si el documento esperado está entre los k recuperados; 0.0 si no."""
    if k < 1:
        raise ValueError("k tiene que ser >= 1.")
    top = documents[:k]
    found = any(is_useful(document, expected_document_id) for document in top)
    return 1.0 if found else 0.0
