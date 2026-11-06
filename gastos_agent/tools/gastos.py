"""Herramientas para gestionar gastos personales en una base SQLite.

Cada herramienta devuelve un diccionario con la clave "status":
  - "ok"     -> la operacion salio bien.
  - "vacio"  -> la operacion salio bien pero no hay resultados.
  - "error"  -> argumentos invalidos o fallo interno (ver "mensaje").
"""

import os
import sqlite3
import unicodedata
from datetime import date, datetime

CATEGORIAS = [
    "comida",
    "transporte",
    "servicios",
    "salud",
    "educacion",
    "ocio",
    "ropa",
    "hogar",
    "otros",
]

_DB_DEFAULT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "gastos.db")


def _db_path() -> str:
    return os.environ.get("GASTOS_DB", _DB_DEFAULT)


def _conectar() -> sqlite3.Connection:
    ruta = _db_path()
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    conn = sqlite3.connect(ruta)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descripcion TEXT NOT NULL,
            monto REAL NOT NULL,
            categoria TEXT NOT NULL,
            fecha TEXT NOT NULL
        )"""
    )
    return conn


def _error(mensaje: str) -> dict:
    return {"status": "error", "mensaje": mensaje}


def _normalizar(texto: str) -> str:
    """Pasa a minusculas y quita acentos ("Educación" -> "educacion")."""
    texto = unicodedata.normalize("NFKD", str(texto).strip().lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def _validar_fecha(fecha: str, nombre: str = "fecha"):
    """Devuelve (fecha_iso, None) o (None, mensaje_de_error)."""
    try:
        return datetime.strptime(fecha.strip(), "%Y-%m-%d").date().isoformat(), None
    except (ValueError, AttributeError):
        return None, f"La {nombre} '{fecha}' no es valida. Usa el formato AAAA-MM-DD (ej: 2026-11-06)."


def registrar_gasto(descripcion: str, monto: float, categoria: str, fecha: str = "") -> dict:
    """Registra un nuevo gasto en la base de datos.

    Usar cuando el usuario cuenta que gasto o pago algo.

    Args:
        descripcion: Que se compro o pago (ej: "almuerzo", "carga SUBE").
        monto: Importe en pesos argentinos. Debe ser mayor a 0.
        categoria: Una de: comida, transporte, servicios, salud, educacion, ocio, ropa, hogar, otros.
        fecha: Fecha del gasto en formato AAAA-MM-DD. Si se deja vacia se usa la fecha de hoy.

    Returns:
        dict con status y el gasto registrado (incluye su id).
    """
    descripcion = str(descripcion or "").strip()
    if not descripcion:
        return _error("La descripcion no puede estar vacia.")
    if len(descripcion) > 200:
        return _error("La descripcion es demasiado larga (maximo 200 caracteres).")

    try:
        monto = round(float(monto), 2)
    except (TypeError, ValueError):
        return _error(f"El monto '{monto}' no es un numero valido.")
    if monto <= 0:
        return _error("El monto debe ser mayor a 0.")
    if monto > 100_000_000:
        return _error("El monto es demasiado grande, verifica el valor.")

    cat = _normalizar(categoria)
    if cat not in CATEGORIAS:
        return _error(f"Categoria '{categoria}' invalida. Opciones: {', '.join(CATEGORIAS)}.")

    if fecha and str(fecha).strip():
        fecha_iso, err = _validar_fecha(str(fecha))
        if err:
            return _error(err)
        if fecha_iso > date.today().isoformat():
            return _error("No se pueden registrar gastos con fecha futura.")
    else:
        fecha_iso = date.today().isoformat()

    try:
        with _conectar() as conn:
            cur = conn.execute(
                "INSERT INTO gastos (descripcion, monto, categoria, fecha) VALUES (?, ?, ?, ?)",
                (descripcion, monto, cat, fecha_iso),
            )
            nuevo_id = cur.lastrowid
        return {
            "status": "ok",
            "gasto": {"id": nuevo_id, "descripcion": descripcion, "monto": monto, "categoria": cat, "fecha": fecha_iso},
        }
    except sqlite3.Error as e:
        return _error(f"Error interno de base de datos: {e}")


def listar_gastos(categoria: str = "", desde: str = "", hasta: str = "", limite: int = 20) -> dict:
    """Lista los gastos registrados, del mas reciente al mas antiguo, con filtros opcionales.

    Usar cuando el usuario quiere ver sus gastos o buscar uno (por ejemplo para saber su id).

    Args:
        categoria: Filtra por categoria. Vacio = todas.
        desde: Fecha minima AAAA-MM-DD (inclusive). Vacio = sin limite.
        hasta: Fecha maxima AAAA-MM-DD (inclusive). Vacio = sin limite.
        limite: Cantidad maxima de gastos a devolver (1 a 100).

    Returns:
        dict con status, la lista de gastos y el total sumado de los gastos listados.
    """
    condiciones, params = [], []

    if categoria and str(categoria).strip():
        cat = _normalizar(categoria)
        if cat not in CATEGORIAS:
            return _error(f"Categoria '{categoria}' invalida. Opciones: {', '.join(CATEGORIAS)}.")
        condiciones.append("categoria = ?")
        params.append(cat)

    for valor, nombre, op in ((desde, "fecha 'desde'", ">="), (hasta, "fecha 'hasta'", "<=")):
        if valor and str(valor).strip():
            fecha_iso, err = _validar_fecha(str(valor), nombre)
            if err:
                return _error(err)
            condiciones.append(f"fecha {op} ?")
            params.append(fecha_iso)

    if desde and hasta and len(params) >= 2 and params[-2] > params[-1]:
        return _error("La fecha 'desde' no puede ser posterior a la fecha 'hasta'.")

    try:
        limite = int(limite)
    except (TypeError, ValueError):
        return _error(f"El limite '{limite}' no es un numero entero.")
    if not 1 <= limite <= 100:
        return _error("El limite debe estar entre 1 y 100.")

    sql = "SELECT id, descripcion, monto, categoria, fecha FROM gastos"
    if condiciones:
        sql += " WHERE " + " AND ".join(condiciones)
    sql += " ORDER BY fecha DESC, id DESC LIMIT ?"

    try:
        with _conectar() as conn:
            filas = [dict(f) for f in conn.execute(sql, (*params, limite))]
    except sqlite3.Error as e:
        return _error(f"Error interno de base de datos: {e}")

    if not filas:
        return {"status": "vacio", "mensaje": "No se encontraron gastos con esos filtros.", "gastos": []}
    return {
        "status": "ok",
        "cantidad": len(filas),
        "total": round(sum(f["monto"] for f in filas), 2),
        "gastos": filas,
    }


def resumen_gastos(mes: str = "") -> dict:
    """Calcula el total gastado y el desglose por categoria de un mes.

    Usar cuando el usuario pregunta cuanto gasto, en que gasto mas o pide un resumen/balance.

    Args:
        mes: Mes en formato AAAA-MM (ej: 2026-11). Vacio = mes actual.

    Returns:
        dict con status, total del mes, cantidad de gastos, categoria con mayor gasto
        y el detalle por categoria (monto y porcentaje).
    """
    if mes and str(mes).strip():
        try:
            mes = datetime.strptime(str(mes).strip(), "%Y-%m").strftime("%Y-%m")
        except ValueError:
            return _error(f"El mes '{mes}' no es valido. Usa el formato AAAA-MM (ej: 2026-11).")
    else:
        mes = date.today().strftime("%Y-%m")

    try:
        with _conectar() as conn:
            filas = conn.execute(
                """SELECT categoria, SUM(monto) AS total, COUNT(*) AS cantidad
                   FROM gastos WHERE substr(fecha, 1, 7) = ?
                   GROUP BY categoria ORDER BY total DESC""",
                (mes,),
            ).fetchall()
    except sqlite3.Error as e:
        return _error(f"Error interno de base de datos: {e}")

    if not filas:
        return {"status": "vacio", "mes": mes, "mensaje": f"No hay gastos registrados en {mes}."}

    total = sum(f["total"] for f in filas)
    detalle = [
        {
            "categoria": f["categoria"],
            "total": round(f["total"], 2),
            "cantidad": f["cantidad"],
            "porcentaje": round(f["total"] * 100 / total, 1),
        }
        for f in filas
    ]
    return {
        "status": "ok",
        "mes": mes,
        "total": round(total, 2),
        "cantidad_gastos": sum(f["cantidad"] for f in filas),
        "categoria_mayor_gasto": detalle[0]["categoria"],
        "por_categoria": detalle,
    }


def eliminar_gasto(gasto_id: int) -> dict:
    """Elimina un gasto por su id.

    Usar solo cuando el usuario pide borrar un gasto concreto. Si no conoces el id,
    primero usa listar_gastos para encontrarlo.

    Args:
        gasto_id: Id numerico del gasto a eliminar.

    Returns:
        dict con status y los datos del gasto eliminado.
    """
    try:
        gasto_id = int(gasto_id)
    except (TypeError, ValueError):
        return _error(f"El id '{gasto_id}' no es un numero entero.")
    if gasto_id <= 0:
        return _error("El id debe ser un numero positivo.")

    try:
        with _conectar() as conn:
            fila = conn.execute(
                "SELECT id, descripcion, monto, categoria, fecha FROM gastos WHERE id = ?", (gasto_id,)
            ).fetchone()
            if fila is None:
                return {"status": "vacio", "mensaje": f"No existe un gasto con id {gasto_id}."}
            conn.execute("DELETE FROM gastos WHERE id = ?", (gasto_id,))
        return {"status": "ok", "eliminado": dict(fila)}
    except sqlite3.Error as e:
        return _error(f"Error interno de base de datos: {e}")
