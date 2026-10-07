# Pre-entrega 4: Sistema RAG escalable en la nube con Pinecone

Módulo de recuperación híbrida: ingesta de documentos técnicos a un índice Pinecone Serverless, búsqueda que combina vectores y BM25, y evaluación con Precision@5 y Recall@5.

## Requisitos

- Python **3.12**
- Una API key de [Pinecone](https://app.pinecone.io/)
- Una API key de [Pinecone](https://app.pinecone.io/)
- Una API key de Gemini (embeddings `gemini-embedding-001`, dimensión **1536**)

Esta entrega no genera respuestas con un modelo de chat. `GEMINI_API_KEY` se usa solo para los embeddings. Si preferís OpenAI, poné `EMBEDDING_PROVIDER=openai`, `EMBEDDING_MODEL=text-embedding-3-small` y `OPENAI_API_KEY`.

## Estructura

```
.
├── embeddings.py          # Gemini (o OpenAI) con la dimensión del índice
├── setup_index.py         # Crea el índice serverless si no existe
├── ingest.py              # Chunking, metadata y upsert a Pinecone
├── retriever.py           # RAGSystem (EnsembleRetriever: BM25 + Pinecone)
├── evaluate.py            # Precision@5 y Recall@5 sobre el golden set
├── metrics.py             # Definición de las métricas
├── main.py                # Consulta de prueba (top-5)
├── data/
│   ├── catalog.json       # document_id, fuente y categorías
│   └── docs/              # Notas técnicas en Markdown
├── evaluation/
│   └── golden_set.json    # 5 preguntas con documento_id_esperado
├── requirements.txt
├── .env.example
└── README.md
```

`data/chunks.jsonl` lo genera `ingest.py`. Es el corpus en memoria de BM25. El texto de cada chunk también queda en la metadata `text` del vector, así la búsqueda semántica no consulta otra base.

## Instalación

Desde esta carpeta (`coderhouse-ai-engineering-pre-entrega-4`):

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Editá `.env` y completá `PINECONE_API_KEY` y `GEMINI_API_KEY`.

## Réplica del índice

El índice es serverless, con métrica coseno y dimensión 1536. El namespace `tecnico` separa este corpus de cualquier otro dato del mismo índice.

```bash
source .venv/bin/activate

# 1. Crear el índice si no existe y comprobar la dimensión
python setup_index.py

# 2. Partir los Markdown, embeberlos y subirlos al namespace
python ingest.py

# 3. Repetir la carga desde cero (borra el namespace antes del upsert)
python ingest.py --reset
```

Qué hace la ingesta:

1. Lee `data/catalog.json` y los Markdown de `data/docs/`.
2. Parte cada archivo con `RecursiveCharacterTextSplitter` en chunks de **650 tokens** y **80 de solapamiento** (rango pedido: 500–800). El encoding es `cl100k_base`, el de `text-embedding-3-small`.
3. Guarda en la metadata de cada vector: `text` (el chunk), `source`, `page`, `categories` y `document_id`. En estos Markdown `page` es el número de chunk dentro del archivo, desde 1.
4. Hace upsert con ids estables (`fastapi::p1`). Volver a correr la ingesta pisa esos ids.

Si el índice ya existe con otra dimensión, `setup_index.py` corta. No intentes subir vectores de 1536 a un índice de 512 o 768: creá otro `INDEX_NAME` o borrá el índice en la consola de Pinecone.

Región por defecto: `aws` / `us-east-1`. Si tu proyecto de Pinecone usa otra, cambiala en `PINECONE_CLOUD` y `PINECONE_REGION` antes de crear el índice.

## Consulta híbrida

`RAGSystem` arma un `EnsembleRetriever` con dos patas de peso igual:

- **BM25** (`BM25Retriever`) sobre `data/chunks.jsonl`, para nombres propios y términos exactos (`Depends`, `model_validator`, `PersistentClient`).
- **Pinecone** (`PineconeVectorStore`) en el namespace `tecnico`, para similitud semántica.

La fusión es reciprocal rank fusion. `retrieve()` devuelve los **top-5**.

```bash
python main.py "¿Para qué sirve Depends en FastAPI al declarar un endpoint?"
```

Sin argumentos, `main.py` pregunta por el namespace de un índice serverless.

## Evaluación

`evaluation/golden_set.json` tiene 5 preguntas. Cada una indica el `documento_id_esperado`.

Definiciones que usa `evaluate.py` (k = 5):

- Un chunk es útil si su `document_id` coincide con el documento esperado.
- **Recall@5** = 1 si ese documento aparece al menos una vez en el top-5; 0 si no.
- **Precision@5** = (chunks útiles en el top-5) / 5.

Cada nota se parte en pocos chunks. Si un documento solo tiene dos fragmentos, Precision@5 no puede pasar de 0.40: el denominador es 5 y no hay más chunks útiles. Recall@5 igual puede ser 1.00.

```bash
python evaluate.py
```

El reporte se imprime en consola. Con el índice `rag-tecnico` (namespace `tecnico`, embeddings de Gemini en 1536) el resultado fue:

```
--- Resumen ---
Preguntas: 5
Recall@5 promedio: 1.00
Precision@5 promedio: 0.40 (40%)
Aciertos (documento esperado en el top-5): 5/5
```

Las cinco preguntas trajeron el documento esperado. Precision@5 quedó en 0.40 porque cada nota tiene dos chunks y el denominador es 5.

## Variables de entorno

| Variable | Descripción | Ejemplo |
|---|---|---|
| `PINECONE_API_KEY` | Clave del proyecto Pinecone | |
| `GEMINI_API_KEY` | Clave para `gemini-embedding-001` | |
| `OPENAI_API_KEY` | Clave de OpenAI, solo si `EMBEDDING_PROVIDER=openai` | |
| `EMBEDDING_PROVIDER` | `gemini` u `openai` | `gemini` |
| `INDEX_NAME` | Nombre del índice serverless | `rag-tecnico` |
| `PINECONE_NAMESPACE` | Partición lógica dentro del índice | `tecnico` |
| `PINECONE_CLOUD` | Nube del índice nuevo | `aws` |
| `PINECONE_REGION` | Región del índice nuevo | `us-east-1` |
| `EMBEDDING_MODEL` | Modelo de embeddings | `gemini-embedding-001` |
| `EMBEDDING_DIMENSION` | Dimensión, tiene que coincidir con el índice | `1536` |
| `TOP_K` | Documentos que devuelve el recuperador | `5` |

## Uso programático

```python
from dotenv import load_dotenv
from retriever import RAGSystem

load_dotenv()
sistema = RAGSystem.from_env()
for documento in sistema.retrieve("¿Qué es un namespace en Pinecone?"):
    print(documento.metadata["document_id"], documento.page_content[:200])
```
