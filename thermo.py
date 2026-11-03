
"""
JET FAN - THERMODYNAMIC AND ENERGY MODEL
Thrust Issues

Simplified momentum and energy calculations.
Pressure thrust is neglected.
"""

from losses import calculate_specific_work


def operating_point(
    nominal_thrust,
    air_density,
    jet_velocity,
    ambient_velocity,
    rotor_efficiency
):
    """
    Calculate the preliminary operating point.

    Returns:
        flow_rate       [m3/s]
        specific_head   [J/kg]
        specific_work   [J/kg]
        rotor_power     [W]
    """

    # Velocity difference and mean velocity
    delta_velocity = jet_velocity - ambient_velocity

    mean_velocity = (
        jet_velocity / 2 + ambient_velocity / 2
    )

    # Volumetric flow rate from momentum balance
    flow_rate = (
        nominal_thrust
        / air_density
        / delta_velocity
    )

    # Specific kinetic energy increase
    specific_head = delta_velocity * mean_velocity

    # Rotor specific work
    specific_work = calculate_specific_work(
        specific_head,
        rotor_efficiency
    )

    # Preliminary shaft power
    rotor_power = (
        nominal_thrust
        * mean_velocity
        / rotor_efficiency
    )

    return (
        flow_rate,
        specific_head,
        specific_work,
        rotor_power
    )


def mach_numbers(
    max_relative_speed,
    max_absolute_speed,
    speed_of_sound
):
    """
    Calculate relative and absolute Mach numbers.
    """

    mach_relative = (
        max_relative_speed / speed_of_sound
    )

    mach_absolute = (
        max_absolute_speed / speed_of_sound
    )

    mach_max = max(
        mach_relative,
        mach_absolute
    )

    return (
        mach_relative,
        mach_absolute,
        mach_max
    )
