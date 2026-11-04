import math
from pathlib import Path
from typing import Any
import numpy as np
import yaml

# Import dei moduli per perdite, efficienza e prestazioni complessive
from losses import compute_all_Y_loss_coefficients
from efficiency import calculate_rotor_efficiency
from overall_performance import calculate_overall_performance

# Import dei moduli dei colleghi per termodinamica, progettazione e triangoli
from thermo import operating_point
from machine import preliminary_design
from geometry import calculate_velocity_triangles


def load_config(config_path: str = "config.yaml") -> dict[str, Any]:
    """
    Carica il file di configurazione config.yaml.
    Solleva FileNotFoundError se il file non esiste sul disco.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"File di configurazione non trovato: {path.resolve()}")

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError("Il file config.yaml deve contenere una struttura dizionario/mapping.")

    return config


def run_main_performance(config_path: str = "config.yaml") -> dict[str, Any]:
    """
    Esegue il ciclo iterativo di convergenza sul rendimento della girante (eta_rot),
    interfacciandosi con i moduli dei colleghi (thermo, machine, geometry)
    e calcola le prestazioni complessive finali della macchina.
    """
    config = load_config(config_path)

    # 1. Parametri di controllo dell'iterazione con valori di fallback sicuri
    eta_assumed = float(config.get("rotor_efficiency_initial", config.get("initial_eta_guess", 0.80)))
    tolerance = float(config.get("tolerance", 1e-4))
    max_iter = int(config.get("max_iterations", 50))
    alpha = float(config.get("relaxation_factor", 0.5))

    # Parametri operativi e fisici da config.yaml
    nominal_thrust = float(config["nominal_thrust_N"])
    air_density = float(config["air_density_kg_m3"])
    jet_velocity = float(config["jet_velocity_m_s"])
    ambient_velocity = float(config["ambient_velocity_m_s"])
    work_done_factor = float(config["work_done_factor"])
    max_tip_diameter = float(config["max_tip_diameter_m"])
    diameter_fraction = float(config["tip_diameter_fraction"])
    speed_min = float(config["specific_speed_min"])
    speed_max = float(config["specific_speed_max"])
    speed_points = int(config["specific_speed_points"])
    speed_of_sound = float(config["speed_of_sound_m_s"])
    mach_limit = float(config["max_mach_number"])
    section_count = int(config["number_of_sections"])

    tip_diameter = diameter_fraction * max_tip_diameter

    print("=" * 65)
    print("      SIMULAZIONE JET FAN ASSIALE - MAIN PERFORMANCE")
    print("=" * 65 + "\n")

    selected_design: dict[str, Any] = {}
    triangles: dict[str, dict[str, float]] = {}
    y_results: dict[str, float] = {}
    eff_results: dict[str, float] = {}
    converged = False

    # Dati aerodinamici provvisori (in attesa del completamento di aerodynamics.py)
    mock_aero = {"sigma_eff": 1.12, "Z": 12}
    chord_val = 0.12  # Corda fittizia [m]

    print("-" * 65)
    print(f"{'Iter':<6} | {'eta_assumed':<12} | {'eta_calculated':<15} | {'Delta':<12}")
    print("-" * 65)

    for k in range(1, max_iter + 1):
        # A. Punto operativo termodinamico (thermo.py)
        flow_rate, specific_head, specific_work, rotor_power = operating_point(
            nominal_thrust=nominal_thrust,
            air_density=air_density,
            jet_velocity=jet_velocity,
            ambient_velocity=ambient_velocity,
            rotor_efficiency=eta_assumed,
        )

        # B. Scansione sulla velocita specifica ed elica ottimale (machine.py)
        specific_speeds = np.linspace(speed_min, speed_max, speed_points)
        results = [
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

        feasible = [r for r in results if r["status"] == "PASS"]
        if not feasible:
            raise ValueError("Nessuna configurazione geometrica rispetta i vincoli di mozzo e Mach.")

        # Selezione della macchina ottimale (minimo scostamento dai coefficienti di Eckert)
        selected_design = min(
            feasible,
            key=lambda candidate: math.hypot(
                candidate["psi_deviation_pct"], candidate["phi_deviation_pct"]
            ),
        )

        # C. Triangoli di velocita (geometry.py)
        triangles = calculate_velocity_triangles(
            selected_design,
            specific_work=specific_work,
            work_done_factor=work_done_factor,
            speed_of_sound=speed_of_sound,
        )

        # D. Coefficienti di perdita Y_P e Y_sg (losses.py)
        y_results = compute_all_Y_loss_coefficients(triangles, mock_aero, selected_design)

        # E. Rendimento del rotore eta_rot (efficiency.py)
        eff_results = calculate_rotor_efficiency(y_results, triangles, chord_val, config)

        eta_calc = eff_results["eta_rot"]
        delta_eta = abs(eta_calc - eta_assumed)

        print(f"{k:<6} | {eta_assumed:<12.5f} | {eta_calc:<15.5f} | {delta_eta:<12.5e}")

        # F. Controllo tolleranza di convergenza
        if delta_eta < tolerance:
            converged = True
            print("-" * 65)
            print(f"✅ CONVERGENZA RAGGIUNTA all'iterazione {k}!\n")
            break

        # Aggiornamento mediante rilassamento lineare
        eta_assumed = alpha * eta_calc + (1.0 - alpha) * eta_assumed

    if not converged:
        print("\n⚠️ Raggiunto il limite massimo di iterazioni senza convergenza stazionaria.\n")

    # G. Prestazioni complessive e spinta ISO 13350 (overall_performance.py)
    overall_res = calculate_overall_performance(selected_design, triangles, eff_results, config)

    # Report finale a schermo
    print("=" * 65)
    print("                    REPORT FINALE DI PROGETTO")
    print("=" * 65)
    print(f"• Diametro Apicale (D_tip)      : {selected_design['D_tip_m']:.4f} m")
    print(f"• Diametro Mozzo (D_hub)        : {selected_design['D_hub_m']:.4f} m")
    print(f"• Rapporto di Mozzo (chi)       : {selected_design['chi']:.4f}")
    print(f"• Velocita Assiale (c_m)        : {selected_design['c_m_m_s']:.2f} m/s")
    print(f"• Velocita Periferica (U_tip)   : {selected_design['U_tip_m_s']:.2f} m/s")
    print(f"• Regime di Rotazione (RPM)     : {selected_design['rpm']:.1f} rpm")
    print(f"• Mach Relativo Massimo         : {selected_design['mach_max']:.3f}")
    print("-" * 65)
    print(f"• Rendimento Rotore (eta_rot)   : {eff_results['eta_rot'] * 100:.2f} %")
    print(f"• Rendimento Globale Fluido     : {overall_res['eta_global'] * 100:.2f} %")
    print(f"• Rendimento Elettromeccanico   : {overall_res['eta_overall'] * 100:.2f} %")
    print("-" * 65)
    print(f"• Spinta Richiesta (ISO 13350)  : {config['nominal_thrust_N']:.2f} N")
    print(f"• Spinta Calcolata dal Getto    : {overall_res['thrust_N']:.2f} N")
    print(f"• Margine di Spinta             : {overall_res['thrust_margin_percent']:+.2f} %")
    print(
        f"• Esito Verifica Spinta         : {'✅ SODDISFATTO' if overall_res['thrust_verified'] else '❌ NON SODDISFATTO'}")
    print("-" * 65)
    print(f"• Potenza Cinetica Utile        : {overall_res['P_useful_kW']:.2f} kW")
    print(f"• Potenza Aerodinamica Rotore   : {overall_res['P_rot_kW']:.2f} kW")
    print(f"• Potenza Meccanica all'Asse    : {overall_res['P_shaft_kW']:.2f} kW")
    print(f"• Potenza Elettrica Assorbita   : {overall_res['P_elec_kW']:.2f} kW")
    print("=" * 65)

    return {
        "design": selected_design,
        "triangles": triangles,
        "losses": y_results,
        "efficiency": eff_results,
        "overall": overall_res,
    }


if __name__ == "__main__":
    run_main_performance("config.yaml")