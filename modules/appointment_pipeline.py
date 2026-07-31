# -*- coding: utf-8 -*-
"""
Módulo 3: Ingesta flexible y evaluación de costo/tokenización para
gestión de citas médicas vía Excel.

- Modo A / Modo B de carga -> utils.load_excel_source
- Bandera optimizar_tokens: True/False
- Extracción de intención {"accion", "especialidad", "preferencia_horario"}
  (Ollama/llama3 si está disponible; si no, reglas por palabras clave)
- Tasa de fragmentación de términos médicos ES vs EN (tokens por palabra)
- Proyección de costo diario/mensual para 15,000 mensajes/día
- Exporta resultados a Excel y JSON
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import utils

VOLUME_PER_DAY = 15_000
PRICE_PER_MILLION = 2.50
OUTPUT_DIR = Path("/mnt/user-data/outputs")


def _extract_intent(text: str) -> dict:
    if utils.ollama_available():
        prompt = (
            "Extract the intent from this patient message about a medical "
            "appointment, written in Spanish. Return ONLY a JSON object with "
            'exactly these keys: "accion" (one of "reprogramar", "cancelar", '
            '"confirmar", "agendar", "no_identificada"), "especialidad" (the '
            "medical specialty mentioned, in Spanish without accents, or "
            '"no_identificada"), and "preferencia_horario" (one of "manana", '
            '"tarde", "noche", "no_especificado").\n\n'
            f"Message:\n{text}"
        )
        result = utils.ollama_extract_json(prompt)
        if result.get("accion"):
            return result
    return utils.rule_based_appointment_extraction(text)


def run():
    print("\n" + "=" * 70)
    print(" MÓDULO 3: Gestión de citas médicas (Excel)")
    print("=" * 70)

    try:
        df = utils.load_excel_source()
    except Exception as e:
        print(f"[ERROR] {e}")
        return

    try:
        text_col = utils.detect_text_column(df, name_hints=["mensaje_texto", "mensaje", "texto"])
    except Exception as e:
        print(f"[ERROR] {e}")
        return
    id_col = utils.detect_id_column(df)
    print(f"Columna de texto detectada: '{text_col}'"
          + (f" | Columna de ID: '{id_col}'" if id_col else " | No se detectó columna de ID"))

    flag = input("\n¿Activar evaluación/optimización de tokens (traducción previa)? "
                 "(optimizar_tokens) [s/n]: ").strip().lower()
    optimizar_tokens = flag == "s"

    if not utils.ollama_available():
        print("[Nota] Ollama no está corriendo: se usará extracción por reglas "
              "(palabras clave) en lugar de un LLM. Para usar llama3 localmente, "
              "instala Ollama y ejecuta 'ollama pull llama3'.")

    results = []
    tokens_es_total = 0
    tokens_en_total = 0
    words_es_total = 0
    words_en_total = 0

    n = len(df)
    print(f"\nProcesando {n} mensaje(s)...")
    for i, row in df.iterrows():
        raw_text = str(row[text_col]) if pd.notna(row[text_col]) else ""
        if not raw_text.strip():
            continue

        tokens_es = utils.count_tokens(raw_text)
        words_es = utils.word_count(raw_text)
        tokens_es_total += tokens_es
        words_es_total += words_es

        if optimizar_tokens:
            translated = utils.translate_es_en(raw_text)
            tokens_en = utils.count_tokens(translated)
            words_en = utils.word_count(translated)
            text_for_llm = translated
        else:
            translated = None
            tokens_en = None
            words_en = None
            text_for_llm = raw_text

        if tokens_en is not None:
            tokens_en_total += tokens_en
            words_en_total += words_en

        intent = _extract_intent(text_for_llm)

        results.append({
            "row_index": int(i),
            "paciente_id": row[id_col] if id_col else None,
            "mensaje_original": raw_text,
            "tokens_es": tokens_es,
            "tokens_en": tokens_en,
            "accion": intent.get("accion", "no_identificada"),
            "especialidad": intent.get("especialidad", "no_identificada"),
            "preferencia_horario": intent.get("preferencia_horario", "no_especificado"),
        })

        if (i + 1) % 25 == 0 or (i + 1) == n:
            print(f"  Procesados {i + 1}/{n}")

    if not results:
        print("No se encontró texto válido para procesar.")
        return

    processed = len(results)
    avg_tokens_es = tokens_es_total / processed
    daily_tokens_es = avg_tokens_es * VOLUME_PER_DAY
    daily_cost_es = utils.cost_usd(daily_tokens_es, PRICE_PER_MILLION)

    print("\n--- FRAGMENTACIÓN Y PROYECCIÓN ECONÓMICA (15,000 mensajes/día) ---")
    print(f"Promedio tokens/mensaje (ES):  {avg_tokens_es:.1f}")
    print(f"Costo diario (ES, sin traducir):   {utils.format_usd(daily_cost_es)}")
    print(f"Costo mensual (ES, sin traducir):  {utils.format_usd(daily_cost_es * 30)}")

    summary = {
        "modo": "appointment_pipeline",
        "optimizar_tokens": optimizar_tokens,
        "volumen_referencia_dia": VOLUME_PER_DAY,
        "precio_por_millon_usd": PRICE_PER_MILLION,
        "avg_tokens_es": avg_tokens_es,
        "costo_diario_es_usd": daily_cost_es,
        "costo_mensual_es_usd": daily_cost_es * 30,
    }

    if optimizar_tokens and words_en_total:
        avg_tokens_en = tokens_en_total / processed
        daily_tokens_en = avg_tokens_en * VOLUME_PER_DAY
        daily_cost_en = utils.cost_usd(daily_tokens_en, PRICE_PER_MILLION)
        frag_es = tokens_es_total / words_es_total  # tokens por palabra, ES
        frag_en = tokens_en_total / words_en_total  # tokens por palabra, EN

        print(f"Promedio tokens/mensaje (EN):  {avg_tokens_en:.1f}")
        print(f"Costo diario (EN, traducido):      {utils.format_usd(daily_cost_en)}")
        print(f"Costo mensual (EN, traducido):     {utils.format_usd(daily_cost_en * 30)}")
        print(f"Fragmentación (tokens/palabra) ES: {frag_es:.2f}  |  EN: {frag_en:.2f}")

        diff_day = daily_cost_es - daily_cost_en
        signo = "ahorro" if diff_day > 0 else "sobrecosto"
        print(f"Diferencia diaria por traducir antes de procesar ({signo}): "
              f"{utils.format_usd(abs(diff_day))}  |  Mensual: {utils.format_usd(abs(diff_day) * 30)}")

        summary.update({
            "avg_tokens_en": avg_tokens_en,
            "costo_diario_en_usd": daily_cost_en,
            "costo_mensual_en_usd": daily_cost_en * 30,
            "fragmentacion_tokens_por_palabra_es": frag_es,
            "fragmentacion_tokens_por_palabra_en": frag_en,
            "diferencia_diaria_usd": diff_day,
            "diferencia_mensual_usd": diff_day * 30,
        })
    else:
        print("(optimizar_tokens desactivado: no se tradujo, sólo se midió el "
              "español directamente)")

    _export_results(results, summary)


def _export_results(results: list, summary: dict):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    df_out = pd.DataFrame(results)
    xlsx_path = OUTPUT_DIR / f"citas_analisis_{ts}.xlsx"
    df_out.to_excel(xlsx_path, index=False)

    json_path = OUTPUT_DIR / f"citas_analisis_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, ensure_ascii=False, indent=2)

    print(f"\nResultados exportados:\n  - {xlsx_path}\n  - {json_path}")
