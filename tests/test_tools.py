"""Pruebas de las herramientas (sin usar el modelo de IA).

Ejecutar con:  python -m pytest -v
"""

from datetime import date, timedelta
from unittest.mock import patch

import pytest

from gastos_agent.tools import cotizacion, gastos
from gastos_agent.tools import (
    cotizacion_dolar,
    eliminar_gasto,
    listar_gastos,
    registrar_gasto,
    resumen_gastos,
)


@pytest.fixture(autouse=True)
def db_temporal(tmp_path, monkeypatch):
    """Cada prueba usa una base de datos vacia propia."""
    monkeypatch.setenv("GASTOS_DB", str(tmp_path / "test.db"))


# ---------- registrar_gasto ----------

def test_registrar_ok_con_fecha_por_defecto():
    r = registrar_gasto("almuerzo", 4500, "Comida")
    assert r["status"] == "ok"
    assert r["gasto"]["categoria"] == "comida"
    assert r["gasto"]["fecha"] == date.today().isoformat()


def test_registrar_normaliza_acentos():
    assert registrar_gasto("apunte", 1200, "Educación")["gasto"]["categoria"] == "educacion"


@pytest.mark.parametrize(
    "args",
    [
        ("", 100, "comida"),            # descripcion vacia
        ("pan", 0, "comida"),           # monto cero
        ("pan", -50, "comida"),         # monto negativo
        ("pan", "abc", "comida"),       # monto no numerico
        ("pan", 100, "golosinas"),      # categoria invalida
        ("pan", 100, "comida", "06/11/2026"),  # formato de fecha invalido
    ],
)
def test_registrar_argumentos_invalidos(args):
    assert registrar_gasto(*args)["status"] == "error"


def test_registrar_fecha_futura():
    manana = (date.today() + timedelta(days=1)).isoformat()
    assert registrar_gasto("pan", 100, "comida", manana)["status"] == "error"


# ---------- listar_gastos ----------

def test_listar_vacio():
    assert listar_gastos()["status"] == "vacio"


def test_listar_con_filtros():
    registrar_gasto("colectivo", 800, "transporte", "2026-10-01")
    registrar_gasto("cine", 6000, "ocio", "2026-10-05")
    registrar_gasto("taxi", 3000, "transporte", "2026-10-10")

    r = listar_gastos(categoria="transporte")
    assert r["status"] == "ok" and r["cantidad"] == 2 and r["total"] == 3800

    r = listar_gastos(desde="2026-10-04", hasta="2026-10-06")
    assert [g["descripcion"] for g in r["gastos"]] == ["cine"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"categoria": "xyz"},
        {"desde": "ayer"},
        {"desde": "2026-10-10", "hasta": "2026-10-01"},
        {"limite": 0},
        {"limite": "muchos"},
    ],
)
def test_listar_argumentos_invalidos(kwargs):
    assert listar_gastos(**kwargs)["status"] == "error"


# ---------- resumen_gastos ----------

def test_resumen_por_categoria():
    registrar_gasto("super", 30000, "comida", "2026-09-03")
    registrar_gasto("luz", 10000, "servicios", "2026-09-10")
    registrar_gasto("verduleria", 10000, "comida", "2026-09-15")
    registrar_gasto("otro mes", 99999, "ocio", "2026-08-15")

    r = resumen_gastos("2026-09")
    assert r["status"] == "ok"
    assert r["total"] == 50000
    assert r["cantidad_gastos"] == 3
    assert r["categoria_mayor_gasto"] == "comida"
    assert r["por_categoria"][0]["porcentaje"] == 80.0


def test_resumen_mes_sin_datos():
    assert resumen_gastos("2020-01")["status"] == "vacio"


def test_resumen_mes_invalido():
    assert resumen_gastos("septiembre")["status"] == "error"


# ---------- eliminar_gasto ----------

def test_eliminar_ok_y_luego_inexistente():
    gid = registrar_gasto("pan", 100, "comida")["gasto"]["id"]
    assert eliminar_gasto(gid)["status"] == "ok"
    assert eliminar_gasto(gid)["status"] == "vacio"


@pytest.mark.parametrize("valor", [0, -3, "abc"])
def test_eliminar_id_invalido(valor):
    assert eliminar_gasto(valor)["status"] == "error"


# ---------- cotizacion_dolar (sin internet: se simula la API) ----------

class _RespuestaFalsa:
    def __init__(self, cuerpo: bytes):
        self.cuerpo = cuerpo

    def read(self):
        return self.cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_cotizacion_y_conversion():
    cuerpo = b'{"nombre": "Blue", "compra": 1400, "venta": 1500, "fechaActualizacion": "2026-11-06T12:00:00Z"}'
    with patch.object(cotizacion.urllib.request, "urlopen", return_value=_RespuestaFalsa(cuerpo)):
        r = cotizacion_dolar("blue", 30000)
    assert r["status"] == "ok"
    assert r["venta"] == 1500
    assert r["monto_dolares"] == 20.0


def test_cotizacion_tipo_invalido():
    assert cotizacion_dolar("euro")["status"] == "error"


def test_cotizacion_monto_negativo():
    assert cotizacion_dolar("oficial", -5)["status"] == "error"


def test_cotizacion_sin_conexion():
    import urllib.error

    with patch.object(cotizacion.urllib.request, "urlopen", side_effect=urllib.error.URLError("sin red")):
        assert cotizacion_dolar("oficial")["status"] == "error"


# ---------- reparacion de tool calls escritas como texto ----------

from gastos_agent.reparar_tool_calls import extraer_llamadas  # noqa: E402


def test_extraer_llamada_json():
    texto = '<tool_call>\n{"name": "resumen_gastos", "arguments": {"mes": "2026-11"}}\n</tool_call>'
    assert extraer_llamadas(texto) == [("resumen_gastos", {"mes": "2026-11"})]


def test_extraer_llamada_xml():
    texto = "<tool_call>\n<function=eliminar_gasto>\n<parameter=gasto_id>\n9999\n</parameter>\n</function>\n</tool_call>"
    assert extraer_llamadas(texto) == [("eliminar_gasto", {"gasto_id": 9999})]


def test_extraer_sin_llamada():
    assert extraer_llamadas("<tool_call>") == []


def test_extraer_llamada_xml_con_name():
    texto = '<function name="listar_gastos"><parameter name="categoria">ocio</parameter></function>'
    assert extraer_llamadas(texto) == [("listar_gastos", {"categoria": "ocio"})]
