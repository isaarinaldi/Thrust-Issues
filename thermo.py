
"""
JET FAN - THERMODYNAMIC AND ENERGY MODEL
Thrust Issues

Simplified momentum and energy calculations.
Pressure thrust is neglected.
"""

from losses import calculate_specific_work
import math
from geometry import maximum_section_speeds

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

def check_mach(triangles, speed_of_sound, mach_limit, section_count):
    """Verifica il Mach massimo sulle sezioni radiali della pala."""

    if not math.isfinite(speed_of_sound) or speed_of_sound <= 0:
        raise ValueError("La velocità del suono deve essere positiva e finita.")

    if not math.isfinite(mach_limit) or not 0 < mach_limit < 1:
        raise ValueError("Il limite di Mach deve essere compreso tra 0 e 1.")

    max_relative_speed, max_absolute_speed = maximum_section_speeds(
        axial_velocity=triangles["Tip"]["c_m"],
        angular_velocity=(
            triangles["Tip"]["U"] / triangles["Tip"]["radius"]
        ),
        hub_radius=triangles["Hub"]["radius"],
        tip_radius=triangles["Tip"]["radius"],
        outlet_swirl_tip=triangles["Tip"]["c_theta2"],
        section_count=section_count,
    )

    mach_relative, mach_absolute, mach_max = mach_numbers(
        max_relative_speed=max_relative_speed,
        max_absolute_speed=max_absolute_speed,
        speed_of_sound=speed_of_sound,
    )

    return {
        "number_of_sections": section_count,
        "max_relative_speed": max_relative_speed,
        "max_absolute_speed": max_absolute_speed,
        "mach_relative": mach_relative,
        "mach_absolute": mach_absolute,
        "mach_max": mach_max,
        "mach_limit": mach_limit,
        "mach_ok": mach_max < mach_limit,
    }