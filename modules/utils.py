# -*- coding: utf-8 -*-
"""
utils.py
Funciones compartidas por los 3 módulos:
 - Conteo de tokens (tiktoken / o200k_base)
 - Cálculo de costo USD
 - Traducción ES -> EN (deep_translator)
 - Cliente opcional para Ollama (LLM local, ej. llama3) para extracción estructurada
 - Lectura flexible de Excel (archivo único o carpeta completa)
"""

import glob
import json
import os
import re
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# 1. TOKENIZACIÓN Y COSTOS
# ---------------------------------------------------------------------------

_ENCODER = None
_ENCODER_FAILED = False
_WARNED_FALLBACK = False


def get_encoder():
    """Carga (una sola vez) el encoder o200k_base de tiktoken.

    NOTA: la primera vez que se ejecuta, tiktoken necesita descargar el
    archivo de vocabulario desde internet. Después queda cacheado en disco
    y funciona sin conexión. Si la descarga falla, count_tokens() cae a
    una estimación aproximada.
    """
    global _ENCODER
    if _ENCODER is None:
        import tiktoken
        _ENCODER = tiktoken.get_encoding("o200k_base")
    return _ENCODER


def _estimate_tokens_fallback(text: str) -> int:
    """Estimación aproximada (~4.3 caracteres/token) usada SOLO si tiktoken
    no pudo descargar su vocabulario. No es exacta, pero mantiene el
    programa funcionando sin conexión."""
    global _WARNED_FALLBACK
    if not _WARNED_FALLBACK:
        print("  [WARN] tiktoken no pudo cargar 'o200k_base' (sin internet o red "
              "restringida). Usando una ESTIMACIÓN aproximada de tokens hasta "
              "que haya conexión disponible.")
        _WARNED_FALLBACK = True
    return max(1, round(len(text) / 4.3))


def count_tokens(text: str) -> int:
    global _ENCODER_FAILED
    if not text:
        return 0
    if _ENCODER_FAILED:
        return _estimate_tokens_fallback(text)
    try:
        enc = get_encoder()
        return len(enc.encode(text))
    except Exception:
        _ENCODER_FAILED = True
        return _estimate_tokens_fallback(text)


def cost_usd(tokens: int, price_per_million: float = 2.50) -> float:
    return (tokens / 1_000_000) * price_per_million


def format_usd(value: float) -> str:
    return f"${value:,.4f}"


# ---------------------------------------------------------------------------
# 2. TRADUCCIÓN ES -> EN
# ---------------------------------------------------------------------------

def translate_es_en(text: str) -> str:
    """Traduce texto de español a inglés usando deep_translator (Google).

    Requiere conexión a internet. Si falla (sin red, límite de la API, etc.)
    se devuelve el texto original y se marca el error en consola.
    """
    if not text or not text.strip():
        return text
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source="es", target="en").translate(text)
    except Exception as e:
        print(f"  [WARN] No se pudo traducir ('{e}'). Se usa el texto original.")
        return text


# ---------------------------------------------------------------------------
# 3. CLIENTE OPCIONAL PARA OLLAMA (LLM LOCAL)
# ---------------------------------------------------------------------------

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"


def ollama_available() -> bool:
    """Comprueba si hay un servidor Ollama corriendo localmente."""
    try:
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=1.5)
        return r.status_code == 200
    except Exception:
        return False


