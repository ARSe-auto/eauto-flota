# -*- coding: utf-8 -*-
"""
metodologia.py — Pestaña "Metodología" del modelador de flota.
Explica cada cálculo con: (1) un esquema visual (Graphviz), (2) la fórmula (LaTeX),
y (3) un ejemplo numérico EN VIVO con los valores actuales del modelo.
"""
import pandas as pd
import streamlit as st

# Paleta e-auto para los diagramas
_NODE = 'shape=box style="rounded,filled" fillcolor="#E6F6EE" color="#0B5E2F" fontname="Helvetica" fontsize="11" fontcolor="#10321F"'
_EDGE = 'color="#6B7280" arrowsize="0.7"'
_HILITE = 'fillcolor="#00A651" fontcolor="white"'
_DECISION = 'shape="diamond" fillcolor="#FCEFC7" color="#B8860B"'
_RESULT = 'fillcolor="#D7F3E3" color="#0B5E2F"'


def _clp(x):
    return "$" + f"{x:,.0f}".replace(",", ".")


def _mm(x):
    s = f"{x/1e6:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return "$" + s + "M"


def _md(t):
    """Escapa '$' para que Streamlit (KaTeX) no interprete pares de $ como fórmulas
    dentro de st.markdown/st.success. No usar en st.metric ni en st.dataframe.format."""
    return t.replace("$", "\\$")


# ════════════════════════════════════════════════════════════════════════════
#  DIAGRAMAS (estructura estática — los números van en los ejemplos al lado)
# ════════════════════════════════════════════════════════════════════════════
MASTER = f'''digraph {{
  rankdir=LR; nodesep=0.25; ranksep=0.55; bgcolor="transparent";
  node [{_NODE}]; edge [{_EDGE}];
  subgraph cluster_in {{ label="① INPUTS"; fontname="Helvetica"; fontcolor="#0B5E2F"; style="rounded,dashed"; color="#9CC7B0";
    in1 [label="Operación\\nkm/año · horizonte · tasa"];
    in2 [label="Diésel\\nprecio · km/L · $/L · mant."];
    in3 [label="Eléctrico\\nprecio · km/kWh · $/kWh · mant."];
    in4 [label="Logística\\ncarga · volumen · chofer"];
    in5 [label="Tributario\\ntasa · régimen deprec."];
  }}
  ckm  [label="② Costo / km"];
  opex [label="③ OPEX anual\\n(escalado)"];
  depr [label="⑦ Depreciación\\n→ escudo fiscal"];
  log  [label="⑥ Equivalencia\\n→ N° EV · choferes"];
  fd   [label="④ Flujo de caja\\nFLOTA DIÉSEL"];
  fe   [label="④ Flujo de caja\\nFLOTA EV"];
  tco  [label="⑤ TCO (valor presente)\\nde cada flota" {_RESULT}];
  inc  [label="⑤ Flujo INCREMENTAL\\n(diésel − EV + choferes)"];
  out  [label="VAN · TIR · Payback" {_HILITE}];
  in1->ckm; in2->ckm; in3->ckm;
  ckm->opex; in2->opex; in3->opex;
  in5->depr; in4->log;
  opex->fd; opex->fe; depr->fd; depr->fe; log->fe;
  fd->tco; fe->tco; fd->inc; fe->inc; log->inc;
  tco->out; inc->out;
}}'''

DIAG_CKM = f'''digraph {{ rankdir=LR; bgcolor="transparent"; node [{_NODE}]; edge [{_EDGE}];
  d1 [label="1 ÷ rendimiento\\n(km por litro)"]; d2 [label="× precio diésel\\n($/litro)"];
  dr [label="Costo/km DIÉSEL" {_RESULT}]; d1->d2->dr;
  e1 [label="1 ÷ eficiencia\\n(km por kWh)"]; e2 [label="× precio energía\\n($/kWh)"];
  e3 [label="× (1 + pérdidas\\nde carga)"]; er [label="Costo/km EV" {_RESULT}]; e1->e2->e3->er;
}}'''

