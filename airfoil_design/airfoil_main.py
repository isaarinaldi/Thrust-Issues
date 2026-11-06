import yaml
import csv
from machine import scelta_profilo, calcola_diffusion_factor, curvatura_iniziale, calcola_incidenza_lieblein, calcola_deviazione_lieblein, curvatura_corretta, convergenza_curvatura, dimensionamento_geometrico, calcola_calettamento, verifica_aerodinamica_finale
from losses import interpola_curva, interpola_2d

# ASSEGNAZIONE SOLIDITA PRELIMINARE


with open("config.yaml", "r", encoding="utf-8") as file:
    dati_base = yaml.safe_load(file)
def progetta(dati):
    profilo, tmax_c, sigma_prog = scelta_profilo(dati)
    print("Profilo selezionato:", profilo)
    print("Spessore relativo:", tmax_c)
    print("Solidità preliminare:", sigma_prog)
    D = calcola_diffusion_factor(dati)
    print("Diffusion Factor:", round(D, 4))
    if D <= dati["D_max"]: print("Solidita preliminare accettata")
    else: return False
    theta0 = curvatura_iniziale(dati)
    print("Curvatura iniziale:", theta0, "gradi")


    with open("data/lieblein_i0.csv", "r", encoding="utf-8", newline="") as file:
        punti_i0 = [
            (float(r["alpha_deg"]), float(r["sigma"]), float(r["i0_10_deg"]))
            for r in csv.DictReader(file)
        ]

    i0_10 = interpola_2d(punti_i0, dati["beta1"], sigma_prog)

    print("Incidenza di riferimento:", round(i0_10, 3), "gradi")

    # INTERPOLAZIONE DEL COEFFICIENTE n


    with open("data/lieblein_n.csv", "r", encoding="utf-8", newline="") as file:
        punti_n = [
            (float(r["alpha_deg"]), float(r["sigma"]), float(r["n"]))
            for r in csv.DictReader(file)
        ]

    n = interpola_2d(punti_n, dati["beta1"], sigma_prog)


    print("Coefficiente n:", round(n, 4))

    # PRIMA INCIDENZA OTTIMALE DI LIEBLEIN

    i_rif_0 = calcola_incidenza_lieblein(
        theta0, i0_10, dati["Kti"], dati["Ksh"], n
    )

    print("Prima incidenza ottimale:", round(i_rif_0, 3), "gradi")

    # 9. PRIMA DEVIAZIONE DI LIEBLEIN

    with open("data/lieblein_deviazione.csv", "r", encoding="utf-8", newline="") as file:
        righe_delta = list(csv.DictReader(file))

    angoli_delta = []
    valori_delta0 = []
    valori_m = []
    valori_b = []

    for riga in righe_delta:
        angoli_delta.append(float(riga["alpha_deg"]))
        valori_delta0.append(float(riga["delta0_10_deg"]))
        valori_m.append(float(riga["m"]))
        valori_b.append(float(riga["b"]))


    with open("data/lieblein_delta0_sigma.csv", "r", encoding="utf-8", newline="") as file:
        punti_delta0 = [
            (float(r["alpha_deg"]), float(r["sigma"]), float(r["delta0_10_deg"]))
            for r in csv.DictReader(file)
        ]

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

    def leggi_superficie(percorso, colonna):
        with open(percorso, "r", encoding="utf-8", newline="") as file:
            righe = csv.DictReader(file)
            return [
                (float(r["alpha_deg"]), float(r["sigma"]), float(r[colonna]))
                for r in righe
            ]


    punti_i0 = leggi_superficie("data/lieblein_i0.csv", "i0_10_deg")
    punti_n = leggi_superficie("data/lieblein_n.csv", "n")
    punti_delta0 = leggi_superficie("data/lieblein_delta0_sigma.csv", "delta0_10_deg")

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
        print("Solidita preliminare approvata:", sigma_prog)
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


# 16. CICLO ESTERNO DI PROGETTAZIONE

soluzione_trovata = False
sigma_iniziale = dati_base["sigma_prog"]

for tentativo in range(dati_base["max_iter_sigma"]):

    sigma = round(
        sigma_iniziale + tentativo * dati_base["sigma_step"], 6
    )

    if sigma > dati_base["sigma_max"]:
        break

    dati_tentativo = dati_base.copy()
    dati_tentativo["sigma_prog"] = sigma

    print("Tentativo:", tentativo + 1, "Solidita:", sigma)

    if progetta(dati_tentativo):
        soluzione_trovata = True
        break

if not soluzione_trovata:
    raise ValueError("Nessuna soluzione trovata nei limiti di solidita")


def esegui_airfoil():
    return None