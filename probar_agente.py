"""Prueba rapida del agente por consola, mostrando que herramienta elige en cada paso.

Uso:
    python probar_agente.py                       -> corre los mensajes de ejemplo
    python probar_agente.py "gaste 3000 en taxi"  -> corre solo ese mensaje
"""

import asyncio
import sys

from dotenv import load_dotenv

load_dotenv("gastos_agent/.env")

from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

from gastos_agent.agent import root_agent  # noqa: E402

EJEMPLOS = [
    "Hoy gaste 4500 en un almuerzo y 800 de colectivo",
    "Mostrame mis gastos de transporte",
    "Cuanto gaste este mes y en que categoria gaste mas?",
    "Cuanto es mi total del mes en dolar blue?",
    "Registra un gasto de -200 en comida",
    "Borra el gasto con id 9999",
]


async def main(mensajes):
    runner = InMemoryRunner(agent=root_agent, app_name="gastos")
    sesion = await runner.session_service.create_session(app_name="gastos", user_id="demo")

    for texto in mensajes:
        print(f"\n\033[1mUsuario:\033[0m {texto}")
        contenido = types.Content(role="user", parts=[types.Part(text=texto)])
        async for evento in runner.run_async(user_id="demo", session_id=sesion.id, new_message=contenido):
            for parte in evento.content.parts if evento.content and evento.content.parts else []:
                if parte.function_call:
                    print(f"  -> herramienta: {parte.function_call.name}({dict(parte.function_call.args or {})})")
                elif parte.function_response:
                    print(f"  <- resultado:   {parte.function_response.response}")
                elif parte.text and evento.is_final_response():
                    print(f"\033[1mAgente:\033[0m {parte.text.strip()}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or EJEMPLOS))
