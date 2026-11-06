import math
from pathlib import Path
from typing import Any
import numpy as np
import yaml

# Moduli dei colleghi
from thermo import operating_point
from machine import preliminary_design
from geometry import calculate_velocity_triangles
from airfoil_design.airfoil_inputs import prepara_input_airfoil
from airfoil_design.airfoil_main import esegui_airfoil
from airfoil_design.airfoil_machine import dimensionamento_geometrico, scelta_profilo

# Moduli di verifica prestazionale
from losses import compute_all_Y_loss_coefficients
from efficiency import calculate_rotor_efficiency
from overall_performance import calculate_overall_performance


def load_config(config_path: str = "config.yaml") -> dict[str, Any]:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path.resolve()}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_main_performance(config_path: str = "config.yaml") -> dict[str, Any]:
    config = load_config(config_path)

    # Caricamento configurazione airfoil
    airfoil_config_path = Path("airfoil_design/airfoil_config.yaml")
    with open(airfoil_config_path, "r", encoding="utf-8") as f:
        config_airfoil = yaml.safe_load(f)

    # Parametri di convergenza
    eta_assumed = float(
        config.get("rotor_efficiency_initial", config.get("initial_eta_guess", 0.80))
    )
    tolerance = float(config.get("tolerance", 1e-4))
    max_iter = int(config.get("max_iterations", 50))
    alpha = float(config.get("relaxation_factor", 0.5))

    print("=" * 70)
    print("      AXIAL JET FAN SIMULATION - MAIN PERFORMANCE PIPELINE")
    print("=" * 70 + "\n")

    selected_design: dict[str, Any] = {}
    triangles: dict[str, dict[str, float]] = {}
    aero_res: dict[str, Any] = {}
    y_results: dict[str, float] = {}
    eff_results: dict[str, float] = {}
    profile_name: str = "Undefined"
    converged = False

    print("-" * 70)
    print(f"{'Iter':<6} | {'eta_assumed':<12} | {'eta_calculated':<15} | {'Delta':<12}")
    print("-" * 70)

    for k in range(1, max_iter + 1):
        # 1. Punto operativo termodinamico
        flow_rate, specific_head, specific_work, rotor_power = operating_point(
            nominal_thrust=float(config["nominal_thrust_N"]),
            air_density=float(config["air_density_kg_m3"]),
            jet_velocity=float(config["jet_velocity_m_s"]),
            ambient_velocity=float(config["ambient_velocity_m_s"]),
            rotor_efficiency=eta_assumed,
        )

        # 2. Ottimizzazione elica preliminare
        tip_diameter = float(config["tip_diameter_fraction"]) * float(
            config["max_tip_diameter_m"]
        )
        specific_speeds = np.linspace(
            float(config["specific_speed_min"]),
            float(config["specific_speed_max"]),
            int(config["specific_speed_points"]),
        )

        results = [
            preliminary_design(
                float(omega_s),
                flow_rate=flow_rate,
                specific_head=specific_head,
                specific_work=specific_work,
                work_done_factor=float(config["work_done_factor"]),
                tip_diameter=tip_diameter,
                max_tip_diameter=float(config["max_tip_diameter_m"]),
                speed_of_sound=float(config["speed_of_sound_m_s"]),
                mach_limit=float(config["max_mach_number"]),
                section_count=int(config["number_of_sections"]),
            )
            for omega_s in specific_speeds
        ]

        feasible = [r for r in results if r["status"] == "PASS"]
        if not feasible:
            raise ValueError("No geometric configuration satisfied the design constraints.")

        selected_design = min(
            feasible,
            key=lambda c: math.hypot(c["psi_deviation_pct"], c["phi_deviation_pct"]),
        )

        # 3. Triangoli di velocita
        triangles = calculate_velocity_triangles(
            selected_design,
            specific_work=specific_work,
            work_done_factor=float(config["work_done_factor"]),
            speed_of_sound=float(config["speed_of_sound_m_s"]),
        )

        # 4. Verifica e geometria del profilo alare (Lieblein)
        dati_airfoil = prepara_input_airfoil(triangles, config_airfoil)
        verified = esegui_airfoil(dati_airfoil)
        if not verified:
            raise ValueError("The selected airfoil profile failed the aerodynamic checks.")

        profile_name, tmax_c, _ = scelta_profilo(dati_airfoil)

        h_blade, chord_val, sprog, Z_blades, delta_phi, seff, sigma_eff = dimensionamento_geometrico(
            dati_airfoil["rtip"],
            dati_airfoil["rhub"],
            dati_airfoil["rm"],
            dati_airfoil["AR"],
            dati_airfoil["sigma_prog"],
        )

        aero_res = {
            "profile": profile_name,
            "sigma_eff": float(sigma_eff),
            "chord": float(chord_val),
            "Z": int(Z_blades),
        }

        # 5. Coefficienti di perdita Y_P e Y_sg
        y_results = compute_all_Y_loss_coefficients(triangles, aero_res, selected_design)

        # 6. Bilancio energetico e rendimento rotore
        eff_results = calculate_rotor_efficiency(
            y_results, triangles, aero_res["chord"], config
        )

        eta_calc = eff_results["eta_rot"]
        delta_eta = abs(eta_calc - eta_assumed)

        print(f"{k:<6} | {eta_assumed:<12.5f} | {eta_calc:<15.5f} | {delta_eta:<12.5e}")

        if delta_eta < tolerance:
            converged = True
            print("-" * 70)
            print(f"✅ CONVERGENCE ACHIEVED at iteration {k}!\n")
            break

        eta_assumed = alpha * eta_calc + (1.0 - alpha) * eta_assumed

    if not converged:
        print("\n⚠️ Maximum iterations reached without full convergence.\n")

    # 7. Prestazioni complessive e gerarchia potenze (ISO 13350)
    overall_res = calculate_overall_performance(
        selected_design, triangles, eff_results, config
    )

    # =========================================================================
    # ENGLISH FINAL PERFORMANCE REPORT
    # =========================================================================
    print("=" * 70)
    print("                FINAL PROJECT PERFORMANCE REPORT")
    print("=" * 70)
    print(f"• Airfoil Profile Selected     : {aero_res['profile']}")
    print(f"• Number of Blades (Z)         : {aero_res['Z']}")
    print(f"• Rotational Speed             : {selected_design['rpm']:.1f} RPM")
    print("-" * 70)
    print(f"• Rotor Efficiency (eta_rot)   : {eff_results['eta_rot'] * 100:.2f} %")
    print(f"• Global Fluid Efficiency      : {overall_res['eta_global'] * 100:.2f} %")
    print(f"• Mechanical Efficiency (eta_m): {overall_res['eta_mech'] * 100:.2f} %")
    print(f"• Motor Efficiency (eta_mot)   : {overall_res['eta_motor'] * 100:.2f} %")
    print("-" * 70)
    print(f"• Useful Jet Power             : {overall_res['P_useful_kW']:.2f} kW")
    print(f"• Rotor Aerodynamic Power      : {overall_res['P_rot_kW']:.2f} kW")
    print(f"• Shaft Power                  : {overall_res['P_shaft_kW']:.2f} kW")
    print(f"• Electrical Power Input       : {overall_res['P_elec_kW']:.2f} kW")
    print("-" * 70)
    print(f"• Overall Machine Efficiency   : {overall_res['eta_overall'] * 100:.2f} %")
    print("=" * 70)

    return {
        "design": selected_design,
        "triangles": triangles,
        "airfoil": aero_res,
        "losses": y_results,
        "efficiency": eff_results,
        "overall": overall_res,
    }


if __name__ == "__main__":
    run_main_performance("config.yaml")