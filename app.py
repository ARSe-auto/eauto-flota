# -*- coding: utf-8 -*-
"""
app.py — Modelador de reemplazo de flota diésel → eléctrica (E-AUTO Global).
Interfaz Streamlit. Ejecutar:  streamlit run app.py
"""
from dataclasses import asdict
import pandas as pd
import streamlit as st

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

# ── Estilos (criterio de diseño limpio: tipografía Montserrat, grilla, aire) ──
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700;800&display=swap');
  html, body, [class*="css"], .stMarkdown, [data-testid="stMetric"], button[data-baseweb="tab"]
        { font-family:'Montserrat',-apple-system,Helvetica,Arial,sans-serif; }
  .block-container { padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1290px; }

  /* quitar chrome de Streamlit para un lienzo limpio */
  [data-testid="stToolbar"], #MainMenu, footer { visibility: hidden; }
  header[data-testid="stHeader"] { background: transparent; height: 0; }

  /* Encabezado */
  .ea-hero { background:#0B5E2F; padding: 26px 30px; border-radius: 10px; color:#fff;
             margin-bottom: 22px; border-left: 4px solid #00A651; }
  .ea-hero .eyebrow { text-transform:uppercase; letter-spacing:.2em; font-size:10.5px;
                      font-weight:700; opacity:.82; margin-bottom:9px; }
  .ea-hero h1 { margin:0; font-size:25px; font-weight:700; letter-spacing:-.01em; line-height:1.18; }
  .ea-hero p  { margin:9px 0 0; opacity:.82; font-size:13px; font-weight:300; }

  /* Métricas como tarjetas sobrias */
  div[data-testid="stMetric"] { background:#FAFBFA; border:1px solid #ECEFEE; border-radius:8px;
                                padding:13px 16px; }
  div[data-testid="stMetricLabel"] p { font-size:12px; color:#7A8780; font-weight:500; }
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

st.markdown(
    '<div class="ea-hero">'
    '<div class="eyebrow">E-AUTO Global · Electromovilidad utilitaria</div>'
    '<h1>Modelador de Reemplazo de Flota · Diésel → Eléctrico</h1>'
    '<p>Análisis TCO + logística + tributario · Gecko EV48 / MagicWay · '
    'valores base: Estudio de Mercado EV Comerciales Chile (jun-2026)</p></div>',
    unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
#  SIDEBAR — INPUTS (cada campo con su ayuda)
# ════════════════════════════════════════════════════════════════════════════
sb = st.sidebar
sb.header("⚙️ Variables del modelo")
sb.caption("Pasa el cursor sobre el ícono **ⓘ** de cada campo para ver la ayuda, "
           "el valor típico en Chile y la fuente del supuesto.")

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
with sb.expander("🚚 Logística y choferes"):
    equivalencia = st.checkbox("Aplicar equivalencia por capacidad (reducir flota)", value=False,
        help="Si lo activas, el modelo calcula cuántos EV bastan para mover la MISMA carga que la flota diésel. "
             "Como el EV48 carga más (1.440 kg), a veces se necesitan MENOS vehículos → menos choferes.")
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
    pb_txt = f"{r['payback']:.1f} a"
ahorro_anio_prom = sum(r["ahorro_anual"]) / len(r["ahorro_anual"])

k = st.columns(6)
k[0].metric("VAN del cambio", clp_mm(r["van"]),
            help="Valor Actual Neto: la riqueza neta (en $ de hoy) que genera reemplazar la flota. Positivo = conviene.")
k[1].metric("TIR incremental", tir_txt,
            help="Tasa Interna de Retorno de la inversión incremental. Compárala con tu costo de capital.")
k[2].metric("Payback", pb_txt,
            help="Años para recuperar el sobrecosto inicial del cambio.")
k[3].metric("Ahorro anual prom.", clp_mm(ahorro_anio_prom),
            help="Ahorro promedio por año de toda la flota (energía + mantención + choferes + tributario).")
k[4].metric(f"Ventaja TCO {horizonte}a", f"{r['tco_delta_pct']*100:.0f}%", clp_mm(r["tco_delta"]),
            help="Cuánto más barato es el TCO eléctrico vs diésel en el horizonte (valor presente).")
k[5].metric("CO₂ evitado/año", f"{r['co2_evitado_anio']:.0f} t",
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

# ════════════════════════════════════════════════════════════════════════════
#  TABS
# ════════════════════════════════════════════════════════════════════════════
t1, t2, t3, tcap, t4, t5, t6, t7 = st.tabs(
    ["📊 Resumen ejecutivo", "💰 TCO detallado", "🚚 Logística", "📦 Capacidad equivalente",
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

# ── TAB 3: Logística ──────────────────────────────────────────────────────
with t3:
    log = r["logistica"]
    st.plotly_chart(g.fig_logistica(r), use_container_width=True, config=PLOTCFG)
    c = st.columns(4)
    c[0].metric("Vehículos diésel hoy", r["n_diesel"])
    c[1].metric("Vehículos EV equivalentes", r["n_ev"], delta=f"{r['n_ev']-r['n_diesel']}")
    c[2].metric("Choferes reducibles", log["reduccion_choferes"])
    c[3].metric("Ahorro choferes/año", clp_mm(r["ahorro_choferes_anual"]))
    st.markdown(f"""
**Restricción que manda (binding): `{log['restriccion_binding']}`**

La flota diésel mueve por día tipo: **{log['peso_dia_kg']:,.0f} kg** ·
**{log['volumen_dia_m3']:,.1f} m³** · **{log['km_dia_flota']:,.0f} km**.
Para igualar esa capacidad con el EV ({s.carga_util_ev_kg:,.0f} kg / {s.volumen_ev_m3} m³ /
{s.autonomia_km:.0f} km) se requieren:
- por **peso**: {log['req_peso']:.2f} vehículos
- por **volumen**: {log['req_volumen']:.2f} vehículos
- por **autonomía**: {log['req_autonomia']:.2f} vehículos

→ binding = **{log['n_ev_equivalente']} EV**.
""".replace(",", "."))
    if not s.aplicar_equivalencia_capacidad:
        st.info("Estás en modo **reemplazo 1:1**. Activa *«Aplicar equivalencia por capacidad»* en la barra "
                "lateral para que el modelo reduzca la flota (y los choferes) usando la mayor carga del EV.")
    elif log["reduccion_vehiculos"] > 0:
        st.success(f"Con la mayor capacidad del EV puedes operar con **{log['reduccion_vehiculos']} vehículos menos** "
                   f"y **{log['reduccion_choferes']} choferes menos** — la palanca de mayor valor en última milla.")

# ── TAB CAPACIDAD: Capacidad equivalente ──────────────────────────────────
with tcap:
    st.markdown("### 📦 Capacidad equivalente de transporte · diésel → eléctrico")
    st.caption("La mayor carga por unidad del EV se lee de dos formas: **(A)** mover la misma carga "
               "con **menos unidades**, o **(B)** mover **más carga** con las mismas unidades. "
               "Cálculo a capacidad nominal (vehículo lleno).")

    ci = st.columns(5)
    cap_n = ci[0].number_input("Furgones diésel", 1, 500, int(s.num_vehiculos_diesel), step=1, key="cap_n")
    cap_vd = ci[1].number_input("Volumen diésel (m³/u)", 0.5, 30.0, float(s.volumen_diesel_m3), step=0.1, key="cap_vd")
    cap_pd = ci[2].number_input("Carga diésel (kg/u)", 100, 6000, int(s.carga_util_diesel_kg), step=10, key="cap_pd")
    cap_ve = ci[3].number_input("Volumen EV (m³/u)", 0.5, 30.0, round(max(6.7, float(s.volumen_ev_m3)), 1), step=0.1,
        key="cap_ve", help="EV48 = 6,2 m³ certificado (GB/T) · 6,7 m³ con mampara abierta · MagicWay = 8,1 m³.")
    cap_pe = ci[4].number_input("Carga EV (kg/u)", 100, 6000, int(s.carga_util_ev_kg), step=10, key="cap_pe")

    eq = equivalencia_capacidad(cap_n, cap_vd, cap_pd, cap_ve, cap_pe)

    # — Ecuación sinóptica —
    eqn = (f"<div style='background:#F2F8F4;border-left:4px solid #00A651;border-radius:8px;"
           f"padding:14px 18px;margin:6px 0 4px;font-size:17px;color:#15302A'>"
           f"<b>{eq['n_diesel']}</b> furgones diésel "
           f"<span style='color:#7A8780'>({cap_vd:g} m³ · {cap_pd:,.0f} kg c/u)</span>"
           f" &nbsp;≡&nbsp; <b style='color:#0B5E2F'>{eq['n_ev']}</b> Gecko EV "
           f"<span style='color:#7A8780'>({cap_ve:g} m³ · {cap_pe:,.0f} kg c/u)</span>"
           f" &nbsp;→&nbsp; <b style='color:#00A651'>−{eq['reduccion_u']} unidades</b></div>")
    st.markdown(eqn.replace(",", "."), unsafe_allow_html=True)

    # — Dos modos, lado a lado —
    cA, cB = st.columns(2)
    with cA:
        st.markdown("#### 🔻 Modo A · misma carga, **menos unidades**")
        m = st.columns(2)
        m[0].metric("Unidades EV necesarias", eq["n_ev"], delta=f"−{eq['reduccion_u']} vs {eq['n_diesel']}")
        m[1].metric("Reducción de flota", f"−{eq['reduccion_pct']*100:.0f}%")
        st.caption(f"Restricción que manda: **{eq['binding']}** "
                   f"(volumen {eq['ev_vol_exacto']:.2f}→{eq['ev_vol']} · peso {eq['ev_peso_exacto']:.2f}→{eq['ev_peso']} EV). "
                   f"Se redondea hacia arriba (no se compran fracciones de vehículo).")
    with cB:
        st.markdown("#### 🔺 Modo B · mismas unidades, **más capacidad**")
        m = st.columns(2)
        m[0].metric("Volumen total", f"+{eq['amp_vol_pct']*100:.0f}%",
                    delta=f"+{eq['amp_vol_abs']:.0f} m³")
        m[1].metric("Carga útil total", f"+{eq['amp_peso_pct']*100:.0f}%",
                    delta=f"+{eq['amp_peso_abs']:,.0f} kg".replace(",", "."))
        cap_txt = (f"Con las mismas **{eq['n_diesel']} unidades**, la flota EV transporta "
                   f"**{eq['vol_total_ev']:.0f} m³** (vs {eq['vol_total_d']:.0f}) y "
                   f"**{eq['peso_total_ev']:,.0f} kg** (vs {eq['peso_total_d']:,.0f}).")
        st.caption(cap_txt.replace(",", "."))

    # — Pictograma sinóptico —
    st.plotly_chart(g.fig_pictograma_capacidad(eq), use_container_width=True, config=PLOTCFG)

    # — Barras de capacidad (modo B) —
    cv, cp = st.columns(2)
    cv.plotly_chart(g.fig_capacidad_total(eq, "volumen"), use_container_width=True, config=PLOTCFG)
    cp.plotly_chart(g.fig_capacidad_total(eq, "peso"), use_container_width=True, config=PLOTCFG)

    # — Tabla numérica sinóptica —
    st.markdown("##### Detalle numérico")
    tabla_cap = pd.DataFrame({
        "Dimensión": ["Volumen", "Carga útil (peso)"],
        "Diésel (por u.)": [f"{cap_vd:g} m³", f"{cap_pd:,.0f} kg".replace(",", ".")],
        "EV (por u.)": [f"{cap_ve:g} m³", f"{cap_pe:,.0f} kg".replace(",", ".")],
        "Más capacidad/u.": [f"+{eq['amp_vol_pct']*100:.0f}%", f"+{eq['amp_peso_pct']*100:.0f}%"],
        "Flota diésel total": [f"{eq['vol_total_d']:.0f} m³", f"{eq['peso_total_d']:,.0f} kg".replace(",", ".")],
        "EV p/ igualar": [f"{eq['ev_vol_exacto']:.2f} → {eq['ev_vol']}",
                          f"{eq['ev_peso_exacto']:.2f} → {eq['ev_peso']}"],
    })
    st.dataframe(tabla_cap, use_container_width=True, hide_index=True)
    st.caption("Nota: el EV48 declara **6,2 m³ certificados (GB/T)** y **6,7 m³ con mampara abierta**; "
               "el MagicWay, **8,1 m³**. Ajusta los campos de arriba según el modelo y configuración.")

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
    st.subheader("Tornado — ¿qué palancas mueven más el VAN?")
    filas = tornado(s, delta=0.20)
    st.plotly_chart(g.fig_tornado(filas, r["van"]), use_container_width=True, config=PLOTCFG)
    st.caption("Cada barra mueve una variable ±20% dejando todo lo demás constante. Las de arriba son las más "
               "decisivas — donde más vale la pena tener datos reales del cliente.")
    st.divider()
    st.subheader("Mapa de calor — Precio diésel × Kilómetros al año → VAN")
    precios = [800, 950, 1050, 1150, 1300, 1500]
    kms = [15_000, 20_000, 30_000, 40_000, 50_000, 60_000]
    Z = sensibilidad_2d(s, "precio_diesel_l", precios, "km_anual_por_vehiculo", kms, "van")
    st.plotly_chart(g.fig_heatmap(Z, precios, kms, "Precio diésel (CLP/L)", "Km/año", "VAN (M)"),
                    use_container_width=True, config=PLOTCFG)
    st.caption("Verde = el cambio conviene; rojo = no. Se ve cómo el caso eléctrico se fortalece con más "
               "kilómetros y diésel más caro — exactamente el perfil de las flotas de alta utilización.")

# ── TAB 6: CO₂ ────────────────────────────────────────────────────────────
with t6:
    c1, c2 = st.columns([3, 2])
    with c1:
        st.plotly_chart(g.fig_co2(r), use_container_width=True, config=PLOTCFG)
    with c2:
        st.metric("CO₂ evitado al año", f"{r['co2_evitado_anio']:.1f} t")
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

st.caption("E-AUTO Global · Modelador de flota v1.0 · Las cifras de arriba reflejan TUS inputs actuales. "
           "El motor reproduce además el caso base validado del Estudio de Mercado (Entregable 7): "
           "payback ~2,6 a · VAN +7M/u · TIR ~33%, con los supuestos originales de ese estudio "
           "(diésel 1.050/L, sin recuperación de IVA).")
