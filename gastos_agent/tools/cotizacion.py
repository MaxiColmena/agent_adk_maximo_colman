"""Herramienta para consultar la cotizacion del dolar en Argentina (API publica dolarapi.com)."""

import json
import urllib.error
import urllib.request

API_URL = "https://dolarapi.com/v1/dolares/{tipo}"
TIPOS = ["oficial", "blue", "bolsa", "contadoconliqui", "mayorista", "cripto", "tarjeta"]


def cotizacion_dolar(tipo: str = "oficial", monto_pesos: float = 0) -> dict:
    """Consulta en internet la cotizacion actual del dolar en Argentina y opcionalmente convierte pesos a dolares.

    Usar cuando el usuario pregunta por el precio del dolar o quiere saber cuanto
    representa un monto en pesos (por ejemplo, su total de gastos) en dolares.

    Args:
        tipo: Tipo de dolar: oficial, blue, bolsa, contadoconliqui, mayorista, cripto o tarjeta.
        monto_pesos: Monto en pesos a convertir a dolares usando el precio de venta. 0 = no convertir.

    Returns:
        dict con status, precios de compra y venta, fecha de actualizacion y,
        si se pidio, el monto convertido a dolares.
    """
    tipo_norm = str(tipo or "oficial").strip().lower().replace(" ", "").replace("_", "")
    if tipo_norm == "ccl":
        tipo_norm = "contadoconliqui"
    if tipo_norm not in TIPOS:
        return {"status": "error", "mensaje": f"Tipo de dolar '{tipo}' invalido. Opciones: {', '.join(TIPOS)}."}

    try:
        monto_pesos = float(monto_pesos or 0)
    except (TypeError, ValueError):
        return {"status": "error", "mensaje": f"El monto '{monto_pesos}' no es un numero valido."}
    if monto_pesos < 0:
        return {"status": "error", "mensaje": "El monto a convertir no puede ser negativo."}

    try:
        req = urllib.request.Request(API_URL.format(tipo=tipo_norm), headers={"User-Agent": "gastos-agent/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            datos = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"status": "error", "mensaje": f"El servicio de cotizaciones respondio con error {e.code}."}
    except (urllib.error.URLError, TimeoutError) as e:
        return {"status": "error", "mensaje": f"No se pudo conectar con el servicio de cotizaciones: {e}"}
    except json.JSONDecodeError:
        return {"status": "error", "mensaje": "El servicio de cotizaciones devolvio una respuesta invalida."}

    venta = datos.get("venta")
    if not venta:
        return {"status": "vacio", "mensaje": f"No hay cotizacion disponible para el dolar {tipo_norm}."}

    resultado = {
        "status": "ok",
        "tipo": datos.get("nombre", tipo_norm),
        "compra": datos.get("compra"),
        "venta": venta,
        "actualizado": datos.get("fechaActualizacion"),
    }
    if monto_pesos > 0:
        resultado["monto_pesos"] = round(monto_pesos, 2)
        resultado["monto_dolares"] = round(monto_pesos / float(venta), 2)
    return resultado
