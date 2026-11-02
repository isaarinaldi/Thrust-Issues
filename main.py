import math
from collections.abc import Mapping
from pathlib import Path

import yaml


def _read_number(config: Mapping[str, object], key: str) -> float:
    try:
        value = config[key]
    except KeyError:
        raise ValueError(f"Missing required configuration value: {key}") from None

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Configuration value {key!r} must be a number.")
    try:
        number = float(value)
    except OverflowError:
        raise ValueError(f"Configuration value {key!r} must be finite.") from None
    if not math.isfinite(number):
        raise ValueError(f"Configuration value {key!r} must be finite.")
    return number


def _print_velocity_triangles(
    config: Mapping[str, object], flow_rate: float, specific_work: float, omega: float
) -> None:
    work_done_factor = _read_number(config, "work_done_factor")
    tip_diameter = _read_number(config, "tip_diameter_m")
    hub_to_tip_ratio = _read_number(config, "hub_to_tip_ratio")
    section_count_value = _read_number(config, "number_of_sections")
    max_tip_diameter = _read_number(config, "max_tip_diameter_m")
    speed_of_sound = _read_number(config, "speed_of_sound_m_s")
    max_mach_number = _read_number(config, "max_mach_number")

    if work_done_factor <= 0:
        raise ValueError("work_done_factor must be greater than zero.")
    if tip_diameter <= 0 or tip_diameter > max_tip_diameter:
        raise ValueError(
            "tip_diameter_m must be greater than zero and at most max_tip_diameter_m."
        )
    if not 0 < hub_to_tip_ratio < 1:
        raise ValueError("hub_to_tip_ratio must be greater than zero and less than one.")
    if not section_count_value.is_integer() or section_count_value < 2:
        raise ValueError("number_of_sections must be an integer of at least two.")
    if speed_of_sound <= 0 or max_mach_number <= 0:
        raise ValueError("speed_of_sound_m_s and max_mach_number must be positive.")

    section_count = int(section_count_value)
    r_tip = tip_diameter / 2
    r_hub = hub_to_tip_ratio * r_tip
    annulus_area = math.pi * (r_tip**2 - r_hub**2)
    c_m = flow_rate / annulus_area
    u_tip = omega * r_tip
    c_theta2_tip = specific_work / (work_done_factor * u_tip)
    radii = (
        r_hub + (r_tip - r_hub) * index / (section_count - 1)
        for index in range(section_count)
    )

    print("\nFREE-VORTEX VELOCITY TRIANGLES")
    print("\nMACH NUMBER VERIFICATION")
    for index, radius in enumerate(radii):
        blade_speed = omega * radius
        c_theta2 = c_theta2_tip * r_tip / radius
        w1 = math.hypot(c_m, blade_speed)
        w2 = math.hypot(c_m, blade_speed - c_theta2)
        w_mean = math.hypot(c_m, blade_speed - c_theta2 / 2)
        beta1 = math.degrees(math.atan2(c_m, blade_speed))
        beta2 = math.degrees(math.atan2(c_m, blade_speed - c_theta2))

        print(f"\nSECTION {index + 1}")
        print(f"Radius: {radius:.3f} m")
        print(f"Peripheral speed: {blade_speed:.2f} m/s")
        print(f"Outlet swirl: {c_theta2:.2f} m/s")
        print(f"Inlet relative velocity: {w1:.2f} m/s")
        print(f"Outlet relative velocity: {w2:.2f} m/s")
        print(f"Mean relative velocity: {w_mean:.2f} m/s")
        print(f"Beta 1: {beta1:.2f} deg")
        print(f"Beta 2: {beta2:.2f} deg")

        mach_inlet = w1 / speed_of_sound
        mach_outlet = w2 / speed_of_sound
        max_relative_mach = max(mach_inlet, mach_outlet)
        print(f"Inlet Mach number: {mach_inlet:.3f}")
        print(f"Outlet Mach number: {mach_outlet:.3f}")
        print(f"Maximum relative Mach number: {max_relative_mach:.3f}")
        if max_relative_mach >= max_mach_number:
            raise ValueError(
                f"Mach number limit exceeded at section {index + 1}."
            )

        work_check = work_done_factor * blade_speed * c_theta2
        if not math.isclose(specific_work, work_check, rel_tol=1e-9):
            raise ValueError(f"Euler work check failed at section {index + 1}.")

    print("\nMach number check: PASSED")


