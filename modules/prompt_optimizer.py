# -*- coding: utf-8 -*-
"""
Módulo 1: Ahorrador de tokens y optimizador de prompts.

Flujo:
 1) El usuario escribe/pega un prompt en español.
 2) Se traduce a inglés (deep_translator).
 3) Se cuentan tokens de ambas versiones (tiktoken o200k_base) y se compara
    costo estimado.
 4) Se intenta una compresión adicional del prompt (vía Ollama/llama3 si
    está disponible, o con una heurística simple de limpieza si no lo está)
    y se muestra si hay más ahorro posible.
"""

from . import utils


def _heuristic_compress(text: str) -> str:
    """Compresión simple sin LLM: elimina relleno/cortesías típicas de
    prompts y espacios redundantes, sin tocar el contenido técnico."""
    fillers = [
        "por favor", "me gustaría que", "quisiera que", "podrías", "puedes",
        "me podrías ayudar a", "te pido que", "necesito que", "quiero que",
        "please", "could you", "would you", "i would like you to",
        "i want you to", "can you",
    ]
    out = text
    for f in fillers:
        out = out.replace(f, "").replace(f.capitalize(), "")
    out = " ".join(out.split())
    return out.strip(" ,.")


def _llm_compress(text_en: str) -> str:
    """Intenta comprimir el prompt (en inglés) usando un LLM local vía
    Ollama (llama3). Si no está disponible, cae al método heurístico."""
    if utils.ollama_available():
        prompt = (
            "Rewrite the following prompt to be as short as possible while "
            "preserving 100% of its instructions and meaning. Return ONLY a "
            "JSON object: {\"optimized_prompt\": \"...\"}.\n\n"
            f"Prompt:\n{text_en}"
        )
        result = utils.ollama_extract_json(prompt)
        if result.get("optimized_prompt"):
            return result["optimized_prompt"]
    return _heuristic_compress(text_en)


def run():
    print("\n" + "=" * 70)
    print(" MÓDULO 1: Ahorrador de tokens / Optimizador de prompts (ES -> EN)")
    print("=" * 70)
    print("Escribe o pega el prompt en español (termina con una línea vacía):")

    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    text_es = "\n".join(lines).strip()

    if not text_es:
        print("No se ingresó texto. Volviendo al menú.")
        return

    print("\nTraduciendo a inglés...")
    text_en = utils.translate_es_en(text_es)

    tokens_es = utils.count_tokens(text_es)
    tokens_en = utils.count_tokens(text_en)
    cost_es = utils.cost_usd(tokens_es)
    cost_en = utils.cost_usd(tokens_en)

    print("\n--- COMPARACIÓN INICIAL ---")
    print(f"[ES] '{text_es[:80]}{'...' if len(text_es) > 80 else ''}'")
    print(f"     Tokens: {tokens_es}  |  Costo estimado: {utils.format_usd(cost_es)}")
    print(f"[EN] '{text_en[:80]}{'...' if len(text_en) > 80 else ''}'")
    print(f"     Tokens: {tokens_en}  |  Costo estimado: {utils.format_usd(cost_en)}")

    if tokens_en < tokens_es:
        ahorro = tokens_es - tokens_en
        pct = (ahorro / tokens_es * 100) if tokens_es else 0
        mejor = "INGLÉS"
        print(f"\n>> La versión en INGLÉS es más eficiente: ahorra {ahorro} tokens "
              f"({pct:.1f}%) y {utils.format_usd(cost_es - cost_en)} por cada envío.")
    elif tokens_es < tokens_en:
        ahorro = tokens_en - tokens_es
        pct = (ahorro / tokens_en * 100) if tokens_en else 0
        mejor = "ESPAÑOL"
        print(f"\n>> La versión en ESPAÑOL es más eficiente: ahorra {ahorro} tokens "
              f"({pct:.1f}%) y {utils.format_usd(cost_en - cost_es)} por cada envío.")
    else:
        mejor = "EMPATE"
        print("\n>> Ambas versiones usan el mismo número de tokens.")

    # Paso extra: intentar comprimir aún más la versión ganadora
    base_text = text_en if mejor != "ESPAÑOL" else text_es
    print(f"\nBuscando una compresión adicional sobre la versión en {mejor if mejor!='EMPATE' else 'inglés'}...")
    compressed = _llm_compress(base_text) if mejor != "ESPAÑOL" else _heuristic_compress(base_text)
    tokens_compressed = utils.count_tokens(compressed)
    tokens_base = tokens_en if mejor != "ESPAÑOL" else tokens_es

    print("\n--- OPTIMIZACIÓN ADICIONAL ---")
    print(f"Versión comprimida: '{compressed[:100]}{'...' if len(compressed) > 100 else ''}'")
    print(f"Tokens: {tokens_compressed}  |  Costo estimado: {utils.format_usd(utils.cost_usd(tokens_compressed))}")

    if tokens_compressed < tokens_base:
        extra_ahorro = tokens_base - tokens_compressed
        print(f">> Se logró un ahorro adicional de {extra_ahorro} tokens "
              f"({extra_ahorro / tokens_base * 100:.1f}%) sobre la mejor versión.")
    else:
        print(">> No se encontró una compresión adicional significativa; "
              "la versión anterior ya es cercana al óptimo.")

    print("\n--- RESUMEN FINAL ---")
    print(f"Prompt original (ES): {tokens_es} tokens")
    print(f"Prompt traducido (EN): {tokens_en} tokens")
    print(f"Prompt final optimizado: {tokens_compressed} tokens "
          f"({utils.format_usd(utils.cost_usd(tokens_compressed))})")
    if not utils.ollama_available():
        print("\n[Nota] Ollama no está corriendo localmente: la compresión adicional "
              "usó una heurística simple. Para mejores resultados, instala Ollama "
              "y descarga el modelo 'llama3' (ollama pull llama3) y vuelve a ejecutar.")
