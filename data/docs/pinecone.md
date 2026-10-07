# Pinecone serverless: índice, dimensión y namespace

Pinecone guarda vectores en un índice y responde búsquedas por similitud. En modo serverless el índice no reserva pods fijos: escala con el uso y se crea con `ServerlessSpec`, indicando nube y región. La métrica habitual para embeddings de texto normalizados es coseno.

## Dimensión del índice

La dimensión se fija al crear el índice y tiene que coincidir con el modelo de embeddings. `text-embedding-3-small` produce vectores de 1536 dimensiones. Si el índice se creó en 512 o 768, el upsert rechaza los vectores. No se puede cambiar la dimensión de un índice existente: hay que crear otro con el tamaño correcto o borrar el anterior.

```python
from pinecone import Pinecone, ServerlessSpec

pc = Pinecone(api_key="...")
if not pc.has_index("rag-tecnico"):
    pc.create_index(
        name="rag-tecnico",
        dimension=1536,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )
```

Hasta que `describe_index` marca el índice como listo, las escrituras fallan. Conviene esperarlo en el script de inicialización en lugar de reintentar el upsert a ciegas.

## Namespace

Un namespace es una partición lógica dentro del mismo índice. El namespace aísla conjuntos de vectores que no deberían mezclarse en una búsqueda: un inquilino, un idioma o un tipo de documento. La query sin namespace recorre el namespace por defecto y se vuelve ruidosa si ahí conviven datos distintos. Cada upsert y cada búsqueda tienen que nombrar el mismo namespace; si no, la consulta no ve los vectores recién cargados.

El nombre del índice (`INDEX_NAME`) identifica el contenedor físico. El namespace no crea otro índice ni cambia la dimensión: solo acota qué vectores participan de la búsqueda.

## Metadata

Cada vector puede llevar metadata. Ahí se guarda el texto original del chunk, la fuente, el número de página y etiquetas de categoría. Así la búsqueda devuelve el contenido sin ir a una base relacional. La metadata acepta strings, números, booleanos y listas de strings. No conviene meter el documento entero sin partir: un chunk de unos 500 a 800 tokens mantiene el contexto sin diluir el embedding.

Un identificador estable, por ejemplo `fastapi::p1`, permite reinsertar el mismo chunk sin duplicarlo. Borrar el namespace antes de una carga completa deja el índice alineado con el corpus local cuando los documentos cambiaron de forma grande.

## Consulta

La consulta embebe el texto con el mismo modelo usado en la carga y pide los vecinos más cercanos dentro del namespace. El `top_k` limita cuántos chunks vuelven. Filtros por metadata, como la fuente o una categoría, achican el espacio antes de ordenar por similitud. El score de coseno no es una probabilidad: sirve para ordenar, no para decidir solo con un umbral copiado de otro índice.

## Filtros, lotes y reingesta

Un filtro de metadata se manda junto con la búsqueda y se evalúa dentro del namespace. Si las etiquetas de categoría se guardaron como lista de strings, el filtro puede pedir que el vector tenga una de esas etiquetas. El filtro no corrige un namespace equivocado: si los vectores se escribieron en `tecnico` y la consulta mira el namespace por defecto, el resultado vuelve vacío aunque el filtro sea correcto.

Los upserts conviene mandarlos en lotes. Cada lote lleva id, vector y metadata. El id estable permite repetir la carga cuando cambia un párrafo: el mismo `document_id` y el mismo número de página pisan el vector anterior en lugar de dejar dos copias. Si el corpus cambió de forma grande, lo más simple es vaciar el namespace y volver a insertar. Borrar el índice entero no hace falta y obliga a esperar de nuevo a que el serverless quede listo.

Antes de la primera búsqueda después de un upsert, el índice serverless puede tardar un instante en reflejar los vectores nuevos. En un script de evaluación, lo prudente es correr la ingesta completa y después las preguntas, no mezclar las dos cosas en el mismo segundo. La dimensión, el modelo y el namespace tienen que ser los mismos en la carga y en la consulta. Cambiar solo uno de los tres alcanza para que el ranking deje de tener sentido.
