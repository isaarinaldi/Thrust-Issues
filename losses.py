
"""
JET FAN - PRELIMINARY LOSS MODEL
Thrust Issues

Only preliminary efficiency assumptions are included.
Detailed aerodynamic loss correlations are not yet implemented.
"""


def calculate_specific_work(specific_head, rotor_efficiency):
    """
    Required specific rotor work [J/kg].

    L = gH / eta_rotor
    """

    if not 0 < rotor_efficiency <= 1:
        raise ValueError(
            "Rotor efficiency must be greater than 0 and at most 1."
        )

    return specific_head / rotor_efficiency


def calculate_outlet_swirl(
    specific_work,
    peripheral_speed,
    work_done_factor
):
    """
    Outlet tangential velocity [m/s].

    c_theta2 = L / (zeta * U)

    Assumes no inlet prerotation.
    """

    if peripheral_speed <= 0:
        raise ValueError("Peripheral speed must be positive.")

    if work_done_factor <= 0:
        raise ValueError("Work-done factor must be positive.")

    return specific_work / (
        work_done_factor * peripheral_speed
    )
