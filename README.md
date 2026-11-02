# Asistente Registraduría — agente inteligente (Python 3 + Gemini)

Proyecto académico · Corhuila · Electiva Aplicaciones con IA 2026-2

## Clave gratuita de Gemini
1. Entra a https://aistudio.google.com e inicia sesión con tu cuenta Google.
2. Haz clic en **Get API key** → **Create API key** y copia la clave.

## Instalación en Windows (PowerShell o CMD, dentro de esta carpeta)
```bat
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
notepad .env
```
En `.env` pega tu `GEMINI_API_KEY` y guarda con **Ctrl+S**.
Verifica que el archivo se llame `.env` y NO `.env.txt`.

Si PowerShell bloquea `activate` ("ejecución de scripts deshabilitada"):
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```
(o usa CMD, que no tiene ese problema).

## Ejecución (con el entorno activado)
```bat
python pruebas.py              :: pruebas automáticas (sin API)
python consola.py              :: versión consola
python -m streamlit run web.py :: versión web (abre http://localhost:8501)
```

## Si algo falla
- "Falta GEMINI_API_KEY": revisa que `.env` exista y tenga la clave sin comillas.
- "modelo no existe": cambia `MODELO` en `.env` (ej. `gemini-3.5-flash-lite`).
- "Gemini está saturado" (error 503): es de Google, no de tu código. El agente reintenta solo y luego prueba un modelo de respaldo (`MODELOS_RESPALDO` en `.env`); si aun así falla, espera unos segundos y reenvía el mensaje.
- "límite de la capa gratuita": espera un minuto y reintenta.
- "Gemini tardó demasiado" / "No se pudo conectar": es la red (internet lento, VPN o antivirus). El agente reintenta solo 3 veces; si persiste, corre `python diagnostico.py`. Si el diagnóstico recomienda IPv4, pon `FORZAR_IPV4=1` en `.env`. Reenvía tu último mensaje: no pierdes la conversación.
- Los festivos están cargados solo para 2026 (`FESTIVOS` en `herramientas.py`).
- Usa solo datos ficticios en las pruebas: en la capa gratuita Google puede usar los datos para mejorar sus productos.

## Estructura
- `agente.py` — system prompt y ciclo del agente (modelo ⇄ herramientas)
- `herramientas.py` — 4 herramientas: requisitos, disponibilidad, agendar, cancelar
- `base_conocimiento.json` — trámites de ejemplo (verificar en registraduria.gov.co)
- `consola.py` / `web.py` — las dos interfaces (la web trae 4 paletas de colores, sugerencias y panel de citas)
- `.streamlit/config.toml` — tema base de la web
- `CASOS_DE_PRUEBA.md` — 15 casos para probar en consola y web (con columna para anotar resultados)
- `pruebas.py` — pruebas automáticas
- `diagnostico.py` — revisa la conexión con Gemini (útil si hay errores de red)

## Pruebas manuales sugeridas (consola y web)
1. "¿Qué necesito para sacar el duplicado de la cédula?"  → usa `consultar_requisitos`
2. "Quiero una cita para el próximo lunes"  → usa `ver_disponibilidad`, pide datos
3. Dar nombre, documento, trámite y hora; confirmar  → usa `agendar_cita`, entrega código
4. "Cancela la cita CT-XXXXXX"  → usa `cancelar_cita`
5. "¿Cuánto cuesta un pasaporte?"  → debe indicar que está fuera de su alcance
6. Agendar la misma hora dos veces  → debe rechazarla y ofrecer otras horas
