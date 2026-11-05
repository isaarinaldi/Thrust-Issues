import os
import yaml
from main_performance import run_main_performance


def ensure_config_exists(config_path: str = "config.yaml") -> bool:
    """Verifica se config.yaml esiste sul disco; se manca, genera un file di test temporaneo."""
    if not os.path.exists(config_path):
        print(f"⚠️ '{config_path}' non trovato: creazione file temporaneo di test...")
        test_config = {
            "nominal_thrust_N": 650.0,
            "air_density_kg_m3": 1.2,
            "dynamic_viscosity_Pa_s": 1.81e-5,
            "max_tip_diameter_m": 1.120,
            "tip_clearance_mm": 2.8,
            "mechanical_efficiency": 0.95,
            "motor_efficiency": 0.90,
            "initial_eta_guess": 0.88,
            "tolerance": 1e-4,
            "max_iterations": 50,
            "relaxation_factor": 0.5,
        }
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(test_config, f)
        return True
    return False


def test_main_performance_pipeline():
    print("=== TEST COMPLETO DI INTEGRATORE MAIN_PERFORMANCE.PY ===\n")

    config_path = "../config.yaml"
    is_temp = ensure_config_exists(config_path)

    try:
        # Esecuzione del flusso di simulazione completo
        results = run_main_performance(config_path)

        eff_res = results["efficiency"]
        overall_res = results["overall"]

        # 1. Verifiche di integrità fisica su Rendimenti
        assert 0.70 <= eff_res["eta_rot"] <= 0.95, (
            f"Rendimento rotore non fisico: {eff_res['eta_rot']}"
        )
        assert 0.60 <= overall_res["eta_global"] <= 0.95, (
            f"Rendimento globale non fisico: {overall_res['eta_global']}"
        )

        # 2. Verifica Gerarchia delle Potenze: P_elec > P_shaft > P_rot > P_useful
        p_useful = overall_res["P_useful_kW"]
        p_rot = overall_res["P_rot_kW"]
        p_shaft = overall_res["P_shaft_kW"]
        p_elec = overall_res["P_elec_kW"]

        assert p_elec >= p_shaft >= p_rot >= p_useful, (
            f"Inversione non fisica nella gerarchia delle potenze:\n"
            f"P_elec={p_elec:.2f}kW, P_shaft={p_shaft:.2f}kW, "
            f"P_rot={p_rot:.2f}kW, P_useful={p_useful:.2f}kW"
        )

        # 3. Verifica Spinta erogata (ISO 13350)
        assert overall_res["thrust_N"] > 0, "Spinta erogata non valida (<= 0 N)"

        print("\n✅ TUTTI I CONTROLLI E LE ASSERZIONI FISICHE SONO STATI SUPERATI CON SUCCESSO!")

    finally:
        # Se il file config.yaml era temporaneo, viene rimosso alla fine del test
        if is_temp and os.path.exists(config_path):
            os.remove(config_path)


if __name__ == "__main__":
    test_main_performance_pipeline()