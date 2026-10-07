# LangChain LCEL: prompts, runnables y el operador pipe

LCEL (LangChain Expression Language) declara una cadena como composición de piezas `Runnable`. Cada pieza acepta una entrada, produce una salida y se puede invocar con `invoke` o `ainvoke`. El armado se lee de izquierda a derecha, igual que un pipeline de funciones.

## ChatPromptTemplate

`ChatPromptTemplate` arma la lista de mensajes que va a ver el modelo. `from_messages` recibe pares rol-plantilla. Las llaves de la plantilla, como `{texto}`, son variables que se completan en el `invoke`. El prompt no llama al modelo: solo formatea mensajes.

```python
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "Respondé en una oración, sin relleno."),
        ("human", "{texto}"),
    ]
)
```

Si falta una variable, el prompt falla antes de gastar una llamada. Conviene nombrar las variables igual que las claves del diccionario de entrada.

## El operador pipe

El operador `|` (pipe) conecta runnables. `prompt | modelo` significa: formatear los mensajes y pasárselos al chat model. El resultado de esa expresión es otro runnable, una `RunnableSequence`, que se ejecuta con un solo `invoke`. No hace falta una clase intermedia para unir los pasos.

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "Extraé el lenguaje mencionado."),
        ("human", "{texto}"),
    ]
)
modelo = ChatOpenAI(model="gpt-4o-mini", temperature=0)
cadena = prompt | modelo
respuesta = cadena.invoke({"texto": "El servicio está escrito en Python."})
```

`respuesta` es un mensaje de chat. Si el paso siguiente espera un string, se agrega un parser a la derecha del pipe, por ejemplo `prompt | modelo | parser`. El orden importa: el parser no puede ir antes del modelo porque todavía no hay texto generado.

## RunnableLambda y salida estructurada

`RunnableLambda` envuelve una función Python para que entre en la cadena. Sirve para un recorte, un cálculo o una adaptación del diccionario entre dos pasos. Tiene que ser pura respecto de la entrada que recibe: la traza de la cadena se vuelve difícil de leer si la lambda esconde I/O.

`with_structured_output` le pide al modelo un objeto que cumpla un esquema. El runnable que devuelve reemplaza al modelo pelado dentro del pipe: `prompt | modelo.with_structured_output(Esquema)`. La salida de `invoke` ya es una instancia de ese esquema, no un mensaje con JSON adentro.

## Reintentos

`with_retry(stop_after_attempt=3)` envuelve la cadena y vuelve a invocarla si el paso lanza. Tiene sentido cuando el fallo es transitorio o cuando un parser rechazó un JSON incompleto. No conviene reintentar errores de validación de la entrada del usuario: esos no se arreglan repitiendo la llamada.

Una cadena LCEL mínima, entonces, es un `ChatPromptTemplate` unido con pipe a un modelo. Cada pieza se puede probar sola con `invoke` antes de componerla, y la secuencia final se llama igual que cualquiera de sus partes.

## Probar cada pieza

Antes de unir el pipe, el `ChatPromptTemplate` se puede invocar con un diccionario y revisar los mensajes formateados. Si una llave no aparece, el error es del prompt, no del modelo. El modelo, a su vez, se puede invocar con una lista de mensajes ya armada para ver temperatura y límite de tokens sin pasar por la plantilla.

Cuando la cadena incluye `with_structured_output`, un fallo de esquema se ve en ese paso. `with_retry` lo vuelve a intentar, pero no cambia el prompt: si el esquema es imposible de llenar con la instrucción actual, los reintentos repiten el mismo error. Conviene achicar la plantilla o el esquema antes de subir `stop_after_attempt`.

`RunnableLambda` queda en el medio del pipe solo cuando transforma datos, por ejemplo para quedarse con el texto de un mensaje antes de un parser. Si la lambda llama a la red, la cadena deja de ser fácil de repetir. La secuencia final se invoca igual que una pieza suelta: un diccionario entra y el último runnable define qué sale.