DIAG_FLUJO = f'''digraph {{ rankdir=LR; bgcolor="transparent"; node [{_NODE}]; edge [{_EDGE}];
  a0 [label="AÑO 0\\n− CAPEX\\n(vehículos + cargadores)" fillcolor="#F8D7D2" color="#B23B2E"];
  a1 [label="AÑO 1\\n− OPEX\\n+ escudo tributario"];
  ad [label="…" shape=plaintext fillcolor="transparent"];
  aN [label="AÑO N\\n− OPEX + escudo\\n+ valor residual" {_RESULT}];
  a0->a1->ad->aN;
}}'''

DIAG_LOG = f'''digraph {{ rankdir=LR; bgcolor="transparent"; node [{_NODE}]; edge [{_EDGE}];
  dem [label="Demanda diaria\\nde la flota diésel\\n(kg · m³ · km)"];
  c1 [label="÷ carga útil EV\\n= req. por PESO"];
  c2 [label="÷ volumen EV\\n= req. por VOLUMEN"];
  c3 [label="÷ autonomía útil\\n= req. por AUTONOMÍA"];
  mx [label="MAX\\n= restricción que manda" {_DECISION}];
  cl [label="techo ⌈ ⌉\\n→ N° de EV"];
  rd [label="N diésel − N EV\\n= choferes reducidos" {_RESULT}];
  dem->c1; dem->c2; dem->c3; c1->mx; c2->mx; c3->mx; mx->cl->rd;
}}'''

DIAG_DEPR = f'''digraph {{ rankdir=LR; bgcolor="transparent"; node [{_NODE}]; edge [{_EDGE}];
  cap [label="CAPEX del vehículo"];
  l [label="LINEAL\\nCAPEX ÷ 7 años\\n(deducción repartida)"];
  a [label="ACELERADA\\nvida = 7÷3 ≈ 2 años\\n(deducción concentrada)"];
  i [label="INSTANTÁNEA\\n100% el AÑO 1" {_HILITE}];
  cap->l; cap->a; cap->i;
  esc [label="× tasa impuesto\\n= escudo (ahorro de impuesto)" {_RESULT}];
  l->esc; a->esc; i->esc;
}}'''


