# agent_adk_maximo_colman — "Gastito", agente de gastos personales

Agente de inteligencia artificial desarrollado con **Python** y **Google ADK (Agent Development Kit)** que ayuda a llevar el control de los gastos personales en pesos argentinos.

El usuario le habla en lenguaje natural ("hoy gasté 4500 en un almuerzo y 800 de colectivo", "¿en qué gasté más este mes?", "¿cuánto es eso en dólar blue?") y el agente **decide qué herramienta usar**, la ejecuta y arma la respuesta con los resultados reales. No es un chatbot que solo genera texto: los datos se guardan en una base SQLite y la cotización del dólar se consulta en internet.

> Trabajo práctico — *Fundamentos de Agentes de Inteligencia Artificial* · Modelos de IA · Maximo Colman

---

## Problema que resuelve

Anotar gastos en una planilla es tedioso y por eso casi nadie lo sostiene. Con Gastito alcanza con contarle qué gastaste, como a una persona. El agente:

1. Interpreta el mensaje (monto, descripción, fecha: entiende "ayer", "el lunes", etc.).
2. Elige la categoría adecuada y registra el gasto.
3. Responde consultas: listados, totales del mes, la categoría con más gasto.
4. Convierte montos a dólares con la cotización del día.

---

## Componentes del agente

