from pathlib import Path
import numpy as np
from scipy.interpolate import interp1d

# Individua la cartella 'data/' in modo dinamico rispetto alla posizione di questo file
_DATA_DIR = Path(__file__).resolve().parent
_CSV_PATH = _DATA_DIR / "theta_l_sandrolini.csv"


def get_theta_l_interpolator():
    """
    Carica i punti digitalizzati del grafico Sandrolini (1996) (DR vs theta/l)
    e restituisce la funzione interpolatrice cubica.

    Solleva FileNotFoundError se 'theta_l_sandrolini.csv' non e' nella cartella 'data/'.
    """
    if not _CSV_PATH.exists():
        raise FileNotFoundError(
            f"File dei dati non trovato in: {_CSV_PATH}\n"
            "Assicurati che 'theta_l_sandrolini.csv' sia presente nella cartella 'data/'."
        )

    # Caricamento dei punti ignorando l'intestazione CSV
    dr_data, theta_l_data = np.loadtxt(
        _CSV_PATH, delimiter=",", skiprows=1, unpack=True
    )

    # Interpolatore cubico con blocco agli estremi (bounds_error=True)
    return interp1d(dr_data, theta_l_data, kind="cubic", bounds_error=True)


# Variable interna per memorizzare l'istanza dell'interpolatore (lazy loading)
_interpolator = None


def evaluate_theta_l(dr: float) -> float:
    """
    Restituisce lo spessore di quantita' di moto ridotto (theta/l)
    dato il Local Diffusion Ratio di Lieblein (DR = w1 / w2).

    Esempio di utilizzo:
        from data.loss_charts import evaluate_theta_l
        val = evaluate_theta_l(1.4)
    """
    global _interpolator
    if _interpolator is None:
        _interpolator = get_theta_l_interpolator()

    return float(_interpolator(dr))


if __name__ == "__main__":
    # Test esecuzione autonoma
    print("=== TEST MODULO DATA/LOSS_CHARTS.PY ===")
    print(f"Lettura file CSV da: {_CSV_PATH.name}")

    test_dr = 1.5
    theta_l_res = evaluate_theta_l(test_dr)
    print(f"DR = {test_dr:.2f}  ->  theta/l = {theta_l_res:.4f}")

    # Verifica blocco fuori scala
    try:
        evaluate_theta_l(2.5)
    except ValueError as err:
        print("\nVerifica bounds_error=True superata:")
        print(f"ValueError intercettato: {err}")