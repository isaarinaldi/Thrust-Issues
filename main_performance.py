import math
from pathlib import Path
from typing import Any

import yaml

# =============================================================================
# MODULI DEI COLLEGHI (Importati in sola lettura - nessuna modifica richiesta)
# =============================================================================
from geometry import (
    annulus_geometry,
    calculate_velocity_triangles,
    hub_ratio_from_continuity,
)
from machine import check_continuity, eckert_search, select_design
from thermo import operating_point

try:
    from airfoil_losses.airfoil_inputs import prepara_input_airfoil
    from airfoil_losses.airfoil_machine import (
        calcola_diffusion_factor,
        dimensionamento_geometrico,
        scelta_profilo,
        verifica_aerodinamica_finale,
    )
except ModuleNotFoundError:
    import airfoil_inputs
    import airfoil_machine

# =============================================================================
# MODULI DI VERIFICA PRESTAZIONALE (Parte 3 - losses.py unificato)
# =============================================================================
from losses import (
    RotorLossesAndEfficiencyResult,
    compute_rotor_losses_and_efficiency,
)
from overall_performance import (
    OverallPerformanceResult,
    calculate_overall_performance,
)

PROJECT_DIR = Path(__file__).resolve().parent


def _load_yaml(file_path: Path) -> dict[str, Any]:
    """Carica un file YAML verificandone l'esistenza e la validità."""
    if not file_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path.resolve()}")
    with file_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML mapping in: {file_path.resolve()}")
    return data


def _resolve_path(path_like: str | Path) -> Path:
    """Risolve il percorso rispetto alla directory corrente o alla cartella del progetto."""
    candidate = Path(path_like)
    if candidate.exists():
        return candidate
    return PROJECT_DIR / candidate


def _run_airfoil_sizing(
    triangles: dict[str, dict[str, float]],
    config_airfoil: dict[str, Any],
    speed_of_sound: float,
    air_density: float,
    dynamic_viscosity: float,
) -> dict[str, Any]:
    """
    Esegue il dimensionamento del profilo NACA 65 usando esclusivamente le funzioni
    dei colleghi (prepara_input_airfoil, scelta_profilo, dimensionamento_geometrico,
    calcola_diffusion_factor, verifica_aerodinamica_finale).
    """
    dati_airfoil = prepara_input_airfoil(
        triangles,
        config_airfoil,
        speed_of_sound=speed_of_sound,
        air_density=air_density,
        dynamic_viscosity=dynamic_viscosity,
    )

    profile_name, tmax_c, sigma_start = scelta_profilo(dati_airfoil)
    d_max = float(config_airfoil.get("D_max", 0.45))
    de_haller_min = float(config_airfoil.get("de_haller_min", 0.72))
    sigma_step = float(config_airfoil.get("sigma_step", 0.02))
    sigma_max = float(config_airfoil.get("sigma_max", 1.14))
    max_iter_sigma = int(config_airfoil.get("max_iter_sigma", 8))

    de_haller = float(dati_airfoil["W2"]) / float(dati_airfoil["W1"])

    sigma_curr = float(sigma_start)
    d_eff = 0.0
    for _ in range(max_iter_sigma + 1):
        (
            _h_blade,
            chord_val,
            _sprog,
            z_blades,
            _delta_phi,
            _seff,
            sigma_eff,
        ) = dimensionamento_geometrico(
            dati_airfoil["rtip"],
            dati_airfoil["rhub"],
            dati_airfoil["rm"],
            dati_airfoil["AR"],
            sigma_curr,
        )

        dati_eff = dict(dati_airfoil)
        dati_eff["sigma_prog"] = float(sigma_eff)
        d_eff = float(calcola_diffusion_factor(dati_eff))

        if verifica_aerodinamica_finale(d_eff, de_haller, d_max, de_haller_min):
            return {
                "profile": str(profile_name),
                "tmax_c": float(tmax_c),
                "sigma_eff": float(sigma_eff),
                "chord": float(chord_val),
                "Z": int(z_blades),
                "D_factor": d_eff,
                "de_haller": de_haller,
            }

        sigma_curr = round(sigma_curr + sigma_step, 6)
        if sigma_curr > sigma_max + 1e-9:
            break

    raise ValueError(
        f"Airfoil aerodynamic verification failed (D_eff={d_eff:.4f} <= {d_max}, "
        f"de_Haller={de_haller:.4f} >= {de_haller_min})."
    )


