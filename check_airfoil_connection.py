
import yaml
from pathlib import Path

from main import main as preliminary_main
from airfoil_design.airfoil_inputs import prepara_input_airfoil
from airfoil_design.airfoil_main import esegui_airfoil

# ESECUZIONE DEL CODICE PRELIMINARE
preliminary_main()

if triangles is None:
    raise ValueError("Nessuna configurazione preliminare valida")

# LETTURA DELLA CONFIGURAZIONE AIRFOIL
percorso = Path(__file__).parent / "airfoil_design" / "airfoil_config.yaml"

with percorso.open("r", encoding="utf-8") as file:
    config_airfoil = yaml.safe_load(file)

# COLLEGAMENTO TRA I DUE ALGORITMI
dati_airfoil = prepara_input_airfoil(triangles, config_airfoil)

print("\nINPUT RICEVUTI DALL'ALGORITMO PRELIMINARE")

for nome in ("C1", "C2", "W1", "W2", "beta1", "beta2",
             "Ma", "rhub", "rm", "rtip"):
    print(nome, "=", round(dati_airfoil[nome], 4))

# ESECUZIONE DEL DIMENSIONAMENTO AERODINAMICO

print("\nAVVIO PROGETTAZIONE PROFILO ALARE")

esegui_airfoil(dati_airfoil)
