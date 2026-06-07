#!/bin/bash
# Lanzador de doble-clic (macOS) para el Modelador de Flota E-AUTO.
# La primera vez crea el entorno e instala dependencias; luego solo abre la app.
cd "$(dirname "$0")" || exit 1

if [ ! -d ".venv" ]; then
  echo "▶ Primera ejecución: creando entorno virtual…"
  python3 -m venv .venv
  source .venv/bin/activate
  pip install --upgrade pip >/dev/null
  pip install -r requirements.txt
else
  source .venv/bin/activate
fi

echo "▶ Abriendo el Modelador de Flota en http://localhost:8501 …"
exec streamlit run app.py --server.port 8501
