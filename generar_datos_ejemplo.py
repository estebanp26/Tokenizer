# -*- coding: utf-8 -*-
"""
Genera archivos Excel de ejemplo para probar rápidamente los módulos 2 y 3
sin depender de datos reales.

Uso:
    python generar_datos_ejemplo.py
"""

from pathlib import Path

import pandas as pd

OUT_DIR = Path("./datos_ejemplo")


def generar_reviews():
    data = {
        "usuario_id": [f"U{i:03d}" for i in range(1, 9)],
        "reseña": [
            "La aplicación se cierra inesperadamente cada vez que intento subir una foto de perfil desde la galería de mi teléfono.",
            "No puedo iniciar sesión, me dice que la contraseña es incorrecta aunque la acabo de restablecer.",
            "La app tarda muchísimo en cargar la pantalla de inicio, a veces hasta un minuto.",
            "El botón de pagar no responde cuando intento confirmar mi compra con tarjeta.",
            "La pantalla se queda en blanco después de actualizar la app a la última versión.",
            "No me llegan las notificaciones de nuevos mensajes aunque las tengo activadas.",
            "Excelente app, todo funciona perfecto, sin quejas.",
            "Cada vez que subo una imagen desde la galería la app se crashea de inmediato.",
        ],
    }
    df = pd.DataFrame(data)
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / "reviews_ejemplo.xlsx"
    df.to_excel(path, index=False)
    print(f"Generado: {path}")


def generar_citas():
    data = {
        "paciente_id": [f"P{i:03d}" for i in range(1, 9)],
        "mensaje_texto": [
            "Deseo solicitar la reprogramación de mi cita médica con el cardiólogo para la próxima semana en el horario de la mañana.",
            "Quiero cancelar mi cita con el dermatólogo de este viernes por la tarde.",
            "Necesito confirmar mi cita de mañana con el pediatra.",
            "Quisiera agendar una nueva cita con el ginecólogo para la semana que viene, preferiblemente en la noche.",
            "Buenas, ¿podrían reprogramar mi cita con el traumatólogo? No puedo asistir en la mañana.",
            "Quiero confirmar la cita con el oftalmólogo del jueves en la tarde.",
            "Solicito cancelar mi cita con el psiquiatra de este mes.",
            "Me gustaría reprogramar mi consulta con el nutricionista para la tarde de la próxima semana.",
        ],
    }
    df = pd.DataFrame(data)
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / "citas_ejemplo.xlsx"
    df.to_excel(path, index=False)
    print(f"Generado: {path}")


if __name__ == "__main__":
    generar_reviews()
    generar_citas()
