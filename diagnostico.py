"""Diagnóstico de conexión con Gemini.  Uso:  python diagnostico.py

Prueba varias veces la conexión a Google/Gemini (normal y forzando IPv4) y a otra
alternativa, y dice qué conviene hacer. No necesita saldo; usa tu GEMINI_API_KEY solo
para una llamada pequeña al final.
"""
import os
import socket
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

HOST = "generativelanguage.googleapis.com"
INTENTOS = 6


def probar(nombre: str, url: str, ipv4: bool = False) -> int:
    transporte = httpx.HTTPTransport(local_address="0.0.0.0") if ipv4 else None
    tiempos, fallos = [], []
    with httpx.Client(timeout=15, transport=transporte) as cliente:
        for _ in range(INTENTOS):
            inicio = time.time()
            try:
                cliente.get(url)  # cualquier respuesta HTTP (aunque sea 404) prueba la conexión
                tiempos.append(time.time() - inicio)
            except httpx.HTTPError as error:
                fallos.append(type(error).__name__)
            time.sleep(0.5)
    resumen = f"{len(tiempos)}/{INTENTOS} conexiones OK"
    if tiempos:
        resumen += f", promedio {sum(tiempos) / len(tiempos):.2f} s"
    if fallos:
        resumen += f" | errores: {', '.join(sorted(set(fallos)))}"
    print(f"  [{'OK' if not fallos else 'FALLA'}] {nombre}: {resumen}")
    return len(tiempos)


def main() -> None:
    print("\n1) Resolución de nombres (DNS)")
    for familia, etiqueta in ((socket.AF_INET, "IPv4"), (socket.AF_INET6, "IPv6")):
        try:
            direccion = socket.getaddrinfo(HOST, 443, familia)[0][4][0]
            print(f"  [OK] {etiqueta}: {direccion}")
        except OSError as error:
            print(f"  [--] {etiqueta}: no disponible ({error})")

    print(f"\n2) Conexión HTTPS ({INTENTOS} intentos cada una)")
    internet = probar("Internet en general (google.com)", "https://www.google.com")
    normal = probar("Gemini - conexión normal", f"https://{HOST}/")
    ipv4 = probar("Gemini - forzando IPv4", f"https://{HOST}/", ipv4=True)
    groq = probar("Groq (alternativa)", "https://api.groq.com")

    print("\n3) Llamada real al modelo")
    clave = os.getenv("GEMINI_API_KEY")
    if not clave:
        print("  [--] No hay GEMINI_API_KEY en .env; se omite.")
    else:
        from google import genai
        from google.genai import types

        cliente = genai.Client(api_key=clave, http_options=types.HttpOptions(timeout=30000))
        modelo = os.getenv("MODELO", "gemini-3.1-flash-lite")
        for i in range(3):
            inicio = time.time()
            try:
                cliente.models.generate_content(model=modelo, contents="Responde solo: ok")
                print(f"  [OK] intento {i + 1}: respondió en {time.time() - inicio:.1f} s")
            except Exception as error:  # noqa: BLE001 - es un diagnóstico, se muestra todo
                print(f"  [FALLA] intento {i + 1}: {type(error).__name__}: {str(error)[:110]}")

    print("\n4) Conclusión")
    if internet == 0:
        print("  Este computador no tiene internet estable. Revisa Wi-Fi/cable o prueba con los datos del celular.")
    elif normal < INTENTOS and ipv4 > normal:
        print("  La conexión por IPv4 funciona mejor. Agrega  FORZAR_IPV4=1  al archivo .env y reinicia.")
    elif normal == 0 and ipv4 == 0:
        print("  Hay internet pero no llegas a Gemini: revisa VPN, antivirus/firewall o prueba con otra red.")
    elif normal < INTENTOS:
        print("  La conexión es intermitente. Prueba otra red (datos del celular) y desactiva VPN/antivirus web.")
        if groq == INTENTOS:
            print("  Groq sí conecta bien desde aquí: sería un buen respaldo si Gemini sigue fallando.")
    else:
        print("  La conexión está bien. Si el agente falló antes, fue un problema temporal.")


if __name__ == "__main__":
    main()
