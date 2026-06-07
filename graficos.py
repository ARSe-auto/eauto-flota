# -*- coding: utf-8 -*-
"""graficos.py — Constructores de gráficos Plotly para el modelador de flota e-auto."""
from __future__ import annotations
import plotly.graph_objects as go
from motor import vpn

# ── Paleta e-auto (tonal, sobria — criterio de diseño europeo) ───────────────
VERDE = "#00A651"          # e-auto (marca)
VERDE_OSC = "#0B5E2F"
VERDE_CLARO = "#3FB984"
DIESEL = "#9C8B7A"         # taupe cálido (sustituye al marrón estridente)
GRIS = "#9AA3AD"
GRIS_OSC = "#6B7280"
AHORRO = "#3FB984"
ROJO = "#C9514E"           # terracota sobria (no rojo puro)
AZUL = "#8FA1B3"           # slate suave
AMBAR = "#C8A15A"          # oro apagado
TINTA = "#15302A"          # texto/títulos
GRID = "#ECEFEE"           # grilla casi imperceptible
LINEA = "#D7DBDA"          # ejes
MUTED = "#7A8780"          # etiquetas de ejes
PLANTILLA = "plotly_white"

FONT = dict(family="Montserrat, Helvetica Neue, Arial, sans-serif", size=13, color="#2B3B33")


def _layout(fig, titulo="", alto=420, leg=True, leg_y=-0.16, b=64, hover="x unified", **kw):
    """Layout base unificado: título alineado a la izquierda, leyenda al pie (nunca
    sobre el título), grilla mínima y ejes sobrios. `leg_y`/`b` controlan el espacio
    para la leyenda al pie según cuántas series tenga el gráfico."""
    fig.update_layout(
        title=dict(text=titulo, x=0, xanchor="left", y=0.97, yanchor="top",
                   font=dict(size=16, color=TINTA, family=FONT["family"]),
                   pad=dict(b=12, l=2)),
        template=PLANTILLA, font=FONT, height=alto,
        margin=dict(l=66, r=28, t=64, b=b),
        paper_bgcolor="white", plot_bgcolor="white",
        hovermode=hover, **kw,
    )
    if leg:
        fig.update_layout(legend=dict(
            orientation="h", yanchor="top", y=leg_y, xanchor="left", x=0,
            font=dict(size=11.5, color=GRIS_OSC), bgcolor="rgba(255,255,255,0)",
            borderwidth=0, itemsizing="constant"))
    else:
        fig.update_layout(showlegend=False)
    fig.update_xaxes(showgrid=False, zeroline=False, ticks="outside", ticklen=4,
                     tickcolor=LINEA, linecolor=LINEA,
                     title_font=dict(size=12, color=MUTED), tickfont=dict(color=MUTED, size=11.5),
                     title_standoff=12)
    fig.update_yaxes(showgrid=True, gridcolor=GRID, zeroline=False, linecolor="rgba(0,0,0,0)",
                     ticks="", title_font=dict(size=12, color=MUTED),
                     tickfont=dict(color=MUTED, size=11.5), title_standoff=14)
    return fig


def _mm(x):
    return x / 1e6


