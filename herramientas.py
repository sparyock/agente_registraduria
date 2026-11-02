"""Herramientas (tools) que el agente puede invocar.

Cada herramienta es una función normal de Python. La lista TOOLS describe,
en formato JSON Schema, cómo debe llamarlas el modelo.
"""
import json
import re
import unicodedata
import uuid
from datetime import date, datetime
from pathlib import Path

BASE = Path(__file__).parent
RUTA_KB = BASE / "base_conocimiento.json"
RUTA_CITAS = BASE / "citas.json"

HORAS = ["08:00", "09:00", "10:00", "11:00", "14:00", "15:00", "16:00"]
# Festivos de Colombia 2026 (ya incluyen los traslados al lunes de la Ley Emiliani).
# Verificar en fuentes oficiales; para otros años habría que ampliar esta tabla.
FESTIVOS = {
    "2026-01-01": "Año Nuevo", "2026-01-12": "Reyes Magos", "2026-03-23": "San José",
    "2026-04-02": "Jueves Santo", "2026-04-03": "Viernes Santo", "2026-05-01": "Día del Trabajo",
    "2026-05-18": "Ascensión del Señor", "2026-06-08": "Corpus Christi",
    "2026-06-15": "Sagrado Corazón", "2026-06-29": "San Pedro y San Pablo",
    "2026-07-13": "Nuestra Señora del Rosario de Chiquinquirá",
    "2026-07-20": "Día de la Independencia", "2026-08-07": "Batalla de Boyacá",
    "2026-08-17": "Asunción de la Virgen", "2026-10-12": "Día de la Raza",
    "2026-11-02": "Todos los Santos", "2026-11-16": "Independencia de Cartagena",
    "2026-12-08": "Inmaculada Concepción", "2026-12-25": "Navidad",
}
# El calendario de festivos solo está cargado hasta esta fecha; no se agenda más allá.
COBERTURA_HASTA = date(2026, 12, 31)
PALABRAS_VACIAS = {"de", "la", "el", "los", "las", "del", "por", "para", "un", "una",
                   "mi", "quiero", "necesito", "sacar", "tramite"}


# ---------- utilidades internas ----------
def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", str(texto).lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", texto).strip()


def _cargar_kb() -> list:
    with open(RUTA_KB, encoding="utf-8") as f:
        return json.load(f)["tramites"]


def _cargar_citas() -> list:
    if not RUTA_CITAS.exists():
        return []
    with open(RUTA_CITAS, encoding="utf-8") as f:
        return json.load(f)


def _guardar_citas(citas: list) -> None:
    with open(RUTA_CITAS, "w", encoding="utf-8") as f:
        json.dump(citas, f, ensure_ascii=False, indent=2)


def listar_citas() -> list:
    """Citas guardadas, ordenadas por fecha y hora (se muestran en la web)."""
    return sorted(_cargar_citas(), key=lambda c: (c["fecha"], c["hora"]))


def _parsear_fecha(fecha):
    try:
        return datetime.strptime(str(fecha), "%Y-%m-%d").date()
    except ValueError:
        return None


# ---------- herramientas ----------
def _buscar_tramite(tramite: str):
    """Devuelve (trámite, None) si hay uno claro, (None, [nombres]) si es ambiguo
    o (None, None) si no se encontró ninguno."""
    consulta = _normalizar(tramite)
    palabras = set(consulta.split()) - PALABRAS_VACIAS
    tramites = _cargar_kb()
    puntajes = []
    for t in tramites:
        claves = [_normalizar(t["nombre"])] + [_normalizar(a) for a in t["alias"]]
        if consulta in claves:  # coincidencia exacta con el nombre o un alias
            return t, None
        puntajes.append((max(len(palabras & set(c.split())) for c in claves), t))
    mejor = max(p for p, _ in puntajes)
    if mejor == 0:
        return None, None
    candidatos = [t for p, t in puntajes if p == mejor]
    if len(candidatos) > 1:
        return None, [t["nombre"] for t in candidatos]
    return candidatos[0], None


def consultar_requisitos(tramite: str) -> dict:
    """Busca un trámite en la base de conocimiento y devuelve sus requisitos."""
    encontrado, ambiguos = _buscar_tramite(tramite)
    if encontrado:
        return {"encontrado": True, "tramite": encontrado["nombre"],
                "requisitos": encontrado["requisitos"],
                "observaciones": encontrado["observaciones"]}
    if ambiguos:
        return {"encontrado": False, "ambiguo": True, "opciones": ambiguos,
                "instruccion": "Pregunta al usuario cuál de estos trámites necesita."}
    return {"encontrado": False,
            "tramites_disponibles": [t["nombre"] for t in _cargar_kb()]}


