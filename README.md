# Thrust-Issues

Run the preliminary design with `python main.py`. Inputs are read from
`config.yaml`; the speed search results are written to `preliminary_results.csv`.

The calculation assumes equal inlet and outlet static pressures, so pressure
thrust is neglected. The digitized Eckert coefficients are approximate, and
the Mach-number and geometry checks are preliminary screening criteria rather
than a validated aerodynamic design.