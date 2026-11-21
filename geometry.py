import math

# ==========================================
# GEOMETRIA DEL CANALE ANULARE
# ==========================================

def annulus_geometry(tip_diameter, chi):
    """Calcola diametro del mozzo, raggi e area anulare."""

    if not math.isfinite(tip_diameter) or tip_diameter <= 0:
        raise ValueError("Il diametro esterno deve essere positivo e finito.")

    if not 0 < chi < 1:
        raise ValueError("Chi deve essere compreso tra 0 e 1.")

    # Diametro del mozzo [m]
    hub_diameter = chi * tip_diameter

    # Raggi delle sezioni di riferimento [m]
    tip_radius = tip_diameter / 2
    hub_radius = hub_diameter / 2

    # Sezione media scelta a metà dell'altezza della pala [m]
    mean_radius = (hub_radius + tip_radius) / 2

    # Altezza della pala [m]
    blade_height = tip_radius - hub_radius

    # Area anulare, senza considerare il bloccaggio delle pale [m²]
    annulus_area = (
        math.pi / 4
        * (tip_diameter**2 - hub_diameter**2)
    )

    return {
        "tip_diameter": tip_diameter,
        "hub_diameter": hub_diameter,
        "tip_radius": tip_radius,
        "hub_radius": hub_radius,
        "mean_radius": mean_radius,
        "blade_height": blade_height,
        "annulus_area": annulus_area,
    }

#==============================================================#
# CONTINUITà CON LA PORTATA #
#==============================================================#

def hub_ratio_from_continuity(flow_rate, tip_diameter, phi, tip_speed):
    """Ricava chi imponendo Q = area anulare * phi * Utip."""

    values = (flow_rate, tip_diameter, phi, tip_speed)

    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("Gli input devono essere finiti e positivi.")

    # Area circolare totale [m²]
    total_area = math.pi * tip_diameter**2 / 4

    # Velocità meridiana [m/s]
    c_m = phi * tip_speed

    # Area anulare richiesta dalla continuità [m²]
    annulus_area_required = flow_rate / c_m

    if annulus_area_required >= total_area:
        raise ValueError(
            "Configurazione non ammissibile: la continuità richiede "
            "un mozzo nullo o un'area anulare maggiore dell'area totale."
        )

    chi = math.sqrt(1 - annulus_area_required / total_area)

    return chi

#===========================================================#
#CALCOLO DEI TRIANGOLI DELLA VELOCITA'#
#===========================================================#

def calculate_velocity_triangles(
    geometry,
    tip_speed,
    c_m,
    specific_head,
    rotor_efficiency_initial,
    work_done_factor,
):
    """Calcola i triangoli a hub, medio e tip con legge free vortex."""

    values = (
        tip_speed,
        c_m,
        specific_head,
        rotor_efficiency_initial,
        work_done_factor,
    )

    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError(
            "Gli input dei triangoli devono essere finiti e positivi."
        )

    if rotor_efficiency_initial > 1:
        raise ValueError("Il rendimento non può essere maggiore di 1.")

    tip_radius = geometry["tip_radius"]

    # Incremento della componente tangenziale al tip [m/s]
    delta_c_u_tip = specific_head / (
        work_done_factor * rotor_efficiency_initial * tip_speed
    )

    sections = {
        "Hub": geometry["hub_radius"],
        "Mean": geometry["mean_radius"],
        "Tip": tip_radius,
    }

    triangles = {}

    for section, radius in sections.items():
        # Velocità periferica locale [m/s]
        U = tip_speed * radius / tip_radius

        # Legge free vortex: r * delta_c_u = costante [m/s]
        delta_c_u = delta_c_u_tip * tip_radius / radius

        # Velocità assolute [m/s]
        c1 = c_m
        c3 = c_m
        c2 = math.hypot(c_m, delta_c_u)

        # Velocità relative [m/s]
        w1 = math.hypot(c_m, U)
        w2 = math.hypot(c_m, U - delta_c_u)

        # Angoli rispetto alla direzione tangenziale [gradi]
        alpha1 = 90.0
        alpha3 = 90.0
        alpha2 = math.degrees(math.asin(c_m / c2))

        beta1 = math.degrees(math.asin(c_m / w1))
        beta2 = math.degrees(math.asin(c_m / w2))

        if U - delta_c_u < 0:
            beta2 = 180.0 - beta2

        triangles[section] = {
            "radius": radius,
            "U": U,
            "c_m": c_m,
            "c_theta2": delta_c_u,
            "c1": c1,
            "c2": c2,
            "c3": c3,
            "w1": w1,
            "w2": w2,
            "alpha1": alpha1,
            "alpha2": alpha2,
            "alpha3": alpha3,
            "beta1": beta1,
            "beta2": beta2,
        }

    return triangles

