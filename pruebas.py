"""Pruebas automáticas SIN conexión al modelo.  Uso:  python pruebas.py

Verifican las herramientas y el ciclo del agente con un cliente simulado.
Las pruebas con el modelo real se hacen a mano (ver README.md).
"""
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import httpx
from google.genai import errors, types

import agente as modulo_agente
import herramientas as h
from agente import Agente, mensaje_error


def proximo_dia_habil() -> str:
    d = date.today() + timedelta(days=1)
    while d.weekday() >= 5 or d.isoformat() in h.FESTIVOS:
        d += timedelta(days=1)
    return d.isoformat()


class PruebasHerramientas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        h.RUTA_CITAS = Path(self.tmp.name) / "citas.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_requisitos_encontrados(self):
        r = h.consultar_requisitos("perdí mi cédula")
        self.assertTrue(r["encontrado"])
        self.assertIn("Duplicado", r["tramite"])

    def test_tramite_ambiguo_pide_aclarar(self):
        r = h.consultar_requisitos("cédula")
        self.assertFalse(r["encontrado"])
        self.assertTrue(r["ambiguo"])
        self.assertGreaterEqual(len(r["opciones"]), 2)
        f = proximo_dia_habil()
        c = h.agendar_cita("Ana Pérez", "1075123456", "cédula", f, "09:00")
        self.assertFalse(c["exito"])
        self.assertIn("ambiguo", c["error"])

    def test_copia_del_registro_civil_no_se_confunde(self):
        self.assertIn("Copia", h.consultar_requisitos("copia autenticada de un registro civil")["tramite"])
        self.assertIn("nacimiento", h.consultar_requisitos("registro civil")["tramite"])

    def test_fecha_fuera_de_cobertura(self):
        r = h.ver_disponibilidad("2027-05-14")
        self.assertIn("error", r)
        if date.today() <= date(2026, 12, 31):
            self.assertIn("2026", r["error"])

    def test_requisitos_no_encontrados(self):
        r = h.consultar_requisitos("pasaporte")
        self.assertFalse(r["encontrado"])
        self.assertTrue(r["tramites_disponibles"])

    def test_fecha_invalida_y_fin_de_semana(self):
        self.assertIn("error", h.ver_disponibilidad("mañana"))
        d = date.today() + timedelta(days=1)
        while d.weekday() != 5:
            d += timedelta(days=1)
        self.assertIn("error", h.ver_disponibilidad(d.isoformat()))

    def test_festivo_sin_atencion(self):
        r = h.ver_disponibilidad("2026-12-25")
        self.assertIn("error", r)
        if date.today() <= date(2026, 12, 25):
            self.assertIn("festivo", r["error"])

    def test_agendar_y_ocupar_hora(self):
        f = proximo_dia_habil()
        c = h.agendar_cita("Ana Pérez", "1075123456", "duplicado de cédula", f, "09:00")
        self.assertTrue(c["exito"])
        self.assertNotIn("09:00", h.ver_disponibilidad(f)["horas_libres"])
        repetida = h.agendar_cita("Luis Gómez", "1075654321", "duplicado de cédula", f, "09:00")
        self.assertFalse(repetida["exito"])

    def test_validaciones_de_agendamiento(self):
        f = proximo_dia_habil()
        self.assertFalse(h.agendar_cita("Ana", "1075123456", "duplicado", f, "09:00")["exito"])
        self.assertFalse(h.agendar_cita("Ana Pérez", "12", "duplicado", f, "09:00")["exito"])

    def test_cancelar(self):
        f = proximo_dia_habil()
        c = h.agendar_cita("Ana Pérez", "1075123456", "registro civil", f, "10:00")
        self.assertTrue(h.cancelar_cita(c["codigo"])["exito"])
        self.assertFalse(h.cancelar_cita(c["codigo"])["exito"])
        self.assertIn("10:00", h.ver_disponibilidad(f)["horas_libres"])

    def test_herramienta_desconocida(self):
        self.assertIn("error", h.ejecutar_herramienta("hackear", {}))


# ---- cliente simulado para probar el ciclo del agente sin API ----
class ClienteFalso:
    """Imita a genai.Client: primero pide una herramienta, luego responde con texto."""

    def __init__(self, falla=None):
        self.llamadas = 0
        self.falla = falla  # excepción a lanzar, o None
        self.models = self

    def generate_content(self, **kwargs):
        self.llamadas += 1
        if self.falla:
            raise self.falla
        if self.llamadas == 1:
            llamada = types.FunctionCall(id="t1", name="consultar_requisitos",
                                         args={"tramite": "duplicado de cédula"})
            contenido = types.Content(role="model", parts=[types.Part(function_call=llamada)])
            return SimpleNamespace(candidates=[SimpleNamespace(content=contenido)],
                                   function_calls=[llamada], text=None)
        texto = "Listo, aquí están los requisitos."
        contenido = types.Content(role="model", parts=[types.Part(text=texto)])
        return SimpleNamespace(candidates=[SimpleNamespace(content=contenido)],
                               function_calls=None, text=texto)


