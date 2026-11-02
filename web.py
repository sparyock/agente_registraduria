"""Interfaz web (Streamlit) del agente.  Uso:  python -m streamlit run web.py"""
import html

import streamlit as st

import herramientas as herr
from agente import ERRORES_API, MODELO, Agente, mensaje_error

st.set_page_config(page_title="Asistente Registraduría", page_icon="🏛️")

# ------------------------------------------------------------------ paletas
PALETAS = {
    "🌊 Océano": dict(primario="#0F4C81", secundario="#1FA2B8", acento="#FFC93C",
                      fondo="#EEF5FA", tarjeta="#FFFFFF", texto="#10263A",
                      suave="rgba(31,162,184,.13)"),
    "🌅 Atardecer": dict(primario="#7B2CBF", secundario="#FF6B6B", acento="#FFD166",
                         fondo="#FFF4EE", tarjeta="#FFFFFF", texto="#2B1B3D",
                         suave="rgba(255,107,107,.13)"),
    "🌿 Bosque": dict(primario="#1B5E4B", secundario="#3FA796", acento="#F4B942",
                      fondo="#EDF7F2", tarjeta="#FFFFFF", texto="#12332B",
                      suave="rgba(63,167,150,.15)"),
    "💜 Orquídea": dict(primario="#5B3FD1", secundario="#C04DD6", acento="#FFB400",
                        fondo="#F5F1FF", tarjeta="#FFFFFF", texto="#241A4A",
                        suave="rgba(192,77,214,.13)"),
}

SUGERENCIAS = [
    ("📋 Requisitos del duplicado", "¿Qué necesito para el duplicado de la cédula?"),
    ("📅 Horas libres el martes", "¿Qué horas hay libres el próximo martes?"),
    ("🧒 Tarjeta de identidad", "¿Qué requisitos tiene la tarjeta de identidad?"),
    ("🗓️ Quiero agendar una cita", "Quiero agendar una cita"),
]

ACCIONES = [
    ("📋 Consultar requisitos", "Quiero consultar los requisitos de un trámite"),
    ("🕘 Ver horas libres", "Quiero ver las horas libres de un día"),
    ("📅 Agendar una cita", "Quiero agendar una cita"),
    ("❌ Cancelar una cita", "Quiero cancelar una cita"),
]

HERRAMIENTAS_INFO = [
    ("consultar_requisitos", "Requisitos de cada trámite"),
    ("ver_disponibilidad", "Horas libres (lun–vie, sin festivos)"),
    ("agendar_cita", "Crea la cita y entrega un código"),
    ("cancelar_cita", "Cancela una cita con su código"),
]

AVATARES = {"user": "🙋", "assistant": "🤖"}
CLASE_MARCADOR = {"user": "msg-user", "assistant": "msg-bot"}

# ------------------------------------------------------------------ estilos
FUENTE = "@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');"

