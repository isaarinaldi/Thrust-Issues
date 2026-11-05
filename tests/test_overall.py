from overall_performance import calculate_overall_performance


def test_overall_performance():
    print("=== TEST OVERALL MACHINE PERFORMANCE (ISO 13350) ===\n")

    # 1. Dati estratti da config.yaml (nominal_thrust_N e un dato IMPOSITO di progetto)
    config_yaml = {
        "nominal_thrust_N": 650.0,       # F_nom [N] impostato nel config.yaml
        "air_density_kg_m3": 1.2,        # rho [kg/m^3]
        "mechanical_efficiency": 0.95,   # eta_m [-]
        "motor_efficiency": 0.90,        # eta_el [-]
    }

    # 2. Output dal dimensionamento geometrico (preliminary_design.py)
    mock_design = {
        "D_tip_m": 1.1144,
        "D_hub_m": 0.5572,
        "c_m_m_s": 27.65,
    }

    # 3. Output dai triangoli di velocita (aerodynamics.py)
    mock_triangles = {
        "Tip": {"c_theta2": 10.2},
        "Mean": {"U": 43.76, "c_theta2": 15.42},
    }

    # 4. Output dal modulo perdite ed efficienza (efficiency.py)
    mock_eff_result = {
        "L_euler_J_kg": 674.8,
        "eta_rot": 0.885,  # Rendimento del rotore ipotizzato all'88.5%
    }

    # Esecuzione del calcolo delle prestazioni complessive
    results = calculate_overall_performance(
        mock_design, mock_triangles, mock_eff_result, config_yaml
    )

    # Stampa formattata dei risultati a schermo
    f_nom = config_yaml["nominal_thrust_N"]
    f_calc = results["thrust_N"]

    print(f"Spinta Nominale da config.yaml : {f_nom:.2f} N")
    print(f"Spinta Calcolata dal getto      : {f_calc:.2f} N")
    print(f"Margine di Spinta ottenuto      : {results['thrust_margin_percent']:.2f} %")
    print(f"Esito Verifica Spinta           : {'✅ SODDISFATTA' if results['thrust_verified'] else '❌ INSUFFICIENTE'}\n")

    print(f"Portata massica (m_dot)         : {results['mass_flow_rate_kg_s']:.2f} kg/s")
    print(f"Rendimento Rotore (eta_rot)     : {mock_eff_result['eta_rot'] * 100:.2f} %")
    print(f"Perdita di Swirl (R_sw)         : {results['R_sw_J_kg']:.2f} J/kg")
    print(f"Rendimento Globale Fluido       : {results['eta_global'] * 100:.2f} %\n")

    print("--- GERARCHIA DELLE POTENZE ---")
    print(f"P_utile (cinetica getto)        : {results['P_useful_kW']:.2f} kW")
    print(f"P_rotore (aerodinamica)         : {results['P_rot_kW']:.2f} kW")
    print(f"P_asse (meccanica)              : {results['P_shaft_kW']:.2f} kW")
    print(f"P_elettrica (assorbita rete)    : {results['P_elec_kW']:.2f} kW")
    print(f"Rendimento Elettromeccanico     : {results['eta_overall'] * 100:.2f} %\n")

    # CONTROLLI AUTOMATICI (Asserzioni di integrita fisica)
    assert results["thrust_verified"], (
        f"ERRORE: Spinta insufficiente ({f_calc:.2f} N < {f_nom:.2f} N)"
    )
    assert (
        results["P_elec_kW"]
        > results["P_shaft_kW"]
        > results["P_rot_kW"]
        > results["P_useful_kW"]
    ), "ERRORE: La gerarchia delle potenze (P_elec > P_shaft > P_rot > P_useful) non e rispettata"
    assert 0.70 <= results["eta_global"] <= 0.95, (
        f"ERRORE: Rendimento globale non fisico: {results['eta_global']}"
    )

    print("✅ TEST SUPERATO: Tutti i controlli fisici e il vincolo sulla spinta da config.yaml sono verificati!")


if __name__ == "__main__":
    test_overall_performance()