from pathlib import Path

import yaml

import csv
from collections.abc import Mapping

from airfoil_interpolation import interpola_curva, interpola_2d

from machine import (
    scelta_profilo,
    calcola_diffusion_factor,
    curvatura_iniziale,
    calcola_incidenza_lieblein,
    calcola_deviazione_lieblein,
    curvatura_corretta,
    convergenza_curvatura,
    dimensionamento_geometrico,
    calcola_calettamento,
    verifica_aerodinamica_finale,
)
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


import math
from typing import Any

from losses import compute_rotor_losses_and_efficiency
from overall_performance import calculate_overall_performance





# ============================================================
# PERCORSI COMUNI DEL PROGETTO
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"




def main(rotor_efficiency_override=None):

    # ==========================================
    # 1. LETTURA INPUT
    # ==========================================

    config_path = Path(__file__).resolve().parent / "config.yaml"

    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)


    # Aggiornamento del rendimento durante la convergenza
    if rotor_efficiency_override is not None:
        if not 0 < rotor_efficiency_override <= 1:
            raise ValueError("Rendimento del rotore non valido.")

        config["rotor_efficiency_initial"] = rotor_efficiency_override



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



    # ============================================================
    # AIRFOIL DESIGN - NACA 65
    # COLLEGAMENTO CON IL DIMENSIONAMENTO PRELIMINARE
    # ============================================================

    # Preparazione degli input dai triangoli di velocita
    dati_airfoil = prepara_input_airfoil(
        triangles,
        config["airfoil"],
        speed_of_sound=config["speed_of_sound"],
        air_density=config["air_density"],
        dynamic_viscosity=config["dynamic_viscosity"],
    )

    print("\nINPUT AIRFOIL DALLA SEZIONE MEDIA")

    for key in (
        "W1", "W2", "beta1", "beta2",
        "Ma", "Re", "rhub", "rm", "rtip"
    ):
        print(f"  {key}: {dati_airfoil[key]:.5f}")

    # Progettazione del profilo alare
    print("\nPROGETTAZIONE DEL PROFILO ALARE NACA 65")

    risultato_airfoil = esegui_airfoil(dati_airfoil)
    verifica_airfoil = bool(risultato_airfoil)

    if not verifica_airfoil:
        raise ValueError("Airfoil Design non verificato.")




    return {
        "flow_rate": flow_rate,
        "specific_head": specific_head,
        "specific_work": specific_work,
        "rotor_power": rotor_power,
        "selected_design": selected_design,
        "geometry": geometry,
        "continuity": continuity,
        "triangles": triangles,

        # Risultati Airfoil Design
        "airfoil_inputs": dati_airfoil,
        "airfoil_verified": verifica_airfoil,
        "airfoil_result": risultato_airfoil,}




# ============================================================
# AIRFOIL DESIGN - NACA 65
# ============================================================
# Preparazione input, correlazioni di Lieblein,
# dimensionamento geometrico e verifiche aerodinamiche.
# ============================================================


def prepara_input_airfoil(
    triangles,
    config,
    *,
    speed_of_sound=None,
    air_density=None,
    dynamic_viscosity=None,
):
    mean = triangles["Mean"]
    hub = triangles["Hub"]
    tip = triangles["Tip"]

    dati = dict(config)


    # Dati aerodinamici delle 9 sezioni radiali
    dati["sezioni_radiali"] = {}

    for nome, sec in triangles.items():
        dati["sezioni_radiali"][nome] = {
            "radius": sec["radius"],
            "W1": sec["w1"],
            "W2": sec["w2"],
            "beta1": 90.0 - sec["beta1"],
            "beta2": 90.0 - sec["beta2"],
        }

    print("Sezioni Airfoil:", list(dati["sezioni_radiali"]))


    # Velocita' [m/s] alla sezione media.
    dati["C1"] = mean["c1"]
    dati["C2"] = mean["c2"]
    dati["W1"] = mean["w1"]
    dati["W2"] = mean["w2"]

    # La geometria usa beta dalla tangente; le carte Lieblein, dall'asse.
    dati["beta1"] = 90.0 - mean["beta1"]
    dati["beta2"] = 90.0 - mean["beta2"]

    # Raggi del rotore (geometria gia' verificata per continuita').
    dati["rtip"] = tip["radius"]
    dati["rhub"] = hub["radius"]
    dati["rm"] = mean["radius"]

    # Mach RELATIVO in ingresso al rotore, non Mach assoluto.
    if speed_of_sound is not None:
        if speed_of_sound <= 0:
            raise ValueError("speed_of_sound deve essere positivo.")
        dati["Ma"] = mean["w1"] / speed_of_sound
    elif "Ma1" in mean:
        # Compatibilita' con i dati precedenti, se presenti.
        dati["Ma"] = mean["Ma1"]

    # Reynolds relativo riferito alla corda preliminare c=(rtip-rhub)/AR.
    # In assenza di proprieta' fisiche, conserva il valore della config.
    if air_density is not None or dynamic_viscosity is not None:
        if air_density is None or dynamic_viscosity is None:
            raise ValueError("Re richiede sia densita' che viscosita'.")
        AR = float(dati["AR"])
        if air_density <= 0 or dynamic_viscosity <= 0 or AR <= 0:
            raise ValueError("Densita', viscosita' e AR devono essere positivi.")
        c = (dati["rtip"] - dati["rhub"]) / AR
        dati["Re"] = air_density * mean["w1"] * c / dynamic_viscosity


    if "Ma" not in dati:
        raise ValueError("Mach mancante: indicare speed_of_sound o Ma1.")

    # Conserva i triangoli di tutte le sezioni radiali
    dati["triangles"] = triangles

    return dati







