
"""
JET FAN - PRELIMINARY DESIGN
Thrust Issues

Mach number plot
"""

import csv
from pathlib import Path

import matplotlib.pyplot as plt


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

    import yaml

    with open(
        PROJECT_DIR / "config.yaml",
        "r",
        encoding="utf-8"
    ) as file:
        config = yaml.safe_load(file)

    plot_mach_number(
        mach_limit=config["max_mach_number"]
    )
