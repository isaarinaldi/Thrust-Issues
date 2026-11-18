import csv
from collections.abc import Mapping
from pathlib import Path

import yaml

if __package__:
    from .airfoil_losses import interpola_curva, interpola_2d
    from .airfoil_machine import (
        calcola_calettamento,
        calcola_deviazione_lieblein,
        calcola_diffusion_factor,
        calcola_incidenza_lieblein,
        convergenza_curvatura,
        curvatura_corretta,
        curvatura_iniziale,
        dimensionamento_geometrico,
        scelta_profilo,
        verifica_aerodinamica_finale,
    )
else:
    from airfoil_losses import interpola_curva, interpola_2d
    from airfoil_machine import (
        calcola_calettamento,
        calcola_deviazione_lieblein,
        calcola_diffusion_factor,
        calcola_incidenza_lieblein,
        convergenza_curvatura,
        curvatura_corretta,
        curvatura_iniziale,
        dimensionamento_geometrico,
        scelta_profilo,
        verifica_aerodinamica_finale,
    )

PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"


def _leggi_tabella(percorso: Path, colonne: tuple[str, ...]) -> list[dict[str, str]]:
    with percorso.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None or not set(colonne).issubset(reader.fieldnames):
            raise ValueError(f"Tabella CSV non valida: {percorso}")
        return list(reader)


def progetta(dati, tabelle):
    profilo, tmax_c, sigma_prog = scelta_profilo(dati)
    print("Profilo selezionato:", profilo)
    print("Spessore relativo:", tmax_c)
    print("Solidità preliminare:", sigma_prog)
    D = calcola_diffusion_factor(dati)
    print("Diffusion Factor:", round(D, 4))
    if D <= dati["D_max"]:
        print("Solidita preliminare accettata")
    else:
        return False
    theta0 = curvatura_iniziale(dati)
    print("Curvatura iniziale:", theta0, "gradi")

    punti_i0 = tabelle["i0"]
    i0_10 = interpola_2d(punti_i0, dati["beta1"], sigma_prog)

    print("Incidenza di riferimento:", round(i0_10, 3), "gradi")

    # INTERPOLAZIONE DEL COEFFICIENTE n

    punti_n = tabelle["n"]
    n = interpola_2d(punti_n, dati["beta1"], sigma_prog)

    print("Coefficiente n:", round(n, 4))

    # PRIMA INCIDENZA OTTIMALE DI LIEBLEIN

    i_rif_0 = calcola_incidenza_lieblein(
        theta0, i0_10, dati["Kti"], dati["Ksh"], n
    )

    print("Prima incidenza ottimale:", round(i_rif_0, 3), "gradi")

    # 9. PRIMA DEVIAZIONE DI LIEBLEIN

    tabella_deviazione = tabelle["deviazione"]
    angoli_delta = [float(riga["alpha_deg"]) for riga in tabella_deviazione]
    valori_m = [float(riga["m"]) for riga in tabella_deviazione]
    valori_b = [float(riga["b"]) for riga in tabella_deviazione]
    punti_delta0 = tabelle["delta0"]
    delta0_10 = interpola_2d(punti_delta0, dati["beta1"], sigma_prog)

    m = interpola_curva(angoli_delta, valori_m, dati["beta1"])
    b = interpola_curva(angoli_delta, valori_b, dati["beta1"])

    delta_0 = calcola_deviazione_lieblein(
        theta0, delta0_10, m, b, sigma_prog, dati["Kdelta_t"]
    )

    print("Prima deviazione:", round(delta_0, 3), "gradi")

    # PRIMA CURVATURA CORRETTA

    theta1 = curvatura_corretta(
        dati["beta1"], dati["beta2"], i_rif_0, delta_0
    )

    print("Prima curvatura corretta:", round(theta1, 3), "gradi")

    # CONVERGENZA ITERATIVA DELLA CURVATURA

    theta_conv, i_conv, delta_conv, n_iter = convergenza_curvatura(
        theta1,
        dati["beta1"], dati["beta2"],
        i0_10, dati["Kti"], dati["Ksh"], n,
        delta0_10, m, b, sigma_prog, dati["Kdelta_t"],
        dati["epsilon_theta_deg"], dati["max_iter_theta"]
    )

    print("Curvatura convergente:", round(theta_conv, 4), "gradi")
    print("Incidenza finale:", round(i_conv, 4), "gradi")
    print("Deviazione finale:", round(delta_conv, 4), "gradi")
    print("Numero di iterazioni:", n_iter)

    # DIMENSIONAMENTO GEOMETRICO

    h, c, sprog, Z, delta_phi, seff, sigma_eff = dimensionamento_geometrico(
        dati["rtip"], dati["rhub"], dati["rm"],
        dati["AR"], sigma_prog
    )

    print("Altezza pala:", round(h, 4), "m")
    print("Corda:", round(c, 4), "m")
    print("Passo preliminare:", round(sprog, 4), "m")
    print("Numero di pale:", Z)
    print("Spaziatura angolare:", round(delta_phi, 3), "gradi")
    print("Passo effettivo:", round(seff, 4), "m")
    print("Solidita effettiva:", round(sigma_eff, 4))

    # INCIDENZA E DEVIAZIONE EFFETTIVE

    i0_eff = interpola_2d(punti_i0, dati["beta1"], sigma_eff)
    n_eff = interpola_2d(punti_n, dati["beta1"], sigma_eff)
    delta0_eff = interpola_2d(punti_delta0, dati["beta1"], sigma_eff)

    i_eff = calcola_incidenza_lieblein(
        theta_conv, i0_eff, dati["Kti"], dati["Ksh"], n_eff
    )

    delta_eff = calcola_deviazione_lieblein(
        theta_conv, delta0_eff, m, b, sigma_eff, dati["Kdelta_t"]
    )

    # ANGOLO DI CALETTAMENTO

    gamma = calcola_calettamento(
        dati["beta1"], dati["beta2"], i_eff, delta_eff
    )

    print("Incidenza effettiva:", round(i_eff, 3), "gradi")
    print("Deviazione effettiva:", round(delta_eff, 3), "gradi")
    print("Angolo di calettamento:", round(gamma, 3), "gradi")

    # VERIFICA AERODINAMICA FINALE

    dati_finali = dati.copy()
    dati_finali["sigma_prog"] = sigma_eff

    D_eff = calcola_diffusion_factor(dati_finali)

    de_haller = dati["W2"] / dati["W1"]

    verifica = verifica_aerodinamica_finale(
        D_eff,
        de_haller,
        dati["D_max"],
        dati["de_haller_min"]
    )

    print("Diffusion Factor finale:", round(D_eff, 4))
    print("Rapporto De Haller:", round(de_haller, 4))

    if verifica:
        print("VERIFIED AIRFOIL PROFILE")
        print("Solidita effettiva approvata:", sigma_eff)
        print("Corda finale:", round(c, 4), "m")
        print("Numero di pale:", Z)
        print("Angolo di calettamento:", round(gamma, 3), "gradi")

        return True

    else:
        if de_haller < dati["de_haller_min"]:
            raise ValueError(
                "De Haller non soddisfatto: modificare i triangoli di velocita"
            )

        return False


