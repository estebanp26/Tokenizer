# -*- coding: utf-8 -*-
"""
Suite de herramientas LLM para el sector salud.
Menú principal con 3 funcionalidades:

 1) Ahorrador de tokens / optimizador de prompts (ES -> EN)
 2) Análisis de reseñas de usuarios en Excel (con optimización opcional de tokens)
 3) Gestión de citas médicas en Excel (con evaluación opcional de tokenización)

Ejecutar con:  python main.py
"""

import sys

from modules import prompt_optimizer, review_pipeline, appointment_pipeline


BANNER = r"""
╔══════════════════════════════════════════════════════════════════╗
║   SUITE DE PROCESAMIENTO LLM - SECTOR SALUD                       ║
║   Tokenización · Traducción · Ingesta Excel · Análisis            ║
╚══════════════════════════════════════════════════════════════════╝
"""


def show_menu():
    print(BANNER)
    print("Selecciona una funcionalidad:\n")
    print("  [1] Ahorrador de tokens / Optimizador de prompts (ES -> EN)")
    print("  [2] Análisis de reseñas de usuarios (Excel)")
    print("  [3] Gestión de citas médicas (Excel)")
    print("  [0] Salir\n")


def main():
    while True:
        show_menu()
        choice = input("Opción: ").strip()

        if choice == "1":
            prompt_optimizer.run()
        elif choice == "2":
            review_pipeline.run()
        elif choice == "3":
            appointment_pipeline.run()
        elif choice == "0":
            print("Saliendo. ¡Hasta luego!")
            sys.exit(0)
        else:
            print("Opción inválida, intenta de nuevo.")

        input("\nPresiona Enter para volver al menú...")


if __name__ == "__main__":
    main()
