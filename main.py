"""Command-line entry point for the preliminary jet-fan design."""

import argparse
import csv
import math
from collections.abc import Mapping
from pathlib import Path

import numpy as np
import yaml

from geometry import calculate_velocity_triangles
from machine import preliminary_design
from plots import plot_design_search
from thermo import air_properties, operating_point


def _read_number(config: Mapping[str, object], key: str) -> float:
    value = config.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Configuration value {key!r} must be a number.")
    try:
        number = float(value)
    except OverflowError:
        raise ValueError(
            f"Configuration value {key!r} must be finite."
        ) from None
    if not math.isfinite(number):
        raise ValueError(f"Configuration value {key!r} must be finite.")
    return number


def _read_integer(config: Mapping[str, object], key: str) -> int:
    number = _read_number(config, key)
    if not number.is_integer():
        raise ValueError(f"Configuration value {key!r} must be an integer.")
    return int(number)


def _configured_path(
    config: Mapping[str, object],
    key: str,
    config_directory: Path,
    default: str,
) -> Path:
    value = config.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Configuration value {key!r} must be a path string.")
    path = Path(value).expanduser()
    return path if path.is_absolute() else config_directory / path


def main(
    config_path: Path | None = None,
    output_path: Path | None = None,
    *,
    generate_plots: bool = True,
) -> None:
    config_path = Path(config_path or Path(__file__).with_name("config.yaml"))
    config_path = config_path.expanduser().resolve()
    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)
    if not isinstance(config, Mapping):
        raise ValueError(
            f"Configuration file {config_path} must contain a YAML mapping."
        )

    nominal_thrust = _read_number(config, "nominal_thrust_N")
    jet_velocity = _read_number(config, "jet_velocity_m_s")
    ambient_velocity = _read_number(config, "ambient_velocity_m_s")
    rotor_efficiency = _read_number(config, "rotor_efficiency_initial")
    work_done_factor = _read_number(config, "work_done_factor")
    max_tip_diameter = _read_number(config, "max_tip_diameter_m")
    diameter_fraction = _read_number(config, "tip_diameter_fraction")
    speed_min = _read_number(config, "specific_speed_min")
    speed_max = _read_number(config, "specific_speed_max")
    speed_points = _read_integer(config, "specific_speed_points")
    mach_limit = _read_number(config, "max_mach_number")
    section_count = _read_integer(config, "number_of_sections")
    air_density, speed_of_sound = air_properties(config)

    if nominal_thrust <= 0:
        raise ValueError("nominal_thrust_N must be greater than zero.")
    if ambient_velocity < 0 or jet_velocity <= ambient_velocity:
        raise ValueError(
            "Velocities must satisfy 0 <= ambient_velocity_m_s "
            "< jet_velocity_m_s."
        )
    if not 0 < rotor_efficiency <= 1:
        raise ValueError(
            "rotor_efficiency_initial must be greater than 0 and at most 1."
        )
    if work_done_factor <= 0:
        raise ValueError("work_done_factor must be greater than zero.")
    if max_tip_diameter <= 0 or not 0 < diameter_fraction < 1:
        raise ValueError(
            "max_tip_diameter_m must be positive and "
            "tip_diameter_fraction must be between 0 and 1."
        )
    if not 2.5 <= speed_min < speed_max <= 5.0:
        raise ValueError(
            "Specific speed range must satisfy 2.5 <= min < max <= 5.0."
        )
    if speed_points < 2 or section_count < 3:
        raise ValueError(
            "specific_speed_points must be at least 2 and "
            "number_of_sections must be at least 3."
        )
    if not 0 < mach_limit < 1:
        raise ValueError("max_mach_number must be between 0 and 1.")

    flow_rate, specific_head, specific_work, rotor_power = operating_point(
        nominal_thrust,
        air_density,
        jet_velocity,
        ambient_velocity,
        rotor_efficiency,
    )

    tip_diameter = diameter_fraction * max_tip_diameter
    specific_speeds = np.linspace(speed_min, speed_max, speed_points)
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

    if output_path is None:
        output_path = _configured_path(
            config,
            "output_csv",
            config_path.parent,
            "preliminary_results.csv",
        )
    else:
        output_path = Path(output_path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(dict(result) for result in results)

    feasible = [result for result in results if result["status"] == "PASS"]
    print("\nJET FAN - PRELIMINARY DESIGN")
    print(f"Nominal thrust: {nominal_thrust:.1f} N")
    print("Pressure thrust neglected (equal inlet/outlet static pressure assumed)")
    print(f"Air density: {air_density:.4f} kg/m³")
    print(f"Speed of sound: {speed_of_sound:.2f} m/s")
    print(f"Volume flow rate: {flow_rate:.2f} m³/s")
    print(f"Specific head: {specific_head:.2f} J/kg")
    print(f"Specific work: {specific_work:.2f} J/kg")
    print(f"Preliminary power: {float(rotor_power) / 1000:.2f} kW")
    print(f"Tip diameter: {tip_diameter:.4f} m")
    print(
        f"Radial tip clearance: "
        f"{(max_tip_diameter - tip_diameter) * 500:.2f} mm"
    )
    print(f"Results saved to: {output_path}")
    print(f"Configurations evaluated: {len(results)}")
    print(f"Passing geometry and Mach screening: {len(feasible)}")

    if not feasible:
        raise ValueError(
            "No candidate passed the geometry and Mach screening; "
            "results were written to the CSV."
        )

    selected = min(
        feasible,
        key=lambda result: math.hypot(
            result["psi_deviation_pct"],
            result["phi_deviation_pct"],
        ),
    )
    print(
        "\nClosest Eckert-coefficient match among screening-pass candidates "
        "(not a validated aerodynamic design):"
    )
    print(f"Specific speed: {selected['omega_s']:.2f}")
    print(f"Rotational speed: {selected['rpm']:.1f} rpm")
    print(
        f"Head coefficient psi: {selected['psi']:.4f} "
        f"(reference {selected['psi_opt']:.4f}, "
        f"deviation {selected['psi_deviation_pct']:+.1f}%)"
    )
    print(
        f"Flow coefficient phi: {selected['phi']:.4f} "
        f"(reference {selected['phi_opt']:.4f}, "
        f"deviation {selected['phi_deviation_pct']:+.1f}%)"
    )
    print(f"Hub-to-tip ratio chi: {selected['chi']:.4f}")
    print(f"Maximum screened Mach number: {selected['mach_max']:.3f}")

    triangles = calculate_velocity_triangles(
        selected,
        specific_work=specific_work,
        work_done_factor=work_done_factor,
        speed_of_sound=speed_of_sound,
    )
    _print_velocity_triangles(triangles)

    if generate_plots:
        figure_directory = _configured_path(
            config,
            "figure_directory",
            config_path.parent,
            "outputs/figures",
        )
        figure_paths = plot_design_search(results, figure_directory)
        print(f"Figures saved to: {figure_directory}")
        for figure_path in figure_paths:
            print(f"  {figure_path.name}")


def _print_velocity_triangles(triangles: Mapping[str, Mapping[str, float]]) -> None:
    print("\nVELOCITY TRIANGLES - SELECTED CANDIDATE")
    for name, values in triangles.items():
        print(
            f"{name}: U={values['U']:.2f} m/s, "
            f"c_m={values['c_m']:.2f} m/s, "
            f"c_theta2={values['c_theta2']:.2f} m/s, "
            f"alpha1={values['alpha1']:.2f}°, "
            f"alpha2={values['alpha2']:.2f}°, "
            f"beta1={values['beta1']:.2f}°, "
            f"beta2={values['beta2']:.2f}°"
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the preliminary jet-fan design."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="YAML configuration file (default: config.yaml next to main.py).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="CSV output path (overrides output_csv in the configuration).",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Skip saving design-search plots.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = _parse_args()
    main(
        config_path=arguments.config,
        output_path=arguments.output,
        generate_plots=not arguments.no_plots,
    )
