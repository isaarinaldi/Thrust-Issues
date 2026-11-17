"""Interface and integration checks for updated preliminary -> airfoil."""

import math

import pytest

from airfoil_design.airfoil_inputs import prepara_input_airfoil
from airfoil_design.airfoil_machine import calcola_diffusion_factor


def test_angle_conversion_mach_and_re():
    triangles = {
        "Hub": {"radius": 0.3},
        "Mean": {
            "radius": 0.45,
            "c1": 32.0, "c2": 34.0, "w1": 61.0, "w2": 52.0,
            "beta1": 32.0, "beta2": 38.0,
        },
        "Tip": {"radius": 0.6},
    }
    result = prepara_input_airfoil(
        triangles,
        {"AR": 2.2, "sigma_prog": 1.0},
        speed_of_sound=343.0,
        air_density=1.2,
        dynamic_viscosity=1.81e-5,
    )

    assert result["beta1"] == pytest.approx(58.0)
    assert result["beta2"] == pytest.approx(52.0)
    assert result["Ma"] == pytest.approx(61.0 / 343.0)
    assert result["Re"] == pytest.approx(
        1.2 * 61.0 * ((0.6 - 0.3) / 2.2) / 1.81e-5
    )


def test_diffusion_factor_with_axial_beta():
    data = {
        "W1": 61.0, "W2": 52.0,
        "beta1": 58.0, "beta2": 52.0,
        "sigma_prog": 1.0,
    }
    delta_w_theta = abs(
        52.0 * math.sin(math.radians(52.0))
        - 61.0 * math.sin(math.radians(58.0))
    )
    expected = 1 - 52 / 61 + delta_w_theta / (2 * 61)
    assert calcola_diffusion_factor(data) == pytest.approx(expected)


def test_integrated_airfoil_smoke():
    from run_airfoil_integrated import run_integrated_airfoil

    result = run_integrated_airfoil()
    assert result["airfoil_verified"] is True
    assert result["airfoil_inputs"]["Ma"] > 0
    assert result["airfoil_inputs"]["Re"] > 0
    assert result["preliminary"]["continuity"]["continuity_ok"]