CSS = """
html, body, .stApp, button, input, textarea { font-family: 'Poppins', 'Segoe UI', sans-serif; }
.stApp {
  background-color: var(--fondo);
  background-image: radial-gradient(circle at 6% 0%, var(--suave), transparent 38%),
                    radial-gradient(circle at 96% 14%, var(--suave), transparent 34%);
}
#MainMenu, footer { visibility: hidden; }
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1.4rem; max-width: 860px; }
.stApp p, .stApp li, .stApp label { color: var(--texto); }

/* ---- encabezado ---- */
.hero { position: relative; overflow: hidden; display: flex; gap: 18px; align-items: center;
  padding: 22px 26px; border-radius: 22px; margin-bottom: 18px;
  background: linear-gradient(135deg, var(--primario) 0%, var(--secundario) 100%);
  box-shadow: 0 16px 34px -14px var(--primario); }
.hero::before { content: ""; position: absolute; width: 230px; height: 230px; right: -60px; top: -95px;
  border-radius: 50%; background: rgba(255,255,255,.14); }
.hero::after { content: ""; position: absolute; width: 120px; height: 120px; right: 95px; bottom: -72px;
  border-radius: 50%; background: var(--acento); opacity: .4; }
.hero > div { position: relative; z-index: 1; }
.hero-icon { font-size: 2.3rem; width: 66px; height: 66px; flex-shrink: 0; display: flex;
  align-items: center; justify-content: center; border-radius: 18px;
  background: rgba(255,255,255,.2); border: 1px solid rgba(255,255,255,.3); }
.hero-title { font-size: 1.5rem; font-weight: 700; line-height: 1.2; color: #fff !important; }
.hero-sub { margin: 4px 0 10px; font-size: .86rem; color: rgba(255,255,255,.92) !important; }
.hero-chips span { display: inline-block; margin: 0 6px 4px 0; padding: 3px 11px; border-radius: 999px;
  font-size: .73rem; color: #fff; background: rgba(255,255,255,.2); border: 1px solid rgba(255,255,255,.3); }

/* ---- tarjetas de bienvenida ---- */
.features { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 4px 0 14px; }
.feature { background: var(--tarjeta); border-radius: 16px; padding: 14px 16px; border-top: 4px solid var(--secundario);
  box-shadow: 0 10px 24px -16px rgba(16,38,58,.55); }
.feature:nth-child(2) { border-top-color: var(--primario); }
.feature:nth-child(3) { border-top-color: var(--acento); }
.feature b { display: block; margin-bottom: 2px; font-size: .92rem; color: var(--texto); }
.feature span { font-size: .79rem; line-height: 1.35; color: var(--texto); opacity: .75; }
@media (max-width: 640px) { .features { grid-template-columns: 1fr; } .hero { padding: 18px; } }

/* ---- burbujas de chat ---- */
[data-testid="stElementContainer"]:has(> [data-testid="stMarkdown"] .msg-user),
[data-testid="stElementContainer"]:has(> [data-testid="stMarkdown"] .msg-bot),
.element-container:has(> .stMarkdown .msg-user),
.element-container:has(> .stMarkdown .msg-bot) { display: none; }
.msg-user, .msg-bot { display: none; }
[data-testid="stChatMessage"] { border-radius: 20px; padding: 14px 18px; margin-bottom: 10px;
  background: var(--tarjeta); border: 1px solid rgba(16,38,58,.06);
  box-shadow: 0 12px 26px -18px rgba(16,38,58,.6); }
[data-testid="stChatMessage"]:has(.msg-bot) { border-left: 5px solid var(--secundario); }
[data-testid="stChatMessage"]:has(.msg-user) { border: none;
  background: linear-gradient(135deg, var(--primario), var(--secundario));
  box-shadow: 0 14px 28px -16px var(--primario); }
[data-testid="stChatMessage"]:has(.msg-user) * { color: #fff !important; }
[data-testid="stChatMessage"] p, [data-testid="stChatMessage"] li { line-height: 1.55; font-size: .95rem; }

/* ---- detalle de herramientas ---- */
[data-testid="stExpander"] { border: 1px dashed var(--secundario) !important; border-radius: 14px;
  background: var(--suave); }
[data-testid="stExpander"] summary p { font-size: .82rem; font-weight: 600; color: var(--primario); }

/* ---- caja de escritura ---- */
[data-testid="stBottom"], [data-testid="stBottom"] > div { background: transparent !important; }
[data-testid="stChatInput"] { border-radius: 999px; background: var(--tarjeta);
  border: 2px solid var(--secundario); box-shadow: 0 14px 30px -16px var(--primario); }
[data-testid="stChatInput"] textarea { color: var(--texto); }
[data-testid="stChatInput"] button { border-radius: 50%; color: #fff;
  background: linear-gradient(135deg, var(--primario), var(--secundario)); }

/* ---- botones (sugerencias y panel) ---- */
.stButton > button { width: 100%; border-radius: 999px; padding: .5rem 1rem; font-weight: 600;
  background: var(--tarjeta); border: 1.5px solid var(--secundario);
  box-shadow: 0 8px 18px -12px var(--primario); transition: all .2s ease; }
.stButton > button p { color: var(--primario); }
.stButton > button:hover { transform: translateY(-2px); border-color: transparent;
  background: linear-gradient(135deg, var(--primario), var(--secundario)); }
.stButton > button:hover p { color: #fff; }

/* ---- panel lateral ---- */
[data-testid="stSidebar"] { background: var(--tarjeta); border-right: 1px solid rgba(16,38,58,.08); }
.side-title { margin: 14px 0 6px; font-size: .92rem; font-weight: 700; color: var(--primario); }
.cita { margin-bottom: 8px; padding: 8px 11px; border-radius: 12px; font-size: .78rem; line-height: 1.4;
  color: var(--texto); background: var(--suave); border-left: 4px solid var(--secundario); }
.cita b { color: var(--primario); }
.vacio { font-size: .8rem; color: var(--texto); opacity: .7; }
.tool { margin: 4px 0; font-size: .77rem; color: var(--texto); }
.tool code { padding: 1px 6px; border-radius: 6px; color: var(--primario); background: var(--suave); }
.pie { margin-top: 6px; font-size: .74rem; text-align: center; color: var(--texto); opacity: .65; }
"""


def inyectar_estilos(paleta: dict) -> None:
    variables = ":root{" + "".join(f"--{k}:{v};" for k, v in paleta.items()) + "}"
    st.markdown(f"<style>{FUENTE}{variables}{CSS}</style>", unsafe_allow_html=True)


# ------------------------------------------------------------------ estado
def nueva_conversacion() -> None:
    st.session_state.agente = Agente()
    st.session_state.mensajes = []


def pedir(texto: str) -> None:
    st.session_state.pendiente = texto


# ------------------------------------------------------------------ piezas de pantalla
def encabezado() -> None:
    st.markdown(
        '<div class="hero"><div class="hero-icon">🏛️</div><div>'
        '<div class="hero-title">Asistente de trámites y citas</div>'
        '<div class="hero-sub">Registraduría · Proyecto académico Corhuila · Electiva Aplicaciones con IA</div>'
        '<div class="hero-chips"><span>🟢 En línea</span>'
        f'<span>🤖 {html.escape(MODELO)}</span><span>🛠️ 4 herramientas</span></div>'
        '</div></div>',
        unsafe_allow_html=True,
    )


