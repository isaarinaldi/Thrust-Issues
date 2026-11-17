"""Compatibility entry point for the integrated NACA65 design.

The original script relied on an undefined global `triangles`; delegate to
the single verified orchestration path instead.
"""

from run_airfoil_integrated import run_integrated_airfoil


if __name__ == "__main__":
    run_integrated_airfoil()
