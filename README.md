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

El motor (`motor.py`) reproduce el **caso base del Estudio de Mercado (Entregable 7, jun-2026)**
con el precio de diésel **actualizado a $1.500/L** (el estudio usó $1.050, hoy desactualizado):
payback ≈ 1,8 años · TIR ≈ 52 % · VAN ≈ +$13,0M/unidad · TCO 7 años −24 %.
*(Con el $1.050 original el estudio daba 2,6 a · 33 % · +$7,0M · −27 %.)*
Verificable con:
```bash
python test_motor.py
```

---

## 🔗 Relación con las calculadoras públicas de la web (`e-auto.global`)

Hay **tres superficies de cálculo** del TCO en el proyecto, con propósitos distintos. Dan
números diferentes **por diseño**, no por error: las dos de la web son *lead magnets*
simplificados; este modelador es el modelo completo de decisión.

| Superficie | Dónde vive | Qué calcula |
|---|---|---|
| **Calculadora home** (viva) | `index.html#tco` → `app.js` | "TCO total" simplificado: energía + mantención (CLP/km) **+ un fijo anual prorrateado** (`fixedYr` = seguro + permiso + *depreciación prorrateada*) + diferencia de precio de compra. Nominal, sin descuento. |
| **Calculadora `/tco`** (histórica) | `calculadora.js` | **Solo operacional**: energía + mantención. Hoy `/tco` **redirige a este modelador**. |
| **Este modelador** | `motor.py` | **TCO completo**: VPN de todos los egresos. |

Diferencias estructurales de las web vs. este motor:

| | Web (`app.js` / `calculadora.js`) | Este modelador (`motor.py`) |
|---|---|---|
| Descuento (VPN) | No (suma nominal) | Sí |
| Escalamiento de precios | No | Diésel / electricidad / costos |
| OPEX | energía + mantención (+ fijo prorrateado en `app.js`) | energía, mantención, **neumáticos, seguro, permiso, AdBlue** desglosados |
| Depreciación | proxy de costo prorrateado (`app.js`) / aparte (`calculadora.js`) | **escudo tributario SII** dentro de los flujos (lineal/acel./instantánea) |
| IVA, residual, cargadores | No | Sí (IVA recuperable, residual neto, CAPEX de carga) |
| Choferes / equivalencia logística | No | Sí (palanca mayor) |
| Pérdidas de carga | No | Sí (+10 %) |
| CO₂ | Solo diésel evitado | Diésel evitado **− emisiones de la red EV** |

> ⚠️ Importante: hoy la página dedicada `/tco` **redirige a este Streamlit**, así que abrir
> "la página explícita de TCO" muestra *este mismo* motor (resultados idénticos por
> definición). La calculadora pública que **sí difiere** es la de la **home** (`app.js`).

**Se reconcilian al peso en su núcleo compartido.** Forzando los mismos inputs y apagando en
este modelador las capas que la web no tiene (descuento = 0, escalamientos = 0, sin pérdidas,
sin neumáticos/seguro/permiso/AdBlue, sin choferes/residual/tributo, mantención por km
equivalente), coinciden exactamente en:

- **Ahorro operacional** (energía + mantención, nominal) — al peso.
- **Escudo tributario año 1** — idéntica fórmula: `precio_EV / 1,19 · 0,27 · nº vehículos`
  (depreciación instantánea sobre el valor neto de IVA).
- **Payback simple** (alineando los precios de compra).

**Trampas al comparar** (por qué los titulares *no* cuadran out-of-the-box):

- **Unidades del consumo diésel:** la web pide **L/100 km**; este motor pide **km/L**
  (11 L/100 km ≠ 11 km/L). Convertir antes de comparar.
- **Costo/km:** las barras de la web **incluyen mantención** (y `app.js` además el fijo
  prorrateado); el titular de costo/km de este motor es **solo combustible/energía** (lo demás
  va como gasto anual aparte).
- **CO₂:** la web solo cuenta el diésel evitado; este motor además **resta** las emisiones de
  la red eléctrica (factor 0,30 kg CO₂/kWh), por lo que da menos toneladas.
- **Defaults distintos:** km/año, precio del diésel, tarifa eléctrica y horizonte difieren
  entre las tres.
- **`app.js` ≠ `calculadora.js`:** la de la home incluye un fijo anual prorrateado (seguro +
  permiso + depreciación) y suma la diferencia de precio de compra; la de `/tco` es solo
  energía + mantención. Mantenerlas coherentes al editar supuestos.

> Verificación cruzada: se replicó `calculadora.js` en Python y se enfrentó a `motor.py` en el
> mismo escenario → el núcleo operacional y el escudo tributario cuadran al peso.

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