def _leggi_tabella(percorso, colonne):


    print("FILE LETTO:", percorso.resolve())
    print("DIMENSIONE:", percorso.stat().st_size)
    print("PRIMI CARATTERI:", repr(percorso.read_text(encoding="utf-8-sig")[:100]))

    with percorso.open("r", encoding="utf-8-sig", newline="") as file:

        prima_riga = file.readline()
        file.seek(0)

        separatore = ";" if prima_riga.count(";") > prima_riga.count(",") else ","

        reader = csv.DictReader(
            file,
            delimiter=separatore,
            skipinitialspace=True
        )

        if reader.fieldnames is None:
            raise ValueError(f"Tabella vuota: {percorso}")

        reader.fieldnames = [
            nome.strip().replace("\ufeff", "")
            for nome in reader.fieldnames
        ]

        if not set(colonne).issubset(reader.fieldnames):
            raise ValueError(
                f"Tabella CSV non valida: {percorso}. "
                f"Colonne lette: {reader.fieldnames}. "
                f"Colonne richieste: {colonne}"
            )

        return list(reader)




def progetta_sezioni_radiali(dati, tabelle, Z, c):
    risultati = {}
    tutte_verificate = True

    tab_dev = tabelle["deviazione"]
    angoli = [float(x["alpha_deg"]) for x in tab_dev]
    valori_m = [float(x["m"]) for x in tab_dev]
    valori_b = [float(x["b"]) for x in tab_dev]

    print("\nPROGETTAZIONE RADIALE - 9 SEZIONI")
    print("Sezione | Sigma | Curvatura | Incidenza | Deviazione | Calettamento | D")

    for nome, sec in dati["sezioni_radiali"].items():
        r = sec["radius"]
        beta1 = sec["beta1"]
        beta2 = sec["beta2"]
        sigma = Z * c / (2.0 * math.pi * r)

        if not 0.25 <= sigma <= 2.0:
            print(f"{nome}: solidita {sigma:.4f} fuori dalle tabelle")
            return None

        i0 = interpola_2d(tabelle["i0"], beta1, sigma)
        n = interpola_2d(tabelle["n"], beta1, sigma)
        delta0 = interpola_2d(tabelle["delta0"], beta1, sigma)

        m = interpola_curva(angoli, valori_m, beta1)
        b = interpola_curva(angoli, valori_b, beta1)

        theta0 = beta1 - beta2

        i_iniziale = calcola_incidenza_lieblein(
            theta0, i0, dati["Kti"], dati["Ksh"], n
        )
        delta_iniziale = calcola_deviazione_lieblein(
            theta0, delta0, m, b, sigma, dati["Kdelta_t"]
        )

        theta1 = curvatura_corretta(
            beta1, beta2, i_iniziale, delta_iniziale
        )

        theta, incidenza, deviazione, iterazioni = convergenza_curvatura(
            theta1, beta1, beta2,
            i0, dati["Kti"], dati["Ksh"], n,
            delta0, m, b, sigma, dati["Kdelta_t"],
            dati["epsilon_theta_deg"], dati["max_iter_theta"]
        )

        gamma = calcola_calettamento(
            beta1, beta2, incidenza, deviazione
        )

        dati_D = {
            "W1": sec["W1"],
            "W2": sec["W2"],
            "beta1": beta1,
            "beta2": beta2,
            "sigma_prog": sigma
        }

        D = calcola_diffusion_factor(dati_D)
        de_haller = sec["W2"] / sec["W1"]

        verifica = verifica_aerodinamica_finale(
            D, de_haller, dati["D_max"], dati["de_haller_min"]
        )

        if not verifica:
            tutte_verificate = False

        risultati[nome] = {
            "radius": r,
            "sigma": sigma,
            "curvatura_deg": theta,
            "incidenza_deg": incidenza,
            "deviazione_deg": deviazione,
            "calettamento_deg": gamma,
            "D": D,
            "de_haller": de_haller,
            "verifica": verifica
        }

        print(
            f"{nome:>5} | {sigma:.3f} | {theta:.3f} | "
            f"{incidenza:.3f} | {deviazione:.3f} | "
            f"{gamma:.3f} | {D:.3f}"
        )

    if not tutte_verificate:
        print("Verifica radiale NON soddisfatta")
        return None

    print("TUTTE LE 9 SEZIONI VERIFICATE")
    return risultati


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

    # Verifica che la solidita effettiva sia
    # compresa nel dominio delle tre tabelle.
    tabelle_sigma = ("i0", "n", "delta0")

    sigma_min_tab = max(
        min(p[1] for p in tabelle[nome])
        for nome in tabelle_sigma
    )

    sigma_max_tab = min(
        max(p[1] for p in tabelle[nome])
        for nome in tabelle_sigma
    )

    if not 0.25 <= sigma_eff <= sigma_max_tab:
        print(
            f"Solidita effettiva {sigma_eff:.4f} "
            "fuori dal dominio delle tabelle."
        )
        return False

    i0_eff = interpola_2d(
        punti_i0, dati["beta1"], sigma_eff
    )

    n_eff = interpola_2d(
        punti_n, dati["beta1"], sigma_eff
    )

    delta0_eff = interpola_2d(
        punti_delta0, dati["beta1"], sigma_eff
    )

    # Nuova convergenza con la solidita effettiva
    theta_eff, i_eff, delta_eff, iter_eff = (
        convergenza_curvatura(
            theta_conv,
            dati["beta1"],
            dati["beta2"],
            i0_eff,
            dati["Kti"],
            dati["Ksh"],
            n_eff,
            delta0_eff,
            m,
            b,
            sigma_eff,
            dati["Kdelta_t"],
            dati["epsilon_theta_deg"],
            dati["max_iter_theta"]
        )
    )

    print("Curvatura effettiva:", round(theta_eff, 4))
    print("Iterazioni effettive:", iter_eff)



    # VERIFICA AERODINAMICA FINALE

    dati_finali = dati.copy()
    dati_finali["sigma_prog"] = sigma_eff

    D_eff = calcola_diffusion_factor(dati_finali)

    de_haller = dati["W2"] / dati["W1"]


    # VERIFICA AERODINAMICA RADIALE
    for nome, sezione in dati["triangles"].items():

        r = sezione["radius"]
        w1 = sezione["w1"]
        w2 = sezione["w2"]
        delta_wu = abs(sezione["c_theta2"])

        sigma_locale = c * Z / (2 * math.pi * r)

        D_locale = (
            1 - w2 / w1
            + delta_wu / (2 * sigma_locale * w1)
        )

        de_haller_locale = w2 / w1

        print(
            f"{nome}: sigma={sigma_locale:.3f}, "
            f"D={D_locale:.4f}, "
            f"DeHaller={de_haller_locale:.4f}"
        )

        if (
            not 0 <= D_locale <= dati["D_max"]
            or de_haller_locale < dati["de_haller_min"]
        ):
            print(
                f"Configurazione non ammissibile "
                f"alla sezione {nome}"
            )
            return False



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

        gamma = calcola_calettamento(
            dati["beta1"],
            dati["beta2"],
            i_eff,
            delta_eff
        )

        print("Angolo di calettamento:", round(gamma, 3), "gradi")


        profili_radiali = progetta_sezioni_radiali(
            dati, tabelle, Z, c
        )

        if profili_radiali is None:
            return False



        return {
            "profile": profilo,
            "tmax_c": tmax_c,
            "sigma_prog": sigma_prog,
            "sigma_eff": sigma_eff,
            "chord": c,
            "Z": Z,
            "stagger_deg": gamma,
            "D_factor": D_eff,
            "de_haller": de_haller,
            "sezioni_radiali": profili_radiali,
        }


    else:
        if de_haller < dati["de_haller_min"]:
            raise ValueError(
                "De Haller non soddisfatto: modificare i triangoli di velocita"
            )

        return False

