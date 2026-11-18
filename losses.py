import math
from collections.abc import Mapping
from typing import Any, TypedDict

from data.loss_charts import evaluate_phi_loss


class YLossCoefficients(TypedDict):
    Y_P_hub: float
    Y_P_mean: float
    Y_P_tip: float
    Y_sg: float
    D_hub: float
    D_mean: float
    D_tip: float
    sigma_hub: float
    sigma_mean: float
    sigma_tip: float
    g_tip_mm: float


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


class RotorLossesAndEfficiencyResult(YLossCoefficients, EfficiencyResult):
    """Dizionario unificato con coefficienti Y, controlli D(r), energie R e eta_rot."""


# =============================================================================
# SEZIONE 0: Funzioni di supporto importate dai moduli dei colleghi (thermo.py)
# =============================================================================
def calculate_specific_work(specific_head: float, rotor_efficiency: float) -> float:
    """Lavoro specifico richiesto al rotore L = gH / eta_rotor [J/kg]."""
    if not 0.0 < rotor_efficiency <= 1.0:
        raise ValueError("Rotor efficiency must be greater than 0 and at most 1.")
    return specific_head / rotor_efficiency


def calculate_outlet_swirl(
    specific_work: float,
    peripheral_speed: float,
    work_done_factor: float,
) -> float:
    """Velocità tangenziale in uscita c_theta2 = L / (zeta * U) [m/s]."""
    if peripheral_speed <= 0.0:
        raise ValueError("Peripheral speed must be positive.")
    if work_done_factor <= 0.0:
        raise ValueError("Work-done factor must be positive.")
    return specific_work / (work_done_factor * peripheral_speed)


# =============================================================================
# SEZIONE 1: Diffusion Factor D(r), Controllo Separazione e Perdita di Profilo Y_P
# =============================================================================
def compute_lieblein_diffusion_factor(
    w1: float,
    w2: float,
    delta_w_theta: float,
    sigma_local: float,
) -> float:
    """
    Calcola il Diffusion Factor di Lieblein locale:
        D = 1 - (w2 / w1) + |Delta_w_theta| / (2 * sigma * w1)
    """
    if w1 <= 0.0 or sigma_local <= 0.0:
        raise ValueError(
            f"Parametri non fisici per il calcolo di D: w1={w1}, sigma={sigma_local}"
        )

    d_factor = 1.0 - (w2 / w1) + abs(delta_w_theta) / (2.0 * sigma_local * w1)
    return float(d_factor)


def check_diffusion_factor_limits(
    d_values: Mapping[str, float],
    d_max: float = 0.45,
) -> None:
    """
    Verifica che il Diffusion Factor D non superi il limite di separazione
    di Lieblein (D <= 0.45) in nessuna sezione radiale (Hub, Mean, Tip).
    """
    violazioni = [
        f"{sec}: D = {val:.4f} > {d_max:.2f}"
        for sec, val in d_values.items()
        if val > d_max
    ]
    if violazioni:
        dettaglio_completo = ", ".join(
            f"{sec}={val:.4f}" for sec, val in d_values.items()
        )
        raise ValueError(
            "Separazione del flusso rilevata (criterio di Lieblein D <= "
            f"{d_max:.2f} violato in {', '.join(violazioni)}). "
            f"Valori radiali calcolati -> [{dettaglio_completo}]."
        )


def compute_Y_P_section_sandrolini(
    section: str,
    sigma_local: float,
    beta2_deg: float,
    d_factor: float,
) -> float:
    """
    Calcola il coefficiente di perdita di profilo Y_P(r) entrando nelle carte
    sperimentali del rotore di Sandrolini (1996):
        Y_P = Phi(D) * (2 * sigma / sin(beta2'))
    """
    sin_b2 = math.sin(math.radians(beta2_deg))
    if sin_b2 <= 0.0:
        raise ValueError(f"Angolo beta2 non valido ({beta2_deg}°): sin(beta2) <= 0.")

    phi_loss = evaluate_phi_loss(section, d_factor)
    y_p = phi_loss * (2.0 * sigma_local) / sin_b2
    return float(y_p)


# =============================================================================
# SEZIONE 2: Coefficiente di Perdita Secondaria e di Gioco Y_{s+g} (Vavra)
# =============================================================================
def compute_Y_s_plus_g(
    r_mean: float,
    h_blade: float,
    g_tip_m: float,
    z_blades: int,
    beta1_deg: float,
    beta2_deg: float,
    beta_inf_deg: float,
) -> float:
    """
    Calcola il coefficiente adimensionale di perdita secondaria e di gioco al tip Y_{s+g}
    al raggio medio secondo la formulazione di Vavra (Eq. 5.34 Sandrolini & Naldi).
    """
    s_pitch = (2.0 * math.pi * r_mean) / z_blades

    b1_rad = math.radians(beta1_deg)
    b2_rad = math.radians(beta2_deg)
    b_inf_rad = math.radians(beta_inf_deg)

    cot_b1 = 1.0 / math.tan(b1_rad)
    cot_b2 = 1.0 / math.tan(b2_rad)

    term_geo = 0.16 * (s_pitch / h_blade) + (g_tip_m / h_blade) * (1.0 / math.sin(b2_rad))
    term_aero = (((cot_b1 - cot_b2) ** 2) / math.sin(b_inf_rad)) * (math.sin(b1_rad) ** 2)

    return float(term_geo * term_aero)