| Componente | Implementación |
|---|---|
| **Modelo de IA** | Modelo de Ollama conectado mediante **LiteLLM** (por defecto `ollama_chat/nemotron-3-nano:4b`, configurable en `.env`). |
| **Instrucciones** | Rol ("Gastito"), objetivo, cuándo usar cada herramienta, restricciones (solo temas de gastos, no inventar datos, no dar consejos de inversión) y cómo responder ante `ok` / `vacio` / `error`. Incluyen la fecha de hoy, que se recalcula en cada turno. |
| **Herramientas** | 5 herramientas con responsabilidades distintas (ver abajo). |
| **Contexto** | La fecha actual y el historial de la conversación (sesión de ADK). |
| **Estado / memoria** | Los gastos se guardan en SQLite (`gastos_agent/data/gastos.db`) y quedan entre sesiones. |
| **Controles** | Validación de argumentos en cada herramienta, temperatura moderada y un *callback* que repara llamadas a herramientas mal formadas (ver [Validaciones y controles](#validaciones-y-controles)). |

---

## Herramientas

| Herramienta | ¿Qué hace? | Argumentos |
|---|---|---|
| `registrar_gasto` | Guarda un gasto nuevo en la base de datos. | `descripcion`, `monto`, `categoria`, `fecha` (opcional, AAAA-MM-DD; si falta usa hoy) |
| `listar_gastos` | Lista gastos del más reciente al más antiguo, con filtros. Devuelve también el total. | `categoria`, `desde`, `hasta`, `limite` (todos opcionales) |
| `resumen_gastos` | Total del mes, cantidad de gastos, categoría con mayor gasto y desglose con porcentajes. | `mes` (AAAA-MM, opcional; si falta usa el mes actual) |
| `eliminar_gasto` | Borra un gasto por su id. | `gasto_id` |
| `cotizacion_dolar` | Consulta en internet ([dolarapi.com](https://dolarapi.com)) la cotización del dólar y, si se pide, convierte un monto en pesos a dólares. | `tipo` (oficial, blue, bolsa, contadoconliqui, mayorista, cripto, tarjeta), `monto_pesos` (opcional) |

Categorías válidas: `comida`, `transporte`, `servicios`, `salud`, `educacion`, `ocio`, `ropa`, `hogar`, `otros`.

Todas las herramientas devuelven un diccionario con un campo `status`:

- `"ok"`: la operación salió bien, con los datos.
- `"vacio"`: salió bien pero no hay resultados (por ejemplo, un mes sin gastos o un id que no existe).
- `"error"`: argumentos inválidos o falla interna, con un `mensaje` claro que el agente le explica al usuario.

Cada función tiene un **docstring** detallado: es lo que lee el modelo para saber cuándo usarla y qué argumentos pasar.

---

## Validaciones y controles

**Errores y argumentos inválidos** (devuelven `status: "error"`):

- Descripción vacía o de más de 200 caracteres.
- Monto no numérico, menor o igual a 0 o absurdamente grande.
- Categoría que no está en la lista (acepta mayúsculas y acentos: `Educación` se toma como `educacion`).
- Fechas con formato incorrecto, fechas futuras o un rango con `desde` posterior a `hasta`.
- Límite fuera de 1 a 100, id no numérico o negativo.
- Tipo de dólar inexistente, monto a convertir negativo.
- Sin conexión a internet o error de la API de cotizaciones, sin que el agente se caiga.
- Errores de la base de datos.

**Resultados vacíos** (devuelven `status: "vacio"`): listado sin coincidencias, mes sin gastos, id inexistente, cotización no disponible.

**Controles del agente:**

- Con Ollama se desactiva el modo *thinking* (`reasoning_effort="none"`) y se usa temperatura 0.4. Los modelos chicos razonaban en voz alta y entraban en bucles de repetición con temperaturas muy bajas.
- `reparar_tool_calls.py`: un `after_model_callback` de ADK. Si el modelo escribe la llamada a la herramienta como texto (`<tool_call>{...}</tool_call>`) en vez de ejecutarla, el callback la convierte en una llamada real. Solo acepta herramientas que existen en el agente. Es un problema que se observó con el modelo de 4B parámetros en conversaciones largas.

---

## Estructura del proyecto

```
agent_adk_maximo_colman/
├── gastos_agent/              # Carpeta del agente (la que detecta `adk web`)
│   ├── __init__.py
│   ├── agent.py               # Definición del agente: modelo, instrucciones, herramientas
│   ├── reparar_tool_calls.py  # Callback de control
│   ├── .env.example           # Configuración de ejemplo (copiar a .env)
│   ├── tools/
│   │   ├── gastos.py          # registrar, listar, resumir y eliminar gastos (SQLite)
│   │   └── cotizacion.py      # cotización del dólar (API web)
│   └── data/                  # Se crea sola: base de datos gastos.db
├── tests/
│   └── test_tools.py          # 31 pruebas automáticas de las herramientas
├── probar_agente.py           # Prueba por consola mostrando qué herramienta elige el agente
├── requirements.txt
└── README.md
```

---

## Instalación

Requisitos: **Python 3.12**, [uv](https://docs.astral.sh/uv/) y [Ollama](https://ollama.com) instalados.

1. Clonar el repositorio:

   ```bash
   git clone https://github.com/<tu-usuario>/agent_adk_maximo_colman.git
   cd agent_adk_maximo_colman
   ```

2. Crear y activar el entorno virtual:

   ```bash
   uv venv env --python 3.12
   env\Scripts\activate        # Windows
   source env/bin/activate     # Linux / Mac
   ```

3. Instalar las dependencias:

   ```bash
   uv pip install -r requirements.txt
   ```

4. Descargar el modelo y verificar que Ollama esté activo:

   ```bash
   ollama pull nemotron-3-nano:4b
   ollama ls
   ```

5. Crear el archivo de configuración:

   ```bash
   cp gastos_agent/.env.example gastos_agent/.env
   ```

   En `gastos_agent/.env` se puede cambiar el modelo con la variable `MODELO`. Sirve cualquier modelo de Ollama que soporte herramientas, por ejemplo `ollama_chat/qwen3:8b` o `ollama_chat/gemma4:31b-cloud`. Un modelo más grande elige las herramientas con más precisión.

---

## Uso

### Interfaz web de ADK

Desde la carpeta raíz del proyecto (no desde adentro de `gastos_agent`):

```bash
adk web
```

Abrir <http://localhost:8000>, elegir **gastos_agent** en el selector y empezar a chatear. En el panel **Events** se ve cada herramienta que llama el agente, con sus argumentos y su resultado.

### Por consola

```bash
python probar_agente.py
```

Ejecuta una conversación de ejemplo y muestra cada herramienta que elige el agente (`->`) y su resultado (`<-`). También se le puede pasar un mensaje propio:

```bash
python probar_agente.py "ayer gaste 12000 en la farmacia"
```

### Pruebas automáticas

```bash
python -m pytest -v
```

Prueban las herramientas sin usar el modelo: validaciones, filtros, resúmenes, resultados vacíos, la API de dólar simulada (no hace falta internet) y el parser del callback.

---

## Ejemplos de uso (pruebas realizadas con `nemotron-3-nano:4b`)

Las herramientas elegidas y sus argumentos son los que usó el agente en las pruebas. Las respuestas están resumidas.

| Pedido del usuario | Herramienta(s) que eligió el agente | Respuesta |
|---|---|---|
| "Hoy gasté 4500 en un almuerzo y 800 de colectivo" | `registrar_gasto` ×2 (comida y transporte) | Confirma los dos gastos registrados |
| "Mostrame mis gastos de transporte" | `listar_gastos(categoria="transporte")` | "Tienes un gasto de transporte: colectivo ($800)…" |
| "¿Cuánto gasté este mes y en qué categoría gasté más?" | `resumen_gastos(mes="2026-11")` | "Este mes gastaste $5.300. La categoría con mayor gasto es comida ($4.500, 84.9%)" |
| "¿Cuánto es mi total del mes en dólar blue?" | `cotizacion_dolar(tipo="blue", monto_pesos=5300)` | "Tu total de $5.300 equivale a US$ 3,41 (dólar blue)" |
| "Registrá un gasto de -200 en comida" | `registrar_gasto` → `status: error` | "El monto debe ser mayor a 0. ¿Querés registrar otro monto?" |
| "Borrá el gasto con id 9999" | `eliminar_gasto(gasto_id=9999)` → `status: vacio` | "No existe un gasto con id 9999." |
| "¿Cuánto está el dólar oficial?" (desde `adk web`) | `cotizacion_dolar(tipo="oficial")` | "El dólar oficial está a $1.520 (compra) y $1.570 (venta)…" |

---

## Limitaciones

- Con un modelo chico (4B parámetros) a veces pide confirmación de más (por ejemplo, la categoría de un gasto obvio) o formatea los números de forma inconsistente. Con un modelo más grande el comportamiento mejora.
- La cotización depende de que `dolarapi.com` esté disponible. Si no responde, el agente lo informa.
- Es un agente de un solo usuario: todos los gastos se guardan en la misma base local.
