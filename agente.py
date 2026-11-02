"""Núcleo del agente (Gemini): system prompt + ciclo de razonamiento con herramientas.

El mismo objeto Agente se usa desde la consola (consola.py) y desde la web (web.py).
"""
import os
import time
from datetime import date

import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from herramientas import TOOLS, ejecutar_herramienta

load_dotenv()

MODELO = os.getenv("MODELO", "gemini-3.1-flash-lite")
MAX_PASOS = 6  # tope de vueltas modelo <-> herramientas por mensaje
TIMEOUT_MS = 30_000  # espera máxima por respuesta de Gemini (30 s)
# Si el modelo principal está saturado o sin cuota, se prueba con los de respaldo.
MODELOS = [MODELO] + [m.strip() for m in os.getenv("MODELOS_RESPALDO", "gemini-3.5-flash-lite").split(",")
                      if m.strip() and m.strip() != MODELO]
REINTENTOS = 2  # intentos por modelo cuando Gemini responde 500/503/504
REINTENTOS_RED = 3  # intentos si falla la conexión (ConnectError, ReadError, etc.)
ESPERA_S = 3    # segundos de espera base entre reintentos
# Errores que las interfaces deben atrapar (API de Gemini + problemas de red)
ERRORES_API = (errors.APIError, httpx.HTTPError)
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def opciones_http() -> types.HttpOptions:
    """Timeout y, si FORZAR_IPV4=1 en .env, conexión solo por IPv4 (arregla fallos
    intermitentes de conexión en algunas redes domésticas)."""
    opciones = {"timeout": TIMEOUT_MS}
    if os.getenv("FORZAR_IPV4") == "1":
        opciones["client_args"] = {"transport": httpx.HTTPTransport(local_address="0.0.0.0")}
    return types.HttpOptions(**opciones)


def construir_system_prompt() -> str:
    hoy = date.today()
    return f"""Eres "Asistente Registraduría", un agente virtual que orienta a la ciudadanía \
sobre trámites de identificación (cédula, tarjeta de identidad, registro civil) y gestiona \
citas de atención. Es un proyecto académico de la Corporación Universitaria del Huila.

Fecha actual: {hoy.isoformat()} ({DIAS[hoy.weekday()]}).

ALCANCE
- Puedes: explicar requisitos de trámites, consultar horas disponibles, agendar y cancelar citas.
- No puedes: consultar datos personales de nadie, realizar el trámite ni dar asesoría legal. \
Si piden algo fuera de tu alcance, dilo con amabilidad y ofrece lo que sí puedes hacer.

REGLAS
1. Para requisitos usa SIEMPRE la herramienta consultar_requisitos. No inventes requisitos, \
costos ni plazos.
2. Antes de agendar necesitas: nombre completo (nombre y apellido; si solo dan un nombre, pide \
el apellido), número de documento, trámite, fecha y hora. Pide lo que falte.
3. Usa ver_disponibilidad antes de ofrecer horas. A las herramientas las fechas se envían como \
AAAA-MM-DD; interpreta "mañana" o "el lunes" con la fecha actual.
4. Antes de agendar, resume los datos y pide confirmación. Agenda solo cuando el usuario confirme.
5. Tras agendar, entrega el código de la cita y recuerda que lo necesita para cancelar.
6. Responde en español, con tono cordial y breve.
7. Al informar requisitos, recuerda que deben verificarse en registraduria.gov.co.
8. Si una herramienta indica que un día es festivo, que no hay atención o que la fecha está fuera \
de cobertura, explícalo y propón otra fecha.
9. Nunca afirmes que una hora está libre u ocupada, ni que existe una cita, sin haber llamado a una \
herramienta en este mismo turno.
10. Si piden requisitos sin decir el trámite, pregunta cuál es (cédula por primera vez, duplicado de \
cédula, tarjeta de identidad, registro civil o copia del registro civil); no elijas uno por tu cuenta. \
Si solo dicen "cédula", pregunta si es por primera vez o duplicado.
11. Si la herramienta no trae lo que se pidió, dilo y remite a registraduria.gov.co. No completes con \
conocimiento propio.
12. Al agendar o cancelar, repite en tu respuesta final el trámite, la fecha y la hora."""


