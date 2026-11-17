from pathlib import Path
import numpy as np
from scipy.interpolate import PchipInterpolator

_DATA_DIR = Path(__file__).resolve().parent

_CHART_FILES = {
    "Hub": _DATA_DIR / "sandrolini_rotor_hub.csv",
    "Mean": _DATA_DIR / "sandrolini_rotor_mean.csv",
    "Tip": _DATA_DIR / "sandrolini_rotor_tip.csv",
}

_interpolators: dict[str, tuple[PchipInterpolator, float, float]] = {}


def _load_section_interpolator(section: str) -> tuple[PchipInterpolator, float, float]:
    """Carica e costruisce l'interpolatore monotono PCHIP per una sezione radiale."""
    if section not in _CHART_FILES:
        raise ValueError(f"Sezione non valida '{section}'. Usa 'Hub', 'Mean' o 'Tip'.")

    csv_path = _CHART_FILES[section]
    if not csv_path.exists():
        raise FileNotFoundError(
            f"File CSV non trovato per la sezione {section}: {csv_path}"
        )

    # Legge solo le prime 2 colonne (D, phi_loss), compatibile anche con il CSV Tip a 4 colonne
    d_data, phi_data = np.loadtxt(
        csv_path, delimiter=",", skiprows=1, usecols=(0, 1), unpack=True
    )

    interp = PchipInterpolator(d_data, phi_data, extrapolate=False)
    return interp, float(d_data.min()), float(d_data.max())


def evaluate_phi_loss(section: str, diffusion_factor: float) -> float:
    """
    Restituisce il parametro di perdita adimensionale Phi = Y_P * sin(beta2') / (2 * sigma)
    dai grafici sperimentali del rotore di Sandrolini (1996).

    Parametri:
    - section: 'Hub', 'Mean' oppure 'Tip'
    - diffusion_factor: Fattore di diffusione di Lieblein D [-] (intervallo [0.0, 0.7])
    """
    sec_key = section.strip().capitalize()
    if sec_key not in _interpolators:
        _interpolators[sec_key] = _load_section_interpolator(sec_key)

    interp, d_min, d_max = _interpolators[sec_key]

    if diffusion_factor < d_min or diffusion_factor > d_max:
        raise ValueError(
            f"Diffusion Factor D = {diffusion_factor:.4f} nella sezione '{sec_key}' "
            f"fuori dal dominio del grafico Sandrolini [{d_min:.2f}, {d_max:.2f}]."
        )

    return float(interp(diffusion_factor))


if __name__ == "__main__":
    print("=== TEST INTERPOLATORI SANDROLINI (1996) ===")
    for sec in ("Hub", "Mean", "Tip"):
        print(f"{sec:<5} | D = 0.35 -> Phi = {evaluate_phi_loss(sec, 0.35):.5f}")