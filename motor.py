# -*- coding: utf-8 -*-
"""
motor.py — Motor de modelación de reemplazo de flota diésel → eléctrica (E-AUTO).

Núcleo de cálculo SIN interfaz (para poder testearlo de forma aislada).
Implementa el modelo estándar de TCO (Total Cost of Ownership) ampliado con:

  • OPEX desglosado y escalado en el tiempo (energía/combustible, mantención,
    neumáticos, seguro, permiso de circulación, AdBlue).
  • Indicadores de inversión sobre el sobrecosto incremental: VAN, TIR, payback.
  • Capa LOGÍSTICA: equivalencia de capacidad (peso / volumen / autonomía) que
    determina cuántos vehículos eléctricos reemplazan a la flota diésel y, por lo
    tanto, cuántos CHOFERES se reducen (la palanca de mayor valor en última milla).
  • Capa TRIBUTARIA: escudo fiscal de la depreciación bajo tres regímenes
    (lineal / acelerada 1/3 / instantánea 100% año 1) y decisión de si conviene.
  • Externalidades: toneladas de CO₂ evitadas.

Caso base = Entregable 7 del «Estudio de Mercado EV Comerciales Chile» (jun-2026),
validado por el directorio de E-Auto. Los valores por defecto reproducen ese caso:
payback ~2,6 años · TIR ~33% · VAN +$7,0M/unidad · TCO 7 años −27% vs diésel.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional
import math

# ───────────────────────────────────────────────────────────────────────────
#  Constantes de referencia (Chile, jun-2026)
# ───────────────────────────────────────────────────────────────────────────
CO2_KG_POR_LITRO_DIESEL = 2.68      # factor de emisión combustión diésel (kg CO₂/L)
CO2_KG_POR_KWH_SEN = 0.30           # intensidad media red eléctrica chilena (SEN), kg CO₂/kWh

# ───────────────────────────────────────────────────────────────────────────
#  Fichas de producto e-auto (presets) — fuente: cotizador/productos.md
# ───────────────────────────────────────────────────────────────────────────
PRESETS_EV = {
    "Gecko EV48 (cargo van)": dict(
        precio_ev_clp=29_750_000,      # IVA incluido (precio de lista)
        eficiencia_km_kwh=6.2,         # certificada 3CV Chile
        bateria_kwh=41.86,
        autonomia_km=305,              # CLTC
        carga_util_ev_kg=1_440,
        volumen_ev_m3=6.2,
    ),
    "Gecko MagicWay (L1H2)": dict(
        precio_ev_clp=49_990_000,
        eficiencia_km_kwh=3.6,         # 276 Wh/km ≈ 3,62 km/kWh (WLTP)
        bateria_kwh=70.19,
        autonomia_km=353,              # CHTC-LT
        carga_util_ev_kg=1_765,
        volumen_ev_m3=8.1,
    ),
    "Personalizado": dict(
        precio_ev_clp=29_750_000, eficiencia_km_kwh=6.2, bateria_kwh=41.86,
        autonomia_km=305, carga_util_ev_kg=1_440, volumen_ev_m3=6.2,
    ),
}

# Perfiles diésel típicos a reemplazar (puntos de partida; el usuario ajusta)
PRESETS_DIESEL = {
    "Furgón compacto reparto (~1,0 t)": dict(
        precio_diesel_clp=22_000_000, rendimiento_km_l=11.0,
        carga_util_diesel_kg=1_000, volumen_diesel_m3=5.0, mantencion_diesel_anual=1_200_000),
    "Furgón mediano (~1,5 t)": dict(
        precio_diesel_clp=28_000_000, rendimiento_km_l=9.5,
        carga_util_diesel_kg=1_500, volumen_diesel_m3=8.0, mantencion_diesel_anual=1_500_000),
    "Van pasajeros / transfer (HiAce-class)": dict(
        precio_diesel_clp=33_000_000, rendimiento_km_l=10.0,
        carga_util_diesel_kg=1_200, volumen_diesel_m3=6.0, mantencion_diesel_anual=1_400_000),
    "Personalizado": dict(
        precio_diesel_clp=22_000_000, rendimiento_km_l=11.0,
        carga_util_diesel_kg=1_000, volumen_diesel_m3=5.0, mantencion_diesel_anual=1_200_000),
}


# ───────────────────────────────────────────────────────────────────────────
#  Supuestos (todos los inputs del modelo). Defaults = caso base del estudio.
# ───────────────────────────────────────────────────────────────────────────
@dataclass
class Supuestos:
    # — Flota y operación —
    num_vehiculos_diesel: int = 10          # tamaño de la flota diésel a evaluar
    km_anual_por_vehiculo: float = 30_000   # base estudio
    horizonte_anios: int = 7
    tasa_descuento: float = 0.10            # costo de capital para VAN
    escalamiento_diesel: float = 0.04       # alza anual nominal precio diésel
    escalamiento_energia: float = 0.03      # alza anual nominal precio electricidad
    escalamiento_costos: float = 0.03       # alza anual mantención/seguros/sueldos

    # — Vehículo DIÉSEL a reemplazar —
    precio_diesel_clp: float = 22_000_000
    rendimiento_km_l: float = 11.0          # km por litro
    precio_diesel_l: float = 1_050          # CLP/L
    mantencion_diesel_anual: float = 1_200_000
    neumaticos_diesel_anual: float = 350_000
    seguro_diesel_anual: float = 600_000
    permiso_circulacion_diesel: float = 280_000
    adblue_anual: float = 120_000           # urea SCR diésel moderno
    carga_util_diesel_kg: float = 1_000
    volumen_diesel_m3: float = 5.0
    valor_residual_diesel_pct: float = 0.20  # % del precio al final del horizonte

    # — Vehículo ELÉCTRICO (Gecko EV48 por defecto) —
    precio_ev_clp: float = 29_750_000       # IVA incluido (precio de lista)
    eficiencia_km_kwh: float = 6.2          # certificada 3CV
    precio_energia_kwh: float = 130         # CLP/kWh comercial
    perdidas_carga_pct: float = 0.10        # pérdidas AC/DC al cargar
    mantencion_ev_anual: float = 400_000
    neumaticos_ev_anual: float = 350_000
    seguro_ev_anual: float = 650_000
    permiso_circulacion_ev: float = 210_000  # menor (beneficio EV)
    carga_util_ev_kg: float = 1_440
    volumen_ev_m3: float = 6.2
    autonomia_km: float = 305
    autonomia_utilizable_pct: float = 0.85   # SoC útil real en operación
    valor_residual_ev_pct: float = 0.15      # conservador (mercado secundario incipiente)

    # — Infraestructura de carga (CAPEX extra del EV) —
    costo_cargador_clp: float = 900_000     # wallbox AC instalado por punto
    vehiculos_por_cargador: float = 1.0
    costo_instalacion_electrica: float = 0  # obra eléctrica única (tablero, empalme)

    # — Choferes y equivalencia logística —
    costo_anual_chofer: float = 11_000_000  # sueldo + leyes sociales
    aplicar_equivalencia_capacidad: bool = False  # si True, el EV reduce la flota
    utilizacion_peso_pct: float = 0.80      # cuán llenos van los diésel (peso)
    utilizacion_volumen_pct: float = 0.85   # cuán llenos van los diésel (volumen)
    incluir_ahorro_choferes: bool = True

    # — Tributario —
    tasa_impuesto: float = 0.27             # Primera Categoría (régimen general)
    vida_util_normal: int = 7               # SII vehículos de transporte
    regimen_depreciacion: str = "instantanea"  # lineal | acelerada | instantanea
    empresa_con_utilidades: bool = True     # ¿hay base imponible que absorba la rebaja?
    aplicar_efecto_tributario: bool = True  # mostrar flujos después de impuestos

    # — IVA (tratamiento IDÉNTICO para diésel y eléctrico: ambos son vehículos
    #   comerciales y permiten recuperar el IVA como crédito fiscal si la empresa
    #   es contribuyente de IVA). Los precios de compra se ingresan IVA INCLUIDO. —
    iva_pct: float = 0.19                   # tasa de IVA Chile
    iva_recuperable: bool = True            # crédito fiscal → CAPEX neto de IVA (ambos)


# ───────────────────────────────────────────────────────────────────────────
#  Utilidades financieras
# ───────────────────────────────────────────────────────────────────────────
def vpn(tasa: float, flujos: list[float]) -> float:
    """Valor presente neto. flujos[0] = año 0 (no se descuenta)."""
    return sum(f / (1 + tasa) ** t for t, f in enumerate(flujos))


def tir(flujos: list[float]) -> Optional[float]:
    """TIR por bisección. Devuelve None si no hay cambio de signo / no converge."""
    if all(f >= 0 for f in flujos) or all(f <= 0 for f in flujos):
        return None
    lo, hi = -0.95, 10.0
    f_lo, f_hi = vpn(lo, flujos), vpn(hi, flujos)
    if f_lo * f_hi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = vpn(mid, flujos)
        if abs(f_mid) < 1e-3:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def payback(flujos: list[float]) -> Optional[float]:
    """Payback (años) con interpolación lineal sobre el acumulado. flujos[0] = inversión (neg).
    Si no hay inversión neta inicial (flujos[0] >= 0), el retorno es inmediato → 0."""
    if flujos[0] >= 0:
        return 0.0
    acum = flujos[0]
    for t in range(1, len(flujos)):
        nuevo = acum + flujos[t]
        if acum < 0 <= nuevo:
            frac = -acum / (nuevo - acum) if (nuevo - acum) != 0 else 0
            return (t - 1) + frac
        acum = nuevo
    return None  # no se recupera dentro del horizonte


def _serie(valor_base: float, escal: float, n: int) -> list[float]:
    """Serie de n años con escalamiento compuesto (año 1 = valor_base)."""
    return [valor_base * (1 + escal) ** t for t in range(n)]


# ───────────────────────────────────────────────────────────────────────────
#  Depreciación (Chile)
# ───────────────────────────────────────────────────────────────────────────
def plan_depreciacion(capex: float, vida_normal: int, regimen: str, horizonte: int) -> list[float]:
    """
    Devuelve la depreciación de cada año [1..horizonte].

      • lineal      : capex / vida_normal cada año (régimen general SII).
      • acelerada   : vida = max(1, vida_normal // 3) — Art. 31 N°5 LIR para bienes
                      nuevos con vida útil ≥ 3 años (1/3 de la vida normal).
      • instantanea : 100% del capex deducido en el año 1 (regímenes transitorios /
                      Pyme; SII Res. Ex. 56/2021 citada en el GTM, ventana a 2031).
    """
    dep = [0.0] * horizonte
    if regimen == "instantanea":
        dep[0] = capex
    else:
        vida = vida_normal if regimen == "lineal" else max(1, vida_normal // 3)
        cuota = capex / vida
        for t in range(min(vida, horizonte)):
            dep[t] = cuota
        # remanente si vida > horizonte: queda sin depreciar dentro de la ventana
    return dep


# ───────────────────────────────────────────────────────────────────────────
#  Costo de energía por km
# ───────────────────────────────────────────────────────────────────────────
def costo_energia_km_ev(s: Supuestos) -> float:
    return (1.0 / s.eficiencia_km_kwh) * s.precio_energia_kwh * (1 + s.perdidas_carga_pct)


def costo_combustible_km_diesel(s: Supuestos) -> float:
    return (1.0 / s.rendimiento_km_l) * s.precio_diesel_l


# ───────────────────────────────────────────────────────────────────────────
#  Logística: equivalencia de capacidad → vehículos y choferes
# ───────────────────────────────────────────────────────────────────────────
def evaluar_logistica(s: Supuestos) -> dict:
    """
    Determina cuántos EV se necesitan para igualar la capacidad de transporte de la
    flota diésel, y cuántos choferes se reducen.

    Demanda diaria a cubrir (la que hoy mueve la flota diésel, a su nivel de uso):
        peso_dia   = N_diesel · carga_util_diesel · util_peso
        volumen_dia= N_diesel · volumen_diesel    · util_volumen
        km_dia     = N_diesel · km_dia_por_vehiculo

    Vehículos EV requeridos = techo del binding entre las tres restricciones:
        por peso     = peso_dia    / carga_util_ev
        por volumen  = volumen_dia / volumen_ev
        por autonomía= km_dia      / (autonomia · util_autonomia)   [1 carga/día]
    """
    dias = 1  # razonamos por "día tipo"; las tres restricciones escalan igual
    peso_dia = s.num_vehiculos_diesel * s.carga_util_diesel_kg * s.utilizacion_peso_pct
    vol_dia = s.num_vehiculos_diesel * s.volumen_diesel_m3 * s.utilizacion_volumen_pct
    km_dia_veh = s.km_anual_por_vehiculo / 260.0  # ~260 días hábiles
    km_dia_flota = s.num_vehiculos_diesel * km_dia_veh

    req_peso = peso_dia / s.carga_util_ev_kg
    req_vol = vol_dia / s.volumen_ev_m3
    autonomia_util = s.autonomia_km * s.autonomia_utilizable_pct
    req_autonomia = km_dia_flota / autonomia_util if autonomia_util > 0 else math.inf

    binding_val = max(req_peso, req_vol, req_autonomia)
    binding = max(
        [("peso", req_peso), ("volumen", req_vol), ("autonomía", req_autonomia)],
        key=lambda x: x[1],
    )[0]
    n_ev = max(1, math.ceil(binding_val))

    if s.aplicar_equivalencia_capacidad:
        n_ev_final = min(n_ev, s.num_vehiculos_diesel)  # nunca más que la flota base
    else:
        n_ev_final = s.num_vehiculos_diesel  # reemplazo 1:1

    reduccion_vehiculos = s.num_vehiculos_diesel - n_ev_final
    reduccion_choferes = reduccion_vehiculos  # 1 chofer por vehículo

    return dict(
        peso_dia_kg=peso_dia, volumen_dia_m3=vol_dia, km_dia_flota=km_dia_flota,
        req_peso=req_peso, req_volumen=req_vol, req_autonomia=req_autonomia,
        restriccion_binding=binding, n_ev_equivalente=n_ev,
        n_ev_final=n_ev_final, reduccion_vehiculos=reduccion_vehiculos,
        reduccion_choferes=reduccion_choferes,
    )


# ───────────────────────────────────────────────────────────────────────────
#  Capacidad equivalente (calculadora dedicada, a capacidad NOMINAL)
# ───────────────────────────────────────────────────────────────────────────
def equivalencia_capacidad(n_diesel: int, vol_diesel: float, peso_diesel: float,
                           vol_ev: float, peso_ev: float) -> dict:
    """
    Equivalencia de capacidad de transporte diésel → EV, en sus DOS lecturas, a
    capacidad NOMINAL (vehículo lleno), sin utilización ni autonomía:

      (A) MISMA capacidad total → MENOS unidades.
          EV necesarios por dimensión = capacidad total diésel / capacidad por EV.
          La dimensión que exige MÁS unidades manda (binding). Se redondea hacia
          arriba (no se compran fracciones de vehículo).
      (B) MISMAS unidades → MÁS capacidad.
          Con el mismo N° de vehículos, la flota EV transporta más peso y volumen.
          La ampliación por unidad es independiente del N°: depende solo del ratio.

    Ej. 10 furgones (5 m³ · 1.000 kg) vs EV48 (6,7 m³ · 1.440 kg):
        (A) 50 m³ / 6,7 = 7,46 → 8 EV (binding volumen) ⇒ −2 unidades (−20%).
        (B) 10 EV ⇒ 67 m³ (+34%) y 14.400 kg (+44%).
    """
    n_diesel = int(n_diesel)
    vol_total_d = n_diesel * vol_diesel
    peso_total_d = n_diesel * peso_diesel

    # (A) Unidades EV para igualar (exacto y redondeado hacia arriba)
    ev_vol_exacto = vol_total_d / vol_ev if vol_ev else float("inf")
    ev_peso_exacto = peso_total_d / peso_ev if peso_ev else float("inf")
    ev_vol = math.ceil(ev_vol_exacto - 1e-9)
    ev_peso = math.ceil(ev_peso_exacto - 1e-9)
    if ev_vol_exacto >= ev_peso_exacto:
        binding, ev_binding_exacto, n_ev = "volumen", ev_vol_exacto, ev_vol
    else:
        binding, ev_binding_exacto, n_ev = "peso", ev_peso_exacto, ev_peso
    n_ev = max(1, n_ev)
    reduccion_u = n_diesel - n_ev
    reduccion_pct = reduccion_u / n_diesel if n_diesel else 0.0

    # (B) Mantener n_diesel unidades EV → capacidad ampliada
    vol_total_ev = n_diesel * vol_ev
    peso_total_ev = n_diesel * peso_ev
    amp_vol_abs = vol_total_ev - vol_total_d
    amp_peso_abs = peso_total_ev - peso_total_d
    amp_vol_pct = (vol_ev / vol_diesel - 1.0) if vol_diesel else 0.0
    amp_peso_pct = (peso_ev / peso_diesel - 1.0) if peso_diesel else 0.0

    return dict(
        n_diesel=n_diesel, vol_diesel=vol_diesel, peso_diesel=peso_diesel,
        vol_ev=vol_ev, peso_ev=peso_ev,
        vol_total_d=vol_total_d, peso_total_d=peso_total_d,
        vol_total_ev=vol_total_ev, peso_total_ev=peso_total_ev,
        ev_vol_exacto=ev_vol_exacto, ev_peso_exacto=ev_peso_exacto,
        ev_vol=ev_vol, ev_peso=ev_peso,
        binding=binding, ev_binding_exacto=ev_binding_exacto, n_ev=n_ev,
        reduccion_u=reduccion_u, reduccion_pct=reduccion_pct,
        amp_vol_abs=amp_vol_abs, amp_peso_abs=amp_peso_abs,
        amp_vol_pct=amp_vol_pct, amp_peso_pct=amp_peso_pct,
        ratio_vol=(vol_ev / vol_diesel) if vol_diesel else 0.0,
        ratio_peso=(peso_ev / peso_diesel) if peso_diesel else 0.0,
    )


# ───────────────────────────────────────────────────────────────────────────
#  OPEX anual por vehículo (escalado)
# ───────────────────────────────────────────────────────────────────────────
def opex_por_vehiculo(s: Supuestos, tipo: str) -> dict:
    """Devuelve series anuales [1..N] del OPEX desglosado de UN vehículo."""
    n = s.horizonte_anios
    km = s.km_anual_por_vehiculo
    if tipo == "ev":
        energia = _serie(costo_energia_km_ev(s) * km, s.escalamiento_energia, n)
        mant = _serie(s.mantencion_ev_anual, s.escalamiento_costos, n)
        neum = _serie(s.neumaticos_ev_anual, s.escalamiento_costos, n)
        seg = _serie(s.seguro_ev_anual, s.escalamiento_costos, n)
        perm = _serie(s.permiso_circulacion_ev, s.escalamiento_costos, n)
        adblue = [0.0] * n
    else:
        energia = _serie(costo_combustible_km_diesel(s) * km, s.escalamiento_diesel, n)
        mant = _serie(s.mantencion_diesel_anual, s.escalamiento_costos, n)
        neum = _serie(s.neumaticos_diesel_anual, s.escalamiento_costos, n)
        seg = _serie(s.seguro_diesel_anual, s.escalamiento_costos, n)
        perm = _serie(s.permiso_circulacion_diesel, s.escalamiento_costos, n)
        adblue = _serie(s.adblue_anual, s.escalamiento_diesel, n)
    total = [energia[t] + mant[t] + neum[t] + seg[t] + perm[t] + adblue[t] for t in range(n)]
    return dict(energia=energia, mantencion=mant, neumaticos=neum, seguro=seg,
                permiso=perm, adblue=adblue, total=total)


# ───────────────────────────────────────────────────────────────────────────
#  Evaluación de un escenario (flota completa) → flujos y TCO
# ───────────────────────────────────────────────────────────────────────────
def evaluar_escenario(s: Supuestos, tipo: str, n_vehiculos: int) -> dict:
    n = s.horizonte_anios
    precio = s.precio_ev_clp if tipo == "ev" else s.precio_diesel_clp
    residual_pct = s.valor_residual_ev_pct if tipo == "ev" else s.valor_residual_diesel_pct

    # IVA: los precios se ingresan IVA INCLUIDO. Si la empresa recupera el IVA
    # (crédito fiscal, vehículo comercial), el CAPEX económico es NETO de IVA.
    # Se aplica EXACTAMENTE IGUAL a diésel y a eléctrico (y a la infraestructura).
    factor_iva = 1.0 / (1.0 + s.iva_pct) if s.iva_recuperable else 1.0

    # CAPEX (año 0), neto de IVA
    capex_vehiculos = precio * n_vehiculos * factor_iva
    if tipo == "ev":
        n_cargadores = math.ceil(n_vehiculos / max(1e-9, s.vehiculos_por_cargador))
        capex_infra = (n_cargadores * s.costo_cargador_clp + s.costo_instalacion_electrica) * factor_iva
    else:
        capex_infra = 0.0
    capex = capex_vehiculos + capex_infra

    # OPEX (años 1..N), escalado, × flota
    op = opex_por_vehiculo(s, tipo)
    opex_flota = [op["total"][t] * n_vehiculos for t in range(n)]

    # Depreciación y escudo tributario
    dep = plan_depreciacion(capex_vehiculos, s.vida_util_normal, s.regimen_depreciacion, n)
    aplica_trib = s.aplicar_efecto_tributario and s.empresa_con_utilidades
    # El gasto OPEX es deducible; el escudo = tasa × (OPEX + depreciación)
    escudo = [s.tasa_impuesto * (opex_flota[t] + dep[t]) if aplica_trib else 0.0 for t in range(n)]

    # Valor residual (año N), neto del impuesto a la utilidad sobre el residual
    residual = residual_pct * capex_vehiculos
    residual_neto = residual * (1 - s.tasa_impuesto) if aplica_trib else residual

    # Flujo de caja (negativo = egreso). Año 0 = -CAPEX.
    flujo = [-capex]
    for t in range(n):
        f = -opex_flota[t] + escudo[t]
        if t == n - 1:
            f += residual_neto
        flujo.append(f)

    # TCO = valor presente de los egresos netos (positivo = costo)
    tco_vpn = -vpn(s.tasa_descuento, flujo)
    tco_nominal = -sum(flujo)

    return dict(
        tipo=tipo, n_vehiculos=n_vehiculos, capex=capex, capex_vehiculos=capex_vehiculos,
        capex_infra=capex_infra, opex_flota=opex_flota, opex_desglose=op,
        depreciacion=dep, escudo=escudo, residual=residual, residual_neto=residual_neto,
        flujo=flujo, tco_vpn=tco_vpn, tco_nominal=tco_nominal,
    )


# ───────────────────────────────────────────────────────────────────────────
#  Decisión de depreciación: ¿conviene la instantánea/acelerada?
# ───────────────────────────────────────────────────────────────────────────
def analisis_depreciacion(s: Supuestos, capex_ev: float) -> dict:
    """Compara el VPN del escudo tributario de la depreciación del EV bajo cada régimen."""
    n, td, tasa = s.horizonte_anios, s.tasa_descuento, s.tasa_impuesto
    out = {}
    for reg in ("lineal", "acelerada", "instantanea"):
        dep = plan_depreciacion(capex_ev, s.vida_util_normal, reg, n)
        escudo = [tasa * d for d in dep]
        vpn_escudo = vpn(td, [0.0] + escudo)  # año 0 sin escudo
        out[reg] = dict(dep=dep, escudo=escudo, vpn_escudo=vpn_escudo)
    base = out["lineal"]["vpn_escudo"]
    ganancia_instant = out["instantanea"]["vpn_escudo"] - base
    conviene = s.empresa_con_utilidades and ganancia_instant > 0
    return dict(regimenes=out, ganancia_vpn_instantanea_vs_lineal=ganancia_instant,
                conviene_acelerar=conviene)


# ───────────────────────────────────────────────────────────────────────────
#  EVALUACIÓN COMPLETA
# ───────────────────────────────────────────────────────────────────────────
def evaluar(s: Supuestos) -> dict:
    n = s.horizonte_anios

    # 1) Logística → cuántos EV reemplazan a la flota
    log = evaluar_logistica(s)
    n_diesel = s.num_vehiculos_diesel
    n_ev = log["n_ev_final"]

    # 2) Escenarios de flota
    esc_diesel = evaluar_escenario(s, "diesel", n_diesel)
    esc_ev = evaluar_escenario(s, "ev", n_ev)

    # 3) Ahorro de choferes (flota EV puede operar con menos conductores)
    ahorro_choferes_anual = 0.0
    if s.incluir_ahorro_choferes and log["reduccion_choferes"] > 0:
        ahorro_choferes_anual = log["reduccion_choferes"] * s.costo_anual_chofer
        # El sueldo del chofer es gasto deducible: si la empresa tributa, el ahorro
        # neto es después de impuesto (consistente con los flujos de OPEX, que ya
        # incorporan el escudo). Sin tributación, el ahorro es íntegro.
        if s.aplicar_efecto_tributario and s.empresa_con_utilidades:
            ahorro_choferes_anual *= (1 - s.tasa_impuesto)
    serie_choferes = _serie(ahorro_choferes_anual, s.escalamiento_costos, n) if ahorro_choferes_anual else [0.0] * n

    # 4) Flujo INCREMENTAL (cambiarse a EV): diésel − EV, año a año
    #    Año 0: -(CAPEX_ev - CAPEX_diesel)  → el sobrecosto que se invierte
    inc_capex = esc_ev["capex"] - esc_diesel["capex"]
    flujo_inc = [-inc_capex]
    ahorro_opex_anual = []
    for t in range(n):
        # ahorro operativo = (egreso diésel) − (egreso EV)  [ambos ya con escudo y residual]
        ahorro = (-esc_diesel["flujo"][t + 1]) - (-esc_ev["flujo"][t + 1])
        ahorro += serie_choferes[t]  # + ahorro de choferes
        flujo_inc.append(ahorro)
        ahorro_opex_anual.append(ahorro)

    van = vpn(s.tasa_descuento, flujo_inc)
    tir_inc = tir(flujo_inc)
    pb = payback(flujo_inc)
    # payback simple (sin descuento) — comparable al titular del estudio
    pb_simple = payback([flujo_inc[0]] + ahorro_opex_anual)

    # 5) Análisis tributario (decisión acelerar)
    trib = analisis_depreciacion(s, esc_ev["capex_vehiculos"])

    # 6) Externalidades: CO₂
    litros_anio = (s.km_anual_por_vehiculo / s.rendimiento_km_l) * n_diesel
    kwh_anio = (s.km_anual_por_vehiculo / s.eficiencia_km_kwh) * (1 + s.perdidas_carga_pct) * n_ev
    co2_diesel_anio = litros_anio * CO2_KG_POR_LITRO_DIESEL / 1000.0   # toneladas
    co2_ev_anio = kwh_anio * CO2_KG_POR_KWH_SEN / 1000.0
    co2_evitado_anio = co2_diesel_anio - co2_ev_anio

    # 7) Ahorros desagregados (para waterfall), valor presente a lo largo del horizonte
    def vp_serie(serie):
        return vpn(s.tasa_descuento, [0.0] + list(serie))

    # Descomposición DESPUÉS de impuesto: los ahorros de OPEX se muestran netos del
    # impuesto (factor 1−tasa) y el escudo es SOLO el de la depreciación (positivo).
    # Así cada barra conserva su signo intuitivo y la suma sigue dando exactamente el VAN.
    aplica_trib = s.aplicar_efecto_tributario and s.empresa_con_utilidades
    factor_at = (1 - s.tasa_impuesto) if aplica_trib else 1.0

    ahorro_energia = vp_serie([
        ((esc_diesel["opex_desglose"]["energia"][t] * n_diesel) -
         (esc_ev["opex_desglose"]["energia"][t] * n_ev)) * factor_at for t in range(n)])
    ahorro_mant = vp_serie([
        ((esc_diesel["opex_desglose"]["mantencion"][t] * n_diesel) -
         (esc_ev["opex_desglose"]["mantencion"][t] * n_ev)) * factor_at for t in range(n)])
    ahorro_otros_opex = vp_serie([
        (((esc_diesel["opex_desglose"]["neumaticos"][t] + esc_diesel["opex_desglose"]["seguro"][t]
           + esc_diesel["opex_desglose"]["permiso"][t] + esc_diesel["opex_desglose"]["adblue"][t]) * n_diesel) -
         ((esc_ev["opex_desglose"]["neumaticos"][t] + esc_ev["opex_desglose"]["seguro"][t]
           + esc_ev["opex_desglose"]["permiso"][t]) * n_ev)) * factor_at for t in range(n)])
    ahorro_choferes_vp = vp_serie(serie_choferes)  # ya después de impuesto (ver arriba)
    # Escudo = SOLO depreciación incremental (el efecto fiscal del OPEX ya está en las barras de OPEX)
    escudo_dep_vp = vp_serie([s.tasa_impuesto * (esc_ev["depreciacion"][t] - esc_diesel["depreciacion"][t])
                              for t in range(n)]) if aplica_trib else 0.0
    residual_diff_vp = (esc_ev["residual_neto"] / (1 + s.tasa_descuento) ** n) - \
                       (esc_diesel["residual_neto"] / (1 + s.tasa_descuento) ** n)
    capex_extra_vp = -inc_capex  # negativo (egreso)

    return dict(
        supuestos=s,
        logistica=log,
        escenario_diesel=esc_diesel,
        escenario_ev=esc_ev,
        n_diesel=n_diesel, n_ev=n_ev,
        inc_capex=inc_capex,
        flujo_incremental=flujo_inc,
        ahorro_anual=ahorro_opex_anual,
        ahorro_choferes_anual=ahorro_choferes_anual,
        serie_choferes=serie_choferes,
        van=van, tir=tir_inc, payback=pb, payback_simple=pb_simple,
        tco_diesel=esc_diesel["tco_vpn"], tco_ev=esc_ev["tco_vpn"],
        tco_delta=esc_diesel["tco_vpn"] - esc_ev["tco_vpn"],
        tco_delta_pct=(esc_diesel["tco_vpn"] - esc_ev["tco_vpn"]) / esc_diesel["tco_vpn"] if esc_diesel["tco_vpn"] else 0,
        tributario=trib,
        co2_diesel_anio=co2_diesel_anio, co2_ev_anio=co2_ev_anio, co2_evitado_anio=co2_evitado_anio,
        co2_evitado_horizonte=co2_evitado_anio * n,
        waterfall=dict(
            energia=ahorro_energia, mantencion=ahorro_mant, otros_opex=ahorro_otros_opex,
            choferes=ahorro_choferes_vp, tributario=escudo_dep_vp, residual=residual_diff_vp,
            capex_extra=capex_extra_vp,
        ),
        # costo por km (titular comercial)
        costo_km_diesel=costo_combustible_km_diesel(s),
        costo_km_ev=costo_energia_km_ev(s),
    )


# ───────────────────────────────────────────────────────────────────────────
#  Sensibilidad
# ───────────────────────────────────────────────────────────────────────────
def sensibilidad_2d(s: Supuestos, var_x: str, valores_x, var_y: str, valores_y, metrica="van"):
    """Malla 2D de una métrica variando dos parámetros (para heatmap)."""
    Z = []
    for vy in valores_y:
        fila = []
        for vx in valores_x:
            s2 = Supuestos(**asdict(s))
            setattr(s2, var_x, vx)
            setattr(s2, var_y, vy)
            r = evaluar(s2)
            val = r.get(metrica)
            if metrica == "tir" and val is not None:
                val = val * 100
            fila.append(val if val is not None else float("nan"))
        Z.append(fila)
    return Z


def tornado(s: Supuestos, delta=0.20):
    """Sensibilidad univariada (±delta) del VAN para las palancas clave.

    Devuelve, por palanca, además del VAN con el input bajo/alto:
    - los VALORES de input usados (y su etiqueta formateada),
    - el SENTIDO de la relación: 'directa' (más input ⇒ más VAN) o 'inversa'
      (más input ⇒ menos VAN), que es lo que se percibe como "proporción inversa",
    - el SWING |ΔVAN| = cuánto mueve el VAN entre los dos extremos (su INFLUENCIA).
    Ordenadas de mayor a menor influencia.
    """
    def _clp(v): return "$" + f"{v:,.0f}".replace(",", ".")
    def _mm(v): return "$" + f"{v/1e6:.1f}".replace(".", ",") + "M"
    def _pct(v): return f"{v*100:.0f}%"
    def _km(v): return f"{v:,.0f}".replace(",", ".") + " km"

    # (attr, nombre legible, formateador del valor de input)
    palancas = [
        ("precio_diesel_l",        "Precio del diésel",     lambda v: _clp(v) + "/L"),
        ("precio_energia_kwh",     "Precio electricidad",   lambda v: _clp(v) + "/kWh"),
        ("km_anual_por_vehiculo",  "Kilómetros al año",     _km),
        ("mantencion_diesel_anual","Mantención diésel/año", _mm),
        ("precio_ev_clp",          "Precio del EV",         _mm),
        ("valor_residual_ev_pct",  "Valor residual EV",     _pct),
        ("tasa_descuento",         "Tasa de descuento",     _pct),
    ]
    base = evaluar(s)["van"]
    filas = []
    for attr, nombre, fmt in palancas:
        v_base = getattr(s, attr)
        v_bajo, v_alto = v_base * (1 - delta), v_base * (1 + delta)
        s_lo = Supuestos(**asdict(s)); setattr(s_lo, attr, v_bajo)
        s_hi = Supuestos(**asdict(s)); setattr(s_hi, attr, v_alto)
        van_bajo = evaluar(s_lo)["van"]
        van_alto = evaluar(s_hi)["van"]
        filas.append(dict(
            palanca=nombre, attr=attr,
            van_bajo=van_bajo, van_alto=van_alto, base=base,
            val_base=v_base, val_bajo=v_bajo, val_alto=v_alto,
            lbl_base=fmt(v_base), lbl_bajo=fmt(v_bajo), lbl_alto=fmt(v_alto),
            swing=abs(van_alto - van_bajo),
            sentido="directa" if van_alto >= van_bajo else "inversa",
        ))
    filas.sort(key=lambda r: r["swing"], reverse=True)
    return filas