def airfoil_design_main(
                config_path: Path | None = None,
                input_data: Mapping[str, object] | None = None,
        ) -> bool:


        # Percorso del file YAML principale
    if config_path is None:
        config_path = PROJECT_DIR / "config.yaml"

    # Lettura della configurazione generale
    with Path(config_path).open("r", encoding="utf-8") as file:
        config_general = yaml.safe_load(file)

    # Estrazione dei parametri Airfoil Design
    dati_base = dict(config_general["airfoil"])

    # Aggiunta dei dati provenienti dai triangoli di velocita
    if input_data is not None:
        if not isinstance(input_data, Mapping):
            raise TypeError(
                "Gli input aerodinamici devono essere una mappa."
            )
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


    # ==========================================
    # CICLO AUTOMATICO DELLA SOLIDITA
    # ==========================================

    sigma_iniziale = float(dati_base["sigma_prog"])
    sigma_step = float(dati_base["sigma_step"])
    sigma_max = float(dati_base["sigma_max"])
    max_iter_sigma = int(dati_base["max_iter_sigma"])

    # Dominio comune delle tabelle di Lieblein
    nomi_tabelle = ("i0", "n", "delta0")

    sigma_min_tab = max(
        min(p[1] for p in tabelle[nome])
        for nome in nomi_tabelle
    )

    sigma_max_tab = min(
        max(p[1] for p in tabelle[nome])
        for nome in nomi_tabelle
    )

    # Verifica degli input
    if sigma_step <= 0:
        raise ValueError("sigma_step deve essere positivo")

    if not 0.25 <= sigma_iniziale <= sigma_max_tab:
        raise ValueError(
            f"Solidita iniziale fuori dal dominio "
            f"[{sigma_min_tab}, {sigma_max_tab}]"
        )

    if not sigma_iniziale <= sigma_max <= sigma_max_tab:
        raise ValueError(
            f"sigma_max non valido. "
            f"Dominio massimo: {sigma_max_tab}"
        )

    # Verifica del dominio angolare per m e b
    angoli_mb = [
        float(r["alpha_deg"])
        for r in tabelle["deviazione"]
    ]

    beta1 = float(dati_base["beta1"])

    if not min(angoli_mb) <= beta1 <= max(angoli_mb):
        raise ValueError(
            f"Angolo beta1={beta1:.2f} fuori "
            "dal dominio della tabella m,b"
        )

    # Numero di tentativi necessario
    n_necessari = (
        math.floor(
            (sigma_max - sigma_iniziale) / sigma_step
            + 1e-9
        ) + 1
    )

    if max_iter_sigma < n_necessari:
        raise ValueError(
            f"max_iter_sigma insufficiente: "
            f"servono {n_necessari} tentativi"
        )

    # Ricerca della prima soluzione ammissibile
    for tentativo in range(n_necessari):

        sigma = round(
            sigma_iniziale + tentativo * sigma_step, 6
        )

        dati_tentativo = dict(dati_base)
        dati_tentativo["sigma_prog"] = sigma

        print(
            f"\nTentativo {tentativo + 1}: "
            f"solidita = {sigma:.4f}"
        )

        try:
            risultato = progetta(
                dati_tentativo, tabelle
            )

        except ValueError as errore:
            # Solo la mancata convergenza della
            # curvatura consente un nuovo tentativo.
            if (
                "Convergenza della curvatura non raggiunta"
                in str(errore)
            ):
                print(f"Tentativo scartato: {errore}")
                continue

            # Altri errori richiedono correzione.
            raise

        if risultato:
            print(
                f"\nSOLUZIONE TROVATA "
                f"con sigma = {sigma:.4f}"
            )
            return risultato

        print("Tentativo scartato: vincoli non soddisfatti")

    raise ValueError(
        "Nessuna soluzione aerodinamicamente "
        "ammissibile nell'intervallo di solidita "
        f"[{sigma_iniziale}, {sigma_max}]."
    )