# ════════════════════════════════════════════════════════════════════════════
#  RENDER
# ════════════════════════════════════════════════════════════════════════════
def render(s, r):
    st.markdown("## 🧭 Cómo calcula este modelo — mapa completo")
    st.caption("Cada caja es un paso de cálculo. Los números ⓵–⑦ corresponden a las secciones de abajo, "
               "donde cada paso se abre con su esquema, su fórmula y un ejemplo con TUS valores actuales.")
    st.graphviz_chart(MASTER, use_container_width=True)
    st.divider()

    # ── 1. Costo por km ──────────────────────────────────────────────────────
    st.markdown("### ② Costo de energía por kilómetro")
    st.caption("El corazón de la ventaja eléctrica: cuánto cuesta mover el vehículo 1 km.")
    st.graphviz_chart(DIAG_CKM, use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        st.latex(r"C^{diésel}_{km}=\frac{1}{\text{km/L}}\times P_{L}")
        st.markdown(_md(f"**Con tus valores:** 1 ÷ {s.rendimiento_km_l:g} × {_clp(s.precio_diesel_l)} "
                        f"= **{_clp(r['costo_km_diesel'])}/km**"))
    with c2:
        st.latex(r"C^{EV}_{km}=\frac{1}{\text{km/kWh}}\times P_{kWh}\times(1+\text{pérdidas})")
        st.markdown(_md(f"**Con tus valores:** 1 ÷ {s.eficiencia_km_kwh:g} × {_clp(s.precio_energia_kwh)} "
                        f"× {1+s.perdidas_carga_pct:.2f} = **{_clp(r['costo_km_ev'])}/km**"))
    ratio = r['costo_km_diesel'] / r['costo_km_ev'] if r['costo_km_ev'] else 0
    st.success(f"El km eléctrico es **{ratio:.1f}× más barato** en energía que el diésel "
               f"(−{(1-1/ratio)*100:.0f}% por km).")
    st.divider()

    # ── 2. OPEX anual ────────────────────────────────────────────────────────
    st.markdown("### ③ OPEX anual por vehículo (y su escalamiento)")
    st.caption("Suma de todos los costos de operar un vehículo un año. Cada partida sube un % cada año.")
    st.latex(r"\text{OPEX}_t = (E + M + N + S + P + A)\times(1+g)^{\,t-1}"
             r"\quad\scriptstyle E=\text{energía},\,M=\text{mant.},\,N=\text{neum.},\,S=\text{seguro},\,P=\text{permiso},\,A=\text{AdBlue}")
    od, oe = r["escenario_diesel"]["opex_desglose"], r["escenario_ev"]["opex_desglose"]
    tabla = pd.DataFrame({
        "Partida (año 1, por vehículo)": ["Energía / combustible", "Mantención", "Neumáticos",
                                          "Seguro", "Permiso circulación", "AdBlue", "TOTAL OPEX/año"],
        "Diésel": [od["energia"][0], od["mantencion"][0], od["neumaticos"][0], od["seguro"][0],
                   od["permiso"][0], od["adblue"][0], od["total"][0]],
        "Eléctrico": [oe["energia"][0], oe["mantencion"][0], oe["neumaticos"][0], oe["seguro"][0],
                      oe["permiso"][0], oe["adblue"][0], oe["total"][0]],
    })
    st.dataframe(tabla.style.format({"Diésel": _clp, "Eléctrico": _clp})
                 .apply(lambda x: ['font-weight:bold' if x.name == 6 else '' for _ in x], axis=1),
                 use_container_width=True, hide_index=True)
    st.markdown(f"Escalamiento usado: diésel **+{s.escalamiento_diesel*100:g}%/año**, "
                f"energía **+{s.escalamiento_energia*100:g}%/año**, "
                f"otros costos **+{s.escalamiento_costos*100:g}%/año**.")
    st.divider()

    # ── 3. Flujo de caja ─────────────────────────────────────────────────────
    st.markdown("### ④ Construcción del flujo de caja de cada flota")
    st.caption("Se ordenan todos los desembolsos e ingresos en una línea de tiempo, por flota.")
    st.graphviz_chart(DIAG_FLUJO, use_container_width=True)
    cd = r["escenario_diesel"]; ce = r["escenario_ev"]
    cols = st.columns(2)
    cols[0].markdown(_md(f"**Flota diésel ({r['n_diesel']} veh.)**\n\n"
                         f"- Año 0: − CAPEX **{_mm(cd['capex'])}**\n"
                         f"- Años 1–{s.horizonte_anios}: − OPEX + escudo\n"
                         f"- Año {s.horizonte_anios}: + residual **{_mm(cd['residual_neto'])}**"))
    cols[1].markdown(_md(f"**Flota eléctrica ({r['n_ev']} veh.)**\n\n"
                         f"- Año 0: − CAPEX **{_mm(ce['capex'])}** (incl. cargadores {_mm(ce['capex_infra'])})\n"
                         f"- Años 1–{s.horizonte_anios}: − OPEX + escudo\n"
                         f"- Año {s.horizonte_anios}: + residual **{_mm(ce['residual_neto'])}**"))
    st.divider()

    # ── 4. TCO ───────────────────────────────────────────────────────────────
    st.markdown("### ⑤ TCO — costo total de propiedad (valor presente)")
    st.caption("Todos los desembolsos futuros se traen a 'pesos de hoy' dividiéndolos por (1+tasa)^año. "
               "Así $1 dentro de 5 años vale menos que $1 hoy.")
    st.latex(r"\text{TCO}=\sum_{t=0}^{N}\frac{\text{egreso}_t}{(1+r)^{t}}")
    e3 = -cd["flujo"][3] if len(cd["flujo"]) > 3 else 0
    st.markdown(_md(f"**Ejemplo de descuento** (tasa = {s.tasa_descuento*100:g}%): un egreso de {_clp(e3)} en el "
                    f"año 3 vale hoy {_clp(e3)} ÷ (1+{s.tasa_descuento:.2f})³ = **{_clp(e3/(1+s.tasa_descuento)**3)}**."))
    m = st.columns(3)
    m[0].metric("TCO flota diésel (VP)", _mm(r["tco_diesel"]))
    m[1].metric("TCO flota eléctrica (VP)", _mm(r["tco_ev"]))
    m[2].metric("Ventaja eléctrica", f"{r['tco_delta_pct']*100:.0f}%", _mm(r["tco_delta"]))
    st.divider()

    # ── 5. VAN / TIR / Payback ───────────────────────────────────────────────
    st.markdown("### ⑤ Indicadores de la decisión de cambiarse")
    st.caption("Se evalúa el SOBRECOSTO de cambiar (CAPEX EV − CAPEX diésel) contra el AHORRO anual que produce.")
    cc = st.columns(3)
    with cc[0]:
        st.latex(r"\text{VAN}=\sum_t\frac{\text{flujo}_t}{(1+r)^t}")
        st.markdown(_md(f"Riqueza neta creada. Tuyo: **{_mm(r['van'])}**."))
    with cc[1]:
        st.latex(r"\text{TIR}:\ \text{VAN}=0")
        tir = f"{r['tir']*100:.0f}%" if r["tir"] is not None else "∞ (sin inversión neta)"
        st.markdown(f"Rentabilidad del cambio (bisección). Tuyo: **{tir}**.")
    with cc[2]:
        st.latex(r"\text{Payback}=\frac{\text{sobrecosto}}{\text{ahorro/año}}")
        pb = "Inmediato" if (r["payback"] or 0) <= 0.01 else (f"{r['payback']:.1f} años" if r["payback"] else ">horizonte")
        st.markdown(f"Tiempo de recuperación. Tuyo: **{pb}**.")
    st.markdown(_md(f"Sobrecosto inicial (CAPEX delta) = {_mm(r['escenario_ev']['capex'])} − "
                    f"{_mm(r['escenario_diesel']['capex'])} = **{_mm(r['inc_capex'])}**. "
                    f"Ahorro promedio = **{_mm(sum(r['ahorro_anual'])/len(r['ahorro_anual']))}/año**."))
    st.divider()

    # ── 6. Logística ─────────────────────────────────────────────────────────
    st.markdown("### ⑥ Equivalencia logística — ¿cuántos EV y cuántos choferes?")
    st.caption("La carga que hoy mueve la flota diésel se divide por la capacidad del EV. La restricción más "
               "exigente (la mayor) fija cuántos EV se necesitan. Si el EV carga más → menos vehículos y choferes.")
    st.graphviz_chart(DIAG_LOG, use_container_width=True)
    log = r["logistica"]
    eq = pd.DataFrame({
        "Restricción": ["Por peso (kg)", "Por volumen (m³)", "Por autonomía (km)"],
        "Demanda diaria flota": [log["peso_dia_kg"], log["volumen_dia_m3"], log["km_dia_flota"]],
        "Capacidad por EV": [s.carga_util_ev_kg, s.volumen_ev_m3, s.autonomia_km * s.autonomia_utilizable_pct],
        "EV requeridos": [log["req_peso"], log["req_volumen"], log["req_autonomia"]],
    })
    st.dataframe(eq.style.format({"Demanda diaria flota": "{:,.0f}", "Capacidad por EV": "{:,.0f}",
                                  "EV requeridos": "{:.2f}"}), use_container_width=True, hide_index=True)
    st.markdown(f"Restricción que manda (**binding**) = **{log['restriccion_binding']}** → "
                f"techo = **{log['n_ev_equivalente']} EV**. "
                + (f"Modo equivalencia activo → flota EV = **{log['n_ev_final']}** "
                   f"→ **{log['reduccion_choferes']} choferes menos**."
                   if s.aplicar_equivalencia_capacidad else
                   "Estás en modo **reemplazo 1:1** (la equivalencia no reduce la flota; actívala en la "
                   "pestaña «Capacidad y flota» o en la barra lateral)."))
    st.divider()

    # ── 7. Depreciación / escudo tributario ──────────────────────────────────
    st.markdown("### ⑦ Escudo tributario de la depreciación — ¿conviene acelerar?")
    st.caption("Depreciar es un gasto que rebaja el impuesto. Acelerar no cambia el TOTAL deducido, pero lo "
               "adelanta en el tiempo → su valor presente es mayor.")
    st.graphviz_chart(DIAG_DEPR, use_container_width=True)
    st.latex(r"\text{escudo}_t=\text{tasa impuesto}\times\text{depreciación}_t"
             r"\qquad\text{valor del beneficio}=\sum_t\frac{\text{escudo}_t}{(1+r)^t}")
    reg = r["tributario"]["regimenes"]
    n = s.horizonte_anios
    dep_tab = pd.DataFrame({
        "Año": list(range(1, n + 1)),
        "Lineal": reg["lineal"]["dep"],
        "Acelerada": reg["acelerada"]["dep"],
        "Instantánea": reg["instantanea"]["dep"],
    })
    st.markdown(_md(f"Depreciación anual del CAPEX EV ({_mm(r['escenario_ev']['capex_vehiculos'])}), por régimen "
                    f"(tasa impuesto {s.tasa_impuesto*100:g}%):"))
    st.dataframe(dep_tab.style.format({c: _clp for c in ["Lineal", "Acelerada", "Instantánea"]}),
                 use_container_width=True, hide_index=True)
    g = st.columns(3)
    g[0].metric("VP escudo · Lineal", _mm(reg["lineal"]["vpn_escudo"]))
    g[1].metric("VP escudo · Acelerada", _mm(reg["acelerada"]["vpn_escudo"]))
    g[2].metric("VP escudo · Instantánea", _mm(reg["instantanea"]["vpn_escudo"]),
                _mm(r["tributario"]["ganancia_vpn_instantanea_vs_lineal"]))
    if r["tributario"]["conviene_acelerar"]:
        st.success(_md(f"✅ **Conviene la instantánea**: adelantar el 100% al año 1 suma "
                       f"**{_mm(r['tributario']['ganancia_vpn_instantanea_vs_lineal'])}** de valor presente vs. lineal, "
                       f"solo por el efecto del tiempo. (Marco: Ley 21.305 / SII Res. Ex. 56/2021, ventana a feb-2031.)"))
    else:
        st.warning("⚠️ El beneficio de acelerar requiere utilidades que absorban la deducción. Sin ellas, se "
                   "difiere como pérdida de arrastre y pierde valor.")
    st.divider()

    # ── 8. CO₂ ───────────────────────────────────────────────────────────────
    st.markdown("### 🌱 Emisiones de CO₂ evitadas")
    st.latex(r"CO_2^{diésel}=\frac{km/\text{año}}{\text{km/L}}\times 2{,}68\ \tfrac{kg}{L}"
             r"\qquad CO_2^{EV}=\frac{km/\text{año}}{\text{km/kWh}}\times 0{,}30\ \tfrac{kg}{kWh}")
    st.markdown(f"Flota diésel: **{r['co2_diesel_anio']:.1f} t/año** · Flota EV: **{r['co2_ev_anio']:.1f} t/año** "
                f"→ evitas **{r['co2_evitado_anio']:.1f} t/año** "
                f"(**{r['co2_evitado_horizonte']:.0f} t** en {n} años). El factor EV baja a futuro porque la "
                f"red eléctrica chilena se descarboniza.")
    st.divider()

    # ── Supuestos y fuentes ──────────────────────────────────────────────────
    st.markdown("""
### ⚠️ Supuestos clave y advertencias
- **IVA — tratamiento idéntico para ambos:** diésel y eléctrico son vehículos comerciales y
  permiten **recuperar el IVA como crédito fiscal** si la empresa es contribuyente de IVA.
  Los precios se ingresan **IVA incluido** y el modelo descuenta el IVA por igual en los dos
  (CAPEX neto). No hay ventaja de IVA de un combustible sobre el otro.
- **Valor residual** del EV: mercado secundario incipiente → conviene ser conservador.
- Precios de **diésel y energía**: usar los reales del cliente (las palancas más sensibles — ver pestaña Sensibilidad).
- El **chofer**, no el combustible, es el mayor costo de la última milla: la equivalencia logística suele ser
  la palanca de mayor valor.
- Los resultados son **escenarios de decisión**, no hechos auditados. Validar en piloto residual, mantención y km/año.

**Fuentes:** Estudio de Mercado EV Comerciales Chile (jun-2026, Entregable 7) · Go-To-Market Killer EV48 ·
fichas técnicas certificadas 3CV · Ley 21.305 / SII Res. Ex. 56/2021 · ANAC 2025.
""")