# ── 1. TCO acumulado (costo de propiedad descontado, año a año) ──────────────
def fig_tco_acumulado(r):
    s = r["supuestos"]
    n = s.horizonte_anios
    anios = list(range(0, n + 1))
    ch = r.get("serie_choferes") or [0.0] * n   # ahorro de choferes por año (1..n)

    # Costo acumulado NOMINAL (misma base que el payback simple del KPI) → el cruce
    # de las curvas coincide exactamente con el payback reportado. La flota EV se
    # muestra neta del ahorro de choferes que habilita (consistente con el flujo
    # incremental que define el payback/VAN).
    def acum_costo(esc, neto_choferes=False):
        out, c = [], 0.0
        for t, f in enumerate(esc["flujo"]):
            c += -f                                  # egreso nominal acumulado (+ = costo)
            if neto_choferes and t >= 1:
                c -= ch[t - 1]
            out.append(_mm(c))
        return out

    cd = acum_costo(r["escenario_diesel"])
    ce = acum_costo(r["escenario_ev"], neto_choferes=True)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=anios, y=cd, name="Flota diésel", mode="lines+markers",
                             line=dict(color=DIESEL, width=2.5),
                             marker=dict(size=6),
                             fill="tonexty", fillcolor="rgba(156,139,122,0.10)"))
    fig.add_trace(go.Scatter(x=anios, y=ce, name="Flota eléctrica (e-auto)", mode="lines+markers",
                             line=dict(color=VERDE, width=3.5),
                             marker=dict(size=6),
                             fill="tozeroy", fillcolor="rgba(0,166,81,0.08)"))
    # marca de payback (cruce de la inversión incremental) — línea + PUNTO explícito
    # en la intersección para que coincida sin ambigüedad con el KPI/gauge.
    pb = r["payback"]
    if pb is not None and pb <= n:
        lo = int(pb); hi = min(lo + 1, n); frac = pb - lo
        y_cross = cd[lo] + (cd[hi] - cd[lo]) * frac   # cd y ce coinciden en el cruce
        fig.add_vline(x=pb, line=dict(color=AMBAR, width=2, dash="dot"),
                      annotation_text=f"Payback {pb:.1f} a", annotation_position="top")
        fig.add_trace(go.Scatter(
            x=[pb], y=[y_cross], mode="markers",
            marker=dict(size=15, color=AMBAR, symbol="circle", line=dict(color="white", width=2.5)),
            name="Punto de equilibrio", showlegend=False,
            hovertemplate=f"Se igualan a los {pb:.1f} años<extra></extra>"))
        fig.add_annotation(x=pb, y=y_cross, text="se igualan", showarrow=True,
                           arrowhead=2, arrowsize=0.8, arrowcolor=AMBAR, ax=28, ay=38,
                           font=dict(size=11, color=VERDE_OSC))
    _layout(fig, "Costo acumulado de cada flota (nominal) · el cruce = payback", b=90, leg_y=-0.22)
    fig.update_yaxes(title="Millones CLP acumulados")
    fig.update_xaxes(title="Año", dtick=1)
    return fig


# ── 2. Waterfall del VAN (de dónde viene el valor de cambiarse) ──────────────
def fig_waterfall(r):
    w = r["waterfall"]
    etiquetas = ["Sobrecosto CAPEX", "Ahorro energía", "Ahorro mantención",
                 "Otros OPEX", "Choferes", "Escudo depreciación", "Valor residual", "VAN"]
    valores = [_mm(w["capex_extra"]), _mm(w["energia"]), _mm(w["mantencion"]),
               _mm(w["otros_opex"]), _mm(w["choferes"]), _mm(w["tributario"]),
               _mm(w["residual"]), _mm(r["van"])]
    medidas = ["relative"] * 7 + ["total"]
    fig = go.Figure(go.Waterfall(
        orientation="v", measure=medidas, x=etiquetas, y=valores,
        text=[f"{v:+.1f}" for v in valores[:-1]] + [f"{valores[-1]:.1f}"],
        textposition="outside",
        connector=dict(line=dict(color=GRIS, width=1)),
        increasing=dict(marker=dict(color=AHORRO)),
        decreasing=dict(marker=dict(color=ROJO)),
        totals=dict(marker=dict(color=VERDE_OSC)),
    ))
    _layout(fig, "¿De dónde nace el valor de cambiarse? — VAN descompuesto",
            alto=470, leg=False, b=84, hover="x")
    fig.update_yaxes(title="Millones CLP (valor presente)")
    fig.update_xaxes(tickangle=-20)
    return fig


# ── 3. Flujo de caja incremental (anual + acumulado) ─────────────────────────
def fig_cashflow(r):
    s = r["supuestos"]
    n = s.horizonte_anios
    flujo = r["flujo_incremental"]
    anios = list(range(0, n + 1))
    acum, c = [], 0.0
    for f in flujo:
        c += f
        acum.append(_mm(c))
    colores = [ROJO] + [AHORRO] * n
    fig = go.Figure()
    fig.add_trace(go.Bar(x=anios, y=[_mm(f) for f in flujo], name="Flujo del año",
                         marker_color=colores, opacity=0.85))
    fig.add_trace(go.Scatter(x=anios, y=acum, name="Flujo acumulado", mode="lines+markers",
                             line=dict(color=VERDE_OSC, width=3), yaxis="y"))
    fig.add_hline(y=0, line=dict(color=GRIS, width=1))
    _layout(fig, "Flujo de caja incremental del cambio (diésel → eléctrico)", b=90, leg_y=-0.22)
    fig.update_yaxes(title="Millones CLP")
    fig.update_xaxes(title="Año", dtick=1)
    return fig


