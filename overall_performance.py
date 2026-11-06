import math
from typing import Any, TypedDict


class OverallPerformanceResult(TypedDict):
    area_annulus_m2: float
    mass_flow_rate_kg_s: float
    R_sw_J_kg: float
    eta_global: float
    thrust_N: float
    thrust_verified: bool
    thrust_margin_percent: float
    P_useful_kW: float
    P_rot_kW: float
    P_shaft_kW: float
    P_elec_kW: float
    eta_overall: float


def compute_swirl_loss_and_global_efficiency(
    triangles: dict[str, dict[str, float]],
    r_tip: float,
    r_hub: float,
    l_euler: float,
    eta_rot: float,
) -> tuple[float, float]:
    """Calcola la perdita per swirl residuo R_sw e il rendimento globale fluido."""
    c_theta2_tip = triangles["Tip"]["c_theta2"]
    gamma_swirl = r_tip * c_theta2_tip

    # Integrazione del vortice libero nell'annulus
    r_sw = (gamma_swirl**2 * math.log(r_tip / r_hub)) / (r_tip**2 - r_hub**2)
    eta_global = eta_rot - (r_sw / l_euler)

    return float(r_sw), float(eta_global)


def calculate_overall_performance(
    design: dict[str, Any],
    triangles: dict[str, dict[str, float]],
    eff_result: dict[str, float],
    config: dict[str, Any],
) -> OverallPerformanceResult:
    """
    Riceve i risultati geometrici (machine.py), i triangoli (geometry.py) e
    il rendimento (efficiency.py) per calcolare spinta ISO 13350 e potenze.
    """
    d_tip = float(design["D_tip_m"])
    d_hub = float(design["D_hub_m"])
    r_tip = d_tip / 2.0
    r_hub = d_hub / 2.0
    c_m = float(design["c_m_m_s"])

    rho = float(config["air_density_kg_m3"])
    f_nominal = float(config["nominal_thrust_N"])

    eta_mech = float(config.get("mechanical_efficiency", 0.95))
    eta_motor = float(config.get("motor_efficiency", 0.90))

    l_euler = float(eff_result["L_euler_J_kg"])
    eta_rot = float(eff_result["eta_rot"])

    # 1. Swirl residuo e rendimento globale del fluido
    r_sw, eta_global = compute_swirl_loss_and_global_efficiency(
        triangles, r_tip, r_hub, l_euler, eta_rot
    )

    # 2. Portata massica e Spinta (ISO 13350)
    area_annulus = (math.pi / 4.0) * (d_tip**2 - d_hub**2)
    m_dot = rho * area_annulus * c_m
    thrust_calc = m_dot * c_m

    thrust_ok = bool(thrust_calc >= f_nominal)
    margin_pct = ((thrust_calc - f_nominal) / f_nominal) * 100.0

    # 3. Gerarchia delle potenze [kW]
    p_useful_kw = (0.5 * m_dot * (c_m**2)) / 1000.0
    p_rot_kw = (m_dot * l_euler) / 1000.0
    p_shaft_kw = p_rot_kw / eta_mech
    p_elec_kw = p_shaft_kw / eta_motor

    # 4. Rendimento elettromeccanico complessivo
    eta_overall = p_useful_kw / p_elec_kw

    return {
        "area_annulus_m2": float(area_annulus),
        "mass_flow_rate_kg_s": float(m_dot),
        "R_sw_J_kg": float(r_sw),
        "eta_global": float(eta_global),
        "thrust_N": float(thrust_calc),
        "thrust_verified": thrust_ok,
        "thrust_margin_percent": float(margin_pct),
        "P_useful_kW": float(p_useful_kw),
        "P_rot_kW": float(p_rot_kw),
        "P_shaft_kW": float(p_shaft_kw),
        "P_elec_kW": float(p_elec_kw),
        "eta_mech": float(eta_mech),  # <--- AGGIUNTA
        "eta_motor": float(eta_motor),  # <--- AGGIUNTA
        "eta_overall": float(eta_overall),
    }