# ==========================================
# VELOCITÀ MASSIME LUNGO LA PALA
# ==========================================

def maximum_section_speeds(
    *,
    axial_velocity,
    angular_velocity,
    hub_radius,
    tip_radius,
    outlet_swirl_tip,
    section_count,
):
    """
    Calcola le velocità massime su section_count sezioni radiali.

    Ipotesi:
        - velocità assiale costante;
        - prerotazione nulla;
        - legge free vortex all'uscita del rotore.

    outlet_swirl_tip: componente tangenziale c_theta2 al tip [m/s].

    Restituisce:
        max_relative_speed [m/s]
        max_absolute_speed [m/s]
    """

    # Controllo degli input
    values = (
        axial_velocity,
        angular_velocity,
        hub_radius,
        tip_radius,
    )

    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError(
            "Velocità assiale, velocità angolare e raggi "
            "devono essere positivi e finiti."
        )

    if tip_radius <= hub_radius:
        raise ValueError(
            "Il raggio al tip deve essere maggiore del raggio al mozzo."
        )

    if not math.isfinite(outlet_swirl_tip):
        raise ValueError(
            "La componente tangenziale al tip deve essere finita."
        )

    if (
        isinstance(section_count, bool)
        or not isinstance(section_count, int)
        or section_count < 2
    ):
        raise ValueError(
            "Il numero di sezioni deve essere un intero almeno pari a 2."
        )

    max_relative_speed = 0.0
    max_absolute_speed = 0.0

    for index in range(section_count):

        # Raggi equidistanti dal mozzo alla punta, estremi inclusi [m]
        radius = (
            hub_radius
            + (tip_radius - hub_radius)
            * index / (section_count - 1)
        )

        # Velocità periferica locale [m/s]
        U = angular_velocity * radius

        # Componente tangenziale in uscita: r * c_theta2 = costante
        c_theta2 = outlet_swirl_tip * tip_radius / radius

        # Velocità relative all'ingresso e all'uscita [m/s]
        w1 = math.hypot(axial_velocity, U)
        w2 = math.hypot(axial_velocity, U - c_theta2)

        # Velocità assolute all'ingresso e all'uscita [m/s]
        c1 = axial_velocity
        c2 = math.hypot(axial_velocity, c_theta2)

        # Aggiornamento dei massimi
        max_relative_speed = max(max_relative_speed, w1, w2)
        max_absolute_speed = max(max_absolute_speed, c1, c2)

    return max_relative_speed, max_absolute_speed

def outlet_geometry(flow_rate, tip_radius, tip_clearance_ratio):
    """Uscita circolare senza mozzo, con diametro uguale al condotto al rotore."""

    if not math.isfinite(flow_rate) or flow_rate <= 0:
        raise ValueError("La portata deve essere positiva e finita.")

    if not math.isfinite(tip_radius) or tip_radius <= 0:
        raise ValueError("Il raggio al tip deve essere positivo e finito.")

    if (
        not math.isfinite(tip_clearance_ratio)
        or not 0 <= tip_clearance_ratio < 0.5
    ):
        raise ValueError(
            "tip_clearance_ratio deve essere compreso tra 0 e 0.5 escluso."
        )

    tip_diameter = 2 * tip_radius

    # Dtip = Dcondotto * (1 - 2 * rapporto di gioco)
    duct_diameter = tip_diameter / (1 - 2 * tip_clearance_ratio)

    # Gioco radiale [m]
    tip_clearance = tip_clearance_ratio * duct_diameter

    # Area totale e velocità media di uscita
    total_area = math.pi * (duct_diameter / 2)**2
    outlet_velocity = flow_rate / total_area

    return total_area, outlet_velocity, tip_clearance