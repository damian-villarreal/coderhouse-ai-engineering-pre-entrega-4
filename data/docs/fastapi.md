# FastAPI: rutas, dependencias y ciclo de vida

FastAPI es un framework para construir APIs HTTP en Python sobre ASGI. Una aplicación se declara con `FastAPI()`, y cada operación se cuelga de un path con decoradores como `@app.get` o `@app.post`. El servidor de desarrollo habitual es uvicorn, que importa el objeto `app` y atiende el tráfico asíncrono.

## APIRouter

Cuando la API crece, las rutas no viven todas en el mismo módulo. `APIRouter` agrupa endpoints de un dominio y después se monta en la aplicación con `include_router`. El argumento `prefix` evita repetir el segmento común, y `tags` agrupa esas rutas en la documentación OpenAPI.

```python
from fastapi import APIRouter, FastAPI

router = APIRouter(prefix="/items", tags=["items"])

@router.get("/{item_id}")
def leer_item(item_id: int) -> dict:
    return {"item_id": item_id}

app = FastAPI()
app.include_router(router)
```

El router no reemplaza a la aplicación: solo colecciona rutas. El objeto `app` sigue siendo el punto de entrada que uvicorn carga.

## Depends

`Depends` declara una dependencia que FastAPI resuelve antes de entrar al endpoint. Sirve para abrir una sesión de base, leer un usuario autenticado o validar un encabezado, sin mezclar esa lógica con el cuerpo de la ruta. La dependencia es una función callable. FastAPI la invoca, cachea el resultado dentro del mismo request y se lo pasa al endpoint por el parámetro anotado.

```python
from fastapi import Depends, FastAPI

app = FastAPI()

def obtener_token(x_token: str) -> str:
    if x_token != "secreto":
        raise ValueError("token inválido")
    return x_token

@app.get("/perfil")
def perfil(token: str = Depends(obtener_token)) -> dict:
    return {"token": token}
```

Si la dependencia falla, el endpoint no se ejecuta. Se pueden anidar: una dependencia puede recibir otra con el mismo `Depends`. Eso conviene para armar una cadena corta, por ejemplo "leer el header y después cargar el usuario", en lugar de un único callable enorme.

`Depends` también aplica a routers. Un `dependencies=[Depends(...)]` en el `APIRouter` corre para todas las rutas de ese grupo, útil cuando un prefijo entero exige autenticación.

## HTTPException

Los errores de negocio se expresan con `HTTPException`. Recibe `status_code` y `detail`. Un 404 indica que el recurso no existe; un 401, que la credencial no fue aceptada; un 422 lo arma FastAPI solo cuando el cuerpo no cumple el esquema. No hace falta capturar la excepción dentro del endpoint: FastAPI la convierte en una respuesta JSON.

```python
from fastapi import FastAPI, HTTPException

app = FastAPI()

@app.get("/items/{item_id}")
def leer_item(item_id: int) -> dict:
    if item_id < 1:
        raise HTTPException(status_code=404, detail="El item no existe")
    return {"item_id": item_id}
```

## response_model y CORS

`response_model` filtra la salida del endpoint contra un modelo. Aunque la función devuelva un diccionario con campos de más, la respuesta HTTP solo incluye lo declarado. Eso evita filtrar columnas internas. Para el navegador, `CORSMiddleware` habilita orígenes, métodos y encabezados. Se agrega con `app.add_middleware` y no cambia la firma de las rutas.

## Lifespan y tareas en segundo plano

El ciclo de vida de la aplicación se declara con un context manager `lifespan`. Ahí se abre el pool de conexiones al arrancar y se cierra al apagar, en lugar de hacerlo en cada request. `BackgroundTasks` programa trabajo después de enviar la respuesta, por ejemplo un envío de correo, sin bloquear al cliente. La tarea corre en el mismo proceso: no reemplaza una cola si el trabajo es largo o tiene que sobrevivir a un reinicio.

En resumen, una API FastAPI típica combina `APIRouter` para ordenar rutas, `Depends` para inyectar recursos del request, `HTTPException` para los fallos esperados y `lifespan` para lo que vive durante todo el proceso. El mismo `Depends` se puede reutilizar en varias rutas sin copiar la función.
