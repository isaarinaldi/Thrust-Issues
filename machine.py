import math
import numpy as np

from math import sin, radians, pi, ceil

from data.eckert_data import eckert_coefficients

# ==========================================
# PORTATA E LAVORO SPECIFICO #
# ==========================================

def operating_point(
    nominal_thrust,
    air_density,
    jet_velocity,
    ambient_velocity,
    rotor_efficiency_initial,
):
    values = (
        nominal_thrust,
        air_density,
        jet_velocity,
        ambient_velocity,
        rotor_efficiency_initial,
    )

    if any(not math.isfinite(value) for value in values):
        raise ValueError("Gli input devono essere finiti.")

    if nominal_thrust <= 0 or air_density <= 0:
        raise ValueError("Spinta e densità devono essere positive.")

    if ambient_velocity < 0 or jet_velocity <= ambient_velocity:
        raise ValueError(
            "Per questo modello deve risultare "
            "jet_velocity > ambient_velocity >= 0."
        )

    if not 0 < rotor_efficiency_initial <= 1:
        raise ValueError(
            "Il rendimento deve essere maggiore di 0 e minore o uguale a 1."
        )
    """Calcola Q, gH, L e P per il dimensionamento preliminare."""

    # Portata volumetrica Q [m³/s]
    flow_rate = nominal_thrust / (air_density * (jet_velocity - ambient_velocity))

    # Energia specifica utile gH [J/kg]
    specific_head = (jet_velocity**2 - ambient_velocity**2) / 2

    # Lavoro specifico L [J/kg]
    specific_work = specific_head / rotor_efficiency_initial

    # Potenza del rotore P [W]
    rotor_power = air_density * flow_rate * specific_work

    return flow_rate, specific_head, specific_work, rotor_power


#===========================================#
#ECKERT DIAGRAM
# ==========================================#

def eckert_search(
    flow_rate,
    specific_head,
    max_tip_diameter,
    tip_diameter_fraction,
    specific_speed_min,
    specific_speed_max,
    specific_speed_points,
):
    """Valuta tutte le configurazioni e verifica il diametro esterno."""

    # Controllo degli input
    positive_values = (
        flow_rate,
        specific_head,
        max_tip_diameter,
    )

    if any(
        not math.isfinite(value) or value <= 0
        for value in positive_values
    ):
        raise ValueError(
            "Portata, energia specifica e diametro massimo "
            "devono essere positivi e finiti."
        )

    if not 0 < tip_diameter_fraction <= 1:
        raise ValueError(
            "La frazione del diametro deve essere maggiore di 0 "
            "e minore o uguale a 1."
        )

    if not 3 <= specific_speed_min < specific_speed_max <= 7:
        raise ValueError(
            "L'intervallo di ricerca deve essere compreso tra 3 e 7."
        )

    if (isinstance(specific_speed_points, bool)
        or not isinstance(specific_speed_points, int)
        or specific_speed_points < 2
    ):
        raise ValueError(
            "Il numero di punti deve essere un intero maggiore o uguale a 2."
        )

    # Diametro limite adottato nel progetto [m]
    tip_diameter_limit = (
        tip_diameter_fraction * max_tip_diameter
    )

    # Velocità specifiche da esaminare [-]
    specific_speeds = np.linspace(
        specific_speed_min,
        specific_speed_max,
        specific_speed_points,
    )

    results = []

    for specific_speed in specific_speeds:

        # Coefficienti di riferimento dal diagramma [-]
        phi, psi, chi = eckert_coefficients(specific_speed)

        # Velocità angolare [rad/s]
        angular_velocity = (
            specific_speed * specific_head**0.75
            / math.sqrt(flow_rate)
        )

        # Velocità di rotazione [giri/min]
        rotational_speed = angular_velocity * 60 / (2 * math.pi)

        # Velocità periferica alla punta [m/s]
        tip_speed = math.sqrt(specific_head / psi)

        # Diametro esterno calcolato [m]
        tip_diameter = 2 * tip_speed / angular_velocity

        # Verifica del vincolo sul diametro
        diameter_ok = tip_diameter <= tip_diameter_limit

        # Memorizzazione dei risultati della configurazione
        results.append({
            "specific_speed": float(specific_speed),
            "phi": phi,
            "psi": psi,
            "chi": chi,
            "angular_velocity": angular_velocity,
            "rotational_speed": rotational_speed,
            "tip_speed": tip_speed,
            "tip_diameter": tip_diameter,
            "tip_diameter_limit": tip_diameter_limit,
            "diameter_ok": diameter_ok,
        })

    return results

# ==========================================
# SELEZIONE DELLA PRIMA CONFIGURAZIONE AMMISSIBILE
# ==========================================

def select_design(results):
    """Seleziona la minima velocità specifica che rispetta il diametro."""

    feasible = [
        result for result in results
        if result["diameter_ok"]
    ]

    if not feasible:
        raise ValueError(
            "Nessuna configurazione rispetta il limite sul diametro."
        )

    return min(
        feasible,
        key=lambda result: result["specific_speed"],
    ).copy()


# ==========================================
# VELOCITÀ MERIDIANA E CONTINUITÀ
# ==========================================