def esegui_airfoil(dati: Mapping[str, object]) -> bool:
    return airfoil_design_main(input_data=dati)




# ============================================================
# CALCOLO PERDITE E PRESTAZIONI 3 PARTE
# ============================================================

def _load_yaml(file_path: Path) -> dict[str, Any]:
    """Carica un file YAML verificandone l'esistenza e la validità."""
    if not file_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path.resolve()}")
    with file_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML mapping in: {file_path.resolve()}")
    return data


def _resolve_path(path_like: str | Path) -> Path:
    """Risolve il percorso rispetto alla directory corrente o alla cartella del progetto."""
    candidate = Path(path_like)
    if candidate.exists():
        return candidate
    return PROJECT_DIR / candidate



# ============================================================
# PERFORMANCE DESIGN - COLLEGAMENTO AL MAIN GENERALE
# ============================================================

def run_main_performance(
            config_path: str | Path = "config.yaml",
            eta_override: float | None = None,
) -> dict[str, Any]:

    # 1. Lettura dei parametri generali
    config = _load_yaml(_resolve_path(config_path))

    # 2. Esecuzione del dimensionamento completo
    risultati = main(
        rotor_efficiency_override=eta_override
    )
    if not isinstance(risultati, dict):
        raise ValueError("Il main non ha restituito risultati validi.")

    # 3. Acquisizione dei risultati
    selected_design = risultati["selected_design"]
    geometry = risultati["geometry"]
    triangles = risultati["triangles"]

    dati_airfoil = risultati["airfoil_inputs"]
    verifica_airfoil = risultati["airfoil_verified"]

    # ============================================================
    # RISULTATI DEL DIMENSIONAMENTO AERODINAMICO
    # ============================================================

    profilo = risultati["airfoil_result"]

    print("\nRISULTATI AIRFOIL ACQUISITI")
    print("Profilo:", profilo["profile"])
    print("Numero di pale:", profilo["Z"])
    print("Corda:", round(profilo["chord"], 4), "m")
    print("Solidita effettiva:", round(profilo["sigma_eff"], 4))
    print("Angolo di calettamento:", round(profilo["stagger_deg"], 3), "gradi")
    print("Diffusion Factor:", round(profilo["D_factor"], 4))

    profilo = risultati["airfoil_result"]

    print("\nRISULTATI AERODINAMICI ACQUISITI")
    print("Numero di pale:", profilo["Z"])
    print("Corda:", round(profilo["chord"], 4), "m")
    print("Solidita effettiva:", round(profilo["sigma_eff"], 4))

    if not verifica_airfoil:
        raise ValueError("Airfoil Design non verificato.")

    # 4. Verifica del collegamento
    print("\n======================================")
    print("PERFORMANCE DESIGN - INPUT ACQUISITI")
    print("======================================")

    print("Diametro esterno:", geometry["tip_diameter"], "m")
    print("Diametro mozzo:", geometry["hub_diameter"], "m")
    print("Sezioni disponibili:", list(triangles.keys()))
    print("Airfoil verificato:", verifica_airfoil)

    # 5. Restituzione dei dati per il calcolo delle perdite


    # ============================================================
    # 5. PREPARAZIONE DEGLI INPUT PER IL CALCOLO DELLE PERDITE
    # ============================================================

    # Geometria richiesta dal modulo losses.py
    design_losses = {
        "D_tip_m": geometry["tip_diameter"],
        "D_hub_m": geometry["hub_diameter"],
        "tip_clearance_mm": config["tip_clearance_mm"],
    }

    # Allineamento dei nomi delle proprieta dell'aria
    config_losses = dict(config)
    config_losses["air_density_kg_m3"] = config["air_density"]
    config_losses["dynamic_viscosity_Pa_s"] = config["dynamic_viscosity"]

    # Copia dei triangoli, senza modificare quelli originali
    triangles_losses = {
        section: dict(values)
        for section, values in triangles.items()
    }

    # Angolo medio relativo per la correlazione di Vavra
    mean = triangles_losses["Mean"]

    beta_inf = math.degrees(
        math.atan2(
            mean["c_m"],
            mean["U"] - mean["c_theta2"] / 2.0
        )
    )

    mean["beta_inf"] = beta_inf


    # ============================================================
    # 6. CALCOLO PERDITE AERODINAMICHE E RENDIMENTO ROTORE
    # ============================================================

    rotor_performance = compute_rotor_losses_and_efficiency(
        triangles=triangles_losses,
        aero_design=profilo,
        design=design_losses,
        config=config_losses,
        d_max=config["airfoil"]["D_max"],
    )

    print("\n========================================")
    print("VERIFICA PRESTAZIONALE DEL ROTORE")
    print("========================================")

    print(
        "Diffusion Factor Hub:",
        round(rotor_performance["D_hub"], 4)
    )
    print(
        "Diffusion Factor Mean:",
        round(rotor_performance["D_mean"], 4)
    )
    print(
        "Diffusion Factor Tip:",
        round(rotor_performance["D_tip"], 4)
    )

    print(
        "Perdita specifica totale:",
        round(rotor_performance["R_total_J_kg"], 3),
        "J/kg"
    )

    print(
        "Rendimento del rotore:",
        round(rotor_performance["eta_rot"] * 100, 2),
        "%"
    )


    # ============================================================
    # 7. CALCOLO DELLE PRESTAZIONI COMPLESSIVE DEL JET FAN
    # ============================================================

    # Adattamento della geometria
    design_overall = {
        "D_tip_m": geometry["tip_diameter"],
        "D_hub_m": geometry["hub_diameter"],
        "c_m_m_s": triangles["Mean"]["c_m"],
    }

    # Adattamento dei parametri generali
    config_overall = dict(config)
    config_overall["air_density_kg_m3"] = config["air_density"]
    config_overall["nominal_thrust_N"] = config["nominal_thrust"]

    # Calcolo delle prestazioni complessive
    overall_result = calculate_overall_performance(
        design=design_overall,
        triangles=triangles,
        eff_result=rotor_performance,
        config=config_overall,
    )

    print("\n======================================")
    print("PRESTAZIONI COMPLESSIVE DEL JET FAN")
    print("======================================")

    print("Spinta calcolata:", round(overall_result["thrust_N"], 2), "N")
    print("Spinta verificata:", overall_result["thrust_verified"])
    print("Rendimento globale del fluido:",
          round(overall_result["eta_global"] * 100, 2), "%")
    print("Potenza elettrica:",
          round(overall_result["P_elec_kW"], 2), "kW")
    print("Rendimento complessivo:",
          round(overall_result["eta_overall"] * 100, 2), "%")







    return {
        "config": config,
        "selected_design": selected_design,
        "geometry": geometry,
        "triangles": triangles,
        "airfoil_inputs": dati_airfoil,
        "airfoil_verified": verifica_airfoil,
        "airfoil_result": profilo,
        "rotor_performance": rotor_performance,
        "overall_performance": overall_result,
    }



