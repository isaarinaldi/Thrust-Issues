
"""
JET FAN - GEOMETRY AND VELOCITY TRIANGLES
Thrust Issues
"""

import math
from typing import TYPE_CHECKING

from losses import calculate_outlet_swirl

if TYPE_CHECKING:
    from machine import DesignResult


# ==========================================
# ANNULUS GEOMETRY
# ==========================================

def annulus_geometry(tip_diameter, chi):
    """
    Calculate hub diameter, radii and annulus area.

    chi = D_hub / D_tip
    """
    _require_positive_finite("tip diameter", tip_diameter)
    if not math.isfinite(chi) or not 0 < chi < 1:
        raise ValueError("Hub-to-tip diameter ratio must be between 0 and 1.")

    tip_radius = tip_diameter / 2

    hub_diameter = chi * tip_diameter

    hub_radius = hub_diameter / 2

    annulus_area = (
        math.pi / 4
        * (tip_diameter**2 - hub_diameter**2)
    )

    return (
        hub_diameter,
        hub_radius,
        tip_radius,
        annulus_area
    )


# ==========================================
# MAXIMUM VELOCITIES ALONG THE BLADE
# ==========================================

def maximum_section_speeds(
    *,
    axial_velocity,
    angular_velocity,
    hub_radius,
    tip_radius,
    outlet_swirl_tip,
    section_count
):
    """
    Evaluate relative and absolute velocities
    along radial sections of the rotor.

    Assumptions:
        Constant axial velocity
        No inlet prerotation
        Free vortex at rotor outlet
    """
    _require_positive_finite("axial velocity", axial_velocity)
    _require_positive_finite("angular velocity", angular_velocity)
    _require_positive_finite("hub radius", hub_radius)
    _require_positive_finite("tip radius", tip_radius)
    if tip_radius <= hub_radius:
        raise ValueError("Tip radius must exceed hub radius.")
    if not math.isfinite(outlet_swirl_tip):
        raise ValueError("Tip outlet swirl must be finite.")
    if isinstance(section_count, bool) or not isinstance(section_count, int):
        raise ValueError("section_count must be an integer.")
    if section_count < 2:
        raise ValueError("section_count must be at least 2.")

    max_relative_speed = 0.0
    max_absolute_speed = 0.0

    for index in range(section_count):

        radius = (
            hub_radius
            + (tip_radius - hub_radius)
            * index / (section_count - 1)
        )

        blade_speed = angular_velocity * radius

        # Free vortex distribution
        outlet_swirl = (
            outlet_swirl_tip * tip_radius / radius
        )

        # Inlet relative velocity
        inlet_relative_speed = math.hypot(
            axial_velocity,
            blade_speed
        )

        # Outlet relative velocity
        outlet_relative_speed = math.hypot(
            axial_velocity,
            blade_speed - outlet_swirl
        )

        # Outlet absolute velocity
        outlet_absolute_speed = math.hypot(
            axial_velocity,
            outlet_swirl
        )

        max_relative_speed = max(
            max_relative_speed,
            inlet_relative_speed,
            outlet_relative_speed
        )

        max_absolute_speed = max(
            max_absolute_speed,
            axial_velocity,
            outlet_absolute_speed
        )

    return (
        max_relative_speed,
        max_absolute_speed
    )


# ==========================================
# VELOCITY TRIANGLES
# ==========================================

def calculate_velocity_triangles(
    design: "DesignResult",
    *,
    specific_work,
    work_done_factor,
    speed_of_sound
):
    """
    Calculate velocity triangles at:
        Hub
        Mean
        Tip

    Absolute flow angles are measured from the axial direction.
    """
    _require_positive_finite("specific work", specific_work)
    _require_positive_finite("work-done factor", work_done_factor)
    _require_positive_finite("speed of sound", speed_of_sound)

    angular_velocity = design["omega_rad_s"]

    tip_radius = design["D_tip_m"] / 2

    hub_radius = design["D_hub_m"] / 2

    axial_velocity = design["c_m_m_s"]

    tip_speed = design["U_tip_m_s"]

    # Outlet swirl velocity at the tip
    outlet_swirl_tip = calculate_outlet_swirl(
        specific_work,
        tip_speed,
        work_done_factor
    )

    # Reference radial sections
    radii = {
        "Hub": hub_radius,
        "Mean": (hub_radius + tip_radius) / 2,
        "Tip": tip_radius,
    }

    triangles = {}

    for name, radius in radii.items():

        # Peripheral velocity
        blade_speed = angular_velocity * radius

        # Free vortex distribution
        outlet_swirl = (
            outlet_swirl_tip * tip_radius / radius
        )

        # Relative velocities
        inlet_relative_speed = math.hypot(
            axial_velocity,
            blade_speed
        )

        outlet_relative_speed = math.hypot(
            axial_velocity,
            blade_speed - outlet_swirl
        )

        # Absolute outlet velocity
        outlet_absolute_speed = math.hypot(
            axial_velocity,
            outlet_swirl
        )

        # Euler work consistency check
        work_check = (
            work_done_factor
            * blade_speed
            * outlet_swirl
        )

        if not math.isclose(
            specific_work,
            work_check,
            rel_tol=1e-9
        ):
            raise ValueError(
                f"Euler work check failed at {name} section."
            )

        triangles[name] = {

            "radius": radius,

            "U": blade_speed,

            "c_m": axial_velocity,

            "c_theta2": outlet_swirl,

            "c1": axial_velocity,

            "c2": outlet_absolute_speed,

            "c_inf": math.hypot(
                axial_velocity,
                outlet_swirl / 2
            ),

            "w1": inlet_relative_speed,

            "w2": outlet_relative_speed,

            "w_inf": math.hypot(
                axial_velocity,
                blade_speed - outlet_swirl / 2
            ),

            "alpha1": 0.0,

            "alpha2": math.degrees(
                math.atan2(
                    outlet_swirl,
                    axial_velocity
                )
            ),

            "beta1": math.degrees(
                math.atan2(
                    axial_velocity,
                    blade_speed
                )
            ),

            "beta2": math.degrees(
                math.atan2(
                    axial_velocity,
                    blade_speed - outlet_swirl
                )
            ),

            "beta_inf": math.degrees(
                math.atan2(
                    axial_velocity,
                    blade_speed - outlet_swirl / 2
                )
            ),

            "Ma1": (
                inlet_relative_speed / speed_of_sound
            ),

            "Ma2": (
                outlet_relative_speed / speed_of_sound
            ),
        }

    return triangles


def _require_positive_finite(name, value):
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be positive and finite.")