def main(
    config_path: Path | None = None,
    input_data: Mapping[str, object] | None = None,
) -> bool:
    if config_path is None:
        config_path = PROJECT_DIR / "airfoil_config.yaml"

    with Path(config_path).open("r", encoding="utf-8") as file:
        dati_base = yaml.safe_load(file)
    if not isinstance(dati_base, Mapping):
        raise ValueError(
            f"Il file di configurazione {config_path} deve contenere "
            "una mappa YAML."
        )
    dati_base = dict(dati_base)
    if input_data is not None:
        if not isinstance(input_data, Mapping):
            raise TypeError("Gli input aerodinamici devono essere una mappa.")
        dati_base.update(input_data)

    tabelle = {
        "i0": [
            (float(r["alpha_deg"]), float(r["sigma"]), float(r["i0_10_deg"]))
            for r in _leggi_tabella(
                DATA_DIR / "lieblein_i0.csv",
                ("alpha_deg", "sigma", "i0_10_deg"),
            )
        ],
        "n": [
            (float(r["alpha_deg"]), float(r["sigma"]), float(r["n"]))
            for r in _leggi_tabella(
                DATA_DIR / "lieblein_n.csv", ("alpha_deg", "sigma", "n")
            )
        ],
        "delta0": [
            (
                float(r["alpha_deg"]),
                float(r["sigma"]),
                float(r["delta0_10_deg"]),
            )
            for r in _leggi_tabella(
                DATA_DIR / "lieblein_delta0_sigma.csv",
                ("alpha_deg", "sigma", "delta0_10_deg"),
            )
        ],
        "deviazione": _leggi_tabella(
            DATA_DIR / "lieblein_deviazione.csv",
            ("alpha_deg", "m", "b"),
        ),
    }

    soluzione_trovata = False
    sigma_iniziale = float(dati_base["sigma_prog"])
    sigma_step = float(dati_base["sigma_step"])
    sigma_max = float(dati_base["sigma_max"])
    max_iter_sigma = int(dati_base["max_iter_sigma"])
    if sigma_iniziale <= 0 or sigma_step <= 0 or sigma_max < sigma_iniziale:
        raise ValueError("Limiti di solidita non validi nella configurazione.")
    if max_iter_sigma < 1:
        raise ValueError("max_iter_sigma deve essere almeno 1.")

    for tentativo in range(max_iter_sigma):
        sigma = round(sigma_iniziale + tentativo * sigma_step, 6)
        if sigma > sigma_max:
            break

        dati_tentativo = dict(dati_base)
        dati_tentativo["sigma_prog"] = sigma

        print("Tentativo:", tentativo + 1, "Solidita:", sigma)

        if progetta(dati_tentativo, tabelle):
            return True

    raise ValueError("Nessuna soluzione trovata nei limiti di solidita")


def esegui_airfoil(dati: Mapping[str, object]) -> bool:
    """Run the airfoil design using inputs from the preliminary design."""
    return main(input_data=dati)


if __name__ == "__main__":
    main()
