import math
import numpy as np

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
    #(questa linea di codice dovrebbe essere cancellata)#
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
        "flow_rate_check": flow_rate_check,
        "flow_rate_deviation": flow_rate_deviation,
        "continuity_ok": continuity_ok,
    }

