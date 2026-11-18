# Integrazione Jet Fan -> NACA 65 (branch di revisione)

Questo branch collega l'attuale `main.py` al modulo `airfoil_design` senza
modificare la logica del dimensionamento preliminare dei colleghi.

## Esecuzione

```bash
pip install -r requirements.txt
python main.py                 # algoritmo preliminare originale
python run_airfoil_integrated.py  # preliminare + NACA 65
python -m pytest tests/test_airfoil_integration.py
```

`check_airfoil_connection.py` resta utilizzabile come alias del nuovo
comando integrato.

## Interfaccia
- `main.main()` restituisce ora un dizionario con il punto operativo,
  la geometria, la continuita' e i triangoli. Le stampe originali non
  cambiano; il nuovo valore di ritorno non influisce su `python main.py`.
- `prepara_input_airfoil()` estrae la sezione media e converte beta
  tangenziale in beta assiale con `90 - beta`.
- Mach in ingresso al rotore = `W1/speed_of_sound`.
- Reynolds preliminare = `rho * W1 * chord / mu`, con
  `chord = (rtip - rhub)/AR`.
- Il Diffusion Factor usa la differenza tangenziale corretta,
  `|W2*sin(beta2) - W1*sin(beta1)|`, dato che beta e' assiale.

## Limiti e verifiche da completare
- La progettazione NACA 65 e' attualmente sulla sola sezione media; occorre
  estenderla radialmente prima di considerare validata la pala 3D.
- I coefficienti di Lieblein sono interpolati dai CSV esistenti; la loro
  provenienza e accuratezza devono essere documentate e controllate.
- Le prestazioni `main_performance.py` e i test storici contengono API
  non allineate al `machine.py` aggiornato: NON sono stati modificati.
- Questo branch non e' una validazione sperimentale o CFD.