def run_main_performance(config_path: str | Path = "config.yaml") -> dict[str, Any]:
    """
    Orchestra l'intera progettazione del Jet Fan assiale chiudendo simultaneamente:
      1. Il bilancio interno del rotore (eta_assumed -> eta_rot)
      2. La compensazione energetica per lo swirl residuo allo scarico (R_sw_assumed -> R_sw)
         in modo da garantire esattamente la spinta nominale netta entro D_tip <= D_max.
    """
    # -------------------------------------------------------------------------
    # 1. LETTURA CONFIGURAZIONI (config.yaml unificato dei colleghi)
    # -------------------------------------------------------------------------
    config = _load_yaml(_resolve_path(config_path))
    if isinstance(config.get("airfoil"), dict):
        config_airfoil = config["airfoil"]
    else:
        config_airfoil = _load_yaml(
            PROJECT_DIR / "airfoil_losses" / "airfoil_config.yaml"
        )

    d_max_limit = float(config_airfoil.get("D_max", 0.45))

    # Parametri di controllo del ciclo iterativo adattivo
    eta_assumed = float(config.get("rotor_efficiency_initial", 0.80))
    r_sw_assumed = 0.0  # [J/kg] energia di swirl da compensare sul carico del rotore
    tolerance = float(config.get("tolerance", 1e-4))
    r_sw_tolerance = 1e-2  # [J/kg]
    max_iter = int(config.get("max_iterations", 150))
    relax_switch_1 = int(config.get("relaxation_switch_iter", 50))
    relax_switch_2 = int(config.get("relaxation_switch_iter_2", 100))
    alpha_stage_1 = float(config.get("relaxation_factor", 0.5))
    alpha_stage_2 = float(config.get("relaxation_factor_2", 0.25))

    # Parametri di progetto estratti da config.yaml
    nominal_thrust = float(config["nominal_thrust"])
    air_density = float(config["air_density"])
    dynamic_viscosity = float(config["dynamic_viscosity"])
    jet_velocity = float(config["jet_velocity"])
    ambient_velocity = float(config["ambient_velocity"])
    work_done_factor = float(config["work_done_factor"])
    max_tip_diameter = float(config["max_tip_diameter"])
    tip_diameter_fraction = float(config["tip_diameter_fraction"])
    speed_of_sound = float(config["speed_of_sound"])
    specific_speed_min = float(config["specific_speed_min"])
    specific_speed_max = float(config["specific_speed_max"])
    specific_speed_points = int(config["specific_speed_points"])

    # Energia specifica assiale richiesta per produrre la spinta nominale
    g_h_required = 0.5 * (jet_velocity**2 - ambient_velocity**2)

    print("=" * 94)
    print("               AXIAL JET FAN SIMULATION - MAIN PERFORMANCE PIPELINE")
    print("=" * 94 + "\n")
    print("-" * 94)
    print(
        f"{'Iter':<5} | {'alpha':<6} | {'eta_ass':<9} | {'eta_rot':<9} | "
        f"{'R_sw [J/kg]':<12} | {'Thrust [N]':<11} | {'Delta_eta':<11}"
    )
    print("-" * 94)

    selected_design: dict[str, Any] = {}
    geometry: dict[str, float] = {}
    continuity: dict[str, Any] = {}
    triangles: dict[str, dict[str, float]] = {}
    aero_res: dict[str, Any] = {}
    rotor_perf: RotorLossesAndEfficiencyResult | dict[str, float] = {}
    overall_res: OverallPerformanceResult | dict[str, Any] = {}
    eta_calc = eta_assumed
    r_sw_calc = r_sw_assumed
    delta_eta = float("inf")
    converged = False

    # -------------------------------------------------------------------------
    # 2. LOOP ITERATIVO ADATTIVO (CONVERGENZA SU ETA_ROT E COMPENSAZIONE SWIRL)
    # -------------------------------------------------------------------------
    for iteration in range(1, max_iter + 1):
        # Compensazione del salto energetico per coprire sia il getto assiale
        # sia l'energia cinetica di swirl residuo, mantenendo invariata la portata Q
        g_h_design = g_h_required + r_sw_assumed
        c_jet_design = math.sqrt(ambient_velocity**2 + 2.0 * g_h_design)
        thrust_design = (
            nominal_thrust
            * (c_jet_design - ambient_velocity)
            / (jet_velocity - ambient_velocity)
        )

        # A. Punto operativo termodinamico (thermo.py)
        flow_rate, specific_head, specific_work, _ = operating_point(
            nominal_thrust=thrust_design,
            air_density=air_density,
            jet_velocity=c_jet_design,
            ambient_velocity=ambient_velocity,
            rotor_efficiency=eta_assumed,
        )

        # B. Ricerca su Eckert e geometria anulare (machine.py + geometry.py)
        eckert_results = eckert_search(
            flow_rate=flow_rate,
            specific_head=specific_head,
            max_tip_diameter=max_tip_diameter,
            tip_diameter_fraction=tip_diameter_fraction,
            specific_speed_min=specific_speed_min,
            specific_speed_max=specific_speed_max,
            specific_speed_points=specific_speed_points,
        )

        selected_design = select_design(eckert_results)
        selected_design["chi"] = hub_ratio_from_continuity(
            flow_rate=flow_rate,
            tip_diameter=selected_design["tip_diameter"],
            phi=selected_design["phi"],
            tip_speed=selected_design["tip_speed"],
        )

        geometry = annulus_geometry(
            tip_diameter=selected_design["tip_diameter"],
            chi=selected_design["chi"],
        )

        c_m = selected_design["phi"] * selected_design["tip_speed"]
        continuity = check_continuity(
            flow_rate=flow_rate,
            phi=selected_design["phi"],
            tip_speed=selected_design["tip_speed"],
            annulus_area=geometry["annulus_area"],
            jet_velocity=c_jet_design,
        )

        # C. Triangoli di velocità alle sezioni Hub, Mean, Tip (geometry.py)
        triangles = calculate_velocity_triangles(
            geometry=geometry,
            tip_speed=selected_design["tip_speed"],
            c_m=c_m,
            specific_head=specific_head,
            rotor_efficiency_initial=eta_assumed,
            work_done_factor=work_done_factor,
        )

        # D. Progettazione e verifica profilo alare NACA 65 (airfoil_losses)
        aero_res = _run_airfoil_sizing(
            triangles=triangles,
            config_airfoil=config_airfoil,
            speed_of_sound=speed_of_sound,
            air_density=air_density,
            dynamic_viscosity=dynamic_viscosity,
        )

        # E. Controllo D(r) <= D_max, perdite Y_P/Y_{s+g} e rendimento rotore (losses.py)
        rotor_perf = compute_rotor_losses_and_efficiency(
            triangles=triangles,
            aero_design=aero_res,
            design=geometry,
            config=config,
            d_max=d_max_limit,
        )

        # F. Swirl residuo R_sw, spinta netta ISO 13350 e potenze (overall_performance.py)
        overall_res = calculate_overall_performance(
            design=selected_design,
            triangles=triangles,
            eff_result=dict(rotor_perf),
            config=config,
            geometry=geometry,
        )

        eta_calc = float(rotor_perf["eta_rot"])
        r_sw_calc = float(overall_res["R_sw_J_kg"])
        thrust_curr = float(overall_res["thrust_N"])

        delta_eta = abs(eta_calc - eta_assumed)
        delta_r_sw = abs(r_sw_calc - r_sw_assumed)

        # Scelta adattiva del fattore di rilassamento alpha:
        # - Iterazioni 1..50   : alpha = 1.0  (sostituzione diretta, massima velocità)
        # - Iterazioni 51..100 : alpha = 0.5  (sottorilassamento per smorzare oscillazioni)
        # - Iterazioni > 100   : alpha = 0.25 (sottorilassamento forte)
        if iteration <= relax_switch_1:
            alpha_curr = 1.0
        elif iteration <= relax_switch_2:
            alpha_curr = alpha_stage_1
        else:
            alpha_curr = alpha_stage_2

        print(
            f"{iteration:<5} | {alpha_curr:<6.2f} | {eta_assumed:<9.5f} | {eta_calc:<9.5f} | "
            f"{r_sw_calc:<12.3f} | {thrust_curr:<11.2f} | {delta_eta:<11.4e}"
        )

        if delta_eta < tolerance and delta_r_sw < r_sw_tolerance:
            converged = True
            print("-" * 94)
            print(
                f"✅ CONVERGENCE ACHIEVED at iteration {iteration} "
                f"(alpha={alpha_curr:.2f})!\n"
            )
            break

        eta_assumed = alpha_curr * eta_calc + (1.0 - alpha_curr) * eta_assumed
        r_sw_assumed = alpha_curr * r_sw_calc + (1.0 - alpha_curr) * r_sw_assumed

    if not converged:
        print("-" * 94)
        raise RuntimeError(
            f"Convergence failed after {max_iter} iterations "
            f"(eta_assumed={eta_assumed:.5f}, eta_calc={eta_calc:.5f}, "
            f"R_sw={r_sw_calc:.3f} J/kg, delta_eta={delta_eta:.5e})."
        )

    eta_mech = float(overall_res["eta_mech"])
    eta_motor = float(overall_res["eta_motor"])

    # -------------------------------------------------------------------------
    # 3. REPORT FINALE COMPLETO IN INGLESE
    # -------------------------------------------------------------------------
    print("=" * 94)
    print("                         FINAL PROJECT PERFORMANCE REPORT")
    print("=" * 94)
    print(f"• Airfoil Profile Selected     : {aero_res['profile']}")
    print(f"• Number of Blades (Z)         : {aero_res['Z']}")
    print(f"• Blade Chord (c)              : {aero_res['chord'] * 1000.0:.2f} mm")
    print(
        f"• Tip / Hub Diameter           : {geometry['tip_diameter']:.4f} m / "
        f"{geometry['hub_diameter']:.4f} m (Max limit: {max_tip_diameter:.2f} m)"
    )
    print(f"• Tip Clearance (g_tip)        : {rotor_perf['g_tip_mm']:.2f} mm")
    print(f"• Rotational Speed             : {selected_design['rotational_speed']:.1f} RPM")
    print("-" * 94)
    print(f"• Target Nominal Thrust        : {nominal_thrust:.2f} N")
    print(f"• Calculated Net Thrust        : {overall_res['thrust_N']:.2f} N")
    print(f"• Effective Jet Velocity       : {overall_res['c_jet_effective_m_s']:.2f} m/s")
    print(f"• Thrust Margin                : {overall_res['thrust_margin_percent']:+.2f} %")
    print(
        f"• Thrust Requirement Status    : "
        f"{'PASSED ✅' if overall_res['thrust_verified'] else 'FAILED ❌'}"
    )
    print("-" * 94)
    print(
        f"• Diffusion Factor (D <= {d_max_limit:.2f}) : "
        f"Hub={rotor_perf['D_hub']:.4f} | "
        f"Mean={rotor_perf['D_mean']:.4f} | "
        f"Tip={rotor_perf['D_tip']:.4f} (PASSED ✅)"
    )
    print("-" * 94)
    print(f"• Residual Swirl Loss (R_sw)   : {overall_res['R_sw_J_kg']:.2f} J/kg")
    print(f"• Rotor Efficiency (eta_rot)   : {rotor_perf['eta_rot'] * 100:.2f} %")
    print(f"• Global Fluid Efficiency      : {overall_res['eta_global'] * 100:.2f} %")
    print(f"• Mechanical Efficiency (eta_m): {eta_mech * 100:.2f} %")
    print(f"• Motor Efficiency (eta_mot)   : {eta_motor * 100:.2f} %")
    print("-" * 94)
    print(f"• Useful Jet Power             : {overall_res['P_useful_kW']:.2f} kW")
    print(f"• Rotor Aerodynamic Power      : {overall_res['P_rot_kW']:.2f} kW")
    print(f"• Shaft Power                  : {overall_res['P_shaft_kW']:.2f} kW")
    print(f"• Electrical Power Input       : {overall_res['P_elec_kW']:.2f} kW")
    print("-" * 94)
    print(f"• Overall Machine Efficiency   : {overall_res['eta_overall'] * 100:.2f} %")
    print("=" * 94)

    return {
        "design": selected_design,
        "geometry": geometry,
        "continuity": continuity,
        "triangles": triangles,
        "airfoil": aero_res,
        "rotor_performance": rotor_perf,
        "overall": overall_res,
    }


if __name__ == "__main__":
    run_main_performance("config.yaml")