# ── 4. Composición del TCO (stacked, EV vs diésel) ───────────────────────────
def fig_composicion_tco(r):
    s = r["supuestos"]
    td = s.tasa_descuento
    n = s.horizonte_anios

    def vp(serie):  # valor presente de una serie año 1..N
        return vpn(td, [0.0] + list(serie))

    d, e = r["escenario_diesel"], r["escenario_ev"]
    nd, ne = d["n_vehiculos"], e["n_vehiculos"]  # el OPEX desglosado es POR VEHÍCULO → ×flota

    def vpf(esc, comps, nfl):  # valor presente de la suma de partidas OPEX, escalado a la flota
        return vp([sum(esc["opex_desglose"][c][t] for c in comps) * nfl for t in range(n)])

    comp = {
        "CAPEX vehículos": (_mm(d["capex_vehiculos"]), _mm(e["capex_vehiculos"])),
        "Infraestructura carga": (0.0, _mm(e["capex_infra"])),
        "Energía / combustible": (_mm(vpf(d, ["energia"], nd)), _mm(vpf(e, ["energia"], ne))),
        "Mantención": (_mm(vpf(d, ["mantencion"], nd)), _mm(vpf(e, ["mantencion"], ne))),
        "Neumáticos+seguro+permiso+AdBlue": (
            _mm(vpf(d, ["neumaticos", "seguro", "permiso", "adblue"], nd)),
            _mm(vpf(e, ["neumaticos", "seguro", "permiso", "adblue"], ne))),
        "Escudo tributario (−)": (-_mm(vp(d["escudo"])), -_mm(vp(e["escudo"]))),
        "Valor residual (−)": (-_mm(d["residual_neto"] / (1 + td) ** n), -_mm(e["residual_neto"] / (1 + td) ** n)),
    }
    # paleta tonal: costos en gama tierra/neutra, reductores (escudo/residual) en verde
    paleta = ["#6B5B4F", "#9C8B7A", AMBAR, AZUL, "#B7BEC4", VERDE_CLARO, VERDE_OSC]
    fig = go.Figure()
    for i, (k, (vd, ve)) in enumerate(comp.items()):
        fig.add_trace(go.Bar(name=k, x=["Flota diésel", "Flota eléctrica"], y=[vd, ve],
                             marker_color=paleta[i % len(paleta)],
                             marker_line=dict(width=0)))
    fig.update_layout(barmode="relative", bargap=0.45)
    _layout(fig, f"Composición del TCO · valor presente a {n} años", alto=520, b=132, leg_y=-0.10)
    fig.update_yaxes(title="Millones CLP (VP)")
    return fig


# ── 5. Costo por kilómetro (energía/combustible) ─────────────────────────────
def fig_costo_km(r):
    fig = go.Figure(go.Bar(
        x=["Diésel", "Eléctrico (e-auto)"],
        y=[r["costo_km_diesel"], r["costo_km_ev"]],
        marker_color=[DIESEL, VERDE], width=[0.46, 0.46],
        text=[f"${r['costo_km_diesel']:.0f}/km", f"${r['costo_km_ev']:.0f}/km"],
        textposition="outside", textfont=dict(size=14, color=TINTA), cliponaxis=False,
    ))
    _layout(fig, "Costo de energía por kilómetro", alto=360, leg=False, b=48, hover=False)
    fig.update_yaxes(title="CLP / km")
    return fig


