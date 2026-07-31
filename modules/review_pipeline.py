# -*- coding: utf-8 -*-
"""
Módulo 2: Ingesta flexible de datos y optimización opcional de tokens
para análisis de reseñas en Excel.

- Modo A / Modo B de carga (archivo único o carpeta) -> utils.load_excel_source
- Bandera optent_tokens: True/False
- Clasificación de cada reseña en {"error_type": ..., "component": ...}
  (usa Ollama/llama3 si está disponible; si no, reglas por palabras clave)
- Análisis de impacto económico para 10,000 reseñas/día
- Exporta resultados a Excel y JSON
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import utils

VOLUME_PER_DAY = 10_000
PRICE_PER_MILLION = 2.50
OUTPUT_DIR = Path("/mnt/user-data/outputs")


def _classify_review(text: str) -> dict:
    if utils.ollama_available():
        prompt = (
            "Extract the main technical issue from this app review. "
            "Return ONLY a JSON object with exactly these keys: "
            '"error_type" (a short snake_case label like "crash", "login_error", '
            '"slow_performance", "ui_bug", "upload_error", or "unknown") and '
            '"component" (a short snake_case label of the affected feature, e.g. '
            '"profile_picture_upload", "authentication", "payments", "general").\n\n'
            f"Review:\n{text}"
        )
        result = utils.ollama_extract_json(prompt)
        if result.get("error_type") and result.get("component"):
            return {"error_type": result["error_type"], "component": result["component"]}
    return utils.rule_based_review_extraction(text)


def run():
    print("\n" + "=" * 70)
    print(" MÓDULO 2: Análisis de reseñas de usuarios (Excel)")
    print("=" * 70)

    try:
        df = utils.load_excel_source()
    except Exception as e:
        print(f"[ERROR] {e}")
        return

    try:
        text_col = utils.detect_text_column(df)
    except Exception as e:
        print(f"[ERROR] {e}")
        return
    print(f"Columna de texto detectada: '{text_col}'")

    flag = input("\n¿Activar optimización/traducción de tokens antes del análisis? "
                 "(optent_tokens) [s/n]: ").strip().lower()
    optent_tokens = flag == "s"

    if not utils.ollama_available():
        print("[Nota] Ollama no está corriendo: se usará clasificación por reglas "
              "(palabras clave) en lugar de un LLM. Para usar llama3 localmente, "
              "instala Ollama y ejecuta 'ollama pull llama3'.")

    results = []
    tokens_direct_total = 0
    tokens_optimized_total = 0

    n = len(df)
    print(f"\nProcesando {n} reseña(s)...")
    for i, row in df.iterrows():
        raw_text = str(row[text_col]) if pd.notna(row[text_col]) else ""
        if not raw_text.strip():
            continue

        tokens_direct = utils.count_tokens(raw_text)
        tokens_direct_total += tokens_direct

        if optent_tokens:
            translated = utils.translate_es_en(raw_text)
            tokens_opt = utils.count_tokens(translated)
            text_for_llm = translated
        else:
            tokens_opt = tokens_direct
            text_for_llm = raw_text
        tokens_optimized_total += tokens_opt

        extraction = _classify_review(text_for_llm)

        results.append({
            "row_index": int(i),
            "original_text": raw_text,
            "tokens_direct": tokens_direct,
            "tokens_processed": tokens_opt,
            "error_type": extraction.get("error_type", "unknown"),
            "component": extraction.get("component", "general"),
        })

        if (i + 1) % 25 == 0 or (i + 1) == n:
            print(f"  Procesadas {i + 1}/{n}")

    if not results:
        print("No se encontró texto válido para procesar.")
        return

    processed = len(results)
    avg_tokens_direct = tokens_direct_total / processed
    avg_tokens_opt = tokens_optimized_total / processed

    daily_tokens_direct = avg_tokens_direct * VOLUME_PER_DAY
    daily_tokens_opt = avg_tokens_opt * VOLUME_PER_DAY
    daily_cost_direct = utils.cost_usd(daily_tokens_direct, PRICE_PER_MILLION)
    daily_cost_opt = utils.cost_usd(daily_tokens_opt, PRICE_PER_MILLION)
    diff = daily_cost_direct - daily_cost_opt

    print("\n--- IMPACTO ECONÓMICO (proyección a 10,000 reseñas/día) ---")
    print(f"Promedio tokens/reseña (directo, ES):    {avg_tokens_direct:.1f}")
    print(f"Promedio tokens/reseña (procesado):       {avg_tokens_opt:.1f}")
    print(f"Costo diario estimado (directo):          {utils.format_usd(daily_cost_direct)}")
    print(f"Costo diario estimado (procesado):        {utils.format_usd(daily_cost_opt)}")
    if optent_tokens:
        signo = "ahorro" if diff > 0 else "sobrecosto"
        print(f"Diferencia diaria ({signo} por traducir antes de analizar): "
              f"{utils.format_usd(abs(diff))}  |  Mensual: {utils.format_usd(abs(diff) * 30)}")
    else:
        print("(optent_tokens estaba desactivado: no hubo traducción, procesado = directo)")

    _export_results(results, {
        "modo": "review_pipeline",
        "optent_tokens": optent_tokens,
        "volumen_referencia_dia": VOLUME_PER_DAY,
        "precio_por_millon_usd": PRICE_PER_MILLION,
        "avg_tokens_direct": avg_tokens_direct,
        "avg_tokens_processed": avg_tokens_opt,
        "costo_diario_directo_usd": daily_cost_direct,
        "costo_diario_procesado_usd": daily_cost_opt,
    })


def _export_results(results: list, summary: dict):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    df_out = pd.DataFrame(results)
    xlsx_path = OUTPUT_DIR / f"reviews_analisis_{ts}.xlsx"
    df_out.to_excel(xlsx_path, index=False)

    json_path = OUTPUT_DIR / f"reviews_analisis_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, ensure_ascii=False, indent=2)

    print(f"\nResultados exportados:\n  - {xlsx_path}\n  - {json_path}")
