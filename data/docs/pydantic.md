# Pydantic v2: modelos, campos y validadores

Pydantic describe estructuras de datos con clases que heredan de `BaseModel`. Al instanciar el modelo, cada campo se valida y se coerza al tipo anotado. Si algo no cierra, Pydantic levanta `ValidationError` con el detalle de los campos rotos, en lugar de dejar pasar un objeto a medias.

## Field

`Field` agrega restricciones y documentación sobre un atributo. `min_length`, `ge`, `le` y `pattern` se evalúan después de la coerción de tipo. `description` y `examples` viajan a un esquema JSON cuando otra herramienta, como una API, exporta el modelo.

```python
from pydantic import BaseModel, Field

class Producto(BaseModel):
    nombre: str = Field(min_length=1, description="Nombre visible")
    precio: float = Field(ge=0, description="Precio en la moneda local")
    stock: int = Field(ge=0, le=10_000)
```

Un `precio` negativo o un `nombre` vacío no construyen el objeto. El default de un campo puede ser un valor o `default_factory` cuando el default es mutable, como una lista.

## field_validator

`field_validator` corre sobre uno o varios campos ya convertidos al tipo declarado. Sirve para reglas que el tipo solo no expresa: un correo en minúsculas, un código que tiene que existir en un conjunto, un string que hay que recortar. El modo `after` es el habitual. El decorador recibe el nombre del campo y puede aplicarse a más de uno.

```python
from pydantic import BaseModel, field_validator

class Usuario(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, value: str) -> str:
        normalizado = value.strip().lower()
        if "@" not in normalizado:
            raise ValueError("el email no tiene @")
        return normalizado
```

La regla vive junto al campo. No ve el resto del modelo de forma cómoda: si la condición compara dos atributos, este validador se queda corto.

## model_validator

`model_validator` corre sobre el modelo entero. Conviene usarlo en lugar de `field_validator` cuando la regla cruza campos: una fecha de fin que tiene que ser posterior a la de inicio, un descuento que solo es válido si hay un cupón, o un total que tiene que coincidir con la suma de las líneas. En modo `after` recibe la instancia ya armada y puede devolverla o levantar `ValueError`.

```python
from pydantic import BaseModel, model_validator

class Rango(BaseModel):
    inicio: int
    fin: int

    @model_validator(mode="after")
    def fin_posterior(self) -> "Rango":
        if self.fin < self.inicio:
            raise ValueError("fin tiene que ser mayor o igual que inicio")
        return self
```

El modo `before` recibe el dato crudo, antes de validar campo por campo, y sirve para adaptar un payload legado. No reemplaza a `field_validator` para normalizar un solo atributo: mezclar las dos responsabilidades vuelve opaco qué falló.

## ConfigDict y model_dump

`model_config = ConfigDict(...)` reemplaza la clase `Config` interna de la versión anterior. `extra="ignore"` descarta claves desconocidas; `extra="forbid"` las rechaza. `str_strip_whitespace` recorta strings sin escribir un validador por campo.

`model_dump()` exporta el modelo a un diccionario. `model_dump(mode="json")` deja valores que un `json.dumps` acepta, como fechas en ISO. `model_dump_json()` devuelve el string directamente. `model_validate` construye el modelo desde un diccionario y es el camino inverso.

Una práctica sana es dejar en `field_validator` las reglas de un campo y reservar `model_validator` para las que necesitan ver el objeto completo. `ValidationError` agrupa todos los fallos, así el llamador puede mostrarlos juntos en vez de corregir de a uno.

## model_validate y errores

`model_validate` es el constructor explícito desde un diccionario o desde un objeto con atributos. `model_validate_json` hace lo mismo desde un string JSON. Los dos devuelven la instancia o levantan `ValidationError`. Recorrer `error.errors()` da la ubicación del campo, el tipo de falla y el mensaje. Eso es lo que conviene mostrar en un formulario, en lugar de convertir la excepción en un 500 genérico.

`model_dump(exclude_none=True)` omite campos que quedaron en `None`. `model_dump(include={"nombre", "precio"})` recorta la salida cuando el consumidor no tiene que ver el resto. Ninguno de los dos vuelve a validar: la validación ya ocurrió al construir el modelo. Si hace falta una segunda pasada, se llama otra vez a `model_validate` con el diccionario resultante.

Los valores por defecto no pasan por `field_validator` en modo `after` salvo que se pida. Si un default también tiene que normalizarse, conviene generarlo con `default_factory` y una función que ya entregue el valor final, en lugar de confiar en que el validador lo va a ver.
