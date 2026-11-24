
"""
JET FAN - PRELIMINARY DESIGN
Thrust Issues

Mach number plot
"""

import csv
from pathlib import Path

import matplotlib.pyplot as plt
from main import main

risultati = main()

triangles = risultati["triangles"]
airfoil = risultati["airfoil_result"]
sezioni = airfoil["sezioni_radiali"]

PROJECT_DIR = Path(__file__).resolve().parent


def plot_mach_number(
    csv_path=None,
    mach_limit=0.3,
    output_path=None
):
    """
    Plot the maximum Mach number against specific speed.

    Data source: preliminary_results.csv
    """

    if csv_path is None:
        csv_path = PROJECT_DIR / "preliminary_results.csv"

    if output_path is None:
        output_path = PROJECT_DIR / "mach_check.png"

    # Read Preliminary Design results
    with open(csv_path, "r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        results = list(reader)

    if not results:
        raise ValueError("The results CSV file is empty.")

    omega_s = [
        float(row["omega_s"])
        for row in results
    ]

    mach_relative = [
        float(row["mach_relative"])
        for row in results
    ]

    mach_absolute = [
        float(row["mach_absolute"])
        for row in results
    ]

    mach_max = [
        float(row["mach_max"])
        for row in results
    ]

    # Create figure
    fig, ax = plt.subplots(figsize=(9, 5.5))

    ax.plot(
        omega_s,
        mach_relative,
        label="Maximum relative Mach",
        linewidth=2
    )

    ax.plot(
        omega_s,
        mach_absolute,
        label="Maximum absolute Mach",
        linewidth=2
    )

    ax.plot(
        omega_s,
        mach_max,
        label="Overall maximum Mach",
        linewidth=2.5
    )

    ax.axhline(
        y=mach_limit,
        color="red",
        linestyle="--",
        linewidth=2,
        label=f"Mach limit = {mach_limit}"
    )

    ax.set_title(
        "Mach Number Verification",
        fontsize=14
    )

    ax.set_xlabel(
        "Specific speed",
        fontsize=12
    )

    ax.set_ylabel(
        "Mach number [-]",
        fontsize=12
    )

    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=10)

    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)

    print(f"Mach number plot saved to: {output_path}")


