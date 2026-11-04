import math
from typing import TypedDict


class LossCoefficients(TypedDict):
    Y_P_hub: float
    Y_P_mean: float
    Y_P_tip: float
    Y_sg: float


# =============================================================================
# FUNZIONI DI SERVIZIO RICHIESTE DAI MODULI DEI COLLEGHI (geometry.py / thermo.py)
# =============================================================================

def calculate_specific_work(specific_head: float, rotor_efficiency: float) -> float:
    """Calcola il lavoro specifico di Eulero L = Y / eta_rot [J/kg]."""
    return specific_head / rotor_efficiency


def calculate_outlet_swirl(
    specific_work: float, tip_speed: float, work_done_factor: float
) -> float:
    """Calcola la velocita tangenziale residua allo scarico al tip c_theta2_tip [m/s]."""
    return specific_work / (work_done_factor * tip_speed)


# =============================================================================
# FORMULA DI TRAUPEL (Perdite di Profilo Y_P)
# =============================================================================

def compute_traupel_profile_loss(
    w1: float, w2: float, beta1_deg: float, beta2_deg: float, solidity: float
) -> float:
    """
    Calcola il coefficiente di perdita di profilo Y_P secondo la correlazione di Traupel.
    I valori di beta sono gli angoli del flusso relativo rispetto alla direzione tangenziale.
    """
    beta1_rad = math.radians(beta1_deg)
    beta2_rad = math.radians(beta2_deg)

    # Decelerazione del flusso relativo
    w_ratio = w2 / w1

    # Termine di deviazione ed effetto di carico (Traupel)
    sin_beta2 = math.sin(beta2_rad)
    if sin_beta2 <= 0:
        raise ValueError(f"Angolo beta2 non valido: {beta2_deg} gradi")

    # Coefficiente adimensionale di profilo
    y_p = 0.04 * (1.0 + (solidity / sin_beta2) * ((1.0 - w_ratio) ** 2))
    return float(y_p)


# =============================================================================
# FORMULA DI VAVRA (Perdite Secondarie e di Gioco Y_{s+g})
# =============================================================================

def compute_vavra_secondary_clearance_loss(
    triangles: dict[str, dict[str, float]],
    aero_design: dict[str, float],
    design: dict[str, float],
) -> float:
    """
    Calcola il coefficiente di perdita combinato secondario e di gioco radiale (Y_sg)
    secondo la correlazione empirica di Vavra al raggio medio.
    """
    # Geometria del condotto dal modulo dei colleghi
    d_tip = design["D_tip_m"]
    d_hub = design["D_hub_m"]
    h_blade = (d_tip - d_hub) / 2.0  # Altezza pala [m]
    g_clearance = design["tip_clearance_mm"] / 1000.0  # Gioco radiale [m]

    # Parametri cinematici alla sezione Mean
    beta1_deg = triangles["Mean"]["beta1"]
    beta2_deg = triangles["Mean"]["beta2"]
    beta_inf_deg = triangles["Mean"]["beta_inf"]

    solidity = aero_design.get("sigma_eff", 1.12)

    # Deflessione del flusso delta_beta = beta2 - beta1
    delta_beta_rad = math.radians(abs(beta2_deg - beta1_deg))
    beta_inf_rad = math.radians(beta_inf_deg)

    # Coefficiente di portanza equivalente C_L (Vavra)
    sin_beta_inf = math.sin(beta_inf_rad)
    c_l = 2.0 * (1.0 / solidity) * delta_beta_rad * sin_beta_inf

    # Componente secondaria Y_s e componente di gioco Y_g
    y_secondary = 0.03 * (c_l**2) * (solidity / (h_blade / d_tip))
    y_clearance = 0.25 * (g_clearance / h_blade) * c_l

    return float(y_secondary + y_clearance)


# =============================================================================
# CALCOLO GLOBALE DEI COEFFICIENTI Y
# =============================================================================

def compute_all_Y_loss_coefficients(
    triangles: dict[str, dict[str, float]],
    aero_design: dict[str, float],
    design: dict[str, float],
) -> LossCoefficients:
    """
    Riceve i triangoli di velocita (da geometry.py) e la geometria (da machine.py)
    per calcolare i 4 coefficienti di perdita Y_P (Hub, Mean, Tip) e Y_sg.
    """
    solidity = aero_design.get("sigma_eff", 1.12)

    # Calcolo Y_P per le 3 sezioni radiali
    y_p_hub = compute_traupel_profile_loss(
        triangles["Hub"]["w1"],
        triangles["Hub"]["w2"],
        triangles["Hub"]["beta1"],
        triangles["Hub"]["beta2"],
        solidity,
    )

    y_p_mean = compute_traupel_profile_loss(
        triangles["Mean"]["w1"],
        triangles["Mean"]["w2"],
        triangles["Mean"]["beta1"],
        triangles["Mean"]["beta2"],
        solidity,
    )

    y_p_tip = compute_traupel_profile_loss(
        triangles["Tip"]["w1"],
        triangles["Tip"]["w2"],
        triangles["Tip"]["beta1"],
        triangles["Tip"]["beta2"],
        solidity,
    )

    # Calcolo Y_sg (Vavra)
    y_sg = compute_vavra_secondary_clearance_loss(triangles, aero_design, design)

    return {
        "Y_P_hub": y_p_hub,
        "Y_P_mean": y_p_mean,
        "Y_P_tip": y_p_tip,
        "Y_sg": y_sg,
    }