def ver_disponibilidad(fecha: str) -> dict:
    """Devuelve las horas libres para una fecha (AAAA-MM-DD)."""
    d = _parsear_fecha(fecha)
    if d is None:
        return {"error": "Formato de fecha inválido. Usa AAAA-MM-DD."}
    if d < date.today():
        return {"error": "Esa fecha ya pasó."}
    if d > COBERTURA_HASTA:
        return {"error": "Por ahora solo se agendan citas hasta el 31 de diciembre de 2026."}
    if d.weekday() >= 5:
        return {"error": "Solo se atiende de lunes a viernes."}
    iso = d.isoformat()
    if iso in FESTIVOS:
        return {"error": f"El {iso} es festivo ({FESTIVOS[iso]}) y no hay atención."}
    ocupadas = {c["hora"] for c in _cargar_citas() if c["fecha"] == iso}
    libres = [h for h in HORAS if h not in ocupadas]
    if d == date.today():
        ahora = datetime.now().strftime("%H:%M")
        libres = [h for h in libres if h > ahora]
    return {"fecha": iso, "horas_libres": libres}


def agendar_cita(nombre: str, documento: str, tramite: str, fecha: str, hora: str) -> dict:
    """Agenda una cita si los datos son válidos y la hora está libre."""
    nombre = (nombre or "").strip()
    documento = re.sub(r"\D", "", str(documento or ""))
    if len(nombre.split()) < 2:
        return {"exito": False, "error": "Se requiere el nombre completo (nombre y apellido)."}
    if not 6 <= len(documento) <= 10:
        return {"exito": False, "error": "El documento debe tener entre 6 y 10 dígitos."}
    req = consultar_requisitos(tramite)
    if not req["encontrado"]:
        if req.get("ambiguo"):
            return {"exito": False, "error": "Trámite ambiguo: pregunta al usuario cuál necesita.",
                    "opciones": req["opciones"]}
        return {"exito": False, "error": "Trámite no reconocido.",
                "tramites_disponibles": req["tramites_disponibles"]}
    disp = ver_disponibilidad(fecha)
    if "error" in disp:
        return {"exito": False, "error": disp["error"]}
    if hora not in disp["horas_libres"]:
        return {"exito": False, "error": f"La hora {hora} no está disponible.",
                "horas_libres": disp["horas_libres"]}
    cita = {"codigo": "CT-" + uuid.uuid4().hex[:6].upper(), "nombre": nombre,
            "documento": documento, "tramite": req["tramite"],
            "fecha": disp["fecha"], "hora": hora}
    citas = _cargar_citas()
    citas.append(cita)
    _guardar_citas(citas)
    return {"exito": True, **cita}


def cancelar_cita(codigo: str) -> dict:
    """Cancela una cita a partir de su código."""
    codigo = (codigo or "").strip().upper()
    citas = _cargar_citas()
    restantes = [c for c in citas if c["codigo"] != codigo]
    if len(restantes) == len(citas):
        return {"exito": False, "error": "No existe una cita con ese código."}
    _guardar_citas(restantes)
    return {"exito": True, "mensaje": f"La cita {codigo} fue cancelada."}


# ---------- registro y esquemas ----------
FUNCIONES = {
    "consultar_requisitos": consultar_requisitos,
    "ver_disponibilidad": ver_disponibilidad,
    "agendar_cita": agendar_cita,
    "cancelar_cita": cancelar_cita,
}


def ejecutar_herramienta(nombre: str, argumentos: dict) -> dict:
    funcion = FUNCIONES.get(nombre)
    if funcion is None:
        return {"error": f"Herramienta desconocida: {nombre}"}
    try:
        return funcion(**argumentos)
    except TypeError as error:
        return {"error": f"Argumentos inválidos: {error}"}


TOOLS = [
    {
        "name": "consultar_requisitos",
        "description": "Consulta los requisitos de un trámite de identificación "
                       "(cédula, duplicado, tarjeta de identidad, registro civil).",
        "parameters": {
            "type": "object",
            "properties": {"tramite": {"type": "string",
                                       "description": "Nombre del trámite que pregunta el usuario."}},
            "required": ["tramite"],
        },
    },
    {
        "name": "ver_disponibilidad",
        "description": "Devuelve las horas libres para una fecha. Solo lunes a viernes.",
        "parameters": {
            "type": "object",
            "properties": {"fecha": {"type": "string",
                                     "description": "Fecha en formato AAAA-MM-DD."}},
            "required": ["fecha"],
        },
    },
    {
        "name": "agendar_cita",
        "description": "Agenda una cita. Úsala solo cuando el usuario ya confirmó todos los datos.",
        "parameters": {
            "type": "object",
            "properties": {
                "nombre": {"type": "string", "description": "Nombre completo del ciudadano."},
                "documento": {"type": "string", "description": "Número de documento (solo dígitos)."},
                "tramite": {"type": "string", "description": "Trámite a realizar."},
                "fecha": {"type": "string", "description": "Fecha AAAA-MM-DD."},
                "hora": {"type": "string", "description": "Hora HH:MM en formato 24 h, p. ej. 14:00."},
            },
            "required": ["nombre", "documento", "tramite", "fecha", "hora"],
        },
    },
    {
        "name": "cancelar_cita",
        "description": "Cancela una cita existente usando su código (p. ej. CT-1A2B3C).",
        "parameters": {
            "type": "object",
            "properties": {"codigo": {"type": "string", "description": "Código de la cita."}},
            "required": ["codigo"],
        },
    },
]
