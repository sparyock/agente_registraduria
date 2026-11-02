"""Interfaz de consola del agente.  Uso:  python consola.py"""
from agente import ERRORES_API, Agente, mensaje_error


def main() -> None:
    try:
        agente = Agente()
    except RuntimeError as error:
        print(error)
        return

    print("=== Asistente Registraduría (proyecto académico) ===")
    print("Escribe tu mensaje. Comandos: /reiniciar  |  salir\n")

    while True:
        try:
            entrada = input("Tú: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not entrada:
            continue
        if entrada.lower() in {"salir", "exit", "quit"}:
            break
        if entrada.lower() == "/reiniciar":
            agente.reiniciar()
            print("Conversación reiniciada.\n")
            continue

        try:
            respuesta = agente.responder(entrada)
        except ERRORES_API as error:
            print(f"\n[Error con el modelo] {mensaje_error(error)}\n")
            continue

        for uso in agente.ultimas_herramientas:
            print(f"  [herramienta] {uso['herramienta']}({uso['entrada']})")
        print(f"\nAgente: {respuesta}\n")

    print("¡Hasta luego!")


if __name__ == "__main__":
    main()
