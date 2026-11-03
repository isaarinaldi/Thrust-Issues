import csv
import math
from collections.abc import Mapping
from pathlib import Path
from typing import TypedDict

import numpy as np
import yaml

from data.eckert_data import eckert_coefficients


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


def _read_number(config: Mapping[str, object], key: str) -> float:
    if key not in config:
        raise ValueError(f"Missing required configuration value: {key}")
    value = config[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Configuration value {key!r} must be a number.")
    try:
        number = float(value)
    except OverflowError:
        raise ValueError(f"Configuration value {key!r} must be finite.") from None
    if not math.isfinite(number):
        raise ValueError(f"Configuration value {key!r} must be finite.")
    return number


def _read_integer(config: Mapping[str, object], key: str) -> int:
    value = _read_number(config, key)
    if not value.is_integer():
        raise ValueError(f"Configuration value {key!r} must be an integer.")
    return int(value)


def _require_positive_finite(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(
            f"Configuration values produce an invalid {name}; check their magnitudes."
        )


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
    phi_opt, psi_opt, chi = eckert_coefficients(omega_s)
    angular_velocity = omega_s * specific_head**0.75 / math.sqrt(flow_rate)
    rpm = angular_velocity * 60 / (2 * math.pi)
    tip_radius = tip_diameter / 2
    tip_speed = angular_velocity * tip_radius

    hub_diameter = chi * tip_diameter
    hub_radius = hub_diameter / 2
    annulus_area = math.pi / 4 * (tip_diameter**2 - hub_diameter**2)
    axial_velocity = flow_rate / annulus_area

    psi = specific_head / tip_speed**2
    phi = axial_velocity / tip_speed
    psi_deviation = 100 * (psi / psi_opt - 1)
    phi_deviation = 100 * (phi / phi_opt - 1)
    outlet_swirl_tip = specific_work / (work_done_factor * tip_speed)

    max_relative_speed = 0.0
    max_absolute_speed = 0.0
    for index in range(section_count):
        radius = hub_radius + (tip_radius - hub_radius) * index / (section_count - 1)
        blade_speed = angular_velocity * radius
        outlet_swirl = outlet_swirl_tip * tip_radius / radius
        inlet_relative_speed = math.hypot(axial_velocity, blade_speed)
        outlet_relative_speed = math.hypot(
            axial_velocity, blade_speed - outlet_swirl
        )
        outlet_absolute_speed = math.hypot(axial_velocity, outlet_swirl)
        max_relative_speed = max(
            max_relative_speed, inlet_relative_speed, outlet_relative_speed
        )
        max_absolute_speed = max(
            max_absolute_speed, axial_velocity, outlet_absolute_speed
        )

    mach_relative = max_relative_speed / speed_of_sound
    mach_absolute = max_absolute_speed / speed_of_sound
    mach_max = max(mach_relative, mach_absolute)
    geometry_ok = 0 < hub_diameter < tip_diameter <= max_tip_diameter
    mach_ok = mach_max < mach_limit

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
    if not math.isfinite(phi_deviation) or not math.isfinite(psi_deviation):
        raise ValueError("Configuration values produce invalid coefficient deviations.")

    return {
        "omega_s": float(omega_s),
        "rpm": rpm,
        "omega_rad_s": angular_velocity,
        "D_tip_m": tip_diameter,
        "D_hub_m": hub_diameter,
        "tip_clearance_mm": (max_tip_diameter - tip_diameter) * 500,
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
        "status": "PASS" if geometry_ok and mach_ok else "FAIL",
    }


def calculate_velocity_triangles(
    design: DesignResult,
    *,
    specific_work: float,
    work_done_factor: float,
    speed_of_sound: float,
) -> dict[str, dict[str, float]]:
    angular_velocity = design["omega_rad_s"]
    tip_radius = design["D_tip_m"] / 2
    hub_radius = design["D_hub_m"] / 2
    axial_velocity = design["c_m_m_s"]
    tip_speed = design["U_tip_m_s"]
    outlet_swirl_tip = specific_work / (work_done_factor * tip_speed)
    radii = {
        "Hub": hub_radius,
        "Mean": (hub_radius + tip_radius) / 2,
        "Tip": tip_radius,
    }
    triangles: dict[str, dict[str, float]] = {}

    for name, radius in radii.items():
        blade_speed = angular_velocity * radius
        outlet_swirl = outlet_swirl_tip * tip_radius / radius
        inlet_relative_speed = math.hypot(axial_velocity, blade_speed)
        outlet_relative_speed = math.hypot(
            axial_velocity, blade_speed - outlet_swirl
        )
        outlet_absolute_speed = math.hypot(axial_velocity, outlet_swirl)
        work_check = work_done_factor * blade_speed * outlet_swirl
        if not math.isclose(specific_work, work_check, rel_tol=1e-9):
            raise ValueError(f"Euler work check failed at {name} section.")

        triangles[name] = {
            "radius": radius,
            "U": blade_speed,
            "c_m": axial_velocity,
            "c_theta2": outlet_swirl,
            "c1": axial_velocity,
            "c2": outlet_absolute_speed,
            "c_inf": math.hypot(axial_velocity, outlet_swirl / 2),
            "w1": inlet_relative_speed,
            "w2": outlet_relative_speed,
            "w_inf": math.hypot(
                axial_velocity, blade_speed - outlet_swirl / 2
            ),
            "alpha1": 90.0,
            "alpha2": math.degrees(math.atan2(axial_velocity, outlet_swirl)),
            "beta1": math.degrees(math.atan2(axial_velocity, blade_speed)),
            "beta2": math.degrees(
                math.atan2(axial_velocity, blade_speed - outlet_swirl)
            ),
            "beta_inf": math.degrees(
                math.atan2(axial_velocity, blade_speed - outlet_swirl / 2)
            ),
            "Ma1": inlet_relative_speed / speed_of_sound,
            "Ma2": outlet_relative_speed / speed_of_sound,
        }

    return triangles


def main(
    config_path: Path | None = None, output_path: Path | None = None
) -> None:
    project_dir = Path(__file__).resolve().parent
    if config_path is None:
        config_path = project_dir / "config.yaml"

    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)
    if not isinstance(config, Mapping):
        raise ValueError(f"Configuration file {config_path} must contain a YAML mapping.")

    nominal_thrust = _read_number(config, "nominal_thrust_N")
    air_density = _read_number(config, "air_density_kg_m3")
    jet_velocity = _read_number(config, "jet_velocity_m_s")
    ambient_velocity = _read_number(config, "ambient_velocity_m_s")
    rotor_efficiency = _read_number(config, "rotor_efficiency_initial")
    work_done_factor = _read_number(config, "work_done_factor")
    max_tip_diameter = _read_number(config, "max_tip_diameter_m")
    diameter_fraction = _read_number(config, "tip_diameter_fraction")
    speed_min = _read_number(config, "specific_speed_min")
    speed_max = _read_number(config, "specific_speed_max")
    speed_points = _read_integer(config, "specific_speed_points")
    speed_of_sound = _read_number(config, "speed_of_sound_m_s")
    mach_limit = _read_number(config, "max_mach_number")
    section_count = _read_integer(config, "number_of_sections")

    if nominal_thrust <= 0 or air_density <= 0:
        raise ValueError("nominal_thrust_N and air_density_kg_m3 must be positive.")
    if ambient_velocity < 0 or jet_velocity <= ambient_velocity:
        raise ValueError(
            "Velocities must satisfy 0 <= ambient_velocity_m_s < jet_velocity_m_s."
        )
    if not 0 < rotor_efficiency <= 1:
        raise ValueError("rotor_efficiency_initial must be greater than zero and at most one.")
    if work_done_factor <= 0:
        raise ValueError("work_done_factor must be greater than zero.")
    if max_tip_diameter <= 0 or not 0 < diameter_fraction < 1:
        raise ValueError(
            "max_tip_diameter_m must be positive and tip_diameter_fraction "
            "must be greater than zero and less than one."
        )
    if not 2.5 <= speed_min < speed_max <= 5.0:
        raise ValueError(
            "Specific speed bounds must satisfy 2.5 <= minimum < maximum <= 5.0 "
            "to stay within the Eckert reference data."
        )
    if speed_points < 2 or section_count < 3:
        raise ValueError("specific_speed_points must be at least two and "
                         "number_of_sections at least three.")
    if speed_of_sound <= 0 or not 0 < mach_limit < 1:
        raise ValueError("Invalid speed_of_sound_m_s or max_mach_number.")

    delta_velocity = jet_velocity - ambient_velocity
    mean_velocity = jet_velocity / 2 + ambient_velocity / 2
    try:
        flow_rate = nominal_thrust / air_density / delta_velocity
        specific_head = delta_velocity * mean_velocity
        specific_work = specific_head / rotor_efficiency
        rotor_power = nominal_thrust * mean_velocity / rotor_efficiency
    except (OverflowError, ZeroDivisionError) as error:
        raise ValueError("Configuration values exceed the supported numeric range.") from error

    for name, value in (
        ("volumetric flow rate", flow_rate),
        ("specific head", specific_head),
        ("specific work", specific_work),
        ("rotor power", rotor_power),
    ):
        _require_positive_finite(name, value)

    tip_diameter = diameter_fraction * max_tip_diameter
    _require_positive_finite("tip diameter", tip_diameter)
    specific_speeds = np.linspace(speed_min, speed_max, speed_points)
    try:
        results = [
            preliminary_design(
                float(omega_s),
                flow_rate=flow_rate,
                specific_head=specific_head,
                specific_work=specific_work,
                work_done_factor=work_done_factor,
                tip_diameter=tip_diameter,
                max_tip_diameter=max_tip_diameter,
                speed_of_sound=speed_of_sound,
                mach_limit=mach_limit,
                section_count=section_count,
            )
            for omega_s in specific_speeds
        ]
    except (OverflowError, ZeroDivisionError) as error:
        raise ValueError(
            "Configuration values produce results outside the supported numeric range."
        ) from error

    print("\nJET FAN - PRELIMINARY DESIGN")
    print(f"Nominal thrust: {nominal_thrust:.1f} N")
    print("Pressure thrust: neglected (equal inlet/outlet static pressure assumed)")
    print(f"Volume flow rate: {flow_rate:.2f} m³/s")
    print(f"Specific head: {specific_head:.2f} J/kg")
    print(f"Specific work: {specific_work:.2f} J/kg")
    print(f"Preliminary power: {rotor_power / 1000:.2f} kW")
    print("\nFIXED GEOMETRY")
    print(f"Tip diameter: {tip_diameter:.4f} m")
    print(f"Radial tip clearance: {(max_tip_diameter - tip_diameter) * 500:.2f} mm")

    print("\nSPECIFIC SPEED SEARCH")
    print(f"{'Omega_s':>8} {'RPM':>8} {'psi':>8} {'phi':>8} {'Mach':>8} {'Status':>8}")
    for result in results:
        print(
            f"{result['omega_s']:8.2f} {result['rpm']:8.1f} "
            f"{result['psi']:8.3f} {result['phi']:8.3f} "
            f"{result['mach_max']:8.3f} {result['status']:>8}"
        )

    if output_path is None:
        output_path = project_dir / "preliminary_results.csv"
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(dict(result) for result in results)
    print(f"\nResults saved to: {output_path}")

    feasible = [result for result in results if result["status"] == "PASS"]
    print(f"Configurations evaluated: {len(results)}")
    print(f"Passing geometry and Mach checks: {len(feasible)}")
    if not feasible:
        print("\nNo configuration passes the checks.")
        return

    # Compare percentage deviations from the approximate Eckert reference values.
    selected_design = min(
        feasible,
        key=lambda candidate: math.hypot(
            candidate["psi_deviation_pct"], candidate["phi_deviation_pct"]
        ),
    )
    print(f"Specific speed: {selected_design['omega_s']:.2f}")
    print(f"Rotational speed: {selected_design['rpm']:.1f} rpm")
    print(f"Head coefficient (psi): {selected_design['psi']:.4f}")
    print(f"Flow coefficient (phi): {selected_design['phi']:.4f}")
    print(f"Hub-to-tip ratio (chi): {selected_design['chi']:.4f}")
    print(f"Maximum Mach number: {selected_design['mach_max']:.3f}")

    triangles = calculate_velocity_triangles(
        selected_design,
        specific_work=specific_work,
        work_done_factor=work_done_factor,
        speed_of_sound=speed_of_sound,
    )
    print("\n" + "=" * 50)
    print("VELOCITY TRIANGLES - SELECTED DESIGN")
    print("=" * 50)
    print(f"Specific speed: {selected_design['omega_s']:.2f}")
    print(f"Rotational speed: {selected_design['rpm']:.2f} rpm")
    for name, data in triangles.items():
        print(f"\n{name.upper()} SECTION")
        print(f"Radius: {data['radius']:.4f} m")
        print(f"Peripheral speed: {data['U']:.2f} m/s")
        print(f"Axial velocity: {data['c_m']:.2f} m/s")
        print(f"Outlet swirl: {data['c_theta2']:.2f} m/s")
        print(f"Absolute inlet velocity: {data['c1']:.2f} m/s")
        print(f"Absolute outlet velocity: {data['c2']:.2f} m/s")
        print(f"Relative inlet velocity: {data['w1']:.2f} m/s")
        print(f"Relative outlet velocity: {data['w2']:.2f} m/s")
        print(f"Mean relative velocity: {data['w_inf']:.2f} m/s")
        print(f"Alpha 1: {data['alpha1']:.2f} deg")
        print(f"Alpha 2: {data['alpha2']:.2f} deg")
        print(f"Beta 1: {data['beta1']:.2f} deg")
        print(f"Beta 2: {data['beta2']:.2f} deg")
        print(f"Beta mean: {data['beta_inf']:.2f} deg")
        print(f"Mach inlet: {data['Ma1']:.3f}")
        print(f"Mach outlet: {data['Ma2']:.3f}")


if __name__ == "__main__":
    main()
