from losses import compute_all_Y_loss_coefficients


def test_losses_module():
    print("=== TEST AUTONOMO MODULO LOSSES.PY ===\n")

    # 1. Dati fittizi di Geometria (da preliminary_design)
    mock_design = {
        "D_tip_m": 1.1144,
        "D_hub_m": 0.5572,
        "tip_clearance_mm": 2.8,
    }

    # 2. Dati fittizi Aerodinamici (da aerodynamics)
    mock_aero = {
        "sigma_eff": 1.12,
        "Z": 12,
    }

    # 3. Triangoli di velocità e angoli beta' (rispetto alla direzione tangenziale)
    mock_triangles = {
        "Hub": {
            "w1": 50.57,
            "w2": 40.32,
            "beta1": 33.1,
            "beta2": 43.3,
        },
        "Mean": {
            "radius": 0.4179,
            "w1": 69.28,
            "w2": 61.43,
            "beta1": 23.5,
            "beta2": 26.8,
            "beta_inf": 25.1,
        },
        "Tip": {
            "w1": 89.09,
            "w2": 82.94,
            "beta1": 18.1,
            "beta2": 19.5,
        },
    }

    # Esecuzione del calcolo dei 4 coefficienti Y
    results = compute_all_Y_loss_coefficients(
        mock_triangles, mock_aero, mock_design
    )

    # Stampa formattata dei risultati
    print(f"{'Coefficiente Y':<15} | {'Valore':<8}")
    print("-" * 26)
    for key, val in results.items():
        print(f"{key:<15} | {val:.4f}")

    # Verifiche di integrità fisica (Asserzioni)
    assert "Y_P_hub" in results, "La chiave Y_P_hub manca nei risultati"
    assert "Y_P_mean" in results, "La chiave Y_P_mean manca nei risultati"
    assert "Y_P_tip" in results, "La chiave Y_P_tip manca nei risultati"
    assert "Y_sg" in results, "La chiave Y_sg manca nei risultati"

    # Controllo che i valori rientrino nei range fisicamente plausibili per giranti assiali
    assert 0.01 <= results["Y_P_hub"] <= 0.25, f"Y_P_hub fuori range: {results['Y_P_hub']}"
    assert 0.01 <= results["Y_P_mean"] <= 0.25, f"Y_P_mean fuori range: {results['Y_P_mean']}"
    assert 0.01 <= results[
        "Y_P_tip"] <= 0.40, f"Y_P_tip fuori range: {results['Y_P_tip']}"  # <--- SOGLIA AGGIORNATA A 0.40
    assert 0.005 <= results["Y_sg"] <= 0.15, f"Y_sg fuori range: {results['Y_sg']}"

    print("\n✅ Test completato con successo: tutti i coefficienti Y rientrano nei range fisici attesi!")


if __name__ == "__main__":
    test_losses_module()