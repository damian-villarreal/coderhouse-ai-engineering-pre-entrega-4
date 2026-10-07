# ChromaDB: cliente persistente y colecciones locales

ChromaDB es una base vectorial que puede correr en el mismo proceso que la aplicación. No hace falta un servicio aparte para un prototipo: el cliente abre un directorio del disco, crea una colección y guarda ahí embeddings, documentos y metadata.

## PersistentClient

`PersistentClient` abre o crea el almacén en `persist_directory`. Esa ruta es la que hay que conservar entre ejecuciones. Si el proceso vuelve a construir el cliente apuntando al mismo directorio, la colección sigue ahí y no hace falta recalcular embeddings. Un cliente en memoria, en cambio, pierde los datos al terminar el proceso.

```python
import chromadb

cliente = chromadb.PersistentClient(path="./vectorstore")
coleccion = cliente.get_or_create_collection(name="manuales")
```

`get_or_create_collection` devuelve la colección si el nombre ya existe y la crea si no. Conviene chequear ese nombre antes de volver a insertar todo el corpus: reindexar en cada arranque repite costo y puede duplicar ids si no se controlan.

## Documentos, ids y metadata

`collection.add` recibe en paralelo los textos, los ids y, si hace falta, embeddings ya calculados o metadata. El id es la clave del registro. Reusar el mismo id actualiza el vector en lugar de sumar otro. La metadata guarda la fuente y el número de fragmento para citar el origen en la respuesta.

```python
coleccion.add(
    ids=["nota-p1"],
    documents=["El fragmento describe cómo abrir el almacén local."],
    metadatas=[{"source": "docs/nota.md", "page": 1}],
)
```

Si no se pasan embeddings, la colección usa la función de embedding con la que fue creada. Indexar con una función y consultar con otra deja las distancias sin sentido: el modelo de la carga y el de la búsqueda tienen que ser el mismo.

## Consulta

`collection.query` toma un texto o un vector y devuelve los `n_results` más cercanos. La respuesta trae documentos, metadatas y distancias alineados por posición. Un `n_results` entre 3 y 5 alcanza para armar el contexto de una respuesta; subir mucho ese número mete fragmentos poco relacionados y alarga el prompt.

`where` filtra por metadata antes de recortar el ranking. Sirve, por ejemplo, para quedarse con una sola fuente. El directorio `persist_directory` se puede versionar o borrar: borrarlo equivale a vaciar el índice local y obliga a correr de nuevo la ingesta.

ChromaDB en disco cubre el caso de un solo proceso y un corpus chico. El directorio local no se comparte entre máquinas salvo que se copie entero. Para eso el flujo es el mismo: `PersistentClient` con la ruta, `get_or_create_collection` y `query` con el mismo embedding de la carga.

## Cuándo no volver a indexar

Abrir `PersistentClient` sobre un `persist_directory` que ya tiene la colección es suficiente para consultar. Recalcular embeddings en cada arranque solo tiene sentido si cambió un archivo fuente o si se reemplazó la función de embedding. Una marca simple es guardar, junto al directorio, la lista de archivos y un hash: si el hash coincide, se salta el `add`.

Los ids tienen que ser deterministas. Si cada ejecución inventa un id nuevo, la colección crece con copias del mismo párrafo y la búsqueda devuelve duplicados. Borrar la colección con `delete_collection` y crearla de nuevo es el camino cuando el esquema de metadata cambió. Borrar el directorio a mano equivale a lo mismo, siempre que ningún proceso tenga el cliente abierto.

La distancia que devuelve `query` depende de la configuración de la colección, que se elige al crearla. No se compara un umbral tomado de otro proyecto sin mirar esa configuración. Para armar el contexto de una respuesta alcanza con mirar `documents` y `metadatas` de los primeros `n_results`, y descartar el resto. Si la colección está vacía, `query` no inventa textos: devuelve listas vacías y el llamador tiene que decir que no hay contexto. El directorio de `persist_directory` tiene que existir o poder crearse: si el proceso no tiene permiso de escritura, `PersistentClient` falla al abrir y no llega a crear la colección. Conviene resolver esa ruta al arrancar, antes de intentar una consulta.
