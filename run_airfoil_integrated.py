"""Run updated preliminary design and NACA65 airfoil design together.

This is deliberately a separate entry point: python preliminary_design.py continues to
run the colleagues' original preliminary design and is not modified in flow.
"""

from pathlib import Path
import yaml

from preliminary_design import main as preliminary_main
from airfoil_losses.airfoil_inputs import prepara_input_airfoil
from airfoil_losses.airfoil_main import esegui_airfoil


def run_integrated_airfoil():
    preliminary = preliminary_main()

    config = preliminary["selected_design"]
    triangles = preliminary["triangles"]

    root = Path(__file__).resolve().parent

    with (root / "config.yaml").open("r", encoding="utf-8") as handle:
        config_general = yaml.safe_load(handle)

    # Parametri Airfoil Design dal YAML principale
    config_airfoil = config_general["airfoil"]

    dati_airfoil = prepara_input_airfoil(
        triangles,
        config_airfoil,
        speed_of_sound=config_general["speed_of_sound"],
        air_density=config_general["air_density"],
        dynamic_viscosity=config_general["dynamic_viscosity"],
    )

    print("\nINPUT AIRFOIL DALLA SEZIONE MEDIA")
    for key in ("W1", "W2", "beta1", "beta2", "Ma", "Re", "rhub", "rm", "rtip"):
        print(f"  {key}: {dati_airfoil[key]:.5f}")

    print("\nPROGETTAZIONE DEL PROFILO ALARE NACA 65")
    verified = esegui_airfoil(dati_airfoil)
    if not verified:
        raise ValueError("Airfoil design non verificato.")

    return {
        "preliminary": preliminary,
        "airfoil_inputs": dati_airfoil,
        "airfoil_verified": verified,
    }


if __name__ == "__main__":
    run_integrated_airfoil()