# ============================================================
# CONVERGENZA ITERATIVA DEL RENDIMENTO DEL ROTORE
# ============================================================

def run_performance_convergence(
    config_path="config.yaml",
    tolerance=1e-4,
    max_iterations=20,
    relaxation=0.5,
):

    config = _load_yaml(_resolve_path(config_path))
    eta_assumed = float(config["rotor_efficiency_initial"])

    for iteration in range(1, max_iterations + 1):

        print(f"\n========== ITERAZIONE {iteration} ==========")
        print(f"Rendimento ipotizzato: {eta_assumed:.5f}")

        risultati = run_main_performance(
            config_path,
            eta_override=eta_assumed,
        )

        eta_calculated = float(
            risultati["rotor_performance"]["eta_rot"]
        )

        if not math.isfinite(eta_calculated) or not 0 < eta_calculated <= 1:
            raise ValueError("Rendimento calcolato non fisico.")

        delta = abs(eta_calculated - eta_assumed)

        print(f"Rendimento calcolato: {eta_calculated:.5f}")
        print(f"Errore di convergenza: {delta:.6f}")

        if delta < tolerance:
            print("\nCONVERGENZA DEL RENDIMENTO RAGGIUNTA")
            print(f"Iterazioni: {iteration}")
            print(f"Rendimento finale: {eta_calculated * 100:.2f}%")

            risultati["convergence"] = {
                "iterations": iteration,
                "eta_rot": eta_calculated,
                "error": delta,
            }

            return risultati

        eta_assumed = (
            (1.0 - relaxation) * eta_assumed
            + relaxation * eta_calculated
        )

    raise RuntimeError(
        "Convergenza non raggiunta entro il numero massimo di iterazioni."
    )




# ============================================================
# AVVIO DEL PROGRAMMA COMPLETO
# ============================================================

if __name__ == "__main__":
    run_performance_convergence()