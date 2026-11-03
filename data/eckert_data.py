
import math
import numpy as np

# Preliminary digitization of the Eckert diagram.
# Columns: Omega_s, Phi_opt, psi_opt.
# Approximate values, to be refined before final design.

ECKERT_DATA = np.array([
    [2.50, 0.450, 0.260],
    [2.75, 0.445, 0.239],
    [3.00, 0.441, 0.216],
    [3.25, 0.438, 0.201],
    [3.50, 0.437, 0.185],
    [3.75, 0.436, 0.173],
    [4.00, 0.437, 0.161],
    [4.25, 0.438, 0.152],
    [4.50, 0.440, 0.142],
    [4.75, 0.443, 0.134],
    [5.00, 0.446, 0.127],
])


def eckert_coefficients(omega_s):
    """Return approximate reference coefficients."""

    x = ECKERT_DATA[:, 0]

    if not (x[0] <= omega_s <= x[-1]):
        raise ValueError("Specific speed outside Eckert range.")

    phi_opt = float(
        np.interp(omega_s, x, ECKERT_DATA[:, 1])
    )
    psi_opt = float(
        np.interp(omega_s, x, ECKERT_DATA[:, 2])
    )

    # Chi is derived from the similitude identity,
    # not independently digitized from the chart.
    chi_squared = (
        1 - omega_s**2 * psi_opt**1.5
        / (math.pi * phi_opt)
    )

    if not (0 < chi_squared < 1):
        raise ValueError(
            "Inconsistent Eckert reference coefficients."
        )

    chi_opt = math.sqrt(chi_squared)

    return phi_opt, psi_opt, chi_opt
