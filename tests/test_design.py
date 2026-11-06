
import math
import pytest

from machine import preliminary_design
from thermo import operating_point


# ==========================================
# REFERENCE OPERATING CONDITIONS
# ==========================================

Q, gH, L, P = operating_point(
    nominal_thrust=1000.0,
    air_density=1.2,
    jet_velocity=30.0,
    ambient_velocity=0.0,
    rotor_efficiency=0.8,
)


def get_design(omega_s=5.0):

    return preliminary_design(
        omega_s=omega_s,
        flow_rate=Q,
        specific_head=gH,
        specific_work=L,
        work_done_factor=1.0,
        tip_diameter=1.194,
        max_tip_diameter=1.2,
        speed_of_sound=343.0,
        mach_limit=0.3,
        section_count=21,
    )


# ==========================================
# TEST 1 - CONTINUITY
# ==========================================

def test_continuity():

    design = get_design()

    D_tip = design["D_tip_m"]
    D_hub = design["D_hub_m"]
    c_m = design["c_m_m_s"]

    area = math.pi / 4 * (
        D_tip**2 - D_hub**2
    )

    Q_calculated = area * c_m

    assert Q_calculated == pytest.approx(
        Q, rel=1e-10
    )


# ==========================================
# TEST 2 - DIAMETER CONSTRAINT
# ==========================================

def test_diameter_constraint():

    design = get_design()

    D_hub = design["D_hub_m"]
    D_tip = design["D_tip_m"]
    D_max = 1.2

    assert 0 < D_hub < D_tip <= D_max


# ==========================================
# TEST 3 - MACH CONSTRAINT
# ==========================================

def test_mach_constraint():

    design = get_design()

    assert design["mach_max"] < 0.3
    assert design["status"] == "PASS"