def mensaje_error(error: Exception) -> str:
    """Traduce errores comunes de la API a mensajes entendibles."""
    if isinstance(error, httpx.TimeoutException):
        return ("Gemini tardó demasiado en responder. Revisa tu internet y vuelve a enviar "
                "tu último mensaje.")
    if isinstance(error, httpx.HTTPError):
        return ("No se pudo conectar con Gemini después de varios intentos. Revisa tu internet, "
                "VPN o antivirus, o corre `python diagnostico.py` para ver qué falla.")
    codigo = getattr(error, "code", None)
    if codigo in (500, 503, 504):
        return ("Gemini está saturado en este momento (pasa a veces en la capa gratuita). "
                "Espera unos segundos y reenvía tu mensaje.")
    if codigo == 429:
        return "Se alcanzó el límite de la capa gratuita. Espera un minuto y vuelve a intentar."
    if codigo in (400, 401, 403):
        return "La API rechazó la solicitud. Revisa GEMINI_API_KEY y MODELO en el archivo .env."
    if codigo == 404:
        return f"El modelo '{MODELO}' no existe o ya no está disponible. Cambia MODELO en .env."
    return f"Error al contactar el modelo: {error}"


class Agente:
    def __init__(self, cliente=None):
        if cliente is None:
            clave = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not clave:
                raise RuntimeError(
                    "Falta GEMINI_API_KEY. Copia .env.example a .env y pega tu clave."
                )
            cliente = genai.Client(api_key=clave, http_options=opciones_http())
        self.cliente = cliente
        self.historial = []
        self.ultimas_herramientas = []

    def reiniciar(self) -> None:
        self.historial = []
        self.ultimas_herramientas = []

    def _config(self) -> types.GenerateContentConfig:
        declaraciones = [types.FunctionDeclaration(**t) for t in TOOLS]
        return types.GenerateContentConfig(
            system_instruction=construir_system_prompt(),
            tools=[types.Tool(function_declarations=declaraciones)],
        )

    def _llamar(self, modelo: str):
        """Una llamada a Gemini; reintenta si se cae la conexión (no si es solo lentitud)."""
        for intento in range(REINTENTOS_RED):
            try:
                return self.cliente.models.generate_content(
                    model=modelo, contents=self.historial, config=self._config()
                )
            except httpx.ReadTimeout:
                if intento >= 1:
                    raise  # dos intentos sin respuesta: se avisa al usuario
                # primer silencio: casi siempre es una conexión colgada, una nueva suele responder
            except httpx.TransportError:
                if intento == REINTENTOS_RED - 1:
                    raise
                time.sleep(ESPERA_S * (intento + 1))

    def _generar(self):
        """Llama a Gemini; reintenta si está saturado y usa modelos de respaldo."""
        ultimo_error = None
        for modelo in MODELOS:
            for intento in range(REINTENTOS):
                try:
                    return self._llamar(modelo)
                except errors.APIError as error:
                    ultimo_error = error
                    codigo = getattr(error, "code", None)
                    if codigo in (500, 503, 504):  # saturado: esperar y reintentar
                        time.sleep(ESPERA_S * (intento + 1))
                        continue
                    if codigo in (404, 429):  # sin modelo o sin cuota: probar el siguiente
                        break
                    raise
        raise ultimo_error

    def responder(self, mensaje: str) -> str:
        self.ultimas_herramientas = []
        estado_previo = len(self.historial)
        self.historial.append(types.Content(role="user", parts=[types.Part(text=mensaje)]))

        try:
            for _ in range(MAX_PASOS):
                respuesta = self._generar()
                if not respuesta.candidates:
                    return "No pude generar una respuesta. ¿Puedes reformular tu mensaje?"

                # Se guarda el contenido tal cual lo devolvió el modelo (incluye
                # información interna que Gemini necesita en el siguiente turno).
                self.historial.append(respuesta.candidates[0].content)

                llamadas = respuesta.function_calls
                if not llamadas:
                    return respuesta.text or "No tengo una respuesta para eso."

                partes = []
                for llamada in llamadas:
                    argumentos = dict(llamada.args or {})
                    salida = ejecutar_herramienta(llamada.name, argumentos)
                    self.ultimas_herramientas.append(
                        {"herramienta": llamada.name, "entrada": argumentos, "salida": salida}
                    )
                    partes.append(types.Part(function_response=types.FunctionResponse(
                        id=llamada.id, name=llamada.name, response=salida)))
                self.historial.append(types.Content(role="user", parts=partes))
        except Exception:
            # Si falla la API o la red, se deshace este turno para no dejar el historial a medias.
            self.historial = self.historial[:estado_previo]
            raise

        return "No pude completar la solicitud. ¿Puedes reformularla, por favor?"