def check_continuity(
    flow_rate,
    phi,
    tip_speed,
    annulus_area,
    jet_velocity,
):
    """Confronta portata richiesta e portata ricavata da Eckert."""

    # Velocità meridiana dal coefficiente di portata [m/s]
    c_m_eckert = phi * tip_speed

    # Velocità meridiana necessaria per conservare la portata [m/s]
    c_m_continuity = flow_rate / annulus_area

    # Portata ricavata dalla geometria e dal coefficiente phi [m³/s]
    flow_rate_check = annulus_area * c_m_eckert

    # Scostamento relativo della portata [-]
    flow_rate_deviation = (
        flow_rate_check - flow_rate
    ) / flow_rate

    continuity_ok = math.isclose(
        flow_rate_check,
        flow_rate,
        rel_tol=1e-9,
        abs_tol=1e-12,
    )

    return {
        "c_m_eckert": c_m_eckert,
        "c_m_continuity": c_m_continuity,
        "flow_rate_check": flow_rate_check,
        "flow_rate_deviation": flow_rate_deviation,
        "continuity_ok": continuity_ok,
    }


# ============================================================
# ============================================================
#
#              AIRFOIL DESIGN - NACA 65
#
#        PROGETTAZIONE AERODINAMICA DELLE PALE
#        Correlazioni di Lieblein
#
# ============================================================
# ============================================================


# ------------------------------------------------------------
# 1. SCELTA DEL PROFILO E SOLIDITA PRELIMINARE
# ------------------------------------------------------------
def scelta_profilo(dati):
    profilo = dati["profilo"]
    tmax_c = dati["tmax_c"]
    sigma_prog = dati["sigma_prog"]
    return profilo, tmax_c, sigma_prog

# ------------------------------------------------------------
# 2. CALCOLO DEL DIFFUSION FACTOR
# ------------------------------------------------------------
def calcola_diffusion_factor(dati):
    W1 = dati["W1"]
    W2 = dati["W2"]
    beta1 = radians(dati["beta1"])
    beta2 = radians(dati["beta2"])
    sigma = dati["sigma_prog"]
    # beta e' misurato dall'asse: componente tangenziale = W * sin(beta)
    delta_Wu = abs(W2 * sin(beta2) - W1 * sin(beta1))
    D = 1 - W2 / W1 + delta_Wu / (2 * sigma * W1)
    return D

# ------------------------------------------------------------
# 3. CALCOLO DELLA CURVATURA INIZIALE
# ------------------------------------------------------------
def curvatura_iniziale(dati):
    beta1 = dati["beta1"]
    beta2 = dati["beta2"]

    theta0 = beta1 - beta2

    return theta0

# ------------------------------------------------------------
# 4. INCIDENZA E DEVIAZIONE - LIEBLEIN
# ------------------------------------------------------------
def calcola_incidenza_lieblein(theta, i0_10, Kti, Ksh, n):
    i_rif = Ksh * Kti * i0_10 + n * theta

    return i_rif

def calcola_deviazione_lieblein(theta, delta0_10, m, b, sigma, Kdelta_t):
    delta = Kdelta_t * delta0_10 + (m / sigma ** b) * theta

    return delta

# ------------------------------------------------------------
# 5. CONVERGENZA ITERATIVA DELLA CURVATURA
# ------------------------------------------------------------
def curvatura_corretta(beta1, beta2, incidenza, deviazione):
    theta1 = beta1 - beta2 - incidenza + deviazione

    return theta1


def convergenza_curvatura(theta1, beta1, beta2,
                          i0_10, Kti, Ksh, n,
                          delta0_10, m, b, sigma, Kdelta_t,
                          epsilon, max_iter):
    theta = theta1
    iterazione = 0

    while iterazione < max_iter:

        i = calcola_incidenza_lieblein(theta, i0_10, Kti, Ksh, n)

        delta = calcola_deviazione_lieblein(
            theta, delta0_10, m, b, sigma, Kdelta_t
        )

        theta_nuova = curvatura_corretta(beta1, beta2, i, delta)

        iterazione += 1

        if abs(theta_nuova - theta) < epsilon:
            i_finale = calcola_incidenza_lieblein(
                theta_nuova, i0_10, Kti, Ksh, n
            )
            delta_finale = calcola_deviazione_lieblein(
                theta_nuova, delta0_10, m, b, sigma, Kdelta_t
            )
            return theta_nuova, i_finale, delta_finale, iterazione

        theta = theta_nuova

    raise ValueError("Convergenza della curvatura non raggiunta")
# ------------------------------------------------------------
# 6. DIMENSIONAMENTO GEOMETRICO DELLE PALE
# ------------------------------------------------------------
def dimensionamento_geometrico(rtip, rhub, rm, AR, sigma_prog):
    if not (2 < AR < 2.5):
        raise ValueError("Aspect Ratio fuori dai limiti")

    if not (0 < rhub < rm < rtip):
        raise ValueError("Raggi non validi")

    if sigma_prog <= 0:
        raise ValueError("Solidita non valida")

    h = rtip - rhub

    c = h / AR

    sprog = c / sigma_prog

    Z = ceil(2 * pi * rm / sprog)

    delta_phi = 360 / Z

    seff = 2 * pi * rm / Z

    sigma_eff = c / seff

    return h, c, sprog, Z, delta_phi, seff, sigma_eff

# ------------------------------------------------------------
# 7. CALCOLO DELL'ANGOLO DI CALETTAMENTO
# ------------------------------------------------------------
def calcola_calettamento(beta1, beta2, i_eff, delta_eff):
    gamma = 90 - (beta1 + beta2 - i_eff - delta_eff) / 2

    return gamma

# ------------------------------------------------------------
# 8. VERIFICA AERODINAMICA FINALE
# ------------------------------------------------------------
def verifica_aerodinamica_finale(D_eff, de_haller, D_max, de_haller_min):
    verifica_D = D_eff <= D_max
    verifica_de_haller = de_haller >= de_haller_min

    requisiti_soddisfatti = verifica_D and verifica_de_haller

    return requisiti_soddisfatti
