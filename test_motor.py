# -*- coding: utf-8 -*-
"""Test de regresión: el motor debe reproducir el caso base del Entregable 7 del estudio."""
from motor import Supuestos, evaluar, analisis_depreciacion

def test_caso_base_estudio():
    # Configuración = modelo simplificado del estudio (per-unidad, pre-impuestos, sin residual)
    s = Supuestos(
        num_vehiculos_diesel=1,
        km_anual_por_vehiculo=30_000,
        horizonte_anios=7, tasa_descuento=0.10,
        escalamiento_diesel=0, escalamiento_energia=0, escalamiento_costos=0,
        precio_diesel_clp=22_000_000, rendimiento_km_l=11.0, precio_diesel_l=1_050,
        mantencion_diesel_anual=1_200_000,
        precio_ev_clp=29_750_000, eficiencia_km_kwh=6.2, precio_energia_kwh=130,
        perdidas_carga_pct=0.0, mantencion_ev_anual=400_000,
        # neutralizar partidas que el estudio no separó
        neumaticos_diesel_anual=350_000, neumaticos_ev_anual=350_000,
        seguro_diesel_anual=600_000, seguro_ev_anual=600_000,
        permiso_circulacion_diesel=250_000, permiso_circulacion_ev=250_000,
        adblue_anual=0,
        valor_residual_diesel_pct=0, valor_residual_ev_pct=0,
        costo_cargador_clp=0, costo_instalacion_electrica=0,
        aplicar_equivalencia_capacidad=False, incluir_ahorro_choferes=False,
        aplicar_efecto_tributario=False,
        # el estudio comparó a valor nominal (EV $29,75M vs diésel $22M, delta $7,75M):
        # equivale a NO descontar IVA (el descuento de IVA es simétrico y no altera el delta relativo)
        iva_recuperable=False,
    )
    r = evaluar(s)
    print(f"  inc_capex        = ${r['inc_capex']:,.0f}  (esperado ~7.750.000)")
    print(f"  ahorro OPEX/año  = ${r['ahorro_anual'][0]:,.0f}  (esperado ~3.034.000)")
    print(f"  payback simple   = {r['payback_simple']:.2f} años  (esperado ~2,6)")
    print(f"  VAN (7a, 10%)    = ${r['van']:,.0f}  (esperado ~+7.000.000)")
    print(f"  TIR              = {r['tir']*100:.1f}%  (esperado ~33%)")
    print(f"  TCO diésel 7a    = ${r['tco_diesel']:,.0f}")
    print(f"  TCO EV 7a        = ${r['tco_ev']:,.0f}")
    print(f"  costo/km diésel  = ${r['costo_km_diesel']:.1f}  | costo/km EV = ${r['costo_km_ev']:.1f}")

    assert abs(r["inc_capex"] - 7_750_000) < 1, "CAPEX delta debe ser $7,75M"
    assert abs(r["ahorro_anual"][0] - 3_034_000) < 20_000, "Ahorro OPEX/año ~$3,03M"
    assert abs(r["payback_simple"] - 2.6) < 0.15, "Payback ~2,6 años"
    assert abs(r["van"] - 7_000_000) < 200_000, "VAN ~+$7,0M"
    assert r["tir"] is not None and abs(r["tir"] - 0.33) < 0.03, "TIR ~33%"
    print("  ✓ Caso base del Entregable 7 reproducido.")


def test_depreciacion_instantanea_conviene():
    s = Supuestos(empresa_con_utilidades=True)
    a = analisis_depreciacion(s, s.precio_ev_clp)
    print(f"\n  VPN escudo lineal      = ${a['regimenes']['lineal']['vpn_escudo']:,.0f}")
    print(f"  VPN escudo acelerada   = ${a['regimenes']['acelerada']['vpn_escudo']:,.0f}")
    print(f"  VPN escudo instantánea = ${a['regimenes']['instantanea']['vpn_escudo']:,.0f}")
    print(f"  Ganancia instant. vs lineal = ${a['ganancia_vpn_instantanea_vs_lineal']:,.0f}")
    assert a["conviene_acelerar"] is True
    assert a["ganancia_vpn_instantanea_vs_lineal"] > 0
    print("  ✓ Con utilidades, la depreciación instantánea aumenta el VPN del escudo → conviene.")


if __name__ == "__main__":
    print("TEST 1 — Caso base estudio (Entregable 7):")
    test_caso_base_estudio()
    print("\nTEST 2 — Decisión de depreciación:")
    test_depreciacion_instantanea_conviene()
    print("\n✅ Todos los tests pasaron.")
