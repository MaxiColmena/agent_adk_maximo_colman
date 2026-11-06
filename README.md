# agent_adk_maximo_colman

Agente de inteligencia artificial hecho con **Python** y **Google ADK (Agent Development Kit)** que responde preguntas sobre **programación**.

El agente no solo genera texto con el modelo: **decide qué herramienta usar** según lo que le pide el usuario.

- Primero busca en una **base de datos vectorial** (Chroma) con información que el usuario fue guardando.
- Si ahí no encuentra lo necesario, **busca en internet** (DuckDuckGo).
- Cuando el usuario se lo pide, **guarda información nueva** en la base de datos para usarla después.

> Actividad práctica — *Fundamentos de Agentes de Inteligencia Artificial* · Modelos de IA · Maximo Colman

---

## Componentes del agente

| Componente | Implementación |
|---|---|
| **Modelo de IA** | `gemma4:31b-cloud` de Ollama, conectado a ADK mediante **LiteLLM** (`LiteLlm("ollama_chat/gemma4:31b-cloud")`). |
| **Instrucciones** | Rol (asistente de programación), objetivo (responder con información real obtenida con las herramientas), orden de uso de las herramientas y restricciones (solo programación, no inventar, avisar los errores, indicar la fuente). |
| **Herramientas** | 4 herramientas con responsabilidades distintas (ver abajo). |
| **Contexto** | Los fragmentos recuperados de la base vectorial o los resultados de internet. |
| **Memoria** | La base de datos vectorial Chroma (`./vector_store`) guarda la información entre sesiones. |
| **Controles** | Cada herramienta valida sus argumentos y avisa cuando no hay resultados. |

---

## Herramientas

Están en [`tools/tools.py`](tools/tools.py). Cada una tiene un **docstring**, que es la descripción que lee el modelo para saber cuándo usarla y qué argumentos recibe.

| Herramienta | ¿Qué hace? | Argumentos |
|---|---|---|
| `web_search` | Busca en internet con DuckDuckGo (biblioteca `ddgs`). | `query`, `max_results` (1 a 10, por defecto 5) |
| `index_data` | Divide un texto en fragmentos (`RecursiveCharacterTextSplitter`, 500 caracteres con 50 de solapamiento), genera embeddings con `nomic-embed-text` y los guarda en Chroma. | `query` (texto a guardar), `collection_name` |
| `list_collection` | Lista las colecciones que existen en la base vectorial. | — |
| `retrieval` | Busca en una colección los fragmentos más parecidos a la consulta (búsqueda por similitud con puntaje de relevancia). | `query`, `collection_name`, `k` (1 a 10, por defecto 5) |

### Validación de errores, argumentos inválidos y resultados vacíos

| Caso | Respuesta de la herramienta |
|---|---|
| Consulta o texto vacío | `Error: la consulta no puede estar vacia.` / `Error: no hay texto para indexar.` |
| Nombre de colección inválido (vacío, con espacios, menos de 3 caracteres, etc.) | `Error: nombre de coleccion invalido...` |
| `max_results` o `k` fuera de rango | `Error: ... debe ser un numero entero entre 1 y 10.` |
| La colección no existe | `Error: la coleccion 'x' no existe. Colecciones disponibles: [...]` |
| Sin resultados en internet | `No se encontraron resultados en internet para esa consulta.` |
| Base vectorial vacía | `No hay colecciones en la base de datos vectorial.` |
| Búsqueda sin documentos | `No se encontraron documentos relacionados en la coleccion.` |
| Error inesperado (sin internet, Ollama apagado, etc.) | Se captura con `try/except` y se devuelve el mensaje del error, así el agente no se cae. |

La instrucción le indica al agente que, si una herramienta devuelve un mensaje que empieza con "Error", se lo explique al usuario con palabras simples.

---

## Estructura del proyecto

```
agent_adk_maximo_colman/
├── agent/              # Creado con `adk create agent`
│   ├── __init__.py
│   └── agent.py        # Modelo, instrucciones y herramientas del agente
├── tools/
│   ├── __init__.py
│   └── tools.py        # web_search, index_data, list_collection, retrieval
├── requirements.txt
└── README.md
```

La carpeta `vector_store/` se crea sola la primera vez que se guarda información.

---

## Instalación

Requisitos: Python, [uv](https://docs.astral.sh/uv/) y [Ollama](https://ollama.com).

1. Clonar el repositorio y entrar a la carpeta:

   ```bash
   git clone https://github.com/MaxiColmena/agent_adk_maximo_colman.git
   cd agent_adk_maximo_colman
   ```

2. Crear y activar el entorno virtual:

   ```bash
   uv venv env && env\Scripts\activate      # Windows
   uv venv env && source env/bin/activate   # Linux
   ```

3. Instalar las dependencias:

   ```bash
   uv pip install -r requirements.txt
   ```

4. Preparar Ollama. `gemma4:31b-cloud` es un modelo de la nube de Ollama, así que hay que iniciar sesión una vez:

   ```bash
   ollama signin
   ollama pull gemma4:31b-cloud
   ollama pull nomic-embed-text
   ollama ls
   ```

   `ollama ls` debería mostrar los dos modelos.

---

## Uso

Desde la carpeta raíz del proyecto:

```bash
adk web
```

Abrir <http://localhost:8000>, elegir **agent** en el selector y escribir. En el panel **Events** se ve qué herramienta usa el agente en cada paso, con sus argumentos y su resultado.

### Ejemplos (pruebas realizadas)

| Pedido del usuario | Herramientas que usó el agente | Resultado |
|---|---|---|
| "Guarda en la base de datos: En Python, un decorador es una función que…" | `index_data` (colección `programacion`) | "He guardado la información… en la colección programacion" |
| "¿Qué es un decorador en Python según mi base de datos?" | `retrieval` | Responde con el fragmento guardado e indica *Fuente: base de datos vectorial* |
| "¿Qué es una list comprehension en Python?" | `list_collection` → `retrieval` | Responde con la información de la base vectorial |
| "¿Cuál es la última versión estable de Django?" | `list_collection` → `retrieval` (no encuentra nada útil) → `web_search` | Responde con la versión encontrada e indica *Fuente: internet* |
| "Buscá en la colección java qué es una interfaz" | `retrieval` → error | "No pude encontrar la información porque la colección java no existe. Las disponibles son: programacion" |
| "¿Cuál es la capital de Francia?" | ninguna | Explica que solo responde preguntas de programación |