# ── 6. Logística: equivalencia de flota y choferes ───────────────────────────
def fig_logistica(r):
    log = r["logistica"]
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Vehículos", x=["Flota diésel actual", "Flota eléctrica equivalente"],
                         y=[r["n_diesel"], r["n_ev"]], marker_color=[DIESEL, VERDE],
                         text=[r["n_diesel"], r["n_ev"]], textposition="outside",
                         textfont=dict(size=15, color=TINTA), cliponaxis=False, width=[0.46, 0.46]))
    _layout(fig, "Equivalencia de flota por capacidad de transporte", alto=380,
            leg=False, b=48, hover=False)
    fig.update_yaxes(title="N° de vehículos")
    return fig


# ── 7. Depreciación: VPN del escudo tributario por régimen ───────────────────
def fig_depreciacion(r):
    reg = r["tributario"]["regimenes"]
    nombres = {"lineal": "Lineal (7 años)", "acelerada": "Acelerada (1/3)", "instantanea": "Instantánea (año 1)"}
    fig = go.Figure(go.Bar(
        x=[nombres[k] for k in ("lineal", "acelerada", "instantanea")],
        y=[_mm(reg[k]["vpn_escudo"]) for k in ("lineal", "acelerada", "instantanea")],
        marker_color=[GRIS, AMBAR, VERDE],
        text=[f"${_mm(reg[k]['vpn_escudo']):.1f}M" for k in ("lineal", "acelerada", "instantanea")],
        textposition="outside", textfont=dict(size=14, color=TINTA), cliponaxis=False, width=0.55,
    ))
    _layout(fig, "Valor presente del escudo tributario por régimen de depreciación",
            alto=400, leg=False, b=52, hover=False)
    fig.update_yaxes(title="Millones CLP (VP del ahorro de impuestos)")
    return fig


# ── 8. Tornado de sensibilidad (VAN ±20%) ────────────────────────────────────
def fig_tornado(filas, base, delta_pct=20):
    """Tornado autoexplicativo. Una fila por variable, ordenadas de MAYOR a menor
    INFLUENCIA (la más decisiva arriba). Cada etiqueta lleva, en una 2ª línea gris,
    la DIRECCIÓN en palabras ('mejora al subir' / 'mejora al bajar' — sin flechas
    ambiguas) y la MAGNITUD del swing. Dos barras por variable: verde = sube el VAN,
    rojo = lo baja."""
    fig = go.Figure()
    for f in filas:
        direc = "subir" if f["sentido"] == "directa" else "bajar"
        f["_et"] = (f"{f['palanca']}<br>"
                    f"<span style='font-size:11px;color:#9AA3AD'>"
                    f"mejora al {direc} · ±{delta_pct}% mueve {_mm(f['swing']):.0f}M</span>")

    leyenda = set()
    for f in filas:
        for clave, lblk in (("van_bajo", "lbl_bajo"), ("van_alto", "lbl_alto")):
            d = _mm(f[clave] - base)
            sube = d >= 0
            nombre = "Sube el VAN" if sube else "Baja el VAN"
            fig.add_trace(go.Bar(
                y=[f["_et"]], x=[d], orientation="h", base=0,
                marker_color=(AHORRO if sube else ROJO), name=nombre,
                legendgroup=nombre, showlegend=nombre not in leyenda,
                hovertemplate=(f"<b>{f['palanca']}</b><br>{f[lblk]}"
                               f"  ⇒  Δ VAN %{{x:+.1f}} M<extra></extra>")))
            leyenda.add(nombre)

    fig.add_vline(x=0, line=dict(color=VERDE_OSC, width=1.5))
    fig.add_annotation(x=0, y=1.045, yref="paper", xanchor="center", showarrow=False,
                       text="VAN del caso base", font=dict(size=10.5, color=VERDE_OSC))
    # Sin leyenda: el eje X es la clave de color (rojo = lado «baja», verde = lado «sube»).
    _layout(fig, "Sensibilidad del VAN · variables ordenadas de MAYOR a menor influencia",
            alto=470, leg=False, b=50, hover="closest")
    fig.update_yaxes(categoryorder="array", categoryarray=[f["_et"] for f in filas][::-1],
                     tickfont=dict(size=12.5))
    fig.update_xaxes(title="Δ VAN vs caso base (millones CLP)   ·   ◀ rojo: baja   |   verde: sube ▶")
    fig.update_layout(barmode="overlay", margin=dict(l=202, r=40))
    return fig


