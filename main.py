from pathlib import Path

import yaml

from machine import (
    operating_point,
    eckert_search,
    select_design,
    check_continuity,
)

from geometry import (
    annulus_geometry,
    hub_ratio_from_continuity,
    calculate_velocity_triangles,
)


def main():

    # ==========================================
    # 1. LETTURA INPUT
    # ==========================================

    config_path = Path(__file__).resolve().parent / "config.yaml"

    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    # ==========================================
    # 2. PUNTO DI FUNZIONAMENTO
    # ==========================================

    flow_rate, specific_head, specific_work, rotor_power = operating_point(
        nominal_thrust=config["nominal_thrust"],
        air_density=config["air_density"],
        jet_velocity=config["jet_velocity"],
        ambient_velocity=config["ambient_velocity"],
        rotor_efficiency_initial=config["rotor_efficiency_initial"],
    )

    print("\nDATI DI FUNZIONAMENTO")
    print(f"Portata Q = {flow_rate:.2f} m³/s")
    print(f"Energia specifica gH = {specific_head:.2f} J/kg")
    print(f"Lavoro specifico L = {specific_work:.2f} J/kg")
    print(f"Potenza P = {rotor_power / 1000:.2f} kW")

    # ==========================================
    # 3. RICERCA ECKERT
    # ==========================================

    results = eckert_search(
        flow_rate=flow_rate,
        specific_head=specific_head,
        max_tip_diameter=config["max_tip_diameter"],
        tip_diameter_fraction=config["tip_diameter_fraction"],
        specific_speed_min=config["specific_speed_min"],
        specific_speed_max=config["specific_speed_max"],
        specific_speed_points=config["specific_speed_points"],
    )

    print("\nRICERCA ECKERT")
    print(
        f"{'Omega_s':>8} "
        f"{'Phi':>7} "
        f"{'Psi':>7} "
        f"{'Chi':>8} "
        f"{'Dtip [m]':>10} "
        f"{'Diametro OK':>12}"
    )

    for result in results:
        check = "SI" if result["diameter_ok"] else "NO"

        print(
            f"{result['specific_speed']:8.2f} "
            f"{result['phi']:7.3f} "
            f"{result['psi']:7.3f} "
            f"{result['chi']:8.3f} "
            f"{result['tip_diameter']:10.4f} "
            f"{check:>12}"
        )

    # ==========================================
    # 4. SELEZIONE DELLA CONFIGURAZIONE
    # ==========================================

    if not any(result["diameter_ok"] for result in results):
        print("\nNessuna configurazione rispetta il limite sul diametro.")
        return

    selected_design = select_design(results)

    print("\nCONFIGURAZIONE SELEZIONATA")
    print(f"Velocità specifica = {selected_design['specific_speed']:.2f}")
    print(f"Phi = {selected_design['phi']:.4f}")
    print(f"Psi = {selected_design['psi']:.4f}")
    print(f"Chi = {selected_design['chi']:.4f}")
    print(
        f"Velocità angolare = "
        f"{selected_design['angular_velocity']:.2f} rad/s"
    )
    print(
        f"Velocità di rotazione = "
        f"{selected_design['rotational_speed']:.1f} giri/min"
    )
    print(f"Utip = {selected_design['tip_speed']:.2f} m/s")
    print(
        f"Diametro limite = "
        f"{selected_design['tip_diameter_limit']:.4f} m"
    )

    # ==========================================
    # 5. GEOMETRIA
    # ==========================================

    # Conserviamo il riferimento letto dal diagramma
    chi_eckert = selected_design["chi"]

    # Correzione del rapporto hub-to-tip dalla continuità
    selected_design["chi"] = hub_ratio_from_continuity(
        flow_rate=flow_rate,
        tip_diameter=selected_design["tip_diameter"],
        phi=selected_design["phi"],
        tip_speed=selected_design["tip_speed"],
    )

    # Geometria aggiornata con il nuovo chi
    geometry = annulus_geometry(
        tip_diameter=selected_design["tip_diameter"],
        chi=selected_design["chi"],
    )

    print("\nVERIFICA DI CONTINUITÀ")
    print(f"Portata di progetto = {flow_rate:.3f} m³/s")
    print(f"Chi di riferimento Eckert = {chi_eckert:.4f}")
    print(f"Chi calcolato per conservare la portata = {selected_design['chi']:.4f}")

    # ==========================================
    # 6. DATI DEFINITIVI E VERIFICA DI CONTINUITÀ
    # ==========================================

    # Velocità meridiana adottata [m/s]
    c_m = selected_design["phi"] * selected_design["tip_speed"]

    # La portata di progetto rimane quella iniziale [m³/s]
    flow_rate_design = flow_rate

    continuity = check_continuity(
        flow_rate=flow_rate,
        phi=selected_design["phi"],
        tip_speed=selected_design["tip_speed"],
        annulus_area=geometry["annulus_area"],
        jet_velocity=config["jet_velocity"],
    )

    print("\nGEOMETRIA DEFINITIVA DEL ROTORE")
    print(f"Chi = {selected_design['chi']:.4f}")
    print(f"Dtip = {geometry['tip_diameter']:.4f} m")
    print(f"Dhub = {geometry['hub_diameter']:.4f} m")
    print(f"Raggio hub = {geometry['hub_radius']:.4f} m")
    print(f"Raggio medio = {geometry['mean_radius']:.4f} m")
    print(f"Raggio tip = {geometry['tip_radius']:.4f} m")
    print(f"Altezza pala = {geometry['blade_height']:.4f} m")
    print(f"Area anulare = {geometry['annulus_area']:.4f} m²")

    # ==========================================
    # 7. TRIANGOLI DI VELOCITA'
    # ==========================================
    triangles = calculate_velocity_triangles(
        geometry=geometry,
        tip_speed=selected_design["tip_speed"],
        c_m=c_m,
        specific_head=specific_head,
        rotor_efficiency_initial=config["rotor_efficiency_initial"],
        work_done_factor=config["work_done_factor"],
    )

    print("\nTRIANGOLI DELLE VELOCITÀ")
    print(f"Cm = {c_m:.3f} m/s")
    print(f"Q = {flow_rate_design:.3f} m³/s")

    print(
        f"\n{'Sezione':>8} {'U':>9} {'Delta Cu':>10}"
        f" {'c2':>9} {'w1':>9} {'w2':>9}"
        f" {'alpha2':>9} {'beta1':>9} {'beta2':>9}"
    )

    for section, values in triangles.items():
        print(
            f"{section:>8}"
            f" {values['U']:9.3f}"
            f" {values['c_theta2']:10.3f}"
            f" {values['c2']:9.3f}"
            f" {values['w1']:9.3f}"
            f" {values['w2']:9.3f}"
            f" {values['alpha2']:9.2f}"
            f" {values['beta1']:9.2f}"
            f" {values['beta2']:9.2f}"
        )

    print("\nVelocità in m/s; angoli in gradi.")
    print("In tutte le sezioni: c1 = c3 = Cm; alpha1 = alpha3 = 90°.")

    # Risultati disponibili anche per gli altri moduli, senza cambiare
    # l'esecuzione standalone di python main.py.
    return {
        "flow_rate": flow_rate,
        "specific_head": specific_head,
        "specific_work": specific_work,
        "rotor_power": rotor_power,
        "selected_design": selected_design,
        "geometry": geometry,
        "continuity": continuity,
        "triangles": triangles,
    }


if __name__ == "__main__":
    main()