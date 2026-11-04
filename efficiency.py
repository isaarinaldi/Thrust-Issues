import math
from typing import TypedDict


class EfficiencyResult(TypedDict):
    R_P_hub_J_kg: float
    R_P_mean_J_kg: float
    R_P_tip_J_kg: float
    R_P_bar_J_kg: float
    Re_mid: float
    chi_Re: float
    R_P_star_J_kg: float
    R_sg_J_kg: float
    R_total_J_kg: float
    L_euler_J_kg: float
    eta_rot: float


def compute_profile_energy_losses(
    y_p_hub: float,
    y_p_mean: float,
    y_p_tip: float,
    w1_hub: float,
    w1_mean: float,
    w1_tip: float,
) -> tuple[dict[str, float], float]:
    """Converte Y_P in energie perse R_P [J/kg] e applica la media di Simpson 1/3."""
    r_p_hub = y_p_hub * (w1_hub**2) / 2.0
    r_p_mean = y_p_mean * (w1_mean**2) / 2.0
    r_p_tip = y_p_tip * (w1_tip**2) / 2.0

    # Integrazione di Simpson (Sandrolini & Naldi)
    r_p_bar = (r_p_hub + r_p_tip + 4.0 * r_p_mean) / 6.0
    return {"Hub": r_p_hub, "Mean": r_p_mean, "Tip": r_p_tip}, float(r_p_bar)


def apply_reynolds_correction(
    r_p_bar: float,
    w1_mean: float,
    chord: float,
    density: float,
    viscosity: float,
) -> tuple[float, float, float]:
    """Applica la correzione di Reynolds alla perdita di profilo media."""
    re_mid = (density * w1_mean * chord) / viscosity
    chi_re = (2.0e5 / re_mid) ** 0.2
    r_p_star = r_p_bar * chi_re
    return float(re_mid), float(chi_re), float(r_p_star)


def calculate_rotor_efficiency(
    y_results: dict[str, float],
    triangles: dict[str, dict[str, float]],
    chord: float,
    config: dict[str, float],
) -> EfficiencyResult:
    """
    Riceve i coefficienti Y da losses.py e i triangoli da geometry.py
    per calcolare il bilancio delle energie e il rendimento del rotore.
    """
    rho = float(config["air_density_kg_m3"])
    mu = float(config["dynamic_viscosity_Pa_s"])

    w1_h = triangles["Hub"]["w1"]
    w1_m = triangles["Mean"]["w1"]
    w1_t = triangles["Tip"]["w1"]

    u_mean = triangles["Mean"]["U"]
    c_theta2_mean = triangles["Mean"]["c_theta2"]

    # 1. Energie R_P locali e media di Simpson
    r_p_dict, r_p_bar = compute_profile_energy_losses(
        y_results["Y_P_hub"],
        y_results["Y_P_mean"],
        y_results["Y_P_tip"],
        w1_h,
        w1_m,
        w1_t,
    )

    # 2. Correzione di Reynolds
    re_mid, chi_re, r_p_star = apply_reynolds_correction(
        r_p_bar, w1_m, chord, rho, mu
    )

    # 3. Perdite secondarie R_{s+g}
    r_sg = float(y_results["Y_sg"] * (w1_m**2) / 2.0)

    # 4. Lavoro di Eulero L = U_mean * c_theta2_mean [J/kg]
    l_euler = u_mean * c_theta2_mean
    if l_euler <= 0:
        raise ValueError(f"Lavoro di Eulero non valido: {l_euler:.2f} J/kg")

    # 5. Rendimento del rotore
    r_total = r_p_star + r_sg
    eta_rot = 1.0 - (r_total / l_euler)

    return {
        "R_P_hub_J_kg": r_p_dict["Hub"],
        "R_P_mean_J_kg": r_p_dict["Mean"],
        "R_P_tip_J_kg": r_p_dict["Tip"],
        "R_P_bar_J_kg": r_p_bar,
        "Re_mid": re_mid,
        "chi_Re": chi_re,
        "R_P_star_J_kg": r_p_star,
        "R_sg_J_kg": r_sg,
        "R_total_J_kg": r_total,
        "L_euler_J_kg": l_euler,
        "eta_rot": float(eta_rot),
    }