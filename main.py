
"""
JET FAN - PRELIMINARY DESIGN
Thrust Issues

Main program
"""

import csv
import math
from collections.abc import Mapping
from pathlib import Path

import numpy as np
import yaml

from geometry import calculate_velocity_triangles
from machine import preliminary_design, _require_positive_finite
from thermo import operating_point


# ==========================================
# CONFIGURATION FUNCTIONS
# ==========================================

def _read_number(config: Mapping[str, object], key: str) -> float:

    if key not in config:
        raise ValueError(
            f"Missing required configuration value: {key}"
        )

    value = config[key]

    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
    ):
        raise ValueError(
            f"Configuration value {key!r} must be a number."
        )

    try:
        number = float(value)
    except OverflowError:
        raise ValueError(
            f"Configuration value {key!r} must be finite."
        ) from None

    if not math.isfinite(number):
        raise ValueError(
            f"Configuration value {key!r} must be finite."
        )

    return number


def _read_integer(config: Mapping[str, object], key: str) -> int:

    value = _read_number(config, key)

    if not value.is_integer():
        raise ValueError(
            f"Configuration value {key!r} must be an integer."
        )

    return int(value)


# ==========================================
# MAIN PROGRAM
# ==========================================

def main(
    config_path: Path | None = None,
    output_path: Path | None = None
) -> dict[str, dict[str, float]] | None:

    project_dir = Path(__file__).resolve().parent

    if config_path is None:
        config_path = project_dir / "config.yaml"

    # --------------------------------------
    # 1. READ CONFIGURATION
    # --------------------------------------

    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not isinstance(config, Mapping):
        raise ValueError(
            f"Configuration file {config_path} "
            "must contain a YAML mapping."
        )

    nominal_thrust = _read_number(
        config, "nominal_thrust_N"
    )

    air_density = _read_number(
        config, "air_density_kg_m3"
    )

    jet_velocity = _read_number(
        config, "jet_velocity_m_s"
    )

    ambient_velocity = _read_number(
        config, "ambient_velocity_m_s"
    )

    rotor_efficiency = _read_number(
        config, "rotor_efficiency_initial"
    )

    work_done_factor = _read_number(
        config, "work_done_factor"
    )

    max_tip_diameter = _read_number(
        config, "max_tip_diameter_m"
    )

    diameter_fraction = _read_number(
        config, "tip_diameter_fraction"
    )

    speed_min = _read_number(
        config, "specific_speed_min"
    )

    speed_max = _read_number(
        config, "specific_speed_max"
    )

    speed_points = _read_integer(
        config, "specific_speed_points"
    )

    speed_of_sound = _read_number(
        config, "speed_of_sound_m_s"
    )

    mach_limit = _read_number(
        config, "max_mach_number"
    )

    section_count = _read_integer(
        config, "number_of_sections"
    )

    # --------------------------------------
    # 2. INPUT VALIDATION
    # --------------------------------------

    if nominal_thrust <= 0 or air_density <= 0:
        raise ValueError(
            "Nominal thrust and air density must be positive."
        )

    if ambient_velocity < 0 or jet_velocity <= ambient_velocity:
        raise ValueError(
            "Velocities must satisfy "
            "0 <= ambient_velocity < jet_velocity."
        )

    if not 0 < rotor_efficiency <= 1:
        raise ValueError(
            "Rotor efficiency must be between 0 and 1."
        )

    if work_done_factor <= 0:
        raise ValueError(
            "Work-done factor must be positive."
        )

    if max_tip_diameter <= 0 or not 0 < diameter_fraction < 1:
        raise ValueError(
            "Invalid tip diameter or diameter fraction."
        )

    if not 2.5 <= speed_min < speed_max <= 5.0:
        raise ValueError(
            "Specific speed range must be within 2.5 and 5.0."
        )

    if speed_points < 2 or section_count < 3:
        raise ValueError(
            "Invalid number of search points or radial sections."
        )

    if speed_of_sound <= 0 or not 0 < mach_limit < 1:
        raise ValueError(
            "Invalid speed of sound or Mach limit."
        )

    # --------------------------------------
    # 3. OPERATING POINT
    # --------------------------------------

    try:
        (
            flow_rate,
            specific_head,
            specific_work,
            rotor_power
        ) = operating_point(
            nominal_thrust,
            air_density,
            jet_velocity,
            ambient_velocity,
            rotor_efficiency
        )

    except (OverflowError, ZeroDivisionError) as error:
        raise ValueError(
            "Configuration values exceed the supported numeric range."
        ) from error

    for name, value in (
        ("volumetric flow rate", flow_rate),
        ("specific head", specific_head),
        ("specific work", specific_work),
        ("rotor power", rotor_power),
    ):
        _require_positive_finite(name, value)

    # --------------------------------------
    # 4. FIXED TIP DIAMETER
    # --------------------------------------

    tip_diameter = (
        diameter_fraction * max_tip_diameter
    )

    _require_positive_finite(
        "tip diameter", tip_diameter
    )

    # --------------------------------------
    # 5. SPECIFIC SPEED SEARCH
    # --------------------------------------

    specific_speeds = np.linspace(
        speed_min,
        speed_max,
        speed_points
    )

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
            "Configuration values produce results "
            "outside the supported numeric range."
        ) from error

    # --------------------------------------
    # 6. PRINT OPERATING CONDITIONS
    # --------------------------------------

    print("\nJET FAN - PRELIMINARY DESIGN")

    print(f"Nominal thrust: {nominal_thrust:.1f} N")

    print(
        "Pressure thrust: neglected "
        "(equal inlet/outlet static pressure assumed)"
    )

    print(f"Volume flow rate: {flow_rate:.2f} m³/s")

    print(f"Specific head: {specific_head:.2f} J/kg")

    print(f"Specific work: {specific_work:.2f} J/kg")

    print(
        f"Preliminary power: {rotor_power / 1000:.2f} kW"
    )

    print("\nFIXED GEOMETRY")

    print(f"Tip diameter: {tip_diameter:.4f} m")

    tip_clearance = (
        max_tip_diameter - tip_diameter
    ) * 500

    print(
        f"Radial tip clearance: {tip_clearance:.2f} mm"
    )

    # --------------------------------------
    # 7. PRINT SEARCH RESULTS
    # --------------------------------------

    print("\nSPECIFIC SPEED SEARCH")

    print(
        f"{'Omega_s':>8} "
        f"{'RPM':>8} "
        f"{'psi':>8} "
        f"{'phi':>8} "
        f"{'Mach':>8} "
        f"{'Status':>8}"
    )

    for result in results:

        print(
            f"{result['omega_s']:8.2f} "
            f"{result['rpm']:8.1f} "
            f"{result['psi']:8.3f} "
            f"{result['phi']:8.3f} "
            f"{result['mach_max']:8.3f} "
            f"{result['status']:>8}"
        )

    # --------------------------------------
    # 8. SAVE RESULTS TO CSV
    # --------------------------------------

    if output_path is None:
        output_path = (
            project_dir / "preliminary_results.csv"
        )

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=list(results[0])
        )

        writer.writeheader()

        writer.writerows(
            dict(result) for result in results
        )

    print(f"\nResults saved to: {output_path}")

    # --------------------------------------
    # 9. SELECT FEASIBLE CONFIGURATIONS
    # --------------------------------------

    feasible = [
        result
        for result in results
        if result["status"] == "PASS"
    ]

    print(
        f"Configurations evaluated: {len(results)}"
    )

    print(
        "Passing geometry and Mach checks: "
        f"{len(feasible)}"
    )

    if not feasible:
        print("\nNo configuration passes the checks.")
        return

    # --------------------------------------
    # 10. SELECT THE BEST CONFIGURATION
    # --------------------------------------

    selected_design = min(
        feasible,
        key=lambda candidate: math.hypot(
            candidate["psi_deviation_pct"],
            candidate["phi_deviation_pct"]
        ),
    )

    print(
        f"Specific speed: "
        f"{selected_design['omega_s']:.2f}"
    )

    print(
        f"Rotational speed: "
        f"{selected_design['rpm']:.1f} rpm"
    )

    print(
        f"Head coefficient (psi): "
        f"{selected_design['psi']:.4f}"
    )

    print(
        f"Flow coefficient (phi): "
        f"{selected_design['phi']:.4f}"
    )

    print(
        f"Hub-to-tip ratio (chi): "
        f"{selected_design['chi']:.4f}"
    )

    print(
        f"Maximum Mach number: "
        f"{selected_design['mach_max']:.3f}"
    )

    # --------------------------------------
    # 11. VELOCITY TRIANGLES
    # --------------------------------------

    triangles = calculate_velocity_triangles(
        selected_design,
        specific_work=specific_work,
        work_done_factor=work_done_factor,
        speed_of_sound=speed_of_sound,
    )

    print("\n" + "=" * 50)

    print("VELOCITY TRIANGLES - SELECTED DESIGN")

    print("=" * 50)

    print(
        f"Specific speed: "
        f"{selected_design['omega_s']:.2f}"
    )

    print(
        f"Rotational speed: "
        f"{selected_design['rpm']:.2f} rpm"
    )

    for name, data in triangles.items():

        print(f"\n{name.upper()} SECTION")

        print(f"Radius: {data['radius']:.4f} m")

        print(
            f"Peripheral speed: {data['U']:.2f} m/s"
        )

        print(
            f"Axial velocity: {data['c_m']:.2f} m/s"
        )

        print(
            f"Outlet swirl: {data['c_theta2']:.2f} m/s"
        )

        print(
            f"Absolute inlet velocity: {data['c1']:.2f} m/s"
        )

        print(
            f"Absolute outlet velocity: {data['c2']:.2f} m/s"
        )

        print(
            f"Relative inlet velocity: {data['w1']:.2f} m/s"
        )

        print(
            f"Relative outlet velocity: {data['w2']:.2f} m/s"
        )

        print(
            f"Mean relative velocity: {data['w_inf']:.2f} m/s"
        )

        print(
            f"Alpha 1: {data['alpha1']:.2f} deg"
        )

        print(
            f"Alpha 2: {data['alpha2']:.2f} deg"
        )

        print(
            f"Beta 1: {data['beta1']:.2f} deg"
        )

        print(
            f"Beta 2: {data['beta2']:.2f} deg"
        )

        print(
            f"Beta mean: {data['beta_inf']:.2f} deg"
        )

        print(
            f"Mach inlet: {data['Ma1']:.3f}"
        )

        print(
            f"Mach outlet: {data['Ma2']:.3f}"
        )

    return triangles

if __name__ == "__main__":
    main()
