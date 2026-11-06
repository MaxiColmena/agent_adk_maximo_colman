"""Red de seguridad para modelos chicos de Ollama.

A veces el modelo escribe la llamada a una herramienta como TEXTO (por ejemplo
"<tool_call>{...}</tool_call>") en lugar de usar el mecanismo de tool calling.
Este callback (after_model_callback de ADK) detecta ese texto y lo convierte en
una llamada real a la herramienta, para que el agente no se quede trabado.
"""

import json
import re
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse
from google.genai import types

# Formato JSON:  <tool_call>{"name": "x", "arguments": {...}}</tool_call>
_RE_JSON = re.compile(r"<tool_call>\s*(\{.*?\})\s*(?:</tool_call>|$)", re.DOTALL)
# Formato XML:   <function=x><parameter=a>valor</parameter></function>
#           o:   <function name="x"><parameter name="a">valor</parameter></function>
_RE_FUNC = re.compile(r"""<function(?:=|\s+name=["']?)([\w\-]+)["']?>(.*?)(?:</function>|$)""", re.DOTALL)
_RE_PARAM = re.compile(
    r"""<parameter(?:=|\s+name=["']?)([\w\-]+)["']?>(.*?)(?:</parameter>|(?=<parameter)|$)""", re.DOTALL
)


def _valor(texto: str):
    texto = texto.strip()
    try:
        return json.loads(texto)
    except (json.JSONDecodeError, ValueError):
        return texto


def extraer_llamadas(texto: str) -> list[tuple[str, dict]]:
    """Devuelve [(nombre, argumentos), ...] encontrados en el texto."""
    llamadas = []
    for bloque in _RE_JSON.findall(texto):
        try:
            datos = json.loads(bloque)
        except json.JSONDecodeError:
            continue
        nombre = datos.get("name")
        args = datos.get("arguments", datos.get("parameters", {}))
        if isinstance(args, str):
            args = _valor(args)
        if nombre and isinstance(args, dict):
            llamadas.append((nombre, args))
    if not llamadas:
        for nombre, cuerpo in _RE_FUNC.findall(texto):
            args = {k: _valor(v) for k, v in _RE_PARAM.findall(cuerpo)}
            llamadas.append((nombre, args))
    return llamadas


def crear_reparador(herramientas: list):
    """Crea el callback sabiendo que herramientas existen (solo se aceptan esas)."""
    nombres_validos = {h.__name__ for h in herramientas}

    def reparar_tool_calls(callback_context: CallbackContext, llm_response: LlmResponse) -> Optional[LlmResponse]:
        contenido = llm_response.content
        if not contenido or not contenido.parts:
            return None
        if any(p.function_call for p in contenido.parts):
            return None  # el modelo ya llamo bien a la herramienta

        texto = "".join(p.text or "" for p in contenido.parts if not p.thought)
        if "<tool_call>" not in texto and "<function" not in texto:
            return None

        llamadas = [(n, a) for n, a in extraer_llamadas(texto) if n in nombres_validos]
        if llamadas:
            print(f"[reparar_tool_calls] llamada recuperada desde texto: {llamadas} | texto: {texto[:300]!r}")
            partes = [types.Part(function_call=types.FunctionCall(name=n, args=a)) for n, a in llamadas]
        else:
            # No se pudo interpretar: mejor pedir que reformule que mostrar etiquetas raras.
            print(f"[reparar_tool_calls] texto no interpretable: {texto[:300]!r}")
            partes = [types.Part(text="Perdon, tuve un problema procesando tu pedido. ¿Podes repetirlo con otras palabras?")]
        return LlmResponse(content=types.Content(role="model", parts=partes))

    return reparar_tool_calls
