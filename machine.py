
"""
JET FAN - PRELIMINARY DESIGN
Thrust Issues
"""

import math
from typing import TypedDict

from data.eckert_data import eckert_coefficients
from geometry import annulus_geometry, maximum_section_speeds
from losses import calculate_outlet_swirl
from thermo import mach_numbers


# ==========================================
# DESIGN RESULT STRUCTURE
# ==========================================

class DesignResult(TypedDict):
    omega_s: float
    rpm: float
    omega_rad_s: float
    D_tip_m: float
    D_hub_m: float
    tip_clearance_mm: float
    chi: float
    chi_opt: float
    phi: float
    phi_opt: float
    psi: float
    psi_opt: float
    phi_deviation_pct: float
    psi_deviation_pct: float
    c_m_m_s: float
    U_tip_m_s: float
    mach_relative: float
    mach_absolute: float
    mach_max: float
    status: str


# ==========================================
# NUMERICAL VALIDATION
# ==========================================

def _require_positive_finite(name: str, value: float) -> None:

    if not math.isfinite(value) or value <= 0:
        raise ValueError(
            f"Configuration values produce an invalid {name}; "
            "check their magnitudes."
        )


def _validate_design_inputs(
    omega_s: float,
    flow_rate: float,
    specific_head: float,
    specific_work: float,
    work_done_factor: float,
    tip_diameter: float,
    max_tip_diameter: float,
    speed_of_sound: float,
    mach_limit: float,
    section_count: int,
) -> None:
    for name, value in (
        ("specific speed", omega_s),
        ("flow rate", flow_rate),
        ("specific head", specific_head),
        ("specific work", specific_work),
        ("work-done factor", work_done_factor),
        ("tip diameter", tip_diameter),
        ("maximum tip diameter", max_tip_diameter),
        ("speed of sound", speed_of_sound),
        ("Mach limit", mach_limit),
    ):
        _require_positive_finite(name, value)
    if not 0 < mach_limit < 1:
        raise ValueError("Mach limit must be greater than 0 and less than 1.")
    if isinstance(section_count, bool) or not isinstance(section_count, int):
        raise ValueError("section_count must be an integer.")
    if section_count < 2:
        raise ValueError("section_count must be at least 2.")


# ==========================================
# PRELIMINARY DESIGN
# ==========================================

def preliminary_design(
    omega_s: float,
    *,
    flow_rate: float,
    specific_head: float,
    specific_work: float,
    work_done_factor: float,
    tip_diameter: float,
    max_tip_diameter: float,
    speed_of_sound: float,
    mach_limit: float,
    section_count: int,
) -> DesignResult:
    _validate_design_inputs(
        omega_s,
        flow_rate,
        specific_head,
        specific_work,
        work_done_factor,
        tip_diameter,
        max_tip_diameter,
        speed_of_sound,
        mach_limit,
        section_count,
    )

    # --------------------------------------
    # 1. ECKERT REFERENCE COEFFICIENTS
    # --------------------------------------

    phi_opt, psi_opt, chi = eckert_coefficients(omega_s)

    # --------------------------------------
    # 2. ROTATIONAL SPEED
    # --------------------------------------

    angular_velocity = (
        omega_s
        * specific_head**0.75
        / math.sqrt(flow_rate)
    )

    rpm = angular_velocity * 60 / (2 * math.pi)

    # --------------------------------------
    # 3. ROTOR GEOMETRY
    # --------------------------------------

    (
        hub_diameter,
        hub_radius,
        tip_radius,
        annulus_area
    ) = annulus_geometry(
        tip_diameter,
        chi
    )

    # Peripheral speed at rotor tip
    tip_speed = angular_velocity * tip_radius

    # Axial velocity
    axial_velocity = flow_rate / annulus_area

    # --------------------------------------
    # 4. DIMENSIONLESS COEFFICIENTS
    # --------------------------------------

    psi = specific_head / tip_speed**2

    phi = axial_velocity / tip_speed

    psi_deviation = 100 * (psi / psi_opt - 1)

    phi_deviation = 100 * (phi / phi_opt - 1)

    # --------------------------------------
    # 5. OUTLET SWIRL
    # --------------------------------------

    outlet_swirl_tip = calculate_outlet_swirl(
        specific_work,
        tip_speed,
        work_done_factor
    )

    # --------------------------------------
    # 6. MAXIMUM VELOCITY SCREENING
    # --------------------------------------

    (
        max_relative_speed,
        max_absolute_speed
    ) = maximum_section_speeds(
        axial_velocity=axial_velocity,
        angular_velocity=angular_velocity,
        hub_radius=hub_radius,
        tip_radius=tip_radius,
        outlet_swirl_tip=outlet_swirl_tip,
        section_count=section_count,
    )

    # --------------------------------------
    # 7. MACH NUMBERS
    # --------------------------------------

    (
        mach_relative,
        mach_absolute,
        mach_max
    ) = mach_numbers(
        max_relative_speed,
        max_absolute_speed,
        speed_of_sound
    )

    # --------------------------------------
    # 8. DESIGN CONSTRAINTS
    # --------------------------------------

    geometry_ok = (
        0 < hub_diameter
        < tip_diameter
        <= max_tip_diameter
    )

    mach_ok = mach_max < mach_limit

    # --------------------------------------
    # 9. NUMERICAL VALIDATION
    # --------------------------------------

    calculated_values = (
        ("angular velocity", angular_velocity),
        ("rotational speed", rpm),
        ("tip speed", tip_speed),
        ("annulus area", annulus_area),
        ("axial velocity", axial_velocity),
        ("flow coefficient", phi),
        ("head coefficient", psi),
        ("relative Mach number", mach_relative),
        ("absolute Mach number", mach_absolute),
    )

    for name, value in calculated_values:
        _require_positive_finite(name, value)

    if (
        not math.isfinite(phi_deviation)
        or not math.isfinite(psi_deviation)
    ):
        raise ValueError(
            "Configuration values produce invalid coefficient deviations."
        )

    # --------------------------------------
    # 10. RETURN DESIGN RESULTS
    # --------------------------------------

    return {
        "omega_s": float(omega_s),
        "rpm": rpm,
        "omega_rad_s": angular_velocity,
        "D_tip_m": tip_diameter,
        "D_hub_m": hub_diameter,
        "tip_clearance_mm": (
            max_tip_diameter - tip_diameter
        ) * 500,
        "chi": chi,
        "chi_opt": chi,
        "phi": phi,
        "phi_opt": phi_opt,
        "psi": psi,
        "psi_opt": psi_opt,
        "phi_deviation_pct": phi_deviation,
        "psi_deviation_pct": psi_deviation,
        "c_m_m_s": axial_velocity,
        "U_tip_m_s": tip_speed,
        "mach_relative": mach_relative,
        "mach_absolute": mach_absolute,
        "mach_max": mach_max,
        "status": (
            "PASS" if geometry_ok and mach_ok else "FAIL"
        ),
    }