def ollama_extract_json(prompt: str, model: str = OLLAMA_MODEL) -> dict:
    """Pide a un modelo local (por defecto llama3 vía Ollama) que devuelva
    un JSON estructurado. Si Ollama no está disponible o falla, devuelve
    un dict vacío para que el llamador use el fallback basado en reglas.
    """
    try:
        import requests
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
        r = requests.post(OLLAMA_URL, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        raw = data.get("response", "{}")
        return json.loads(raw)
    except Exception as e:
        print(f"  [WARN] Ollama no disponible/falló ('{e}'). Usando extracción por reglas.")
        return {}


# ---------------------------------------------------------------------------
# 4. LECTURA FLEXIBLE DE EXCEL (Modo A: archivo único / Modo B: carpeta)
# ---------------------------------------------------------------------------

def load_excel_source() -> pd.DataFrame:
    """Pregunta al usuario si quiere cargar un archivo único o una carpeta
    completa de .xlsx y devuelve un único DataFrame consolidado.
    """
    print("\n¿Cómo quieres cargar los datos?")
    print("  [1] Archivo único (.xlsx)")
    print("  [2] Carpeta local (consolida todos los .xlsx encontrados)")
    choice = input("Selecciona una opción (1/2): ").strip()

    frames = []
    if choice == "1":
        path = input("Ruta del archivo .xlsx: ").strip().strip('"')
        frames.append(_read_one_excel(path))
    elif choice == "2":
        folder = input("Ruta de la carpeta: ").strip().strip('"')
        files = sorted(glob.glob(os.path.join(folder, "*.xlsx")))
        if not files:
            raise FileNotFoundError(f"No se encontraron archivos .xlsx en '{folder}'")
        print(f"  Se encontraron {len(files)} archivo(s) .xlsx. Consolidando...")
        for f in files:
            try:
                frames.append(_read_one_excel(f))
            except Exception as e:
                print(f"  [WARN] No se pudo leer '{f}': {e}")
    else:
        raise ValueError("Opción inválida.")

    df = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
    print(f"  Total de filas consolidadas: {len(df)}")
    return df


def _read_one_excel(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No existe el archivo: {path}")
    return pd.read_excel(p)


def detect_text_column(df: pd.DataFrame, name_hints=None) -> str:
    """Detecta automáticamente la columna que contiene el texto principal.

    1) Busca coincidencias por nombre (name_hints).
    2) Si no encuentra, elige la columna de tipo texto con mayor longitud
       promedio de contenido (heurística: es la más "narrativa").
    """
    name_hints = name_hints or ["reseña", "resena", "review", "comentario",
                                 "texto", "mensaje", "mensaje_texto", "descripcion"]
    cols_lower = {c.lower(): c for c in df.columns}
    for hint in name_hints:
        for lower, original in cols_lower.items():
            if hint in lower:
                return original

    # Fallback: columna de texto (object) con mayor longitud promedio
    candidate, best_len = None, -1
    for c in df.columns:
        if df[c].dtype == object:
            avg_len = df[c].dropna().astype(str).str.len().mean()
            if pd.notna(avg_len) and avg_len > best_len:
                candidate, best_len = c, avg_len
    if candidate is None:
        raise ValueError("No se pudo detectar una columna de texto en el archivo.")
    return candidate


def detect_id_column(df: pd.DataFrame, name_hints=None):
    name_hints = name_hints or ["paciente_id", "id_paciente", "id", "paciente"]
    cols_lower = {c.lower(): c for c in df.columns}
    for hint in name_hints:
        for lower, original in cols_lower.items():
            if hint == lower or hint in lower:
                return original
    return None


# ---------------------------------------------------------------------------
# 5. EXTRACCIÓN POR REGLAS (fallback sin Ollama) para el módulo de reseñas
# ---------------------------------------------------------------------------

_ERROR_KEYWORDS = {
    "crash": ["cierra", "crashe", "se cierra", "falla", "se detiene", "crash"],
    "login_error": ["iniciar sesión", "login", "contraseña", "no puedo entrar"],
    "slow_performance": ["lento", "tarda", "demora", "carga lento"],
    "ui_bug": ["no se ve", "pantalla en blanco", "botón no funciona", "visual"],
    "upload_error": ["subir", "cargar foto", "no sube", "upload"],
}

_COMPONENT_KEYWORDS = {
    "profile_picture_upload": ["foto de perfil", "galería", "avatar"],
    "authentication": ["sesión", "contraseña", "login"],
    "payments": ["pago", "tarjeta", "cobro"],
    "notifications": ["notificación", "alerta"],
    "general": [],
}


def rule_based_review_extraction(text: str) -> dict:
    t = text.lower()
    error_type = "unknown"
    for etype, kws in _ERROR_KEYWORDS.items():
        if any(kw in t for kw in kws):
            error_type = etype
            break
    component = "general"
    for comp, kws in _COMPONENT_KEYWORDS.items():
        if any(kw in t for kw in kws):
            component = comp
            break
    return {"error_type": error_type, "component": component}


# ---------------------------------------------------------------------------
# 6. EXTRACCIÓN POR REGLAS (fallback sin Ollama) para citas médicas
# ---------------------------------------------------------------------------

_ACCION_KEYWORDS = {
    "reprogramar": ["reprogramar", "reprogramación", "cambiar la cita", "mover mi cita"],
    "cancelar": ["cancelar", "anular"],
    "confirmar": ["confirmar", "confirmación"],
    "agendar": ["agendar", "solicitar una cita", "nueva cita"],
}

_ESPECIALIDAD_KEYWORDS = [
    "cardiólogo", "cardiologia", "dermatólogo", "dermatologia", "pediatra",
    "ginecólogo", "ginecologia", "traumatólogo", "traumatologia",
    "oftalmólogo", "oftalmologia", "psiquiatra", "psicólogo", "nutricionista",
    "medicina general", "odontólogo", "odontologia",
]

_HORARIO_KEYWORDS = {
    "manana": ["mañana", "am"],
    "tarde": ["tarde", "pm"],
    "noche": ["noche"],
}


def rule_based_appointment_extraction(text: str) -> dict:
    t = text.lower()
    accion = "no_identificada"
    for a, kws in _ACCION_KEYWORDS.items():
        if any(kw in t for kw in kws):
            accion = a
            break
    especialidad = "no_identificada"
    for esp in _ESPECIALIDAD_KEYWORDS:
        if esp in t:
            especialidad = re.sub(r"[óáéíú]", lambda m: {"ó": "o", "á": "a", "é": "e",
                                                            "í": "i", "ú": "u"}[m.group()], esp)
            break
    horario = "no_especificado"
    for h, kws in _HORARIO_KEYWORDS.items():
        if any(kw in t for kw in kws):
            horario = h
            break
    return {"accion": accion, "especialidad": especialidad, "preferencia_horario": horario}


def word_count(text: str) -> int:
    return len(re.findall(r"\w+", text or ""))
