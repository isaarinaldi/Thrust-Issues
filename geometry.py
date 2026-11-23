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


    r_hub = geometry["hub_radius"]
    r_tip = geometry["tip_radius"]

    sections = {}

    for j in range(9):
        r = r_hub + j * (r_tip - r_hub) / 8

        if j == 0:
            nome = "Hub"
        elif j == 4:
            nome = "Mean"
        elif j == 8:
            nome = "Tip"
        else:
            nome = f"S{j + 1}"

        sections[nome] = r


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