def main(config_path: Path | None = None) -> None:
    if config_path is None:
        config_path = Path(__file__).resolve().with_name("config.yaml")

    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)
    if not isinstance(config, Mapping):
        raise ValueError(
            f"Configuration file {config_path} must contain a YAML mapping."
        )

    F_nom = _read_number(config, "nominal_thrust_N")
    rho = _read_number(config, "air_density_kg_m3")
    V_j = _read_number(config, "jet_velocity_m_s")
    V_amb = _read_number(config, "ambient_velocity_m_s")
    eta_rotor = _read_number(config, "rotor_efficiency_initial")
    Omega_s = _read_number(config, "specific_speed")

    if F_nom <= 0:
        raise ValueError("nominal_thrust_N must be greater than zero.")
    if rho <= 0:
        raise ValueError("air_density_kg_m3 must be greater than zero.")
    if V_amb < 0 or V_j <= V_amb:
        raise ValueError(
            "Velocities must satisfy 0 <= ambient_velocity_m_s < jet_velocity_m_s."
        )
    if not 0 < eta_rotor <= 1:
        raise ValueError(
            "rotor_efficiency_initial must be greater than 0 and at most 1."
        )
    if Omega_s <= 0:
        raise ValueError("specific_speed must be greater than zero.")

    # This momentum-only thrust model assumes equal inlet and outlet static
    # pressures, so pressure thrust is neglected.
    delta_V = V_j - V_amb
    mean_velocity = V_j / 2 + V_amb / 2
    try:
        # Sequential division and the factored head avoid unnecessary
        # intermediate overflow and cancellation.
        Q = F_nom / rho / delta_V
        gH = delta_V * mean_velocity
        L = gH / eta_rotor
        P_rotor = F_nom * mean_velocity / eta_rotor

        # Dimensionless SI convention: Omega_s = omega * sqrt(Q) / gH**0.75.
        omega = Omega_s * (gH**0.75) / math.sqrt(Q)
        n_rpm = omega * 60 / (2 * math.pi)
    except (OverflowError, ZeroDivisionError) as error:
        raise ValueError(
            "Configuration values produce a result outside the supported numeric range."
        ) from error

    for name, result in (
        ("volumetric flow rate", Q),
        ("specific head", gH),
        ("specific work", L),
        ("rotor power", P_rotor),
        ("angular velocity", omega),
        ("rotational speed", n_rpm),
    ):
        if not math.isfinite(result) or result <= 0:
            raise ValueError(
                f"Configuration values produce an invalid {name}; "
                "check their magnitudes."
            )

    print("JET FAN - PRELIMINARY DESIGN")
    print(f"Nominal thrust: {F_nom:.1f} N")
    print("Pressure thrust: neglected (equal inlet/outlet static pressure assumed)")
    print(f"Volumetric flow rate: {Q:.2f} m³/s")
    print(f"Specific head: {gH:.2f} J/kg")
    print(f"Specific work: {L:.2f} J/kg")
    print(f"Preliminary rotor power: {P_rotor / 1000:.2f} kW")
    print(f"Specific speed: {Omega_s:.2f}")
    print(f"Angular velocity: {omega:.2f} rad/s")
    print(f"Rotational speed: {n_rpm:.2f} rpm")
    _print_velocity_triangles(config, Q, L, omega)


if __name__ == "__main__":
    main()