def compute_all_Y_loss_coefficients(
    triangles: dict[str, dict[str, float]],
    aero_design: Mapping[str, object],
    design: Mapping[str, object],
    config: Mapping[str, Any] | None = None,
    d_max: float = 0.45,
) -> YLossCoefficients:
    """
    Calcola i coefficienti Y_P (Hub, Mean, Tip) tramite Sandrolini (1996) e Y_{s+g} (Vavra),
    imponendo la verifica aerodinamica D(r) <= d_max (default 0.45) su tutte e tre le sezioni.
    """
    cfg = config or {}

    d_tip = float(design.get("tip_diameter", design.get("D_tip_m", 0.0)))
    d_hub = float(design.get("hub_diameter", design.get("D_hub_m", 0.0)))
    r_tip = float(design.get("tip_radius", d_tip / 2.0))
    r_hub = float(design.get("hub_radius", d_hub / 2.0))
    if d_tip <= 0.0:
        d_tip = 2.0 * r_tip
    r_mean_geom = float(design.get("mean_radius", 0.5 * (r_hub + r_tip)))
    h_blade = float(design.get("blade_height", r_tip - r_hub))

    # Gioco radiale al tip g_tip:
    # 1. Legge da design o config se specificato in m o mm
    # 2. Altrimenti usa tip_clearance_ratio da config (default 0.005 -> 0.5% di D_tip)
    if "tip_clearance_m" in design:
        g_tip_m = float(design["tip_clearance_m"])
    elif "tip_clearance_mm" in design:
        g_tip_m = float(design["tip_clearance_mm"]) / 1000.0
    elif "tip_clearance_m" in cfg:
        g_tip_m = float(cfg["tip_clearance_m"])
    elif "tip_clearance_mm" in cfg:
        g_tip_m = float(cfg["tip_clearance_mm"]) / 1000.0
    else:
        clearance_ratio = float(cfg.get("tip_clearance_ratio", 0.005))
        g_tip_m = clearance_ratio * d_tip

    z_blades = int(aero_design["Z"])
    if "chord" in aero_design:
        chord = float(aero_design["chord"])
    elif "c" in aero_design:
        chord = float(aero_design["c"])
    else:
        s_mean_fallback = (2.0 * math.pi * r_mean_geom) / z_blades
        chord = float(aero_design["sigma_eff"]) * s_mean_fallback

    radii = {
        "Hub": float(triangles["Hub"].get("radius", r_hub)),
        "Mean": float(triangles["Mean"].get("radius", r_mean_geom)),
        "Tip": float(triangles["Tip"].get("radius", r_tip)),
    }
    sigmas = {
        sec: (chord * z_blades) / (2.0 * math.pi * rad)
        for sec, rad in radii.items()
    }

    d_mean_from_colleague = None
    for key in ("D_mean", "D_factor", "D_eff"):
        if key in aero_design and aero_design[key] is not None:
            d_mean_from_colleague = float(aero_design[key])
            break

    d_overrides = {
        "Hub": float(aero_design["D_hub"]) if aero_design.get("D_hub") is not None else None,
        "Mean": d_mean_from_colleague,
        "Tip": float(aero_design["D_tip"]) if aero_design.get("D_tip") is not None else None,
    }

    d_vals: dict[str, float] = {}
    for sec in ("Hub", "Mean", "Tip"):
        if d_overrides[sec] is not None:
            d_vals[sec] = float(d_overrides[sec])
        else:
            sec_tri = triangles[sec]
            w1_sec = float(sec_tri["w1"])
            w2_sec = float(sec_tri["w2"])
            if "c_theta2" in sec_tri:
                delta_w_theta = abs(float(sec_tri["c_theta2"]))
            else:
                b1_rad = math.radians(float(sec_tri["beta1"]))
                b2_rad = math.radians(float(sec_tri["beta2"]))
                delta_w_theta = abs(w1_sec * math.cos(b1_rad) - w2_sec * math.cos(b2_rad))
            d_vals[sec] = compute_lieblein_diffusion_factor(
                w1=w1_sec,
                w2=w2_sec,
                delta_w_theta=delta_w_theta,
                sigma_local=sigmas[sec],
            )

    # Controllo di separazione D(r) <= 0.45 su Hub, Mean e Tip
    check_diffusion_factor_limits(d_vals, d_max=d_max)

    y_p_vals = {
        sec: compute_Y_P_section_sandrolini(
            section=sec,
            sigma_local=sigmas[sec],
            beta2_deg=float(triangles[sec]["beta2"]),
            d_factor=d_vals[sec],
        )
        for sec in ("Hub", "Mean", "Tip")
    }

    sec_m = triangles["Mean"]
    beta1_m = float(sec_m["beta1"])
    beta2_m = float(sec_m["beta2"])
    if "beta_inf" in sec_m:
        beta_inf_m = float(sec_m["beta_inf"])
    else:
        cot_b1 = 1.0 / math.tan(math.radians(beta1_m))
        cot_b2 = 1.0 / math.tan(math.radians(beta2_m))
        beta_inf_m = math.degrees(math.atan2(1.0, 0.5 * (cot_b1 + cot_b2)))

    y_sg = compute_Y_s_plus_g(
        r_mean=radii["Mean"],
        h_blade=h_blade,
        g_tip_m=g_tip_m,
        z_blades=z_blades,
        beta1_deg=beta1_m,
        beta2_deg=beta2_m,
        beta_inf_deg=beta_inf_m,
    )

    return {
        "Y_P_hub": y_p_vals["Hub"],
        "Y_P_mean": y_p_vals["Mean"],
        "Y_P_tip": y_p_vals["Tip"],
        "Y_sg": y_sg,
        "D_hub": d_vals["Hub"],
        "D_mean": d_vals["Mean"],
        "D_tip": d_vals["Tip"],
        "sigma_hub": sigmas["Hub"],
        "sigma_mean": sigmas["Mean"],
        "sigma_tip": sigmas["Tip"],
        "g_tip_mm": float(g_tip_m * 1000.0),
    }


