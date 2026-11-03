
"""
JET FAN - THERMODYNAMIC AND ENERGY MODEL
Thrust Issues

Simplified momentum and energy calculations.
Pressure thrust is neglected.
"""

import math
from collections.abc import Mapping

from losses import calculate_specific_work


def air_properties(config: Mapping[str, object]) -> tuple[float, float]:
    """Return density [kg/m³] and speed of sound [m/s] from configuration."""
    model = config.get("thermo_model", "perfect_gas")
    if not isinstance(model, str):
        raise ValueError("thermo_model must be a string.")

    pressure = _positive_number(config, "pressure_Pa")
    temperature = _positive_number(config, "air_temperature_K")

    if model == "perfect_gas":
        gas_constant = _positive_number(config, "gas_constant_J_kg_K")
        gamma = _positive_number(config, "specific_heat_ratio")
        if gamma <= 1:
            raise ValueError("specific_heat_ratio must be greater than 1.")
        return (
            pressure / (gas_constant * temperature),
            math.sqrt(gamma * gas_constant * temperature),
        )

    if model == "CoolProp":
        fluid = config.get("coolprop_fluid", "Air")
        if not isinstance(fluid, str) or not fluid.strip():
            raise ValueError("coolprop_fluid must be a non-empty string.")
        try:
            from CoolProp.CoolProp import PropsSI
        except ImportError as error:
            raise ImportError(
                "thermo_model is CoolProp, but CoolProp is not installed."
            ) from error
        try:
            density = float(PropsSI("D", "P", pressure, "T", temperature, fluid))
            speed_of_sound = float(PropsSI("A", "P", pressure, "T", temperature, fluid))
        except (ValueError, RuntimeError) as error:
            raise ValueError(
                f"CoolProp could not calculate properties for {fluid!r} "
                f"at {pressure:g} Pa and {temperature:g} K."
            ) from error
        _require_positive_finite("air density", density)
        _require_positive_finite("speed of sound", speed_of_sound)
        return density, speed_of_sound

    raise ValueError("thermo_model must be 'perfect_gas' or 'CoolProp'.")


def _positive_number(config: Mapping[str, object], key: str) -> float:
    value = config.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Configuration value {key!r} must be a number.")
    number = float(value)
    _require_positive_finite(key, number)
    return number


def _require_positive_finite(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be positive and finite.")


def operating_point(
    nominal_thrust: float,
    air_density: float,
    jet_velocity: float,
    ambient_velocity: float,
    rotor_efficiency: float,
) -> tuple[float, float, float, float]:
    """
    Calculate the preliminary operating point.

    Returns:
        flow_rate       [m3/s]
        specific_head   [J/kg]
        specific_work   [J/kg]
        rotor_power     [W]
    """

    for name, value in (
        ("nominal thrust", nominal_thrust),
        ("air density", air_density),
        ("jet velocity", jet_velocity),
        ("rotor efficiency", rotor_efficiency),
    ):
        _require_positive_finite(name, value)
    if not math.isfinite(ambient_velocity) or ambient_velocity < 0:
        raise ValueError("Ambient velocity must be finite and non-negative.")
    if jet_velocity <= ambient_velocity:
        raise ValueError("Jet velocity must exceed ambient velocity.")
    if rotor_efficiency > 1:
        raise ValueError("Rotor efficiency must be at most 1.")

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
    max_relative_speed: float,
    max_absolute_speed: float,
    speed_of_sound: float,
) -> tuple[float, float, float]:
    """
    Calculate relative and absolute Mach numbers.
    """
    for name, value in (
        ("maximum relative speed", max_relative_speed),
        ("maximum absolute speed", max_absolute_speed),
        ("speed of sound", speed_of_sound),
    ):
        _require_positive_finite(name, value)

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