class ClienteSecuencia:
    """Devuelve, en orden, excepciones o respuestas; guarda el modelo usado en cada llamada."""

    def __init__(self, resultados):
        self.resultados = list(resultados)
        self.modelos_usados = []
        self.models = self

    def generate_content(self, **kwargs):
        self.modelos_usados.append(kwargs["model"])
        resultado = self.resultados.pop(0)
        if isinstance(resultado, Exception):
            raise resultado
        return resultado


def _respuesta_texto(texto):
    contenido = types.Content(role="model", parts=[types.Part(text=texto)])
    return SimpleNamespace(candidates=[SimpleNamespace(content=contenido)],
                           function_calls=None, text=texto)


class PruebasResiliencia(unittest.TestCase):
    def setUp(self):
        self.espera_original = modulo_agente.ESPERA_S
        modulo_agente.ESPERA_S = 0  # sin esperas reales en las pruebas

    def tearDown(self):
        modulo_agente.ESPERA_S = self.espera_original

    def test_reintenta_ante_503(self):
        cliente = ClienteSecuencia([errors.APIError(503, {}), _respuesta_texto("Hola")])
        self.assertEqual(Agente(cliente=cliente).responder("hola"), "Hola")
        self.assertEqual(len(cliente.modelos_usados), 2)

    def test_usa_modelo_de_respaldo_si_no_hay_cuota(self):
        cliente = ClienteSecuencia([errors.APIError(429, {}), _respuesta_texto("Hola")])
        Agente(cliente=cliente).responder("hola")
        self.assertEqual(len(set(cliente.modelos_usados)), 2)

    def test_reintenta_si_se_cae_la_conexion(self):
        cliente = ClienteSecuencia([httpx.ConnectError("sin red"), _respuesta_texto("Hola")])
        self.assertEqual(Agente(cliente=cliente).responder("hola"), "Hola")
        self.assertEqual(len(cliente.modelos_usados), 2)

    def test_conexion_caida_agota_reintentos(self):
        cliente = ClienteSecuencia([httpx.ConnectError("sin red")] * 10)
        agente = Agente(cliente=cliente)
        with self.assertRaises(httpx.ConnectError):
            agente.responder("hola")
        self.assertEqual(len(cliente.modelos_usados), modulo_agente.REINTENTOS_RED)
        self.assertEqual(agente.historial, [])

    def test_read_timeout_se_reintenta_una_sola_vez(self):
        cliente = ClienteSecuencia([httpx.ReadTimeout("lento")] * 10)
        with self.assertRaises(httpx.ReadTimeout):
            Agente(cliente=cliente).responder("hola")
        self.assertEqual(len(cliente.modelos_usados), 2)

    def test_read_timeout_pasajero_se_recupera(self):
        cliente = ClienteSecuencia([httpx.ReadTimeout("lento"), _respuesta_texto("Hola")])
        self.assertEqual(Agente(cliente=cliente).responder("hola"), "Hola")

    def test_falla_si_todos_estan_saturados(self):
        cliente = ClienteSecuencia([errors.APIError(503, {})] * 10)
        agente = Agente(cliente=cliente)
        with self.assertRaises(errors.APIError):
            agente.responder("hola")
        self.assertEqual(agente.historial, [])
        self.assertIn("saturado", mensaje_error(errors.APIError(503, {})))


class PruebasAgente(unittest.TestCase):
    def test_ciclo_con_herramienta(self):
        agente = Agente(cliente=ClienteFalso())
        texto = agente.responder("¿Qué necesito para el duplicado?")
        self.assertEqual(texto, "Listo, aquí están los requisitos.")
        self.assertEqual(agente.ultimas_herramientas[0]["herramienta"], "consultar_requisitos")
        respuesta_herramienta = agente.historial[2].parts[0].function_response
        self.assertEqual(respuesta_herramienta.name, "consultar_requisitos")

    def test_configuracion_valida(self):
        config = Agente(cliente=ClienteFalso())._config()
        self.assertEqual(len(config.tools[0].function_declarations), 4)
        self.assertIn("Fecha actual", config.system_instruction)

    def test_error_de_api_no_deja_historial_a_medias(self):
        agente = Agente(cliente=ClienteFalso(falla=errors.APIError(429, {"error": {"message": "cuota"}})))
        with self.assertRaises(errors.APIError):
            agente.responder("hola")
        self.assertEqual(agente.historial, [])
        self.assertIn("límite", mensaje_error(errors.APIError(429, {})))

    def test_timeout_de_red_no_deja_historial_a_medias(self):
        agente = Agente(cliente=ClienteFalso(falla=httpx.ReadTimeout("sin respuesta")))
        with self.assertRaises(httpx.HTTPError):
            agente.responder("CONFIRMADO")
        self.assertEqual(agente.historial, [])
        self.assertIn("tardó", mensaje_error(httpx.ReadTimeout("x")))

    def test_reiniciar(self):
        agente = Agente(cliente=ClienteFalso())
        agente.responder("hola")
        agente.reiniciar()
        self.assertEqual(agente.historial, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
