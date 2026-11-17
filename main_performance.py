import math
from pathlib import Path
from typing import Any

import numpy as np
import yaml

# =============================================================================
# MODULI DEI COLLEGHI (Importati in sola lettura - nessuna modifica richiesta)
# =============================================================================
from airfoil_design.airfoil_inputs import prepara_input_airfoil
from airfoil_design.airfoil_machine import (
    calcola_diffusion_factor,
    dimensionamento_geometrico,
    scelta_profilo,
)
from airfoil_design.airfoil_main import esegui_airfoil
from geometry import calculate_velocity_triangles
from machine import preliminary_design
from thermo import operating_point

# =============================================================================
# MODULI DI VERIFICA PRESTAZIONALE (Parte 3 - losses.py unificato)
# =============================================================================
from losses import (
    RotorLossesAndEfficiencyResult,
    compute_rotor_losses_and_efficiency,
)
from overall_performance import calculate_overall_performance

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


def run_main_performance(config_path: str | Path = "config.yaml") -> dict[str, Any]:
    """
    Orchestra l'intera progettazione del Jet Fan assiale:
      1. Punto operativo termodinamico (thermo.py)
      2. Scansione adimensionale e geometria preliminare (machine.py)
      3. Triangoli di velocità a vortice libero (geometry.py)
      4. Dimensionamento e verifica profilo alare Lieblein (airfoil_design)
      5. Controllo D(r) <= 0.45, perdite Y e rendimento rotore eta_rot (losses.py)
      6. Prestazioni complessive, spinta ISO 13350 e potenze (overall_performance.py)
    """
    # -------------------------------------------------------------------------
    # 1. LETTURA CONFIGURAZIONI (Generale + Airfoil in sola lettura)
    # -------------------------------------------------------------------------
    config = _load_yaml(_resolve_path(config_path))
    config_airfoil = _load_yaml(
        PROJECT_DIR / "airfoil_design" / "airfoil_config.yaml"
    )

    # Soglia limite del Diffusion Factor imposta dal collega (default 0.45)
    d_max_limit = float(config_airfoil.get("D_max", 0.45))

    # Parametri di controllo del ciclo iterativo sul rendimento
    eta_assumed = float(
        config.get("rotor_efficiency_initial", config.get("initial_eta_guess", 0.80))
    )
    tolerance = float(config.get("tolerance", 1e-4))
    max_iter = int(config.get("max_iterations", 50))
    alpha = float(config.get("relaxation_factor", 0.5))

    # Parametri di progetto costanti estratti da config.yaml
    nominal_thrust = float(config["nominal_thrust_N"])
    air_density = float(config["air_density_kg_m3"])
    jet_velocity = float(config["jet_velocity_m_s"])
    ambient_velocity = float(config["ambient_velocity_m_s"])
    work_done_factor = float(config["work_done_factor"])
    max_tip_diameter = float(config["max_tip_diameter_m"])
    tip_diameter = float(config["tip_diameter_fraction"]) * max_tip_diameter
    speed_of_sound = float(config["speed_of_sound_m_s"])
    mach_limit = float(config["max_mach_number"])
    section_count = int(config["number_of_sections"])

    specific_speeds = np.linspace(
        float(config["specific_speed_min"]),
        float(config["specific_speed_max"]),
        int(config["specific_speed_points"]),
    )

    print("=" * 72)
    print("       AXIAL JET FAN SIMULATION - MAIN PERFORMANCE PIPELINE")
    print("=" * 72 + "\n")
    print("-" * 72)
    print(f"{'Iter':<6} | {'eta_assumed':<13} | {'eta_calculated':<15} | {'Delta':<12}")
    print("-" * 72)

    selected_design: dict[str, Any] = {}
    triangles: dict[str, dict[str, float]] = {}
    aero_res: dict[str, Any] = {}
    rotor_perf: RotorLossesAndEfficiencyResult | dict[str, float] = {}
    converged = False

    # -------------------------------------------------------------------------
    # 2. LOOP ITERATIVO DI CONVERGENZA SU ETA_ROT
    # -------------------------------------------------------------------------
    for iteration in range(1, max_iter + 1):
        # A. Punto operativo termodinamico (thermo.py)
        flow_rate, specific_head, specific_work, _ = operating_point(
            nominal_thrust=nominal_thrust,
            air_density=air_density,
            jet_velocity=jet_velocity,
            ambient_velocity=ambient_velocity,
            rotor_efficiency=eta_assumed,
        )

        # B. Scansione velocità specifica e scelta configurazione ottimale (machine.py)
        candidates = [
            preliminary_design(
                float(omega_s),
                flow_rate=flow_rate,
                specific_head=specific_head,
                specific_work=specific_work,
                work_done_factor=work_done_factor,
                tip_diameter=tip_diameter,
                max_tip_diameter=max_tip_diameter,
                speed_of_sound=speed_of_sound,
                mach_limit=mach_limit,
                section_count=section_count,
            )
            for omega_s in specific_speeds
        ]

        feasible = [res for res in candidates if res["status"] == "PASS"]
        if not feasible:
            raise ValueError(
                "No geometric configuration satisfied the preliminary design constraints."
            )

        selected_design = min(
            feasible,
            key=lambda cand: math.hypot(
                cand["psi_deviation_pct"], cand["phi_deviation_pct"]
            ),
        )

        # C. Triangoli di velocità alle sezioni Hub, Mean, Tip (geometry.py)
        triangles = calculate_velocity_triangles(
            selected_design,
            specific_work=specific_work,
            work_done_factor=work_done_factor,
            speed_of_sound=speed_of_sound,
        )

        # D. Progettazione e verifica profilo alare (airfoil_design in sola lettura)
        dati_airfoil = prepara_input_airfoil(triangles, config_airfoil)
        if not esegui_airfoil(dati_airfoil):
            raise ValueError("Airfoil aerodynamic verification failed.")

        profile_name, tmax_c, _ = scelta_profilo(dati_airfoil)

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
            dati_airfoil["sigma_prog"],
        )

        # Diffusion Factor sulla linea media tramite la funzione del collega
        dati_eff = dict(dati_airfoil)
        dati_eff["sigma_prog"] = float(sigma_eff)
        d_mean_colleague = float(calcola_diffusion_factor(dati_eff))

        aero_res = {
            "profile": str(profile_name),
            "tmax_c": float(tmax_c),
            "sigma_eff": float(sigma_eff),
            "chord": float(chord_val),
            "Z": int(z_blades),
            "D_factor": d_mean_colleague,
        }

        # E. Controllo D(r) <= D_max, perdite Y_P/Y_{s+g} e rendimento rotore (losses.py)
        rotor_perf = compute_rotor_losses_and_efficiency(
            triangles=triangles,
            aero_design=aero_res,
            design=selected_design,
            config=config,
            d_max=d_max_limit,
        )

        eta_calc = float(rotor_perf["eta_rot"])
        delta_eta = abs(eta_calc - eta_assumed)

        print(
            f"{iteration:<6} | {eta_assumed:<13.5f} | {eta_calc:<15.5f} | {delta_eta:<12.5e}"
        )

        if delta_eta < tolerance:
            converged = True
            print("-" * 72)
            print(f"✅ CONVERGENCE ACHIEVED at iteration {iteration}!\n")
            break

        eta_assumed = alpha * eta_calc + (1.0 - alpha) * eta_assumed

    if not converged:
        print("-" * 72)
        print("⚠️ Maximum iterations reached without full convergence.\n")

    # -------------------------------------------------------------------------
    # 3. PRESTAZIONI COMPLESSIVE, SPINTA ISO 13350 E BILANCIO POTENZE
    # -------------------------------------------------------------------------
    overall_res = calculate_overall_performance(
        selected_design,
        triangles,
        dict(rotor_perf),
        config,
    )

    eta_mech = float(
        overall_res.get("eta_mech", config.get("mechanical_efficiency", 0.95))
    )
    eta_motor = float(
        overall_res.get("eta_motor", config.get("motor_efficiency", 0.90))
    )

    # -------------------------------------------------------------------------
    # 4. REPORT FINALE COMPLETO IN INGLESE
    # -------------------------------------------------------------------------
    print("=" * 72)
    print("                 FINAL PROJECT PERFORMANCE REPORT")
    print("=" * 72)
    print(f"• Airfoil Profile Selected     : {aero_res['profile']}")
    print(f"• Number of Blades (Z)         : {aero_res['Z']}")
    print(f"• Blade Chord (c)              : {aero_res['chord'] * 1000.0:.2f} mm")
    print(f"• Rotational Speed             : {selected_design['rpm']:.1f} RPM")
    print("-" * 72)
    print(f"• Target Nominal Thrust        : {nominal_thrust:.2f} N")
    print(f"• Calculated Thrust (ISO 13350): {overall_res['thrust_N']:.2f} N")
    print(f"• Thrust Margin                : {overall_res['thrust_margin_percent']:+.2f} %")
    print(
        f"• Thrust Requirement Status    : "
        f"{'PASSED ✅' if overall_res['thrust_verified'] else 'FAILED ❌'}"
    )
    print("-" * 72)
    print(
        f"• Diffusion Factor (D <= {d_max_limit:.2f}) : "
        f"Hub={rotor_perf['D_hub']:.4f} | "
        f"Mean={rotor_perf['D_mean']:.4f} | "
        f"Tip={rotor_perf['D_tip']:.4f} (PASSED ✅)"
    )
    print("-" * 72)
    print(f"• Rotor Efficiency (eta_rot)   : {rotor_perf['eta_rot'] * 100:.2f} %")
    print(f"• Global Fluid Efficiency      : {overall_res['eta_global'] * 100:.2f} %")
    print(f"• Mechanical Efficiency (eta_m): {eta_mech * 100:.2f} %")
    print(f"• Motor Efficiency (eta_mot)   : {eta_motor * 100:.2f} %")
    print("-" * 72)
    print(f"• Useful Jet Power             : {overall_res['P_useful_kW']:.2f} kW")
    print(f"• Rotor Aerodynamic Power      : {overall_res['P_rot_kW']:.2f} kW")
    print(f"• Shaft Power                  : {overall_res['P_shaft_kW']:.2f} kW")
    print(f"• Electrical Power Input       : {overall_res['P_elec_kW']:.2f} kW")
    print("-" * 72)
    print(f"• Overall Machine Efficiency   : {overall_res['eta_overall'] * 100:.2f} %")
    print("=" * 72)

    return {
        "design": selected_design,
        "triangles": triangles,
        "airfoil": aero_res,
        "rotor_performance": rotor_perf,
        "overall": overall_res,
    }


if __name__ == "__main__":
    run_main_performance("config.yaml")