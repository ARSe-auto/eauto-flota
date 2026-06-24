# -*- coding: utf-8 -*-
"""
app.py — Modelador de reemplazo de flota diésel → eléctrica (E-AUTO Global).
Interfaz Streamlit. Ejecutar:  streamlit run app.py
"""
import base64
from dataclasses import asdict
from pathlib import Path
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from motor import (Supuestos, evaluar, tornado, sensibilidad_2d,
                   equivalencia_capacidad, PRESETS_EV, PRESETS_DIESEL)
import graficos as g
import metodologia

st.set_page_config(page_title="E-AUTO · Modelador de Flota EV",
                   page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

# ── Formato CLP (locale chileno: miles con punto, decimales con coma) ─────────
def clp(x):
    return "$" + f"{x:,.0f}".replace(",", ".")

def clp_mm(x):
    s = f"{x/1e6:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return "$" + s + "M"

# Config Plotly: sin barra de herramientas (diseño limpio, sin íconos flotantes)
PLOTCFG = {"displayModeBar": False, "responsive": True}

# Logo e-auto (en assets/, ruta relativa robusta para local y Streamlit Cloud)
@st.cache_data
def _logo_b64():
    p = Path(__file__).parent / "assets" / "eauto_logo.png"
    try:
        return base64.b64encode(p.read_bytes()).decode()
    except Exception:
        return ""

# ── Estilos (criterio de diseño limpio: tipografía Montserrat, grilla, aire) ──
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700;800&display=swap');
  html, body, [class*="css"], .stMarkdown, [data-testid="stMetric"], button[data-baseweb="tab"]
        { font-family:'Montserrat',-apple-system,Helvetica,Arial,sans-serif; }
  .block-container { padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1290px; }

  /* quitar SOLO el chrome que estorba (menú, deploy, status, footer),
     nunca toda la barra: así el botón para reabrir la sidebar nunca se oculta */
  #MainMenu, [data-testid="stMainMenu"],
  [data-testid="stAppDeployButton"], [data-testid="stToolbarActions"],
  [data-testid="stStatusWidget"], footer { display: none !important; }
  header[data-testid="stHeader"] { background: transparent; }

  /* Botón para reabrir la barra lateral: verde, grande e imposible de no ver.
     OJO: este elemento ES el <button>, no contiene un button hijo. */
  [data-testid="stExpandSidebarButton"] {
      visibility: visible !important; display: flex !important;
      align-items:center !important; justify-content:center !important;
      background:#00A651 !important; border:none !important; border-radius:9px !important;
      width:44px !important; height:44px !important; min-width:44px !important;
      box-shadow:0 3px 10px rgba(0,0,0,.28) !important; }
  [data-testid="stExpandSidebarButton"]:hover { background:#0B5E2F !important; }
  [data-testid="stExpandSidebarButton"] svg,
  [data-testid="stExpandSidebarButton"] span,
  [data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"] {
      color:#fff !important; fill:#fff !important;
      width:26px !important; height:26px !important; font-size:26px !important; }

  /* Encabezado */
  .ea-hero { background:#0B5E2F; padding: 24px 30px; border-radius: 10px; color:#fff;
             margin-bottom: 22px; border-left: 4px solid #00A651;
             display:flex; align-items:center; gap:26px; flex-wrap:wrap; }
  .ea-hero-text { flex:1 1 360px; min-width:0; }
  .ea-logo-chip { flex:0 0 auto; background:#fff; border-radius:10px; padding:12px 18px;
                  box-shadow:0 2px 10px rgba(0,0,0,.14); }
  .ea-logo-chip img { height:52px; display:block; }
  .ea-hero .eyebrow { text-transform:uppercase; letter-spacing:.2em; font-size:10.5px;
                      font-weight:700; opacity:.82; margin-bottom:9px; }
  .ea-hero h1 { margin:0; font-size:25px; font-weight:700; letter-spacing:-.01em; line-height:1.18; }
  .ea-hero p  { margin:9px 0 0; opacity:.82; font-size:13px; font-weight:300; }

  /* Métricas como tarjetas sobrias */
  div[data-testid="stMetric"] { background:#FAFBFA; border:1px solid #ECEFEE; border-radius:8px;
                                padding:13px 16px; min-height:104px; }
  /* la etiqueta puede envolver a 2 líneas en vez de truncarse con elipsis */
  div[data-testid="stMetricLabel"] p { font-size:12px; color:#5C6B63; font-weight:500;
        white-space:normal !important; overflow:visible !important; text-overflow:clip !important;
        line-height:1.25; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;
        min-height:2.5em; }
  div[data-testid="stMetricValue"] { font-size:23px; font-weight:700; color:#15302A; letter-spacing:-.01em; }
  div[data-testid="stMetricDelta"] { font-size:12px; }

  /* Pestañas */
  div[data-baseweb="tab-list"] { gap:4px; border-bottom:1px solid #ECEFEE; }
  button[data-baseweb="tab"] { font-weight:600; font-size:13.5px; }

  /* Chips, separadores, títulos */
  .ea-tag { display:inline-block; background:#E6F6EE; color:#0B5E2F; padding:3px 11px;
            border-radius:6px; font-size:12px; font-weight:600; margin-right:6px; }
  hr { border-color:#ECEFEE; }
  h2, h3 { color:#15302A; letter-spacing:-.01em; font-weight:700; }
</style>
""", unsafe_allow_html=True)

_logo = _logo_b64()
_logo_chip = (f'<div class="ea-logo-chip"><img src="data:image/png;base64,{_logo}" '
              f'alt="e-auto · Electric Vehicles"></div>') if _logo else ""
st.markdown(
    '<div class="ea-hero">'
    '<div class="ea-hero-text">'
    '<div class="eyebrow">E-AUTO Global · Electromovilidad utilitaria</div>'
    '<h1>Modelador de Reemplazo de Flota · Diésel → Eléctrico</h1>'
    '<p>Análisis TCO + logística + tributario · Gecko EV48 / MagicWay · '
    'valores base: Estudio de Mercado EV Comerciales Chile (jun-2026)</p></div>'
    + _logo_chip +
    '</div>',
    unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
#  SIDEBAR — INPUTS (cada campo con su ayuda)
# ════════════════════════════════════════════════════════════════════════════
sb = st.sidebar
sb.header("⚙️ Variables del modelo")
sb.caption("Pasa el cursor sobre el ícono **ⓘ** de cada campo para ver la ayuda, "
           "el valor típico en Chile y la fuente del supuesto.")

# Toggle de equivalencia controlado por DOS checkboxes sincronizados (barra lateral + pestaña
# «Capacidad y flota»). Patrón canónico Streamlit: cada callback ESPEJA su valor en la clave del
# otro widget. La fuente de verdad es ss.eq_cap_sb (== ss.eq_cap_tab). Parten en True: la app
# abre en el caso real (reemplazar la flota por la cantidad MÍNIMA de EV que iguala la capacidad,
# que reduce vehículos y choferes) — es el escenario fuerte y representativo. Se puede desactivar
# para ver el reemplazo 1:1.
ss = st.session_state
ss.setdefault("eq_cap_sb", True)
ss.setdefault("eq_cap_tab", True)
def _eq_from_sb():  ss.eq_cap_tab = ss.eq_cap_sb
def _eq_from_tab(): ss.eq_cap_sb = ss.eq_cap_tab

# — Presets —
with sb.expander("🚐 Vehículo eléctrico (preset)", expanded=True):
    preset_ev = st.selectbox("Modelo e-auto", list(PRESETS_EV.keys()), index=0,
        help="Carga la ficha técnica certificada del modelo. 'Personalizado' te deja editar todo a mano.")
    p = PRESETS_EV[preset_ev]

with sb.expander("🛻 Vehículo diésel a reemplazar (preset)", expanded=True):
    preset_d = st.selectbox("Perfil diésel actual", list(PRESETS_DIESEL.keys()), index=0,
        help="Punto de partida típico. Ajusta los valores a tu flota real más abajo.")
    pd_ = PRESETS_DIESEL[preset_d]

# — Operación —
with sb.expander("📋 Flota y operación", expanded=True):
    num_diesel = st.number_input("N° de vehículos diésel en la flota", 1, 5000, 10, step=1,
        help="Tamaño de la flota que evalúas reemplazar. El modelo escala todos los resultados a este número.")
    km_mensual = st.number_input("Kilómetros por vehículo al mes", 400, 10_000, 2_500, step=100,
        help="Uso mensual promedio por vehículo. Reparto urbano intensivo ≈ 2.500–3.750 km/mes; "
             "transfer/turismo ≈ 3.300–5.000 km/mes. A más km, más fuerte el caso eléctrico. "
             "El modelo lo anualiza (×12) internamente.")
    km_anual = km_mensual * 12
    st.caption(f"≈ {km_anual:,.0f} km/año por vehículo".replace(",", "."))
    horizonte = st.number_input("Horizonte de evaluación (años)", 3, 12, 7, step=1,
        help="Período sobre el que se calcula el TCO. El estudio usa 7 años (vida útil contable del vehículo).")
    tasa_desc = st.slider("Tasa de descuento (costo de capital) %", 4.0, 25.0, 10.0, 0.5,
        help="Rentabilidad mínima exigida / costo del dinero de la empresa. Se usa para traer los flujos "
             "futuros a valor presente (VAN). El estudio usa 10%.") / 100

# — Diésel —
with sb.expander("⛽ Costos del vehículo diésel"):
    precio_diesel = st.number_input("Precio de compra diésel (CLP, IVA incluido)", 5_000_000, 120_000_000,
        int(pd_["precio_diesel_clp"]), step=500_000,
        help="Precio del furgón diésel equivalente, IVA incluido. Por ser vehículo comercial, el IVA es "
             "recuperable como crédito fiscal — el modelo lo trata IGUAL que el EV (ver sección Tributario). "
             "Referencia ≈ 22 millones (Maxus/DFSK-class).")
    rendimiento = st.number_input("Rendimiento (km por litro)", 3.0, 25.0, float(pd_["rendimiento_km_l"]), step=0.5,
        help="Consumo del furgón diésel. Reparto urbano cargado ≈ 9–12 km/L. El estudio usa 11 km/L.")
    precio_diesel_l = st.number_input("Precio del diésel (CLP/litro)", 600, 3_000, 1_500, step=10,
        help="Precio del litro en surtidor o estación propia. Referencia 2026 ≈ $1.400–1.500/L. "
             "Usa el precio real de tus cargas.")
    mant_diesel = st.number_input("Mantención diésel al año (CLP)", 0, 8_000_000, int(pd_["mantencion_diesel_anual"]), step=50_000,
        help="Servicios, filtros, aceite, correas, frenos, etc. por vehículo/año. El estudio usa $1,2M.")
    neum_diesel = st.number_input("Neumáticos diésel al año (CLP)", 0, 3_000_000, 350_000, step=50_000,
        help="Costo prorrateado anual de neumáticos por vehículo.")
    seguro_diesel = st.number_input("Seguro diésel al año (CLP)", 0, 5_000_000, 600_000, step=50_000,
        help="Prima anual del seguro por vehículo.")
    permiso_diesel = st.number_input("Permiso de circulación diésel (CLP/año)", 0, 3_000_000, 280_000, step=10_000,
        help="Permiso municipal anual (depende de la tasación del vehículo).")
    adblue = st.number_input("AdBlue / urea al año (CLP)", 0, 1_500_000, 120_000, step=10_000,
        help="Solución de urea (SCR) que consumen los diésel modernos Euro 5/6. El EV no la usa.")
    residual_diesel = st.slider("Valor residual diésel al final (% del precio)", 0, 60, 20, 1,
        help="Cuánto vale el furgón diésel al terminar el horizonte, como % del precio de compra.") / 100
    diesel_pagado = st.checkbox("La flota diésel ya está pagada (costo hundido)", value=False,
        help="Actívalo si YA posees y pagaste tus diésel. El modelo deja de contar su precio de compra (es costo "
             "hundido: $0) y supone que, al cambiarte, VENDES los diésel usados — ese ingreso rebaja la compra de "
             "los EV. Así el payback deja de ser «inmediato» y refleja la recuperación real de la inversión EV.")
    if diesel_pagado:
        diesel_reventa = st.slider("↳ Reventa de tus diésel actuales (% del precio de compra)", 0, 80, 40, 5,
            help="Cuánto recuperas HOY al vender tus diésel usados, como % de su precio original. Un furgón "
                 "comercial de pocos años ≈ 35–50%. Ese monto se descuenta de la inversión en EV.") / 100
    else:
        diesel_reventa = 0.40

# — EV —
with sb.expander("🔋 Costos del vehículo eléctrico"):
    precio_ev = st.number_input("Precio de compra EV (CLP, IVA incluido)", 10_000_000, 150_000_000,
        int(p["precio_ev_clp"]), step=250_000,
        help="Precio de lista del modelo e-auto, IVA incluido. Por ser vehículo comercial, el IVA es "
             "recuperable como crédito fiscal — el modelo lo trata IGUAL que el diésel (ver sección Tributario). "
             "EV48 ≈ 29,75 millones · MagicWay ≈ 49,99 millones.")
    eficiencia = st.number_input("Eficiencia (km por kWh)", 2.0, 10.0, float(p["eficiencia_km_kwh"]), step=0.1,
        help="Energía que rinde el EV. EV48 = 6,2 km/kWh CERTIFICADO por 3CV (la más alta del mercado chileno). "
             "MagicWay ≈ 3,6 km/kWh.")
    precio_kwh = st.number_input("Precio de la electricidad (CLP/kWh)", 50, 400, 130, step=5,
        help="Tarifa comercial. Diurna ≈ 130–160 CLP; nocturna gestionada ≈ 110 CLP. Cargar de noche mejora el caso.")
    perdidas = st.slider("Pérdidas de carga (%)", 0, 20, 10, 1,
        help="Energía que se pierde al cargar (calor en cargador/batería). Típico 8–12%.") / 100
    mant_ev = st.number_input("Mantención EV al año (CLP)", 0, 5_000_000, 400_000, step=50_000,
        help="El EV tiene ~⅓ de la mantención del diésel (sin aceite, correas, embrague, escape). El estudio usa $0,4M.")
    neum_ev = st.number_input("Neumáticos EV al año (CLP)", 0, 3_000_000, 350_000, step=50_000,
        help="Similar al diésel; el mayor torque puede aumentar levemente el desgaste.")
    seguro_ev = st.number_input("Seguro EV al año (CLP)", 0, 5_000_000, 650_000, step=50_000,
        help="Prima anual. Puede ser algo mayor que el diésel por valor de reposición de la batería.")
    permiso_ev = st.number_input("Permiso de circulación EV (CLP/año)", 0, 3_000_000, 210_000, step=10_000,
        help="Los EV han tenido rebajas/beneficios en permiso e impuestos. Suele ser menor que el diésel.")
    autonomia = st.number_input("Autonomía (km)", 100, 600, int(p["autonomia_km"]), step=5,
        help="Rango con carga llena. EV48 = 305 km (CLTC) · MagicWay = 353 km (CHTC-LT).")
    autonomia_util = st.slider("Autonomía utilizable real (%)", 50, 100, 85, 1,
        help="Fracción del rango que usas en operación (margen de seguridad de carga, frío, carga útil).") / 100
    residual_ev = st.slider("Valor residual EV al final (% del precio)", 0, 60, 15, 1,
        help="Mercado secundario EV aún incipiente en Chile → se sugiere ser conservador (10–20%). "
             "La garantía de batería 8 años / 400.000 km lo sostiene.") / 100

# — Infraestructura de carga —
with sb.expander("🔌 Infraestructura de carga"):
    costo_cargador = st.number_input("Costo por cargador instalado (CLP)", 0, 30_000_000, 900_000, step=100_000,
        help="Wallbox AC instalado ≈ $0,7–1,2M por punto. Cargador DC compartido cuesta más pero sirve a varios.")
    veh_por_cargador = st.number_input("Vehículos por cargador", 1.0, 10.0, 1.0, step=0.5,
        help="Cuántos vehículos comparten un punto de carga. El EV48 carga AC de noche → 1 punto por vehículo es típico.")
    instalacion = st.number_input("Obra eléctrica única (CLP)", 0, 100_000_000, 0, step=500_000,
        help="Inversión única en empalme/tablero/medidor si la instalación lo requiere. Déjalo en 0 si no aplica.")

# — Logística / choferes —
with sb.expander("🚚 Logística y choferes", expanded=True):
    st.checkbox("Aplicar equivalencia por capacidad (reducir flota)", key="eq_cap_sb", on_change=_eq_from_sb,
        help="Si lo activas, el modelo calcula cuántos EV bastan para mover la MISMA carga que la flota diésel. "
             "Como el EV48 carga más (1.440 kg), a veces se necesitan MENOS vehículos → menos choferes. "
             "También puedes activarlo arriba en la pestaña «Capacidad y flota».")
    equivalencia = ss.eq_cap_sb
    carga_diesel = st.number_input("Carga útil del diésel (kg)", 200, 5_000, int(pd_["carga_util_diesel_kg"]), step=50,
        help="Cuánto carga cada furgón diésel actual. Necesario para la equivalencia de capacidad.")
    vol_diesel = st.number_input("Volumen del diésel (m³)", 1.0, 20.0, float(pd_["volumen_diesel_m3"]), step=0.5,
        help="Volumen de carga de cada furgón diésel actual.")
    carga_ev = st.number_input("Carga útil del EV (kg)", 200, 5_000, int(p["carga_util_ev_kg"]), step=50,
        help="Carga útil del modelo e-auto. EV48 = 1.440 kg (líder de su clase) · MagicWay = 1.765 kg.")
    vol_ev = st.number_input("Volumen del EV (m³)", 1.0, 20.0, float(p["volumen_ev_m3"]), step=0.5,
        help="Volumen de carga del EV. EV48 = 6,2 m³ · MagicWay = 8,1 m³.")
    util_peso = st.slider("Utilización promedio en peso (%)", 30, 100, 80, 5,
        help="Cuán llenos (en kg) van tus diésel en promedio. Sirve para dimensionar la flota EV equivalente.") / 100
    util_vol = st.slider("Utilización promedio en volumen (%)", 30, 100, 85, 5,
        help="Cuán llenos (en m³) van tus diésel en promedio.") / 100
    incluir_choferes = st.checkbox("Incluir ahorro de choferes", value=True,
        help="El chofer —no el combustible— es el mayor costo de la última milla. Si reduces vehículos, reduces choferes.")
    costo_chofer_mensual = st.number_input("Costo mensual de un chofer (CLP, incluye leyes/impuestos)",
        300_000, 3_000_000, 950_000, step=10_000,
        help="Costo TOTAL mensual de UN conductor para la empresa: sueldo líquido + cotizaciones e impuestos "
             "(leyes sociales: AFP, salud, seguro de cesantía, mutual). El modelo lo anualiza automáticamente "
             "(×12). Referencia última milla ≈ $0,8–1,1M/mes.")
    st.caption(f"→ Costo anual por chofer: **{clp(costo_chofer_mensual*12)}** (mensual × 12).")

# — Tributario —
with sb.expander("🏛️ Régimen tributario"):
    iva_recuperable = st.checkbox("IVA recuperable como crédito fiscal (vehículo comercial)", value=True,
        help="Diésel y eléctrico son vehículos COMERCIALES: si la empresa es contribuyente de IVA, recupera el "
             "IVA de la compra como crédito fiscal. El modelo lo aplica IGUAL a ambos → el CAPEX se considera "
             "NETO de IVA en los dos. Desactívalo solo si la empresa NO recupera IVA (ahí ambos van con IVA incluido).")
    iva_pct = st.slider("Tasa de IVA (%)", 0, 19, 19, 1,
        help="IVA en Chile = 19%. Se descuenta por igual del precio de diésel y de EV cuando es recuperable.") / 100
    factor_iva_app = 1 / (1 + iva_pct) if iva_recuperable else 1.0
    st.caption((f"→ CAPEX neto de IVA · diésel **{clp(precio_diesel*factor_iva_app)}** · "
                f"EV **{clp(precio_ev*factor_iva_app)}** (mismo trato para ambos).").replace("$", "\\$"))
    tasa_imp = st.slider("Tasa Impuesto Primera Categoría (%)", 0, 35, 27, 1,
        help="Régimen general = 27%. Pyme Pro (ProPyme) = 25%. Sobre esta tasa se calcula el escudo de la depreciación.") / 100
    con_utilidades = st.checkbox("La empresa tiene utilidades que absorben la rebaja", value=True,
        help="La depreciación solo da ahorro de impuestos si hay base imponible que rebajar. "
             "Si la empresa da pérdida, el beneficio se difiere (pérdida de arrastre) y pierde valor en el tiempo.")
    regimen = st.selectbox("Régimen de depreciación", ["instantanea", "acelerada", "lineal"], index=0,
        format_func=lambda x: {"instantanea": "Instantánea — 100% el año 1",
                               "acelerada": "Acelerada — 1/3 de la vida útil",
                               "lineal": "Lineal — vida útil normal (7 años)"}[x],
        help="Cómo deduces el valor del vehículo. La INSTANTÁNEA (Ley 21.305 / Res. SII 56/2021, ventana a feb-2031) "
             "deduce el 100% el primer año → adelanta el ahorro de impuestos y maximiza su valor presente.")
    aplicar_trib = st.checkbox("Mostrar flujos después de impuestos", value=True,
        help="Si lo activas, los KPI incorporan el escudo tributario y el impuesto sobre el residual. "
             "Si lo desactivas, ves el caso 'operacional puro' (comparable al titular del estudio).")

# — Escalamiento —
with sb.expander("📈 Escalamiento de precios (avanzado)"):
    esc_diesel = st.slider("Alza anual precio diésel (%)", 0.0, 15.0, 4.0, 0.5,
        help="Cuánto sube el diésel cada año (nominal). Históricamente sube más que la inflación general.") / 100
    esc_energia = st.slider("Alza anual precio electricidad (%)", 0.0, 15.0, 3.0, 0.5,
        help="Cuánto sube la tarifa eléctrica cada año.") / 100
    esc_costos = st.slider("Alza anual mantención/seguros/sueldos (%)", 0.0, 15.0, 3.0, 0.5,
        help="Inflación de costos operativos y laborales.") / 100

# ── Construir supuestos ──────────────────────────────────────────────────────
s = Supuestos(
    num_vehiculos_diesel=int(num_diesel), km_anual_por_vehiculo=float(km_anual),
    horizonte_anios=int(horizonte), tasa_descuento=tasa_desc,
    escalamiento_diesel=esc_diesel, escalamiento_energia=esc_energia, escalamiento_costos=esc_costos,
    precio_diesel_clp=float(precio_diesel), rendimiento_km_l=float(rendimiento),
    precio_diesel_l=float(precio_diesel_l), mantencion_diesel_anual=float(mant_diesel),
    neumaticos_diesel_anual=float(neum_diesel), seguro_diesel_anual=float(seguro_diesel),
    permiso_circulacion_diesel=float(permiso_diesel), adblue_anual=float(adblue),
    carga_util_diesel_kg=float(carga_diesel), volumen_diesel_m3=float(vol_diesel),
    valor_residual_diesel_pct=residual_diesel,
    diesel_costo_hundido=diesel_pagado, diesel_reventa_pct=diesel_reventa,
    precio_ev_clp=float(precio_ev), eficiencia_km_kwh=float(eficiencia),
    precio_energia_kwh=float(precio_kwh), perdidas_carga_pct=perdidas,
    mantencion_ev_anual=float(mant_ev), neumaticos_ev_anual=float(neum_ev),
    seguro_ev_anual=float(seguro_ev), permiso_circulacion_ev=float(permiso_ev),
    carga_util_ev_kg=float(carga_ev), volumen_ev_m3=float(vol_ev),
    autonomia_km=float(autonomia), autonomia_utilizable_pct=autonomia_util,
    valor_residual_ev_pct=residual_ev,
    costo_cargador_clp=float(costo_cargador), vehiculos_por_cargador=float(veh_por_cargador),
    costo_instalacion_electrica=float(instalacion),
    costo_anual_chofer=float(costo_chofer_mensual) * 12, aplicar_equivalencia_capacidad=equivalencia,
    utilizacion_peso_pct=util_peso, utilizacion_volumen_pct=util_vol,
    incluir_ahorro_choferes=incluir_choferes,
    tasa_impuesto=tasa_imp, regimen_depreciacion=regimen,
    empresa_con_utilidades=con_utilidades, aplicar_efecto_tributario=aplicar_trib,
    iva_pct=iva_pct, iva_recuperable=iva_recuperable,
)
r = evaluar(s)

# ════════════════════════════════════════════════════════════════════════════
#  KPIs PRINCIPALES
# ════════════════════════════════════════════════════════════════════════════
sin_inversion = r["inc_capex"] <= 0  # la flota EV cuesta lo mismo o menos al comprar
if r["tir"] is not None:
    tir_txt = f"{r['tir']*100:.0f}%"
elif sin_inversion and r["van"] > 0:
    tir_txt = "∞"
else:
    tir_txt = "—"
if r["payback"] is None:
    pb_txt = ">horizonte"
elif r["payback"] <= 0.01:
    pb_txt = "Inmediato"
else:
    pb_txt = f"{r['payback']:.1f}".replace(".", ",") + " años"
ahorro_anio_prom = sum(r["ahorro_anual"]) / len(r["ahorro_anual"])

k = st.columns(6)
k[0].metric("VAN del cambio", clp_mm(r["van"]),
            help="Valor Actual Neto: la riqueza neta (en $ de hoy) que genera reemplazar la flota. Positivo = conviene.")
k[1].metric("TIR", tir_txt,
            help="Tasa Interna de Retorno de la inversión incremental. Compárala con tu costo de capital.")
k[2].metric("Payback", pb_txt,
            help="Años para recuperar el sobrecosto inicial del cambio.")
k[3].metric("Ahorro/año", clp_mm(ahorro_anio_prom),
            help="Ahorro promedio por año de toda la flota (energía + mantención + choferes + tributario).")
k[4].metric("Ventaja TCO", f"{r['tco_delta_pct']*100:.0f}%", clp_mm(r["tco_delta"]),
            help=f"Cuánto más barato es el TCO eléctrico vs diésel a {horizonte} años (valor presente).")
k[5].metric("CO₂ evitado", f"{r['co2_evitado_anio']:.1f}".replace(".", ",") + " t",
            help="Toneladas de CO₂ que deja de emitir la flota al año.")

if r["van"] > 0 and sin_inversion:
    st.success(f"✅ **El cambio CONVIENE y NO requiere inversión neta.** Reemplazar {r['n_diesel']} furgones "
               f"diésel por {r['n_ev']} eléctricos cuesta lo mismo o menos al comprar (gracias a la menor flota) "
               f"y genera un VAN de **{clp_mm(r['van'])}** con un TCO **{r['tco_delta_pct']*100:.0f}% menor** a "
               f"{horizonte} años. El ahorro empieza el día 1.")
elif r["van"] > 0:
    st.success(f"✅ **El cambio CONVIENE.** Reemplazar {r['n_diesel']} furgones diésel por "
               f"{r['n_ev']} eléctricos genera un VAN de **{clp_mm(r['van'])}** "
               f"(TIR {tir_txt}, payback {pb_txt}) y un TCO **{r['tco_delta_pct']*100:.0f}% menor** a {horizonte} años.")
else:
    st.warning(f"⚠️ Con estos supuestos el VAN es **{clp_mm(r['van'])}** (negativo). "
               "Revisa km/año, precio del diésel o el financiamiento — el caso mejora con más uso y diésel más caro.")

if s.diesel_costo_hundido:
    st.caption(f"🔧 **Modo «flota diésel ya pagada».** No se cuenta el precio de compra de los diésel (costo "
               f"hundido); la decisión es *seguir con los diésel pagados* vs *comprar EV*. Al cambiarte se asume "
               f"que vendes los diésel usados por **{clp(r['diesel_reventa'])}** "
               f"({diesel_reventa*100:.0f}% de su precio), que se descuenta de la inversión en EV. Por eso el "
               f"payback ya no es «inmediato»: refleja recuperar la inversión EV neta.")

# ════════════════════════════════════════════════════════════════════════════
#  TABS
# ════════════════════════════════════════════════════════════════════════════
t1, t2, tflota, t4, t5, t6, t7 = st.tabs(
    ["📊 Resumen ejecutivo", "💰 TCO detallado", "🚚 Capacidad y flota",
     "🏛️ Tributario", "📈 Sensibilidad", "🌱 Impacto CO₂", "📖 Metodología"])

# ── TAB 1: Resumen ejecutivo ──────────────────────────────────────────────
with t1:
    c1, c2 = st.columns([3, 2])
    with c1:
        st.plotly_chart(g.fig_tco_acumulado(r), use_container_width=True, config=PLOTCFG)
    with c2:
        st.plotly_chart(g.fig_gauge_payback(r["payback"], horizonte), use_container_width=True, config=PLOTCFG)
        st.markdown(f"<span class='ea-tag'>Costo/km diésel: {r['costo_km_diesel']:.0f} CLP</span> "
                    f"<span class='ea-tag'>Costo/km EV: {r['costo_km_ev']:.0f} CLP</span>", unsafe_allow_html=True)
        ratio = r["costo_km_diesel"] / r["costo_km_ev"] if r["costo_km_ev"] else 0
        st.info(f"El kilómetro eléctrico es **{ratio:.1f}× más barato** que el diésel en energía "
                f"(−{(1-1/ratio)*100:.0f}% por km).")
    st.plotly_chart(g.fig_waterfall(r), use_container_width=True, config=PLOTCFG)
    st.plotly_chart(g.fig_cashflow(r), use_container_width=True, config=PLOTCFG)

# ── TAB 2: TCO detallado ──────────────────────────────────────────────────
with t2:
    c1, c2 = st.columns([3, 2])
    with c1:
        st.plotly_chart(g.fig_composicion_tco(r), use_container_width=True, config=PLOTCFG)
    with c2:
        st.plotly_chart(g.fig_costo_km(r), use_container_width=True, config=PLOTCFG)
    st.subheader("Detalle año a año (flota completa)")
    n = horizonte
    df = pd.DataFrame({
        "Año": list(range(0, n + 1)),
        "Flujo diésel": [round(-f) for f in r["escenario_diesel"]["flujo"]],
        "Flujo EV": [round(-f) for f in r["escenario_ev"]["flujo"]],
        "Ahorro incremental": [0] + [round(a) for a in r["ahorro_anual"]],
        "Flujo neto del cambio": [round(f) for f in r["flujo_incremental"]],
    })
    st.dataframe(df.style.format({c: clp for c in df.columns if c != "Año"}), use_container_width=True, hide_index=True)
    st.download_button("⬇️ Descargar detalle (CSV)", df.to_csv(index=False).encode("utf-8"),
                       "tco_flota_eauto.csv", "text/csv")
    cc = st.columns(3)
    cc[0].metric("TCO diésel (VP)", clp_mm(r["tco_diesel"]))
    cc[1].metric("TCO eléctrico (VP)", clp_mm(r["tco_ev"]))
    cc[2].metric("Sobrecosto inicial (CAPEX delta)", clp_mm(r["inc_capex"]))

# ── TAB: Capacidad y flota (fusión Logística + Capacidad equivalente) ──────
with tflota:
    log = r["logistica"]
    # Lectura B (más capacidad, NOMINAL) desde una sola fuente: los valores de la barra lateral.
    # La cifra de unidades equivalentes (Lectura A) viene SIEMPRE del motor (r['logistica']),
    # que usa utilización real + autonomía y es la que alimenta el VAN/choferes.
    cap = equivalencia_capacidad(int(s.num_vehiculos_diesel), float(s.volumen_diesel_m3),
                                 float(s.carga_util_diesel_kg), float(s.volumen_ev_m3),
                                 float(s.carga_util_ev_kg))

    st.markdown("### Capacidad y flota equivalente")
    st.caption("La mayor carga por unidad del EV se puede aprovechar de dos formas: **(A)** mover la misma "
               "carga con **menos unidades** (y menos choferes), o **(B)** mover **más carga** con las mismas unidades.")

    # — Toggle de equivalencia EN LA PESTAÑA (sincronizado con el de la barra lateral) —
    st.checkbox("**Aplicar equivalencia por capacidad** — reemplazar la flota por la cantidad mínima de EV "
                "que iguala la capacidad", key="eq_cap_tab", on_change=_eq_from_tab,
        help="Activado: el modelo calcula cuántos EV bastan para mover la misma carga diaria y reemplaza la flota "
             "por esa cantidad MENOR (Lectura A) → menos vehículos y choferes, lo que alimenta el VAN. "
             "Desactivado: reemplazo 1:1 (mismo nº de vehículos). Es el mismo control de la barra lateral.")
    if s.aplicar_equivalencia_capacidad:
        st.markdown(
            f"<div style='color:#0B5E2F;font-size:13px;margin:-2px 0 8px'>✅ <b>Modo equivalencia activo.</b> "
            f"El modelo reemplaza los <b>{r['n_diesel']}</b> furgones diésel por <b>{r['n_ev']} EV</b> "
            f"(−{log['reduccion_vehiculos']} unidades · −{log['reduccion_choferes']} choferes). "
            f"Todo lo de abajo refleja esa flota reducida.</div>", unsafe_allow_html=True)
    else:
        st.markdown(
            "<div style='color:#5C6B63;font-size:13px;margin:-2px 0 8px'>○ <b>Modo reemplazo 1:1.</b> "
            "Misma cantidad de vehículos que la flota diésel. Marca la casilla para que el modelo reduzca la "
            "flota (y los choferes) usando la mayor carga del EV, y veas el ahorro que aporta al VAN.</div>",
            unsafe_allow_html=True)

    # 1) Ecuación sinóptica — unidades desde el motor (misma flota que el VAN)
    eqn = (f"<div style='background:#F2F8F4;border-left:4px solid #00A651;border-radius:8px;"
           f"padding:14px 18px;margin:6px 0 10px;font-size:17px;color:#15302A'>"
           f"<b>{r['n_diesel']}</b> furgones diésel "
           f"<span style='color:#5C6B63'>({s.volumen_diesel_m3:g} m³ · {s.carga_util_diesel_kg:,.0f} kg c/u)</span>"
           f" &nbsp;≡&nbsp; <b style='color:#0B5E2F'>{r['n_ev']}</b> Gecko EV "
           f"<span style='color:#5C6B63'>({s.volumen_ev_m3:g} m³ · {s.carga_util_ev_kg:,.0f} kg c/u)</span>"
           f" &nbsp;→&nbsp; <b style='color:#0B5E2F'>−{log['reduccion_vehiculos']} unidades</b></div>")
    st.markdown(eqn.replace(",", "."), unsafe_allow_html=True)

    # 2) Cuatro métricas: las dos lecturas + el puente a operación y dinero
    c = st.columns(4)
    c[0].metric("Flota diésel hoy", r["n_diesel"])
    c[1].metric("Flota EV equivalente", r["n_ev"], delta=f"{r['n_ev']-r['n_diesel']}")
    c[2].metric("Choferes que se liberan", log["reduccion_choferes"])
    c[3].metric("Ahorro choferes/año", clp_mm(r["ahorro_choferes_anual"]))

    # 3) Gráfico hero (Lectura A) — pictograma alimentado por el MOTOR, no por el cálculo nominal
    pic = {"n_diesel": r["n_diesel"], "n_ev": r["n_ev"],
           "vol_total_d": r["n_diesel"] * s.volumen_diesel_m3,
           "peso_total_d": r["n_diesel"] * s.carga_util_diesel_kg}
    st.plotly_chart(g.fig_pictograma_capacidad(pic), use_container_width=True, config=PLOTCFG)

    # 4) Puente al dinero (sólo cuando hay reducción real): cuantifica el aporte al VAN
    if s.aplicar_equivalencia_capacidad and log["reduccion_vehiculos"] > 0:
        chof_vp = r["waterfall"]["choferes"]
        pct = f" (≈{chof_vp / r['van'] * 100:.0f}% del VAN)" if r["van"] and r["van"] > 0 else ""
        st.success(f"Esos **{log['reduccion_vehiculos']} vehículos menos** son **{log['reduccion_choferes']} "
                   f"choferes menos** → aportan **{clp_mm(chof_vp)}** al VAN{pct} "
                   f"(es la barra «Choferes» del waterfall en *Resumen ejecutivo*).")

    # 5) Las dos lecturas en texto — el binding se enuncia SOLO aquí
    st.markdown(f"""
**Lectura A · misma carga, menos unidades.** La flota diésel mueve por día tipo
**{log['peso_dia_kg']:,.0f} kg** · **{log['volumen_dia_m3']:,.1f} m³** · **{log['km_dia_flota']:,.0f} km**.
Igualar esa capacidad con el EV ({s.carga_util_ev_kg:,.0f} kg / {s.volumen_ev_m3:g} m³ / {s.autonomia_km:.0f} km)
requiere **peso {log['req_peso']:.1f}** · **volumen {log['req_volumen']:.1f}** · **autonomía {log['req_autonomia']:.1f}**
vehículos → manda **{log['restriccion_binding']}**: **bastan {log['n_ev_equivalente']} EV** para igualar la capacidad.

**Lectura B · mismas unidades, más capacidad.** Con las mismas **{r['n_diesel']} unidades**, la flota EV transporta
**+{cap['amp_vol_pct']*100:.0f}% de volumen** (+{cap['amp_vol_abs']:.0f} m³) y **+{cap['amp_peso_pct']*100:.0f}% de carga**
(+{cap['amp_peso_abs']:,.0f} kg), a capacidad nominal (vehículo lleno).
""".replace(",", "."))

    # 6) Dos barras compactas — Lectura B (única evidencia gráfica de "más capacidad")
    cv, cp = st.columns(2)
    cv.plotly_chart(g.fig_capacidad_total(cap, "volumen"), use_container_width=True, config=PLOTCFG)
    cp.plotly_chart(g.fig_capacidad_total(cap, "peso"), use_container_width=True, config=PLOTCFG)

    # 7) Tabla numérica única (desde cap)
    tabla_cap = pd.DataFrame({
        "Dimensión": ["Volumen", "Carga útil (peso)"],
        "Diésel (por u.)": [f"{s.volumen_diesel_m3:g} m³", f"{s.carga_util_diesel_kg:,.0f} kg".replace(",", ".")],
        "EV (por u.)": [f"{s.volumen_ev_m3:g} m³", f"{s.carga_util_ev_kg:,.0f} kg".replace(",", ".")],
        "Más capacidad/u.": [f"+{cap['amp_vol_pct']*100:.0f}%", f"+{cap['amp_peso_pct']*100:.0f}%"],
        "Flota diésel total": [f"{cap['vol_total_d']:.0f} m³", f"{cap['peso_total_d']:,.0f} kg".replace(",", ".")],
        "EV p/ igualar (nominal)": [f"{cap['ev_vol_exacto']:.2f} → {cap['ev_vol']}",
                                    f"{cap['ev_peso_exacto']:.2f} → {cap['ev_peso']}"],
    })
    st.dataframe(tabla_cap, use_container_width=True, hide_index=True)

    # 8) Nota al pie — diferencia operativo (A) vs nominal (B) + specs
    st.caption(f"La **Lectura A** (operativa) usa utilización real ({s.utilizacion_peso_pct*100:.0f}% peso / "
               f"{s.utilizacion_volumen_pct*100:.0f}% volumen) y autonomía; la **Lectura B** es nominal (vehículo "
               f"lleno), por eso su N° de EV puede diferir. Specs de volumen: EV48 6,2 m³ certificado (6,7 con "
               f"mampara abierta) · MagicWay 8,1 m³. Edita los valores en la barra lateral (🚚 Logística y choferes).")

# ── TAB 4: Tributario ─────────────────────────────────────────────────────
with t4:
    trib = r["tributario"]
    st.plotly_chart(g.fig_depreciacion(r), use_container_width=True, config=PLOTCFG)
    gan = trib["ganancia_vpn_instantanea_vs_lineal"]
    if trib["conviene_acelerar"]:
        st.success(f"✅ **Conviene aplicar depreciación instantánea.** Adelantar el 100% de la deducción al año 1 "
                   f"aumenta el valor presente del escudo tributario en **{clp_mm(gan)}** por el solo efecto del "
                   f"tiempo (mismo monto deducido, pero antes).")
    else:
        st.warning("⚠️ Con los supuestos actuales **no se captura** el beneficio de acelerar: la empresa necesita "
                   "utilidades que absorban la mayor deducción. Si da pérdida, el beneficio se difiere (pérdida de "
                   "arrastre) y pierde valor en el tiempo.")
    st.markdown(f"""
**Cómo funciona el escudo tributario.** La depreciación es un gasto que rebaja la base imponible:
cada peso depreciado ahorra **{s.tasa_impuesto*100:.0f} centavos** de impuesto (la tasa de Primera Categoría).
Acelerar **no cambia el total** deducido (el vehículo se deduce una sola vez), pero **adelanta** ese ahorro,
y un peso hoy vale más que uno en 7 años. Por eso, con utilidades, la instantánea siempre maximiza el VAN.

> Nota legal: la depreciación acelerada/instantánea afecta el **Impuesto de Primera Categoría**; la diferencia
> con la depreciación normal se controla en un registro aparte para los retiros de los dueños. Confirma con tu
> contador el régimen y la ventana vigente (Ley 21.305 / SII Res. Ex. 56/2021, citada hasta feb-2031).
""")
    df_t = pd.DataFrame({
        "Régimen": ["Lineal (7 a)", "Acelerada (1/3)", "Instantánea (año 1)"],
        "VP escudo tributario": [trib["regimenes"][k]["vpn_escudo"] for k in ("lineal", "acelerada", "instantanea")],
    })
    st.dataframe(df_t.style.format({"VP escudo tributario": clp}), use_container_width=True, hide_index=True)

# ── TAB 5: Sensibilidad ───────────────────────────────────────────────────
with t5:
    st.subheader("¿Qué variables mueven más el VAN? · tornado de sensibilidad")
    filas = tornado(s, delta=0.20)
    st.plotly_chart(g.fig_tornado(filas, r["van"], delta_pct=20), use_container_width=True, config=PLOTCFG)
    top = filas[0]["palanca"] if filas else ""
    st.markdown(
        "**Cómo leerlo.** Cada variable se mueve **±20 %** dejando todo lo demás igual. La **longitud** de "
        "la barra = cuánto cambia el VAN ⇒ **las de arriba son las más decisivas** "
        f"(aquí manda **{top}**). Bajo cada nombre se indica su **dirección** y su **influencia** "
        "(cuánto mueve el VAN). El **color** muestra el efecto: 🟩 verde = el VAN **sube**, "
        "🟥 rojo = el VAN **baja**.")
    st.info(
        "**Sobre la “proporción inversa” que notaste:** no todas las variables empujan en el mismo sentido, "
        "y bajo cada nombre se aclara con **“mejora al subir”** o **“mejora al bajar”**.\n\n"
        "• **Mejora al SUBIR** (costos del *rival*): precio del diésel, kilómetros al año, mantención diésel — "
        "cuando **aumentan**, el caso eléctrico mejora.\n\n"
        "• **Mejora al BAJAR** (costos *propios*): precio del EV, tasa de descuento, precio de la electricidad — "
        "el VAN mejora cuando **disminuyen**.\n\n"
        "No es un error del gráfico: es la dirección real de cada palanca. Pasa el cursor sobre una barra para "
        "ver el valor exacto del input y su efecto en el VAN.")
    st.divider()
    st.subheader("Mapa de calor — Precio diésel × Kilómetros al año → VAN")
    precios = [1100, 1300, 1500, 1700, 1900, 2100]
    kms = [15_000, 20_000, 30_000, 40_000, 50_000, 60_000]
    Z = sensibilidad_2d(s, "precio_diesel_l", precios, "km_anual_por_vehiculo", kms, "van")
    st.plotly_chart(g.fig_heatmap(Z, precios, kms, "Precio diésel (CLP/L)", "Km/año", "VAN (M)"),
                    use_container_width=True, config=PLOTCFG)
    st.caption("Cada celda muestra el VAN con su signo: **positivo (+) = el cambio conviene** (verde); "
               "negativo (−) = no conviene (rojo). Se ve cómo el caso eléctrico se fortalece con más "
               "kilómetros y diésel más caro — el perfil de las flotas de alta utilización.")

# ── TAB 6: CO₂ ────────────────────────────────────────────────────────────
with t6:
    c1, c2 = st.columns([3, 2])
    with c1:
        st.plotly_chart(g.fig_co2(r), use_container_width=True, config=PLOTCFG)
    with c2:
        st.metric("CO₂ evitado al año", f"{r['co2_evitado_anio']:.1f}".replace(".", ",") + " t")
        st.metric(f"CO₂ evitado en {horizonte} años", f"{r['co2_evitado_horizonte']:.0f} t")
        arboles = r["co2_evitado_anio"] * 1000 / 21  # ~21 kg CO₂/árbol/año
        st.info(f"El CO₂ evitado al año equivale a lo que capturan ~**{arboles:,.0f} árboles** en un año."
                .replace(",", "."))
    st.markdown(f"""
**Cálculo.** Emisiones diésel = litros/año × **{2.68} kg CO₂/L** (factor de combustión).
Emisiones EV = kWh/año × **{0.30} kg CO₂/kWh** (intensidad media de la red eléctrica chilena, SEN).
El EV no emite en el punto de uso; su huella depende de la matriz eléctrica, que en Chile se descarboniza año a año
(por lo que el CO₂ evitado real tiende a ser mayor en el futuro). Súmale la exención de restricción vehicular y el
impuesto verde ≈ $0 como beneficios regulatorios adicionales.
""")

# ── TAB 7: Metodología ────────────────────────────────────────────────────
with t7:
    metodologia.render(s, r)

st.caption(f"E-AUTO Global · Modelador de flota v1.0 · Las cifras de arriba reflejan TUS inputs actuales "
           f"(diésel {clp(precio_diesel_l)}/L · IVA {'recuperable' if iva_recuperable else 'no recuperable'}). "
           f"El motor está validado contra el caso base del Estudio de Mercado (Entregable 7).")

# ════════════════════════════════════════════════════════════════════════════
#  EL MENÚ LATERAL SIEMPRE VISIBLE
#  Streamlit recuerda en localStorage si la barra quedó colapsada, y esa marca
#  ANULA initial_sidebar_state="expanded" en las visitas siguientes (por eso a
#  algunos usuarios «desaparecía» el menú sin forma de reabrirlo). Este componente
#  corre en su iframe del MISMO origen (srcDoc → allow-same-origin): borra esa
#  marca y, si la barra está colapsada en un viewport de escritorio, la reabre
#  automáticamente UNA vez por sesión. Si algo fallara, el botón verde de
#  reapertura (CSS de arriba) queda siempre disponible como respaldo.
# ════════════════════════════════════════════════════════════════════════════
components.html("""
<script>
(function () {
  try {
    var p = window.parent;
    if (!p || !p.document) return;
    var SK = '__eauto_sidebar_autoexpanded';
    // 1) Borrar la marca persistente de "barra colapsada".
    try {
      for (var i = p.localStorage.length - 1; i >= 0; i--) {
        var k = p.localStorage.key(i);
        if (k && k.indexOf('stSidebarCollapsed') === 0) p.localStorage.removeItem(k);
      }
    } catch (e) {}
    // 2) Reabrir automáticamente una sola vez por sesión (no peleamos si el
    //    usuario la cierra a propósito), y sólo en pantallas de escritorio.
    if (p.sessionStorage.getItem(SK)) return;
    var tries = 0;
    var iv = setInterval(function () {
      tries++;
      var done = false;
      try {
        var sb = p.document.querySelector('[data-testid="stSidebar"]');
        if (sb) {
          if (sb.getAttribute('aria-expanded') === 'false') {
            if (p.innerWidth >= 640) {
              var btn = p.document.querySelector('[data-testid="stExpandSidebarButton"]');
              if (btn) { btn.click(); done = true; }
            }
          } else { done = true; }
        }
      } catch (e) {}
      if (done || tries > 25) {
        clearInterval(iv);
        try { p.sessionStorage.setItem(SK, '1'); } catch (e) {}
      }
    }, 120);
  } catch (e) {}
})();
</script>
""", height=0)