# ── 9. Heatmap 2D de sensibilidad ────────────────────────────────────────────
def fig_heatmap(Z, valores_x, valores_y, label_x, label_y, label_z="VAN (M)"):
    Zmm = [[(v / 1e6 if v == v else None) for v in fila] for fila in Z]
    fig = go.Figure(go.Heatmap(
        z=Zmm, x=valores_x, y=valores_y, colorscale="RdYlGn", zmid=0,
        colorbar=dict(title=label_z),
        text=[[f"{v:.0f}" if v == v else "" for v in fila] for fila in Zmm],
        texttemplate="%{text}", hovertemplate=f"{label_x}: %{{x}}<br>{label_y}: %{{y}}<br>{label_z}: %{{z:.1f}}<extra></extra>",
    ))
    _layout(fig, f"Mapa de sensibilidad · {label_x} × {label_y} → {label_z}",
            alto=460, leg=False, b=60, hover="closest")
    fig.update_xaxes(title=label_x, ticks="")
    fig.update_yaxes(title=label_y, showgrid=False)
    fig.update_traces(xgap=2, ygap=2)
    return fig


# ── 10. CO₂ evitado ──────────────────────────────────────────────────────────
def fig_co2(r):
    fig = go.Figure(go.Bar(
        x=["Flota diésel", "Flota eléctrica"],
        y=[r["co2_diesel_anio"], r["co2_ev_anio"]],
        marker_color=[DIESEL, VERDE], width=[0.46, 0.46],
        text=[f"{r['co2_diesel_anio']:.1f} t", f"{r['co2_ev_anio']:.1f} t"],
        textposition="outside", textfont=dict(size=14, color=TINTA), cliponaxis=False,
    ))
    _layout(fig, "Emisiones de CO₂ anuales de la flota", alto=360, leg=False, b=48, hover=False)
    fig.update_yaxes(title="Toneladas CO₂ / año")
    return fig


# ── 11. Medidores (gauges) de los KPI principales ────────────────────────────
def fig_gauge_payback(pb, horizonte):
    val = pb if pb is not None else horizonte * 1.5
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=val,
        number=dict(suffix=" años", font=dict(size=36, color=TINTA, family=FONT["family"])),
        title=dict(text="Payback", font=dict(size=15, color=MUTED, family=FONT["family"])),
        gauge=dict(axis=dict(range=[0, horizonte], tickwidth=1, tickcolor=LINEA,
                             tickfont=dict(color=MUTED, size=11)),
                   bar=dict(color=VERDE, thickness=0.32),
                   bgcolor="white", borderwidth=0,
                   steps=[dict(range=[0, horizonte * 0.4], color="#E3F4EA"),
                          dict(range=[horizonte * 0.4, horizonte * 0.7], color="#F6EEDB"),
                          dict(range=[horizonte * 0.7, horizonte], color="#F3E0DD")]),
    ))
    fig.update_layout(height=260, margin=dict(l=24, r=24, t=56, b=12),
                      paper_bgcolor="white", font=FONT)
    return fig


