# ⚡ Modelador de Reemplazo de Flota — Diésel → Eléctrico (E-AUTO Global)

Software de modelación para el directorio de **E-Auto Global** que evalúa, con rigor de
consultoría, el reemplazo de una flota de furgones **diésel** por **eléctricos** (Gecko
**EV48** / **MagicWay**). Combina el estándar de evaluación **TCO** (Total Cost of Ownership)
con tres capas que normalmente quedan fuera del Excel del vendedor:

1. **Logística** — equivalencia de capacidad (peso / volumen / autonomía) que calcula
   cuántos EV reemplazan a la flota y, por tanto, **cuántos choferes se reducen**
   (la mayor palanca de costo de la última milla).
2. **Tributario** — escudo fiscal de la depreciación bajo tres regímenes
   (lineal / acelerada 1/3 / **instantánea 100 % año 1**) y la decisión de **si conviene**.
3. **Impacto** — toneladas de **CO₂ evitadas** y beneficios regulatorios.

Corre **100 % local** (localhost), con interfaz interactiva, ayudas en cada campo y
gráficos exportables.

---

## ▶ Cómo ejecutarlo

**Opción A — doble clic (macOS):** doble-clic en `run.command`.

**Opción B — terminal:**
```bash
cd ~/eauto-flota
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```
Se abre en **http://localhost:8501**. Para detenerlo: `Ctrl-C` en la terminal.

---

## 🧮 Qué calcula (algoritmos)

| Bloque | Fórmula / lógica |
|---|---|
| **Costo de energía/km** | diésel = (1 / km·L⁻¹) · precio_L · `;` EV = (1 / km·kWh⁻¹) · precio_kWh · (1+pérdidas) |
| **OPEX anual** | energía + mantención + neumáticos + seguro + permiso + AdBlue, escalado: `C_t = C_1·(1+g)^{t-1}` |
| **TCO** | valor presente de todos los egresos: `Σ egreso_t / (1+r)^t` (incluye CAPEX, infra de carga, escudo tributario y residual) |
| **VAN** | `Σ flujo_incremental_t / (1+r)^t` sobre el sobrecosto de cambiarse |
| **TIR** | tasa que hace VAN = 0 (bisección) |
| **Payback** | años hasta recuperar el sobrecosto (interpolado) |
| **Equivalencia logística** | demanda diaria (kg, m³, km) ÷ capacidad del EV → restricción *binding* → nº de EV → choferes reducibles |
| **Escudo tributario** | `tasa_impuesto · depreciación_t`; acelerar adelanta el ahorro → mayor valor presente |
| **CO₂** | diésel: L/año · 2,68 kg/L · `;` EV: kWh/año · 0,30 kg/kWh (red SEN) |

---

## 📊 Variables de entrada (todas con ayuda en pantalla)

- **Flota y operación:** nº de vehículos, km/año, horizonte, tasa de descuento.
- **Diésel:** precio, rendimiento (km/L), precio del litro, mantención, neumáticos, seguro,
  permiso, AdBlue, valor residual.
- **Eléctrico:** precio (IVA incluido), eficiencia (km/kWh), precio kWh, pérdidas de carga,
  mantención, neumáticos, seguro, permiso, autonomía, residual.
- **Infraestructura de carga:** costo por cargador, vehículos por cargador, obra eléctrica.
- **Logística:** carga útil y volumen (diésel y EV), utilización, costo de chofer,
  equivalencia por capacidad on/off.
- **Tributario:** tasa Primera Categoría, régimen de depreciación, ¿hay utilidades?
- **Escalamiento:** alza anual de diésel, electricidad y costos/sueldos.

**Presets cargados:** Gecko EV48 (6,2 km/kWh, 1.440 kg, 6,2 m³, $29,75M) · Gecko MagicWay
(70 kWh, 1.765 kg, 8,1 m³, $49,99M) · perfiles diésel típicos.

---

## 🔬 Validación

El motor (`motor.py`) reproduce el **caso base validado del Estudio de Mercado (Entregable 7,
jun-2026)**: payback ≈ 2,6 años · TIR ≈ 33 % · VAN ≈ +$7,0M/unidad · TCO 7 años −27 %.
Verificable con:
```bash
python test_motor.py
```

---

## 📁 Archivos

| Archivo | Rol |
|---|---|
| `app.py` | Interfaz Streamlit (inputs, KPIs, 7 pestañas) |
| `motor.py` | Motor de cálculo puro (TCO, logística, tributario, sensibilidad) |
| `graficos.py` | Gráficos Plotly |
| `test_motor.py` | Test de regresión contra el estudio |
| `requirements.txt` · `run.command` | Dependencias y lanzador |

---

## ⚠️ Notas

- **IVA:** diésel y eléctrico se tratan **igual** — ambos son vehículos comerciales con IVA
  recuperable como crédito fiscal. Precios IVA incluido; el modelo descuenta el IVA en los dos.
- El **valor residual** del EV es conservador (mercado secundario incipiente).
- Usa los **precios reales del cliente** (diésel y energía son las palancas más sensibles).
- Los resultados son **escenarios de decisión**, no hechos auditados.

**Fuentes:** Estudio de Mercado EV Comerciales Chile (jun-2026) · Go-To-Market Killer EV48 ·
fichas técnicas certificadas 3CV · Ley 21.305 / SII Res. Ex. 56/2021 · ANAC 2025.
