import numpy as np
from data.loss_charts import evaluate_theta_l

# Genera 10 valori equidistanti tra 1.0 e 2.2
dr_range = np.linspace(1.0, 2.2, 10)

print("=== SCANSIONE CONTINUA DR vs THETA/L ===")
for dr in dr_range:
    print(f"DR = {dr:.3f} -> theta/l = {evaluate_theta_l(dr):.4f}")