# =============================================================================
# SEZIONE 3: Energie Perse R [J/kg], Correzione Reynolds e Rendimento Rotore
# =============================================================================
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
    y_results: Mapping[str, float],
    triangles: dict[str, dict[str, float]],
    chord: float,
    config: Mapping[str, Any],
) -> EfficiencyResult:
    """
    Calcola le perdite specifiche R_P*, R_{s+g}, il lavoro di Eulero L
    e il rendimento idraulico del rotore eta_rot.
    """
    rho = float(config.get("air_density", config.get("air_density_kg_m3")))
    mu = float(config.get("dynamic_viscosity", config.get("dynamic_viscosity_Pa_s")))

    w1_h = float(triangles["Hub"]["w1"])
    w1_m = float(triangles["Mean"]["w1"])
    w1_t = float(triangles["Tip"]["w1"])

    u_mean = float(triangles["Mean"]["U"])
    c_theta2_mean = float(triangles["Mean"]["c_theta2"])

    # 1. Energie R_P locali e media di Simpson
    r_p_dict, r_p_bar = compute_profile_energy_losses(
        float(y_results["Y_P_hub"]),
        float(y_results["Y_P_mean"]),
        float(y_results["Y_P_tip"]),
        w1_h,
        w1_m,
        w1_t,
    )

    # 2. Correzione di Reynolds
    re_mid, chi_re, r_p_star = apply_reynolds_correction(
        r_p_bar, w1_m, chord, rho, mu
    )

    # 3. Perdite secondarie e di gioco R_{s+g}
    r_sg = float(float(y_results["Y_sg"]) * (w1_m**2) / 2.0)

    # 4. Lavoro di Eulero L = U_mean * c_theta2_mean [J/kg]
    l_euler = u_mean * c_theta2_mean
    if l_euler <= 0.0:
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


# =============================================================================
# SEZIONE 4: Orchestratore Unico (Coefficienti Y + Controllo D + Rendimento)
# =============================================================================
def compute_rotor_losses_and_efficiency(
    triangles: dict[str, dict[str, float]],
    aero_design: Mapping[str, object],
    design: Mapping[str, object],
    config: Mapping[str, Any],
    d_max: float = 0.45,
) -> RotorLossesAndEfficiencyResult:
    """
    Esegue in un unico passaggio:
      1. Calcolo D(r) e verifica D <= d_max (0.45) su Hub, Mean e Tip
      2. Calcolo coefficienti di perdita Y_P(r) e Y_{s+g}
      3. Integrazione di Simpson, correzione di Reynolds e rendimento eta_rot
    """
    y_results = compute_all_Y_loss_coefficients(
        triangles=triangles,
        aero_design=aero_design,
        design=design,
        config=config,
        d_max=d_max,
    )

    if "chord" in aero_design:
        chord = float(aero_design["chord"])
    elif "c" in aero_design:
        chord = float(aero_design["c"])
    else:
        d_tip = float(design.get("tip_diameter", design.get("D_tip_m", 0.0)))
        d_hub = float(design.get("hub_diameter", design.get("D_hub_m", 0.0)))
        r_tip = float(design.get("tip_radius", d_tip / 2.0))
        r_hub = float(design.get("hub_radius", d_hub / 2.0))
        r_mean = float(design.get("mean_radius", 0.5 * (r_hub + r_tip)))
        s_mean = (2.0 * math.pi * r_mean) / int(aero_design["Z"])
        chord = float(aero_design["sigma_eff"]) * s_mean

    eff_results = calculate_rotor_efficiency(
        y_results=y_results,
        triangles=triangles,
        chord=chord,
        config=config,
    )

    return {**y_results, **eff_results}