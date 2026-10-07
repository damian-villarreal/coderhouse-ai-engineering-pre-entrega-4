"""Cliente de embeddings: Gemini por defecto, OpenAI si se elige en .env."""

from langchain_core.embeddings import Embeddings

from config import Settings


def build_embeddings(settings: Settings) -> Embeddings:
    """Mismo modelo y dimensión para la ingesta y para la consulta."""
    if settings.embedding_provider == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        # Sin task_type fijo: embed_documents usa RETRIEVAL_DOCUMENT
        # y embed_query usa RETRIEVAL_QUERY.
        return GoogleGenerativeAIEmbeddings(
            model=settings.embedding_model,
            google_api_key=settings.gemini_api_key,
            output_dimensionality=settings.embedding_dimension,
        )

    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        model=settings.embedding_model,
        openai_api_key=settings.openai_api_key,
    )
