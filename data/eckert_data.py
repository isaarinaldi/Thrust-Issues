import numpy as np


# ==========================================
# DATI DEL DIAGRAMMA DI ECKERT
# Letture manuali approssimate della figura 5.1
# Tutte le grandezze sono adimensionali
# ==========================================

specific_speed_data = np.array([
    3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0
])

# Coefficiente di portata: scala sinistra
phi_data = np.array([
    0.450, 0.445, 0.445, 0.448, 0.455,
    0.462, 0.470, 0.480, 0.490
])

# Coefficiente di prevalenza: scala destra
psi_data = np.array([
    0.230, 0.200, 0.175, 0.150, 0.130,
    0.112, 0.100, 0.087, 0.078
])

# Rapporto diametro mozzo / diametro esterno: scala sinistra
chi_data = np.array([
    0.560, 0.500, 0.500, 0.500, 0.500,
    0.500, 0.500, 0.500, 0.500
])


# ==========================================
# INTERPOLAZIONE DEI COEFFICIENTI
# ==========================================

def eckert_coefficients(specific_speed):
    """Restituisce phi, psi e chi per una velocità specifica."""

    if not np.isfinite(specific_speed):
        raise ValueError("La velocità specifica deve essere finita.")

    if not specific_speed_data[0] <= specific_speed <= specific_speed_data[-1]:
        raise ValueError(
            "La velocità specifica deve essere compresa tra 3 e 7."
        )

    phi = float(np.interp(
        specific_speed, specific_speed_data, phi_data
    ))

    psi = float(np.interp(
        specific_speed, specific_speed_data, psi_data
    ))

    chi = float(np.interp(
        specific_speed, specific_speed_data, chi_data
    ))

    return phi, psi, chi