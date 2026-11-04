# =============================================================================
# BLOCCO DI TEST AUTONOMO
# =============================================================================
from efficiency import calculate_rotor_efficiency

if __name__ == "__main__":
    print("=== TEST AUTONOMO MODULO EFFICIENCY.PY ===\n")

    # Outputs ottenuti direttamente da losses.py
    mock_y_results = {
        "Y_P_hub": 0.1188,
        "Y_P_mean": 0.1990,
        "Y_P_tip": 0.3216,
        "Y_sg": 0.0057,
    }

    # Triangoli di velocita
    mock_triangles = {
        "Hub": {"w1": 50.57},
        "Mean": {"w1": 69.28, "U": 43.76, "c_theta2": 15.42},
        "Tip": {"w1": 89.09},
    }

    mock_chord = 0.12  # [m]
    mock_config = {
        "air_density_kg_m3": 1.2,
        "dynamic_viscosity_Pa_s": 1.81e-5,
    }

    results = calculate_rotor_efficiency(
        mock_y_results, mock_triangles, mock_chord, mock_config
    )

    print(f"Lavoro Eulero (L)    : {results['L_euler_J_kg']:.2f} J/kg")
    print(f"Re (raggio medio)    : {results['Re_mid']:.2e}")
    print(f"Fattore chi_Re       : {results['chi_Re']:.4f}")
    print(f"R_P medio (Simpson)  : {results['R_P_bar_J_kg']:.2f} J/kg")
    print(f"R_P* (corretto Re)   : {results['R_P_star_J_kg']:.2f} J/kg")
    print(f"R_sg (sec + gioco)   : {results['R_sg_J_kg']:.2f} J/kg")
    print(f"R_total              : {results['R_total_J_kg']:.2f} J/kg")
    print("-" * 40)
    print(f"Rendimento Rotore    : {results['eta_rot'] * 100:.2f} %")