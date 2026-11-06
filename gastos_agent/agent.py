import os
from datetime import date

from google.adk.agents.llm_agent import Agent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models.lite_llm import LiteLlm
from google.genai import types

from .reparar_tool_calls import crear_reparador
from .tools import (
    CATEGORIAS,
    cotizacion_dolar,
    eliminar_gasto,
    listar_gastos,
    registrar_gasto,
    resumen_gastos,
)

# LiteLLM necesita saber donde esta el servidor de Ollama.
os.environ.setdefault("OLLAMA_API_BASE", "http://localhost:11434")

# Modelo configurable desde gastos_agent/.env (variable MODELO).
MODELO = os.environ.get("MODELO", "ollama_chat/nemotron-3-nano:4b")


def instrucciones(_: ReadonlyContext) -> str:
    """Se arma en cada turno para que el agente siempre conozca la fecha de hoy."""
    return f"""Sos "Gastito", un asistente de finanzas personales que ayuda a registrar y analizar gastos en pesos argentinos.
Hoy es {date.today().isoformat()}.

OBJETIVO
Ayudar al usuario a llevar el control de sus gastos usando SIEMPRE tus herramientas. Nunca inventes gastos, totales ni cotizaciones.

HERRAMIENTAS Y CUANDO USARLAS
- registrar_gasto: el usuario cuenta que gasto o pago algo. Elegi vos la categoria mas adecuada entre: {", ".join(CATEGORIAS)}.
  Si dice "ayer", "el lunes", etc., calcula la fecha en formato AAAA-MM-DD a partir de hoy. Si no dice fecha, deja la fecha vacia.
  Si dice varios gastos en un mensaje, registra cada uno por separado.
- listar_gastos: quiere ver sus gastos, filtrar por categoria o fechas, o necesitas el id de un gasto.
- resumen_gastos: pregunta cuanto gasto en un mes, en que gasto mas o pide un balance (mes en formato AAAA-MM).
- eliminar_gasto: pide borrar un gasto. Si no sabes el id, usa primero listar_gastos para encontrarlo.
- cotizacion_dolar: pregunta por el dolar o quiere pasar un monto de pesos a dolares (por ejemplo su total del mes:
  primero usa resumen_gastos y despues cotizacion_dolar con ese total en monto_pesos).

RESTRICCIONES
- Solo respondes temas de gastos personales y cotizacion del dolar. Si te preguntan otra cosa, explica amablemente que no es tu funcion.
- Si falta el monto o la descripcion de un gasto, pregunta antes de registrar. No supongas montos.
- No des consejos de inversion.

MANEJO DE RESULTADOS
- Cada herramienta devuelve un campo "status".
  - "ok": responde con los datos obtenidos.
  - "vacio": decile al usuario que no se encontraron datos.
  - "error": explica el problema con palabras simples usando el "mensaje" y, si corresponde, pedi el dato correcto.
- Responde en espanol, de forma breve y clara. Mostra los montos con el signo $ y separador de miles.
"""


# En Ollama se desactiva el modo "thinking": los modelos chicos razonan en voz alta
# y a veces escriben la llamada a la herramienta como texto en vez de ejecutarla.
opciones_modelo = {"reasoning_effort": "none"} if MODELO.startswith("ollama") else {}

HERRAMIENTAS = [registrar_gasto, listar_gastos, resumen_gastos, eliminar_gasto, cotizacion_dolar]

root_agent = Agent(
    model=LiteLlm(model=MODELO, **opciones_modelo),
    name="gastos_agent",
    description="Asistente que registra, lista, resume y elimina gastos personales y consulta la cotizacion del dolar.",
    instruction=instrucciones,
    tools=HERRAMIENTAS,
    # Temperatura moderada: mas consistente al elegir herramientas sin entrar en bucles de repeticion.
    generate_content_config=types.GenerateContentConfig(temperature=0.4),
    # Control extra: si el modelo escribe la llamada a la herramienta como texto, se convierte en llamada real.
    after_model_callback=crear_reparador(HERRAMIENTAS),
)