if __name__ == "__main__":

    from main import main

    risultati = main()

    triangles = risultati["triangles"]

    sezioni = sorted(
        triangles.values(),
        key=lambda s: s["radius"]
    )

    r = [s["radius"] for s in sezioni]
    U = [s["U"] for s in sezioni]

    span = [
        100 * (ri - r[0]) / (r[-1] - r[0])
        for ri in r
    ]

    plt.plot(span, U, marker="o")
    plt.xlabel("Blade span [%]")
    plt.ylabel("Peripheral velocity [m/s]")
    plt.title("Peripheral Velocity Distribution")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("peripheral_velocity.png", dpi=300)

    # VELOCITY TRIANGLES

    fig, axes = plt.subplots(3, 3, figsize=(15, 12))

    for ax, (name, s) in zip(axes.flat, triangles.items()):

        U = s["U"]
        Cm = s["c_m"]
        Cu2 = s["c_theta2"]

        # Absolute velocities
        ax.quiver(0, 0, 0, Cm, color="blue",
                  angles="xy", scale_units="xy", scale=1,
                  label="C1")

        ax.quiver(0, 0, Cu2, Cm, color="cyan",
                  angles="xy", scale_units="xy", scale=1,
                  label="C2")

        # Peripheral velocity
        ax.quiver(0, 0, U, 0, color="red",
                  angles="xy", scale_units="xy", scale=1,
                  label="U")

        # Relative velocities
        ax.quiver(U, 0, -U, Cm, color="green",
                  angles="xy", scale_units="xy", scale=1,
                  label="W1")

        ax.quiver(U, 0, Cu2-U, Cm, color="orange",
                  angles="xy", scale_units="xy", scale=1,
                  label="W2")

        ax.set_title(name)
        ax.set_aspect("equal")
        ax.set_xlim(-5, max(t["U"] for t in triangles.values()) + 10)
        ax.set_ylim(-5, Cm + 10)
        ax.set_xlabel("Tangential velocity [m/s]")
        ax.set_ylabel("Axial velocity [m/s]")
        ax.grid(True)
        ax.legend(loc="upper right", fontsize=8)

    fig.suptitle("Velocity Triangles - Radial Sections")
    fig.tight_layout()
    fig.savefig("velocity_triangles.png", dpi=300)

    # ABSOLUTE VELOCITY DISTRIBUTION

    c1 = [s["c1"] for s in sezioni]
    c2 = [s["c2"] for s in sezioni]
    c3 = [s["c3"] for s in sezioni]

    fig, ax = plt.subplots(figsize=(8, 5))

    ax.plot(span, c1, marker="o", label="C1")
    ax.plot(span, c2, marker="o", label="C2")
    ax.plot(span, c3, marker="o", label="C3")

    ax.set_xlabel("Blade span [%]")
    ax.set_ylabel("Absolute velocity [m/s]")
    ax.set_title("Absolute Velocity Distribution")
    ax.grid(True)
    ax.legend()

    fig.tight_layout()
    fig.savefig("absolute_velocity_distribution.png", dpi=300)


    # RELATIVE VELOCITY DISTRIBUTION

    w1 = [s["w1"] for s in sezioni]
    w2 = [s["w2"] for s in sezioni]

    fig, ax = plt.subplots(figsize=(8, 5))

    ax.plot(span, w1, marker="o", label="W1")
    ax.plot(span, w2, marker="o", label="W2")

    ax.set_xlabel("Blade span [%]")
    ax.set_ylabel("Relative velocity [m/s]")
    ax.set_title("Relative Velocity Distribution")
    ax.grid(True)
    ax.legend()

    fig.tight_layout()
    fig.savefig("relative_velocity_distribution.png", dpi=300)

    # SPECIFIC EULER WORK DISTRIBUTION

    L_euler = [s["U"] * s["c_theta2"] for s in sezioni]

    fig, ax = plt.subplots(figsize=(8, 5))

    ax.plot(span, L_euler, marker="o", label="Euler work")

    ax.set_xlabel("Blade span [%]")
    ax.set_ylabel("Specific Euler work [J/kg]")
    ax.set_title("Specific Euler Work Distribution")
    ax.set_ylim(0, 1.2 * max(L_euler))
    ax.grid(True)
    ax.legend()

    fig.tight_layout()
    fig.savefig("euler_work_distribution.png", dpi=300)

    c_theta2 = [s["c_theta2"] for s in sezioni]
    r_times_ctheta2 = [s["radius"] * s["c_theta2"] for s in sezioni]

    # FREE VORTEX CHECK

    fig, ax = plt.subplots(figsize=(8, 5))

    ax.plot(span, r_times_ctheta2, marker="o", label="r * C_theta2")

    ax.set_xlabel("Blade span [%]")
    ax.set_ylabel("r * C_theta2 [m^2/s]")
    ax.set_title("Free Vortex Verification")
    ax.grid(True)
    ax.legend()

    fig.tight_layout()
    fig.savefig("free_vortex_check.png", dpi=300)

    # SOLIDITY DISTRIBUTION

    airfoil = risultati["airfoil_result"]

    sezioni_airfoil = sorted(
        airfoil["sezioni_radiali"].values(),
        key=lambda s: s["radius"]
    )

    sigma = [s["sigma"] for s in sezioni_airfoil]

    fig, ax = plt.subplots(figsize=(8, 5))

    ax.plot(span, sigma, marker="o", label="Solidity")

    ax.set_xlabel("Blade span [%]")
    ax.set_ylabel("Solidity [-]")
    ax.set_title("Solidity Distribution")
    ax.grid(True)
    ax.legend()

    fig.tight_layout()
    fig.savefig("solidity_distribution.png", dpi=300)

    # STAGGER ANGLE DISTRIBUTION

    gamma = [s["calettamento_deg"] for s in sezioni_airfoil]

    fig, ax = plt.subplots(figsize=(8, 5))

    ax.plot(span, gamma, marker="o", label="Stagger angle")

    ax.set_xlabel("Blade span [%]")
    ax.set_ylabel("Stagger angle [deg]")
    ax.set_title("Stagger Angle Distribution")
    ax.grid(True)
    ax.legend()

    fig.tight_layout()
    fig.savefig("stagger_angle_distribution.png", dpi=300)

    # DIFFUSION FACTOR DISTRIBUTION

    D = [s["D"] for s in sezioni_airfoil]
    D_max = risultati["airfoil_inputs"]["D_max"]

    fig, ax = plt.subplots(figsize=(8, 5))

    ax.plot(span, D, marker="o", label="Diffusion Factor")

    ax.axhline(y=D_max, color="red", linestyle="--",
               label=f"Design limit = {D_max}")

    ax.set_xlabel("Blade span [%]")
    ax.set_ylabel("Diffusion Factor [-]")
    ax.set_title("Diffusion Factor Distribution")
    ax.set_ylim(0, 1.2 * max(D_max, max(D)))
    ax.grid(True)
    ax.legend()

    fig.tight_layout()
    fig.savefig("diffusion_factor_distribution.png", dpi=300)


    # INCIDENCE AND DEVIATION DISTRIBUTION

    incidence = [s["incidenza_deg"] for s in sezioni_airfoil]
    deviation = [s["deviazione_deg"] for s in sezioni_airfoil]

    fig, ax = plt.subplots(figsize=(8, 5))

    ax.plot(span, incidence, marker="o", label="Incidence")
    ax.plot(span, deviation, marker="s", label="Deviation")

    ax.set_xlabel("Blade span [%]")
    ax.set_ylabel("Angle [deg]")
    ax.set_title("Incidence and Deviation Distribution")
    ax.grid(True)
    ax.legend()

    fig.tight_layout()
    fig.savefig("incidence_deviation_distribution.png", dpi=300)

    plt.show()



    plt.show()







