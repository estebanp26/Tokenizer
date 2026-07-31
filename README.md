# Suite de Procesamiento LLM — Sector Salud

Programa de consola en **Python puro** con un menú de 3 funcionalidades:

1. **Ahorrador de tokens / Optimizador de prompts** (ES → EN + compresión adicional)
2. **Análisis de reseñas de usuarios en Excel** (ingesta flexible + optimización opcional de tokens)
3. **Gestión de citas médicas en Excel** (ingesta flexible + evaluación opcional de tokenización)

Todo corre localmente con Python. No usa un backend `/api/analyze` propio (esa ruta
era una referencia interna de las historias de usuario); en su lugar, las funciones
equivalentes se implementaron directamente en el código:

| Historia de usuario pedía... | Implementado con |
|---|---|
| Traducción ES→EN | `deep_translator` (Google Translate, gratis, requiere internet) |
| Tokenización `o200k_base` | `tiktoken` |
| `/api/analyze` (extracción/clasificación) | **Ollama + llama3 (local)** si está instalado, con **fallback por reglas** si no lo está |

## ⚡ ¿Por qué Ollama + llama3?

Pediste que, si algún caso ameritaba un asistente local, usara **Ollama con
llama3**. Eso aplica a los módulos 2 y 3, que necesitan "entender" el texto para
extraer `error_type`/`component` o `accion`/`especialidad`/`preferencia_horario`.
Usar un modelo 100% local:

- Evita depender de una API de pago para la extracción (solo tiktoken/traducción,
  que son gratuitos, consumen recursos externos).
- Es instantáneo una vez cargado el modelo (sin latencia de red a un proveedor externo).
- El programa **detecta automáticamente** si Ollama está corriendo. Si no lo
  encuentra, sigue funcionando con un extractor por palabras clave (menos preciso,
  pero deja el pipeline 100% operativo sin instalar nada).

### Instalar Ollama + llama3 (opcional, recomendado)

```bash
# 1. Instala Ollama: https://ollama.com/download
# 2. Descarga el modelo llama3
ollama pull llama3
# 3. Verifica que el servicio esté corriendo (normalmente arranca solo)
ollama serve
```

Con Ollama corriendo en `http://localhost:11434`, los módulos 1, 2 y 3 lo usarán
automáticamente para la compresión de prompts y la extracción estructurada.

## 📦 Instalación

```bash
cd llm_suite
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

> **Nota sobre `tiktoken`:** la primera vez que cuenta tokens, descarga el
> vocabulario `o200k_base` desde internet y lo cachea en disco. Si no hay
> conexión en ese momento, el programa **no se cae**: usa una estimación
> aproximada (caracteres/4.3) y te avisa con un `[WARN]`.

## ▶️ Uso

```bash
python main.py
```

Verás un menú:

```
[1] Ahorrador de tokens / Optimizador de prompts (ES -> EN)
[2] Análisis de reseñas de usuarios (Excel)
[3] Gestión de citas médicas (Excel)
[0] Salir
```

### Generar datos de ejemplo (opcional)

Para probar los módulos 2 y 3 sin tener tus propios Excel a mano:

```bash
python generar_datos_ejemplo.py
```

Esto crea `datos_ejemplo/reviews_ejemplo.xlsx` y `datos_ejemplo/citas_ejemplo.xlsx`.

## 🧩 Detalle de cada módulo

### Módulo 1 — Ahorrador de tokens / Optimizador de prompts
- Pegas un prompt en español (línea vacía para terminar).
- Se traduce a inglés y se comparan tokens/costo de ambas versiones.
- Se intenta una compresión adicional sobre la versión más eficiente
  (vía llama3 si está disponible, o una limpieza heurística de relleno si no).
- Muestra el resumen final: tokens y costo por cada etapa.

### Módulo 2 — Análisis de reseñas (Excel)
Implementa exactamente los 3 criterios de aceptación de la historia:
- **Ingesta flexible:** Modo A (archivo único) o Modo B (carpeta con varios `.xlsx`,
  consolidados automáticamente). Detecta la columna de texto sola.
- **Pipeline opcional (`optent_tokens`):** si se activa, traduce a inglés antes de
  clasificar; si no, procesa el español directo.
- **Impacto económico:** proyecta el costo para **10,000 reseñas/día** a
  **$2.50 por millón de tokens**, comparando directo vs. optimizado.
- **Salida estructurada:** exporta a `.xlsx` y `.json` con
  `{"error_type": ..., "component": ...}` por cada fila.

### Módulo 3 — Gestión de citas médicas (Excel)
Implementa los 3 criterios de esa historia:
- **Ingesta flexible** con detección de `paciente_id` / `mensaje_texto`.
- **Evaluación opcional (`optimizar_tokens`)** y cálculo de **fragmentación**
  (tokens por palabra) en español vs. inglés para términos médicos.
- **Proyección económica** diaria y mensual para **15,000 mensajes/día**.
- **Salida estructurada** con `{"accion", "especialidad", "preferencia_horario"}`
  exportada a `.xlsx` y `.json`.

## 📁 Estructura del proyecto

```
llm_suite/
├── main.py                     # Menú principal
├── generar_datos_ejemplo.py    # Genera Excel de prueba
├── requirements.txt
├── README.md
└── modules/
    ├── utils.py                 # Tokenización, costos, traducción, Ollama, lectura Excel
    ├── prompt_optimizer.py      # Módulo 1
    ├── review_pipeline.py       # Módulo 2
    └── appointment_pipeline.py  # Módulo 3
```

## ⚠️ Notas importantes

- **Traducción y descarga de tiktoken requieren internet.** Sin conexión, la
  traducción se omite (se usa el texto original) y el conteo de tokens pasa a
  ser una estimación aproximada — ambos casos avisan con `[WARN]` y **no
  detienen el programa**.
- **Ollama es totalmente opcional.** Sin él, los módulos 2 y 3 usan un
  clasificador por palabras clave (reglas simples) que ya viene incluido, así
  que puedes usar el programa "instantáneamente" sin instalar nada más.
- Los resultados de los módulos 2 y 3 se guardan siempre en
  `/mnt/user-data/outputs/` (ajusta `OUTPUT_DIR` en cada módulo si quieres
  otra ruta al correrlo en tu propia máquina).