def bienvenida() -> None:
    st.markdown(
        '<div class="features">'
        '<div class="feature"><b>📋 Requisitos</b><span>Qué necesitas para cédula, duplicado, tarjeta de identidad o registro civil.</span></div>'
        '<div class="feature"><b>📅 Citas</b><span>Consulta horas libres y agenda tu cita en minutos.</span></div>'
        '<div class="feature"><b>🔁 Cancelaciones</b><span>Cancela tu cita con el código que recibes al agendar.</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )
    with st.chat_message("assistant", avatar=AVATARES["assistant"]):
        marcador("assistant")
        st.markdown("¡Hola! 👋 Soy el asistente virtual de la Registraduría. "
                    "Puedo explicarte requisitos y gestionar tu cita. ¿Con qué te ayudo?")
    columnas = st.columns(2)
    for i, (etiqueta, texto) in enumerate(SUGERENCIAS):
        columnas[i % 2].button(etiqueta, key=f"sug{i}", on_click=pedir, args=(texto,))


def marcador(rol: str) -> None:
    st.markdown(f'<span class="{CLASE_MARCADOR[rol]}"></span>', unsafe_allow_html=True)


def mostrar_herramientas(usos: list) -> None:
    if usos:
        with st.expander(f"🔧 Herramientas usadas ({len(usos)})"):
            for uso in usos:
                st.json(uso)


def mostrar_mensaje(m: dict) -> None:
    with st.chat_message(m["rol"], avatar=AVATARES[m["rol"]]):
        marcador(m["rol"])
        st.markdown(m["texto"])
        mostrar_herramientas(m.get("herramientas", []))


def panel_lateral() -> None:
    with st.sidebar:
        st.markdown('<div class="side-title">🎨 Paleta de colores</div>', unsafe_allow_html=True)
        st.selectbox("Paleta", list(PALETAS), key="paleta", label_visibility="collapsed")
        if st.button("🔄 Nueva conversación"):
            nueva_conversacion()
            st.rerun()

        st.markdown('<div class="side-title">⚡ Acciones rápidas</div>', unsafe_allow_html=True)
        for i, (etiqueta, texto) in enumerate(ACCIONES):
            st.button(etiqueta, key=f"acc{i}", on_click=pedir, args=(texto,))

        st.markdown('<div class="side-title">📅 Citas agendadas</div>', unsafe_allow_html=True)
        citas = herr.listar_citas()[:6]
        if not citas:
            st.markdown('<div class="vacio">Aún no hay citas. Agenda una desde el chat.</div>',
                        unsafe_allow_html=True)
        for c in citas:
            e = html.escape
            st.markdown(
                f'<div class="cita"><b>{e(c["codigo"])}</b> · {e(c["tramite"])}<br>'
                f'{e(c["fecha"])} a las {e(c["hora"])}<br>'
                f'{e(c["nombre"])} · doc. •••{e(c["documento"][-3:])}</div>',
                unsafe_allow_html=True,
            )

        with st.expander("🛠️ Herramientas del agente (informativo)"):
            for nombre, descripcion in HERRAMIENTAS_INFO:
                st.markdown(f'<div class="tool"><code>{nombre}</code><br>{descripcion}</div>',
                            unsafe_allow_html=True)


def procesar(pregunta: str) -> None:
    st.session_state.mensajes.append({"rol": "user", "texto": pregunta, "herramientas": []})
    mostrar_mensaje({"rol": "user", "texto": pregunta})

    with st.chat_message("assistant", avatar=AVATARES["assistant"]):
        marcador("assistant")
        with st.spinner("Consultando…"):
            try:
                respuesta = st.session_state.agente.responder(pregunta)
                usos = st.session_state.agente.ultimas_herramientas
            except ERRORES_API as error:
                respuesta, usos = f"⚠️ {mensaje_error(error)}", []
        st.markdown(respuesta)
        mostrar_herramientas(usos)

    st.session_state.mensajes.append({"rol": "assistant", "texto": respuesta, "herramientas": usos})
    # Si cambió la agenda, se redibuja para que el panel lateral muestre el cambio.
    if any(u["herramienta"] in ("agendar_cita", "cancelar_cita") for u in usos):
        st.rerun()


# ------------------------------------------------------------------ programa principal
if "paleta" not in st.session_state:
    st.session_state.paleta = list(PALETAS)[0]
inyectar_estilos(PALETAS[st.session_state.paleta])

if "agente" not in st.session_state:
    try:
        nueva_conversacion()
    except RuntimeError as error:
        st.error(str(error))
        st.stop()

panel_lateral()
encabezado()

pregunta = st.chat_input("Escribe tu mensaje…") or st.session_state.pop("pendiente", None)

if not st.session_state.mensajes and not pregunta:
    bienvenida()

for mensaje in st.session_state.mensajes:
    mostrar_mensaje(mensaje)

if pregunta:
    procesar(pregunta)

st.markdown('<div class="pie">ℹ️ Información de apoyo: verifica siempre en registraduria.gov.co · '
            'Proyecto académico, no es un canal oficial.</div>', unsafe_allow_html=True)
