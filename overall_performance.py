import math
from typing import Any, TypedDict


class OverallPerformanceResult(TypedDict):
    area_annulus_m2: float
    mass_flow_rate_kg_s: float
    c_jet_effective_m_s: float
    R_sw_J_kg: float
    eta_global: float
    thrust_N: float
    thrust_verified: bool
    thrust_margin_percent: float
    P_useful_kW: float
    P_rot_kW: float
    P_shaft_kW: float
    P_elec_kW: float
    eta_mech: float
    eta_motor: float
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

    r_sw = (gamma_swirl**2 * math.log(r_tip / r_hub)) / (r_tip**2 - r_hub**2)
    eta_global = eta_rot - (r_sw / l_euler)

    return float(r_sw), float(eta_global)


def calculate_overall_performance(
    design: dict[str, Any],
    triangles: dict[str, dict[str, float]],
    eff_result: dict[str, float],
    config: dict[str, Any],
    geometry: dict[str, float] | None = None,
) -> OverallPerformanceResult:
    """
    Calcola la perdita per swirl residuo, la spinta ISO 13350 e la gerarchia delle potenze
    utilizzando eta_global (al netto dello swirl residuo allo scarico).
    """
    geom = geometry if geometry is not None else design
    d_tip = float(geom.get("tip_diameter", geom.get("D_tip_m")))
    d_hub = float(geom.get("hub_diameter", geom.get("D_hub_m")))
    r_tip = float(geom.get("tip_radius", d_tip / 2.0))
    r_hub = float(geom.get("hub_radius", d_hub / 2.0))
    c_m = float(triangles["Mean"].get("c_m", design.get("c_m_m_s")))

    rho = float(config.get("air_density", config.get("air_density_kg_m3")))
    f_nominal = float(config.get("nominal_thrust", config.get("nominal_thrust_N")))
    c_amb = float(config.get("ambient_velocity", config.get("ambient_velocity_m_s", 0.0)))

    eta_mech = float(config.get("mechanical_efficiency", 0.95))
    eta_motor = float(config.get("motor_efficiency", 0.90))

    l_euler = float(eff_result["L_euler_J_kg"])
    eta_rot = float(eff_result["eta_rot"])

    # 1. Swirl residuo R_sw e rendimento globale del fluido eta_global
    r_sw, eta_global = compute_swirl_loss_and_global_efficiency(
        triangles, r_tip, r_hub, l_euler, eta_rot
    )

    # 2. Portata massica nell'anulus
    area_annulus = (math.pi / 4.0) * (d_tip**2 - d_hub**2)
    m_dot = rho * area_annulus * c_m

    # 3. Energia specifica assiale netta (al netto dello swirl) e velocità effettiva del getto
    g_h_useful = eta_global * l_euler
    if g_h_useful <= 0.0:
        raise ValueError(f"Energia specifica utile non valida: gH_utile = {g_h_useful:.2f} J/kg")

    c_jet_eff = math.sqrt(c_amb**2 + 2.0 * g_h_useful)

    # Spinta effettiva (ISO 13350) con tolleranza numerica di convergenza (0.05 N)
    thrust_calc = m_dot * (c_jet_eff - c_amb)
    thrust_ok = bool(thrust_calc >= f_nominal - 0.05)
    margin_pct = ((thrust_calc - f_nominal) / f_nominal) * 100.0

    # 4. Gerarchia delle potenze [kW]
    p_useful_kw = (m_dot * g_h_useful) / 1000.0
    p_rot_kw = (m_dot * l_euler) / 1000.0
    p_shaft_kw = p_rot_kw / eta_mech
    p_elec_kw = p_shaft_kw / eta_motor

    # 5. Rendimento elettromeccanico complessivo (eta_global * eta_mech * eta_motor)
    eta_overall = p_useful_kw / p_elec_kw

    return {
        "area_annulus_m2": float(area_annulus),
        "mass_flow_rate_kg_s": float(m_dot),
        "c_jet_effective_m_s": float(c_jet_eff),
        "R_sw_J_kg": float(r_sw),
        "eta_global": float(eta_global),
        "thrust_N": float(thrust_calc),
        "thrust_verified": thrust_ok,
        "thrust_margin_percent": float(margin_pct),
        "P_useful_kW": float(p_useful_kw),
        "P_rot_kW": float(p_rot_kw),
        "P_shaft_kW": float(p_shaft_kw),
        "P_elec_kW": float(p_elec_kw),
        "eta_mech": float(eta_mech),
        "eta_motor": float(eta_motor),
        "eta_overall": float(eta_overall),
    }