# ── 12. Capacidad equivalente: pictograma sinóptico de flota ─────────────────
def fig_pictograma_capacidad(eq, por_fila=10):
    """Dos bandas de furgones: arriba la flota diésel; abajo la flota EV equivalente
    (con las unidades liberadas en fantasma). Lectura sinóptica de '≡ menos unidades'."""
    nd, nev = eq["n_diesel"], eq["n_ev"]
    liberados = max(0, nd - nev)
    filas = max(1, -(-nd // por_fila))            # ceil(nd/por_fila) sin import
    sep = 1.7

    def banda(n, y_techo):
        xs = [i % por_fila for i in range(n)]
        ys = [y_techo - (i // por_fila) for i in range(n)]
        return xs, ys

    y0_diesel = 2 * filas - 1 + sep
    y0_ev = filas - 1
    dx, dy = banda(nd, y0_diesel)
    allx, ally = banda(nd, y0_ev)
    ev_x, ev_y = allx[:nev], ally[:nev]
    lib_x, lib_y = allx[nev:], ally[nev:]

    fig = go.Figure()
    # fondos de banda (color-codificados)
    fig.add_shape(type="rect", x0=-0.65, x1=por_fila - 0.35, y0=y0_diesel - filas + 0.45,
                  y1=y0_diesel + 0.55, fillcolor="rgba(156,139,122,0.10)", line=dict(width=0), layer="below")
    fig.add_shape(type="rect", x0=-0.65, x1=por_fila - 0.35, y0=y0_ev - filas + 0.45,
                  y1=y0_ev + 0.55, fillcolor="rgba(0,166,81,0.09)", line=dict(width=0), layer="below")
    # furgones
    fig.add_trace(go.Scatter(x=dx, y=dy, mode="text", text=["🚐"] * nd,
                             textfont=dict(size=27), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=ev_x, y=ev_y, mode="text", text=["🚐"] * nev,
                             textfont=dict(size=27), hoverinfo="skip", showlegend=False))
    if liberados:
        fig.add_trace(go.Scatter(x=lib_x, y=lib_y, mode="text", text=["🚐"] * liberados,
                                 textfont=dict(size=27), opacity=0.20, hoverinfo="skip", showlegend=False))
    # etiquetas de banda
    fig.add_annotation(x=-0.6, y=y0_diesel + 1.05, xanchor="left", showarrow=False,
        text=(f"<b>FLOTA DIÉSEL</b> · {nd} unidades · {eq['vol_total_d']:.0f} m³ · "
              f"{eq['peso_total_d']:,.0f} kg").replace(",", "."), font=dict(size=13, color=DIESEL))
    fig.add_annotation(x=-0.6, y=y0_ev + 1.05, xanchor="left", showarrow=False,
        text=(f"<b>FLOTA EV EQUIVALENTE</b> · {nev} unidades  "
              f"(−{liberados}, misma capacidad)"), font=dict(size=13, color=VERDE_OSC))
    if liberados:
        fig.add_annotation(x=(por_fila - 0.35), y=(y0_ev - filas + 0.5), xanchor="right", yanchor="bottom",
            showarrow=False, text=f"🚐 ×{liberados} liberados", font=dict(size=11.5, color=MUTED))

    fig.update_xaxes(visible=False, range=[-0.75, por_fila - 0.25])
    fig.update_yaxes(visible=False, range=[y0_ev - filas + 0.1, y0_diesel + 1.7])
    fig.update_layout(template=PLANTILLA, font=FONT,
                      height=int(150 + 2 * filas * 46 + sep * 26),
                      margin=dict(l=12, r=12, t=12, b=12),
                      plot_bgcolor="white", paper_bgcolor="white")
    return fig


# ── 13. Capacidad total de la flota (modo B: mismas unidades, más capacidad) ──
def fig_capacidad_total(eq, dim):
    if dim == "volumen":
        d, e, pct = eq["vol_total_d"], eq["vol_total_ev"], eq["amp_vol_pct"]
        uni, titulo = "m³", "Volumen total de carga"
        fmt = lambda v: f"{v:,.0f} m³".replace(",", ".")
    else:
        d, e, pct = eq["peso_total_d"], eq["peso_total_ev"], eq["amp_peso_pct"]
        uni, titulo = "kg", "Carga útil total"
        fmt = lambda v: f"{v:,.0f} kg".replace(",", ".")
    fig = go.Figure(go.Bar(
        x=["Flota diésel", f"Flota EV · {eq['n_diesel']} u."], y=[d, e],
        marker_color=[DIESEL, VERDE], width=[0.5, 0.5],
        text=[fmt(d), fmt(e)], textposition="outside", cliponaxis=False))
    fig.add_annotation(x=1, y=e, yshift=30, showarrow=False,
        text=f"<b>+{pct * 100:.0f}%</b>", font=dict(size=16, color=VERDE_OSC))
    _layout(fig, f"{titulo} · mismas {eq['n_diesel']} unidades", alto=330, leg=False, hover=False)
    fig.update_yaxes(title=uni, range=[0, e * 1.22])
    return fig
